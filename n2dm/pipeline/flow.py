#!/usr/bin/env python3
"""
n2dm.pipeline.flow — FlowMapper (OpenAI JSON-mode)

Строит список потоков [{from,to,type}] между доменами.
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


class FlowMapper(BaseStep):
    name = "FlowMapper"

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
        domains = list(data.get("domains", {}).keys())
        if not domains:
            raise ValueError("FlowMapper требует domains")

        if self._online:
            try:
                prompt = (
                    "Построй список потоков между доменами, формат "
                    '[{"from":"..","to":"..","type":"R"}]. '
                    f"Домены: {domains}"
                )
                resp = self._client.chat.completions.create(
                    model=self._model,
                    timeout=self._timeout,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": "Ты архитектор потоков."},
                        {"role": "user", "content": prompt},
                    ],
                )
                flows: List[Dict[str, str]] = json.loads(resp.choices[0].message.content)
            except Exception as exc:
                logger.error("OpenAI error (%s), fallback", exc.__class__.__name__)
                flows = self._stub(domains)
        else:
            flows = self._stub(domains)

        data["flows"] = flows
        return {"name": self.name, "payload": {"flows": flows}}

    @staticmethod
    def _stub(domains: list[str]) -> List[Dict[str, str]]:
        if len(domains) < 2:
            return []
        return [{"from": domains[i], "to": domains[i + 1], "type": "R"} for i in range(len(domains) - 1)]
