#!/bin/bash
set -euo pipefail

# Instalación de Xun-POS mediante paquete .deb
# Soporta sistemas basados en Debian (Debian, Ubuntu, etc.)

echo "=== Instalación de Xun-POS ==="

# Detectar el sistema operativo
if [ -f /etc/debian_version ]; then
    echo "Sistema basado en Debian detectado."

    # Instalar dependencias del sistema
    sudo apt-get update
    sudo apt-get install -y python3 python3-pip python3-tk python3-tkcalendar

    # Instalar dependencias de Python
    pip3 install -r requirements.txt

    # Construir e instalar el paquete .deb
    bash packaging/build.sh
    sudo dpkg -i dist/xun-pos_*.deb

    echo ""
    echo "========================================"
    echo "¡Instalación completa!"
    echo "Ejecuta Xun-POS con: xun-pos"
    echo "========================================"

elif [ -f /etc/fedora-release ] || [ -f /etc/arch-release ]; then
    echo "Sistema basado en Fedora/Arch detectado."
    echo "Instalando dependencias..."

    if [ -f /etc/fedora-release ]; then
        sudo dnf install -y python3 python3-pip python3-tkinter python3-tkcalendar
    elif [ -f /etc/arch-release ]; then
        sudo pacman -Syu --noconfirm python python-pip tk tkcalendar
    fi

    pip3 install -r requirements.txt

    echo ""
    echo "========================================"
    echo "Instalación de dependencias completa."
    echo "Ejecuta Xun-POS con: python3 login.py"
    echo "========================================"
else
    echo "Sistema operativo no soportado para instalación automática."
    echo "Instala manualmente las dependencias y ejecuta: python3 login.py"
    exit 1
fi
