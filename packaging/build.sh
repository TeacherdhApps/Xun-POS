#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
export XUN_POS_SOURCE="$(pwd)"

VERSION="1.1.0"
STAGE=$(mktemp -d)
trap 'rm -rf "$STAGE"' EXIT

mkdir -p \
  "$STAGE/DEBIAN" \
  "$STAGE/usr/bin" \
  "$STAGE/usr/share/xun-pos" \
  "$STAGE/usr/share/applications" \
  "$STAGE/usr/share/icons/hicolor/512x512/apps"

cp debian/control "$STAGE/DEBIAN/control"
cp login.py database.py config.py security.py store.py thermal_printer.py \
   pos_gui.py products_gui.py reports_gui.py settings_gui.py \
   Xun-POS.png "$STAGE/usr/share/xun-pos/"
cp -r scripts "$STAGE/usr/share/xun-pos/"
rm -rf "$STAGE/usr/share/xun-pos/scripts/__pycache__" "$STAGE/usr/share/xun-pos/__pycache__"
chmod 0755 "$STAGE/usr/share/xun-pos" "$STAGE/usr/share/xun-pos/scripts"
chmod 0644 "$STAGE/usr/share/xun-pos"/*.py "$STAGE/usr/share/xun-pos/scripts"/*.py \
  "$STAGE/usr/share/xun-pos/Xun-POS.png"

cat > "$STAGE/usr/bin/xun-pos" <<'SH'
#!/bin/sh
exec /usr/bin/python3 /usr/share/xun-pos/login.py "$@"
SH
chmod 0755 "$STAGE/usr/bin/xun-pos"

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

cat > "$STAGE/usr/share/applications/xun-pos.desktop" <<'SH'
[Desktop Entry]
Type=Application
Name=Xun-POS
Comment=Xun-POS - Punto de Venta
Exec=xun-pos
Icon=xun-pos
Terminal=false
Categories=Office;PointOfSale;
SH

mkdir -p dist
dpkg-deb --build --root-owner-group "$STAGE" "dist/xun-pos_${VERSION}_all.deb"

echo "Paquete creado: dist/xun-pos_${VERSION}_all.deb"
