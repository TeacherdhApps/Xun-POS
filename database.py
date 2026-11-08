#!/usr/bin/env python3
"""Esquema y utilidades de SQLite para Xun-POS.

Uso:
    python3 database.py --init [--path RUTA]
"""

from __future__ import annotations

import argparse
import contextlib
import os
import sqlite3
from pathlib import Path

SCHEMA_VERSION = 2
APP_DIR_NAME = "xun-pos"
DB_FILE_NAME = "xun.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL CHECK (role IN ('admin', 'cashier')),
    activo        INTEGER NOT NULL DEFAULT 1,
    creado_en     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS products (
    id              INTEGER PRIMARY KEY,
    codigo          TEXT NOT NULL UNIQUE,
    nombre          TEXT NOT NULL,
    precio_centavos INTEGER NOT NULL CHECK (precio_centavos >= 0),
    inventario      INTEGER NOT NULL DEFAULT 0,
    activo          INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS sales (
    id             INTEGER PRIMARY KEY,
    fecha_hora     TEXT NOT NULL,
    usuario_id     INTEGER REFERENCES users(id),
    total_centavos INTEGER NOT NULL CHECK (total_centavos >= 0),
    estado         TEXT NOT NULL DEFAULT 'completada',
    origen         TEXT NOT NULL DEFAULT 'pos'
);

CREATE TABLE IF NOT EXISTS sale_items (
    id                       INTEGER PRIMARY KEY,
    venta_id                 INTEGER NOT NULL REFERENCES sales(id) ON DELETE CASCADE,
    producto_id              INTEGER REFERENCES products(id),
    codigo                   TEXT NOT NULL,
    nombre                   TEXT NOT NULL,
    cantidad                 REAL NOT NULL CHECK (cantidad > 0),
    precio_unitario_centavos INTEGER NOT NULL CHECK (precio_unitario_centavos >= 0),
    total_centavos           INTEGER NOT NULL CHECK (total_centavos >= 0)
);

CREATE TABLE IF NOT EXISTS cash_movements (
    id             INTEGER PRIMARY KEY,
    fecha_hora     TEXT NOT NULL,
    tipo           TEXT NOT NULL CHECK (tipo IN ('entrada', 'salida', 'venta')),
    monto_centavos INTEGER NOT NULL CHECK (monto_centavos > 0),
    concepto       TEXT NOT NULL,
    usuario_id     INTEGER REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS settings (
    clave TEXT PRIMARY KEY,
    valor TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
    id         INTEGER PRIMARY KEY,
    fecha_hora TEXT NOT NULL,
    usuario_id INTEGER,
    accion     TEXT NOT NULL,
    detalle    TEXT
);

CREATE INDEX IF NOT EXISTS idx_sales_fecha ON sales(fecha_hora);
CREATE INDEX IF NOT EXISTS idx_items_venta ON sale_items(venta_id);
CREATE INDEX IF NOT EXISTS idx_cash_fecha ON cash_movements(fecha_hora);
"""


def default_db_path() -> Path:
    """Return the database path following XDG_DATA_HOME."""
    base = os.environ.get("XDG_DATA_HOME") or os.path.join(
        Path.home(), ".local", "share"
    )
    return Path(base) / APP_DIR_NAME / DB_FILE_NAME


def connect(db_path: str | os.PathLike | None = None) -> sqlite3.Connection:
    """Open a connection with foreign keys, WAL and a busy timeout."""
    path = Path(db_path) if db_path else default_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


MIGRATION_1_TO_2 = """
ALTER TABLE sale_items RENAME TO sale_items_v1;
CREATE TABLE sale_items (
    id                       INTEGER PRIMARY KEY,
    venta_id                 INTEGER NOT NULL REFERENCES sales(id) ON DELETE CASCADE,
    producto_id              INTEGER REFERENCES products(id),
    codigo                   TEXT NOT NULL,
    nombre                   TEXT NOT NULL,
    cantidad                 REAL NOT NULL CHECK (cantidad > 0),
    precio_unitario_centavos INTEGER NOT NULL CHECK (precio_unitario_centavos >= 0),
    total_centavos           INTEGER NOT NULL CHECK (total_centavos >= 0)
);
INSERT INTO sale_items
    (id, venta_id, producto_id, codigo, nombre, cantidad,
     precio_unitario_centavos, total_centavos)
SELECT id, venta_id, producto_id, codigo, nombre, cantidad,
       precio_unitario_centavos, total_centavos
FROM sale_items_v1;
DROP TABLE sale_items_v1;

ALTER TABLE cash_movements RENAME TO cash_movements_v1;
CREATE TABLE cash_movements (
    id             INTEGER PRIMARY KEY,
    fecha_hora     TEXT NOT NULL,
    tipo           TEXT NOT NULL CHECK (tipo IN ('entrada', 'salida', 'venta')),
    monto_centavos INTEGER NOT NULL CHECK (monto_centavos > 0),
    concepto       TEXT NOT NULL,
    usuario_id     INTEGER REFERENCES users(id)
);
INSERT INTO cash_movements
    (id, fecha_hora, tipo, monto_centavos, concepto, usuario_id)
SELECT id, fecha_hora, tipo, monto_centavos, concepto, usuario_id
FROM cash_movements_v1;
DROP TABLE cash_movements_v1;
"""


def init_db(conn: sqlite3.Connection) -> int:
    """Create or upgrade the schema and return its version."""
    version = schema_version(conn)
    if version == 0:
        conn.executescript(SCHEMA)
    elif version < SCHEMA_VERSION:
        if version < 2:
            conn.executescript(MIGRATION_1_TO_2)
        conn.executescript(SCHEMA)
    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    return SCHEMA_VERSION


def schema_version(conn: sqlite3.Connection) -> int:
    """Return the schema version stored in the database."""
    return int(conn.execute("PRAGMA user_version").fetchone()[0])


@contextlib.contextmanager
def transaction(conn: sqlite3.Connection):
    """Run a block in a transaction: commit on success, rollback on error."""
    conn.execute("BEGIN")
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    else:
        conn.commit()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Base de datos de Xun-POS")
    parser.add_argument("--init", action="store_true", help="crear el esquema")
    parser.add_argument("--path", type=Path, default=None, help="ruta del archivo .db")
    parser.add_argument("--version", action="store_true", help="mostrar la versión")
    args = parser.parse_args(argv)

    if args.version:
        print(SCHEMA_VERSION)
        return 0

    if args.init:
        path = args.path or default_db_path()
        conn = connect(path)
        try:
            init_db(conn)
        finally:
            conn.close()
        print(f"Base de datos lista: {path} (esquema v{SCHEMA_VERSION})")
        return 0

    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
