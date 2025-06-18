#!/usr/bin/env python3
"""
n2dm.pipeline.glossary — GlossaryBuilder (OpenAI JSON-mode)
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
except ModuleNotFoundError:
    OpenAI = None  # type: ignore


class GlossaryBuilder(BaseStep):
    name = "GlossaryBuilder"

    def __init__(self) -> None:
        cfg = load_config()["openai"]
        self._api_key = cfg.get("api_key", "")
        self._model = cfg.get("model", "gpt-4o")
        self._timeout = cfg.get("timeout", 60)

        if OpenAI and self._api_key:
            self._client = OpenAI(api_key=self._api_key)
            self._online = True
        else:
            self._client = None
            self._online = False
            logger.warning("%s stub-режим (нет OpenAI / API-key)", self.name)

    async def run(self, data: Dict[str, Any]) -> StepResult:  # noqa: D401
        text: str = data.get("raw_text") or Path(data["input_path"]).read_text("utf-8")

        if self._online:
            try:
                prompt = (
                    "Составь глоссарий терминов из текста. "
                    "Верни JSON-массив строк без описаний.\n\n" + text
                )
                resp = self._client.chat.completions.create(
                    model=self._model,
                    timeout=self._timeout,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": "Ты извлекаешь ключевые термины."},
                        {"role": "user", "content": prompt},
                    ],
                )
                terms: List[str] = json.loads(resp.choices[0].message.content)
            except Exception as exc:
                logger.error("OpenAI error (%s), fallback", exc.__class__.__name__)
                terms = self._stub()
        else:
            terms = self._stub()

        data["glossary"] = terms
        return {"name": self.name, "payload": {"glossary": terms}}

    @staticmethod
    def _stub() -> List[str]:
        return ["Система", "Пользователь", "Процесс"]
