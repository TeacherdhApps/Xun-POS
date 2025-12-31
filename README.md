# Xun-POS - Sistema de Punto de Venta

Punto de venta rápido y ligero.

## Inicio Rápido

### Instalación de Dependencias

Antes de ejecutar el programa, instala las dependencias necesarias:

```bash
pip install -r requirements.txt
```

### Ejecutar el Programa

```bash
./start
```

O directamente:

```bash
python3 login.py
```

### Credenciales por Defecto

- **Usuario:** `admin`
- **Contraseña:** `password`

**Nota:** Cambia la contraseña después del primer inicio

## Requisitos

- **Sistema Operativo:** Linux (Ubuntu, Debian, Fedora, Arch, etc.)
- **Python:** 3.7 o superior

Para otras dependencias, consulta la sección de **Instalación de Dependencias**.

**Importante:** Esta aplicación NO es compatible con Windows

## Características

### Módulos Principales

1. **Punto de Venta (POS)** - Interfaz principal de ventas
2. **Gestión de Productos** - Agregar, editar y eliminar productos
3. **Reportes** - Ventas y movimientos de caja
4. **Configuración** - Datos del negocio y ajustes

### Sistema de Usuarios

**Administrador:**
- Acceso completo a todos los módulos
- Gestión de usuarios (crear, eliminar, cambiar contraseñas)
- Acceso a reportes y configuración

**Cajero:**
- Acceso solo a POS y Productos
- Sin acceso a reportes, configuración ni gestión de usuarios

## Estructura de Archivos

```
Xun-POS/
├── login.py           # Sistema de autenticación
├── pos_gui.py         # Punto de venta
├── products_gui.py    # Gestión de productos
├── reports_gui.py     # Reportes
├── settings_gui.py    # Configuración
├── products.csv       # Base de datos de productos
├── sales.csv          # Registro de ventas
├── cash_flow.csv      # Movimientos de caja
├── .credentials       # Usuarios y contraseñas
├── settings.json      # Configuración de la tienda
└── start              # Script de inicio
```

## Gestión de Usuarios (Solo Admin)

### Agregar Usuario
1. Iniciar sesión como admin
2. Seleccionar opción 5: "Agregar Nuevo Usuario"
3. Ingresar nombre de usuario y contraseña
4. Seleccionar rol (admin o cajero)

### Cambiar Contraseña
1. Iniciar sesión como admin
2. Seleccionar opción 7: "Cambiar Contraseña"
3. Seleccionar usuario
4. Ingresar nueva contraseña

### Eliminar Usuario
1. Iniciar sesión como admin
2. Seleccionar opción 6: "Eliminar Usuario"
3. Seleccionar usuario a eliminar
4. Confirmar eliminación

## Uso Diario

### Para Cajeros
1. Iniciar sesión con credenciales de cajero
2. Acceder al POS para realizar ventas
3. Gestionar inventario de productos según necesidad

### Para Administradores
1. Revisar reportes de ventas diariamente
2. Actualizar inventario y precios
3. Gestionar usuarios y configuración del sistema
4. Monitorear movimientos de caja

## Seguridad

- Contraseñas codificadas en Base64
- Control de acceso por roles
- Protección contra auto-eliminación de usuario activo
- Protección del último usuario administrador

## Archivos de Datos

### products.csv
Formato: `barcode,name,price,inventario`

### sales.csv
Formato: `timestamp,barcode,nombre,cantidad,precio_unitario,precio_total`

### cash_flow.csv
Formato: `timestamp,tipo,monto,concepto`

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
chmod +x start
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

- Los archivos CSV usan formato UTF-8
- Las fechas están en formato dd/mm/yyyy
- La interfaz está completamente en español
- Los movimientos de caja se registran automáticamente con cada venta

## Actualización del Sistema

Para mantener los datos al actualizar:
1. Hacer backup de los archivos .csv, .credentials y settings.json
2. Actualizar los archivos .py
3. Restaurar los datos guardados

## Soporte

Para problemas o preguntas, consulta el código fuente o contacta al administrador del sistema.

## Licencia

Este proyecto está bajo la Licencia MIT. Para más detalles, vea el archivo [LICENSE](LICENSE).

---

**Versión:** 1.0.0  
**Última actualización:** Diciembre 2025