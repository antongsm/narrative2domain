"""
n2dm.pipeline.export — BPMNExporter (Camunda-совместимый)

Экспортирует:
  • domain_model.json
  • process.bpmn  (BPMN 2.0 + BPMNDI)
  • diagram.svg   (опц., Graphviz)
  • report.md
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

import xml.etree.ElementTree as ET

from n2dm.pipeline.base import BaseStep, StepResult

try:
    import graphviz
except ImportError:
    graphviz = None


# ---------------------------------------------------------------------------#
# BPMN-helpers                                                               #
# ---------------------------------------------------------------------------#

NS = {
    "bpmn": "http://www.omg.org/spec/BPMN/20100524/MODEL",
    "bpmndi": "http://www.omg.org/spec/BPMN/20100524/DI",
    "di": "http://www.omg.org/spec/DD/20100524/DI",
    "dc": "http://www.omg.org/spec/DD/20100524/DC",
}
for prefix, uri in NS.items():
    ET.register_namespace(prefix, uri)


def _uid(prefix: str) -> str:
    """Генерирует уникальный id с заданным префиксом."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def build_bpmn(domains: list[str], flows: list[dict[str, str]]) -> str:
    """
    Строит BPMN 2.0 XML:
      – start → все tasks → end
      – sequenceFlow из входного списка flows
      – BPMNDI с координатами (простая горизонтальная схема)
    """
    defs_id = _uid("Definitions")
    proc_id = _uid("Process")
    start_id = _uid("StartEvent")
    end_id = _uid("EndEvent")

    # --- XML дерево ---------------------------------------------------------
    defs = ET.Element(f"{{{NS['bpmn']}}}definitions", {
        "id": defs_id,
        "targetNamespace": "http://example.com/bpmn",
    })

    process = ET.SubElement(defs, f"{{{NS['bpmn']}}}process", {
        "id": proc_id,
        "isExecutable": "false",
    })

    # StartEvent
    ET.SubElement(process, f"{{{NS['bpmn']}}}startEvent", {
        "id": start_id,
        "name": "Начало",
    })

    # Tasks
    task_ids: dict[str, str] = {}
    for dom in domains:
        tid = _uid(dom.replace(" ", "_"))
        task_ids[dom] = tid
        ET.SubElement(process, f"{{{NS['bpmn']}}}task", {
            "id": tid,
            "name": dom,
        })

    # EndEvent
    ET.SubElement(process, f"{{{NS['bpmn']}}}endEvent", {
        "id": end_id,
        "name": "Конец",
    })

    # --- SequenceFlows ------------------------------------------------------
    sf_counter = 1

    # Начало → первый домен
    if domains:
        first_task = task_ids[domains[0]]
        ET.SubElement(process, f"{{{NS['bpmn']}}}sequenceFlow", {
            "id": f"Flow_{sf_counter}",
            "sourceRef": start_id,
            "targetRef": first_task,
        })
        sf_counter += 1

    # Потоки из входных данных
    for fl in flows:
        src = task_ids.get(fl["from"])
        dst = task_ids.get(fl["to"])
        if src and dst:
            ET.SubElement(process, f"{{{NS['bpmn']}}}sequenceFlow", {
                "id": f"Flow_{sf_counter}",
                "sourceRef": src,
                "targetRef": dst,
            })
            sf_counter += 1

    # Последний домен → конец
    if domains:
        last_task = task_ids[domains[-1]]
        ET.SubElement(process, f"{{{NS['bpmn']}}}sequenceFlow", {
            "id": f"Flow_{sf_counter}",
            "sourceRef": last_task,
            "targetRef": end_id,
        })

    # --- BPMNDI (простая раскладка) -----------------------------------------
    diagram = ET.SubElement(defs, f"{{{NS['bpmndi']}}}BPMNDiagram",
                            {"id": _uid("BPMNDiagram")})
    plane = ET.SubElement(diagram, f"{{{NS['bpmndi']}}}BPMNPlane", {
        "id": _uid("BPMNPlane"),
        "bpmnElement": proc_id,
    })

    x = 100
    y = 100

    # Функция-утилита для добавления BPMNShape
    def add_shape(el_id: str, w: int, h: int) -> None:
        shape = ET.SubElement(plane, f"{{{NS['bpmndi']}}}BPMNShape", {
            "id": f"{el_id}_di",
            "bpmnElement": el_id,
        })
        ET.SubElement(shape, f"{{{NS['dc']}}}Bounds", {
            "x": str(wrap_x()),
            "y": str(y),
            "width": str(w),
            "height": str(h),
        })

    # Генератор X-координаты
    def wrap_x(step: int = 120) -> int:
        nonlocal x
        current = x
        x += step
        return current

    add_shape(start_id, 36, 36)
    for dom in domains:
        add_shape(task_ids[dom], 100, 80)
    add_shape(end_id, 36, 36)

    # Эджи (waypoints)
    for sf in process.findall(f"./{{{NS['bpmn']}}}sequenceFlow"):
        edge = ET.SubElement(plane, f"{{{NS['bpmndi']}}}BPMNEdge", {
            "id": f"{sf.attrib['id']}_di",
            "bpmnElement": sf.attrib["id"],
        })
        # Берём координаты source/target shape по порядку добавления (ровно горизонтальные линии)
        idx_src = list(process).index(sf)  # немного хак, но позиции соответствуют
        wp_x1 = 118 + 120 * (idx_src - 1)
        wp_x2 = wp_x1 + 80
        for xpt in (wp_x1, wp_x2):
            ET.SubElement(edge, f"{{{NS['di']}}}waypoint", {"x": str(xpt), "y": "118"})

    # Итоговый XML-строковый вывод
    return ET.tostring(defs, encoding="utf-8", xml_declaration=True).decode("utf-8")


# ---------------------------------------------------------------------------#
# Экспортёр                                                                  #
# ---------------------------------------------------------------------------#

class BPMNExporter(BaseStep):
    name = "BPMNExporter"

    async def run(self, data: dict[str, Any]) -> StepResult:
        out_dir = Path.cwd()

        # --- JSON -----------------------------------------------------------
        domain_json = {
            "domains": data.get("domains", {}),
            "flows": data.get("flows", []),
            "risks": data.get("risks", []),
        }
        (out_dir / "domain_model.json").write_text(
            json.dumps(domain_json, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        # --- BPMN -----------------------------------------------------------
        domains_order = list(domain_json["domains"].keys())
        bpmn_xml = build_bpmn(domains_order, domain_json["flows"])
        (out_dir / "process.bpmn").write_text(bpmn_xml, encoding="utf-8")

        # --- SVG (Graphviz, опц.) ------------------------------------------
        if graphviz:
            dot = graphviz.Digraph(comment="Domain Model")
            for dom in domains_order:
                dot.node(dom)
            for fl in domain_json["flows"]:
                dot.edge(fl["from"], fl["to"], label=fl["type"])
            dot.render(filename="diagram", format="svg", cleanup=True)

        # --- Markdown -------------------------------------------------------
        md = ["# Отчёт о доменной модели", ""]
        md.append("## Домены:")
        md += [f"- {d}" for d in domains_order] or ["(нет)"]
        md.append("\n## Потоки:")
        md += [f"- {f['from']} → {f['to']} ({f['type']})" for f in domain_json["flows"]] or ["(нет)"]
        md.append("\n## Риски:")
        md += [f"- ⚠ {r}" for r in domain_json["risks"]] or ["(нет)"]

        (out_dir / "report.md").write_text("\n".join(md), encoding="utf-8")

        return {
            "name": self.name,
            "payload": {
                "files": ["domain_model.json", "process.bpmn", "diagram.svg", "report.md"],
            },
        }
