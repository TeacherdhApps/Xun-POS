#!/usr/bin/env python3
import config
import os
import platform
import store
import sys
import tempfile
import tkinter as tk
import webbrowser
from datetime import date, datetime, timedelta
from tkinter import messagebox
import customtkinter as ctk

import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg


def _sales_by_day(sales) -> dict:
    """Aggregate sales totals per day (YYYY-MM-DD -> centavos)."""
    totals = {}
    for sale in sales:
        fecha = datetime.fromisoformat(sale["fecha_hora"]).date().isoformat()
        totals[fecha] = totals.get(fecha, 0) + int(sale["total_centavos"])
    return totals


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


# Palette
ACCENT_COLOR = "#007BFF"
SUCCESS_COLOR = "#28A745"
DANGER_COLOR = "#DC3545"
WHITE = "#FFFFFF"
BLACK = "#1A1A1A"


class ReportsApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Reportes de Ventas")
        self.geometry("1400x720")
        self.selected_report_date = date.today()
        self.is_fullscreen = False

        self.store = store.Store()
        if config.get_mode() == "demo":
            self.title(self.title() + " [DEMO]")

        self.settings = self.load_settings()
        self._initialized = False
        self.create_widgets()
        self._initialized = True
        self.load_report_for_date()

        # Bind F11 for fullscreen toggle
        self.bind("<F11>", self.toggle_fullscreen)

    def load_settings(self):
        """Load settings from the database with default fallback."""
        default_settings = {
            "business_name": "Mi Negocio",
            "address": "Calle Principal 123",
            "phone": "555-0123",
            "cashier_name": "Cajero",
        }
        default_settings.update(self.store.get_settings())
        return default_settings

    def toggle_fullscreen(self, event=None):
        """Toggle fullscreen mode with F11."""
        self.is_fullscreen = not self.is_fullscreen
        self.attributes("-fullscreen", self.is_fullscreen)
        return "break"

    def create_widgets(self):
        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.pack(fill=tk.BOTH, expand=True)

        top_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        top_frame.pack(fill=tk.X)

        # Header Info Label
        info_label = ctk.CTkLabel(
            top_frame,
            text="@Xun-POS",
            font=("Arial", 8),
            text_color="#666666",
        )
        info_label.pack(side=tk.RIGHT, anchor=tk.NE)

        self.report_date_label = ctk.CTkLabel(
            top_frame,
            text=f"Reporte del: {self.selected_report_date.strftime('%Y-%m-%d')}",
            font=("Arial", 18, "bold"),
        )
        self.report_date_label.pack(pady=10)

        cal_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
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
        cal_frame.columnconfigure(9, weight=1)  # Grafico button

        # Row 0: Calendar widgets and buttons
        ctk.CTkLabel(cal_frame, text="Desde:", font=("Arial", 14, "bold")).grid(
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

        ctk.CTkLabel(cal_frame, text="Hasta:", font=("Arial", 14, "bold")).grid(
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
        ctk.CTkLabel(cal_frame, text="").grid(row=0, column=4, padx=20)

        # Add Print button
        ctk.CTkButton(
            cal_frame,
            text="F2 - Imprimir",
            command=self.print_report,
            fg_color=SUCCESS_COLOR,
            hover_color="#218838",
            font=("Arial", 14, "bold"),
        ).grid(row=0, column=5, padx=5, sticky="ew")

        # Add Grafico button
        ctk.CTkButton(
            cal_frame,
            text="Gráfico - Ventas por día",
            command=self._open_sales_chart,
            fg_color=ACCENT_COLOR,
            hover_color="#0056b3",
            font=("Arial", 14, "bold"),
        ).grid(row=0, column=9, padx=5, sticky="ew")

        ttk.Button(
            cal_frame,
            text="F6 - Modificar",
            command=self.modify_cash_flow,
        ).grid(row=0, column=6, padx=5, sticky="ew")

        ttk.Button(
            cal_frame,
            text="F7 - Borrar",
            command=self.delete_cash_flow,
        ).grid(row=0, column=7, padx=5, sticky="ew")

        ttk.Button(
            cal_frame,
            text="F12 - Salir",
            command=self.exit_app,
        ).grid(row=0, column=8, padx=5, sticky="ew")

        # Bind F2 and F12 keys
        self.bind("<F2>", lambda e: self.print_report())
        self.bind("<F6>", lambda e: self.modify_cash_flow())
        self.bind("<F7>", lambda e: self.delete_cash_flow())
        self.bind("<F12>", lambda e: self.exit_app())

        content_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        content_frame.pack(fill=tk.BOTH, expand=True)

        # Left side for sales
        sales_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
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
        cash_flow_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
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
        summary_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        summary_frame.pack(fill=tk.X)

        # Create 4 equal columns
        summary_frame.columnconfigure(0, weight=1, uniform="totals")
        summary_frame.columnconfigure(1, weight=1, uniform="totals")
        summary_frame.columnconfigure(2, weight=1, uniform="totals")
        summary_frame.columnconfigure(3, weight=1, uniform="totals")

        # Column 1: Total Sales
        ventas_col = ctk.CTkFrame(summary_frame, fg_color="transparent")
        ventas_col.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")
        ctk.CTkLabel(
            ventas_col, text="Ventas Totales", font=("Arial", 11, "bold")
        ).pack()
        self.report_total_label = ctk.CTkLabel(
            ventas_col, text="$0.00", font=("Arial", 20, "bold")
        )
        self.report_total_label.pack()

        # Column 2: Total Entries
        entradas_col = ctk.CTkFrame(summary_frame, fg_color="transparent")
        entradas_col.grid(row=0, column=1, padx=5, pady=5, sticky="nsew")
        ctk.CTkLabel(
            entradas_col, text="Entradas Totales", font=("Arial", 11, "bold")
        ).pack()
        self.entradas_total_label = ctk.CTkLabel(
            entradas_col, text="$0.00", font=("Arial", 20, "bold"), text_color=SUCCESS_COLOR
        )
        self.entradas_total_label.pack()

        # Column 3: Total Exits
        salidas_col = ctk.CTkFrame(summary_frame, fg_color="transparent")
        salidas_col.grid(row=0, column=2, padx=5, pady=5, sticky="nsew")
        ctk.CTkLabel(salidas_col, text="Salidas Totales", font=("Arial", 11, "bold")).pack()
        self.salidas_total_label = ctk.CTkLabel(
            salidas_col, text="$0.00", font=("Arial", 20, "bold"), text_color=DANGER_COLOR
        )
        self.salidas_total_label.pack()

        # Column 4: Net Total
        general_col = ctk.CTkFrame(summary_frame, fg_color="transparent")
        general_col.grid(row=0, column=3, padx=5, pady=5, sticky="nsew")
        ctk.CTkLabel(general_col, text="Total Neto", font=("Arial", 11, "bold")).pack()
        self.net_total_label = ctk.CTkLabel(
            general_col, text="$0.00", font=("Arial", 20, "bold"), text_color=ACCENT_COLOR
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
        self.report_date_label.configure(
            text=f"Reporte Desde: {start_date.strftime('%Y-%m-%d')} Hasta: {end_date.strftime('%Y-%m-%d')}"
        )
        self.load_report_for_date(start_date, end_date)

    def load_report_for_date(self, start_date=None, end_date=None):
        if start_date is None:
            start_date = self.selected_report_date
        if end_date is None:
            end_date = self.selected_report_date

        if start_date == end_date:
            self.report_date_label.configure(
                text=f"Reporte del: {start_date.strftime('%Y-%m-%d')}"
            )
        else:
            self.report_date_label.configure(
                text=f"Reporte Desde: {start_date.strftime('%Y-%m-%d')} Hasta: {end_date.strftime('%Y-%m-%d')}"
            )
        for i in self.report_tree.get_children():
            self.report_tree.delete(i)
        for i in self.cash_flow_tree.get_children():
            self.cash_flow_tree.delete(i)

        daily_total = 0.0
        entries_total = 0.0
        exits_total = 0.0

        for sale in self.store.sales_between(start_date, end_date):
            sale_time = datetime.fromisoformat(sale["fecha_hora"]).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            total_price = sale["total_centavos"] / 100
            self.report_tree.insert(
                "",
                tk.END,
                values=(
                    sale_time,
                    sale["nombre"],
                    store.format_quantity(sale["cantidad"]),
                    f"${total_price:.2f}",
                ),
            )
            daily_total += total_price

        for movement in self.store.cash_movements_between(
            start_date, end_date
        ):
            transaction_time = datetime.fromisoformat(
                movement["fecha_hora"]
            ).strftime("%Y-%m-%d %H:%M:%S")
            amount = movement["monto_centavos"] / 100
            kind = movement["tipo"].capitalize()
            self.cash_flow_tree.insert(
                "",
                tk.END,
                values=(
                    transaction_time,
                    kind,
                    f"${amount:.2f}",
                    movement["concepto"],
                ),
                tags=(str(movement["id"]),),
            )
            if movement["tipo"] == "entrada":
                entries_total += amount
            elif movement["tipo"] == "salida":
                exits_total += amount

        self.report_total_label.configure(text=f"${daily_total:.2f}")
        self.entradas_total_label.configure(text=f"${entries_total:.2f}")
        self.salidas_total_label.configure(text=f"${exits_total:.2f}")
        net_total = daily_total + entries_total - exits_total
        self.net_total_label.configure(text=f"${net_total:.2f}")

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
<html lang=\"es\">
<head>
    <meta charset=\"UTF-8\">
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
        # Use the tag to get the database row id
        movement_id = int(item["tags"][0]) if item["tags"] else None

        # Create edit dialog
        edit_window = ctk.CTkToplevel(self)
        edit_window.title("Modificar Movimiento")
        edit_window.geometry("400x350")
        edit_window.transient(self)
        edit_window.grab_set()

        # Center window
        x = self.winfo_x() + (self.winfo_width() // 2) - 200
        y = self.winfo_y() + (self.winfo_height() // 2) - 175
        edit_window.geometry(f"+{x}+{y}")

        ctk.CTkLabel(edit_window, text="Modificar Movimiento", font=("Arial", 14, "bold")).pack(pady=10)

        form_frame = ctk.CTkFrame(edit_window, fg_color="transparent")
        form_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # Type (Editable Combobox)
        ctk.CTkLabel(form_frame, text="Tipo:").grid(row=0, column=0, sticky="w", pady=5)
        type_var = tk.StringVar(value=values[1])
        type_combo = ctk.CTkComboBox(form_frame, textvariable=type_var, values=["Entrada", "Salida"], state="readonly")
        type_combo.grid(row=0, column=1, sticky="ew", pady=5)

        # Amount
        ctk.CTkLabel(form_frame, text="Monto ($):").grid(row=1, column=0, sticky="w", pady=5)
        amount_str = str(values[2]).replace("$", "").replace(",", "")
        amount_var = tk.DoubleVar(value=float(amount_str))
        amount_entry = ctk.CTkEntry(form_frame, textvariable=amount_var)
        amount_entry.grid(row=1, column=1, sticky="ew", pady=5)

        # Concept
        ctk.CTkLabel(form_frame, text="Concepto:").grid(row=2, column=0, sticky="w", pady=5)
        concept_var = tk.StringVar(value=values[3])
        concept_entry = ctk.CTkEntry(form_frame, textvariable=concept_var)
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
                if movement_id is None:
                    messagebox.showerror(
                        "Error",
                        "No se encontró el registro original para actualizar",
                        parent=edit_window,
                    )
                    return

                self.store.update_cash_movement(
                    movement_id, new_type, new_amount, new_concept
                )
                self.load_report_for_date()
                edit_window.destroy()
                messagebox.showinfo("Éxito", "Movimiento actualizado correctamente")

            except ValueError:
                messagebox.showerror("Error", "Monto inválido", parent=edit_window)
            except Exception as e:
                messagebox.showerror("Error", f"Error al guardar: {e}", parent=edit_window)

        # Buttons
        btn_frame = ctk.CTkFrame(edit_window, fg_color="transparent")
        btn_frame.pack(fill=tk.X, pady=10)

        ctk.CTkButton(btn_frame, text="Cancelar", command=edit_window.destroy).pack(side=tk.RIGHT, padx=5)
        ctk.CTkButton(btn_frame, text="Guardar", command=save_changes, fg_color=ACCENT_COLOR, hover_color="#0056b3").pack(side=tk.RIGHT, padx=5)

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
        movement_id = int(item["tags"][0]) if item["tags"] else None

        # Custom Spanish Confirmation Dialog
        confirm_dialog = ctk.CTkToplevel(self)
        confirm_dialog.title("Confirmar Borrado")
        confirm_dialog.geometry("450x250")
        confirm_dialog.resizable(False, False)
        confirm_dialog.transient(self)
        confirm_dialog.grab_set()

        # Center window
        x = self.winfo_x() + (self.winfo_width() // 2) - 225
        y = self.winfo_y() + (self.winfo_height() // 2) - 125
        confirm_dialog.geometry(f"+{x}+{y}")

        ctk.CTkLabel(confirm_dialog, text="¿Está seguro de que desea borrar este movimiento?",
                     font=("Arial", 12, "bold"), wraplength=400).pack(pady=20)

        details_frame = ctk.CTkFrame(confirm_dialog, fg_color="transparent")
        details_frame.pack(fill=tk.X, pady=10)

        details_text = f"Fecha: {values[0]}\nTipo: {values[1]} | Monto: {values[2]}\nConcepto: {values[3]}"
        ctk.CTkLabel(details_frame, text=details_text, font=("Arial", 10)).pack()

        btn_frame = ctk.CTkFrame(confirm_dialog, fg_color="transparent")
        btn_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=20)

        self.confirm_res = False

        def on_yes():
            self.confirm_res = True
            confirm_dialog.destroy()

        def on_no():
            self.confirm_res = False
            confirm_dialog.destroy()

        ctk.CTkButton(btn_frame, text="No", command=on_no).pack(side=tk.RIGHT, padx=10)
        ctk.CTkButton(btn_frame, text="Sí", command=on_yes, fg_color=ACCENT_COLOR, hover_color="#0056b3").pack(side=tk.RIGHT, padx=10)

        # Binds
        confirm_dialog.bind("<Return>", lambda e: on_yes())
        confirm_dialog.bind("<Escape>", lambda e: on_no())

        self.wait_window(confirm_dialog)

        if self.confirm_res:
            try:
                if movement_id is None:
                    raise ValueError(
                        "No se encontró el registro para borrar"
                    )
                self.store.delete_cash_movement(movement_id)
                self.load_report_for_date()
                messagebox.showinfo("Éxito", "Movimiento borrado correctamente")
            except Exception as e:
                messagebox.showerror("Error", f"Error al borrar: {e}")

    def _open_sales_chart(self):
        """Show sales per day for the selected range in a bar chart."""
        start = self.start_cal.get_date()
        end = self.end_cal.get_date()
        sales = self.store.sales_between(start, end)
        totals = _sales_by_day(sales)

        window = ctk.CTkToplevel(self)
        window.title("Ventas por día")
        window.geometry("640x400")
        window.transient(self)
        window.grab_set()

        fig, ax = plt.subplots(figsize=(6, 4), dpi=100)
        if totals:
            days = sorted(totals)
            values = [totals[d] / 100 for d in days]
            ax.bar(days, values)
            ax.set_title(f"Ventas por día ({start} a {end})")
            ax.set_ylabel("Ventas ($)")
            ax.tick_params(axis="x", rotation=45)
        else:
            ax.text(
                0.5,
                0.5,
                "Sin ventas en el rango",
                ha="center",
                va="center",
                transform=ax.transAxes,
            )
        fig.tight_layout()

        canvas = FigureCanvasTkAgg(fig, master=window)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def exit_app(self):
        """Exit the application."""
        self.store.close()
        self.destroy()


if __name__ == "__main__":
    app = ReportsApp()
    app.mainloop()
