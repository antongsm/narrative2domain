#!/usr/bin/env python3
"""
GUI-точка входа Narrative2DomainModel
------------------------------------

Запускает графический интерфейс (PySide6).  Если PySide6 отсутствует,
сообщает пользователю, как установить пакет.

▪ Загружает ~/.n2dm/config.toml
▪ Настраивает централизованный логгер
▪ Создаёт и показывает окно MainWindow (см. n2dm/gui_main.py)
"""

from __future__ import annotations

import sys

# --------------------------------------------------------- PySide6 (soft-dep)
try:
    from PySide6.QtWidgets import QApplication
except ModuleNotFoundError:  # PySide6 не установлен
    print(
        "\n❌  PySide6 не найден.\n"
        "   Установите его командой:\n"
        "   pip install PySide6\n"
        "или используйте CLI-режим:\n"
        "   python -m n2dm.cli <input.txt>\n"
    )
    sys.exit(1)

# --------------------------------------------------------- наши модули
from n2dm.config import load_config
from n2dm.log import init_logging

try:
    from n2dm.gui_main import MainWindow  # основной UI-класс вынесен в gui_main.py
except ModuleNotFoundError:
    print(
        "\n❌  n2dm.gui_main не найден.\n"
        "   Убедитесь, что файл n2dm/gui_main.py существует и содержит класс MainWindow.\n"
    )
    sys.exit(1)


def main() -> None:
    """Точка входа для `python -m n2dm.gui`."""
    # 1. Логирование
    init_logging()

    # 2. Конфиг
    cfg = load_config()

    # 3. Qt-приложение
    app = QApplication(sys.argv)
    win = MainWindow(cfg)
    win.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
