#!/usr/bin/env python3
"""n2dm.cli — командная строка Narrative2DomainModel

Запуск конвейера из терминала без GUI.

Пример:
    python -m n2dm.cli requirements.txt -v

Параметры:
    input_path            Путь к .txt или .mp3 (транскрипция пока не реализована)
    -o, --outdir PATH     Папка для выходных файлов (по умолчанию текущая)
    -v, --verbose         Показать финальный словарь data в stdout
    --debug               Уровень логирования DEBUG
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

from n2dm.config import load_config
from n2dm.log import init_logging
from n2dm.pipeline import ALL_STEPS, BaseStep

__all__ = ["main"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="n2dm.cli", description="Запуск конвейера Narrative2DomainModel")
    parser.add_argument("input_path", type=Path, help="Путь к .txt или .mp3 файлу")
    parser.add_argument("-o", "--outdir", type=Path, default=Path.cwd(), help="Выходная директория")
    parser.add_argument("-v", "--verbose", action="store_true", help="Показать итоговый data словарь")
    parser.add_argument("--debug", action="store_true", help="Логирование DEBUG")
    return parser.parse_args()


async def run_pipeline(input_path: Path, out_dir: Path, steps: list[BaseStep]) -> dict[str, Any]:
    data: dict[str, Any] = {"input_path": str(input_path)}
    total = len(steps)

    print(f"🔄 Обработка: {input_path.name}\n")
    for idx, step in enumerate(steps, start=1):
        print(f"▶ ({idx}/{total}) {step.name}…", end=" ")
        result = await step.run(data)
        data[step.name] = result["payload"]
        print("✅")

    # Перемещаем артефакты, если out_dir не текущий
    if out_dir != Path.cwd():
        for fname in ("domain_model.json", "process.bpmn", "diagram.svg", "report.md"):
            src = Path.cwd() / fname
            if src.exists():
                src.replace(out_dir / fname)

    print("\n🎉 Обработка завершена.")
    return data


def main() -> None:  # noqa: D401
    args = parse_args()
    level = logging.DEBUG if args.debug else logging.INFO
    init_logging(level=level)

    # Проверка входного файла
    if not args.input_path.exists():
        print("❌ Файл не найден:", args.input_path)
        sys.exit(1)

    cfg = load_config()
    if not cfg["openai"]["api_key"]:
        logging.warning("API‑key OpenAI пуст — шаги, использующие LLM, могут упасть")

    try:
        result = asyncio.run(run_pipeline(args.input_path, args.outdir, ALL_STEPS))
    except Exception as exc:  # noqa: BLE001
        logging.exception("Pipeline failed")
        sys.exit(2)

    if args.verbose:
        print("\n📦 Итоговый data словарь:\n")
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":  # pragma: no cover
    main()
