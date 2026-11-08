import json
import zipfile
from datetime import date

import pytest

import store


@pytest.fixture
def data_dir(tmp_path):
    directory = tmp_path / "data"
    directory.mkdir()
    return directory


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "xun.db"


@pytest.fixture
def repo(data_dir, db_path):
    instance = store.Store(
        mode="production", db_path=db_path, data_dir=data_dir
    )
    yield instance
    instance.close()


def test_replace_products_and_soft_delete(repo):
    repo.replace_products(
        [
            {
                "codigo": "0001",
                "nombre": "Pan",
                "precio": "10.00",
                "inventario": "5",
            },
            {
                "codigo": "2",
                "nombre": "Queso",
                "precio": "25.50",
                "inventario": "2.5",
            },
        ]
    )

    products = repo.list_products()
    assert products["1"]["precio"] == 10.0
    assert products["1"]["inventario"] == 5
    assert products["2"]["inventario"] == 2.5

    ui_products = {
        row["codigo"]: row for row in repo.list_products_for_ui()
    }
    assert ui_products["1"]["precio"] == "10.00"
    assert ui_products["2"]["inventario"] == "2.5"

    repo.record_sale(
        {"1": {"nombre": "Pan", "precio": 10.0, "qty": 1}}
    )
    repo.replace_products(
        [
            {
                "codigo": "2",
                "nombre": "Queso",
                "precio": "25.50",
                "inventario": "2.5",
            }
        ]
    )

    assert "1" not in repo.list_products()
    row = repo.conn.execute(
        "SELECT activo FROM products WHERE codigo = '1'"
    ).fetchone()
    assert row["activo"] == 0
    assert (
        repo.conn.execute("SELECT COUNT(*) FROM sale_items").fetchone()[0]
        == 1
    )


def test_replace_products_rejects_duplicates(repo):
    with pytest.raises(ValueError):
        repo.replace_products(
            [
                {"codigo": "1", "nombre": "A", "precio": "1"},
                {"codigo": "01", "nombre": "B", "precio": "2"},
            ]
        )


def test_record_sale_updates_stock_and_cash(repo):
    repo.replace_products(
        [
            {
                "codigo": "1",
                "nombre": "Pan",
                "precio": "10.00",
                "inventario": "10",
            }
        ]
    )

    sale_id = repo.record_sale(
        {"1": {"nombre": "Pan", "precio": 10.0, "qty": 2.5}},
        concepto="Venta 1",
        fecha_hora="2026-01-18T10:00:00",
    )

    sale = repo.conn.execute(
        "SELECT total_centavos, origen FROM sales WHERE id = ?",
        (sale_id,),
    ).fetchone()
    assert sale["total_centavos"] == 2500
    assert sale["origen"] == "pos"

    item = repo.conn.execute(
        "SELECT codigo, cantidad, precio_unitario_centavos, total_centavos"
        " FROM sale_items WHERE venta_id = ?",
        (sale_id,),
    ).fetchone()
    assert tuple(item) == ("1", 2.5, 1000, 2500)

    assert repo.get_product("1")["inventario"] == 7.5

    cash = repo.conn.execute(
        "SELECT tipo, monto_centavos, concepto FROM cash_movements"
    ).fetchone()
    assert tuple(cash) == ("venta", 2500, "Venta 1")


def test_record_sale_with_unknown_product(repo):
    sale_id = repo.record_sale(
        {"GEN-1": {"nombre": "General", "precio": 5.0, "qty": 1}}
    )
    item = repo.conn.execute(
        "SELECT producto_id, codigo FROM sale_items WHERE venta_id = ?",
        (sale_id,),
    ).fetchone()
    assert item["producto_id"] is None
    assert item["codigo"] == "GEN-1"


def test_cash_movement_crud(repo):
    entry = repo.add_cash_movement(
        "Entrada", "100.00", "caja", fecha_hora="2026-01-18T09:00:00"
    )
    exit_id = repo.add_cash_movement(
        "Salida", "20.50", "bimbo", fecha_hora="2026-01-18T10:00:00"
    )
    repo.add_cash_movement(
        "venta", "50.00", "mostrador", fecha_hora="2026-01-18T11:00:00"
    )

    rows = repo.cash_movements_between(
        date(2026, 1, 18), date(2026, 1, 18)
    )
    assert [(row["tipo"], row["monto_centavos"]) for row in rows] == [
        ("entrada", 10000),
        ("salida", 2050),
    ]
    assert repo.cash_movements_between(
        date(2026, 1, 17), date(2026, 1, 18)
    )

    repo.update_cash_movement(exit_id, "Entrada", "25.00", "cambio")
    row = repo.conn.execute(
        "SELECT tipo, monto_centavos, concepto FROM cash_movements"
        " WHERE id = ?",
        (exit_id,),
    ).fetchone()
    assert tuple(row) == ("entrada", 2500, "cambio")

    repo.delete_cash_movement(entry)
    remaining = repo.conn.execute(
        "SELECT COUNT(*) FROM cash_movements"
    ).fetchone()[0]
    assert remaining == 2
    with pytest.raises(KeyError):
        repo.delete_cash_movement(entry)


def test_sales_between_filters_dates(repo):
    repo.replace_products(
        [{"codigo": "1", "nombre": "Pan", "precio": "10.00"}]
    )
    repo.record_sale(
        {"1": {"nombre": "Pan", "precio": 10.0, "qty": 1}},
        fecha_hora="2026-01-17T23:59:00",
    )
    repo.record_sale(
        {"1": {"nombre": "Pan", "precio": 10.0, "qty": 3}},
        fecha_hora="2026-01-18T08:00:00",
    )

    rows = repo.sales_between(date(2026, 1, 18), date(2026, 1, 18))
    assert len(rows) == 1
    assert rows[0]["cantidad"] == 3.0
    assert rows[0]["total_centavos"] == 3000
    assert repo.sales_total_between(
        date(2026, 1, 18), date(2026, 1, 18)
    ) == 3000
    assert repo.sales_total_between(
        date(2026, 1, 17), date(2026, 1, 18)
    ) == 4000


def test_settings_roundtrip(repo):
    repo.set_settings(
        {
            "business_name": "Mi Tienda",
            "phone": "555-0101",
            "print_logo": True,
            "copies": 2,
        }
    )
    assert repo.get_settings() == {
        "business_name": "Mi Tienda",
        "phone": "555-0101",
        "print_logo": True,
        "copies": 2,
    }


def test_auto_migration_runs_once(data_dir, db_path):
    (data_dir / "productos.csv").write_text(
        "codigo,nombre,precio,inventario\n"
        "0001,Pan,10.00,7.5\n",
        encoding="utf-8",
    )
    (data_dir / "ventas.csv").write_text(
        "fecha_hora,codigo,nombre,cantidad,precio_unitario,total\n"
        "2026-01-18T10:00:00,0001,Pan,2.5,10.00,25.00\n",
        encoding="utf-8",
    )
    (data_dir / "flujo_caja.csv").write_text(
        "fecha_hora,tipo,monto,concepto\n"
        "2026-01-18T09:00:00,Entrada,100.00,caja\n",
        encoding="utf-8",
    )
    (data_dir / "settings.json").write_text(
        json.dumps({"business_name": "Demo"}), encoding="utf-8"
    )

    first = store.Store(
        mode="production", db_path=db_path, data_dir=data_dir
    )
    assert first.migration is not None
    assert first.list_products()["1"]["inventario"] == 7.5
    assert first.sales_total_between(
        date(2026, 1, 18), date(2026, 1, 18)
    ) == 2500
    assert first.get_settings()["business_name"] == "Demo"
    assert [row["tipo"] for row in first.cash_movements_between(
        date(2026, 1, 18), date(2026, 1, 18)
    )] == ["entrada"]
    first.close()

    second = store.Store(
        mode="production", db_path=db_path, data_dir=data_dir
    )
    assert second.migration is None
    assert second.conn.execute(
        "SELECT COUNT(*) FROM products"
    ).fetchone()[0] == 1
    assert second.conn.execute(
        "SELECT COUNT(*) FROM sales"
    ).fetchone()[0] == 1
    second.close()


def test_export_and_restore_backup(repo, data_dir, db_path, tmp_path):
    repo.replace_products(
        [{"codigo": "1", "nombre": "Pan", "precio": "10.00"}]
    )
    backup = tmp_path / "backup.zip"
    repo.export_backup(backup)
    assert backup.exists()

    repo.replace_products(
        [{"codigo": "2", "nombre": "Queso", "precio": "20.00"}]
    )
    repo.close()

    result = store.restore_backup(backup, db_path=db_path)
    assert result["previous"] is not None

    restored = store.Store(
        mode="production", db_path=db_path, data_dir=data_dir
    )
    assert list(restored.list_products()) == ["1"]
    restored.close()


def test_restore_into_open_store(repo, tmp_path):
    repo.replace_products(
        [{"codigo": "1", "nombre": "Pan", "precio": "10.00"}]
    )
    backup = tmp_path / "backup.zip"
    repo.export_backup(backup)

    repo.replace_products(
        [{"codigo": "2", "nombre": "Queso", "precio": "20.00"}]
    )

    result = repo.restore_backup(backup)
    assert result["db"] == str(repo.db_path)

    assert list(repo.list_products()) == ["1"]
    assert repo.get_product("2") is None


def test_restore_legacy_csv_zip(data_dir, db_path, tmp_path):
    archive_path = tmp_path / "legacy.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr(
            "productos.csv",
            "codigo,nombre,precio,inventario\n0001,Pan,10.00,3\n",
        )
        archive.writestr(
            "settings.json", json.dumps({"business_name": "Viejo"})
        )

    result = store.restore_backup(archive_path, db_path=db_path)
    assert result["previous"] is None

    restored = store.Store(
        mode="production", db_path=db_path, data_dir=data_dir
    )
    assert restored.get_product("1")["nombre"] == "Pan"
    assert restored.get_settings()["business_name"] == "Viejo"
    restored.close()


def test_cierre_de_caja_cuadra_al_centavo(repo):
    """Cierre de caja: ventas del día + entradas/salidas cuadra al centavo."""
    repo.replace_products(
        [{"codigo": "1", "nombre": "Pan", "precio": "10.00", "inventario": "10"}]
    )

    # Venta de 10.00
    repo.record_sale(
        {"1": {"nombre": "Pan", "precio": 10.0, "qty": 1}},
        fecha_hora="2026-01-18T10:00:00",
    )

    # Entrada de 50.00
    repo.add_cash_movement(
        "Entrada", "50.00", "caja inicial", fecha_hora="2026-01-18T08:00:00"
    )

    # Salida de 5.00
    repo.add_cash_movement(
        "Salida", "5.00", "gastos", fecha_hora="2026-01-18T09:00:00"
    )

    today = date(2026, 1, 18)
    sales = repo.sales_between(today, today)
    cash = repo.cash_movements_between(today, today)

    total_sales = sum(int(s["total_centavos"]) for s in sales)
    entries = sum(int(m["monto_centavos"]) for m in cash if m["tipo"] == "entrada")
    exits = sum(int(m["monto_centavos"]) for m in cash if m["tipo"] == "salida")

    neto = entries - exits - total_sales

    assert total_sales == 1000
    assert entries == 5000
    assert exits == 500
    assert neto == 3500


def test_cierre_de_caja_cuadra_al_centavo(repo):
    """Cierre de caja: ventas del día + entradas/salidas cuadra al centavo."""
    repo.replace_products(
        [{"codigo": "1", "nombre": "Pan", "precio": "10.00", "inventario": "10"}]
    )

    # Venta de 10.00
    repo.record_sale(
        {"1": {"nombre": "Pan", "precio": 10.0, "qty": 1}},
        fecha_hora="2026-01-18T10:00:00",
    )

    # Entrada de 50.00
    repo.add_cash_movement(
        "Entrada", "50.00", "caja inicial", fecha_hora="2026-01-18T08:00:00"
    )

    # Salida de 5.00
    repo.add_cash_movement(
        "Salida", "5.00", "gastos", fecha_hora="2026-01-18T09:00:00"
    )

    today = date(2026, 1, 18)
    sales = repo.sales_between(today, today)
    cash = repo.cash_movements_between(today, today)

    total_sales = sum(int(s["total_centavos"]) for s in sales)
    entries = sum(int(m["monto_centavos"]) for m in cash if m["tipo"] == "entrada")
    exits = sum(int(m["monto_centavos"]) for m in cash if m["tipo"] == "salida")

    neto = entries - exits - total_sales

    assert total_sales == 1000
    assert entries == 5000
    assert exits == 500
    assert neto == 3500
