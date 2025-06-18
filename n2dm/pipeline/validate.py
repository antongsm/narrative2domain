#!/usr/bin/env python3
"""
n2dm.pipeline.validate — ConnectivityValidator

Проверяет связность доменной карты.

Правила валидации
-----------------
1. **Участие в потоках** — каждый домен должен фигурировать
   хотя бы в одном элементе `flows` (как source или target).
2. **Связанность графа** — если рассматривать потоки как неориентированные
   рёбра, все домены должны быть достижимы из любого другого.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Set

from n2dm.pipeline.base import BaseStep, StepResult

logger = logging.getLogger(__name__)


class ConnectivityValidator(BaseStep):
    name = "ConnectivityValidator"

    async def run(self, data: Dict[str, Any]) -> StepResult:  # noqa: D401
        domains: Dict[str, list] = data.get("domains", {})
        flows: List[Dict[str, str]] = data.get("flows", [])

        domain_names: Set[str] = set(domains.keys())

        # ------- 1. участие в потоках --------------------------------------
        isolated = {
            d
            for d in domain_names
            if all(d not in (f["from"], f["to"]) for f in flows)
        }

        # ------- 2. связанный граф -----------------------------------------
        edges: Dict[str, Set[str]] = {d: set() for d in domain_names}
        for fl in flows:
            src, dst = fl["from"], fl["to"]
            if src in edges and dst in edges:
                edges[src].add(dst)
                edges[dst].add(src)

        visited: Set[str] = set()

        def dfs(node: str) -> None:
            if node in visited:
                return
            visited.add(node)
            for nb in edges[node]:
                dfs(nb)

        if domain_names:
            dfs(next(iter(domain_names)))

        disconnected = (domain_names - visited) | isolated
        valid = len(disconnected) == 0

        result = {
            "valid": valid,
            "disconnected": sorted(disconnected),
            "total_domains": len(domain_names),
            "connected": len(visited),
        }

        if valid:
            logger.info("Validation succeeded: %d domains connected", len(domain_names))
        else:
            logger.warning("Validation failed: %s disconnected", disconnected)

        data["validation"] = result
        return {"name": self.name, "payload": result}
