import base64
import csv
import fcntl
import json
import os
import platform
import subprocess
import sys
import tempfile
import tkinter as tk
import webbrowser
import theme_manager
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, ttk

try:
    from thermal_printer import ThermalPrinter
except ImportError:
    ThermalPrinter = None

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


class POS_GUI(tk.Tk):
    def __init__(self, user_role="admin"):
        super().__init__()
        self.title("Punto de Venta")
        self.state("normal")
        self.resizable(True, True)
        self.user_role = user_role  # Store user role for access control
        self.is_fullscreen = False  # Track fullscreen state
        
        # Base directory for absolute paths
        self.base_dir = os.path.dirname(os.path.abspath(__file__))

        self.settings = self.load_settings()
        self.products = self.load_products()
        self.active_tickets = {1: {}, 2: {}}
        self.current_ticket_id = 1
        self.sale_items = self.active_tickets[1]  # Dictionary to handle quantities: {codigo: {'nombre': str, 'precio': float, 'cantidad': int}}
        self.last_added_barcode = (
            None  # Track the last added product for quick re-addition
        )
        self.search_timer = None  # Timer for debounce search

        self.create_styles()
        self.init_sales_log()
        self.init_cash_flow_log()
        self.create_widgets()
        self.update_time()  # Start the clock
        self.after(100, lambda: self.product_combobox.focus_set())  # Focus on product combobox

        # Bind F11 for fullscreen toggle
        self.bind("<F11>", self.toggle_fullscreen)

    def load_settings(self):
        """Load settings from JSON file with default fallback."""
        default_settings = {
            "business_name": "Mi Tienda",
            "address": "Calle Principal 123",
            "phone": "555-0199",
            "cashier_name": "Cajero",
            "logo_path": "",
            "dark_mode": False
        }
        try:
            settings_path = os.path.join(self.base_dir, "settings.json")
            if os.path.exists(settings_path):
                with open(settings_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    default_settings.update(loaded)  # Merge with defaults
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        return default_settings

    def update_time(self):
        """Update date and time labels every second."""
        now = datetime.now()
        
        # Spanish day and month names
        dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
        meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
        
        day_name = dias[now.weekday()]
        month_name = meses[now.month - 1]
        
        date_str = f"{day_name}, {now.day} de {month_name} de {now.year}"
        time_str = now.strftime("%I:%M %p")

        self.date_label.config(text=date_str)
        self.time_label.config(text=time_str)

        self.after(1000, self.update_time)

    def init_sales_log(self):
        """Initialize ventas.csv with headers if it doesn't exist."""
        filepath = os.path.join(self.base_dir, "ventas.csv")
        if not os.path.exists(filepath):
            with open(filepath, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(
                    [
                        "fecha_hora",
                        "codigo",
                        "nombre",
                        "cantidad",
                        "precio_unitario",
                        "total",
                    ]
                )

    def log_sale(self, items=None):
        """Log the sale to ventas.csv."""
        target_items = items if items is not None else self.sale_items
        if not target_items:
            return

        timestamp = datetime.now().isoformat()
        filepath = os.path.join(self.base_dir, "ventas.csv")
        with open(filepath, "a", newline="", encoding="utf-8") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                writer = csv.writer(f)
                for barcode, item in target_items.items():
                    writer.writerow(
                        [
                            timestamp,
                            barcode,
                            item["nombre"],
                            item["qty"],
                            item["precio"],
                            item["qty"] * item["precio"],
                        ]
                    )
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)

    def update_inventory(self):
        """Update product inventory in productos.csv after a sale."""
        filepath = Path(os.path.join(self.base_dir, "productos.csv"))
        if not filepath.exists():
            messagebox.showerror("Error", f"Archivo '{filepath}' no encontrado.")
            return

        try:
            with open(filepath, mode="r+", newline="", encoding="utf-8") as file:
                # Acquire an exclusive lock
                fcntl.flock(file, fcntl.LOCK_EX)
                
                try:
                    reader = csv.reader(file)
                    lines = list(reader)
                    
                    if not lines:
                        messagebox.showerror("Error", "El archivo de productos está vacío.")
                        return

                    header = lines[0]
                    product_lines = lines[1:]

                    # Create a dictionary for quick lookup by barcode
                    products_dict = {row[0]: row for row in product_lines}
                    
                    # Track if any changes were made
                    changes_made = False

                    # Update quantities
                    for barcode, item in self.sale_items.items():
                        if barcode in products_dict:
                            try:
                                # Assuming 'inventario' is the 4th column (index 3)
                                current_stock = int(products_dict[barcode][3])
                                new_stock = current_stock - item["qty"]
                                products_dict[barcode][3] = str(new_stock)
                                changes_made = True
                            except (ValueError, IndexError):
                                print(f"Advertencia: No se pudo actualizar el inventario para el código {barcode}")
                    
                    if changes_made:
                        # Reconstruct the lines in the original order
                        updated_lines = [header] + [products_dict.get(row[0], row) for row in product_lines]
                        
                        # Rewind and write
                        file.seek(0)
                        writer = csv.writer(file)
                        writer.writerows(updated_lines)
                        file.truncate()
                        
                finally:
                    # Always unlock
                    fcntl.flock(file, fcntl.LOCK_UN)
                    
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo actualizar el inventario: {e}")

    def load_products(self):
        """Load products from CSV file."""
        products = {}
        filepath = Path(os.path.join(self.base_dir, "productos.csv"))
        if not filepath.exists():
            messagebox.showerror("Error", f"Archivo '{filepath}' no encontrado.")
            self.destroy()
            return products

        try:
            with open(filepath, mode="r", encoding="utf-8") as infile:
                reader = csv.reader(infile)
                header = next(reader, None)  # Skip header
                if not header:
                    raise ValueError("Archivo de productos vacío o faltan encabezados.")
                for row_num, row in enumerate(reader, start=2):
                    if len(row) >= 4:  # At least codigo, nombre, precio, inventario
                        barcode = row[0].strip().lstrip("0") or "0"
                        name, price_str, inventario_str = row[1:4]
                        try:
                            price = float(price_str)
                            inventario = int(inventario_str)
                            products[barcode] = {
                                "nombre": name.strip(),
                                "precio": price,
                                "inventario": inventario,
                            }
                        except ValueError:
                            print(
                                f"Advertencia: Precio o inventario inválido en fila {row_num}"
                            )
                    elif len(row) >= 3:  # Fallback for rows without inventario
                        barcode = row[0].strip().lstrip("0") or "0"
                        name, price_str = row[1:3]
                        try:
                            price = float(price_str)
                            products[barcode] = {
                                "nombre": name.strip(),
                                "precio": price,
                                "inventario": 0,  # Default inventario to 0
                            }
                        except ValueError:
                            print(f"Advertencia: Precio inválido en fila {row_num}")
                    else:
                        print(f"Advertencia: Fila incompleta {row_num}: {row}")
        except Exception as e:
            messagebox.showerror(
                "Error de Datos", f"Error leyendo datos de productos: {e}"
            )
            self.destroy()
        return products

    def create_styles(self):
        """Configure ttk styles."""
        style = ttk.Style(self)
        style.theme_use("clam")

        dark_mode = self.settings.get("dark_mode", False)
        self.colors = theme_manager.get_theme_colors(dark_mode)

        # Palette
        BG_COLOR = self.colors["background"]
        TEXT_COLOR = self.colors["foreground"]
        SECONDARY_TEXT_COLOR = self.colors["secondary_foreground"]
        ACCENT_COLOR = self.colors["accent"]
        SUCCESS_COLOR = self.colors["success"]
        DANGER_COLOR = self.colors["danger"]
        SURFACE = self.colors["surface"]
        ON_SURFACE = self.colors["on_surface"]

        # Combobox Listbox Styling (Global for Tcl/Tk)
        self.option_add("*TCombobox*Listbox.font", ("Arial", 18))
        self.option_add("*TCombobox*Listbox.background", self.colors["field_bg"])
        self.option_add("*TCombobox*Listbox.foreground", self.colors["field_fg"])
        self.option_add("*TCombobox*Listbox.selectBackground", ACCENT_COLOR)
        self.option_add("*TCombobox*Listbox.selectForeground", SURFACE)

        # Custom Combobox styles
        # Product input: Distinct background to indicate readiness
        style.configure("Product.TCombobox", fieldbackground=self.colors["product_field_bg"], background=SURFACE)
        
        # Quantity editor: Subtle background
        style.configure("Qty.TCombobox", fieldbackground=self.colors["qty_field_bg"], background=SURFACE)

        # General styles
        self.configure(bg=BG_COLOR)
        style.configure("TFrame", background=BG_COLOR)
        style.configure(
            "TLabel", background=BG_COLOR, foreground=TEXT_COLOR, font=("Arial", 12)
        )
        style.configure("TButton", font=("Arial", 12, "bold"), padding=5, background=SURFACE, foreground=TEXT_COLOR)
        style.map(
            "TButton",
            background=[("active", self.colors["background"])],
            foreground=[("active", self.colors["accent"])],
        )

        # Treeview styles
        style.configure(
            "Treeview",
            font=("Arial", 16),
            rowheight=35,
            background=self.colors["tree_bg"],
            fieldbackground=self.colors["tree_bg"],
            foreground=self.colors["tree_fg"],
        )
        style.map("Treeview", background=[("selected", self.colors["tree_selected"])])
        style.configure(
            "Treeview.Heading",
            font=("Arial", 16, "bold"),
            background=self.colors["header_bg"],
            foreground=self.colors["header_fg"],
        )

        # Custom Label styles
        style.configure(
            "Total.TLabel",
            font=("Arial", 48, "bold"),
            background=BG_COLOR,
            foreground=ON_SURFACE,
        )
        style.configure(
            "Header.TLabel",
            font=("Arial", 28, "bold"),
            background=BG_COLOR,
            foreground=ON_SURFACE,
        )
        style.configure(
            "DateTime.TLabel",
            font=("Arial", 12, "bold"),
            background=BG_COLOR,
            foreground=TEXT_COLOR,
        )
        style.configure(
            "Subtle.TLabel",
            font=("Arial", 12, "bold"),
            background=BG_COLOR,
            foreground=SECONDARY_TEXT_COLOR,
        )
        style.configure(
            "Success.TLabel",
            font=("Arial", 12, "bold"),
            background=BG_COLOR,
            foreground=SUCCESS_COLOR,
        )

        # Custom Button styles
        style.configure("Accent.TButton", foreground=SURFACE, background=ACCENT_COLOR)
        style.map("Accent.TButton", background=[("active", "#0056b3")])

        style.configure("Success.TButton", foreground=SURFACE, background=SUCCESS_COLOR)
        style.map("Success.TButton", background=[("active", "#1E7E34")])

        style.configure("Danger.TButton", foreground=SURFACE, background=DANGER_COLOR)
        style.map("Danger.TButton", background=[("active", "#BD2130")])

        # Custom style for larger Accent buttons
        style.configure(
            "Large.Accent.TButton",
            foreground=SURFACE,
            background=ACCENT_COLOR,
            font=("Arial", 16, "bold"),  # Larger font
            padding=[20, 15],  # More padding (horizontal, vertical)
        )
        style.map("Large.Accent.TButton", background=[("active", "#0056b3")])

        # Custom style for dark grey buttons
        style.configure("DarkGrey.TButton", foreground=SURFACE, background=TEXT_COLOR)
        style.map("DarkGrey.TButton", background=[("active", SECONDARY_TEXT_COLOR)])

        # Small Button style
        style.configure("Small.TButton", font=("Arial", 10), padding=1)
        style.configure("Small.Accent.TButton", font=("Arial", 10, "bold"), padding=1, foreground=SURFACE, background=ACCENT_COLOR)
        style.map("Small.Accent.TButton", background=[("active", "#0056b3")])

        # Black Exit button
        style.configure("Exit.TButton", foreground=self.colors["exit_fg"], background=self.colors["exit_bg"])
        style.map("Exit.TButton", background=[("active", "#333333")])

    def toggle_fullscreen(self, event=None):
        """Toggle fullscreen mode with F11."""
        self.is_fullscreen = not self.is_fullscreen
        self.attributes("-fullscreen", self.is_fullscreen)
        return "break"

    def create_widgets(self):
        """Create and pack all widgets."""
        # Main layout frames
        main_frame = ttk.Frame(self, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Top menu bar
        self._create_menu_bar(main_frame)

        # Frame for product search
        self._create_top_frame(main_frame)

        # Middle Frame: Sale Items Treeview with scrollbar
        self._create_middle_frame(main_frame)

        # Bottom Frame: Total and Actions
        self._create_bottom_frame(main_frame)

        # No listbox needed for Combobox

        # Bind F1 to show payment window
        self.bind("<F1>", lambda event: self.show_payment_window())
        # Bind F3 to open settings window
        self.bind("<F3>", lambda event: self.open_settings_window())
        # Bind F4 to open products window
        self.bind("<F4>", lambda event: self.open_products_window())
        # Bind F5 to open reports window (only for admin)
        if self.user_role == "admin":
            self.bind("<F5>", lambda event: self.open_reports_window())
        # Bind F12 to exit application
        self.bind("<F12>", lambda event: self.destroy())
        # Bind Tab to focus next widget
        self.bind("<Tab>", lambda event: self.focus_next_widget())

    def _create_menu_bar(self, parent):
        """Create the top menu bar."""
        menu_frame = ttk.Frame(parent)
        menu_frame.pack(fill=tk.X, pady=(0, 10))

        # Store info label (Top Right)
        info_label = ttk.Label(
            menu_frame,
            text="@Xun-POS",
            font=("Arial", 8),
            foreground="#666666",
        )
        info_label.pack(side=tk.RIGHT, anchor=tk.NE, padx=5, pady=5)

        business_name_label = ttk.Label(
            menu_frame, text=self.settings["business_name"], style="Header.TLabel"
        )
        business_name_label.pack(side=tk.TOP, pady=(0, 5))

        # Frame for date and time
        datetime_frame = ttk.Frame(menu_frame)
        datetime_frame.pack(side=tk.LEFT, padx=5)

        self.date_label = ttk.Label(datetime_frame, style="DateTime.TLabel")
        self.date_label.pack(side=tk.TOP)

        self.time_label = ttk.Label(datetime_frame, style="Subtle.TLabel")
        self.time_label.pack(side=tk.TOP)

        # Right-aligned buttons
        button_frame = ttk.Frame(menu_frame)
        button_frame.pack(side=tk.RIGHT)

        # Only show Settings button for admin
        if self.user_role == "admin":
            ttk.Button(
                button_frame, text="F3 - Ajustes", command=self.open_settings_window
            ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            button_frame, text="F4 - Productos", command=self.open_products_window
        ).pack(side=tk.LEFT, padx=5)

        # Only show Reports button for admin
        if self.user_role == "admin":
            ttk.Button(
                button_frame, text="F5 - Reportes", command=self.open_reports_window
            ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            button_frame, text="F12 - Salir", command=self.destroy, style="Exit.TButton"
        ).pack(side=tk.LEFT)

    def switch_ticket(self, ticket_id):
        """Switch to a specific ticket."""
        self.current_ticket_id = ticket_id
        self.sale_items = self.active_tickets[ticket_id]
        self.update_sale_list()
        self.update_total()
        self.refresh_ticket_buttons()
        self.product_combobox.focus()

    def refresh_ticket_buttons(self):
        """Refresh the ticket buttons in the UI."""
        # Check if container exists (it might not be created yet during init)
        if not hasattr(self, 'tickets_container'):
            return

        for widget in self.tickets_container.winfo_children():
            widget.destroy()

        for t_id in sorted(self.active_tickets.keys()):
            style = "Small.Accent.TButton" if t_id == self.current_ticket_id else "Small.TButton"
            
            btn = ttk.Button(self.tickets_container, text=f"Recibo {t_id}", style=style,
                             command=lambda id=t_id: self.switch_ticket(id))
            btn.pack(side=tk.LEFT, padx=2)

    def clear_sale(self):
        """Clear the current sale."""
        self.active_tickets[self.current_ticket_id] = {}
        self.sale_items = self.active_tickets[self.current_ticket_id]
        self.update_sale_list()
        self.update_total()
        self.product_combobox.set('')
        self.product_combobox['values'] = []
        self.product_combobox.focus()

    def reset_sale(self):
        """Reset the sale items and UI."""
        self.active_tickets[self.current_ticket_id] = {}
        self.sale_items = self.active_tickets[self.current_ticket_id]
        self.update_sale_list()
        self.update_total()
        self.product_combobox.set('')
        self.product_combobox['values'] = []
        self.product_combobox.focus()

    def _create_top_frame(self, parent):
        """Create the top frame for product entry."""
        top_frame = ttk.Frame(parent)
        top_frame.pack(fill=tk.X, pady=5)  # Reduced pady

        ttk.Label(
            top_frame,
            text="PRODUCTO (Código o Nombre):",
            font=("Arial", 20, "bold"),
        ).pack(  # Increased font
            side=tk.LEFT, padx=(0, 10)
        )

        self.product_combobox = ttk.Combobox(
            top_frame, font=("Arial", 24, "bold"), style="Product.TCombobox"
        )  # Increased font
        self.product_combobox.pack(side=tk.LEFT, expand=True, fill=tk.X)
        self.product_combobox.bind("<Return>", self.add_product)
        self.product_combobox.bind("<KP_Enter>", self.add_product)
        self.product_combobox.bind("<KeyRelease>", self.show_suggestions)
        self.product_combobox.bind("<<ComboboxSelected>>", self.add_product)

    def _create_middle_frame(self, parent):
        """Create the middle frame with Treeview and scrollbar."""
        middle_frame = ttk.Frame(parent)
        middle_frame.pack(fill=tk.BOTH, expand=True)

        # Treeview with scrollbar
        tree_frame = ttk.Frame(middle_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        self.tree = ttk.Treeview(
            tree_frame,
            columns=("barcode", "name", "qty", "price", "total"),
            show="headings",
            height=8,
        )

        self.tree.tag_configure("low_stock", background=self.colors["low_stock_bg"])
        self.tree.heading("barcode", text="Código")
        self.tree.heading("name", text="Producto")
        self.tree.heading("qty", text="Cant. +/-")
        self.tree.heading("price", text="Precio Unit")
        self.tree.heading("total", text="Total")
        self.tree.column("barcode", anchor=tk.W, width=100, minwidth=80)
        self.tree.column("name", anchor=tk.W, width=300, minwidth=200)
        self.tree.column("qty", anchor=tk.CENTER, width=80, minwidth=60)
        self.tree.column("price", anchor=tk.E, width=100, minwidth=80)
        self.tree.column("total", anchor=tk.E, width=120, minwidth=100)

        # Scrollbar
        scrollbar = ttk.Scrollbar(
            tree_frame, orient=tk.VERTICAL, command=self.tree.yview
        )
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Bind selection for delete
        self.tree.bind("<Delete>", lambda e: self.delete_item())
        self.tree.bind("<Up>", lambda e: self.navigate_tree("up"))
        self.tree.bind("<Down>", lambda e: self.navigate_tree("down"))
        self.tree.bind("<Button-1>", self.on_tree_click)

    def _create_bottom_frame(self, parent):
        """Create the bottom frame with actions and total."""
        bottom_frame = ttk.Frame(parent)
        bottom_frame.pack(fill=tk.X, pady=5)

        # Ticket Controls (Small buttons) - Moved to TOP
        ticket_frame = ttk.Frame(bottom_frame)
        ticket_frame.pack(side=tk.TOP, anchor=tk.W, padx=0, pady=0)
        
        self.tickets_container = ttk.Frame(ticket_frame)
        self.tickets_container.pack(side=tk.LEFT)
        
        self.refresh_ticket_buttons()

        # Pack RIGHT elements first to ensure they take priority and don't get cut
        self.total_label = ttk.Label(
            bottom_frame, text="Total: $0.00", style="Total.TLabel"
        )
        self.total_label.pack(side=tk.RIGHT, padx=(10, 0))

        ttk.Button(
            bottom_frame,
            text="F1 - Cobrar",
            command=self.show_payment_window,
            style="Large.Accent.TButton",
        ).pack(side=tk.RIGHT, padx=(8, 0))

        # Pack LEFT elements
        ttk.Button(
            bottom_frame,
            text="Eliminar Producto",
            command=self.delete_item,
            style="DarkGrey.TButton",
        ).pack(side=tk.LEFT, padx=(0, 8))

        ttk.Button(
            bottom_frame,
            text="Entradas",
            command=self.open_entry_window,
            style="Success.TButton",
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            bottom_frame,
            text="Salidas",
            command=self.open_exit_window,
            style="Danger.TButton",
        ).pack(side=tk.LEFT, padx=(0, 10))

        # Status label for messages
        self.status_label = ttk.Label(bottom_frame, text="", style="Subtle.TLabel")
        self.status_label.pack(side=tk.LEFT, padx=(10, 0))

    def open_settings_window(self):
        """Open settings GUI in a new process."""
        script_path = os.path.join(self.base_dir, "settings_gui.py")
        if os.path.exists(script_path):
            subprocess.Popen([sys.executable, script_path])

    def open_products_window(self):
        """Open products GUI in a new process."""
        script_path = os.path.join(self.base_dir, "products_gui.py")
        if os.path.exists(script_path):
            subprocess.Popen([sys.executable, script_path])

    def open_reports_window(self):
        """Open reports GUI in a new process."""
        script_path = os.path.join(self.base_dir, "reports_gui.py")
        if os.path.exists(script_path):
            subprocess.Popen([sys.executable, script_path])

    def open_entry_window(self):
        """Open entry window for cash inflow."""
        EntryExitWindow(self, "Entrada Efectivo", "entries")

    def open_exit_window(self):
        """Open exit window for cash outflow."""
        EntryExitWindow(self, "Salida Efectivo", "exits")

    def log_cash_flow(self, transaction_type, amount, concept):
        """Log cash flow transaction to CSV."""
        timestamp = datetime.now().isoformat()
        filepath = os.path.join(self.base_dir, "flujo_caja.csv")
        with open(filepath, "a", newline="", encoding="utf-8") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                writer = csv.writer(f)
                writer.writerow([timestamp, transaction_type, amount, concept])
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)

    def init_cash_flow_log(self):
        """Initialize flujo_caja.csv with headers if it doesn't exist."""
        filepath = os.path.join(self.base_dir, "flujo_caja.csv")
        if not os.path.exists(filepath):
            with open(filepath, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["fecha_hora", "tipo", "monto", "concepto"])

    def show_suggestions(self, event=None):
        """Schedule product suggestions update (debounce)."""
        # Ignore navigation keys to avoid resetting the list while navigating
        if event and event.keysym in ['Up', 'Down', 'Left', 'Right', 'Return', 'ISO_Left_Tab', 'Tab']:
            return

        # Cancel previous timer if exists
        if self.search_timer:
            self.after_cancel(self.search_timer)
        
        # Schedule new search in 5 seconds (5000ms)
        self.search_timer = self.after(5000, self.perform_search)

    def perform_search(self):
        """Actual search logic executed after debounce."""
        # Save cursor position before updating values
        try:
            cursor_pos = self.product_combobox.index(tk.INSERT)
        except tk.TclError:
            cursor_pos = None

        search_term = self.product_combobox.get().lower().strip()
        if len(search_term) < 1:
            self.product_combobox["values"] = []
            try:
                self.tk.call('ttk::combobox::Unpost', self.product_combobox._w)
            except tk.TclError:
                pass
            return

        suggestions = []
        terms = search_term.split()

        for code, product in self.products.items():
            # Search in both name and code
            search_target = f"{product['nombre']} {code}".lower()
            if all(term in search_target for term in terms):
                suggestions.append(f"{product['nombre']} ({code})")

        if suggestions:
            # Only update if different to avoid flickering
            current_values = self.product_combobox["values"]
            new_values = tuple(suggestions[:15]) # Limit to 15
            
            if current_values != new_values:
                self.product_combobox["values"] = new_values
                try:
                    self.tk.call('ttk::combobox::Post', self.product_combobox._w)
                except tk.TclError:
                    pass
        else:
            self.product_combobox["values"] = []
            try:
                self.tk.call('ttk::combobox::Unpost', self.product_combobox._w)
            except tk.TclError:
                pass

        # Restore cursor position
        if cursor_pos is not None:
            try:
                self.product_combobox.icursor(cursor_pos)
            except tk.TclError:
                pass

    def hide_suggestions(self, event=None):
        """No need to hide for Combobox."""
        pass

    def select_suggestion(self, event=None):
        """Not needed for Combobox."""
        pass

    def add_product(self, event=None):
        """Add product to sale by barcode or name."""
        # Cancel any pending search to prevent dropdown from popping up after addition
        if self.search_timer:
            self.after_cancel(self.search_timer)
            self.search_timer = None

        # Close the dropdown list if it's open
        try:
            self.tk.call('ttk::combobox::Unpost', self.product_combobox._w)
        except tk.TclError:
            pass

        search_term = self.product_combobox.get().strip()
        if not search_term:
            return "break"

        qty = 1

        base_term = search_term
        # Handle if base_term is "Name (code)" from combobox selection
        if "(" in base_term and ")" in base_term:
            possible_code = base_term.split("(")[-1].rstrip(")")
            if possible_code in self.products:
                base_term = possible_code
        
        # Normalize barcode by stripping leading zeros
        normalized_term = base_term.lstrip("0") or "0"

        product = self.products.get(normalized_term)
        barcode = normalized_term
        if not product:
            # Search by name (exact match)
            for code, prod in self.products.items():
                if prod["nombre"].lower() == base_term.lower():
                    product = prod
                    barcode = code
                    break

        # If not found, try smart search (partial/multi-keyword)
        if not product:
            search_terms = base_term.lower().split()
            matches = []
            for code, prod in self.products.items():
                search_target = f"{prod['nombre']} {code}".lower()
                if all(term in search_target for term in search_terms):
                    matches.append((code, prod))
            
            if len(matches) == 1:
                barcode, product = matches[0]
            elif len(matches) > 1:
                self.status_label.config(text=f"Múltiples coincidencias ({len(matches)}). Seleccione de la lista.")
                self.after(2000, lambda: self.status_label.config(text=""))
                # Re-open dropdown if it was closed but we need selection
                try:
                    self.tk.call('ttk::combobox::Post', self.product_combobox._w)
                except tk.TclError:
                    pass
                return "break"

        if product:
            if barcode in self.sale_items:
                self.sale_items[barcode]["qty"] += qty
            else:
                self.sale_items[barcode] = {
                    "nombre": product["nombre"],
                    "precio": product["precio"],
                    "qty": qty,
                }

            self.last_added_barcode = barcode  # Update last added product
            self.update_sale_list()
            self.update_total()
            self.product_combobox.delete(0, tk.END)
            self.product_combobox.focus()
        else:
            self.status_label.config(text=f"Producto '{base_term}' no encontrado.")
            self.after(2000, lambda: self.status_label.config(text=""))
            self.product_combobox.focus()
        
        return "break"

    def focus_next_widget(self):
        """Focus the next logical widget (e.g., from combobox to treeview)."""
        current_focus = self.focus_get()
        if current_focus == self.product_combobox:
            self.tree.focus_set()
            if self.tree.get_children():
                self.tree.selection_set(self.tree.get_children()[0])
        else:
            self.product_combobox.focus_set()

    def on_tree_click(self, event):
        """Handle click on treeview to edit quantity."""
        region = self.tree.identify("region", event.x, event.y)
        if region == "cell":
            column = self.tree.identify_column(event.x)
            # Assuming 'qty' is the 3rd column (index 2), so '#3'
            if column == "#3":
                item_id = self.tree.identify_row(event.y)
                if not item_id:
                    return

                # Get barcode from tags
                barcode = self.tree.item(item_id, "tags")[0]

                bbox = self.tree.bbox(item_id, column)
                if not bbox:
                    return

                # Create Combobox
                # Using 1-10 range as a reasonable default that covers 1, 2, 3
                entry_edit = ttk.Combobox(
                    self.tree, values=[str(i) for i in range(1, 11)], font=("Arial", 14), state="readonly", style="Qty.TCombobox"
                )
                entry_edit.place(x=bbox[0], y=bbox[1], width=bbox[2], height=bbox[3])

                # Set current value
                current_qty = self.sale_items[barcode]["qty"]
                if current_qty > 10:
                     # If existing qty is > 10, add it to values temporarily so it displays correctly
                     entry_edit['values'] = list(entry_edit['values']) + [str(current_qty)]
                
                entry_edit.set(current_qty)

                def save_edit(event=None):
                    try:
                        new_qty = int(entry_edit.get())
                        if new_qty > 0:
                            self.sale_items[barcode]["qty"] = new_qty
                            self.update_sale_list()
                            self.update_total()
                    except ValueError:
                        pass
                    entry_edit.destroy()

                entry_edit.bind("<Return>", save_edit)
                entry_edit.bind("<<ComboboxSelected>>", save_edit)
                entry_edit.bind("<FocusOut>", lambda e: entry_edit.destroy())
                entry_edit.focus_set()
                # Simulate drop down immediately
                entry_edit.event_generate('<Button-1>')

    def navigate_tree(self, direction):
        """Navigate treeview with arrow keys."""
        selected = self.tree.selection()
        if not selected:
            if self.tree.get_children():
                self.tree.selection_set(self.tree.get_children()[0])
            return
        if direction == "up":
            prev = self.tree.prev(selected[0])
            if prev:
                self.tree.selection_set(prev)
        elif direction == "down":
            next = self.tree.next(selected[0])
            if next:
                self.tree.selection_set(next)

    def delete_item(self):
        """Delete selected item from sale."""
        selected_item = self.tree.selection()
        if selected_item:
            item_id = selected_item[0]
            barcode = self.tree.item(item_id, "tags")[0]
            if barcode in self.sale_items:
                del self.sale_items[barcode]
                self.update_sale_list()
                self.update_total()
        else:
            messagebox.showwarning("Advertencia", "Seleccione un ítem para eliminar.")
        
        self.product_combobox.focus_set()

    def update_sale_list(self):
        """Update the Treeview with current sale items."""
        # Clear existing items
        for item in self.tree.get_children():
            self.tree.delete(item)

        # Insert current items
        for barcode, item in self.sale_items.items():
            total_price = item["qty"] * item["precio"]
            tags = (barcode,)
            if self.products.get(barcode, {}).get("inventario", 0) <= 5:
                tags = (barcode, "low_stock")
            self.tree.insert(
                "",
                tk.END,
                values=(
                    barcode,
                    item["nombre"],
                    item["qty"],
                    f"${item['precio']:.2f}",
                    f"${total_price:.2f}",
                ),
                tags=tags,
            )

    def update_total(self):
        """Update the total label and return total."""
        total = sum(item["qty"] * item["precio"] for item in self.sale_items.values())
        self.total_label.config(text=f"Total: ${total:.2f}")
        return total

    def show_payment_window(self):
        """Show payment window if there are items."""
        total = self.update_total()
        if total > 0:
            PaymentWindow(self, total)
        else:
            messagebox.showwarning("Venta Vacía", "No hay ítems en la venta.")
            self.product_combobox.focus()

    def on_closing(self):
        """Handle window closing."""
        for items in self.active_tickets.values():
            self.log_sale(items)
        self.destroy()


class PaymentWindow(tk.Toplevel):
    """Payment window for finalizing sales."""

    def __init__(self, parent, total):
        super().__init__(parent)
        self.parent = parent
        self.total = total
        self.change_value = 0.0
        self.amount_paid = 0.0

        self.title("Finalizar Venta")
        self.geometry("550x500")
        self.transient(parent)
        self.grab_set()
        self.configure(bg=self.parent.colors["background"])
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.create_payment_styles()
        self.create_widgets()

    def create_payment_styles(self):
        """Create custom styles for payment window with larger fonts."""
        style = ttk.Style(self)
        # Green button for Calculate Change and Print
        style.configure(
            "PaymentGreen.TButton",
            font=("Arial", 14, "bold"),
            padding=12,
            background="#28A745",
            foreground="white",
        )
        style.map(
            "PaymentGreen.TButton",
            background=[("active", "#218838"), ("disabled", "#cccccc")],
            foreground=[("disabled", "#666666")],
        )
        # Red button for Close
        style.configure(
            "PaymentRed.TButton",
            font=("Arial", 14, "bold"),
            padding=12,
            background="#DC3545",
            foreground="white",
        )
        style.map(
            "PaymentRed.TButton",
            background=[("active", "#c82333"), ("disabled", "#cccccc")],
            foreground=[("disabled", "#666666")],
        )
        # Blue button for Close
        style.configure(
            "PaymentBlue.TButton",
            font=("Arial", 14, "bold"),
            padding=12,
            background="#007BFF",
            foreground="white",
        )
        style.map(
            "PaymentBlue.TButton",
            background=[("active", "#0069D9"), ("disabled", "#cccccc")],
            foreground=[("disabled", "#666666")],
        )

    def create_widgets(self):
        """Create payment window widgets."""
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            main_frame,
            text=f"Total a Pagar: ${self.total:.2f}",
            font=("Arial", 34, "bold"),
        ).pack(pady=10)

        ttk.Label(main_frame, text="Monto Recibido:", font=("Arial", 18, "bold")).pack(
            pady=5
        )
        self.amount_entry = ttk.Entry(main_frame, font=("Arial", 24))
        self.amount_entry.pack(pady=5, fill=tk.X)
        self.amount_entry.focus()
        self.amount_entry.bind("<Return>", self.calculate_change)
        self.amount_entry.bind("<KP_Enter>", self.calculate_change)

        self.calculate_button = ttk.Button(
            main_frame,
            text="Calcular Cambio",
            command=self.calculate_change,
            style="PaymentGreen.TButton",
        )
        self.calculate_button.pack(pady=(10, 10))

        self.cancel_button = ttk.Button(
            main_frame,
            text="Esc - Cancelar",
            command=self.destroy,
            style="PaymentRed.TButton",
        )
        self.cancel_button.pack(pady=(0, 25))

        # Bind Escape key
        self.bind("<Escape>", lambda e: self.destroy())

        self.change_label = ttk.Label(
            main_frame, text="", style="Success.TLabel", font=("Arial", 36, "bold")
        )
        self.change_label.pack(pady=15)

        # These buttons will be created after calculating change
        self.print_button = None
        self.close_button = None

    def get_ticket_template(self):
        """Return the ticket HTML template as a string. Robust: embedded in code, no file dependency."""
        return """<!DOCTYPE html>
<html lang=\"es">
<head>
    <meta charset=\"UTF-8">
    <title>Recibo de Venta</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 20px; font-size: 14px; max-width: 300px; margin: auto; }
        .header { text-align: center; margin-bottom: 20px; border-bottom: 2px dashed #000; padding-bottom: 10px; }
        .logo { max-width: 150px; max-height: 100px; margin-bottom: 10px; }
        h2 { margin: 5px 0; font-size: 18px; }
        .info { font-size: 12px; line-height: 1.2; }
        table { width: 100%; border-collapse: collapse; margin-bottom: 15px; }
        th, td { border-bottom: 1px solid #ddd; padding: 5px; text-align: left; }
        th { text-align: right; font-weight: bold; }
        .total { font-size: 16px; font-weight: bold; text-align: right; margin: 5px 0; padding: 5px; border-top: 2px solid #000; }
        .footer { margin-top: 20px; text-align: center; font-size: 10px; color: #666; }
    </style>
</head>
<body>
    <div class="header">
        {{logo}}
        <h2>{{business_name}}</h2>
        <div class="info">{{header_info}}</div>
    </div>
    <table>
        <thead>
            <tr>
                <th>Producto</th>
                <th>Precio</th>
            </tr>
        </thead>
        <tbody>
            {{items}}
        </tbody>
    </table>
    <div class="totals">
        {{totals}}
    </div>
    <div class="footer">
        ¡Gracias por su compra. Vuelva pronto!
    </div>
</body>
</html>"""

    def calculate_change(self, event=None):
        """Calculate change and enable print/finalize if sufficient."""
        try:
            self.amount_paid = float(self.amount_entry.get())
            if self.amount_paid < self.total:
                messagebox.showerror(
                    "Error", "Monto recibido es menor al total.", parent=self
                )
                return
            self.change_value = self.amount_paid - self.total
            self.change_label.config(text=f"Cambio: ${self.change_value:.2f}")

            # Disable entry and hide calculate button
            self.amount_entry.config(state="disabled")
            self.amount_entry.unbind("<Return>")
            self.amount_entry.unbind("<KP_Enter>")
            self.calculate_button.pack_forget()
            if hasattr(self, 'cancel_button'):
                self.cancel_button.pack_forget()

            # Create and show the action buttons
            self.show_action_buttons()
        except ValueError:
            messagebox.showerror(
                "Error", "Monto inválido. Por favor ingrese un número.", parent=self
            )

    def show_action_buttons(self):
        """Show Print and Close buttons after calculating change."""
        # Get the parent frame
        main_frame = self.change_label.master

        # Create Print Ticket button (F2 - Green)
        self.print_button = ttk.Button(
            main_frame,
            text="F2 - Imprimir Recibo",
            command=self.print_and_finalize,
            style="PaymentGreen.TButton",
        )
        self.print_button.pack(pady=(15, 8))

        # Create Close button (Ent - Blue)
        self.close_button = ttk.Button(
            main_frame,
            text="Ent - Cerrar",
            command=self.finalize_sale,
            style="PaymentBlue.TButton",
        )
        self.close_button.pack(pady=(8, 20))

        # Bind F2 to print and Enter to close
        self.bind("<F2>", lambda e: self.print_and_finalize())
        self.bind("<Return>", lambda e: self.finalize_sale())
        self.bind("<KP_Enter>", lambda e: self.finalize_sale())

    def print_ticket(self):
        """Print ticket using ThermalPrinter or fallback to HTML."""
        # Data preparation
        business_info = {
            'name': self.parent.settings["business_name"],
            'address': self.parent.settings["address"],
            'phone': self.parent.settings["phone"],
            'cashier': self.parent.settings["cashier_name"],
            'date': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        items = []
        for item in self.parent.sale_items.values():
            items.append({
                'name': item["nombre"],
                'qty': item["qty"],
                'price': item["precio"]
            })
            
        totals = {
            'total': self.total,
            'paid': self.amount_paid,
            'change': self.change_value
        }

        # Try Thermal Printer first
        if ThermalPrinter:
            try:
                printer = ThermalPrinter()
                printer.print_ticket(business_info, items, totals)
                return # Success
            except Exception as e:
                print(f"Thermal printer error: {e}")
                messagebox.showwarning("Thermal Printer", f"Error printing to thermal printer: {e}\nGenerating HTML...")

        ticket_template = self.get_ticket_template()

        # Prepare items HTML with proper escaping
        items_html = ""
        for item in self.parent.sale_items.values():
            name = (
                item["nombre"]
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
            )
            subtotal = item["precio"] * item["qty"]
            items_html += f'<tr><td>{name} (x{item["qty"]})</td><td>${subtotal:.2f}</td></tr>'

        totals_html = f"""
        <div class="total">Total: ${self.total:.2f}</div>
        <div class="total">Efectivo: ${self.amount_paid:.2f}</div>
        <div class="total">Cambio: ${self.change_value:.2f}</div>
        """
        
        # Handle Logo
        logo_html = ""
        if self.parent.settings.get("logo_path") and os.path.exists(self.parent.settings["logo_path"]):
             logo_html = f'<img src="file://{self.parent.settings["logo_path"]}" class="logo" alt="Logo">'

        header_info = f"{business_info['address']}<br>Tel: {business_info['phone']}<br>Cajero: {business_info['cashier']}<br>Fecha: {business_info['date']}"

        html_content = ticket_template.replace("{{logo}}", logo_html) \
            .replace("{{business_name}}", business_info['name']) \
            .replace("{{header_info}}", header_info) \
            .replace("{{items}}", items_html) \
            .replace("{{totals}}", totals_html)

        # Save to temp file and open in browser
        with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as f:
            f.write(html_content.encode("utf-8"))
            temp_path = f.name
        
        webbrowser.open(f"file://{temp_path}")
        
    def print_and_finalize(self):
        """Print ticket and then finalize sale."""
        self.print_ticket()
        self.finalize_sale()

    def finalize_sale(self):
        """Finalize the sale, clear ticket, and close window."""
        self.parent.log_sale()
        self.parent.update_inventory()
        self.parent.log_cash_flow("Venta", self.total, f"Venta Recibo #{self.parent.current_ticket_id}")
        self.parent.clear_sale()
        self.destroy()

    def on_closing(self):
        """Handle window closing."""
        self.destroy()


class EntryExitWindow(tk.Toplevel):
    """Window for cash entry and exit."""

    def __init__(self, parent, title, transaction_type):
        super().__init__(parent)
        self.parent = parent
        self.transaction_type = transaction_type
        
        self.title(title)
        self.geometry("400x300")
        self.configure(bg=self.parent.colors["background"])
        self.transient(parent)
        self.grab_set()
        
        self.create_widgets()

    def create_widgets(self):
        ttk.Label(self, text="Monto:", font=("Arial", 14, "bold")).pack(pady=10)
        self.amount_entry = ttk.Entry(self, font=("Arial", 14))
        self.amount_entry.pack(pady=5, padx=20, fill=tk.X)
        self.amount_entry.focus()
        
        ttk.Label(self, text="Concepto:", font=("Arial", 14, "bold")).pack(pady=10)
        self.concept_entry = ttk.Entry(self, font=("Arial", 14))
        self.concept_entry.pack(pady=5, padx=20, fill=tk.X)
        
        # Bind Enter keys to save
        self.bind("<Return>", lambda e: self.save())
        self.bind("<KP_Enter>", lambda e: self.save())

        ttk.Button(self, text="Ent - Guardar", command=self.save, style="Success.TButton").pack(pady=20)

    def save(self):
        amount_str = self.amount_entry.get()
        concept = self.concept_entry.get()
        
        if not amount_str or not concept:
            messagebox.showwarning("Error", "Todos los campos son obligatorios.")
            return
            
        try:
            amount = float(amount_str)
        except ValueError:
            messagebox.showerror("Error", "Monto inválido.")
            return
            
        if "Entrada" in self.title():
            t_type = "Entrada"
        else:
            t_type = "Salida"
            
        self.parent.log_cash_flow(t_type, amount, concept)
        messagebox.showinfo("Éxito", "Transacción registrada.")
        self.destroy()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        role = sys.argv[1]
    else:
        role = "admin"
    
    app = POS_GUI(user_role=role)
    app.mainloop()
