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
