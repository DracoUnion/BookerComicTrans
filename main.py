#!/usr/bin/env python3
"""
Main entry point for Manga Translator application.
"""

import sys
import os
from pathlib import Path

# Add the project root to the path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from manga_translator.app import MangaTranslatorApp


def main():
    """Main entry point."""
    app = MangaTranslatorApp(sys.argv)
    return app.run()


if __name__ == "__main__":
    sys.exit(main())