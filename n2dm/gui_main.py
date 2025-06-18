#!/usr/bin/env python3
"""
n2dm.gui_main ― основное Qt-окно Narrative2DomainModel

* Загрузка текстового / аудио-файла
* Запуск асинхронного конвейера
* Вкладки: предпросмотр, прогресс, JSON-схема, BPMN-XML, отчёт
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtGui import QAction, QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QStatusBar,
    QTabWidget,
    QTextEdit,
    QToolBar,
)

from n2dm.pipeline.action import ActionExtractor
from n2dm.pipeline.domain import DomainGrouper
from n2dm.pipeline.export import BPMNExporter
from n2dm.pipeline.flow import FlowMapper
from n2dm.pipeline.glossary import GlossaryBuilder
from n2dm.pipeline.risk import RiskAnnotator
from n2dm.pipeline.validate import ConnectivityValidator

# --------------------------------------------------------------------------- #
# Логирование
# --------------------------------------------------------------------------- #
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("gui")

# --------------------------------------------------------------------------- #
# Qt-совместимый раннер конвейера (работает в отдельном QThread)
# --------------------------------------------------------------------------- #
class PipelineRunner(QObject):
    progress = Signal(int, str)  # процент, сообщение
    finished = Signal(dict)
    failed = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.steps = [
            GlossaryBuilder(),
            ActionExtractor(),
            DomainGrouper(),
            FlowMapper(),
            RiskAnnotator(),
            ConnectivityValidator(),
            BPMNExporter(),
        ]
        self.data: Dict[str, Any] = {}

    @Slot(str)
    def run(self, input_path: str) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._exec(input_path))
        except Exception as exc:
            log.exception("Pipeline failed")
            self.failed.emit(str(exc))
        finally:
            loop.close()

    async def _exec(self, input_path: str) -> None:
        self.data["input_path"] = input_path
        total = len(self.steps)
        for idx, step in enumerate(self.steps, start=1):
            self.progress.emit(int((idx - 1) / total * 100), f"{step.name}…")
            res = await step.run(self.data)
            self.data[step.name] = res["payload"]
            self.progress.emit(int(idx / total * 100), f"{step.name} ✓")
        self.finished.emit(self.data)

# --------------------------------------------------------------------------- #
# Главное окно
# --------------------------------------------------------------------------- #
class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Narrative2DomainModel")
        self.resize(1000, 700)

        # вкладки
        self.tabs = QTabWidget(self)
        self.setCentralWidget(self.tabs)
        self.preview_tab = QTextEdit(readOnly=True)
        self.progress_tab = QTextEdit(readOnly=True)
        self.schema_tab = QTextEdit(readOnly=True)
        self.bpmn_tab = QTextEdit(readOnly=True)
        self.report_tab = QTextEdit(readOnly=True)
        self.tabs.addTab(self.preview_tab, "Предпросмотр")
        self.tabs.addTab(self.progress_tab, "Прогресс")
        self.tabs.addTab(self.schema_tab, "Схема JSON")
        self.tabs.addTab(self.bpmn_tab, "BPMN-XML")
        self.tabs.addTab(self.report_tab, "Отчёт")

        # тулбар
        tb = QToolBar("Main")
        self.addToolBar(tb)
        open_act = QAction("Открыть…", self)
        open_act.triggered.connect(self.open_file)  # type: ignore[arg-type]
        tb.addAction(open_act)
        run_act = QAction("Сгенерировать", self)
        run_act.triggered.connect(self.generate)  # type: ignore[arg-type]
        tb.addAction(run_act)

        # статус-бар + progress
        self.status = QStatusBar(self)
        self.setStatusBar(self.status)
        self.progress = QProgressBar(self)
        self.status.addPermanentWidget(self.progress)

        # pipeline
        self._thread: Optional[QThread] = None
        self._runner: Optional[PipelineRunner] = None
        self._input: Optional[str] = None

    # ---------- Файл --------------------------------------------------------
    @Slot()
    def open_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Выберите файл", os.getcwd(), "Text (*.txt);;All (*)"
        )
        if path:
            self._load(path)

    def _load(self, path: str) -> None:
        self._input = path
        text = Path(path).read_text("utf-8")
        self.preview_tab.setPlainText(text)
        self.status.showMessage(f"Загружен {Path(path).name}")
        self.tabs.setCurrentWidget(self.preview_tab)

    # ---------- Генерация ---------------------------------------------------
    @Slot()
    def generate(self) -> None:
        if not self._input:
            QMessageBox.warning(self, "Нет файла", "Загрузите входной файл.")
            return
        self.progress_tab.clear()
        self.progress.setValue(0)

        self._thread = QThread()
        self._runner = PipelineRunner()
        self._runner.moveToThread(self._thread)
        self._thread.started.connect(lambda: self._runner.run(self._input))  # type: ignore[arg-type]
        self._runner.progress.connect(self._on_progress)
        self._runner.finished.connect(self._on_finish)
        self._runner.failed.connect(self._on_fail)
        self._runner.finished.connect(self._thread.quit)
        self._runner.failed.connect(self._thread.quit)
        self._thread.start()
        self.status.showMessage("Генерация…")

    @Slot(int, str)
    def _on_progress(self, pct: int, msg: str) -> None:
        self.progress.setValue(pct)
        self.progress_tab.append(f"{pct}% — {msg}")

    @Slot(dict)
    def _on_finish(self, data: dict) -> None:
        self.progress.setValue(100)
        self.status.showMessage("Готово")
        out = Path.cwd()
        self.schema_tab.setPlainText((out / "domain_model.json").read_text("utf-8"))
        self.bpmn_tab.setPlainText((out / "process.bpmn").read_text("utf-8"))
        self.report_tab.setPlainText((out / "report.md").read_text("utf-8"))
        self.progress_tab.append("\n✅ Завершено успешно")
        self.tabs.setCurrentWidget(self.report_tab)

    @Slot(str)
    def _on_fail(self, msg: str) -> None:
        QMessageBox.critical(self, "Ошибка", msg)
        self.status.showMessage("Ошибка")
        self.progress.reset()

    # ---------- Закрытие ----------------------------------------------------
    def closeEvent(self, evt: QCloseEvent) -> None:  # noqa: N802
        if self._thread and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait()
        super().closeEvent(evt)

# --------------------------------------------------------------------------- #
# Entry-point
# --------------------------------------------------------------------------- #
def main() -> None:
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":   # pragma: no cover
    main()