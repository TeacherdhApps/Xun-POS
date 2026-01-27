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
import json
import theme_manager

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


class ProductsApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Gestión de Productos - Doble clic para editar")
        self.geometry("1400x720")
        self.is_fullscreen = False
        
        # Base directory for absolute paths
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.settings = self.load_settings()

        # Data Management
        self.all_products = []  # List of dictionaries: {'codigo':, 'nombre':, 'precio':, 'inventario':}
        self.current_sort_col = None
        self.current_sort_reverse = False

        self.create_styles()
        self.create_widgets()
        
        # Load data
        self.load_data_into_memory()
        self.populate_treeview(self.all_products)

        # Bind F11 for fullscreen toggle
        self.bind("<F11>", self.toggle_fullscreen)
        # Bind F12 to exit
        self.bind("<F12>", lambda e: self.exit_app())

    def load_settings(self):
        """Load settings from JSON file with default fallback."""
        default_settings = {
            "business_name": "Mi Tienda",
            "dark_mode": False
        }
        try:
            settings_path = os.path.join(self.base_dir, "settings.json")
            if os.path.exists(settings_path):
                with open(settings_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    default_settings.update(loaded)
        except Exception:
            pass
        return default_settings

    def create_styles(self):
        """Configure ttk styles."""
        style = ttk.Style(self)
        style.theme_use("clam")

        dark_mode = self.settings.get("dark_mode", False)
        colors = theme_manager.get_theme_colors(dark_mode)

        # Palette
        BG_COLOR = colors["background"]
        TEXT_COLOR = colors["foreground"]
        ACCENT_COLOR = colors["accent"]
        SUCCESS_COLOR = colors["success"]
        DANGER_COLOR = colors["danger"]
        SURFACE = colors["surface"]
        ON_SURFACE = colors["on_surface"]

        # General styles
        self.configure(bg=BG_COLOR)
        style.configure("TFrame", background=BG_COLOR)
        style.configure(
            "TLabel", background=BG_COLOR, foreground=TEXT_COLOR, font=("Arial", 12)
        )
        style.configure("TButton", font=("Arial", 14, "bold"), padding=10, background=SURFACE, foreground=TEXT_COLOR)
        style.map(
            "TButton",
            background=[("active", colors["background"])],
            foreground=[("active", colors["accent"])],
        )
        style.configure(
            "TEntry",
            font=("Arial", 14),
            fieldbackground=colors["field_bg"],
            foreground=colors["field_fg"],
            padding=10,
        )
        style.configure(
            "TCombobox",
            fieldbackground=colors["field_bg"],
            foreground=colors["field_fg"],
        )

        # Treeview styles
        style.configure(
            "Treeview",
            font=("Arial", 12),
            rowheight=40,
            background=colors["tree_bg"],
            fieldbackground=colors["tree_bg"],
            foreground=colors["tree_fg"],
        )
        style.map("Treeview", background=[("selected", colors["tree_selected"])])
        style.configure(
            "Treeview.Heading",
            font=("Arial", 12, "bold"),
            background=colors["header_bg"],
            foreground=colors["header_fg"],
        )

        # Custom Button styles
        style.configure("Accent.TButton", foreground=SURFACE, background=ACCENT_COLOR)
        style.map("Accent.TButton", background=[("active", "#0056b3")])

        style.configure("Success.TButton", foreground=SURFACE, background=SUCCESS_COLOR)
        style.map("Success.TButton", background=[("active", "#1E7E34")])

        style.configure("Danger.TButton", foreground=SURFACE, background=DANGER_COLOR)
        style.map("Danger.TButton", background=[("active", "#BD2130")])

        style.configure("Exit.TButton", foreground=colors["exit_fg"], background=colors["exit_bg"])
        style.map("Exit.TButton", background=[("active", "#333333")])

    def toggle_fullscreen(self, event=None):
        """Toggle fullscreen mode with F11."""
        self.is_fullscreen = not self.is_fullscreen
        self.attributes("-fullscreen", self.is_fullscreen)
        return "break"

    def create_widgets(self):
        main_frame = ttk.Frame(self, padding="5")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Header with @Xun-POS
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 2))
        
        info_label = ttk.Label(
            header_frame,
            text="@Xun-POS",
            font=("Arial", 8),
            foreground="#666666",
        )
        info_label.pack(side=tk.RIGHT)

        # --- Search and Filter Section ---
        search_frame = ttk.Frame(main_frame)
        search_frame.pack(fill=tk.X, pady=(0, 5))

        ttk.Label(search_frame, text="Buscar:", font=("Arial", 12, "bold")).pack(side=tk.LEFT, padx=(0, 5))
        
        self.search_var = tk.StringVar()
        self.search_var.trace("w", self.filter_products)
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=40)
        search_entry.pack(side=tk.LEFT, padx=5)

        ttk.Label(search_frame, text="por", font=("Arial", 12)).pack(side=tk.LEFT, padx=5)
        
        self.filter_column = tk.StringVar(value="Nombre")
        filter_combo = ttk.Combobox(search_frame, textvariable=self.filter_column, 
                                    values=["Nombre", "Código", "Precio", "Inventario"], 
                                    state="readonly", font=("Arial", 12), width=15,
                                    style="TCombobox")
        filter_combo.pack(side=tk.LEFT, padx=5)
        filter_combo.bind("<<ComboboxSelected>>", self.filter_products)

        # Treeview for products
        tree_frame = ttk.Frame(main_frame)
        tree_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Add scrollbar
        tree_scroll = ttk.Scrollbar(tree_frame)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree = ttk.Treeview(
            tree_frame,
            columns=("codigo", "nombre", "precio", "inventario"),
            show="headings",
            yscrollcommand=tree_scroll.set,
            height=6
        )
        tree_scroll.config(command=self.tree.yview)

        # Configure columns and headings with sorting
        columns = {
            "codigo": "Código",
            "nombre": "Nombre Producto",
            "precio": "Precio",
            "inventario": "Inventario"
        }
        
        for col, text in columns.items():
            self.tree.heading(col, text=text, command=lambda c=col: self.sort_treeview(c))
            self.tree.column(col, anchor="w" if col in ["codigo", "nombre"] else "center")

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

        # Entry fields for adding a new product
        form_frame = ttk.Frame(main_frame, padding="15")
        form_frame.pack(fill=tk.X, pady=(0, 15))

        for i in range(4):
            form_frame.grid_columnconfigure(i, weight=1, uniform="col")

        # Column 1 - Barcode
        ttk.Label(
            form_frame, text="CÓDIGO:", font=("Arial", 14, "bold")
        ).grid(row=0, column=0, padx=15, pady=(0, 8), sticky="w")
        self.barcode_entry = ttk.Entry(form_frame, font=("Arial", 16), width=15)
        self.barcode_entry.grid(
            row=1, column=0, padx=15, pady=(0, 10), sticky="ew", ipady=8
        )

        # Column 2 - Product Name
        ttk.Label(
            form_frame, text=" NOMBRE PRODUCTO:", font=("Arial", 14, "bold")
        ).grid(row=0, column=1, padx=15, pady=(0, 8), sticky="w")
        self.name_entry = ttk.Entry(form_frame, font=("Arial", 16), width=15)
        self.name_entry.grid(
            row=1, column=1, padx=15, pady=(0, 10), sticky="ew", ipady=8
        )

        # Column 3 - Price
        ttk.Label(form_frame, text="PRECIO:", font=("Arial", 14, "bold")).grid(
            row=0, column=2, padx=15, pady=(0, 8), sticky="w"
        )
        self.price_entry = ttk.Entry(form_frame, font=("Arial", 16), width=15)
        self.price_entry.grid(
            row=1, column=2, padx=15, pady=(0, 10), sticky="ew", ipady=8
        )

        # Column 4 - Inventory
        ttk.Label(form_frame, text="INVENTARIO:", font=("Arial", 14, "bold")).grid(
            row=0, column=3, padx=15, pady=(0, 8), sticky="w"
        )
        self.inventory_entry = ttk.Entry(form_frame, font=("Arial", 16), width=15)
        self.inventory_entry.grid(
            row=1, column=3, padx=15, pady=(0, 10), sticky="ew", ipady=8
        )

        # Bind Enter keys
        for entry in [self.barcode_entry, self.name_entry, self.price_entry, self.inventory_entry]:
            entry.bind("<Return>", lambda e: self.add_product())
            entry.bind("<KP_Enter>", lambda e: self.add_product())

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 10))

        for i in range(4):
            button_frame.grid_columnconfigure(i, weight=1, uniform="btn")

        ttk.Button(
            button_frame,
            text="Agregar Producto",
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
            text="Guardar Cambios",
            command=self.save_to_csv,
            style="Accent.TButton",
        ).grid(row=0, column=2, padx=5, sticky="ew")

        ttk.Button(
            button_frame,
            text="F12 - Salir",
            command=self.exit_app,
            style="Exit.TButton",
        ).grid(row=0, column=3, padx=5, sticky="ew")

    def load_data_into_memory(self):
        """Read CSV and store in self.all_products."""
        filepath = os.path.join(self.base_dir, "productos.csv")
        self.all_products = []
        
        if not os.path.exists(filepath):
            # Create if not exists
            try:
                with open(filepath, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(["codigo", "nombre", "precio", "inventario"])
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo crear el archivo: {e}")
            return

        try:
            with open(filepath, mode="r", encoding="utf-8") as infile:
                reader = csv.reader(infile)
                header = next(reader, None)
                if header != ["codigo", "nombre", "precio", "inventario"]:
                    messagebox.showerror("Error de Formato", "Archivo CSV tiene encabezado incorrecto.")
                    return

                for row in reader:
                    if len(row) >= 4:
                        self.all_products.append({
                            "codigo": row[0].strip().lstrip("0") or "0",
                            "nombre": row[1],
                            "precio": row[2],
                            "inventario": row[3]
                        })
        except Exception as e:
            messagebox.showerror("Error de Carga", f"No se pudo leer archivo: {e}")

    def populate_treeview(self, products):
        """Populate the treeview with the given list of products."""
        # Clear existing items
        for i in self.tree.get_children():
            self.tree.delete(i)
        
        for p in products:
            self.tree.insert("", tk.END, values=(p['codigo'], p['nombre'], p['precio'], p['inventario']))

    def filter_products(self, *args):
        """Filter products based on search criteria."""
        search_term = self.search_var.get().lower()
        filter_by = self.filter_column.get()
        
        # Map friendly names to keys
        key_map = {
            "Nombre": "nombre",
            "Código": "codigo",
            "Precio": "precio",
            "Inventario": "inventario"
        }
        key = key_map.get(filter_by, "nombre")

        filtered = []
        for p in self.all_products:
            if search_term in str(p[key]).lower():
                filtered.append(p)
        
        self.populate_treeview(filtered)

    def sort_treeview(self, col):
        """Sort treeview content when a column header is clicked."""
        if self.current_sort_col == col:
            self.current_sort_reverse = not self.current_sort_reverse
        else:
            self.current_sort_col = col
            self.current_sort_reverse = False

        # Sort the underlying data source (or filtered view)? 
        # Better to sort the currently displayed items to respect search
        
        # Helper to get value for sorting
        def get_value(item):
            val = item[col]
            # Try to convert to float/int for numerical sorting
            try:
                if col in ["precio", "inventario", "codigo"]:
                    return float(val)
            except ValueError:
                pass
            return str(val).lower()

        # We sort self.all_products to maintain order even if search changes
        self.all_products.sort(key=get_value, reverse=self.current_sort_reverse)
        
        # Re-apply filter to update view
        self.filter_products()
        
        # Update heading to show sort direction (optional visual cue)
        for c in self.tree["columns"]:
            text = self.tree.heading(c, "text").replace(" ▲", "").replace(" ▼", "")
            if c == col:
                text += " ▼" if self.current_sort_reverse else " ▲"
            self.tree.heading(c, text=text)

    def on_double_click(self, event):
        region = self.tree.identify_region(event.x, event.y)
        if region != "cell":
            return

        column_id = self.tree.identify_column(event.x)
        column_index = int(column_id.replace("#", "")) - 1
        
        # Determine key from index
        keys = ["codigo", "nombre", "precio", "inventario"]
        key = keys[column_index]

        selected_iid = self.tree.focus()
        if not selected_iid:
            return

        # Get the actual item values
        current_values = self.tree.item(selected_iid, "values")
        # Identify the product in self.all_products using barcode (index 0)
        # Note: If barcode is edited, we need to handle that carefully.
        # But we first need to find the original object.
        original_barcode = current_values[0]
        
        # Find the product dict in memory
        product_idx = -1
        for i, p in enumerate(self.all_products):
            if p['codigo'] == original_barcode:
                product_idx = i
                break
        
        if product_idx == -1: return # Should not happen

        x, y, width, height = self.tree.bbox(selected_iid, column_id)
        value = current_values[column_index]

        entry = ttk.Entry(self.tree, justify="center")
        entry.place(x=x, y=y, width=width, height=height)
        entry.insert(0, value)
        entry.focus()

        def save_edit(event):
            new_value = entry.get()
            if column_index == 0:  # Barcode normalization
                new_value = new_value.strip().lstrip("0") or "0"

            if new_value == value:
                entry.destroy()
                return

            # Validation
            if column_index == 0:  # Barcode
                # Check uniqueness (excluding self)
                if any(p['codigo'] == new_value for i, p in enumerate(self.all_products) if i != product_idx):
                    messagebox.showerror("Error", "El código ya existe.", parent=self)
                    entry.destroy()
                    return
            elif column_index == 2:  # Price
                try:
                    float(new_value)
                except ValueError:
                    messagebox.showerror("Error", "El precio debe ser un número.", parent=self)
                    entry.destroy()
                    return
            elif column_index == 3:  # Inventory
                try:
                    int(new_value)
                except ValueError:
                    messagebox.showerror("Error", "El inventario debe ser un entero.", parent=self)
                    entry.destroy()
                    return

            # Update memory
            self.all_products[product_idx][key] = new_value
            
            # Update View
            # We could just update the tree item, but to keep sort/filter consistent,
            # it's safer to re-run filter/populate. However, that loses scroll position.
            # For specific cell update, direct tree update is better UX.
            
            # Update tree item directly
            new_values = list(current_values)
            new_values[column_index] = new_value
            self.tree.item(selected_iid, values=new_values)
            
            entry.destroy()

        entry.bind("<Return>", save_edit)
        entry.bind("<KP_Enter>", save_edit)
        entry.bind("<FocusOut>", save_edit)

    def add_product(self):
        barcode = self.barcode_entry.get().strip().lstrip("0") or "0"
        name = self.name_entry.get().strip()
        price = self.price_entry.get().strip()
        inventory = self.inventory_entry.get().strip()

        if not all([barcode, name, price]):
            messagebox.showerror("Error", "Código, nombre y precio son requeridos.")
            return

        try:
            float(price)
            if inventory:
                int(inventory)
            else:
                inventory = "0"
        except ValueError:
            messagebox.showerror("Error", "Precio e inventario deben ser números.")
            return

        # Check for duplicates in memory
        if any(p['codigo'] == barcode for p in self.all_products):
            messagebox.showerror("Error", "El código ya existe.")
            return

        new_product = {
            "codigo": barcode,
            "nombre": name,
            "precio": price,
            "inventario": inventory
        }
        
        self.all_products.append(new_product)
        
        # Refresh view (will include new item if it matches filter)
        self.filter_products()
        
        # Scroll to bottom if not filtered or if sorted? 
        # For now, just clear form
        self.clear_form()
        messagebox.showinfo("Éxito", "Producto agregado. Recuerde guardar cambios.")

    def delete_product(self):
        selected_items = self.tree.selection()
        if not selected_items:
            messagebox.showerror("Error", "Seleccione un producto para eliminar.")
            return

        if not messagebox.askyesno("Confirmar", "¿Está seguro de eliminar el producto seleccionado?"):
            return

        barcodes_to_remove = []
        for item_id in selected_items:
            # Get barcode from the visible tree item
            barcode = self.tree.item(item_id, "values")[0]
            barcodes_to_remove.append(barcode)
            self.tree.delete(item_id)

        # Remove from memory
        self.all_products = [p for p in self.all_products if p['codigo'] not in barcodes_to_remove]

    def save_to_csv(self):
        if not messagebox.askyesno(
            "Confirmar Guardar",
            "¿Desea guardar todos los cambios en productos.csv?\nEsto sobrescribirá el archivo.",
        ):
            return

        try:
            filepath = os.path.join(self.base_dir, "productos.csv")
            # Prepare rows
            rows = []
            for p in self.all_products:
                rows.append([p['codigo'], p['nombre'], p['precio'], p['inventario']])

            # Write with lock
            # Ensure file exists first
            if not os.path.exists(filepath):
                 with open(filepath, "w", newline="", encoding="utf-8") as f:
                     writer = csv.writer(f)
                     writer.writerow(["codigo", "nombre", "precio", "inventario"])
            
            with open(filepath, "r+", newline="", encoding="utf-8") as f:
                fcntl.flock(f, fcntl.LOCK_EX)
                try:
                    f.seek(0)
                    f.truncate()
                    writer = csv.writer(f)
                    writer.writerow(["codigo", "nombre", "precio", "inventario"])
                    writer.writerows(rows)
                finally:
                    fcntl.flock(f, fcntl.LOCK_UN)
            
            messagebox.showinfo("Éxito", "Cambios guardados exitosamente en productos.csv.")
            
        except Exception as e:
            messagebox.showerror("Error Guardando", f"Ocurrió un error: {e}")

    def clear_form(self):
        self.barcode_entry.delete(0, tk.END)
        self.name_entry.delete(0, tk.END)
        self.price_entry.delete(0, tk.END)
        self.inventory_entry.delete(0, tk.END)
        self.barcode_entry.focus_set()

    def exit_app(self):
        """Exit the application."""
        self.destroy()


if __name__ == "__main__":
    app = ProductsApp()
    app.mainloop()
