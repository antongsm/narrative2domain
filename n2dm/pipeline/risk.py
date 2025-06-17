#!/usr/bin/env python3
"""n2dm.pipeline.risk — RiskAnnotator (OpenAI + JSON)

Определяет потенциальные риски, сбои и точки отказа на основе входного текста
и извлечённых действий.

*Full‑mode*: GPT возвращает JSON‑массив строк‑рисков.
*Stub‑mode*: выдаёт фиксированный набор рисков, чтобы пайплайн работал офлайн.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

from n2dm.config import load_config
from n2dm.pipeline.base import BaseStep, StepResult

try:
    from openai import OpenAI  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    OpenAI = None  # noqa: N816

logger = logging.getLogger(__name__)


class RiskAnnotator(BaseStep):
    """Шаг конвейера: анализирует риски/точки отказа."""

    name = "RiskAnnotator"

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
            logger.warning("RiskAnnotator работает в stub‑режиме (нет OpenAI / API‑ключа)")

    # ------------------------------------------------------------------
    async def run(self, data: Dict[str, Any]) -> StepResult:  # noqa: D401
        path = data.get("input_path")
        actions = data.get("actions")
        if not path or not actions:
            raise ValueError("RiskAnnotator требует 'input_path' и 'actions' в data")

        text = Path(path).read_text(encoding="utf-8") if Path(path).suffix == ".txt" else ""

        if self.client:  # online‑mode
            prompt = (
                "Определи потенциальные риски, ошибки, точки отказа для описанной системы. "
                "Верни STRICT JSON‑массив строк.\n\n"  # noqa: RUF001
                f"Текст:\n{text}\n\n"
                f"Действия:\n{json.dumps(actions, ensure_ascii=False)}"
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
                                "Ты инженер по надёжности. На основе текста и действий формируешь список рисков."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                )
                risks_raw = resp.choices[0].message.content
                risks: List[str] = json.loads(risks_raw)  # type: ignore[arg-type]
            except Exception as exc:  # noqa: BLE001
                logger.error("GPT вызов не удался (%s) — fallback stub", exc)
                risks = self._stub_risks()
        else:  # offline‑stub
            risks = self._stub_risks()

        data["risks"] = risks
        return {"name": self.name, "payload": {"risks": risks}}

    # ------------------------------------------------------------------
    @staticmethod
    def _stub_risks() -> List[str]:
        """Возвращает фиксированный набор рисков для офлайн‑режима."""
        return [
            "Повреждённый входной файл",
            "Сетевой тайм‑аут при запросе к OpenAI",
            "Неверный формат данных",
        ]
