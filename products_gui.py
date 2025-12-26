#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Product Management System
A POS application for Unix-based systems
"""

import csv
import fcntl
import os
import platform
import sys
import tkinter as tk
from tkinter import messagebox, ttk

# Prevent execution on Windows OS
if platform.system() == "Windows":
    print("=" * 60)
    print("ERROR: Esta aplicación no es compatible con Windows")
    print("=" * 60)
    print("\nEste sistema POS está diseñado exclusivamente para sistemas Unix")
    print("(Linux, macOS, BSD, etc.) y no puede ejecutarse en Windows.")
    print("\nPor favor usa un sistema Linux o macOS para ejecutar esta aplicación.")
    print("=" * 60)
    sys.exit(1)


class ProductsApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Gestión de Productos - Doble-clic para editar")
        self.geometry("1400x720")
        self.is_fullscreen = False  # Track fullscreen state

        self.create_styles()
        self.create_widgets()
        self.load_products()

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
        DANGER_COLOR = "#DC3545"
        WHITE = "#FFFFFF"
        BLACK = "#1A1A1A"

        # General styles
        self.configure(bg=BG_COLOR)
        style.configure("TFrame", background=BG_COLOR)
        style.configure(
            "TLabel", background=BG_COLOR, foreground=TEXT_COLOR, font=("Arial", 12)
        )
        style.configure("TButton", font=("Arial", 14, "bold"), padding=15)
        style.map(
            "TButton",
            background=[("active", "#EAEAEA")],
            foreground=[("active", BLACK)],
        )
        style.configure(
            "TEntry",
            font=("Arial", 14),
            fieldbackground=WHITE,
            foreground=TEXT_COLOR,
            padding=10,
        )

        # Treeview styles
        style.configure(
            "Treeview",
            font=("Arial", 12),
            rowheight=25,
            background=WHITE,
            fieldbackground=WHITE,
            foreground=TEXT_COLOR,
        )
        style.map("Treeview", background=[("selected", ACCENT_COLOR)])
        style.configure(
            "Treeview.Heading",
            font=("Arial", 12, "bold"),
            background=BG_COLOR,
            foreground=BLACK,
        )

        # Custom Button styles
        style.configure("Accent.TButton", foreground=WHITE, background=ACCENT_COLOR)
        style.map("Accent.TButton", background=[("active", "#0056b3")])

        style.configure("Success.TButton", foreground=WHITE, background=SUCCESS_COLOR)
        style.map("Success.TButton", background=[("active", "#1E7E34")])

        style.configure("Danger.TButton", foreground=WHITE, background=DANGER_COLOR)
        style.map("Danger.TButton", background=[("active", "#BD2130")])

        style.configure("Exit.TButton", foreground=WHITE, background="#000000")
        style.map("Exit.TButton", background=[("active", "#333333")])

    def toggle_fullscreen(self, event=None):
        """Toggle fullscreen mode with F11."""
        self.is_fullscreen = not self.is_fullscreen
        self.attributes("-fullscreen", self.is_fullscreen)
        return "break"

    def create_widgets(self):
        main_frame = ttk.Frame(self, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Treeview for products
        tree_frame = ttk.Frame(main_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        self.tree = ttk.Treeview(
            tree_frame,
            columns=("barcode", "name", "price", "inventory"),
            show="headings",
        )
        self.tree.heading("barcode", text="Código de Barras")
        self.tree.heading("name", text="Nombre del Producto")
        self.tree.heading("price", text="Precio")
        self.tree.heading("inventory", text="Inventario")
        self.tree.pack(fill=tk.BOTH, expand=True)
        self.tree.bind("<Double-1>", self.on_double_click)

        # Separator line
        separator = ttk.Separator(main_frame, orient="horizontal")
        separator.pack(fill=tk.X, pady=(0, 15))

        # Section title for adding new product
        title_label = ttk.Label(
            main_frame,
            text="AGREGAR NUEVO PRODUCTO",
            font=("Arial", 16, "bold"),
            foreground="#007BFF",
        )
        title_label.pack(pady=(0, 15))

        # Entry fields for adding a new product - 4 COLUMNS HORIZONTAL Layout
        form_frame = ttk.Frame(main_frame, padding="15")
        form_frame.pack(fill=tk.X, pady=(0, 15))

        # Configure columns to distribute evenly
        for i in range(4):
            form_frame.grid_columnconfigure(i, weight=1, uniform="col")

        # Column 1 - Código de Barras
        ttk.Label(
            form_frame, text="CÓDIGO DE BARRAS:", font=("Arial", 14, "bold")
        ).grid(row=0, column=0, padx=15, pady=(0, 8), sticky="w")
        self.barcode_entry = ttk.Entry(form_frame, font=("Arial", 16), width=15)
        self.barcode_entry.grid(
            row=1, column=0, padx=15, pady=(0, 10), sticky="ew", ipady=8
        )

        # Column 2 - Nombre del Producto
        ttk.Label(
            form_frame, text="NOMBRE DEL PRODUCTO:", font=("Arial", 14, "bold")
        ).grid(row=0, column=1, padx=15, pady=(0, 8), sticky="w")
        self.name_entry = ttk.Entry(form_frame, font=("Arial", 16), width=15)
        self.name_entry.grid(
            row=1, column=1, padx=15, pady=(0, 10), sticky="ew", ipady=8
        )

        # Column 3 - Precio
        ttk.Label(form_frame, text="PRECIO:", font=("Arial", 14, "bold")).grid(
            row=0, column=2, padx=15, pady=(0, 8), sticky="w"
        )
        self.price_entry = ttk.Entry(form_frame, font=("Arial", 16), width=15)
        self.price_entry.grid(
            row=1, column=2, padx=15, pady=(0, 10), sticky="ew", ipady=8
        )

        # Column 4 - Inventario
        ttk.Label(form_frame, text="INVENTARIO:", font=("Arial", 14, "bold")).grid(
            row=0, column=3, padx=15, pady=(0, 8), sticky="w"
        )
        self.inventory_entry = ttk.Entry(form_frame, font=("Arial", 16), width=15)
        self.inventory_entry.grid(
            row=1, column=3, padx=15, pady=(0, 10), sticky="ew", ipady=8
        )

        # Buttons for actions - 4 buttons distributed evenly
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 10))

        # Configure columns for equal distribution
        for i in range(4):
            button_frame.grid_columnconfigure(i, weight=1, uniform="btn")

        ttk.Button(
            button_frame,
            text="Agregar Nuevo Producto",
            command=self.add_product,
            style="Success.TButton",
        ).grid(row=0, column=0, padx=5, sticky="ew")

        ttk.Button(
            button_frame,
            text="Eliminar Seleccionado",
            command=self.delete_product,
            style="Danger.TButton",
        ).grid(row=0, column=1, padx=5, sticky="ew")

        ttk.Button(
            button_frame,
            text="Guardar Cambios al Archivo",
            command=self.save_to_csv,
            style="Accent.TButton",
        ).grid(row=0, column=2, padx=5, sticky="ew")

        ttk.Button(
            button_frame,
            text="F12 - Salir",
            command=self.exit_app,
            style="Exit.TButton",
        ).grid(row=0, column=3, padx=5, sticky="ew")

        # Bind F12 key
        self.bind("<F12>", lambda e: self.exit_app())

        # Footer with store info
        footer_frame = ttk.Frame(main_frame)
        footer_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=(10, 0))

        footer_label = ttk.Label(
            footer_frame,
            text="@Xun-POS",
            font=("Arial", 8),
            foreground="#666666",
        )
        footer_label.pack(side=tk.RIGHT, padx=5)

    def on_double_click(self, event):
        region = self.tree.identify_region(event.x, event.y)
        if region != "cell":
            return

        column_id = self.tree.identify_column(event.x)
        column_index = int(column_id.replace("#", "")) - 1

        selected_iid = self.tree.focus()
        if not selected_iid:
            return

        x, y, width, height = self.tree.bbox(selected_iid, column_id)
        value = self.tree.item(selected_iid, "values")[column_index]

        entry = ttk.Entry(self.tree, justify="center")
        entry.place(x=x, y=y, width=width, height=height)
        entry.insert(0, value)
        entry.focus()

        def save_edit(event):
            new_value = entry.get()
            current_values = list(self.tree.item(selected_iid, "values"))
            original_value = current_values[column_index]

            if new_value == original_value:
                entry.destroy()
                return

            if column_index == 0:  # Barcode validation
                all_barcodes = [
                    self.tree.item(item_id, "values")[0]
                    for item_id in self.tree.get_children()
                    if item_id != selected_iid
                ]
                if new_value in all_barcodes:
                    messagebox.showerror(
                        "Error", "El código de barras ya existe.", parent=self
                    )
                    entry.destroy()
                    return
            elif column_index == 2:  # Price validation
                try:
                    float(new_value)
                except ValueError:
                    messagebox.showerror(
                        "Error", "El precio debe ser un número.", parent=self
                    )
                    entry.destroy()
                    return
            elif column_index == 3:  # Inventory validation
                try:
                    int(new_value)
                except ValueError:
                    messagebox.showerror(
                        "Error", "El inventario debe ser un número entero.", parent=self
                    )
                    entry.destroy()
                    return

            current_values[column_index] = new_value
            self.tree.item(selected_iid, values=tuple(current_values))
            entry.destroy()

        entry.bind("<Return>", save_edit)
        entry.bind("<FocusOut>", save_edit)

    def save_to_csv(self):
        if not messagebox.askyesno(
            "Confirmar Guardado",
            "¿Desea guardar todos los cambios en products.csv?\nEsto sobrescribirá el archivo.",
        ):
            return

        try:
            products = []
            for child_iid in self.tree.get_children():
                products.append(self.tree.item(child_iid)["values"])

            self.write_products_to_csv(products)
            messagebox.showinfo(
                "Éxito", "Los cambios se han guardado correctamente en products.csv."
            )
        except Exception as e:
            messagebox.showerror("Error al Guardar", f"Ocurrió un error: {e}")

    def load_products(self):
        for i in self.tree.get_children():
            self.tree.delete(i)

        filepath = "products.csv"
        if not os.path.exists(filepath):
            messagebox.showwarning(
                "Archivo no encontrado",
                f"El archivo '{filepath}' no fue encontrado. Se creará uno nuevo.",
            )
            self.write_products_to_csv([])
            return

        try:
            with open(filepath, mode="r", encoding="utf-8") as infile:
                reader = csv.reader(infile)
                header = next(reader)
                if header != ["barcode", "name", "price", "inventario"]:
                    messagebox.showerror(
                        "Error de Formato",
                        "El archivo CSV tiene un encabezado incorrecto.",
                    )
                    return
                for i, row in enumerate(reader):
                    if len(row) == 4:
                        self.tree.insert("", tk.END, values=row)
                    else:
                        messagebox.showwarning(
                            "Fila Inválida",
                            f"La fila {i + 2} en '{filepath}' está mal formada y será ignorada.",
                        )
        except StopIteration:
            # This means the file is empty (only headers) which is fine
            pass
        except Exception as e:
            messagebox.showerror("Error al Cargar", f"No se pudo leer el archivo: {e}")

    def add_product(self):
        barcode = self.barcode_entry.get()
        name = self.name_entry.get()
        price = self.price_entry.get()
        inventory = self.inventory_entry.get()

        if not all([barcode, name, price]):
            messagebox.showerror(
                "Error", "Los campos de código, nombre y precio son requeridos."
            )
            return

        try:
            float(price)
            if inventory:
                int(inventory)
            else:
                inventory = "0"
        except ValueError:
            messagebox.showerror(
                "Error", "El precio y el inventario deben ser números."
            )
            return

        all_barcodes = [
            self.tree.item(item_id, "values")[0] for item_id in self.tree.get_children()
        ]
        if barcode in all_barcodes:
            messagebox.showerror("Error", "El código de barras ya existe.")
            return

        self.tree.insert("", tk.END, values=(barcode, name, price, inventory))
        self.clear_form()

    def delete_product(self):
        selected_item = self.tree.selection()
        if not selected_item:
            messagebox.showerror(
                "Error", "Por favor, seleccione un producto para eliminar."
            )
            return

        if not messagebox.askyesno(
            "Confirmar", "¿Está seguro de que desea eliminar el producto seleccionado?"
        ):
            return

        for item in selected_item:
            self.tree.delete(item)

    def write_products_to_csv(self, products):
        filepath = "products.csv"
        # Ensure file exists first if not (though save_to_csv logic usually implies it, 
        # but if we are creating new, we might need 'w' if it doesn't exist)
        if not os.path.exists(filepath):
            with open(filepath, "w", newline="", encoding="utf-8") as f:
                 writer = csv.writer(f)
                 writer.writerow(["barcode", "name", "price", "inventario"])
        
        with open(filepath, "r+", newline="", encoding="utf-8") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                f.seek(0)
                f.truncate()
                writer = csv.writer(f)
                writer.writerow(["barcode", "name", "price", "inventario"])
                writer.writerows(products)
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)

    def clear_form(self):
        self.barcode_entry.delete(0, tk.END)
        self.name_entry.delete(0, tk.END)
        self.price_entry.delete(0, tk.END)
        self.inventory_entry.delete(0, tk.END)
        if self.tree.selection():
            self.tree.selection_remove(self.tree.selection())

    def exit_app(self):
        """Exit the application."""
        self.destroy()


if __name__ == "__main__":
    app = ProductsApp()
    app.mainloop()
