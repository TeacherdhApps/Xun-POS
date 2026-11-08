#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Copia de seguridad automática programada para Xun-POS.
"""

from __future__ import annotations

import os
import shutil
import threading
import time
from datetime import datetime
from pathlib import Path

import config
import store


class AutoBackup:
    """Copia de seguridad automática programada.

    Ejecuta copias de seguridad periódicas de la base de datos SQLite
    y las mantiene rotadas (mantiene las últimas N copias).
    """

    def __init__(self, interval_minutes: int = 60, max_backups: int = 10):
        self.interval_seconds = interval_minutes * 60
        self.max_backups = max_backups
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self.store = store.Store()
        self.backup_dir = config.data_dir() / "backups"
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def start(self) -> None:
        """Inicia el hilo de copia de seguridad automática."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Detiene el hilo de copia de seguridad."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None

    def _run(self) -> None:
        while not self._stop_event.is_set():
            self._stop_event.wait(self.interval_seconds)
            if self._stop_event.is_set():
                break
            self.run_backup()

    def run_backup(self) -> Path | None:
        """Ejecuta una copia de seguridad inmediata."""
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_name = f"auto-backup-{timestamp}.zip"
        backup_path = self.backup_dir / backup_name

        try:
            self.store.export_backup(backup_path)
            self._cleanup_old_backups()
            return backup_path
        except Exception as exc:
            print(f"No se pudo realizar la copia de seguridad automática: {exc}")
            return None

    def _cleanup_old_backups(self) -> None:
        """Mantiene solo las últimas N copias de seguridad."""
        backups = sorted(
            self.backup_dir.glob("auto-backup-*.zip"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for old in backups[self.max_backups :]:
            try:
                old.unlink()
            except OSError:
                pass

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()


# Instancia global para uso en la aplicación
auto_backup = AutoBackup()
