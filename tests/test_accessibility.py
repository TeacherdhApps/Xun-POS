import pytest

import customtkinter as ctk
import tkinter as tk
from tkinter import ttk

import store
from pos_gui import POS_GUI


@pytest.fixture
def pos_app(tmp_path):
    instance = store.Store(
        mode="production", db_path=tmp_path / "xun.db", data_dir=tmp_path / "data"
    )
    instance.replace_products(
        [{"codigo": "1", "nombre": "Pan", "precio": "10.00", "inventario": "5"}]
    )
    app = POS_GUI(user_role="admin")
    yield app, instance
    app.destroy()
    instance.close()


def test_widgets_exist_and_are_focusable(pos_app):
    """Los widgets principales existen y son focuables para navegación por teclado."""
    app, _ = pos_app

    widgets = [
        app.product_combobox,
        app.tree,
    ]
    # Añadir todos los botones CTk
    for widget in app.winfo_children():
        for child in widget.winfo_children():
            if isinstance(child, ctk.CTkButton):
                widgets.append(child)

    for widget in widgets:
        assert isinstance(
            widget, (ctk.CTkComboBox, ctk.CTkButton, ttk.Treeview)
        ), f"Widget {widget} no es un widget de interfaz válido"
        # Verificar que el widget existe y tiene método focus
        assert hasattr(widget, "focus_set")


def test_product_combobox_exists(pos_app):
    """El combobox de producto existe y es un CTkComboBox."""
    app, _ = pos_app
    assert isinstance(app.product_combobox, ctk.CTkComboBox)


def test_tree_exists(pos_app):
    """El treeview de productos existe y es un ttk.Treeview."""
    app, _ = pos_app
    assert isinstance(app.tree, ttk.Treeview)


def test_cash_closure_button_exists(pos_app):
    """El botón 'Cierre de Caja' existe en el botón derecho."""
    app, _ = pos_app
    found = False
    for child in app.right_frame.winfo_children():
        if isinstance(child, ctk.CTkButton) and child.cget("text") == "Cierre de Caja":
            found = True
    assert found, "No se encontró el botón 'Cierre de Caja'"