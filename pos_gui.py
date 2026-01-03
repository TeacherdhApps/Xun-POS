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
    print("ERROR: This application is not compatible with Windows")
    print("=" * 60)
    print("\nThis POS system is designed exclusively for Unix systems")
    print("(Linux, macOS, BSD, etc.) and cannot run on Windows.")
    print("\nPlease use a Linux or macOS system to run this application.")
    print("=" * 60)
    sys.exit(1)


class POS_GUI(tk.Tk):
    def __init__(self, user_role="admin"):
        super().__init__()
        self.title("Point of Sale")
        self.state("normal")
        self.resizable(True, True)
        self.user_role = user_role  # Store user role for access control
        self.is_fullscreen = False  # Track fullscreen state

        self.settings = self.load_settings()
        self.products = self.load_products()
        self.sale_items = {}  # Dictionary to handle quantities: {barcode: {'name': str, 'price': float, 'qty': int}}
        self.last_added_barcode = (
            None  # Track the last added product for quick re-addition
        )

        self.create_styles()
        self.init_sales_log()
        self.init_cash_flow_log()
        self.create_widgets()
        self.update_time()  # Start the clock
        self.product_combobox.focus()  # Focus on product combobox

        # Bind F11 for fullscreen toggle
        self.bind("<F11>", self.toggle_fullscreen)

    def load_settings(self):
        """Load settings from JSON file with default fallback."""
        default_settings = {
            "business_name": "My Business",
            "address": "123 Main St",
            "phone": "555-0123",
            "cashier_name": "Cashier",
        }
        try:
            with open("settings.json", "r", encoding="utf-8") as f:
                loaded = json.load(f)
                default_settings.update(loaded)  # Merge with defaults
                return default_settings
        except (FileNotFoundError, json.JSONDecodeError):
            return default_settings

    def update_time(self):
        """Update date and time labels every second in English format."""
        now = datetime.now()

        # English date formatting
        days = [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        ]
        months = [
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        ]
        day_of_week = days[now.weekday()]
        day = now.day
        month = months[now.month - 1]
        year = now.year

        date_str = f"{day_of_week}, {month} {day}, {year}"
        time_str = now.strftime("%H:%M")

        self.date_label.config(text=date_str)
        self.time_label.config(text=time_str)

        self.after(1000, self.update_time)

    def init_sales_log(self):
        """Initialize sales.csv with headers if it doesn't exist."""
        if not os.path.exists("sales.csv"):
            with open("sales.csv", "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(
                    [
                        "timestamp",
                        "barcode",
                        "name",
                        "quantity",
                        "unit_price",
                        "total_price",
                    ]
                )

    def log_sale(self):
        """Log the current sale to sales.csv."""
        timestamp = datetime.now().isoformat()
        with open("sales.csv", "a", newline="", encoding="utf-8") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                writer = csv.writer(f)
                for barcode, item in self.sale_items.items():
                    writer.writerow(
                        [
                            timestamp,
                            barcode,
                            item["name"],
                            item["qty"],
                            item["price"],
                            item["qty"] * item["price"],
                        ]
                    )
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)

    def update_inventory(self):
        """Update product inventory in products.csv after a sale."""
        filepath = Path("products.csv")
        if not filepath.exists():
            messagebox.showerror("Error", f"File '{filepath}' not found.")
            return

        try:
            with open(filepath, mode="r+", newline="", encoding="utf-8") as file:
                # Acquire an exclusive lock
                fcntl.flock(file, fcntl.LOCK_EX)
                
                try:
                    reader = csv.reader(file)
                    lines = list(reader)
                    
                    if not lines:
                        messagebox.showerror("Error", "Products file is empty.")
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
                                # Assuming 'inventory' is the 4th column (index 3)
                                current_stock = int(products_dict[barcode][3])
                                new_stock = current_stock - item["qty"]
                                products_dict[barcode][3] = str(new_stock)
                                changes_made = True
                            except (ValueError, IndexError):
                                print(f"Warning: Could not update stock for barcode {barcode}")
                    
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
            messagebox.showerror("Error", f"Could not update inventory: {e}")

    def load_products(self):
        """Load products from CSV file."""
        products = {}
        filepath = Path("products.csv")
        if not filepath.exists():
            messagebox.showerror("Error", f"File '{filepath}' not found.")
            self.destroy()
            return products

        try:
            with open(filepath, mode="r", encoding="utf-8") as infile:
                reader = csv.reader(infile)
                header = next(reader, None)  # Skip header
                if not header:
                    raise ValueError("Products file empty or missing headers.")
                for row_num, row in enumerate(reader, start=2):
                    if len(row) >= 4:  # At least barcode, name, price, inventory
                        barcode, name, price_str, inventory_str = row[0:4]
                        try:
                            price = float(price_str)
                            inventory = int(inventory_str)
                            products[barcode] = {
                                "name": name.strip(),
                                "price": price,
                                "inventory": inventory,
                            }
                        except ValueError:
                            print(
                                f"Warning: Invalid price or inventory in row {row_num}"
                            )
                    elif len(row) >= 3:  # Fallback for rows without inventory
                        barcode, name, price_str = row[0:3]
                        try:
                            price = float(price_str)
                            products[barcode] = {
                                "name": name.strip(),
                                "price": price,
                                "inventory": 0,  # Default inventory to 0
                            }
                        except ValueError:
                            print(f"Warning: Invalid price in row {row_num}")
                    else:
                        print(f"Warning: Incomplete row {row_num}: {row}")
        except Exception as e:
            messagebox.showerror(
                "Data Error", f"Error reading product data: {e}"
            )
            self.destroy()
        return products

    def create_styles(self):
        """Configure ttk styles."""
        style = ttk.Style(self)
        style.theme_use("clam")

        # Palette
        BG_COLOR = "#F0F0F0"
        TEXT_COLOR = "#212529"
        SECONDARY_TEXT_COLOR = "#6C757D"
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
        style.configure("TButton", font=("Arial", 12, "bold"), padding=5)
        style.map(
            "TButton",
            background=[("active", "#EAEAEA")],
            foreground=[("active", BLACK)],
        )

        # Treeview styles
        style.configure(
            "Treeview",
            font=("Arial", 16),
            rowheight=35,
            background=WHITE,
            fieldbackground=WHITE,
            foreground=TEXT_COLOR,
        )
        style.map("Treeview", background=[("selected", ACCENT_COLOR)])
        style.configure(
            "Treeview.Heading",
            font=("Arial", 16, "bold"),
            background=BG_COLOR,
            foreground=BLACK,
        )

        # Custom Label styles
        style.configure(
            "Total.TLabel",
            font=("Arial", 36, "bold"),
            background=BG_COLOR,
            foreground=BLACK,
        )
        style.configure(
            "Header.TLabel",
            font=("Arial", 28, "bold"),
            background=BG_COLOR,
            foreground=BLACK,
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
        style.configure("Accent.TButton", foreground=WHITE, background=ACCENT_COLOR)
        style.map("Accent.TButton", background=[("active", "#0056b3")])

        style.configure("Success.TButton", foreground=WHITE, background=SUCCESS_COLOR)
        style.map("Success.TButton", background=[("active", "#1E7E34")])

        style.configure("Danger.TButton", foreground=WHITE, background=DANGER_COLOR)
        style.map("Danger.TButton", background=[("active", "#BD2130")])

        # Custom style for larger Accent buttons
        style.configure(
            "Large.Accent.TButton",
            foreground=WHITE,
            background=ACCENT_COLOR,
            font=("Arial", 16, "bold"),  # Larger font
            padding=[20, 15],  # More padding (horizontal, vertical)
        )
        style.map("Large.Accent.TButton", background=[("active", "#0056b3")])

        # Custom style for dark grey buttons
        style.configure("DarkGrey.TButton", foreground=WHITE, background=TEXT_COLOR)
        style.map("DarkGrey.TButton", background=[("active", SECONDARY_TEXT_COLOR)])

        # Black Exit button
        style.configure("Exit.TButton", foreground=WHITE, background="#000000")
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
        # Bind F2 to open settings window
        self.bind("<F2>", lambda event: self.open_settings_window())
        # Bind F3 to open products window
        self.bind("<F3>", lambda event: self.open_products_window())
        # Bind F4 to open reports window (only for admin)
        if self.user_role == "admin":
            self.bind("<F4>", lambda event: self.open_reports_window())
        # Bind F12 to exit application
        self.bind("<F12>", lambda event: self.destroy())
        # Bind '+' key to add one more of the last product
        self.bind("<plus>", lambda event: self.add_one_more_last_product())
        self.bind("<KP_Add>", lambda event: self.add_one_more_last_product())
        # Bind Tab to focus next widget
        self.bind("<Tab>", lambda event: self.focus_next_widget())

    def _create_menu_bar(self, parent):
        """Create the top menu bar."""
        menu_frame = ttk.Frame(parent)
        menu_frame.pack(fill=tk.X, pady=(0, 10))

        business_name_label = ttk.Label(
            menu_frame, text=self.settings["business_name"], style="Header.TLabel"
        )
        business_name_label.pack(side=tk.TOP, pady=(0, 5))

        # Frame for date and time
        datetime_frame = ttk.Frame(menu_frame)
        datetime_frame.pack(side=tk.LEFT, padx=10)

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
                button_frame, text="F2 - Settings", command=self.open_settings_window
            ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            button_frame, text="F3 - Products", command=self.open_products_window
        ).pack(side=tk.LEFT, padx=5)

        # Only show Reports button for admin
        if self.user_role == "admin":
            ttk.Button(
                button_frame, text="F4 - Reports", command=self.open_reports_window
            ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            button_frame, text="F12 - Exit", command=self.destroy, style="Exit.TButton"
        ).pack(side=tk.LEFT)

    def _create_top_frame(self, parent):
        """Create the top frame for product entry."""
        top_frame = ttk.Frame(parent)
        top_frame.pack(fill=tk.X, pady=40)  # Increased pady

        ttk.Label(
            top_frame,
            text="Search Product (Code or Name):",
            font=("Arial", 20, "bold"),
        ).pack(  # Increased font
            side=tk.LEFT, padx=(0, 20)
        )

        self.product_combobox = ttk.Combobox(
            top_frame, font=("Arial", 24, "bold")
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
        self.tree.tag_configure("low_stock", background="red")
        self.tree.heading("barcode", text="Code")
        self.tree.heading("name", text="Product")
        self.tree.heading("qty", text="Quantity")
        self.tree.heading("price", text="Unit Price")
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

    def _create_bottom_frame(self, parent):
        """Create the bottom frame with actions and total."""
        bottom_frame = ttk.Frame(parent)
        bottom_frame.pack(fill=tk.X, pady=10)

        # Pack RIGHT elements first to ensure they take priority and don't get cut
        self.total_label = ttk.Label(
            bottom_frame, text="Total: $0.00", style="Total.TLabel"
        )
        self.total_label.pack(side=tk.RIGHT, padx=(10, 0))

        ttk.Button(
            bottom_frame,
            text="F1 - Pay",
            command=self.show_payment_window,
            style="Large.Accent.TButton",
        ).pack(side=tk.RIGHT, padx=(8, 0))

        # Pack LEFT elements
        ttk.Button(
            bottom_frame,
            text="Delete Selected",
            command=self.delete_item,
            style="DarkGrey.TButton",
        ).pack(side=tk.LEFT, padx=(0, 10))

        ttk.Button(
            bottom_frame,
            text="Cash In",
            command=self.open_entry_window,
            style="Success.TButton",
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            bottom_frame,
            text="Cash Out",
            command=self.open_exit_window,
            style="Danger.TButton",
        ).pack(side=tk.LEFT, padx=(0, 10))

        # Status label for messages
        self.status_label = ttk.Label(bottom_frame, text="", style="Subtle.TLabel")
        self.status_label.pack(side=tk.LEFT, padx=(10, 0))

        # Footer with store info
        footer_frame = ttk.Frame(parent)
        footer_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=(5, 0))

        footer_label = ttk.Label(
            footer_frame,
            text="@Xun-POS",
            font=("Arial", 8),
            foreground="#666666",
        )
        footer_label.pack(side=tk.RIGHT, padx=5)

    def open_settings_window(self):
        """Open settings GUI in a new process."""
        if Path("settings_gui.py").exists():
            subprocess.Popen([sys.executable, "settings_gui.py"])

    def open_products_window(self):
        """Open products GUI in a new process."""
        if Path("products_gui.py").exists():
            subprocess.Popen([sys.executable, "products_gui.py"])

    def open_reports_window(self):
        """Open reports GUI in a new process."""
        if Path("reports_gui.py").exists():
            subprocess.Popen([sys.executable, "reports_gui.py"])

    def open_entry_window(self):
        """Open entry window for cash inflow."""
        EntryExitWindow(self, "Cash In", "entries")

    def open_exit_window(self):
        """Open exit window for cash outflow."""
        EntryExitWindow(self, "Cash Out", "exits")

    def log_cash_flow(self, transaction_type, amount, concept):
        """Log cash flow transaction to CSV."""
        timestamp = datetime.now().isoformat()
        with open("cash_flow.csv", "a", newline="", encoding="utf-8") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                writer = csv.writer(f)
                writer.writerow([timestamp, transaction_type, amount, concept])
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)

    def init_cash_flow_log(self):
        """Initialize cash_flow.csv with headers if it doesn't exist."""
        if not os.path.exists("cash_flow.csv"):
            with open("cash_flow.csv", "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["timestamp", "type", "amount", "concept"])

    def show_suggestions(self, event=None):
        """Show product suggestions based on search term."""
        search_term = self.product_combobox.get().lower().strip()
        if len(search_term) < 1:
            self.product_combobox["values"] = []
            return

        suggestions = []
        for code, product in self.products.items():
            if search_term in code.lower() or search_term in product["name"].lower():
                suggestions.append(f"{product['name']} ({code})")

        if suggestions:
            self.product_combobox["values"] = suggestions[
                :10
            ]  # Limit to 10 suggestions
        else:
            self.product_combobox["values"] = []

    def hide_suggestions(self, event=None):
        """No need to hide for Combobox."""
        pass

    def select_suggestion(self, event=None):
        """Not needed for Combobox."""
        pass

    def add_product(self, event=None):
        """Add product to sale by barcode or name."""
        search_term = self.product_combobox.get().strip()
        if not search_term:
            return

        # Parse quantity from search_term, e.g., "CODE*5" or "NAME*2"
        parts = search_term.split("*", 1)
        base_term = parts[0].strip()
        # Handle if base_term is "Name (code)" from combobox selection
        if "(" in base_term and ")" in base_term:
            base_term = base_term.split("(")[-1].rstrip(")")
        qty = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1

        product = self.products.get(base_term)
        barcode = base_term
        if not product:
            # Search by name (case-insensitive)
            for code, prod in self.products.items():
                if prod["name"].lower() == base_term.lower():
                    product = prod
                    barcode = code
                    break

        if product:
            if barcode in self.sale_items:
                self.sale_items[barcode]["qty"] += qty
            else:
                self.sale_items[barcode] = {
                    "name": product["name"],
                    "price": product["price"],
                    "qty": qty,
                }

            self.last_added_barcode = barcode  # Update last added product
            self.update_sale_list()
            self.update_total()
            self.product_combobox.delete(0, tk.END)
            self.product_combobox.focus()
        else:
            self.status_label.config(text=f"Product '{base_term}' not found.")
            self.after(2000, lambda: self.status_label.config(text=""))
            self.product_combobox.focus()

    def add_one_more_last_product(self):
        """Adds one more quantity of the last product added to the sale."""
        if self.last_added_barcode and self.last_added_barcode in self.sale_items:
            self.sale_items[self.last_added_barcode]["qty"] += 1
            self.update_sale_list()
            self.update_total()
        else:
            self.status_label.config(
                text="No previous product to add."
            )
            self.after(2000, lambda: self.status_label.config(text=""))

    def focus_next_widget(self):
        """Focus the next logical widget (e.g., from combobox to treeview)."""
        current_focus = self.focus_get()
        if current_focus == self.product_combobox:
            self.tree.focus_set()
            if self.tree.get_children():
                self.tree.selection_set(self.tree.get_children()[0])
        else:
            self.product_combobox.focus_set()

    def clear_sale(self):
        """Clear the current sale."""
        self.sale_items = {}
        self.update_sale_list()
        self.update_total()
        self.product_combobox.focus()

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
            messagebox.showwarning("Warning", "Select an item to delete.")

    def update_sale_list(self):
        """Update the Treeview with current sale items."""
        # Clear existing items
        for item in self.tree.get_children():
            self.tree.delete(item)

        # Insert current items
        for barcode, item in self.sale_items.items():
            total_price = item["qty"] * item["price"]
            tags = (barcode,)
            if self.products.get(barcode, {}).get("inventory", 0) <= 5:
                tags = (barcode, "low_stock")
            self.tree.insert(
                "",
                tk.END,
                values=(
                    barcode,
                    item["name"],
                    item["qty"],
                    f"${item['price']:.2f}",
                    f"${total_price:.2f}",
                ),
                tags=tags,
            )

    def update_total(self):
        """Update the total label and return total."""
        total = sum(item["qty"] * item["price"] for item in self.sale_items.values())
        self.total_label.config(text=f"Total: ${total:.2f}")
        return total

    def show_payment_window(self):
        """Show payment window if there are items."""
        total = self.update_total()
        if total > 0:
            PaymentWindow(self, total)
        else:
            messagebox.showwarning("Empty Sale", "No items in the sale.")
            self.product_combobox.focus()

    def reset_sale(self):
        """Reset the sale items and UI."""
        self.sale_items = {}
        self.update_sale_list()
        self.update_total()
        self.product_combobox.focus()

    def on_closing(self):
        """Handle window closing."""
        self.log_sale() if self.sale_items else None
        self.destroy()


class PaymentWindow(tk.Toplevel):
    """Payment window for finalizing sales."""

    def __init__(self, parent, total):
        super().__init__(parent)
        self.parent = parent
        self.total = total
        self.change_value = 0.0
        self.amount_paid = 0.0

        self.title("Finalize Sale")
        self.geometry("550x500")
        self.transient(parent)
        self.grab_set()
        self.configure(bg="#f0f0f0")
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
            text=f"Total to Pay: ${self.total:.2f}",
            font=("Arial", 34, "bold"),
        ).pack(pady=10)

        ttk.Label(main_frame, text="Amount Received:", font=("Arial", 18, "bold")).pack(
            pady=5
        )
        self.amount_entry = ttk.Entry(main_frame, font=("Arial", 24))
        self.amount_entry.pack(pady=5, fill=tk.X)
        self.amount_entry.focus()
        self.amount_entry.bind("<Return>", self.calculate_change)
        self.amount_entry.bind("<KP_Enter>", self.calculate_change)

        self.calculate_button = ttk.Button(
            main_frame,
            text="Calculate Change",
            command=self.calculate_change,
            style="PaymentGreen.TButton",
        )
        self.calculate_button.pack(pady=(10, 10))

        self.cancel_button = ttk.Button(
            main_frame,
            text="Esc - Cancel",
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

    def print_and_finalize(self):
        """Print ticket and finalize sale."""
        self.print_ticket()
        self.finalize_sale()

    def finalize_sale(self):
        """Log sale, update inventory and close."""
        self.parent.log_sale()
        self.parent.update_inventory()
        self.parent.reset_sale()
        self.destroy()

    def on_closing(self):
        """Handle window closing."""
        self.destroy()

    def get_ticket_template(self):
        """Return the ticket HTML template as a string. Robust: embedded in code, no file dependency."""
        return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Sales Receipt</title>
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
                <th>Product</th>
                <th>Price</th>
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
        Thank you for your purchase. Come back soon!
    </div>
</body>
</html>"""

    def calculate_change(self, event=None):
        """Calculate change and enable print/finalize if sufficient."""
        try:
            self.amount_paid = float(self.amount_entry.get())
            if self.amount_paid < self.total:
                messagebox.showerror(
                    "Error", "Amount received is less than total.", parent=self
                )
                return
            self.change_value = self.amount_paid - self.total
            self.change_label.config(text=f"Change: ${self.change_value:.2f}")

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
                "Error", "Invalid amount. Please enter a number.", parent=self
            )

    def show_action_buttons(self):
        """Show Print and Close buttons after calculating change."""
        # Get the parent frame
        main_frame = self.change_label.master

        # Create Print Ticket button (F2 - Green)
        self.print_button = ttk.Button(
            main_frame,
            text="F2 - Print Ticket",
            command=self.print_and_finalize,
            style="PaymentGreen.TButton",
        )
        self.print_button.pack(pady=(15, 8))

        # Create Close button (Ent - Blue)
        self.close_button = ttk.Button(
            main_frame,
            text="Ent - Close",
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
                'name': item["name"],
                'qty': item["qty"],
                'price': item["price"]
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
                item["name"]
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
            )
            subtotal = item["price"] * item["qty"]
            items_html += f'<tr><td>{name} (x{item["qty"]})</td><td style="text-align:right">${subtotal:.2f}</td></tr>'

        # Prepare totals HTML
        totals_html = (
            f'<div class="total">Total: ${self.total:.2f}</div>'
            f'<div class="total">Paid: ${self.amount_paid:.2f}</div>'
            f'<div class="total">Change: ${self.change_value:.2f}</div>'
        )
        
        # Prepare header info
        header_info = (
            f"{business_info['address']}<br>"
            f"Tel: {business_info['phone']}<br>"
            f"Cashier: {business_info['cashier']}<br>"
            f"Date: {business_info['date']}"
        )

        # Replace placeholders
        html_content = ticket_template.replace("{{business_name}}", business_info['name'])
        html_content = html_content.replace("{{header_info}}", header_info)
        html_content = html_content.replace("{{items}}", items_html)
        html_content = html_content.replace("{{totals}}", totals_html)
        html_content = html_content.replace("{{logo}}", "") # Logo handling if needed

        # Write to temporary file and open
        try:
            temp_file = os.path.join(tempfile.gettempdir(), f"receipt_{datetime.now().strftime('%Y%m%d%H%M%S')}.html")
            with open(temp_file, "w", encoding="utf-8") as f:
                f.write(html_content)
            
            webbrowser.open(f"file://{temp_file}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Could not generate receipt: {e}")


class EntryExitWindow(tk.Toplevel):
    """Window for recording cash entries and exits."""

    def __init__(self, parent, title, transaction_type):
        super().__init__(parent)
        self.parent = parent
        self.transaction_type = transaction_type

        self.title(title)
        self.geometry("400x350")
        self.transient(parent)
        self.grab_set()
        self.configure(bg="#f0f0f0")

        self.create_widgets(title)

    def create_widgets(self, title):
        main_frame = ttk.Frame(self, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=title, font=("Arial", 20, "bold")).pack(pady=(0, 20))

        ttk.Label(main_frame, text="Amount:").pack(anchor="w")
        self.amount_entry = ttk.Entry(main_frame, font=("Arial", 14))
        self.amount_entry.pack(fill=tk.X, pady=(0, 15))
        self.amount_entry.focus()

        ttk.Label(main_frame, text="Concept:").pack(anchor="w")
        self.concept_entry = ttk.Entry(main_frame, font=("Arial", 14))
        self.concept_entry.pack(fill=tk.X, pady=(0, 20))

        btn_style = (
            "Success.TButton"
            if self.transaction_type == "entries"
            else "Danger.TButton"
        )

        ttk.Button(main_frame, text="Save", command=self.save, style=btn_style).pack(
            fill=tk.X, pady=5
        )

        ttk.Button(main_frame, text="Cancel", command=self.destroy).pack(
            fill=tk.X, pady=5
        )

        # Bindings
        self.bind("<Return>", lambda e: self.save())
        self.bind("<KP_Enter>", lambda e: self.save())
        self.bind("<Escape>", lambda e: self.destroy())

    def save(self):
        try:
            amount_str = self.amount_entry.get()
            if not amount_str:
                return
            amount = float(amount_str)
            concept = self.concept_entry.get().strip()

            if not concept:
                messagebox.showerror("Error", "Concept cannot be empty.", parent=self)
                return

            self.parent.log_cash_flow(self.transaction_type, amount, concept)
            messagebox.showinfo(
                "Success",
                f"{self.transaction_type.capitalize()} recorded.",
                parent=self,
            )
            self.destroy()
        except ValueError:
            messagebox.showerror("Error", "Invalid amount.", parent=self)


if __name__ == "__main__":
    role = "admin"
    if len(sys.argv) > 1:
        role = sys.argv[1]
    
    app = POS_GUI(user_role=role)
    app.mainloop()