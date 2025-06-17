"""
n2dm.pipeline.base — абстрактный базовый шаг конвейера

Все шаги должны наследовать BaseStep и реализовывать метод run().
"""

from typing import Any, TypedDict, Protocol


class StepResult(TypedDict):
    name: str
    payload: dict[str, Any]


class BaseStep(Protocol):
    """Базовый интерфейс для шагов конвейера."""

    name: str

    async def run(self, data: dict[str, Any]) -> StepResult:
        """
        Выполняет шаг асинхронно. Должен быть переопределён в подклассе.
        :param data: входной словарь, общий для всех шагов
        :return: StepResult = {"name": ..., "payload": ...}
        """
        ...
