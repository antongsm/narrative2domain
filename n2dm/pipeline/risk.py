#!/usr/bin/env python3
"""
n2dm.pipeline.risk — RiskAnnotator (OpenAI JSON-mode)

Добавляет потенциальные риски (строки) к модели.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

from n2dm.config import load_config
from n2dm.pipeline.base import BaseStep, StepResult

logger = logging.getLogger(__name__)

try:
    from openai import OpenAI
except ModuleNotFoundError:
    OpenAI = None  # type: ignore


class RiskAnnotator(BaseStep):
    name = "RiskAnnotator"

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
            logger.warning("%s stub-режим (нет OpenAI / API-key)", self.name)

    async def run(self, data: Dict[str, Any]) -> StepResult:
        if self._online:
            try:
                prompt = (
                    "Перечисли главные риски (3-5) для процесса из текста. "
                    "Верни JSON-массив строк без описаний."
                )
                resp = self._client.chat.completions.create(
                    model=self._model,
                    timeout=self._timeout,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": "Ты инженер по рискам."},
                        {"role": "user", "content": prompt + "\n\n" + data.get("raw_text", "")},
                    ],
                )
                risks: List[str] = json.loads(resp.choices[0].message.content)
            except Exception as exc:
                logger.error("OpenAI error (%s), fallback", exc.__class__.__name__)
                risks = ["Сетевой тайм-аут", "Ошибочный ввод"]
        else:
            risks = ["Сетевой тайм-аут", "Ошибочный ввод"]

        data["risks"] = risks
        return {"name": self.name, "payload": {"risks": risks}}
