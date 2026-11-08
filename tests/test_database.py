import sqlite3

import pytest

import database


def make_db(tmp_path):
    conn = database.connect(tmp_path / "test.db")
    database.init_db(conn)
    return conn


def test_init_creates_tables(tmp_path):
    conn = make_db(tmp_path)
    names = {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    assert {
        "users",
        "products",
        "sales",
        "sale_items",
        "cash_movements",
        "settings",
        "audit_log",
    } <= names
    assert database.schema_version(conn) == database.SCHEMA_VERSION
    conn.close()


def test_init_is_idempotent(tmp_path):
    conn = make_db(tmp_path)
    database.init_db(conn)
    assert database.schema_version(conn) == database.SCHEMA_VERSION
    conn.close()


def test_connect_enables_wal_and_foreign_keys(tmp_path):
    conn = make_db(tmp_path)
    assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    conn.close()


def test_negative_price_is_rejected(tmp_path):
    conn = make_db(tmp_path)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO products (codigo, nombre, precio_centavos)"
            " VALUES ('1', 'X', -1)"
        )
    conn.close()


def test_foreign_keys_are_enforced(tmp_path):
    conn = make_db(tmp_path)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO sale_items"
            " (venta_id, codigo, nombre, cantidad,"
            "  precio_unitario_centavos, total_centavos)"
            " VALUES (999, '1', 'X', 1, 100, 100)"
        )
    conn.close()


def test_transaction_rolls_back(tmp_path):
    conn = make_db(tmp_path)
    with pytest.raises(RuntimeError):
        with database.transaction(conn):
            conn.execute("INSERT INTO settings (clave, valor) VALUES ('x', '1')")
            raise RuntimeError("falla")
    count = conn.execute("SELECT COUNT(*) FROM settings").fetchone()[0]
    assert count == 0
    conn.close()


def test_default_db_path_uses_xdg_data_home(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    assert database.default_db_path() == tmp_path / "xun-pos" / "xun.db"


def test_migrates_v1_schema(tmp_path):
    path = tmp_path / "v1.db"
    conn = sqlite3.connect(path, isolation_level=None)
    conn.executescript(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('admin', 'cashier')),
            activo INTEGER NOT NULL DEFAULT 1,
            creado_en TEXT NOT NULL
        );
        CREATE TABLE products (
            id INTEGER PRIMARY KEY,
            codigo TEXT NOT NULL UNIQUE,
            nombre TEXT NOT NULL,
            precio_centavos INTEGER NOT NULL CHECK (precio_centavos >= 0),
            inventario INTEGER NOT NULL DEFAULT 0,
            activo INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE sales (
            id INTEGER PRIMARY KEY,
            fecha_hora TEXT NOT NULL,
            usuario_id INTEGER REFERENCES users(id),
            total_centavos INTEGER NOT NULL CHECK (total_centavos >= 0),
            estado TEXT NOT NULL DEFAULT 'completada',
            origen TEXT NOT NULL DEFAULT 'pos'
        );
        CREATE TABLE sale_items (
            id INTEGER PRIMARY KEY,
            venta_id INTEGER NOT NULL REFERENCES sales(id) ON DELETE CASCADE,
            producto_id INTEGER REFERENCES products(id),
            codigo TEXT NOT NULL,
            nombre TEXT NOT NULL,
            cantidad INTEGER NOT NULL CHECK (cantidad > 0),
            precio_unitario_centavos INTEGER NOT NULL
                CHECK (precio_unitario_centavos >= 0),
            total_centavos INTEGER NOT NULL CHECK (total_centavos >= 0)
        );
        CREATE TABLE cash_movements (
            id INTEGER PRIMARY KEY,
            fecha_hora TEXT NOT NULL,
            tipo TEXT NOT NULL CHECK (tipo IN ('entrada', 'salida')),
            monto_centavos INTEGER NOT NULL CHECK (monto_centavos > 0),
            concepto TEXT NOT NULL,
            usuario_id INTEGER REFERENCES users(id)
        );
        CREATE TABLE settings (clave TEXT PRIMARY KEY, valor TEXT NOT NULL);
        CREATE TABLE audit_log (
            id INTEGER PRIMARY KEY,
            fecha_hora TEXT NOT NULL,
            usuario_id INTEGER,
            accion TEXT NOT NULL,
            detalle TEXT
        );
        INSERT INTO sales (id, fecha_hora, total_centavos)
            VALUES (1, '2026-01-01T00:00:00Z', 200);
        INSERT INTO sale_items
            (venta_id, codigo, nombre, cantidad,
             precio_unitario_centavos, total_centavos)
            VALUES (1, '1', 'X', 2, 100, 200);
        PRAGMA user_version = 1;
        """
    )
    conn.close()

    conn = database.connect(path)
    database.init_db(conn)
    assert database.schema_version(conn) == database.SCHEMA_VERSION == 2
    assert conn.execute("SELECT cantidad FROM sale_items").fetchone()[0] == 2.0

    conn.execute(
        "INSERT INTO sale_items"
        " (venta_id, codigo, nombre, cantidad,"
        "  precio_unitario_centavos, total_centavos)"
        " VALUES (1, '2', 'Y', 2.5, 100, 250)"
    )
    conn.execute(
        "INSERT INTO cash_movements"
        " (fecha_hora, tipo, monto_centavos, concepto)"
        " VALUES ('2026-01-01T00:00:00Z', 'venta', 100, 'mostrador')"
    )
    conn.close()
