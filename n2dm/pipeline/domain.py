#!/usr/bin/env python3
"""n2dm.pipeline.domain — DomainGrouper (OpenAI + JSON)

Группирует действия по логическим доменам (модулям/слоям).

• Если доступен пакет `openai` и задан API‑ключ — вызывает GPT (response_format="json").
• При отсутствии — работает в offline‑stub режиме, распределяя действия по двум доменам "UI" и "Backend".
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

from n2dm.config import load_config
from n2dm.pipeline.base import BaseStep, StepResult

logger = logging.getLogger(__name__)

# Try to import OpenAI client -------------------------------------------------
try:
    from openai import OpenAI  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    OpenAI = None  # type: ignore
    logger.warning("openai package not installed — DomainGrouper runs in stub mode")


class DomainGrouper(BaseStep):
    name = "DomainGrouper"

    def __init__(self) -> None:  # noqa: D401
        cfg = load_config().get("openai", {})
        self.api_key: str = cfg.get("api_key", "")
        self.model: str = cfg.get("model", "gpt-4o-mini")
        self.timeout: int = cfg.get("timeout", 60)
        self._client = None
        if OpenAI and self.api_key:
            try:
                self._client = OpenAI(api_key=self.api_key)
            except Exception as exc:  # noqa: BLE001
                logger.warning("OpenAI client init failed → stub mode (%s)", exc)
                self._client = None
        else:
            self._client = None  # stub

    # ---------------------------------------------------------------------
    async def run(self, data: Dict[str, Any]) -> StepResult:  # noqa: D401
        actions: List[Dict[str, str]] = data.get("actions", [])
        if not actions:
            raise ValueError("DomainGrouper требует предварительного шага ActionExtractor")

        if not self._client:  # --------- Stub branch -------------------
            ui, backend = [], []
            for act in actions:
                (ui if act["actor"].lower().startswith("польз") else backend).append(act)
            domains = {"UI": ui, "Backend": backend}
            logger.info("DomainGrouper stub produced %d domains", len(domains))
        else:  # --------- OpenAI branch --------------------------------
            prompt = (
                "Разбей следующий JSON‑список действий по логическим доменам (UI, Backend, DB, и т.д.) "
                "и верни объект JSON {\"DomainName\": [ ...actions... ], ...}.\n\n"
                f"Список действий:\n{json.dumps(actions, ensure_ascii=False, indent=2)}"
            )
            try:
                resp = self._client.chat.completions.create(
                    model=self.model,
                    response_format="json",
                    timeout=self.timeout,
                    messages=[
                        {"role": "system", "content": "Ты архитектор ПО и группируешь действия по доменам"},
                        {"role": "user", "content": prompt},
                    ],
                )
                domains_raw = resp.choices[0].message.content  # type: ignore[index]
                domains = json.loads(domains_raw) if isinstance(domains_raw, str) else domains_raw  # type: ignore[arg-type]
            except Exception as exc:  # noqa: BLE001
                logger.error("OpenAI call failed (%s) → fallback stub", exc)
                domains = {"All": actions}

        data["domains"] = domains
        return {"name": self.name, "payload": {"domains": domains}}
