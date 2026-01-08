#!/bin/bash

# Detect the operating system
if [ -f /etc/debian_version ]; then
    # Debian-based system (Debian, Ubuntu, etc.)
    echo "Debian-based system detected."
    
    # Update package list
    sudo apt-get update
    
    # Install Python, pip, and tkinter
    sudo apt-get install -y python3 python3-pip python3-tk
    
    # Install tkcalendar
    pip3 install tkcalendar
    
elif [ -f /etc/fedora-release ]; then
    # Fedora-based system
    echo "Fedora-based system detected."
    
    # Update package list
    sudo dnf check-update
    
    # Install Python, pip, and tkinter
    sudo dnf install -y python3 python3-pip python3-tkinter
    
    # Install tkcalendar
    pip3 install tkcalendar
    
elif [ -f /etc/arch-release ]; then
    # Arch-based system
    echo "Arch-based system detected."
    
    # Update package list and install packages
    sudo pacman -Syu --noconfirm python python-pip tk
    
    # Install tkcalendar
    pip install tkcalendar
    
else
    echo "Unsupported operating system."
    exit 1
fi

echo "Installation complete."
