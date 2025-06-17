#!/usr/bin/env python3
"""n2dm.pipeline.validate — ConnectivityValidator

Проверяет связность доменной карты.

Правила:
1. **Участие в потоках** — каждый домен должен появляться хотя бы в одном
   элементе `flows` (source или target).  Иначе считается изолированным.
2. **Связанность графа** — если рассматривать потоки как рёбра
   неориентированного графа, все домены должны быть достижимы из любого.

Шаг не использует LLM и всегда работает офлайн.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Set

from n2dm.pipeline.base import BaseStep, StepResult

logger = logging.getLogger(__name__)


class ConnectivityValidator(BaseStep):
    """Проверяет целостность и связность модели доменов."""

    name = "ConnectivityValidator"

    async def run(self, data: Dict[str, Any]) -> StepResult:  # noqa: D401
        domains: Dict[str, List] = data.get("domains", {})
        flows: List[Dict[str, str]] = data.get("flows", [])

        domain_names: Set[str] = set(domains.keys())
        if not domain_names:
            result = {
                "valid": False,
                "reason": "no_domains",
                "disconnected": [],
                "details": "Модель не содержит доменов",
            }
            data["validation"] = result
            return {"name": self.name, "payload": result}

        # --- участие в потоках -------------------------------------------
        appeared: Set[str] = set()
        for fl in flows:
            appeared.add(fl.get("from", ""))
            appeared.add(fl.get("to", ""))

        isolated = sorted(domain_names - appeared)

        # --- построение графа --------------------------------------------
        edges = {d: set() for d in domain_names}
        for fl in flows:
            src, dst = fl.get("from"), fl.get("to")
            if src in domain_names and dst in domain_names:
                edges[src].add(dst)
                edges[dst].add(src)

        # --- обход в глубину ---------------------------------------------
        visited: Set[str] = set()

        def dfs(node: str) -> None:  # noqa: D401
            if node in visited:
                return
            visited.add(node)
            for nbr in edges[node]:
                dfs(nbr)

        dfs(next(iter(domain_names)))  # стартуем с любого домена
        disconnected = sorted(domain_names - visited)

        valid = not isolated and not disconnected
        result = {
            "valid": valid,
            "isolated": isolated,          # домены без потоков
            "disconnected": disconnected,  # недостижимые в графе
            "total_domains": len(domain_names),
            "connected": len(visited),
        }

        if not valid:
            logger.warning("Validation failed: %s", result)
        else:
            logger.info("Validation succeeded: %s domains connected", len(domain_names))

        data["validation"] = result
        return {"name": self.name, "payload": result}
