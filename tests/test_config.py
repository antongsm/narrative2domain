"""
tests/test_config.py — проверки модуля n2dm.config
"""

import os
import tomllib
from pathlib import Path

import pytest

from n2dm import config as cfg_mod


def test_defaults_merge(tmp_path, monkeypatch):
    """
    Если конфиг пока не существует, load_config()
    должен вернуть словарь, включающий все DEFAULTS.
    """
    # Подменяем $HOME, чтобы не трогать реальные файлы.
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))

    cfg = cfg_mod.load_config()

    # Все секции и ключи из DEFAULTS присутствуют
    for section, params in cfg_mod.DEFAULTS.items():
        assert section in cfg
        for key in params:
            assert key in cfg[section]


def test_save_and_reload(tmp_path, monkeypatch):
    """
    save_config() создает ~/.n2dm/config.toml, а load_config() потом его читает.
    """
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))

    # Подготовим конфиг с кастомным API-ключом
    my_cfg = cfg_mod.DEFAULTS.copy()
    my_cfg["openai"] = my_cfg["openai"].copy()
    my_cfg["openai"]["api_key"] = "sk-test-123"

    # Сохраняем
    cfg_mod.save_config(my_cfg)

    # Проверяем, что файл реально создан
    stored_file = fake_home / ".n2dm" / "config.toml"
    assert stored_file.exists()

    # Читаем напрямую TOML и сверяем
    raw = tomllib.loads(stored_file.read_text(encoding="utf-8"))
    assert raw["openai"]["api_key"] == "sk-test-123"

    # Перезагружаем через load_config()
    loaded = cfg_mod.load_config()
    assert loaded["openai"]["api_key"] == "sk-test-123"


@pytest.mark.parametrize(
    "bad_perm",
    [0o777, 0o755, 0o644],
)
def test_directory_permissions(tmp_path, monkeypatch, bad_perm):
    """
    save_config() обязан установить права ~/.n2dm = 700,
    даже если папка изначально создана с другими правами.
    """
    fake_home = tmp_path / "home"
    cfg_dir = fake_home / ".n2dm"
    cfg_dir.mkdir(parents=True)
    cfg_dir.chmod(bad_perm)

    monkeypatch.setenv("HOME", str(fake_home))

    cfg_mod.save_config(cfg_mod.DEFAULTS)
    assert oct(cfg_dir.stat().st_mode & 0o777) == "0o700"
