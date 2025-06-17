#!/usr/bin/env python3
"""n2dm.config — загрузка и сохранение пользовательских настроек

• Читает ~/.n2dm/config.toml (TOML‑формат)
• Гарантирует наличие всех ключей из DEFAULTS
• Поддерживает переопределение API‑ключа переменной окружения OPENAI_API_KEY
• Кроссплатформенная установка прав (0700 только на POSIX)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict

import tomllib  # stdlib (Python 3.11+)

# ---------------------------------------------------------------------------
# Константы и значения по умолчанию                                          
# ---------------------------------------------------------------------------
CONFIG_DIR: Path = Path.home() / ".n2dm"
CONFIG_FILE: Path = CONFIG_DIR / "config.toml"

DEFAULTS: Dict[str, Any] = {
    "openai": {
        "api_key": "",  # переопределяется ENV OPENAI_API_KEY
        "model": "gpt-4o-mini",
        "timeout": 60,
        "max_tokens": 48_000,
    }
}


# ---------------------------------------------------------------------------
# TOML сериализация (пишем файл)                                             
# ---------------------------------------------------------------------------
try:
    # tomli_w является "братом" tomllib для записи TOML
    import tomli_w  # type: ignore

    def _dumps_toml(obj: dict) -> str:  # noqa: D401
        return tomli_w.dumps(obj)

except ModuleNotFoundError:  # минимальная реализация без внешних зависимостей

    def _fmt(val: Any) -> str:  # noqa: D401
        if isinstance(val, str):
            escaped = val.replace("\\", "\\\\").replace("\"", "\\\"")
            return f'"{escaped}"'
        return str(val).lower() if isinstance(val, bool) else str(val)

    def _dumps_toml(obj: dict) -> str:  # noqa: D401
        lines: list[str] = []
        for section, params in obj.items():
            lines.append(f"[{section}]")
            for key, val in params.items():
                lines.append(f"{key} = {_fmt(val)}")
            lines.append("")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Основные функции                                                           
# ---------------------------------------------------------------------------

def load_config() -> dict:  # noqa: D401
    """Читает конфиг с диска, сливает с DEFAULTS и применяет ENV‑переопределения."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    # На POSIX‑системах делаем директорию приватной
    if os.name == "posix":
        try:
            os.chmod(CONFIG_DIR, 0o700)
        except PermissionError:  # может случиться, если нет прав
            pass

    cfg: Dict[str, Any]
    if CONFIG_FILE.exists():
        with CONFIG_FILE.open("rb") as f:
            cfg = tomllib.load(f)
    else:
        cfg = {}

    # Слияние с DEFAULTS (copy → update)
    merged: Dict[str, Any] = {}
    for section, defaults in DEFAULTS.items():
        section_data = defaults.copy()
        section_data.update(cfg.get(section, {}))
        merged[section] = section_data

    # ENV override: OPENAI_API_KEY
    if (env_key := os.getenv("OPENAI_API_KEY")):
        merged.setdefault("openai", {})["api_key"] = env_key

    return merged


def save_config(cfg: dict) -> None:  # noqa: D401
    """Сохраняет конфиг в TOML‑файл (надёжно экранируя строки)."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if os.name == "posix":
        try:
            os.chmod(CONFIG_DIR, 0o700)
        except PermissionError:
            pass

    toml_text = _dumps_toml(cfg)
    with CONFIG_FILE.open("w", encoding="utf-8") as f:
        f.write(toml_text)


# ---------------------------------------------------------------------------
# CLI helper (debug)                                                         
# ---------------------------------------------------------------------------
if __name__ == "__main__":  # pragma: no cover
    import pprint

    pprint.pp(load_config())