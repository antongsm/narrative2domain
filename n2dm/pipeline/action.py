#!/usr/bin/env python3
"""
n2dm.pipeline.action — ActionExtractor (OpenAI JSON-mode)

Извлекает атомарные действия из пользовательского текста.
Результат: list[{"actor": str, "action": str}, …]

• Online-режим (есть openai + API-key) — GPT-вызов с response_format={"type":"json_object"}.
• Stub-режим — фиксированный набор действий.
"""

from __future__ import annotations


import json
import logging
from pathlib import Path
from typing import Any, Dict, List

from n2dm.config import load_config
from n2dm.pipeline.base import BaseStep, StepResult

logger = logging.getLogger(__name__)

try:
    from openai import OpenAI
except ModuleNotFoundError:  # пакет не установлен
    OpenAI = None  # type: ignore


class ActionExtractor(BaseStep):
    name = "ActionExtractor"

    def __init__(self) -> None:
        cfg = load_config()["openai"]
        self._api_key = cfg.get("api_key", "")
        self._model = cfg.get("model", "gpt-4o-mini")
        self._timeout = cfg.get("timeout", 60)

        if OpenAI and self._api_key:
            self._client = OpenAI(api_key=self._api_key)
            self._online = True
        else:
            self._client = None
            self._online = False
            logger.warning("%s работает в stub-режиме (нет OpenAI / API-ключа)", self.name)

    async def run(self, data: Dict[str, Any]) -> StepResult:
        text: str = data.get("raw_text") or Path(data["input_path"]).read_text(encoding="utf-8")

        if self._online:
            try:
                prompt = (
                    "Извлеки все атомарные действия вида <кто> совершает <что> из текста ниже.\n"
                    "Верни ТОЛЬКО JSON-массив объектов вида "
                    '{"actor": "...", "action": "..."} без комментариев.\n\n'
                    f"Текст:\n{text}"
                )
                resp = self._client.chat.completions.create(
                    model=self._model,
                    timeout=self._timeout,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": "Ты инструмент: извлекаешь действия."},
                        {"role": "user", "content": prompt},
                    ],
                )
                actions: List[Dict[str, str]] = json.loads(resp.choices[0].message.content)
                logger.info("%s online: %d действий", self.name, len(actions))
            except Exception as exc:  # pragma: no cover
                logger.error("OpenAI error (%s), fallback", exc.__class__.__name__)
                actions = self._stub()
        else:
            actions = self._stub()

        data["actions"] = actions
        return {"name": self.name, "payload": {"actions": actions}}

    @staticmethod
    def _stub() -> List[Dict[str, str]]:
        return [
            {"actor": "Пользователь", "action": "загружает файл"},
            {"actor": "Система", "action": "валидирует данные"},
        ]
