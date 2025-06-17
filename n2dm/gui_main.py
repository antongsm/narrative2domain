#!/usr/bin/env python3
"""
n2dm.gui_main — графический интерфейс Narrative2DomainModel
-----------------------------------------------------------

Содержит:
• SettingsDialog — ввод / изменение OpenAI API‑ключа
• PipelineRunner  — асинхронный исполнитель конвейера (работает в QThread)
• MainWindow      — главное окно приложения
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QObject, QThread, Signal, Slot, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QStatusBar,
    QTabWidget,
    QTextEdit,
    QToolBar,
    QWidget,
)

from n2dm.config import load_config, save_config
from n2dm.pipeline import ALL_STEPS  # список настроенных шагов
from n2dm.log import init_logging

try:
    import graphviz  # type: ignore
except ImportError:  # pragma: no cover
    graphviz = None

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------#
# Асинхронный исполнитель конвейера                                          #
# ---------------------------------------------------------------------------#
class PipelineRunner(QObject):
    """Qt‑friendly wrapper для выполнения Pipeline в отдельном потоке."""

    progress = Signal(int, str)  # процент, сообщение
    finished = Signal(dict)      # итоговый data‑словарь
    failed = Signal(str)

    def __init__(self, steps: list | None = None) -> None:
        super().__init__()
        self._steps = steps or ALL_STEPS
        self._data: Dict[str, Any] = {}

    @Slot(str)
    def run(self, input_path: str) -> None:
        """Точка входа для QThread — оборачивает asyncio‑цикл."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._execute(input_path))
        except Exception as exc:  # noqa: BLE001
            logger.exception("Pipeline failed")
            self.failed.emit(str(exc))
        finally:
            loop.close()

    async def _execute(self, input_path: str) -> None:
        self._data["input_path"] = input_path
        total = len(self._steps)

        for idx, step in enumerate(self._steps, start=1):
            self.progress.emit(int((idx - 1) / total * 100), f"{step.name}…")
            result = await step.run(self._data)
            self._data[step.name] = result["payload"]
            logger.info("%s done", step.name)
            self.progress.emit(int(idx / total * 100), f"{step.name} ✓")

        self.finished.emit(self._data)


# ---------------------------------------------------------------------------#
# Диалог настроек                                                            #
# ---------------------------------------------------------------------------#
class SettingsDialog(QDialog):
    def __init__(self, cfg: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Настройки")
        self._cfg = cfg

        layout = QFormLayout(self)
        self._api_edit = QLineEdit(cfg["openai"]["api_key"])
        self._api_edit.setEchoMode(QLineEdit.Password)
        layout.addRow("OpenAI API‑Key:", self._api_edit)

        save_label = QLabel('<a href="#">Сохранить</a>')
        save_label.setOpenExternalLinks(False)
        save_label.linkActivated.connect(lambda _: self.accept())
        layout.addRow(save_label)

    def accept(self) -> None:  # noqa: D401
        self._cfg["openai"]["api_key"] = self._api_edit.text().strip()
        save_config(self._cfg)
        super().accept()


# ---------------------------------------------------------------------------#
# Главное окно                                                               #
# ---------------------------------------------------------------------------#
class MainWindow(QMainWindow):
    """Главное окно Narrative2DomainModel GUI."""

    def __init__(self, cfg: dict) -> None:
        super().__init__()
        self.setWindowTitle("Narrative2DomainModel")
        self.resize(1000, 700)
        self.setAcceptDrops(True)

        self.cfg = cfg
        self._input_path: Optional[str] = None
        self._thread: Optional[QThread] = None
        self._runner: Optional[PipelineRunner] = None

        # Tabs
        self.tabs = QTabWidget(self)
        self.setCentralWidget(self.tabs)

        self.preview_tab = QTextEdit(readOnly=True)
        self.progress_tab = QTextEdit(readOnly=True)
        self.schema_tab = QTextEdit(readOnly=True)
        self.bpmn_tab = QTextEdit(readOnly=True)
        self.report_tab = QTextEdit(readOnly=True)

        for widget, title in [
            (self.preview_tab, "Предпросмотр"),
            (self.progress_tab, "Прогресс"),
            (self.schema_tab, "Схема"),
            (self.bpmn_tab, "BPMN"),
            (self.report_tab, "Отчёт"),
        ]:
            self.tabs.addTab(widget, title)

        # Toolbar
        tb = QToolBar("Main", self)
        self.addToolBar(tb)

        open_act = QAction("Открыть…", self)
        open_act.triggered.connect(self.open_file)  # type: ignore[arg-type]
        tb.addAction(open_act)

        gen_act = QAction("Сгенерировать модель", self)
        gen_act.triggered.connect(self.generate_model)  # type: ignore[arg-type]
        tb.addAction(gen_act)

        # Settings menu
        settings_act = QAction("Настройки", self)
        settings_act.triggered.connect(self.open_settings)  # type: ignore[arg-type]
        self.menuBar().addMenu("Настройки").addAction(settings_act)

        # Status bar + progress
        self.status = QStatusBar(self)
        self.setStatusBar(self.status)
        self.progress_bar = QProgressBar(self)
        self.status.addPermanentWidget(self.progress_bar)

    # ------------------------ Drag‑and‑Drop ---------------------------------
    def dragEnterEvent(self, event) -> None:  # noqa: D401
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:  # noqa: D401
        urls = event.mimeData().urls()
        if urls:
            self.load_file(urls[0].toLocalFile())

    # ------------------------ File handling ---------------------------------
    def open_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Выберите файл", os.getcwd(), "Text/Audio (*.txt *.mp3)")
        if path:
            self.load_file(path)

    def load_file(self, path: str) -> None:
        self._input_path = path
        p = Path(path)
        if p.suffix.lower() == ".txt":
            self.preview_tab.setPlainText(p.read_text(encoding="utf-8"))
        else:
            self.preview_tab.setPlainText(f"Аудиофайл: {p.name}\n(расшифровка ещё не реализована)")

        self.tabs.setCurrentWidget(self.preview_tab)
        self.status.showMessage(f"Загружен файл: {p.name}")

    # ------------------------ Settings dialog ------------------------------
    def open_settings(self) -> None:
        SettingsDialog(self.cfg, self).exec()

    # ------------------------ Pipeline run ---------------------------------
    def generate_model(self) -> None:
        if not self._input_path:
            QMessageBox.warning(self, "Нет файла", "Сначала загрузите входной файл.")
            return

        # Очистка вкладок результатов
        self.schema_tab.clear()
        self.bpmn_tab.clear()
        self.report_tab.clear()
        self.progress_tab.clear()
        self.progress_bar.reset()

        # Создаём поток и раннер
        self._thread = QThread(self)
        self._runner = PipelineRunner()
        self._runner.moveToThread(self._thread)

        self._thread.started.connect(lambda: self._runner.run(self._input_path))  # type: ignore[arg-type]
        self._runner.progress.connect(self.on_progress)
        self._runner.finished.connect(self.on_finished)
        self._runner.failed.connect(self.on_failed)
        self._runner.finished.connect(self._thread.quit)
        self._runner.failed.connect(self._thread.quit)

        self._thread.start()
        self.status.showMessage("Генерация модели…")

    # ------------------------ Slots ----------------------------------------
    @Slot(int, str)
    def on_progress(self, percent: int, msg: str) -> None:
        self.progress_bar.setValue(percent)
        self.progress_tab.append(f"{percent}% — {msg}")

    @Slot(dict)
    def on_finished(self, data: dict) -> None:
        self.progress_bar.setValue(100)
        self.progress_tab.append("\n✅ Модель сгенерирована успешно.")
        self.status.showMessage("Готово")

        out_dir = Path.cwd()
        self.schema_tab.setPlainText((out_dir / "domain_model.json").read_text("utf-8"))
        self.bpmn_tab.setPlainText((out_dir / "process.bpmn").read_text("utf-8"))
        self.report_tab.setPlainText((out_dir / "report.md").read_text("utf-8"))
        if (out_dir / "diagram.svg").exists():
            self.schema_tab.append("\n[SVG диаграмма сохранена во внешнем файле]")

        self.tabs.setCurrentWidget(self.report_tab)

    @Slot(str)
    def on_failed(self, message: str) -> None:
        QMessageBox.critical(self, "Ошибка", message)
        self.status.showMessage("Ошибка: " + message)
        self.progress_bar.reset()


# ---------------------------------------------------------------------------#
# Запуск напрямую (debug)                                                    #
# ---------------------------------------------------------------------------#
if __name__ == "__main__":  # pragma: no cover
    init_logging()
    app = QApplication(sys
