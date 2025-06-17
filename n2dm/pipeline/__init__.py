"""
n2dm.pipeline — набор шагов конвейера Narrative2DomainModel
-----------------------------------------------------------

Содержит все конкретные шаги и удобный список `ALL_STEPS`
для быстрого подключения в CLI/GUI.

Импортируйте так:

    from n2dm.pipeline import ALL_STEPS
    for step in ALL_STEPS:
        result = await step.run(data)

или выборочно:

    from n2dm.pipeline import GlossaryBuilder, BPMNExporter
"""

from .base import BaseStep, StepResult
from .glossary import GlossaryBuilder
from .action import ActionExtractor
from .domain import DomainGrouper
from .flow import FlowMapper
from .risk import RiskAnnotator
from .validate import ConnectivityValidator
from .export import BPMNExporter

__all__ = [
    "BaseStep",
    "StepResult",
    "GlossaryBuilder",
    "ActionExtractor",
    "DomainGrouper",
    "FlowMapper",
    "RiskAnnotator",
    "ConnectivityValidator",
    "BPMNExporter",
    "ALL_STEPS",
]

#: Полный конвейер "по умолчанию"
ALL_STEPS: list[BaseStep] = [
    GlossaryBuilder(),
    ActionExtractor(),
    DomainGrouper(),
    FlowMapper(),
    RiskAnnotator(),
    ConnectivityValidator(),
    BPMNExporter(),
]
