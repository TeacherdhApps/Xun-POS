#!/usr/bin/env python3
import base64
import csv
import fcntl
import json
import os
import platform
import sys
import tempfile
import tkinter as tk
import webbrowser
from datetime import date, datetime, timedelta
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

# Note: This application requires the tkcalendar library.
# You can install it with: pip install tkcalendar
try:
    from tkcalendar import DateEntry
except ImportError:
    messagebox.showerror(
        "Error de Dependencia",
        "La librería 'tkcalendar' no está instalada.\n\nPor favor instálela ejecutando:\npip install tkcalendar",
    )
    exit()


class ReportsApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Reportes de Ventas")
        self.geometry("1400x720")
        self.selected_report_date = date.today()
        self.is_fullscreen = False  # Track fullscreen state
        
        # Base directory for absolute paths
        self.base_dir = os.path.dirname(os.path.abspath(__file__))

        self.settings = self.load_settings()
        self._initialized = False
        self.create_styles()
        self.init_sales_log()
        self.create_widgets()
        self._initialized = True
        self.load_report_for_date()

        # Bind F11 for fullscreen toggle
        self.bind("<F11>", self.toggle_fullscreen)

    def load_settings(self):
        """Load settings from JSON file with default fallback."""
        default_settings = {
            "business_name": "Mi Negocio",
            "address": "Calle Principal 123",
            "phone": "555-0123",
            "cashier_name": "Cajero",
        }
        try:
            settings_path = os.path.join(self.base_dir, "settings.json")
            with open(settings_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                default_settings.update(loaded)  # Merge with defaults
                return default_settings
        except (FileNotFoundError, json.JSONDecodeError):
            return default_settings

    def init_sales_log(self):
        # Ensure ventas.csv exists with headers if not present
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
        style.configure("TButton", font=("Arial", 12, "bold"), padding=10)
        style.map(
            "TButton",
            background=[("active", "#EAEAEA")],
            foreground=[("active", BLACK)],
        )

        # Treeview styles
        style.configure(
            "Treeview",
            font=("Arial", 12),
            rowheight=30,
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

        # Custom styles
        style.configure("Big.TButton", font=("Arial", 12, "bold"), padding=8)
        
        # Action buttons uniform style
        ACTION_FONT = ("Arial", 14, "bold")
        ACTION_PADDING = 12

        style.configure(
            "Print.TButton",
            foreground=WHITE,
            background=SUCCESS_COLOR,
            font=ACTION_FONT,
            padding=ACTION_PADDING,
        )
        style.map("Print.TButton", background=[("active", "#218838")])

        style.configure(
            "Modify.TButton",
            foreground=WHITE,
            background=ACCENT_COLOR,
            font=ACTION_FONT,
            padding=ACTION_PADDING,
        )
        style.map("Modify.TButton", background=[("active", "#0056b3")])

        style.configure(
            "Danger.Action.TButton",
            foreground=WHITE,
            background=DANGER_COLOR,
            font=ACTION_FONT,
            padding=ACTION_PADDING,
        )
        style.map("Danger.Action.TButton", background=[("active", "#c82333")])

        style.configure(
            "Exit.TButton",
            foreground=WHITE,
            background="#000000",
            font=ACTION_FONT,
            padding=ACTION_PADDING,
        )
        style.map("Exit.TButton", background=[("active", "#333333")])

        style.configure(
            "Total.TLabel",
            font=("Arial", 20, "bold"),
            background=BG_COLOR,
            foreground=BLACK,
        )
        style.configure(
            "Success.Total.TLabel",
            font=("Arial", 20, "bold"),
            background=BG_COLOR,
            foreground=SUCCESS_COLOR,
        )
        style.configure(
            "Danger.Total.TLabel",
            font=("Arial", 20, "bold"),
            background=BG_COLOR,
            foreground=DANGER_COLOR,
        )
        style.configure(
            "Net.Total.TLabel",
            font=("Arial", 20, "bold"),
            background=BG_COLOR,
            foreground=ACCENT_COLOR,
        )
        style.configure(
            "Date.TLabel",
            font=("Arial", 18, "bold"),
            background=BG_COLOR,
            foreground=BLACK,
        )

        style.configure("Accent.TButton", foreground=WHITE, background=ACCENT_COLOR)
        style.map("Accent.TButton", background=[("active", "#0056b3")])

    def toggle_fullscreen(self, event=None):
        """Toggle fullscreen mode with F11."""
        self.is_fullscreen = not self.is_fullscreen
        self.attributes("-fullscreen", self.is_fullscreen)
        return "break"

    def create_widgets(self):
        main_frame = ttk.Frame(self, padding=8)
        main_frame.pack(fill=tk.BOTH, expand=True)

        top_frame = ttk.Frame(main_frame, padding=8)
        top_frame.pack(fill=tk.X)

        # Header Info Label
        info_label = ttk.Label(
            top_frame,
            text="@Xun-POS restaurant",
            font=("Arial", 8),
            foreground="#666666",
        )
        info_label.pack(side=tk.RIGHT, anchor=tk.NE)

        self.report_date_label = ttk.Label(
            top_frame,
            text=f"Reporte del: {self.selected_report_date.strftime('%Y-%m-%d')}",
            style="Date.TLabel",
        )
        self.report_date_label.pack(pady=10)

        cal_frame = ttk.Frame(main_frame, padding=12)
        cal_frame.pack(pady=8, fill=tk.X)

        # Configure grid columns for horizontal distribution
        cal_frame.columnconfigure(0, weight=0)  # From label
        cal_frame.columnconfigure(1, weight=1)  # Start calendar
        cal_frame.columnconfigure(2, weight=0)  # To label
        cal_frame.columnconfigure(3, weight=1)  # End calendar
        cal_frame.columnconfigure(4, weight=0)  # Spacer
        cal_frame.columnconfigure(5, weight=1)  # Print button
        cal_frame.columnconfigure(6, weight=1)  # Modify button
        cal_frame.columnconfigure(7, weight=1)  # Delete button
        cal_frame.columnconfigure(8, weight=1)  # Exit button

        # Row 0: Calendar widgets and buttons
        ttk.Label(cal_frame, text="Desde:", font=("Arial", 14, "bold")).grid(
            row=0, column=0, padx=5, sticky="e"
        )
        self.start_cal = DateEntry(
            cal_frame,
            width=15,
            background="#007BFF",
            foreground="white",
            borderwidth=3,
            date_pattern="yyyy-mm-dd",
            font=("Arial", 14),
            locale="es_ES",
        )
        self.start_cal.grid(row=0, column=1, padx=5, sticky="ew")

        ttk.Label(cal_frame, text="Hasta:", font=("Arial", 14, "bold")).grid(
            row=0, column=2, padx=5, sticky="e"
        )
        self.end_cal = DateEntry(
            cal_frame,
            width=15,
            background="#007BFF",
            foreground="white",
            borderwidth=3,
            date_pattern="yyyy-mm-dd",
            font=("Arial", 14),
            locale="es_ES",
        )
        self.end_cal.grid(row=0, column=3, padx=5, sticky="ew")

        self.start_cal.bind("<<DateEntrySelected>>", self.on_date_change)
        self.end_cal.bind("<<DateEntrySelected>>", self.on_date_change)

        # Spacer
        ttk.Label(cal_frame, text="").grid(row=0, column=4, padx=20)

        # Add Print and Exit buttons
        ttk.Button(
            cal_frame,
            text="F2 - Imprimir",
            command=self.print_report,
            style="Print.TButton",
        ).grid(row=0, column=5, padx=5, sticky="ew")

        ttk.Button(
            cal_frame,
            text="F6 - Modificar",
            command=self.modify_cash_flow,
            style="Modify.TButton",
        ).grid(row=0, column=6, padx=5, sticky="ew")

        ttk.Button(
            cal_frame,
            text="F7 - Borrar",
            command=self.delete_cash_flow,
            style="Danger.Action.TButton",
        ).grid(row=0, column=7, padx=5, sticky="ew")

        ttk.Button(
            cal_frame,
            text="F12 - Salir",
            command=self.exit_app,
            style="Exit.TButton",
        ).grid(row=0, column=8, padx=5, sticky="ew")

        # Bind F2 and F12 keys
        self.bind("<F2>", lambda e: self.print_report())
        self.bind("<F6>", lambda e: self.modify_cash_flow())
        self.bind("<F7>", lambda e: self.delete_cash_flow())
        self.bind("<F12>", lambda e: self.exit_app())

        content_frame = ttk.Frame(main_frame)
        content_frame.pack(fill=tk.BOTH, expand=True)

        # Left side for sales
        sales_frame = ttk.LabelFrame(content_frame, text="Ventas", padding=8)
        sales_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.report_tree = ttk.Treeview(
            sales_frame, columns=("time", "name", "qty", "total"), show="headings"
        )
        self.report_tree.heading("time", text="Hora")
        self.report_tree.heading("name", text="Producto")
        self.report_tree.heading("qty", text="Cantidad")
        self.report_tree.heading("total", text="Total")
        self.report_tree.column("time", width=150, anchor=tk.CENTER, stretch=tk.NO)
        self.report_tree.column("name", stretch=tk.YES)
        self.report_tree.column("qty", width=80, anchor=tk.CENTER, stretch=tk.NO)
        self.report_tree.column("total", width=100, anchor=tk.E, stretch=tk.NO)
        self.report_tree.pack(fill=tk.BOTH, expand=True)

        # Right side for cash flow
        cash_flow_frame = ttk.LabelFrame(
            content_frame, text="Flujo de Caja", padding=8
        )
        cash_flow_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.cash_flow_tree = ttk.Treeview(
            cash_flow_frame,
            columns=("time", "type", "amount", "concept"),
            show="headings",
        )
        self.cash_flow_tree.heading("time", text="Hora")
        self.cash_flow_tree.heading("type", text="Tipo")
        self.cash_flow_tree.heading("amount", text="Monto")
        self.cash_flow_tree.heading("concept", text="Concepto")
        self.cash_flow_tree.column("time", width=150, anchor=tk.CENTER, stretch=tk.NO)
        self.cash_flow_tree.column("type", width=80, anchor=tk.CENTER, stretch=tk.NO)
        self.cash_flow_tree.column("amount", width=100, anchor=tk.E, stretch=tk.NO)
        self.cash_flow_tree.column("concept", stretch=tk.YES)
        self.cash_flow_tree.pack(fill=tk.BOTH, expand=True)

        # Bottom summary - 4 columns layout
        summary_frame = ttk.Frame(main_frame, padding=10)
        summary_frame.pack(fill=tk.X)

        # Create 4 equal columns
        summary_frame.columnconfigure(0, weight=1, uniform="totals")
        summary_frame.columnconfigure(1, weight=1, uniform="totals")
        summary_frame.columnconfigure(2, weight=1, uniform="totals")
        summary_frame.columnconfigure(3, weight=1, uniform="totals")

        # Column 1: Total Sales
        ventas_col = ttk.Frame(summary_frame)
        ventas_col.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")
        ttk.Label(ventas_col, text="Ventas Totales", font=("Arial", 11, "bold")).pack()
        self.report_total_label = ttk.Label(
            ventas_col, text="$0.00", style="Total.TLabel"
        )
        self.report_total_label.pack()

        # Column 2: Total Entries
        entradas_col = ttk.Frame(summary_frame)
        entradas_col.grid(row=0, column=1, padx=5, pady=5, sticky="nsew")
        ttk.Label(
            entradas_col, text="Entradas Totales", font=("Arial", 11, "bold")
        ).pack()
        self.entradas_total_label = ttk.Label(
            entradas_col, text="$0.00", style="Success.Total.TLabel"
        )
        self.entradas_total_label.pack()

        # Column 3: Total Exits
        salidas_col = ttk.Frame(summary_frame)
        salidas_col.grid(row=0, column=2, padx=5, pady=5, sticky="nsew")
        ttk.Label(salidas_col, text="Salidas Totales", font=("Arial", 11, "bold")).pack()
        self.salidas_total_label = ttk.Label(
            salidas_col, text="$0.00", style="Danger.Total.TLabel"
        )
        self.salidas_total_label.pack()

        # Column 4: Net Total
        general_col = ttk.Frame(summary_frame)
        general_col.grid(row=0, column=3, padx=5, pady=5, sticky="nsew")
        ttk.Label(general_col, text="Total Neto", font=("Arial", 11, "bold")).pack()
        self.net_total_label = ttk.Label(
            general_col, text="$0.00", style="Net.Total.TLabel"
        )
        self.net_total_label.pack()

    def set_report_date(self, day):
        today = date.today()
        if day == "today":
            self.selected_report_date = today
        elif day == "yesterday":
            self.selected_report_date = today - timedelta(days=1)

        self.start_cal.set_date(self.selected_report_date)
        self.end_cal.set_date(self.selected_report_date)
        self.load_report_for_date()

    def on_date_change(self, event):
        if hasattr(self, "_initialized") and self._initialized:
            self.load_report_for_date_range()

    def date_selected_from_calendar(self, event):
        self.selected_report_date = self.start_cal.get_date()
        self.load_report_for_date()

    def load_report_for_date_range(self):
        start_date = self.start_cal.get_date()
        end_date = self.end_cal.get_date()
        self.report_date_label.config(
            text=f"Reporte Desde: {start_date.strftime('%Y-%m-%d')} Hasta: {end_date.strftime('%Y-%m-%d')}"
        )
        self.load_report_for_date(start_date, end_date)

    def load_report_for_date(self, start_date=None, end_date=None):
        if start_date is None:
            start_date = self.selected_report_date
        if end_date is None:
            end_date = self.selected_report_date

        if start_date == end_date:
            self.report_date_label.config(
                text=f"Reporte del: {start_date.strftime('%Y-%m-%d')}"
            )
        else:
            self.report_date_label.config(
                text=f"Reporte Desde: {start_date.strftime('%Y-%m-%d')} Hasta: {end_date.strftime('%Y-%m-%d')}"
            )
        for i in self.report_tree.get_children():
            self.report_tree.delete(i)
        for i in self.cash_flow_tree.get_children():
            self.cash_flow_tree.delete(i)

        daily_total = 0.0
        entries_total = 0.0
        exits_total = 0.0

        try:
            sales_path = os.path.join(self.base_dir, "ventas.csv")
            with open(sales_path, "r", encoding="utf-8") as f:
                fcntl.flock(f, fcntl.LOCK_SH)
                try:
                    reader = csv.DictReader(f)
                    for row in reader:
                        sale_date = datetime.fromisoformat(row["fecha_hora"]).date()
                        if start_date <= sale_date <= end_date:
                            sale_time = datetime.fromisoformat(row["fecha_hora"]).strftime(
                                "%Y-%m-%d %H:%M:%S"
                            )
                            # Using Spanish CSV headers: total
                            total_price = float(row["total"])
                            self.report_tree.insert(
                                "",
                                tk.END,
                                values=(
                                    sale_time,
                                    row["nombre"],
                                    row["cantidad"],
                                    f"${total_price:.2f}",
                                ),
                            )
                            daily_total += total_price
                finally:
                    fcntl.flock(f, fcntl.LOCK_UN)
        except FileNotFoundError:
            pass  # File will be created on first sale

        try:
            cash_flow_path = os.path.join(self.base_dir, "flujo_caja.csv")
            with open(cash_flow_path, "r", encoding="utf-8") as f:
                fcntl.flock(f, fcntl.LOCK_SH)
                try:
                    reader = csv.DictReader(f)
                    for row in reader:
                        transaction_date = datetime.fromisoformat(row["fecha_hora"]).date()
                        if start_date <= transaction_date <= end_date:
                            # Filter out sales from cash flow view, show only Entrada/Salida
                            if row["tipo"] not in ["Entrada", "Salida"]:
                                continue

                            transaction_time = datetime.fromisoformat(
                                row["fecha_hora"]
                            ).strftime("%Y-%m-%d %H:%M:%S")
                            # Using Spanish CSV headers: tipo, monto, concepto
                            amount = float(row["monto"])
                            self.cash_flow_tree.insert(
                                "",
                                tk.END,
                                values=(
                                    transaction_time,
                                    row["tipo"],
                                    f"${amount:.2f}",
                                    row["concepto"],
                                ),
                                tags=(row["fecha_hora"],)
                            )
                            if row["tipo"] == "Entrada":
                                entries_total += amount
                            elif row["tipo"] == "Salida":
                                exits_total += amount
                finally:
                    fcntl.flock(f, fcntl.LOCK_UN)
        except FileNotFoundError:
            pass

        self.report_total_label.config(text=f"${daily_total:.2f}")
        self.entradas_total_label.config(text=f"${entries_total:.2f}")
        self.salidas_total_label.config(text=f"${exits_total:.2f}")
        net_total = daily_total + entries_total - exits_total
        self.net_total_label.config(text=f"${net_total:.2f}")

    def print_report(self):
        """Print the current report to thermal printer or export to HTML."""
        # Get current date range
        start_date = self.start_cal.get_date()
        end_date = self.end_cal.get_date()
        
        # Gather data for printer
        sales_data = []
        for item in self.report_tree.get_children():
            values = self.report_tree.item(item)["values"]
            time_str = values[0].split()[1] if len(values[0].split()) > 1 else values[0]
            sales_data.append({
                'time': time_str,
                'name': values[1],
                'qty': values[2],
                'total': values[3]
            })

        cash_flow_data = []
        for item in self.cash_flow_tree.get_children():
            values = self.cash_flow_tree.item(item)["values"]
            time_str = values[0].split()[1] if len(values[0].split()) > 1 else values[0]
            cash_flow_data.append({
                'time': time_str,
                'type': values[1],
                'amount': values[2],
                'concept': values[3]
            })
            
        totals = {
            'sales': self.report_total_label.cget("text"),
            'entries': self.entradas_total_label.cget("text"),
            'exits': self.salidas_total_label.cget("text"),
            'net': self.net_total_label.cget("text")
        }

        # Try printing to thermal printer first
        if ThermalPrinter:
            try:
                printer = ThermalPrinter()
                printer.print_report(
                    self.settings,
                    start_date.strftime('%Y-%m-%d'),
                    end_date.strftime('%Y-%m-%d'),
                    sales_data,
                    cash_flow_data,
                    totals
                )
                return  # Success
            except Exception as e:
                print(f"Thermal printer error: {e}")
                messagebox.showwarning("Thermal Printer", f"Error printing to thermal printer: {e}\nGenerating HTML...")

        try:
            # Generate HTML report
            html_content = self.generate_html_report(start_date, end_date)

            # Save to temp file and open in browser
            ticket_file = tempfile.NamedTemporaryFile(
                delete=False, suffix=".html", mode="w", encoding="utf-8"
            )
            ticket_file.write(html_content)
            ticket_file.close()
            webbrowser.open(f"file://{os.path.realpath(ticket_file.name)}")

            messagebox.showinfo(
                "Reporte Generado",
                "El reporte se generó temporalmente y se abrirá en su navegador.",
            )
        except Exception as e:
            messagebox.showerror(
                "Error", f"No se pudo generar el reporte.\n\nError: {e}"
            )

    def generate_html_report(self, start_date, end_date):
        """Generate HTML content for the report."""
        # Get totals from labels
        total_ventas = self.report_total_label.cget("text")
        total_entradas = self.entradas_total_label.cget("text")
        total_salidas = self.salidas_total_label.cget("text")
        total_general = self.net_total_label.cget("text")

        # Build sales rows (thermal printer style)
        sales_rows = ""
        for item in self.report_tree.get_children():
            values = self.report_tree.item(item)["values"]
            time_str = values[0].split()[1] if len(values[0].split()) > 1 else values[0]
            sales_rows += f"""
        <div class=\"item\">
            <div>{values[1]} (x{values[2]})</div>
            <div class=\"item-line\">
                <span>{time_str}</span>
                <span>{values[3]}</span>
            </div>
        </div>
            """

        if not sales_rows:
            sales_rows = (
                '<div class="item" style="text-align: center;">Sin ventas</div>'
            )

        # Build cash flow rows (thermal printer style)
        cash_rows = ""
        for item in self.cash_flow_tree.get_children():
            values = self.cash_flow_tree.item(item)["values"]
            time_str = values[0].split()[1] if len(values[0].split()) > 1 else values[0]
            tipo_symbol = "+" if values[1] == "Entrada" else "-"
            cash_rows += f"""
        <div class=\"item\">
            <div>{tipo_symbol} {values[3]}</div>
            <div class=\"item-line\">
                <span>{time_str}</span>
                <span>{values[2]}</span>
            </div>
        </div>
            """

        if not cash_rows:
            cash_rows = (
                '<div class="item" style="text-align: center;">Sin movimientos</div>'
            )

        # Generate HTML (Thermal Printer Style)
        html = f"""<!DOCTYPE html>
<html lang=\"es">
<head>
    <meta charset="UTF-8">
    <title>Reporte de Ventas - {start_date.strftime("%Y-%m-%d")} to {end_date.strftime("%Y-%m-%d")}</title>
    <style>
        body {{
            font-family: 'Courier New', monospace;
            margin: 0;
            padding: 20px;
            font-size: 12px;
            max-width: 350px;
            margin: auto;
        }}
        .header {{
            text-align: center;
            border-bottom: 2px dashed #000;
            padding-bottom: 10px;
            margin-bottom: 10px;
        }}
        h1 {{
            margin: 5px 0;
            font-size: 16px;
            font-weight: bold;
        }}
        .date-range {{
            font-size: 11px;
            margin: 5px 0;
        }}
        .section {{
            margin: 15px 0;
        }}
        .section-title {{
            font-weight: bold;
            text-align: center;
            margin: 10px 0 5px 0;
            border-bottom: 1px dashed #000;
            padding-bottom: 3px;
        }}
        .item {{
            margin: 5px 0;
            line-height: 1.4;
        }}
        .item-line {{
            display: flex;
            justify-content: space-between;
        }}
        .separator {{
            border-bottom: 1px dashed #000;
            margin: 10px 0;
        }}
        .totals {{
            margin-top: 15px;
            border-top: 2px solid #000;
            padding-top: 10px;
        }}
        .total-row {{
            display: flex;
            justify-content: space-between;
            margin: 5px 0;
            font-weight: bold;
        }}
        .grand-total {{
            border-top: 2px solid #000;
            margin-top: 10px;
            padding-top: 5px;
            font-size: 14px;
        }}
        .footer {{
            text-align: center;
            margin-top: 15px;
            padding-top: 10px;
            border-top: 2px dashed #000;
            font-size: 10px;
        }}
        @media print {{
            body {{
                padding: 0;
            }}
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>REPORTE DE VENTAS</h1>
        <div class="date-range">
            {start_date.strftime("%Y-%m-%d")} - {end_date.strftime("%Y-%m-%d")}
        </div>
        <div class="date-range">
            {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        </div>
    </div>

    <div class="section">
        <div class="section-title">VENTAS</div>
        {sales_rows}
    </div>

    <div class="section">
        <div class="section-title">FLUJO DE CAJA</div>
        {cash_rows}
    </div>

    <div class="totals">
        <div class="total-row">
            <span>Ventas Totales:</span>
            <span>{total_ventas}</span>
        </div>
        <div class="total-row">
            <span>Entradas Totales:</span>
            <span>{total_entradas}</span>
        </div>
        <div class="total-row">
            <span>Salidas Totales:</span>
            <span>{total_salidas}</span>
        </div>
        <div class="separator"></div>
        <div class="total-row grand-total">
            <span>TOTAL NETO:</span>
            <span>{total_general}</span>
        </div>
    </div>

    <div class="footer">
        Gracias por usar Xun-POS
    </div>
</body>
</html>"""

        return html

    def modify_cash_flow(self):
        """Modify selected cash flow entry."""
        selected = self.cash_flow_tree.selection()
        if not selected:
            messagebox.showwarning(
                "Seleccionar Elemento",
                "Por favor, seleccione un movimiento de la lista de Flujo de Caja para modificar."
            )
            return

        item = self.cash_flow_tree.item(selected[0])
        values = item["values"]
        # values: [time, type, amount, concept]
        # Use tags to get original ISO timestamp
        original_iso_time = item["tags"][0] if item["tags"] else None
        
        # Create edit dialog
        edit_window = tk.Toplevel(self)
        edit_window.title("Modificar Movimiento")
        edit_window.geometry("400x350")
        edit_window.transient(self)
        edit_window.grab_set()
        edit_window.configure(bg="#F0F0F0")

        # Center window
        x = self.winfo_x() + (self.winfo_width() // 2) - 200
        y = self.winfo_y() + (self.winfo_height() // 2) - 175
        edit_window.geometry(f"+{x}+{y}")

        ttk.Label(edit_window, text="Modificar Movimiento", font=("Arial", 14, "bold")).pack(pady=10)

        form_frame = ttk.Frame(edit_window, padding=20)
        form_frame.pack(fill=tk.BOTH, expand=True)

        # Type (Editable Combobox)
        ttk.Label(form_frame, text="Tipo:").grid(row=0, column=0, sticky="w", pady=5)
        type_var = tk.StringVar(value=values[1])
        type_combo = ttk.Combobox(form_frame, textvariable=type_var, values=["Entrada", "Salida"], state="readonly")
        type_combo.grid(row=0, column=1, sticky="ew", pady=5)

        # Amount
        ttk.Label(form_frame, text="Monto ($):").grid(row=1, column=0, sticky="w", pady=5)
        amount_str = str(values[2]).replace("$", "").replace(",", "")
        amount_var = tk.DoubleVar(value=float(amount_str))
        amount_entry = ttk.Entry(form_frame, textvariable=amount_var)
        amount_entry.grid(row=1, column=1, sticky="ew", pady=5)

        # Concept
        ttk.Label(form_frame, text="Concepto:").grid(row=2, column=0, sticky="w", pady=5)
        concept_var = tk.StringVar(value=values[3])
        concept_entry = ttk.Entry(form_frame, textvariable=concept_var)
        concept_entry.grid(row=2, column=1, sticky="ew", pady=5)

        form_frame.columnconfigure(1, weight=1)

        def save_changes():
            try:
                new_type = type_var.get()
                new_amount = amount_var.get()
                new_concept = concept_var.get().strip()
                
                if not new_concept:
                    messagebox.showerror("Error", "El concepto no puede estar vacío", parent=edit_window)
                    return

                # Update CSV
                rows = []
                updated = False
                file_path = os.path.join(self.base_dir, "flujo_caja.csv")

                with open(file_path, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    fieldnames = reader.fieldnames
                    for row in reader:
                        # Match by original ISO timestamp if available
                        match = False
                        if original_iso_time:
                            if row["fecha_hora"] == original_iso_time:
                                match = True
                        else:
                            row_display_time = datetime.fromisoformat(row["fecha_hora"]).strftime("%Y-%m-%d %H:%M:%S")
                            if row_display_time == values[0] and row["tipo"] == values[1]:
                                match = True
                        
                        if match and not updated:
                             # Update row
                             row["tipo"] = new_type
                             row["monto"] = str(new_amount)
                             row["concepto"] = new_concept
                             updated = True
                        
                        rows.append(row)

                if updated:
                    with open(file_path, "w", newline="", encoding="utf-8") as f:
                        writer = csv.DictWriter(f, fieldnames=fieldnames)
                        writer.writeheader()
                        writer.writerows(rows)
                    
                    self.load_report_for_date()
                    edit_window.destroy()
                    messagebox.showinfo("Éxito", "Movimiento actualizado correctamente")
                else:
                     messagebox.showerror("Error", "No se encontró el registro original para actualizar", parent=edit_window)

            except ValueError:
                messagebox.showerror("Error", "Monto inválido", parent=edit_window)
            except Exception as e:
                messagebox.showerror("Error", f"Error al guardar: {e}", parent=edit_window)

        # Buttons
        btn_frame = ttk.Frame(edit_window, padding=10)
        btn_frame.pack(fill=tk.X)
        
        ttk.Button(btn_frame, text="Cancelar", command=edit_window.destroy).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="Guardar", command=save_changes, style="Accent.TButton").pack(side=tk.RIGHT, padx=5)

    def delete_cash_flow(self):
        """Delete selected cash flow entry."""
        selected = self.cash_flow_tree.selection()
        if not selected:
            messagebox.showwarning(
                "Seleccionar Elemento",
                "Por favor, seleccione un movimiento de la lista de Flujo de Caja para borrar."
            )
            return

        item = self.cash_flow_tree.item(selected[0])
        values = item["values"]
        original_iso_time = item["tags"][0] if item["tags"] else None

        # Custom Spanish Confirmation Dialog
        confirm_dialog = tk.Toplevel(self)
        confirm_dialog.title("Confirmar Borrado")
        confirm_dialog.geometry("450x250")
        confirm_dialog.resizable(False, False)
        confirm_dialog.transient(self)
        confirm_dialog.grab_set()
        confirm_dialog.configure(bg="#F0F0F0")

        # Center window
        x = self.winfo_x() + (self.winfo_width() // 2) - 225
        y = self.winfo_y() + (self.winfo_height() // 2) - 125
        confirm_dialog.geometry(f"+{x}+{y}")

        ttk.Label(confirm_dialog, text="¿Está seguro de que desea borrar este movimiento?", 
                  font=("Arial", 12, "bold"), wraplength=400, justify="center").pack(pady=20)
        
        details_frame = ttk.Frame(confirm_dialog, padding=10)
        details_frame.pack(fill=tk.X)
        
        details_text = f"Fecha: {values[0]}\nTipo: {values[1]} | Monto: {values[2]}\nConcepto: {values[3]}"
        ttk.Label(details_frame, text=details_text, font=("Arial", 10), justify="center").pack()

        btn_frame = ttk.Frame(confirm_dialog, padding=20)
        btn_frame.pack(side=tk.BOTTOM, fill=tk.X)

        self.confirm_res = False

        def on_yes():
            self.confirm_res = True
            confirm_dialog.destroy()

        def on_no():
            self.confirm_res = False
            confirm_dialog.destroy()

        ttk.Button(btn_frame, text="No", command=on_no).pack(side=tk.RIGHT, padx=10)
        ttk.Button(btn_frame, text="Sí", command=on_yes, style="Accent.TButton").pack(side=tk.RIGHT, padx=10)

        # Binds
        confirm_dialog.bind("<Return>", lambda e: on_yes())
        confirm_dialog.bind("<Escape>", lambda e: on_no())

        self.wait_window(confirm_dialog)

        if self.confirm_res:
            try:
                rows = []
                deleted = False
                file_path = os.path.join(self.base_dir, "flujo_caja.csv")

                with open(file_path, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    fieldnames = reader.fieldnames
                    for row in reader:
                        match = False
                        if original_iso_time:
                            if row["fecha_hora"] == original_iso_time:
                                match = True
                        else:
                            row_display_time = datetime.fromisoformat(row["fecha_hora"]).strftime("%Y-%m-%d %H:%M:%S")
                            if row_display_time == values[0] and row["tipo"] == values[1]:
                                match = True

                        if match and not deleted:
                            deleted = True
                            continue # Skip this row to delete it
                        
                        rows.append(row)

                if deleted:
                    with open(file_path, "w", newline="", encoding="utf-8") as f:
                        writer = csv.DictWriter(f, fieldnames=fieldnames)
                        writer.writeheader()
                        writer.writerows(rows)
                    
                    self.load_report_for_date()
                    messagebox.showinfo("Éxito", "Movimiento borrado correctamente")
                else:
                    messagebox.showerror("Error", "No se encontró el registro para borrar")

            except Exception as e:
                messagebox.showerror("Error", f"Error al borrar: {e}")



    def exit_app(self):
        """Exit the application."""
        self.destroy()


if __name__ == "__main__":
    app = ReportsApp()
    app.mainloop()