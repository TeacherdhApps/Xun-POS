import base64
import json
import sqlite3
import stat

import pytest

import security
from scripts.migrate_csv import MigrationError, migrate, money_to_cents


@pytest.fixture
def source(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "productos.csv").write_text(
        "codigo,nombre,precio,inventario\n"
        "1234,PRODUCTO 1,10.00,77\n"
        "5678,PRODUCTO 2,25.50,93\n",
        encoding="utf-8",
    )
    (src / "ventas.csv").write_text(
        "fecha_hora,codigo,nombre,cantidad,precio_unitario,total\n"
        "2026-01-18T18:03:22.208087,1234,PRODUCTO 1,2,10.00,20.00\n"
        "2026-01-18T18:03:43.493298,5678,PRODUCTO 2,1,25.50,25.50\n"
        "2026-01-18T18:04:00.000000,5678,PRODUCTO 2,2.5,10.00,25.00\n",
        encoding="utf-8",
    )
    (src / "flujo_caja.csv").write_text(
        "fecha_hora,tipo,monto,concepto\n"
        "2026-01-18T18:01:54.715813,Entrada,600.00,caja\n"
        "2026-01-18T18:02:06.784156,Salida,200.00,bimbo\n"
        "2026-01-18T18:05:00.000000,Venta,100.00,mostrador\n",
        encoding="utf-8",
    )
    legacy = base64.b64encode(b"clave123").decode()
    pbkdf2 = security.hash_password("otra456", iterations=100_000)
    (src / ".credentials").write_text(
        f"admin:{pbkdf2}:admin\ncajero:{legacy}:cashier\n",
        encoding="utf-8",
    )
    (src / "settings.json").write_text(
        json.dumps({"business_name": "Mi Tienda"}), encoding="utf-8"
    )
    return src


def test_money_to_cents():
    assert money_to_cents("10") == 1000
    assert money_to_cents("10.005") == 1001
    assert money_to_cents("0.01") == 1
    with pytest.raises(ValueError):
        money_to_cents("")


def test_migrate_all_tables(source, tmp_path):
    db = tmp_path / "xun.db"
    summary = migrate(source, db, backup=False)
    assert summary["users"] == 2
    assert summary["products"] == 2
    assert summary["sales"] == 3
    assert summary["cash_movements"] == 3
    assert summary["sales_cents"] == 7050
    assert summary["cash_cents"] == 90000

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row

    users = {
        row["username"]: row["password_hash"]
        for row in conn.execute("SELECT username, password_hash FROM users")
    }
    assert users["admin"].startswith("pbkdf2_sha256$100000$")
    assert users["cajero"].startswith("pbkdf2_sha256$600000$")
    assert security.verify_password(users["cajero"], "clave123")

    products = {
        row["codigo"]: (row["precio_centavos"], row["inventario"])
        for row in conn.execute(
            "SELECT codigo, precio_centavos, inventario FROM products"
        )
    }
    assert products == {"1234": (1000, 77), "5678": (2550, 93)}

    sales = conn.execute(
        "SELECT total_centavos FROM sales ORDER BY id"
    ).fetchall()
    assert [row[0] for row in sales] == [2000, 2550, 2500]
    assert conn.execute("SELECT COUNT(*) FROM sale_items").fetchone()[0] == 3
    quantities = conn.execute(
        "SELECT cantidad FROM sale_items ORDER BY id"
    ).fetchall()
    assert [row[0] for row in quantities] == [2.0, 1.0, 2.5]
    assert conn.execute(
        "SELECT origen FROM sales LIMIT 1"
    ).fetchone()[0] == "legacy"

    cash = conn.execute(
        "SELECT tipo, monto_centavos FROM cash_movements ORDER BY id"
    ).fetchall()
    assert [tuple(row) for row in cash] == [
        ("entrada", 60000),
        ("salida", 20000),
        ("venta", 10000),
    ]

    setting = conn.execute(
        "SELECT valor FROM settings WHERE clave = 'business_name'"
    ).fetchone()[0]
    assert json.loads(setting) == "Mi Tienda"

    marker = conn.execute(
        "SELECT valor FROM settings WHERE clave = 'migracion_csv'"
    ).fetchone()[0]
    data = json.loads(marker)
    assert data["conteos"]["ventas"] == 3
    assert data["totales_centavos"]["caja"] == 90000
    conn.close()


def test_migrate_refuses_second_run(source, tmp_path):
    db = tmp_path / "xun.db"
    migrate(source, db, backup=False)
    with pytest.raises(MigrationError):
        migrate(source, db, backup=False)


def test_dry_run_does_not_create_db(source, tmp_path):
    db = tmp_path / "xun.db"
    summary = migrate(source, db, dry_run=True, backup=False)
    assert summary["sales"] == 3
    assert not db.exists()


def test_backup_is_private(source, tmp_path):
    db = tmp_path / "xun.db"
    summary = migrate(source, db, backup=True)
    backup = summary["backup"]
    assert backup is not None
    products = tmp_path / "src" / "backups"
    assert products.is_dir()
    copied = next(products.iterdir()) / "productos.csv"
    assert copied.exists()
    assert stat.S_IMODE(copied.stat().st_mode) == 0o600
