# BookerComicTrans 架构设计

> 漫画翻译桌面工具。本文件描述 PySide6 迁移与参考架构对齐后的当前代码结构（2026-10-30）。

## 1. 项目简介

将 `pyqt5_momotranslator`（Nuitka 打包的 PyQt5 程序）以 Python + **PySide6** 重写为模块化桌面应用：
多 OCR 引擎（Tesseract / PaddleOCR / EasyOCR / Mock）、多翻译引擎（Google / DeepL / LibreTranslate / LLM）、
交互式图像查看器、文本区域标注、批量导出（PNG / JPEG / PDF / CBZ）。

变更历史：
- `ef10bab` 迁移 PyQt6 → PySide6（`pyqtSignal` → `Signal`，全部 imports 更换）。
- `06bb757` 新增零 Qt 架构层：`common/`、`tasks/`、`services/`、`bootstrap.py`；`app.py` 改用 bootstrap 装配。

## 2. 技术栈与依赖

| 项 | 值 |
|---|---|
| Qt 绑定 | PySide6 ≥ 6.5（`requirements.txt`） |
| 图像 | Pillow、numpy |
| OCR | pytesseract（可选 PaddleOCR / EasyOCR） |
| 翻译 | requests（LibreTranslate）、开箱 LLM（openai + json_repair） |
| 配置 | JSON 文件 + QSettings（窗口几何/最近文件） |
| 测试 | unittest（20 用例，含零 Qt 架构层测试） |

## 3. 目录结构

```text
BookerComicTrans/
├─ main.py                       # 入口 → MangaTranslatorApp(sys.argv).run()
├─ requirements.txt
├─ manga_translator/
│  ├─ app.py                     # QApplication 工厂 + 主题 + 核心装配（经 bootstrap）
│  ├─ bootstrap.py               # build_context()：装配 AppContext（零 Qt）
│  ├─ common/                    # ★ 零 Qt
│  │  ├─ events.py               # EventHub 事件总线
│  │  ├─ context.py              # AppContext 数据类
│  │  ├─ exceptions.py           # 领域异常（MangaTranslatorError/...）
│  │  └─ __init__.py
│  ├─ tasks/                     # ★ 零 Qt
│  │  ├─ task.py                 # Task/TaskState/TaskManager 状态机 + TaskCancelled
│  │  └─ __init__.py
│  ├─ services/                  # ★ 零 Qt
│  │  ├─ facade.py               # ServiceFacade：UI 唯一入口（recognize/translate/submit_*）
│  │  └─ __init__.py
│  ├─ core/                      # 领域逻辑（config/ocr/translator/llm_*/image_processor/logger）
│  ├─ ui/                        # ★ 唯一允许 import PySide6 的包
│  │  ├─ main_window.py          # 三栏 splitter（页列表/图查看器/翻译面板）
│  │  ├─ image_viewer.py
│  │  ├─ settings_dialog.py
│  │  ├─ widgets.py
│  │  ├─ workers.py              # OCR/Translation/Pipeline/ImageLoadWorker（QThread + 协作取消）
│  │  └─ __init__.py
│  └─ utils/resources.py         # 资源路径（fonts/images/icon）
├─ tests/
│  ├─ test_llm_parsing.py        # LLM 输出解析（纯逻辑）
│  └─ test_tasks.py              # EventHub / TaskManager 单测（零 Qt）
```

## 4. 架构分层与依赖方向

```text
ui/ (PySide6, Qt 信号/线程)
 └─ services/facade.py  (ServiceFacade)
     └─ core/ 领域管理器（OCR / Translator / ImageProcessor / LLM）
         └─ common/ 零 Qt 基础设施
```

- 单向依赖：`ui → services → core → common`；禁止反向。
- 只有 `ui/` 可 import PySide6。`core/` 除 `config.py`（QSettings 存窗口几何）、`logger.py`、
  `translator.py`（信号）尚存少量 Qt 依赖外，其余纯 Python（架构要求已基本满足，遗留点见 §9）。

## 5. 关键流程

```text
python main.py
→ MangaTranslatorApp(argv).run()
   ├─ QApplication（应用名/font）→ splash（可选）
   ├─ ctx = build_context()         # ConfigManager + EventHub + TaskManager + ServiceFacade
   ├─ MainWindow(ctx.config, ctx.translator_manager, ctx.ocr_manager)
   └─ app.exec()
```

长任务（OCR / 翻译 / 图片加载）：UI 通过 `ServiceFacade.submit_pipeline()` / `submit_load_image()`
提交到 `TaskManager` 线程池，worker 线程内执行，UI 经 `ui/workers.py` 的 QThread + `Signal` 收
`progress / regions_ready / translations_ready / error / finished_all`，绝不阻塞主线程。

## 6. 线程模型

| 线程 | 职责 |
|---|---|
| Qt 主线程 | 窗口/控件、信号槽、QSettings 读写 |
| QThread（workers） | OCR / 翻译 / 管线 / 图片加载，协作式取消（`_cancelled` 标志） |
| TaskManager 池（零 Qt） | `ServiceFacade.submit_*` 的后台执行，事件经 EventHub 分发 |

## 7. 配置管理

- 功能配置：JSON 文件（`AppConfigLocation/MangaTranslator/config.json`），`ConfigManager` 点号读写。
- 偏执：窗口几何 / 状态 / 最近文件 → QSettings（`BookerComicTrans/MangaTranslator`）。
- 主题：light / dark / system（QSS 字符串）。

## 8. 测试

```bash
python -m unittest discover -s tests        # 20 用例全绿
# 架构层单测（EventHub/TaskManager）: tests/test_tasks.py
# offscreen 冒烟（构建主窗口）: QT_QPA_PLATFORM=offscreen
```

## 9. 与参考架构的差距（后续 TODO）

- `core/translator.py` 仍用 `QObject/Signal` 发布任务进度——可迁到 TaskManager + EventHub，
  worker 只做 Qt 桥。
- `core/config.py` 持有 QSettings 属"仅 UI"偏好，但位置在 core——可归入 `ui/settings_store.py`。
- 尚无 SQLAlchemy / db 层（当前无任务历史持久化需求，按计划不强引 ORM）。
- 尚无 `pyproject.toml` 正式打包配置（requirements.txt 已注释 PyInstaller / Nuitka 可选依赖）。