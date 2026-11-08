# Xun-POS - Sistema de Punto de Venta

Sistema de Punto de Venta rápido y ligero.

## Inicio Rápido

### Instalación de Dependencias

Antes de ejecutar el programa, instale las dependencias necesarias:

```bash
pip install -r requirements.txt
```

### Ejecutar el Programa

```bash
python3 login.py
```

En el primer arranque se elige el modo de uso:

| Modo | Login | Datos |
|------|-------|-------|
| Producción | Usuarios reales con contraseña | `~/.local/share/xun-pos/` |
| Kiosco | Sin login; selección de cajero | Igual que producción |
| Demo | `admin` / `password` | `~/.local/share/xun-pos/demo/` |

Para una demostración sin cambiar el modo guardado:

```bash
python3 login.py --demo
```

El modo se guarda en `~/.config/xun-pos/config.json`. El usuario
`admin`/`password` **solo existe en modo demo**; en producción se crea un
administrador con contraseña propia en el primer arranque.

## Requisitos

- **Sistema Operativo:** Linux (Ubuntu, Debian, Fedora, Arch, etc.)
- **Python:** 3.7 o superior

Para otras dependencias, consulte la sección de **Instalación de Dependencias**.

**Importante:** Esta aplicación NO es compatible con Windows.

## Características

### Módulos Principales

1. **Punto de Venta (POS)** - Interfaz principal de ventas
2. **Gestión de Productos** - Añadir, editar y eliminar productos
3. **Reportes** - Reportes de ventas y flujo de caja
4. **Configuración** - Detalles del negocio y ajustes

### Sistema de Usuarios

**Administrador:**
- Acceso total a todos los módulos
- Gestión de usuarios (crear, eliminar, cambiar contraseñas)
- Acceso a reportes y configuración

**Cajero:**
- Acceso solo a POS y Productos
- Sin acceso a reportes, configuración o gestión de usuarios

## Estructura de Archivos

```
Xun-POS/
├── login.py           # Sistema de autenticación
├── pos_gui.py         # Punto de Venta
├── products_gui.py    # Gestión de productos
├── reports_gui.py     # Reportes
├── settings_gui.py    # Configuración
├── store.py           # Acceso a datos SQLite (repositorio)
├── productos.ejemplo.csv  # Datos de ejemplo para el primer arranque/demo
├── settings.ejemplo.json  # Configuración de ejemplo
├── database.py        # Esquema y conexión SQLite
├── scripts/migrate_csv.py  # Migración CSV -> SQLite
└── install.sh         # Script de instalación
```

> La base de datos real (`xun.db`) se crea en el directorio de datos del modo
> (`~/.local/share/xun-pos/` o `~/.local/share/xun-pos/demo/`) y está excluida
> por `.gitignore`. Los archivos legados (`.credentials`, `productos.csv`,
> `ventas.csv`, `flujo_caja.csv`, `settings.json`) solo se usan como origen de
> la migración automática. Nunca los subas al repositorio.

## Gestión de Usuarios (Solo Administrador)

### Añadir Usuario
1. Inicie sesión como administrador
2. Seleccione la opción 5: "Añadir Nuevo Usuario"
3. Ingrese nombre de usuario y contraseña
4. Seleccione el rol (administrador o cajero)

### Cambiar Contraseña
1. Inicie sesión como administrador
2. Seleccione la opción 7: "Cambiar Contraseña"
3. Seleccione el usuario
4. Ingrese la nueva contraseña

### Eliminar Usuario
1. Inicie sesión como administrador
2. Seleccione la opción 6: "Eliminar Usuario"
3. Seleccione el usuario a eliminar
4. Confirme la eliminación

## Uso Diario

### Para Cajeros
1. Inicie sesión con credenciales de cajero
2. Acceda al POS para realizar ventas
3. Gestione el inventario de productos según sea necesario

### Para Administradores
1. Revise los reportes de ventas diariamente
2. Actualice el inventario y los precios
3. Gestione usuarios y la configuración del sistema
4. Supervise el flujo de caja

## Seguridad

- Contraseñas cifradas (PBKDF2 con SHA256)
- Control de acceso basado en roles
- Protección contra la auto-eliminación del usuario activo
- Protección del último usuario administrador

## Archivos de Datos

Los datos viven en SQLite (esquema v2):

- `~/.local/share/xun-pos/xun.db` (modo producción/kiosco)
- `~/.local/share/xun-pos/demo/xun.db` (modo demo)

### Tablas principales
- `users`, `products`, `sales`, `sale_items`, `cash_movements`, `settings`, `audit_log`

### Repositorio (`store.py`)
- `list_products()` / `replace_products()` / `get_product()`
- `record_sale()` / `sales_between()` / `sales_total_between()`
- `add_cash_movement()` / `update_cash_movement()` / `delete_cash_movement()` / `cash_movements_between()`
- `get_settings()` / `set_settings()`
- `export_backup()` / `restore_backup()`

## Solución de Problemas

### Python no encontrado
```bash
# Ubuntu/Debian
sudo apt install python3 python3-tk

# Fedora
sudo dnf install python3 python3-tkinter

# Arch
sudo pacman -S python tk
```

### Error de permisos
```bash
chmod +x login.py
```

### tkinter no disponible
```bash
# Ubuntu/Debian
sudo apt install python3-tk

# Fedora
sudo dnf install python3-tkinter
```

## Notas

- La base de datos SQLite utiliza UTF-8 para las columnas de texto
- Las fechas están en formato AAAA-MM-DD (principalmente) o específico de la región
- La interfaz está completamente en español
- Los movimientos de flujo de caja se registran automáticamente con cada venta

## Migración a SQLite

`database.py` crea el esquema SQLite v2 en `~/.local/share/xun-pos/xun.db`.
La primera apertura que encuentre archivos CSV/`.credentials` en la carpeta de
datos del modo migra automáticamente (con backup y verificación).

Manualmente:

```bash
python3 scripts/migrate_csv.py --source ~/.local/share/xun-pos --dry-run
python3 scripts/migrate_csv.py --source ~/.local/share/xun-pos
```

## Pruebas

```bash
python3 -m venv .venv
.venv/bin/pip install pytest
.venv/bin/python -m pytest
```

## Actualización del Sistema

Para conservar los datos al actualizar:
1. Realice una copia de seguridad de `~/.local/share/xun-pos/`
   (incluye `xun.db`, los archivos legados y las bases de datos).
2. Actualice los archivos `.py`.
3. Restaure los datos guardados.

Las ventanas de configuración pueden exportar/importar la base de datos
automáticamente (`store.export_backup` / `store.restore_backup`).

## Soporte

Para problemas o preguntas, consulte el código fuente o contacte al administrador del sistema.

## Licencia

Este proyecto está bajo la Licencia MIT. Para más detalles, vea el archivo [LICENSE](LICENSE).

---

**Versión:** 1.0.0  
**Última Actualización:** Febrero 2026
