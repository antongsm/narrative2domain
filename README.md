narrative2domain/                  ← корневая папка репозитория
│
├─ pyproject.toml                  ← метаданные и зависимости (PEP 621 + poetry/setuptools)
├─ README.md                       ← обзор, инструкция по установке и запуску
├─ CHANGELOG.md
├─ .gitignore
│
├─ n2dm/                           ← основной пакет приложения
│   ├─ __init__.py                 ← версия + короткое описание
│   ├─ cli.py                      ← CLI-обёртка (фолбэк, если нет GUI)
│   ├─ gui.py                      ← Qt-GUI (PySide6)
│   ├─ config.py                   ← load_config / save_config
│   ├─ log.py                      ← настройка логгера
│   ├─ pipeline/                   ← конвейер преобразования
│   │   ├─ __init__.py
│   │   ├─ base.py                 ← BaseStep, StepResult
│   │   ├─ glossary.py             ← GlossaryBuilder
│   │   ├─ action.py               ← ActionExtractor
│   │   ├─ domain.py               ← DomainGrouper
│   │   ├─ flow.py                 ← FlowMapper
│   │   ├─ risk.py                 ← RiskAnnotator
│   │   ├─ validate.py             ← ConnectivityValidator
│   │   └─ export.py               ← BPMNExporter
│   └─ resources/                  ← иконки, .ui-файлы (если будут)
│
├─ tests/                          ← pytest-тесты
│   ├─ test_config.py
│   ├─ test_pipeline.py
│   └─ conftest.py
│
├─ docs/                           ← (опционально) sphinx / mkdocs
│   └─ index.md
│
└─ dist/                           ← сюда PyInstaller кладёт артефакты (игнорируется Git)
