#!/usr/bin/env python3
import config
import platform
import store
import sys
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk

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

# Palette
ACCENT_COLOR = "#007BFF"
SUCCESS_COLOR = "#28A745"
DANGER_COLOR = "#DC3545"


class SettingsApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Configuración de Tienda")
        self.geometry("800x600")
        self.is_fullscreen = False  # Track fullscreen state

        self.store = store.Store()
        if config.get_mode() == "demo":
            self.title(self.title() + " [DEMO]")

        self.create_widgets()
        self.load_settings()

        # Bind F11 for fullscreen toggle
        self.bind("<F11>", self.toggle_fullscreen)

    def toggle_fullscreen(self, event=None):
        """Toggle fullscreen mode with F11."""
        self.is_fullscreen = not self.is_fullscreen
        self.attributes("-fullscreen", self.is_fullscreen)
        return "break"

    def create_widgets(self):
        # Title
        title_frame = ctk.CTkFrame(self, fg_color="transparent")
        title_frame.pack(fill=tk.X, pady=(10, 5))

        info_label = ctk.CTkLabel(
            title_frame,
            text="@Xun-POS",
            font=("Arial", 8),
            text_color="#666666",
        )
        info_label.pack(side=tk.RIGHT, anchor=tk.NE)

        ctk.CTkLabel(
            title_frame, text="Configuración de Tienda", font=("Arial", 24, "bold")
        ).pack(side=tk.LEFT, padx=10, pady=10)

        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=30, pady=10)

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
            label = ctk.CTkLabel(main_frame, text=text, font=("Arial", 16, "bold"))
            label.grid(row=i, column=0, sticky="w", padx=10, pady=15)

            if key == "logo_path":
                self.logo_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
                self.logo_frame.grid(row=i, column=1, sticky="ew", padx=10, pady=15)
                self.entries[key] = ctk.CTkLabel(
                    self.logo_frame,
                    text="No seleccionado",
                    anchor="w",
                    font=("Arial", 14),
                )
                self.entries[key].pack(side=tk.LEFT, expand=True, fill=tk.X)
                logo_button = ctk.CTkButton(
                    self.logo_frame,
                    text="Seleccionar...",
                    command=self.select_logo,
                    fg_color=ACCENT_COLOR,
                    hover_color="#0056b3",
                    font=("Arial", 12, "bold"),
                    width=120,
                )
                logo_button.pack(side=tk.RIGHT)
            else:
                self.entries[key] = ctk.CTkEntry(main_frame, font=("Arial", 14))
                if key == "phone":
                    self.entries[key].configure(validate="key", validatecommand=vcmd)
                self.entries[key].grid(row=i, column=1, sticky="ew", padx=10, pady=15)

        main_frame.columnconfigure(1, weight=1)

        # Buttons frame
        buttons_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        buttons_frame.grid(row=len(fields), column=0, columnspan=2, pady=30)
        buttons_frame.columnconfigure(0, weight=1)
        buttons_frame.columnconfigure(1, weight=1)
        buttons_frame.columnconfigure(2, weight=1)
        buttons_frame.columnconfigure(3, weight=1)

        # Save button
        save_button = ctk.CTkButton(
            buttons_frame,
            text="Guardar",
            command=self.save_settings,
            fg_color=ACCENT_COLOR,
            hover_color="#0056b3",
            font=("Arial", 14, "bold"),
        )
        save_button.grid(row=0, column=0, padx=5, sticky="ew")

        # Export button
        export_button = ctk.CTkButton(
            buttons_frame,
            text="Exportar",
            command=self.export_data,
            fg_color=DANGER_COLOR,
            hover_color="#bd2130",
            font=("Arial", 14, "bold"),
        )
        export_button.grid(row=0, column=1, padx=5, sticky="ew")

        # Import button
        import_button = ctk.CTkButton(
            buttons_frame,
            text="Importar",
            command=self.import_data,
            fg_color=SUCCESS_COLOR,
            hover_color="#218838",
            font=("Arial", 14, "bold"),
        )
        import_button.grid(row=0, column=2, padx=5, sticky="ew")

        # Exit button with F12
        exit_button = ctk.CTkButton(
            buttons_frame,
            text="F12 - Salir",
            command=self.exit_app,
            fg_color="#000000",
            hover_color="#333333",
            font=("Arial", 14, "bold"),
        )
        exit_button.grid(row=0, column=3, padx=5, sticky="ew")

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
            self.entries["logo_path"].configure(text=file_path)

    def export_data(self):
        """Export the database to a zip file."""
        save_path = filedialog.asksaveasfilename(
            defaultextension=".zip",
            filetypes=[("Zip files", "*.zip")],
            title="Exportar Datos como...",
            initialfile="xun-pos-backup.zip",
        )

        if not save_path:
            return

        try:
            self.store.export_backup(save_path)
            messagebox.showinfo("Éxito", f"Datos exportados correctamente en:\n{save_path}")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudieron exportar los datos: {e}")

    def import_data(self):
        """Restore the database from a backup zip."""
        import_path = filedialog.askopenfilename(
            filetypes=[("Zip files", "*.zip")],
            title="Seleccionar archivo de datos para importar"
        )

        if not import_path:
            return

        confirm = messagebox.askyesno(
            "Confirmar Importación",
            "Esta acción reemplazará los datos actuales (productos, ventas, ajustes). ¿Desea continuar?"
        )

        if not confirm:
            return

        try:
            result = self.store.restore_backup(import_path)
            self.load_settings() # Refresh UI with new settings
            extra = (
                f"\nCopia de la base anterior: {result['previous']}"
                if result["previous"]
                else ""
            )
            messagebox.showinfo(
                "Éxito",
                "Datos importados correctamente. Reinicie la aplicación "
                f"principal si está abierta.{extra}",
            )
        except Exception as e:
            messagebox.showerror("Error", f"No se pudieron importar los datos: {e}")

    def load_settings(self):
        settings = self.store.get_settings()

        for key, widget in self.entries.items():
            if key in settings:
                if isinstance(widget, ctk.CTkEntry):
                    widget.delete(0, tk.END)
                    widget.insert(0, settings[key])
                elif isinstance(widget, ctk.CTkLabel):
                    widget.configure(text=settings[key] or "No seleccionado")

    def save_settings(self):
        settings = {}
        for key, widget in self.entries.items():
            if isinstance(widget, ctk.CTkEntry):
                settings[key] = widget.get()
            elif isinstance(widget, ctk.CTkLabel):
                settings[key] = widget.cget("text")

        try:
            self.store.set_settings(settings)
            messagebox.showinfo("Éxito", "Configuración guardada exitosamente.")
        except Exception as e:
            messagebox.showerror(
                "Error", f"No se pudo guardar la configuración.\nError: {e}"
            )

    def exit_app(self):
        """Exit the application."""
        self.store.close()
        self.destroy()


if __name__ == "__main__":
    app = SettingsApp()
    app.mainloop()
