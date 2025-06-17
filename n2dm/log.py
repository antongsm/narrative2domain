"""
n2dm.log — настройка логгера для Narrative2DomainModel

Используется как в CLI, так и в GUI:
- Единый стиль сообщений
- Возможность логировать в файл
- Уровни: DEBUG / INFO / WARNING / ERROR
"""

import logging
from pathlib import Path
from typing import Optional

DEFAULT_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s — %(message)s"
DEFAULT_DATE_FORMAT = "%H:%M:%S"


def init_logging(level: int = logging.INFO, log_file: Optional[Path] = None) -> None:
    """
    Инициализирует логирование:
    - в консоль (stdout)
    - (опционально) в файл
    """
    handlers = [logging.StreamHandler()]
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file, mode="w", encoding="utf-8"))

    logging.basicConfig(
        level=level,
        format=DEFAULT_LOG_FORMAT,
        datefmt=DEFAULT_DATE_FORMAT,
        handlers=handlers,
    )
