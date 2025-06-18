#!/usr/bin/env python3
"""
n2dm.pipeline.domain — DomainGrouper (OpenAI JSON-mode)

Группирует действия по логическим доменам.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict

from n2dm.config import load_config
from n2dm.pipeline.base import BaseStep, StepResult

logger = logging.getLogger(__name__)

try:
    from openai import OpenAI
except ModuleNotFoundError:
    OpenAI = None  # type: ignore


class DomainGrouper(BaseStep):
    name = "DomainGrouper"

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
        actions = data.get("actions", [])
        if not actions:
            raise ValueError("DomainGrouper требует actions")

        if self._online:
            try:
                prompt = (
                    "Распредели действия по доменам. Верни JSON-объект: ключ — домен, "
                    "значение — список action-объектов.\n"
                    f"Actions:\n{json.dumps(actions, ensure_ascii=False)}"
                )
                resp = self._client.chat.completions.create(
                    model=self._model,
                    timeout=self._timeout,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": "Ты технический архитектор."},
                        {"role": "user", "content": prompt},
                    ],
                )
                domains = json.loads(resp.choices[0].message.content)
            except Exception as exc:
                logger.error("OpenAI error (%s), fallback", exc.__class__.__name__)
                domains = self._stub(actions)
        else:
            domains = self._stub(actions)

        data["domains"] = domains
        return {"name": self.name, "payload": {"domains": domains}}

    @staticmethod
    def _stub(actions: list[dict]) -> Dict[str, list]:
        split = max(1, len(actions) // 2)
        return {"UI": actions[:split], "Backend": actions[split:]}
