#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
export XUN_POS_SOURCE="$(pwd)"

VERSION="1.1.0"
STAGE=$(mktemp -d)
trap 'rm -rf "$STAGE"' EXIT

# Estructura de directorios del paquete .deb
mkdir -p \
  "$STAGE/DEBIAN" \
  "$STAGE/usr/bin" \
  "$STAGE/usr/share/xun-pos" \
  "$STAGE/usr/share/applications" \
  "$STAGE/usr/share/icons/hicolor/512x512/apps" \
  "$STAGE/usr/share/doc/xun-pos"

# Copiar control
cp debian/control "$STAGE/DEBIAN/control"

# Copiar scripts de la aplicación
cp login.py database.py config.py security.py store.py thermal_printer.py \
   pos_gui.py products_gui.py reports_gui.py settings_gui.py \
   Xun-POS.png "$STAGE/usr/share/xun-pos/"
cp -r scripts "$STAGE/usr/share/xun-pos/"
chmod 0644 "$STAGE/usr/share/xun-pos"/*
chmod 0755 "$STAGE/usr/share/xun-pos/scripts"

# Script de entrada /usr/bin/xun-pos
cat > "$STAGE/usr/bin/xun-pos" <<'SH'
#!/bin/sh
exec /usr/bin/python3 /usr/share/xun-pos/login.py "$@"
SH
chmod 0755 "$STAGE/usr/bin/xun-pos"

# Icono
python3 - <<'PY'
import os
from pathlib import Path
from PIL import Image

source = Path(os.environ["XUN_POS_SOURCE"]) / "Xun-POS.png"
target = Path("/tmp/xun-pos-icon.png")
image = Image.open(source).convert("RGBA")
image = image.resize((512, 512), Image.LANCZOS)
image.save(target, format="PNG")
PY
cp /tmp/xun-pos-icon.png "$STAGE/usr/share/icons/hicolor/512x512/apps/xun-pos.png"
chmod 0644 "$STAGE/usr/share/icons/hicolor/512x512/apps/xun-pos.png"

# Desktop entry
cp packaging/xun-pos.desktop "$STAGE/usr/share/applications/xun-pos.desktop"
chmod 0644 "$STAGE/usr/share/applications/xun-pos.desktop"

# Documentación
cp README.md LICENSE "$STAGE/usr/share/doc/xun-pos/"
chmod 0644 "$STAGE/usr/share/doc/xun-pos/README.md" "$STAGE/usr/share/doc/xun-pos/LICENSE"

# Corregir permisos para dpkg-deb
chmod -R a+r "$STAGE/usr"
chmod -R a+X "$STAGE/usr"
chmod 0755 "$STAGE/usr/bin/xun-pos"

# Construir paquete
mkdir -p dist
dpkg-deb --build --root-owner-group "$STAGE" "dist/xun-pos_${VERSION}_all.deb"

echo "Paquete creado: dist/xun-pos_${VERSION}_all.deb"
