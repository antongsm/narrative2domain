#!/usr/bin/env python3
"""n2dm.pipeline.action — ActionExtractor (OpenAI + безопасный JSON)

Извлекает атомарные действия из пользовательского текста.
Если библиотека `openai` или API‑ключ отсутствуют, работает в режиме
заглушки (возвращает фиксированный набор действий).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, List, Dict, TypedDict

from n2dm.config import load_config
from n2dm.pipeline.base import BaseStep, StepResult

logger = logging.getLogger(__name__)

try:
    from openai import OpenAI  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    OpenAI = None  # type: ignore
    logger.warning("openai package not installed — ActionExtractor works in stub mode")


class Action(TypedDict):
    actor: str
    action: str


class ActionExtractor(BaseStep):
    name = "ActionExtractor"

    def __init__(self) -> None:  # noqa: D401
        cfg = load_config()["openai"]
        self._api_key: str = cfg.get("api_key", "")
        self._model: str = cfg.get("model", "gpt-4o-mini")
        self._timeout: int = cfg.get("timeout", 60)

        if OpenAI and self._api_key:
            self._client = OpenAI(api_key=self._api_key)
        else:
            self._client = None  # заглушка
            logger.info("ActionExtractor: using stub; set OPENAI_API_KEY to enable real extraction")

    async def run(self, data: Dict[str, Any]) -> StepResult:  # noqa: D401
        """Извлекает действия из .txt файла; fallback‑режим без OpenAI — статичный список."""
        path = Path(data.get("input_path", ""))
        if not path.exists() or path.suffix.lower() != ".txt":
            raise ValueError("ActionExtractor поддерживает только текстовые файлы .txt")

        text = path.read_text(encoding="utf-8")

        # --- режим без OpenAI ------------------------------------------------
        if self._client is None:
            stub: List[Action] = [
                {"actor": "Пользователь", "action": "загружает файл"},
                {"actor": "Система", "action": "генерирует модель"},
            ]
            data["actions"] = stub
            return {"name": self.name, "payload": {"actions": stub}}

        # --- запрос к GPT ----------------------------------------------------
        system_prompt = (
            "Ты инструмент, извлекающий атомарные действия из пользовательского текста. "
            "Верни JSON‑массив объектов вида {\"actor\": <кто>, \"action\": <что делает>}"
        )

        user_prompt = (
            "Извлеки все действия из текста ниже. Не описывай, не объясняй. "
            "Верни только JSON‑массив.\n\n" + text
        )

        response = self._client.chat.completions.create(
            model=self._model,
            response_format="json",
            timeout=self._timeout,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )

        # content может быть str (json‑строка) или уже list
        raw = response.choices[0].message.content
        try:
            actions: List[Action] = json.loads(raw) if isinstance(raw, str) else raw  # type: ignore[arg-type]
        except json.JSONDecodeError:
            logger.error("OpenAI вернул некорректный JSON; fallback to stub")
            actions = [{"actor": "LLM", "action": "не смог разобрать JSON"}]

        data["actions"] = actions
        return {"name": self.name, "payload": {"actions": actions}}
