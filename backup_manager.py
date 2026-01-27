import os
import zipfile
from datetime import datetime

def get_data_files(base_dir):
    """Returns a list of essential data files used by the application."""
    return [
        os.path.join(base_dir, "productos.csv"),
        os.path.join(base_dir, "ventas.csv"),
        os.path.join(base_dir, "flujo_caja.csv"),
        os.path.join(base_dir, "settings.json"),
        os.path.join(base_dir, ".credentials")
    ]

def create_backup(base_dir, dest_path):
    """Creates a ZIP backup of all data files."""
    files = get_data_files(base_dir)
    try:
        with zipfile.ZipFile(dest_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file in files:
                if os.path.exists(file):
                    zipf.write(file, os.path.basename(file))
        return True, "Respaldo creado exitosamente."
    except Exception as e:
        return False, f"Error al crear respaldo: {e}"

def restore_backup(base_dir, src_path):
    """Restores data files from a ZIP backup."""
    try:
        if not zipfile.is_zipfile(src_path):
            return False, "El archivo seleccionado no es un respaldo válido."

        with zipfile.ZipFile(src_path, 'r') as zipf:
            # Check if it contains our expected files
            namelist = zipf.namelist()
            essential = ["productos.csv", "settings.json"]
            if not any(f in namelist for f in essential):
                 return False, "El respaldo parece estar incompleto o no es compatible."

            zipf.extractall(base_dir)
        return True, "Respaldo restaurado exitosamente. Reinicie la aplicación para ver los cambios."
    except Exception as e:
        return False, f"Error al restaurar respaldo: {e}"
