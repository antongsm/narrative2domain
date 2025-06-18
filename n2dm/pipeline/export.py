#!/usr/bin/env python3
"""
BPMNExporter — валидный BPMN 2.0 + BPMNDI.

• Латинские, уникальные ID (slug + hash)
• Каждый sequenceFlow ссылается на существующие задачи
• Минимальный BPMNDI: Camunda Modeler открывает без предупреждений
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List

from n2dm.pipeline.base import BaseStep, StepResult

logger = logging.getLogger(__name__)

SAFE_ID = re.compile(r"[^A-Za-z0-9_-]+")


def make_id(raw: str) -> str:
    """Преобразовать подпись в безопасный BPMN-ID (ASCII)."""
    slug = SAFE_ID.sub("_", raw)[:50].strip("_") or "Task"
    return f"{slug}_{abs(hash(raw)) & 0xFFFF:04x}"


class BPMNExporter(BaseStep):
    name = "BPMNExporter"

    async def run(self, data: Dict[str, Any]) -> StepResult:
        out_dir = Path.cwd()

        # ---------- 1. dump JSON ------------------------------------------------
        domain_json = {
            "domains": data.get("domains", {}),
            "flows": data.get("flows", []),
            "risks": data.get("risks", []),
        }
        (out_dir / "domain_model.json").write_text(
            json.dumps(domain_json, ensure_ascii=False, indent=2)
        )

        domains: List[str] = list(domain_json["domains"])
        id_map = {d: make_id(d) for d in domains}

        # ---------- 2. BPMN-XML -------------------------------------------------
        proc_id = "Process_1"
        lines = [
            "<?xml version='1.0' encoding='UTF-8'?>",
            "<definitions xmlns='http://www.omg.org/spec/BPMN/20100524/MODEL'"
            " xmlns:bpmndi='http://www.omg.org/spec/BPMN/20100524/DI'"
            " xmlns:di='http://www.omg.org/spec/DD/20100524/DI'"
            " xmlns:dc='http://www.omg.org/spec/DD/20100524/DC'"
            " id='Defs_1' targetNamespace='http://n2dm'>",
            f"  <process id='{proc_id}' isExecutable='false'>",
        ]

        # tasks
        for dom in domains:
            lines.append(f"    <task id='{id_map[dom]}' name='{dom}'/>")

        # flows
        for i, fl in enumerate(domain_json["flows"], start=1):
            src = id_map[fl['from']]
            dst = id_map[fl['to']]
            lines.append(f"    <sequenceFlow id='Flow_{i}' sourceRef='{src}' targetRef='{dst}'/>")

        lines.append("  </process>")

        # ---------- 3. BPMNDI (минимум) ----------------------------------------
        lines.append("  <bpmndi:BPMNDiagram id='Diag_1'>")
        lines.append(f"    <bpmndi:BPMNPlane id='Plane_1' bpmnElement='{proc_id}'>")

        # простая вертикальная раскладка
        x, y = 100, 100
        for dom in domains:
            tid = id_map[dom]
            lines.append(
                f"      <bpmndi:BPMNShape id='{tid}_di' bpmnElement='{tid}'>"
                f"<dc:Bounds x='{x}' y='{y}' width='100' height='80'/>"
                "</bpmndi:BPMNShape>"
            )
            y += 120

        for i, fl in enumerate(domain_json["flows"], start=1):
            src_idx = domains.index(fl["from"])
            dst_idx = domains.index(fl["to"])
            y1, y2 = 140 + src_idx * 120, 140 + dst_idx * 120
            lines.append(
                f"      <bpmndi:BPMNEdge id='Flow_{i}_di' bpmnElement='Flow_{i}'>"
                f"<di:waypoint x='{x+100}' y='{y1}'/>"
                f"<di:waypoint x='{x+100}' y='{y2}'/>"
                "</bpmndi:BPMNEdge>"
            )

        lines.extend(["    </bpmndi:BPMNPlane>", "  </bpmndi:BPMNDiagram>", "</definitions>"])
        (out_dir / "process.bpmn").write_text("\n".join(lines), encoding="utf-8")

        # ---------- 4. SVG (уже было) ------------------------------------------
        try:
            import graphviz  # type: ignore

            dot = graphviz.Digraph(comment="Domain Model")
            for d in domains:
                dot.node(d)
            for fl in domain_json["flows"]:
                dot.edge(fl["from"], fl["to"], label=fl["type"])
            dot.render(filename="diagram", format="svg", cleanup=True)
        except Exception as exc:
            logger.warning("SVG not generated (%s)", exc)

        logger.info("✅ BPMN exported: %s/process.bpmn", out_dir)
        return {"name": self.name, "payload": {"files": ["process.bpmn"]}}
