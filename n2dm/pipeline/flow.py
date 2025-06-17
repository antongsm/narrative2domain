#!/usr/bin/env python3
"""n2dm.pipeline.flow — FlowMapper (OpenAI + JSON)

Строит список потоков взаимодействия между доменами.

*Full‑mode*: GPT анализирует действия/домены и возвращает список вида
[{"from": "UI", "to": "Backend", "type": "R"}, ...]

*Stub‑mode*: если пакет `openai` или API‑ключ недоступны — формирует
простую цепочку доменов (UI → Backend → Storage …), чтобы пайплайн
оставался рабочим офлайн.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

from n2dm.config import load_config
from n2dm.pipeline.base import BaseStep, StepResult

try:
    from openai import OpenAI  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    OpenAI = None  # noqa: N816

logger = logging.getLogger(__name__)


class FlowMapper(BaseStep):
    """Шаг конвейера: строит граф потоков между доменами."""

    name = "FlowMapper"

    def __init__(self) -> None:  # noqa: D401
        cfg = load_config()["openai"]
        self.api_key: str = cfg.get("api_key", "")
        self.model: str = cfg.get("model", "gpt-4o-mini")
        self.timeout: int = cfg.get("timeout", 60)

        self.client = None
        if OpenAI and self.api_key:
            try:
                self.client = OpenAI(api_key=self.api_key)
            except Exception as exc:  # noqa: BLE001
                logger.warning("OpenAI client init failed: %s", exc)
        if not self.client:
            logger.warning("FlowMapper работает в stub‑режиме (нет OpenAI / API‑ключа)")

    # ---------------------------------------------------------------------
    async def run(self, data: Dict[str, Any]) -> StepResult:  # noqa: D401
        actions = data.get("actions")
        domains = data.get("domains")
        if not actions or not domains:
            raise ValueError("FlowMapper требует 'actions' и 'domains' в data")

        if self.client:  # online‑mode
            prompt = (
                "На основе списка действий и группировки по доменам построи JSON‑массив "
                "объектов {\"from\": <домен‑источник>, \"to\": <домен‑получатель>, \"type\": \"R|F|E\"}.\n\n"
                f"Действия:\n{json.dumps(actions, ensure_ascii=False)}\n\n"
                f"Домены:\n{json.dumps(domains, ensure_ascii=False)}"
            )
            try:
                resp = self.client.chat.completions.create(
                    model=self.model,
                    response_format="json",
                    timeout=self.timeout,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "Ты технический архитектор. На основе действий определяешь потоки "
                                "взаимодействия между доменами. Возвращай STRICT JSON."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                )
                flows_raw = resp.choices[0].message.content
                flows: List[Dict[str, str]] = json.loads(flows_raw)  # type: ignore[arg-type]
            except Exception as exc:  # noqa: BLE001
                logger.error("GPT вызов не удался (%s) — fallback stub", exc)
                flows = self._stub_flows(domains)
        else:  # offline‑stub
            flows = self._stub_flows(domains)

        data["flows"] = flows
        return {"name": self.name, "payload": {"flows": flows}}

    # ------------------------------------------------------------------
    @staticmethod
    def _stub_flows(domains: Dict[str, list]) -> List[Dict[str, str]]:
        """Формирует линейную R‑цепочку доменов: A → B → C."""
        dom_list = list(domains.keys())
        if len(dom_list) < 2:
            return []
        return [
            {"from": dom_list[i], "to": dom_list[i + 1], "type": "R"}
            for i in range(len(dom_list) - 1)
        ]
