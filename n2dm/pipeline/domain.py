# n2dm/pipeline/domain.py
"""LLM-stage: группировка сущностей и связей по доменам.

* Требование к ключам доменов: **РОВНО три русских смысловых слова, заглавными,
  через подчёркивание**. Предлоги/союзы исключаем.
* Используем `response_format={"type": "json_object"}` для строгого JSON.
* Повторяем запрос до `max_retries`, если ответ не парсится.
* Возвращаем `StepResult` вида `{name, payload}`.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, Optional

from openai import OpenAI

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

# ---------------------------------------------------------------------------
# Конфигурация и константы
# ---------------------------------------------------------------------------
try:
    from n2dm.config import OPENAI_API_KEY
except ImportError:
    OPENAI_API_KEY: Optional[str] = None  # type: ignore

DEFAULT_MODEL = "gpt-4o-mini"

DEFAULT_PROMPT_STAGE_1 = (
    "Разбейте следующий текст на логические блоки. Верните строго валидный JSON\n"
    "{\n  \"chunks\": [ {\"id\": str, \"text\": str } ... ]\n}"
)

DEFAULT_PROMPT_STAGE_2 = """
Используя результат первого этапа (`chunks`), сформируйте структуру доменов.
Ключи доменов ДОЛЖНЫ быть на русском языке, состоять РОВНО из трёх смысловых
слов (без предлогов и союзов), соединённых символом подчёркивания (`_`) и
написаны ЗАГЛАВНЫМИ буквами.

Дополнительные требования:
• Не используйте слова: В, НА, С, И, К, ДЛЯ и т.п.
• Если слов больше трёх, сократите или удалите лишние, чтобы осталось ровно три.
• Пример верного ключа: КТО_СОВЕРШАЕТ_КАК.
• Пример неверного: ЧТО_ПРОИСХОДИТ_В_КОНФЛИКТЕ (четыре слова).

Верните строго валидный JSON:
{
  "domains": {<KEY>: {...}, ...},
  "flows": [...],
  "risks": {...}
}
"""

_JSON_RE = re.compile(r"\{.*\}", re.S)

# ---------------------------------------------------------------------------
class DomainGrouper:
    name: str = "Группировка по доменам (LLM)"

    def __init__(
        self,
        client: Optional[OpenAI] = None,
        model: str = DEFAULT_MODEL,
        prompt_stage_1: str = DEFAULT_PROMPT_STAGE_1,
        prompt_stage_2: str = DEFAULT_PROMPT_STAGE_2,
        max_retries: int = 2,
    ) -> None:
        self.client = client or OpenAI(api_key=OPENAI_API_KEY)
        self.model = model
        self.prompt_stage_1 = prompt_stage_1
        self.prompt_stage_2 = prompt_stage_2
        self.max_retries = max_retries

    # ---------------------------------------------------------------------
    def _call_llm(self, *, prompt: str, content: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": content},
            ],
            temperature=0.0,
        )
        return response.choices[0].message.content or ""

    # ---------------------------------------------------------------------
    @staticmethod
    def _parse_json(raw: str) -> Dict[str, Any] | None:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            match = _JSON_RE.search(raw)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    return None
            return None

    # ---------------------------------------------------------------------
    def _run_sync(self, data: Dict[str, Any]) -> Dict[str, Any]:
        # Получаем исходный текст
        text: str = (
            data.get("raw_text")
            or data.get("text")
            or Path(data["input_path"]).read_text("utf-8")
            if "input_path" in data else ""
        )
        logger.info("[CHECK] Передано в stage1: %d символов", len(text))
        if not text:
            raise ValueError("Исходный текст не найден")

        # Stage 1
        parsed1: Dict[str, Any] | None = None
        for attempt in range(self.max_retries + 1):
            raw1 = self._call_llm(prompt=self.prompt_stage_1, content=text)
            parsed1 = self._parse_json(raw1)
            if parsed1:
                break
            logger.warning("Stage 1: invalid JSON, retry %d/%d", attempt + 1, self.max_retries)
        if not parsed1:
            raise ValueError("Stage 1: не удалось получить валидный JSON")

        # Stage 2
        parsed2: Dict[str, Any] | None = None
        stage1_payload = json.dumps(parsed1, ensure_ascii=False)
        for attempt in range(self.max_retries + 1):
            raw2 = self._call_llm(prompt=self.prompt_stage_2, content=stage1_payload)
            parsed2 = self._parse_json(raw2)
            if parsed2:
                break
            logger.warning("Stage 2: invalid JSON, retry %d/%d", attempt + 1, self.max_retries)
        if not parsed2:
            raise ValueError("Stage 2: не удалось получить валидный JSON")

        payload = {
            "domains": parsed2.get("domains", {}),
            "flows": parsed2.get("flows", []),
            "risks": parsed2.get("risks", {}),
        }
        data.update(payload)
        return {"name": self.name, "payload": payload}

    # ---------------------------------------------------------------------
    async def run(self, data: Dict[str, Any]) -> Dict[str, Any]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._run_sync, data)

    # ---------------------------------------------------------------------
    def extract(self, text: str | Path) -> Dict[str, Any]:
        if isinstance(text, Path):
            text = text.read_text("utf-8")
        return asyncio.run(self.run({"raw_text": text}))

__all__ = ["DomainGrouper"]