#!/usr/bin/env python3
"""Migra los datos CSV y .credentials de Xun-POS a SQLite.

Uso:
    python3 scripts/migrate_csv.py --source ~/.local/share/xun-pos --dry-run
    python3 scripts/migrate_csv.py --source ~/.local/share/xun-pos
"""

from __future__ import annotations

import argparse
import base64
import csv
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config
import database
import security

LEGACY_FILES = (
    ".credentials",
    "productos.csv",
    "ventas.csv",
    "flujo_caja.csv",
    "settings.json",
)


class MigrationError(RuntimeError):
    """La migración no se puede completar sin intervención."""


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


def normalize_code(value) -> str:
    """Same normalization the GUI applies to barcodes."""
    return str(value or "").strip().lstrip("0") or "0"


def migrate_password(stored: str) -> str:
    """Keep PBKDF2 hashes and re-hash legacy base64 passwords."""
    if not stored:
        raise ValueError("contraseña vacía")
    if stored.startswith(security.PREFIX + "$") or "$" in stored:
        return stored
    try:
        plain = base64.b64decode(stored).decode("utf-8")
    except Exception as exc:
        raise ValueError("formato de contraseña desconocido") from exc
    return security.hash_password(plain)


def _read_dicts(path: Path) -> list[dict]:
    with open(path, "r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def read_users(source: Path, errors: list[str]) -> list[dict]:
    path = source / ".credentials"
    users = []
    if not path.exists():
        return users
    seen = set()
    with open(path, "r", encoding="utf-8") as handle:
        for number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            parts = line.split(":")
            if len(parts) != 3:
                errors.append(f".credentials:{number}: formato inválido")
                continue
            username, stored, role = (part.strip() for part in parts)
            if not username or username in seen:
                errors.append(f".credentials:{number}: usuario duplicado")
                continue
            if role not in ("admin", "cashier"):
                errors.append(f".credentials:{number}: rol inválido {role!r}")
                continue
            try:
                password_hash = migrate_password(stored)
            except ValueError as exc:
                errors.append(f".credentials:{number}: {exc}")
                continue
            seen.add(username)
            users.append(
                {
                    "username": username,
                    "password_hash": password_hash,
                    "role": role,
                }
            )
    return users


def read_products(source: Path, errors: list[str]) -> list[dict]:
    path = source / "productos.csv"
    products = []
    if not path.exists():
        return products
    seen = set()
    for number, row in enumerate(_read_dicts(path), start=2):
        code = normalize_code(row.get("codigo"))
        name = (row.get("nombre") or "").strip()
        if not name:
            errors.append(f"productos.csv:{number}: nombre vacío")
            continue
        if code in seen:
            errors.append(f"productos.csv:{number}: código duplicado {code}")
            continue
        try:
            price = money_to_cents(row.get("precio"))
        except ValueError as exc:
            errors.append(f"productos.csv:{number}: {exc}")
            continue
        try:
            stock = int(str(row.get("inventario") or "0").strip())
        except ValueError:
            stock = 0
            errors.append(f"productos.csv:{number}: inventario inválido, se usa 0")
        seen.add(code)
        products.append(
            {
                "codigo": code,
                "nombre": name,
                "precio_centavos": price,
                "inventario": stock,
            }
        )
    return products


def read_sales(source: Path, errors: list[str]) -> list[dict]:
    path = source / "ventas.csv"
    sales = []
    if not path.exists():
        return sales
    for number, row in enumerate(_read_dicts(path), start=2):
        code = normalize_code(row.get("codigo"))
        name = (row.get("nombre") or "").strip()
        try:
            quantity = Decimal(str(row.get("cantidad") or "").strip())
        except InvalidOperation:
            errors.append(f"ventas.csv:{number}: cantidad inválida")
            continue
        if not quantity.is_finite() or quantity <= 0:
            errors.append(f"ventas.csv:{number}: cantidad no positiva")
            continue
        try:
            unit = money_to_cents(row.get("precio_unitario"))
            total = money_to_cents(row.get("total"))
        except ValueError as exc:
            errors.append(f"ventas.csv:{number}: {exc}")
            continue
        sales.append(
            {
                "fecha_hora": (row.get("fecha_hora") or "").strip(),
                "codigo": code,
                "nombre": name,
                "cantidad": float(quantity),
                "precio_unitario_centavos": unit,
                "total_centavos": total,
            }
        )
    return sales


def read_cash(source: Path, errors: list[str]) -> list[dict]:
    path = source / "flujo_caja.csv"
    movements = []
    if not path.exists():
        return movements
    for number, row in enumerate(_read_dicts(path), start=2):
        kind = (row.get("tipo") or "").strip().lower()
        if kind not in ("entrada", "salida", "venta"):
            errors.append(f"flujo_caja.csv:{number}: tipo inválido")
            continue
        try:
            amount = abs(money_to_cents(row.get("monto")))
        except ValueError as exc:
            errors.append(f"flujo_caja.csv:{number}: {exc}")
            continue
        if amount == 0:
            errors.append(f"flujo_caja.csv:{number}: monto cero")
            continue
        movements.append(
            {
                "fecha_hora": (row.get("fecha_hora") or "").strip(),
                "tipo": kind,
                "monto_centavos": amount,
                "concepto": (row.get("concepto") or "").strip(),
            }
        )
    return movements


def read_settings(source: Path, errors: list[str]) -> dict:
    path = source / "settings.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        errors.append(f"settings.json: {exc}")
        return {}
    if not isinstance(data, dict):
        errors.append("settings.json: se esperaba un objeto")
        return {}
    return data


def backup_sources(source: Path, backup_dir: Path | None) -> Path | None:
    files = [name for name in LEGACY_FILES if (source / name).exists()]
    if not files:
        return None
    target = backup_dir or (
        source / "backups" / datetime.now().strftime("%Y%m%d-%H%M%S")
    )
    target.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(target, 0o700)
    except OSError:
        pass
    for name in files:
        destination = target / name
        shutil.copy2(source / name, destination)
        try:
            os.chmod(destination, 0o600)
        except OSError:
            pass
    return target


def _stats(conn) -> dict:
    def scalar(sql, default=0):
        return conn.execute(sql).fetchone()[0] or default

    return {
        "users": scalar("SELECT COUNT(*) FROM users"),
        "products": scalar("SELECT COUNT(*) FROM products"),
        "sales": scalar("SELECT COUNT(*) FROM sales"),
        "sale_items": scalar("SELECT COUNT(*) FROM sale_items"),
        "cash_movements": scalar("SELECT COUNT(*) FROM cash_movements"),
        "sales_cents": scalar("SELECT SUM(total_centavos) FROM sales"),
        "cash_cents": scalar("SELECT SUM(monto_centavos) FROM cash_movements"),
    }


def _insert(conn, users, products, sales, cash, settings) -> None:
    now = datetime.now(timezone.utc).isoformat()
    for user in users:
        conn.execute(
            "INSERT INTO users"
            " (username, password_hash, role, activo, creado_en)"
            " VALUES (?, ?, ?, 1, ?)",
            (
                user["username"],
                user["password_hash"],
                user["role"],
                now,
            ),
        )

    product_ids = {}
    for product in products:
        cursor = conn.execute(
            "INSERT INTO products"
            " (codigo, nombre, precio_centavos, inventario)"
            " VALUES (?, ?, ?, ?)",
            (
                product["codigo"],
                product["nombre"],
                product["precio_centavos"],
                product["inventario"],
            ),
        )
        product_ids[product["codigo"]] = cursor.lastrowid

    for sale in sales:
        cursor = conn.execute(
            "INSERT INTO sales"
            " (fecha_hora, usuario_id, total_centavos, origen)"
            " VALUES (?, NULL, ?, 'legacy')",
            (sale["fecha_hora"], sale["total_centavos"]),
        )
        conn.execute(
            "INSERT INTO sale_items"
            " (venta_id, producto_id, codigo, nombre, cantidad,"
            "  precio_unitario_centavos, total_centavos)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                cursor.lastrowid,
                product_ids.get(sale["codigo"]),
                sale["codigo"],
                sale["nombre"],
                sale["cantidad"],
                sale["precio_unitario_centavos"],
                sale["total_centavos"],
            ),
        )

    for movement in cash:
        conn.execute(
            "INSERT INTO cash_movements"
            " (fecha_hora, tipo, monto_centavos, concepto)"
            " VALUES (?, ?, ?, ?)",
            (
                movement["fecha_hora"],
                movement["tipo"],
                movement["monto_centavos"],
                movement["concepto"],
            ),
        )

    for key, value in settings.items():
        conn.execute(
            "INSERT OR REPLACE INTO settings (clave, valor) VALUES (?, ?)",
            (key, json.dumps(value, ensure_ascii=False)),
        )


def migrate(
    source: Path,
    db: Path,
    *,
    dry_run: bool = False,
    force: bool = False,
    backup: bool = True,
    backup_dir: Path | None = None,
) -> dict:
    """Migrate CSV data into SQLite and return a summary."""
    source = Path(source)
    db = Path(db)
    if not source.is_dir():
        raise MigrationError(f"carpeta de origen no encontrada: {source}")

    errors: list[str] = []
    users = read_users(source, errors)
    products = read_products(source, errors)
    sales = read_sales(source, errors)
    cash = read_cash(source, errors)
    settings = read_settings(source, errors)

    total_sales = sum(sale["total_centavos"] for sale in sales)
    total_cash = sum(item["monto_centavos"] for item in cash)

    summary = {
        "source": str(source),
        "db": str(db),
        "dry_run": dry_run,
        "users": len(users),
        "products": len(products),
        "sales": len(sales),
        "cash_movements": len(cash),
        "sales_cents": total_sales,
        "cash_cents": total_cash,
        "errors": errors,
        "backup": None,
    }

    if dry_run:
        return summary

    if backup:
        summary["backup"] = str(backup_sources(source, backup_dir))

    conn = database.connect(db)
    try:
        database.init_db(conn)
        marker = conn.execute(
            "SELECT valor FROM settings WHERE clave = 'migracion_csv'"
        ).fetchone()
        before = _stats(conn)
        if marker is not None and not force:
            raise MigrationError(
                "esta base de datos ya fue migrada; usa --force solo si "
                "sabes lo que haces"
            )
        if any(before[key] for key in ("users", "products", "sales", "cash_movements")):
            if not force:
                raise MigrationError(
                    "la base de datos ya contiene datos; usa --force solo "
                    "si sabes lo que haces"
                )

        with database.transaction(conn):
            _insert(conn, users, products, sales, cash, settings)
            after = _stats(conn)
            expected = {
                "users": len(users),
                "products": len(products),
                "sales": len(sales),
                "sale_items": len(sales),
                "cash_movements": len(cash),
                "sales_cents": total_sales,
                "cash_cents": total_cash,
            }
            for key, value in expected.items():
                if after[key] - before[key] != value:
                    raise MigrationError(
                        f"verificación falló en {key}: "
                        f"esperado {value}, obtenido {after[key] - before[key]}"
                    )
            conn.execute(
                "INSERT OR REPLACE INTO settings (clave, valor) VALUES (?, ?)",
                (
                    "migracion_csv",
                    json.dumps(
                        {
                            "fecha": datetime.now(timezone.utc).isoformat(),
                            "origen": str(source),
                            "conteos": {
                                "usuarios": len(users),
                                "productos": len(products),
                                "ventas": len(sales),
                                "caja": len(cash),
                            },
                            "totales_centavos": {
                                "ventas": total_sales,
                                "caja": total_cash,
                            },
                        },
                        ensure_ascii=False,
                    ),
                ),
            )
        return summary
    finally:
        conn.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Migrar datos CSV de Xun-POS a SQLite"
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=config.data_dir(),
        help="carpeta con .credentials y los CSV",
    )
    parser.add_argument(
        "--db", type=Path, default=config.db_path(), help="base de datos destino"
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--no-backup", action="store_true")
    parser.add_argument("--backup-dir", type=Path, default=None)
    args = parser.parse_args(argv)

    try:
        summary = migrate(
            args.source,
            args.db,
            dry_run=args.dry_run,
            force=args.force,
            backup=not args.no_backup,
            backup_dir=args.backup_dir,
        )
    except MigrationError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    prefix = "[DRY RUN] " if summary["dry_run"] else ""
    print(f"{prefix}Origen: {summary['source']}")
    print(f"{prefix}Destino: {summary['db']}")
    print(
        f"{prefix}Importados: {summary['users']} usuarios, "
        f"{summary['products']} productos, {summary['sales']} ventas, "
        f"{summary['cash_movements']} movimientos de caja"
    )
    print(
        f"{prefix}Totales: ventas {summary['sales_cents']} centavos, "
        f"caja {summary['cash_cents']} centavos"
    )
    if summary["backup"]:
        print(f"Backup: {summary['backup']}")
    if summary["errors"]:
        print(f"Avisos ({len(summary['errors'])}):")
        for message in summary["errors"]:
            print(f"  - {message}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
