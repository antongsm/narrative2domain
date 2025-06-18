#!/usr/bin/env python3
"""n2dm.config — загрузка/сохранение настроек

Правки после unit‑tests:
• CONFIG_DIR больше не кешируется при импорте, чтобы monkeypatch HOME
  внутри тестов корректно менял путь.
• Функции `config_dir()` и `config_file()` вычисляют путь динамически.
• save_config(): на POSIX гарантирует chmod 700 для каталога.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

# ---------------------------------------------------------------------------
# Константы по умолчанию
# ---------------------------------------------------------------------------

DEFAULTS: Dict[str, Any] = {
    "openai": {
        "api_key": "",
        "model": "gpt-4o-mini",
        "timeout": 60,
        "max_tokens": 48000,
    }
}

# ---------------------------------------------------------------------------
# Вспомогательные функции путей (динамические)
# ---------------------------------------------------------------------------

def config_dir() -> Path:
    """Возвращает путь к каталогу ~/.n2dm, вычисляя его каждый вызов."""
    return Path.home() / ".n2dm"

def config_file() -> Path:
    return config_dir() / "config.toml"

# ---------------------------------------------------------------------------
# TOML helpers
# ---------------------------------------------------------------------------
try:
    import tomli_w  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    tomli_w = None  # noqa: N816

import tomllib  # stdlib (read‑only)

def _toml_dump(data: dict) -> str:
    if tomli_w:
        return tomli_w.dumps(data)
    # fallback‑минималист
    return json.dumps(data, ensure_ascii=False, indent=2)

# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

def load_config() -> dict:
    """Читает конфиг, дополняет DEFAULTS."""
    cfg: Dict[str, Any] = {}
    cfile = config_file()
    if cfile.exists():
        cfg = tomllib.loads(cfile.read_text("utf-8"))
    # merge
    out: Dict[str, Any] = {}
    for section, defaults in DEFAULTS.items():
        out[section] = defaults.copy()
        out[section].update(cfg.get(section, {}))
    # override из переменной окружения
    env_key = os.getenv("OPENAI_API_KEY")
    if env_key:
        out.setdefault("openai", {})["api_key"] = env_key
    return out

def save_config(cfg: dict) -> None:
    """Сохраняет словарь cfg в ~/.n2dm/config.toml"""
    cdir = config_dir()
    cdir.mkdir(parents=True, exist_ok=True)
    if os.name == "posix":
        os.chmod(cdir, 0o700)
    cfile = config_file()
    cfile.write_text(_toml_dump(cfg), encoding="utf-8")