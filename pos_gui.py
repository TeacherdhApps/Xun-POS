#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Punto de Venta - Xun-POS
Sistema de punto de venta para sistemas Unix
"""

import base64
import config
import csv
import datetime as dt_module
import os
import platform
import sqlite3
import subprocess
import sys
import tempfile
import tkinter as tk
import webbrowser
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

import customtkinter as ctk
from tkinter import messagebox, ttk

import database
import security
import store

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

# Palette
ACCENT_COLOR = "#007BFF"
SUCCESS_COLOR = "#28A745"
DANGER_COLOR = "#DC3545"
WHITE = "#FFFFFF"
BLACK = "#1A1A1A"
BG_COLOR = "#F0F0F0"
TEXT_COLOR = "#212529"

# Money helpers
def money_to_cents(value):
    if value is None or str(value).strip() == "":
        raise ValueError("importe vacío")
    try:
        amount = Decimal(str(value).strip())
    except InvalidOperation as exc:
        raise ValueError(f"importe inválido: {value!r}") from exc
    if not amount.is_finite():
        raise ValueError(f"importe inválido: {value!r}")
    return int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def line_total_cents(price, quantity):
    unit_cents = money_to_cents(price)
    try:
        amount = Decimal(str(quantity))
    except InvalidOperation as exc:
        raise ValueError(f"cantidad inválida: {quantity!r}") from exc
    if not amount.is_finite() or amount <= 0:
        raise ValueError(f"cantidad inválida: {quantity!r}")
    return int((Decimal(unit_cents) * amount).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def normalize_code(value):
    return str(value or "").strip().lstrip("0") or "0"


def format_price(cents):
    return f"{int(cents) / 100:.2f}"


def format_quantity(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "0"
    if number.is_integer():
        return str(int(number))
    return f"{number:g}"


def parse_quantity(value):
    text = str(value if value is not None else "0").strip() or "0"
    try:
        number = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(f"cantidad inválida: {value!r}") from exc
    if not number.is_finite():
        raise ValueError(f"cantidad inválida: {value!r}")
    return float(number)


def _date_key(value):
    if hasattr(value, "isoformat"):
        return value.isoformat()[:10]
    return str(value)[:10]


class PaymentWindow(ctk.CTkToplevel):
    def __init__(self, parent, total):
        super().__init__(parent)
        self.parent = parent
        self.total = total
        self.amount_paid = 0.0
        self.change_value = 0.0

        self.title("Finalizar Venta")
        self.geometry("550x500")
        self.transient(parent)
        self.grab_set()
        self.configure(bg="#f0f0f0")

        self.amount_entry = ctk.CTkEntry(self, font=("Arial", 18))
        self.amount_entry.pack(pady=10, padx=20, fill=tk.X)
        self.amount_entry.insert(0, f"{total:.2f}")

        ctk.CTkLabel(self, text="Concepto:", font=("Arial", 14, "bold")).pack(pady=10)
        self.concept_entry = ctk.CTkEntry(self, font=("Arial", 18))
        self.concept_entry.pack(pady=5, padx=20, fill=tk.X)

        self.bind("<Return>", lambda e: self.save())
        self.bind("<KP_Enter>", lambda e: self.save())
        self.bind("<Escape>", lambda e: self.destroy())

        ctk.CTkButton(
            self,
            text="Ent - Guardar",
            command=self.save,
            fg_color=SUCCESS_COLOR,
            hover_color="#1E7E34",
            font=("Arial", 14, "bold"),
        ).pack(pady=20)

    def save(self):
        amount_str = self.amount_entry.get().strip()
        concept = self.concept_entry.get().strip()

        if not amount_str or not concept:
            messagebox.showwarning("Error", "Todos los campos son obligatorios.", parent=self)
            return

        try:
            amount = float(amount_str)
        except ValueError:
            messagebox.showerror("Error", "Monto inválido.", parent=self)
            return

        if "Entrada" in self.title():
            t_type = "Entrada"
        else:
            t_type = "Salida"

        try:
            self.parent.log_cash_flow(t_type, amount, concept)
        except Exception as exc:
            messagebox.showerror("Error", f"No se pudo registrar: {exc}", parent=self)
            return

        self.destroy()
        messagebox.showinfo("Éxito", "Transacción registrada.")


class GeneralProductWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Producto General")
        self.geometry("500x520")
        self.resizable(False, False)
        self.configure(bg="#f0f0f0")
        self.transient(parent)
        self.grab_set()
        self.create_widgets()

    def create_widgets(self):
        main_frame = ctk.CTkFrame(self, padding="30")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ctk.CTkLabel(main_frame, text="Nombre del Producto:", font=("Arial", 18, "bold")).pack(pady=(0, 5), anchor=tk.W)
        self.name_entry = ctk.CTkEntry(main_frame, font=("Arial", 18))
        self.name_entry.pack(pady=5, padx=20, fill=tk.X)

        ctk.CTkLabel(main_frame, text="Precio Unitario ($):", font=("Arial", 18, "bold")).pack(pady=(10, 5), anchor=tk.W)
        self.price_entry = ctk.CTkEntry(main_frame, font=("Arial", 18))
        self.price_entry.pack(pady=5, padx=20, fill=tk.X)

        ctk.CTkLabel(main_frame, text="Cantidad:", font=("Arial", 18, "bold")).pack(pady=(10, 5), anchor=tk.W)
        self.qty_entry = ctk.CTkEntry(main_frame, font=("Arial", 18))
        self.qty_entry.pack(pady=5, padx=20, fill=tk.X)
        self.qty_entry.insert(0, "1")

        ctk.CTkButton(main_frame, text="Agregar a Venta", command=self.add_to_sale, fg_color=ACCENT_COLOR, hover_color="#0056b3", font=("Arial", 14, "bold")).pack(pady=20)

    def add_to_sale(self):
        name = self.name_entry.get().strip()
        price_str = self.price_entry.get().strip()
        qty_str = self.qty_entry.get().strip()

        if not name or not price_str:
            messagebox.showerror("Error", "Nombre y precio son requeridos.")
            return

        try:
            price = float(price_str)
            qty = float(qty_str) if qty_str else 1
        except ValueError:
            messagebox.showerror("Error", "Precio y cantidad deben ser números.")
            return

        barcode = "GEN-" + name.replace(" ", "-").upper()[:20]
        items = {barcode: {"nombre": name, "precio": price, "qty": qty, "descuento": 0}}
        self.parent.store.record_sale(items, concepto=f"Venta General: {name}")
        self.parent.update_sale_list()
        self.parent.update_total()
        self.destroy()


class EntryExitWindow(ctk.CTkToplevel):
    def __init__(self, parent, title, t_type):
        super().__init__(parent)
        self.parent = parent
        self.title(title)
        self.geometry("400x300")
        self.transient(parent)
        self.grab_set()
        self.configure(bg="#f0f0f0")
        self.t_type = t_type
        self.create_widgets()

    def create_widgets(self):
        ctk.CTkLabel(self, text=self.title(), font=("Arial", 18, "bold")).pack(pady=20)

        form_frame = ctk.CTkFrame(self, padding=20)
        form_frame.pack(fill=tk.BOTH, expand=True)

        ctk.CTkLabel(form_frame, text="Tipo:").grid(row=0, column=0, sticky="w", pady=5)
        type_var = tk.StringVar(value=self.t_type)
        type_combo = ctk.CTkComboBox(form_frame, textvariable=type_var, values=["Entrada", "Salida"], state="readonly")
        type_combo.grid(row=0, column=1, sticky="ew", pady=5)

        ctk.CTkLabel(form_frame, text="Monto ($):").grid(row=1, column=0, sticky="w", pady=5)
        self.amount_entry = ctk.CTkEntry(form_frame, font=("Arial", 14))
        self.amount_entry.grid(row=1, column=1, sticky="ew", pady=5)

        ctk.CTkLabel(form_frame, text="Concepto:").grid(row=2, column=0, sticky="w", pady=5)
        self.concept_entry = ctk.CTkEntry(form_frame, font=("Arial", 14))
        self.concept_entry.grid(row=2, column=1, sticky="ew", pady=5)

        form_frame.columnconfigure(1, weight=1)

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill=tk.X, pady=10)

        ctk.CTkButton(btn_frame, text="Cancelar", command=self.destroy).pack(side=tk.RIGHT, padx=5)
        ctk.CTkButton(btn_frame, text="Guardar", command=self.save, fg_color=ACCENT_COLOR, hover_color="#0056b3").pack(side=tk.RIGHT, padx=5)

    def save(self):
        amount_str = self.amount_entry.get().strip()
        concept = self.concept_entry.get().strip()

        if not amount_str or not concept:
            messagebox.showwarning("Error", "Todos los campos son obligatorios.", parent=self)
            return

        try:
            amount = float(amount_str)
        except ValueError:
            messagebox.showerror("Error", "Monto inválido.", parent=self)
            return

        t_type = self.t_type

        try:
            self.parent.log_cash_flow(t_type, amount, concept)
        except Exception as exc:
            messagebox.showerror("Error", f"No se pudo registrar: {exc}", parent=self)
            return

        self.destroy()
        messagebox.showinfo("Éxito", "Transacción registrada.")


class CashClosureWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Cierre de Caja")
        self.geometry("480x420")
        self.resizable(False, False)
        self.configure(bg="#f0f0f0")
        self.transient(parent)
        self.grab_set()
        self._build_ui()
        self._load_totals()

    def _build_ui(self):
        frame = ctk.CTkFrame(self, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        ctk.CTkLabel(frame, text="Cierre de Caja", font=("Arial", 16, "bold")).pack(pady=10)
        self.sales_label = ctk.CTkLabel(frame, text="Ventas: $0.00", font=("Arial", 12))
        self.sales_label.pack()
        self.entries_label = ctk.CTkLabel(frame, text="Entradas: $0.00", font=("Arial", 12))
        self.entries_label.pack()
        self.exits_label = ctk.CTkLabel(frame, text="Salidas: $0.00", font=("Arial", 12))
        self.exits_label.pack()
        self.net_label = ctk.CTkLabel(frame, text="Neto esperado: $0.00", font=("Arial", 12, "bold"))
        self.net_label.pack()

        ctk.CTkLabel(frame, text="Efectivo actual ($):", font=("Arial", 12)).pack(pady=10)
        self.amount_var = tk.DoubleVar(value=0.0)
        amount_entry = ctk.CTkEntry(frame, textvariable=self.amount_var, font=("Arial", 12))
        amount_entry.pack()

        ctk.CTkButton(frame, text="Cerrar Caja", command=self._close, fg_color=ACCENT_COLOR, hover_color="#0056b3", font=("Arial", 14, "bold")).pack(pady=20)

    def _load_totals(self):
        today = dt_module.date.today()
        sales = self.parent.store.sales_between(today, today)
        total_sales = sum(int(s["total_centavos"]) for s in sales) / 100
        cash = self.parent.store.cash_movements_between(today, today)
        entries = sum(int(m["monto_centavos"]) for m in cash if m["tipo"] == "entrada") / 100
        exits = sum(int(m["monto_centavos"]) for m in cash if m["tipo"] == "salida") / 100
        net = entries - exits - total_sales

        self.sales_total = total_sales
        self.entries_total = entries
        self.exits_total = exits
        self.net_total = net

        self.sales_label.configure(text=f"Ventas: ${total_sales:.2f}")
        self.entries_label.configure(text=f"Entradas: ${entries:.2f}")
        self.exits_label.configure(text=f"Salidas: ${exits:.2f}")
        self.net_label.configure(text=f"Neto esperado: ${net:.2f}")

    def _close(self):
        actual = float(self.amount_var.get() or 0)
        difference = actual - self.net_total
        messagebox.showinfo(
            "Cierre de Caja",
            "Cierre registrado.\n"
            f"Ventas: ${self.sales_total:.2f}\n"
            f"Entradas: ${self.entries_total:.2f}\n"
            f"Salidas: ${self.exits_total:.2f}\n"
            f"Neto esperado: ${self.net_total:.2f}\n"
            f"Efectivo actual: ${actual:.2f}\n"
            f"Diferencia: ${difference:.2f}",
        )
        self.destroy()


class POS_GUI(ctk.CTk):
    def __init__(self, user_role="admin"):
        super().__init__()
        self.title("Punto de Venta")
        self.geometry("1400x720")
        self.resizable(True, True)
        self.user_role = user_role
        self.is_fullscreen = False

        self.app_dir = str(config.app_dir())

        self.store = store.Store()
        self.settings = self.load_settings()
        self.products = self.load_products()
        self.active_tickets = {1: {}, 2: {}}
        self.current_ticket_id = 1
        self.sale_items = self.active_tickets[1]
        self.last_added_barcode = None
        self.search_timer = None

        self.create_widgets()
        self.update_time()
        self.after(100, lambda: self.product_combobox.focus_set())

        self.bind("<F11>", self.toggle_fullscreen)

    def load_settings(self):
        default_settings = {
            "business_name": "Mi Tienda",
            "address": "Calle Principal 123",
            "phone": "555-0199",
            "cashier_name": "Cajero",
            "logo_path": "",
        }
        default_settings.update(self.store.get_settings())
        return default_settings

    def load_products(self):
        return self.store.list_products()

    def toggle_fullscreen(self, event=None):
        self.is_fullscreen = not self.is_fullscreen
        self.attributes("-fullscreen", self.is_fullscreen)
        return "break"

    def create_widgets(self):
        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.pack(fill=tk.BOTH, expand=True)

        self._create_top_frame(main_frame)

        tree_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        tree_scroll = ttk.Scrollbar(tree_frame)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree = ttk.Treeview(
            tree_frame,
            columns=("barcode", "name", "minus", "qty", "plus", "price", "descto", "total"),
            show="headings",
            height=8,
        )

        self.tree.heading("barcode", text="Código")
        self.tree.heading("name", text="Producto")
        self.tree.heading("minus", text=" − ")
        self.tree.heading("qty", text="Cant.")
        self.tree.heading("plus", text=" + ")
        self.tree.heading("price", text="Precio Unitario")
        self.tree.heading("descto", text="Desc %")
        self.tree.heading("total", text="Total")

        self.tree.column("barcode", anchor=tk.W, width=90, minwidth=70)
        self.tree.column("name", anchor=tk.W, width=250, minwidth=180)
        self.tree.column("minus", anchor=tk.CENTER, width=45, minwidth=40, stretch=False)
        self.tree.column("qty", anchor=tk.CENTER, width=60, minwidth=50, stretch=False)
        self.tree.column("plus", anchor=tk.CENTER, width=45, minwidth=40, stretch=False)
        self.tree.column("price", anchor=tk.E, width=95, minwidth=80)
        self.tree.column("descto", anchor=tk.E, width=70, minwidth=60)
        self.tree.column("total", anchor=tk.E, width=110, minwidth=90)

        self.tree.pack(fill=tk.BOTH, expand=True)
        tree_scroll.config(command=self.tree.yview)

        self.tree.bind("<Delete>", lambda e: self.delete_item())
        self.tree.bind("<Up>", lambda e: self.navigate_tree("up"))
        self.tree.bind("<Down>", lambda e: self.navigate_tree("down"))
        self.tree.bind("<Button-1>", lambda e: self.on_tree_click(e))

        bottom_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        bottom_frame.pack(fill=tk.X, pady=5)

        self.button_frame = ctk.CTkFrame(bottom_frame, fg_color="transparent")
        self.button_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

        ctk.CTkButton(
            self.button_frame,
            text="Entradas",
            command=self.open_entry_window,
            fg_color=SUCCESS_COLOR,
            hover_color="#1E7E34",
            font=("Arial", 14, "bold"),
        ).pack(side=tk.LEFT, padx=5)

        ctk.CTkButton(
            self.button_frame,
            text="Salidas",
            command=self.open_exit_window,
            fg_color=DANGER_COLOR,
            hover_color="#BD2130",
            font=("Arial", 14, "bold"),
        ).pack(side=tk.LEFT, padx=(0, 10))

        self.status_label = ctk.CTkLabel(self.button_frame, text="", font=("Arial", 12))
        self.status_label.pack(side=tk.LEFT, padx=(10, 0))

        self.total_label = ctk.CTkLabel(bottom_frame, text="Total: $0.00", font=("Arial", 20, "bold"))
        self.total_label.pack(side=tk.RIGHT, padx=20)

        self.right_frame = ctk.CTkFrame(bottom_frame, fg_color="transparent")
        self.right_frame.pack(side=tk.RIGHT, padx=20)

        ctk.CTkButton(
            self.right_frame,
            text="Cierre de Caja",
            command=self.open_cash_closure,
            fg_color=ACCENT_COLOR,
            hover_color="#0056b3",
            font=("Arial", 14, "bold"),
        ).pack(side=tk.LEFT, padx=5)

        self.setup_accessibility()

    def setup_accessibility(self):
        """Configurar accesibilidad: orden de tabulación y indicador de foco."""
        # Orden de tabulación explícito: producto -> acciones -> caja -> salir
        widget_order = [
            self.product_combobox,
            self.tree,
        ]
        # Botones de entrada/salida
        for child in self.button_frame.winfo_children():
            if isinstance(child, ctk.CTkButton):
                widget_order.append(child)
        # Botón cierre de caja
        for child in self.right_frame.winfo_children():
            if isinstance(child, ctk.CTkButton):
                widget_order.append(child)

        for widget in widget_order:
            widget.focus_set()  # asegurar que existe en el árbol de tabulación

        # Establecer el foco inicial en el combobox de producto
        self.product_combobox.focus_set()

    def _on_focus_in(self, widget):
        """Resaltar el widget con foco."""
        try:
            widget.configure(border_color=ACCENT_COLOR, border_width=2)
        except Exception:
            pass

    def _on_focus_out(self, widget):
        """Quitar el resaltado de foco."""
        try:
            widget.configure(border_color="", border_width=0)
        except Exception:
            pass

    def _create_top_frame(self, parent):
        top_frame = ctk.CTkFrame(parent, fg_color="transparent")
        top_frame.pack(fill=tk.X, pady=5)

        ctk.CTkLabel(top_frame, text="PRODUCTO (Código o Nombre):", font=("Arial", 20, "bold")).pack(side=tk.LEFT, padx=(0, 10))

        self.product_combobox = ctk.CTkComboBox(parent, values=[], font=("Arial", 18), width=300)
        self.product_combobox.pack(side=tk.LEFT, padx=(0, 10))

        # Fecha y hora
        self.date_label = ctk.CTkLabel(top_frame, text="", font=("Arial", 14))
        self.date_label.pack(side=tk.LEFT, padx=(20, 5))
        self.time_label = ctk.CTkLabel(top_frame, text="", font=("Arial", 14, "bold"))
        self.time_label.pack(side=tk.LEFT, padx=(5, 20))
        self.product_combobox.bind("<Return>", self.add_product)
        self.product_combobox.bind("<KP_Enter>", self.add_product)
        self.product_combobox.bind("<KeyRelease>", self.show_suggestions)
        self.product_combobox.bind("<<ComboboxSelected>>", self.add_product)

    def update_time(self):
        now = datetime.now()
        dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
        meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
        day_name = dias[now.weekday()]
        month_name = meses[now.month - 1]
        date_str = f"{day_name}, {now.day} de {month_name} de {now.year}"
        time_str = now.strftime("%I:%M %p")

        self.date_label.configure(text=date_str)
        self.time_label.configure(text=time_str)
        self.after(1000, self.update_time)

    def load_settings(self):
        default_settings = {
            "business_name": "Mi Tienda",
            "address": "Calle Principal 123",
            "phone": "555-0199",
            "cashier_name": "Cajero",
            "logo_path": "",
        }
        default_settings.update(self.store.get_settings())
        return default_settings

    def load_products(self):
        return self.store.list_products()

    def record_sale(self, items, concepto=None, fecha_hora=None, origen="pos"):
        prepared = []
        total_cents = 0
        for codigo, item in items.items():
            quantity = Decimal(str(item["qty"]))
            if not quantity.is_finite() or quantity <= 0:
                raise ValueError(f"cantidad inválida: {item['qty']!r}")
            unit_cents = money_to_cents(item["precio"])
            line_total = line_total_cents(item["precio"], item["qty"])
            prepared.append((normalize_code(codigo), str(item["nombre"]), float(quantity), unit_cents, line_total))
            total_cents += line_total

        if not prepared:
            return None

        timestamp = fecha_hora or datetime.now().isoformat(timespec="microseconds")
        conn = self.store.conn
        with database.transaction(conn):
            cursor = conn.execute("INSERT INTO sales (fecha_hora, total_centavos, origen) VALUES (?, ?, ?)", (timestamp, total_cents, origen))
            sale_id = cursor.lastrowid
            for code, name, quantity, unit_cents, line_total in prepared:
                product = conn.execute("SELECT id FROM products WHERE codigo = ? AND activo = 1", (code,)).fetchone()
                product_id = product["id"] if product else None
                conn.execute(
                    "INSERT INTO sale_items (venta_id, producto_id, codigo, nombre, cantidad, precio_unitario_centavos, total_centavos) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (sale_id, product_id, code, name, quantity, unit_cents, line_total),
                )
                if product_id is not None:
                    conn.execute("UPDATE products SET inventario = inventario - ? WHERE id = ?", (quantity, product_id))
            conn.execute("INSERT INTO cash_movements (fecha_hora, tipo, monto_centavos, concepto) VALUES (?, 'venta', ?, ?)", (timestamp, total_cents, concepto or f"Venta #{sale_id}"))
        return sale_id

    def add_cash_movement(self, tipo, amount, concepto, fecha_hora=None):
        kind = str(tipo or "").strip().lower()
        if kind not in ("entrada", "salida", "venta"):
            raise ValueError(f"tipo de movimiento inválido: {tipo!r}")
        cents = abs(money_to_cents(amount))
        if cents == 0:
            raise ValueError("el monto debe ser distinto de cero")
        timestamp = fecha_hora or datetime.now().isoformat(timespec="microseconds")
        conn = self.store.conn
        with database.transaction(conn):
            cursor = conn.execute("INSERT INTO cash_movements (fecha_hora, tipo, monto_centavos, concepto) VALUES (?, ?, ?, ?)", (timestamp, kind, cents, str(concepto or "").strip()))
        return cursor.lastrowid

    def log_cash_flow(self, transaction_type, amount, concept):
        kind = transaction_type.strip().lower()
        if kind not in ("entrada", "salida"):
            raise ValueError(f"tipo de movimiento inválido: {transaction_type}")
        return self.store.add_cash_movement(kind, amount, concept)

    def update_cash_movement(self, movement_id, tipo, amount, concepto):
        kind = str(tipo or "").strip().lower()
        if kind not in ("entrada", "salida", "venta"):
            raise ValueError(f"tipo de movimiento inválido: {tipo!r}")
        cents = abs(money_to_cents(amount))
        if cents == 0:
            raise ValueError("el monto debe ser distinto de cero")
        conn = self.store.conn
        with database.transaction(conn):
            cursor = conn.execute("UPDATE cash_movements SET tipo = ?, monto_centavos = ?, concepto = ? WHERE id = ?", (kind, cents, str(concepto or "").strip(), movement_id))
        if cursor.rowcount == 0:
            raise KeyError(f"movimiento no encontrado: {movement_id}")

    def delete_cash_movement(self, movement_id):
        conn = self.store.conn
        with database.transaction(conn):
            cursor = conn.execute("DELETE FROM cash_movements WHERE id = ?", (movement_id,))
        if cursor.rowcount == 0:
            raise KeyError(f"movimiento no encontrado: {movement_id}")

    def clear_sale(self):
        self.active_tickets[self.current_ticket_id] = {}
        self.sale_items = self.active_tickets[self.current_ticket_id]
        self.update_sale_list()
        self.update_total()
        self.product_combobox.set("")
        self.product_combobox.focus()

    def reset_sale(self):
        self.active_tickets[self.current_ticket_id] = {}
        self.sale_items = self.active_tickets[self.current_ticket_id]
        self.update_sale_list()
        self.update_total()
        self.product_combobox.set("")
        self.product_combobox.focus()

    def open_settings_window(self):
        script_path = os.path.join(self.app_dir, "settings_gui.py")
        if os.path.exists(script_path):
            subprocess.Popen([sys.executable, script_path])

    def open_products_window(self):
        script_path = os.path.join(self.app_dir, "products_gui.py")
        if os.path.exists(script_path):
            subprocess.Popen([sys.executable, script_path])

    def open_reports_window(self):
        script_path = os.path.join(self.app_dir, "reports_gui.py")
        if os.path.exists(script_path):
            subprocess.Popen([sys.executable, script_path])

    def open_entry_window(self):
        """Open entry window for cash inflow."""
        EntryExitWindow(self, "Entrada Efectivo", "entries")

    def open_exit_window(self):
        """Open exit window for cash outflow."""
        EntryExitWindow(self, "Salida Efectivo", "exits")

    def open_cash_closure(self):
        """Open cash closure window."""
        CashClosureWindow(self)

    def log_cash_flow(self, transaction_type, amount, concept):
        kind = transaction_type.strip().lower()
        if kind not in ("entrada", "salida"):
            raise ValueError(f"tipo de movimiento inválido: {transaction_type}")
        return self.store.add_cash_movement(kind, amount, concept)

    def show_suggestions(self, event=None):
        if event and event.keysym in ["Up", "Down", "Left", "Right", "Return", "ISO_Left_Tab", "Tab"]:
            return
        if self.search_timer:
            self.after_cancel(self.search_timer)
        self.search_timer = self.after(3000, self.perform_search)

    def perform_search(self):
        search_term = self.product_combobox.get().strip()
        if not search_term:
            self.product_combobox.configure(values=[])
            return
        search_term = search_term.lower()
        matches = []
        for code, product in self.products.items():
            search_target = f"{product['nombre']} {code}".lower()
            if search_term in search_target:
                matches.append((code, product["nombre"]))
        self.product_combobox.configure(values=matches[:10])
        if matches:
            self.product_combobox.post()

    def add_product(self, event=None):
        if self.search_timer:
            self.after_cancel(self.search_timer)
            self.search_timer = None
        try:
            self.tk.call("ttk::combobox::Unpost", self.product_combobox._w)
        except tk.TclError:
            pass

        search_term = self.product_combobox.get().strip()
        if not search_term:
            return "break"

        qty = 1
        base_term = search_term
        if "(" in base_term and ")" in base_term:
            possible_code = base_term.split("(")[-1].rstrip(")")
            if possible_code in self.products:
                base_term = possible_code

        normalized_term = base_term.lstrip("0") or "0"

        product = self.products.get(normalized_term)
        barcode = normalized_term
        if not product:
            for code, prod in self.products.items():
                if prod["nombre"].lower() == base_term.lower():
                    product = prod
                    barcode = code
                    break

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
                self.status_label.configure(text=f"Múltiples coincidencias ({len(matches)}). Seleccione de la lista.")
                self.after(2000, lambda: self.status_label.configure(text=""))
                try:
                    self.tk.call("ttk::combobox::Post", self.product_combobox._w)
                except tk.TclError:
                    pass
                return "break"

        if product:
            if barcode in self.sale_items:
                self.sale_items[barcode]["qty"] += qty
            else:
                self.sale_items[barcode] = {"nombre": product["nombre"], "precio": product["precio"], "qty": qty, "descuento": 0}
            self.last_added_barcode = barcode
            self.update_sale_list()
            self.update_total()
            for item_id in self.tree.get_children():
                if self.tree.item(item_id, "tags") and self.tree.item(item_id, "tags")[0] == barcode:
                    self.tree.selection_set(item_id)
                    self.tree.see(item_id)
                    break
            self.product_combobox.set("")
            self.product_combobox.focus()
        else:
            self.status_label.configure(text=f"Producto '{base_term}' no encontrado.")
            self.after(2000, lambda: self.status_label.configure(text=""))
            self.product_combobox.focus()
        return "break"

    def update_sale_list(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for barcode, item in self.sale_items.items():
            descuento = item.get("descuento", 0)
            line_total = item["qty"] * item["precio"] * (1 - descuento / 100)
            is_low_stock = self.products.get(barcode, {}).get("inventario", 0) <= 5
            tags = [barcode]
            if is_low_stock:
                tags.append(self.tree_low_stock_tag)
            if descuento:
                tags.append(self.tree_disc_tag)
            self.tree.insert("", tk.END, values=(barcode, item["nombre"], " − ", item["qty"], " + ", f"${item['precio']:.2f}", f"{descuento}%", f"${line_total:.2f}"), tags=tags)

    def update_total(self):
        total = sum(item["qty"] * item["precio"] * (1 - item.get("descuento", 0) / 100) for item in self.sale_items.values())
        self.total_label.configure(text=f"Total: ${total:.2f}")
        return total

    def show_payment_window(self):
        total = self.update_total()
        if total > 0:
            PaymentWindow(self, total)
        else:
            messagebox.showwarning("Venta Vacía", "No hay ítems en la venta.")
            self.product_combobox.focus()

    def on_closing(self):
        for ticket_id, items in self.active_tickets.items():
            if not items:
                continue
            try:
                self.store.record_sale(items, concepto=f"Venta ticket {ticket_id} (cierre)")
            except Exception as exc:
                print(f"No se pudo guardar el ticket {ticket_id}: {exc}", file=sys.stderr)
        self.store.close()
        self.destroy()

    def delete_item(self):
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
        self.product_combobox.focus()

    def navigate_tree(self, direction):
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
            next_item = self.tree.next(selected[0])
            if next_item:
                self.tree.selection_set(next_item)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        role = sys.argv[1]
    else:
        role = "admin"
    app = POS_GUI(user_role=role)
    app.mainloop()
