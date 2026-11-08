#!/usr/bin/env python3
"""Acceso a los datos de Xun-POS sobre SQLite.

La primera vez que se abre una base de datos vacía, migra automáticamente
los archivos CSV y .credentials que encuentre en la carpeta de datos.
"""

from __future__ import annotations

import fcntl
import json
import os
import shutil
import sqlite3
import tempfile
import zipfile
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

import config
import database
from scripts import migrate_csv

CASH_TYPES = ("entrada", "salida", "venta")
LEGACY_FILES = config.LEGACY_FILES


def money_to_cents(value) -> int:
    """Convert a decimal amount to integer cents with ROUND_HALF_UP."""
    if value is None or str(value).strip() == "":
        raise ValueError("importe vacío")
    try:
        amount = Decimal(str(value).strip())
    except InvalidOperation as exc:
        raise ValueError(f"importe inválido: {value!r}") from exc
    if not amount.is_finite():
        raise ValueError(f"importe inválido: {value!r}")
    return int(
        (amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    )


def line_total_cents(price, quantity) -> int:
    """Total cents for a line, supporting fractional quantities."""
    unit_cents = money_to_cents(price)
    try:
        amount = Decimal(str(quantity))
    except InvalidOperation as exc:
        raise ValueError(f"cantidad inválida: {quantity!r}") from exc
    if not amount.is_finite() or amount <= 0:
        raise ValueError(f"cantidad inválida: {quantity!r}")
    return int(
        (Decimal(unit_cents) * amount).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
    )


def normalize_code(value) -> str:
    return str(value or "").strip().lstrip("0") or "0"


def format_price(cents) -> str:
    return f"{int(cents) / 100:.2f}"


def format_quantity(value) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "0"
    if number.is_integer():
        return str(int(number))
    return f"{number:g}"


def parse_quantity(value) -> float:
    text = str(value if value is not None else "0").strip() or "0"
    try:
        number = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(f"cantidad inválida: {value!r}") from exc
    if not number.is_finite():
        raise ValueError(f"cantidad inválida: {value!r}")
    return float(number)


def _date_key(value) -> str:
    if hasattr(value, "isoformat"):
        return value.isoformat()[:10]
    return str(value)[:10]


def _safe_extract(archive: zipfile.ZipFile, destination: Path) -> None:
    root = destination.resolve()
    for member in archive.infolist():
        target = (root / member.filename).resolve()
        if target != root and root not in target.parents:
            raise ValueError(f"ruta insegura en el zip: {member.filename}")
        archive.extract(member, destination)


def _prepare_backup(zip_path, destination: Path) -> Path:
    """Extract a xun.db or legacy CSV backup and return a valid database."""
    with zipfile.ZipFile(zip_path) as archive:
        names = set(archive.namelist())
        if database.DB_FILE_NAME in names:
            archive.extract(database.DB_FILE_NAME, destination)
            candidate = destination / database.DB_FILE_NAME
        elif any(name in names for name in LEGACY_FILES):
            _safe_extract(archive, destination)
            candidate = destination / "restored.db"
            migrate_csv.migrate(destination, candidate, backup=False)
        else:
            raise ValueError(
                "El zip no contiene xun.db ni datos CSV de Xun-POS"
            )

    conn = sqlite3.connect(candidate)
    try:
        version = database.schema_version(conn)
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
    finally:
        conn.close()
    if version == 0 and not tables & {"products", "sales"}:
        raise ValueError("El archivo xun.db del zip no es válido")

    conn = database.connect(candidate)
    try:
        database.init_db(conn)
    finally:
        conn.close()
    return candidate


class Store:
    """Repositorio de productos, ventas, caja y ajustes."""

    def __init__(self, mode=None, db_path=None, data_dir=None):
        self.mode = mode or config.get_mode("production")
        self.data_dir = (
            Path(data_dir) if data_dir else config.ensure_data_dir(self.mode)
        )
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = (
            Path(db_path) if db_path else self.data_dir / database.DB_FILE_NAME
        )
        self.migration = self._auto_migrate()
        self.conn = database.connect(self.db_path)
        database.init_db(self.conn)
        try:
            os.chmod(self.db_path, 0o600)
        except OSError:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()

    def close(self):
        if getattr(self, "conn", None) is not None:
            self.conn.close()
            self.conn = None

    # ------------------------------------------------------------------
    # Migración automática
    # ------------------------------------------------------------------
    def _auto_migrate(self):
        legacy = [
            name for name in LEGACY_FILES if (self.data_dir / name).exists()
        ]
        if not legacy:
            return None
        lock_path = self.data_dir / ".migracion.lock"
        fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            if self._db_has_data():
                return None
            return migrate_csv.migrate(
                self.data_dir, self.db_path, backup=True
            )
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    def _db_has_data(self) -> bool:
        if not self.db_path.exists():
            return False
        try:
            conn = sqlite3.connect(self.db_path)
        except sqlite3.Error:
            return True
        try:
            try:
                marker = conn.execute(
                    "SELECT 1 FROM settings WHERE clave = 'migracion_csv'"
                ).fetchone()
                counts = conn.execute(
                    "SELECT (SELECT COUNT(*) FROM products)"
                    " + (SELECT COUNT(*) FROM sales)"
                    " + (SELECT COUNT(*) FROM cash_movements)"
                ).fetchone()[0]
            except sqlite3.Error as exc:
                return "no such table" not in str(exc).lower()
            return bool(marker) or counts > 0
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Productos
    # ------------------------------------------------------------------
    def list_products(self) -> dict[str, dict]:
        rows = self.conn.execute(
            "SELECT codigo, nombre, precio_centavos, inventario"
            " FROM products WHERE activo = 1 ORDER BY id"
        ).fetchall()
        return {
            row["codigo"]: {
                "nombre": row["nombre"],
                "precio": row["precio_centavos"] / 100,
                "inventario": row["inventario"],
            }
            for row in rows
        }

    def list_products_for_ui(self) -> list[dict]:
        rows = self.conn.execute(
            "SELECT codigo, nombre, precio_centavos, inventario"
            " FROM products WHERE activo = 1 ORDER BY id"
        ).fetchall()
        return [
            {
                "codigo": row["codigo"],
                "nombre": row["nombre"],
                "precio": format_price(row["precio_centavos"]),
                "inventario": format_quantity(row["inventario"]),
            }
            for row in rows
        ]

    def get_product(self, codigo):
        code = normalize_code(codigo)
        row = self.conn.execute(
            "SELECT codigo, nombre, precio_centavos, inventario"
            " FROM products WHERE codigo = ? AND activo = 1",
            (code,),
        ).fetchone()
        if row is None:
            return None
        return {
            "codigo": row["codigo"],
            "nombre": row["nombre"],
            "precio": row["precio_centavos"] / 100,
            "inventario": row["inventario"],
        }

    def replace_products(self, rows) -> None:
        """Save the product list, deactivating codes that disappeared.

        Sales keep referencing the old product rows, so removal is a soft
        delete (activo = 0) instead of DELETE.
        """
        cleaned = []
        seen = set()
        for row in rows:
            code = normalize_code(row.get("codigo"))
            name = str(row.get("nombre") or "").strip()
            if not name:
                raise ValueError(f"Producto sin nombre: {code}")
            if code in seen:
                raise ValueError(f"Código duplicado: {code}")
            seen.add(code)
            cleaned.append(
                (
                    code,
                    name,
                    money_to_cents(row.get("precio")),
                    parse_quantity(row.get("inventario")),
                )
            )

        with database.transaction(self.conn):
            for code, name, price, stock in cleaned:
                self.conn.execute(
                    "INSERT INTO products"
                    " (codigo, nombre, precio_centavos, inventario, activo)"
                    " VALUES (?, ?, ?, ?, 1)"
                    " ON CONFLICT(codigo) DO UPDATE SET"
                    "  nombre = excluded.nombre,"
                    "  precio_centavos = excluded.precio_centavos,"
                    "  inventario = excluded.inventario,"
                    "  activo = 1",
                    (code, name, price, stock),
                )
            codes = [row[0] for row in cleaned]
            if codes:
                placeholders = ",".join("?" for _ in codes)
                self.conn.execute(
                    f"UPDATE products SET activo = 0"
                    f" WHERE codigo NOT IN ({placeholders})",
                    codes,
                )
            else:
                self.conn.execute("UPDATE products SET activo = 0")

    # ------------------------------------------------------------------
    # Ventas
    # ------------------------------------------------------------------
    def record_sale(
        self, items, concepto=None, fecha_hora=None, origen="pos"
    ):
        """Insert sale, items, inventory change and cash movement atomically."""
        prepared = []
        total_cents = 0
        for codigo, item in items.items():
            quantity = Decimal(str(item["qty"]))
            if not quantity.is_finite() or quantity <= 0:
                raise ValueError(f"cantidad inválida: {item['qty']!r}")
            unit_cents = money_to_cents(item["precio"])
            line_total = line_total_cents(item["precio"], item["qty"])
            prepared.append(
                (
                    normalize_code(codigo),
                    str(item["nombre"]),
                    float(quantity),
                    unit_cents,
                    line_total,
                )
            )
            total_cents += line_total

        if not prepared:
            return None

        timestamp = fecha_hora or datetime.now().isoformat(
            timespec="microseconds"
        )
        with database.transaction(self.conn):
            cursor = self.conn.execute(
                "INSERT INTO sales (fecha_hora, total_centavos, origen)"
                " VALUES (?, ?, ?)",
                (timestamp, total_cents, origen),
            )
            sale_id = cursor.lastrowid
            for code, name, quantity, unit_cents, line_total in prepared:
                product = self.conn.execute(
                    "SELECT id FROM products WHERE codigo = ? AND activo = 1",
                    (code,),
                ).fetchone()
                product_id = product["id"] if product else None
                self.conn.execute(
                    "INSERT INTO sale_items"
                    " (venta_id, producto_id, codigo, nombre, cantidad,"
                    "  precio_unitario_centavos, total_centavos)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        sale_id,
                        product_id,
                        code,
                        name,
                        quantity,
                        unit_cents,
                        line_total,
                    ),
                )
                if product_id is not None:
                    self.conn.execute(
                        "UPDATE products SET inventario = inventario - ?"
                        " WHERE id = ?",
                        (quantity, product_id),
                    )
            self.conn.execute(
                "INSERT INTO cash_movements"
                " (fecha_hora, tipo, monto_centavos, concepto)"
                " VALUES (?, 'venta', ?, ?)",
                (
                    timestamp,
                    total_cents,
                    concepto or f"Venta #{sale_id}",
                ),
            )
        return sale_id

    def sales_between(self, start, end) -> list[dict]:
        rows = self.conn.execute(
            "SELECT s.id AS venta_id, s.fecha_hora, i.codigo, i.nombre,"
            " i.cantidad, i.total_centavos"
            " FROM sale_items i JOIN sales s ON s.id = i.venta_id"
            " WHERE substr(s.fecha_hora, 1, 10) BETWEEN ? AND ?"
            " ORDER BY s.fecha_hora, i.id",
            (_date_key(start), _date_key(end)),
        ).fetchall()
        return [dict(row) for row in rows]

    def sales_total_between(self, start, end) -> int:
        row = self.conn.execute(
            "SELECT COALESCE(SUM(total_centavos), 0) FROM sales"
            " WHERE substr(fecha_hora, 1, 10) BETWEEN ? AND ?",
            (_date_key(start), _date_key(end)),
        ).fetchone()
        return int(row[0])

    # ------------------------------------------------------------------
    # Caja
    # ------------------------------------------------------------------
    def add_cash_movement(
        self, tipo, amount, concepto, fecha_hora=None
    ) -> int:
        kind = str(tipo or "").strip().lower()
        if kind not in CASH_TYPES:
            raise ValueError(f"tipo de movimiento inválido: {tipo!r}")
        cents = abs(money_to_cents(amount))
        if cents == 0:
            raise ValueError("el monto debe ser distinto de cero")
        timestamp = fecha_hora or datetime.now().isoformat(
            timespec="microseconds"
        )
        with database.transaction(self.conn):
            cursor = self.conn.execute(
                "INSERT INTO cash_movements"
                " (fecha_hora, tipo, monto_centavos, concepto)"
                " VALUES (?, ?, ?, ?)",
                (timestamp, kind, cents, str(concepto or "").strip()),
            )
        return cursor.lastrowid

    def cash_movements_between(
        self, start, end, include_sales=False
    ) -> list[dict]:
        types = CASH_TYPES if include_sales else ("entrada", "salida")
        placeholders = ",".join("?" for _ in types)
        rows = self.conn.execute(
            "SELECT id, fecha_hora, tipo, monto_centavos, concepto"
            " FROM cash_movements"
            " WHERE substr(fecha_hora, 1, 10) BETWEEN ? AND ?"
            f" AND tipo IN ({placeholders})"
            " ORDER BY fecha_hora, id",
            (_date_key(start), _date_key(end), *types),
        ).fetchall()
        return [dict(row) for row in rows]

    def update_cash_movement(
        self, movement_id, tipo, amount, concepto
    ) -> None:
        kind = str(tipo or "").strip().lower()
        if kind not in CASH_TYPES:
            raise ValueError(f"tipo de movimiento inválido: {tipo!r}")
        cents = abs(money_to_cents(amount))
        if cents == 0:
            raise ValueError("el monto debe ser distinto de cero")
        with database.transaction(self.conn):
            cursor = self.conn.execute(
                "UPDATE cash_movements"
                " SET tipo = ?, monto_centavos = ?, concepto = ?"
                " WHERE id = ?",
                (kind, cents, str(concepto or "").strip(), movement_id),
            )
        if cursor.rowcount == 0:
            raise KeyError(f"movimiento no encontrado: {movement_id}")

    def delete_cash_movement(self, movement_id) -> None:
        with database.transaction(self.conn):
            cursor = self.conn.execute(
                "DELETE FROM cash_movements WHERE id = ?", (movement_id,)
            )
        if cursor.rowcount == 0:
            raise KeyError(f"movimiento no encontrado: {movement_id}")

    # ------------------------------------------------------------------
    # Ajustes
    # ------------------------------------------------------------------
    def get_settings(self) -> dict:
        settings = {}
        for row in self.conn.execute("SELECT clave, valor FROM settings"):
            try:
                settings[row["clave"]] = json.loads(row["valor"])
            except ValueError:
                settings[row["clave"]] = row["valor"]
        return settings

    def set_settings(self, settings: dict) -> None:
        with database.transaction(self.conn):
            for key, value in settings.items():
                self.conn.execute(
                    "INSERT INTO settings (clave, valor) VALUES (?, ?)"
                    " ON CONFLICT(clave) DO UPDATE SET valor = excluded.valor",
                    (str(key), json.dumps(value, ensure_ascii=False)),
                )

    # ------------------------------------------------------------------
    # Copias de seguridad
    # ------------------------------------------------------------------
    def _backup_to(self, path) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        dest = sqlite3.connect(target)
        try:
            self.conn.backup(dest)
        finally:
            dest.close()
        try:
            os.chmod(target, 0o600)
        except OSError:
            pass
        return target

    def export_backup(self, zip_path) -> Path:
        target = Path(zip_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        handle = tempfile.NamedTemporaryFile(
            suffix=".db", delete=False, dir=str(self.data_dir)
        )
        temp_path = Path(handle.name)
        handle.close()
        try:
            self._backup_to(temp_path)
            with zipfile.ZipFile(
                target, "w", zipfile.ZIP_DEFLATED
            ) as archive:
                archive.write(temp_path, arcname=database.DB_FILE_NAME)
        finally:
            temp_path.unlink(missing_ok=True)
        return target

    def restore_backup(self, zip_path) -> dict:
        """Replace the live database from a backup, keeping a safety copy.

        Using SQLite's backup API keeps this safe when other windows still
        have the database open.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            candidate = _prepare_backup(Path(zip_path), Path(temp_dir))
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            previous = self.data_dir / f"{self.db_path.name}.bak-{stamp}"
            self._backup_to(previous)

            source = database.connect(candidate)
            try:
                source.backup(self.conn)
            finally:
                source.close()
            database.init_db(self.conn)
        return {"db": str(self.db_path), "previous": str(previous)}


def restore_backup(zip_path, db_path=None, mode=None) -> dict:
    """Restore a backup for a closed database (offline restore)."""
    source_zip = Path(zip_path)
    target = Path(db_path) if db_path else config.db_path(mode)
    target.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as temp_dir:
        candidate = _prepare_backup(source_zip, Path(temp_dir))

        previous = None
        if target.exists():
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            previous = target.with_name(f"{target.name}.bak-{stamp}")
            shutil.copy2(target, previous)
        for suffix in ("-wal", "-shm"):
            Path(f"{target}{suffix}").unlink(missing_ok=True)
        shutil.copy2(candidate, target)
        try:
            os.chmod(target, 0o600)
        except OSError:
            pass

    return {"db": str(target), "previous": str(previous) if previous else None}
