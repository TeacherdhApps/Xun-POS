#!/usr/bin/env python3
import json
import os
import platform
import sys
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, ttk
import backup_manager

# Prevent execution on Windows OS
if platform.system() == "Windows":
    print("=" * 60)
    print("ERROR: Esta aplicación no es compatible con Windows")
    print("=" * 60)
    print("\nEste sistema POS está diseñado exclusivamente para sistemas Unix")
    print("(Linux, macOS, BSD, etc.) y no puede ejecutarse en Windows.")
    print("\nPor favor, utilice un sistema Linux o macOS para ejecutar esta aplicación.")
    print("=" * 60)
    sys.exit(1)


class SettingsApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Configuración de Tienda")
        self.geometry("800x600")
        self.is_fullscreen = False  # Track fullscreen state
        
        # Base directory for absolute paths
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.settings_file = os.path.join(self.base_dir, "settings.json")

        self.create_styles()
        self.create_widgets()
        self.load_settings()

        # Bind F11 for fullscreen toggle
        self.bind("<F11>", self.toggle_fullscreen)

    def create_styles(self):
        """Configure ttk styles."""
        style = ttk.Style(self)
        style.theme_use("clam")

        # Palette
        BG_COLOR = "#F0F0F0"
        TEXT_COLOR = "#212529"
        ACCENT_COLOR = "#007BFF"
        SUCCESS_COLOR = "#28A745"
        WHITE = "#FFFFFF"
        BLACK = "#1A1A1A"

        # General styles
        self.configure(bg=BG_COLOR)
        style.configure("TFrame", background=BG_COLOR)
        style.configure(
            "TLabel",
            background=BG_COLOR,
            foreground=TEXT_COLOR,
            font=("Arial", 16, "bold"),
        )
        style.configure("TButton", font=("Arial", 14, "bold"), padding=12)
        style.map(
            "TButton",
            background=[("active", "#EAEAEA")],
            foreground=[("active", BLACK)],
        )
        style.configure(
            "TEntry", font=("Arial", 18), fieldbackground=WHITE, foreground=TEXT_COLOR
        )

        # Custom Button styles
        style.configure("Accent.TButton", foreground=WHITE, background=ACCENT_COLOR)
        style.map("Accent.TButton", background=[("active", "#0056b3")])

        style.configure(
            "Success.TButton",
            foreground=WHITE,
            background=SUCCESS_COLOR,
            font=("Arial", 16, "bold"),
            padding=15,
        )
        style.map("Success.TButton", background=[("active", "#218838")])

        # Black Exit button
        style.configure(
            "Exit.TButton",
            foreground=WHITE,
            background="#000000",
            font=("Arial", 16, "bold"),
            padding=15,
        )
        style.map("Exit.TButton", background=[("active", "#333333")])

    def toggle_fullscreen(self, event=None):
        """Toggle fullscreen mode with F11."""
        self.is_fullscreen = not self.is_fullscreen
        self.attributes("-fullscreen", self.is_fullscreen)
        return "break"

    def create_widgets(self):
        # Title
        title_frame = ttk.Frame(self, padding="10")
        title_frame.pack(fill=tk.X)
        
        # Header Info Label
        info_label = ttk.Label(
            title_frame,
            text="@Xun-POS",
            font=("Arial", 8),
            foreground="#666666",
        )
        info_label.pack(side=tk.RIGHT, anchor=tk.NE)

        ttk.Label(
            title_frame, text="Configuración de Tienda", font=("Arial", 24, "bold")
        ).pack(side=tk.LEFT, padx=10, pady=10)

        main_frame = ttk.Frame(self, padding="30")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Entry fields
        fields = {
            "logo_path": "Logo:",
            "business_name": "Nombre Negocio:",
            "address": "Dirección:",
            "phone": "Teléfono:",
            "cashier_name": "Nombre Cajero:",
        }

        self.entries = {}
        vcmd = (self.register(self.validate_phone), "%P")

        for i, (key, text) in enumerate(fields.items()):
            label = ttk.Label(main_frame, text=text, font=("Arial", 16, "bold"))
            label.grid(row=i, column=0, sticky="w", padx=10, pady=15)

            if key == "logo_path":
                self.logo_frame = ttk.Frame(main_frame)
                self.logo_frame.grid(row=i, column=1, sticky="ew", padx=10, pady=15)
                self.entries[key] = ttk.Label(
                    self.logo_frame,
                    text="No seleccionado",
                    anchor="w",
                    font=("Arial", 14),
                )
                self.entries[key].pack(side=tk.LEFT, expand=True, fill=tk.X)
                logo_button = ttk.Button(
                    self.logo_frame,
                    text="Seleccionar...",
                    command=self.select_logo,
                    style="Accent.TButton",
                )
                logo_button.pack(side=tk.RIGHT)
            else:
                self.entries[key] = ttk.Entry(main_frame, font=("Arial", 18))
                if key == "phone":
                    self.entries[key].config(validate="key", validatecommand=vcmd)
                self.entries[key].grid(row=i, column=1, sticky="ew", padx=10, pady=15)

        main_frame.columnconfigure(1, weight=1)

        # Data Tools section
        tools_row = len(fields)
        ttk.Label(main_frame, text="Respaldo de Datos:", font=("Arial", 16, "bold")).grid(
            row=tools_row, column=0, sticky="w", padx=10, pady=15
        )

        tools_frame = ttk.Frame(main_frame)
        tools_frame.grid(row=tools_row, column=1, sticky="ew", padx=10, pady=15)

        ttk.Button(
            tools_frame,
            text="Crear Respaldo",
            command=self.run_backup,
            style="Accent.TButton",
        ).pack(side=tk.LEFT, padx=(0, 10))

        ttk.Button(
            tools_frame,
            text="Restaurar Respaldo",
            command=self.run_restore,
            style="Accent.TButton",
        ).pack(side=tk.LEFT)

        # Buttons frame
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.grid(row=tools_row + 1, column=0, columnspan=2, pady=30)
        buttons_frame.columnconfigure(0, weight=1)
        buttons_frame.columnconfigure(1, weight=1)

        # Save button
        save_button = ttk.Button(
            buttons_frame,
            text="Guardar Configuración",
            command=self.save_settings,
            style="Success.TButton",
        )
        save_button.grid(row=0, column=0, padx=10, sticky="ew")

        # Exit button with F12
        exit_button = ttk.Button(
            buttons_frame,
            text="F12 - Salir",
            command=self.exit_app,
            style="Exit.TButton",
        )
        exit_button.grid(row=0, column=1, padx=10, sticky="ew")

        # Bind F12 key
        self.bind("<F12>", lambda e: self.exit_app())
        # Bind Enter keys to save
        self.bind("<Return>", lambda e: self.save_settings())
        self.bind("<KP_Enter>", lambda e: self.save_settings())

    def validate_phone(self, P):
        if P.isdigit() or P == "":
            return True
        return False

    def select_logo(self):
        file_path = filedialog.askopenfilename(
            title="Seleccionar Archivo de Logo",
            filetypes=(
                ("Archivos de imagen", "*.png *.jpg *.jpeg *.gif *.bmp"),
                ("Todos los archivos", "*.* "),
            ),
        )
        if file_path:
            self.entries["logo_path"].config(text=file_path)

    def load_settings(self):
        if not os.path.exists(self.settings_file):
            return

        with open(self.settings_file, "r", encoding="utf-8") as f:
            settings = json.load(f)

        for key, widget in self.entries.items():
            if key in settings:
                if isinstance(widget, ttk.Entry):
                    widget.delete(0, tk.END)
                    widget.insert(0, settings[key])
                elif isinstance(widget, ttk.Label):
                    widget.config(text=settings[key] or "No seleccionado")

    def run_backup(self):
        filename = f"respaldo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        dest_path = filedialog.asksaveasfilename(
            title="Guardar Respaldo",
            initialfile=filename,
            defaultextension=".zip",
            filetypes=[("Archivos ZIP", "*.zip")]
        )
        if dest_path:
            success, message = backup_manager.create_backup(self.base_dir, dest_path)
            if success:
                messagebox.showinfo("Éxito", message)
            else:
                messagebox.showerror("Error", message)

    def run_restore(self):
        if not messagebox.askyesno("Confirmar Restauración",
            "¿Está seguro de que desea restaurar un respaldo? Esto sobrescribirá todos sus datos actuales."):
            return

        src_path = filedialog.askopenfilename(
            title="Seleccionar Respaldo",
            filetypes=[("Archivos ZIP", "*.zip")]
        )
        if src_path:
            success, message = backup_manager.restore_backup(self.base_dir, src_path)
            if success:
                messagebox.showinfo("Éxito", message)
                # Reload settings in case they were restored
                self.load_settings()
            else:
                messagebox.showerror("Error", message)

    def save_settings(self):
        settings = {}
        for key, widget in self.entries.items():
            if isinstance(widget, ttk.Entry):
                settings[key] = widget.get()
            elif isinstance(widget, ttk.Label):
                settings[key] = widget.cget("text")

        try:
            with open(self.settings_file, "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=4)
            messagebox.showinfo("Éxito", "Configuración guardada exitosamente.")
        except Exception as e:
            messagebox.showerror(
                "Error", f"No se pudo guardar la configuración.\nError: {e}"
            )

    def exit_app(self):
        """Exit the application."""
        self.destroy()


if __name__ == "__main__":
    app = SettingsApp()
    app.mainloop()
