# Manga Translator (PyQt6)

A modern **PyQt6** rewrite of the original `pyqt5_momotranslator` — a desktop
application for translating manga / comic images.

The original program (`pyqt5_momotranslator.exe`) was a Nuitka-compiled
Python 3.10 / PyQt5 application. This project reimplements its functionality
with a clean, modular architecture on top of **PyQt6**.

## Features

- **Multiple OCR engines**: Tesseract, PaddleOCR, EasyOCR (auto-detected), plus a
  built-in Mock engine for testing without any dependencies.
- **Multiple translation engines**: Google Translate, DeepL, LibreTranslate,
  plus a Mock engine.
- **Interactive image viewer**: zoom / pan, fit-to-window, fit-width/height,
  smooth rendering.
- **Text region editing**: detected regions are shown as draggable overlay
  rectangles; click a region to edit its translation.
- **Manual region selection**: drag to select an area and OCR just that region.
- **Batch processing**: translate and export whole folders of pages.
- **Image rendering**: inpaint original text and render the translation back
  onto the image.
- **Export** to PNG / JPEG / PDF / CBZ, or bilingual side-by-side images.
- **Translation caching** (memory + disk) to avoid repeated API calls.
- **Light / dark / system themes**.
- **Settings persistence** via JSON + `QSettings`.

## Project layout

```
BookerComicTrans/
├── main.py                       # Entry point
├── requirements.txt
├── README.md
└── manga_translator/
    ├── __init__.py
    ├── app.py                    # QApplication bootstrap + theming
    ├── core/
    │   ├── config.py             # Configuration manager
    │   ├── logger.py             # Logging setup
    │   ├── ocr.py                # OCR engines + OCRManager
    │   ├── translator.py         # Translation engines + TranslatorManager
    │   └── image_processor.py    # Inpainting + text rendering
    ├── ui/
    │   ├── main_window.py        # Main window
    │   ├── image_viewer.py       # Zoomable viewer + overlays
    │   ├── settings_dialog.py    # Settings dialog
    │   ├── widgets.py            # Custom widgets
    │   └── workers.py            # QThread workers
    └── utils/
        └── resources.py          # Resource paths
```

## Installation

```bash
# Create a virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux/macOS

# Install dependencies
pip install -r requirements.txt
```

### Optional: OCR engines

The app runs out of the box with the built-in **Mock OCR/translation** engines,
which is useful for testing the UI. For real translation:

- **Tesseract** — install the Tesseract binary, then set its path in
  *Tools → Settings → OCR*. Install language packs for Japanese/Chinese.
- **PaddleOCR** — `pip install paddleocr paddlepaddle`
- **EasyOCR** — `pip install easyocr`

### Optional: translation engines

- **Google Translate** — `pip install googletrans==4.0.0rc1`
- **DeepL** — `pip install deepl`, then set your API key in settings
- **LibreTranslate** — works out of the box against the public endpoint, or
  point it at your own self-hosted server

## Usage

```bash
python main.py
```

1. **Open** a folder or individual images (*File → Open Images / Open Folder*),
   or drag-and-drop them onto the window.
2. Pick your **OCR engine** and **translation engine** from the toolbar, and set
   the source/target languages.
3. Press **T** (or *Edit → Translate Page*) to run OCR + translation on the
   current page.
4. Review and edit translations in the right-hand panel; click a region in the
   image to jump to its translation.
5. Press **R** to enter *select-region* mode and drag over an area to OCR it
   manually.
6. **Export** the rendered result (*File → Export*) or batch-process every page
   (*File → Export All Pages*).

### Keyboard shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+O` | Open images |
| `Ctrl+Shift+O` | Open folder |
| `T` | Translate current page |
| `Ctrl+T` | Translate all pages |
| `R` | Toggle region-select mode |
| `B` | Toggle bilingual view |
| `Ctrl+E` | Export current page |
| `Ctrl+Shift+E` | Export all pages |
| `←` / `→` | Previous / next page |
| `Ctrl` + wheel | Zoom in / out |
| `W` / `H` | Fit width / height |
| `Ctrl+0` | Fit to window |
| `Esc` | Cancel region selection |

## Notes on the original binary

The original `pyqt5_momotranslator.exe` is a Nuitka onefile build (Python 3.10,
`python310.dll`, PyQt5). Because Nuitka compiles the Python source to native
code, the original high-level structure is not directly recoverable from the
disassembly — function names are stripped (`sub_XXXX`) and the Python module
strings are the standard interpreter/Nuitka runtime strings. This rewrite
therefore reproduces the *functionality* of such a translator tool with an
idiomatic, maintainable PyQt6 codebase rather than a line-by-line port.

## License

MIT
