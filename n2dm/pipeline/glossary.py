#!/usr/bin/env python3
"""n2dm.pipeline.glossary — GlossaryBuilder (OpenAI + JSON)

Извлекает ключевые понятия (глоссарий) из входного текста.
Работает в двух режимах:
  • Full — с использованием OpenAI API (если пакет `openai` установлен и есть API‑ключ).
  • Stub — офлайн‑заглушка, возвращает фиксированный перечень терминов.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, List

from n2dm.pipeline.base import BaseStep, StepResult
from n2dm.config import load_config

logger = logging.getLogger(__name__)

# --- optional dependency ----------------------------------------------------
try:
    from openai import OpenAI  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    OpenAI = None  # type: ignore
    logger.warning("openai package not installed — GlossaryBuilder runs in stub mode")


class GlossaryBuilder(BaseStep):
    """Шаг 1: формирование списка терминов."""

    name = "GlossaryBuilder"

    def __init__(self) -> None:  # noqa: D401
        self._client = None
        cfg = load_config().get("openai", {})
        key = cfg.get("api_key", "").strip()
        if OpenAI is not None and key:
            self._client = OpenAI(api_key=key)
            self._model = cfg.get("model", "gpt-4o-mini")
            self._timeout = cfg.get("timeout", 60)
        else:
            logger.info("GlossaryBuilder will use stub output (no OpenAI)")

    # ---------------------------------------------------------------------
    async def run(self, data: dict[str, Any]) -> StepResult:  # noqa: D401
        path = data.get("input_path")
        if not path or not str(path).endswith(".txt"):
            raise ValueError("GlossaryBuilder поддерживает только текстовые .txt входы")

        text = Path(path).read_text(encoding="utf-8")

        if self._client is None:
            # ------------------ Stub mode ------------------
            terms: List[str] = ["Система", "Пользователь", "Процесс"]
            logger.debug("Stub glossary returned: %s", terms)
        else:
            prompt = (
                "Составь глоссарий терминов из текста. Верни JSON‑массив строк без описаний.\n\n"
                f"Текст:\n{text}"
            )
            try:
                resp = self._client.chat.completions.create(
                    model=self._model,
                    response_format="json",
                    timeout=self._timeout,
                    messages=[
                        {"role": "system", "content": "Ты извлекаешь ключевые термины."},
                        {"role": "user", "content": prompt},
                    ],
                )
                raw = resp.choices[0].message.content
                terms = json.loads(raw)
                if not isinstance(terms, list):  # sanity check
                    raise ValueError("Модель вернула объект неверного типа, ожидался список")
            except Exception as exc:  # noqa: BLE001
                logger.exception("OpenAI call failed, fallback to stub glossary")
                terms = ["Система", "Пользователь", "Процесс"]

        # сохранение
        data["glossary"] = terms
        return {"name": self.name, "payload": {"glossary": terms}}
