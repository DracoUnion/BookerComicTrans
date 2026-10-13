"""
Translation manager for Manga Translator.
Supports multiple translation engines.
"""

import time
import hashlib
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal, QThread

from manga_translator.core.config import ConfigManager
from manga_translator.core.logger import get_logger


@dataclass
class TranslationResult:
    """Result of a translation operation."""
    source_text: str
    translated_text: str
    source_language: str
    target_language: str
    engine: str
    confidence: float = 1.0
    cached: bool = False


class TranslationEngine(ABC):
    """Abstract base class for translation engines."""

    @abstractmethod
    def translate(self, text: str, source_lang: str, target_lang: str) -> TranslationResult:
        """Translate text from source to target language."""
        pass

    @abstractmethod
    def get_supported_languages(self) -> Dict[str, str]:
        """Return supported language codes and names."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Return engine name."""
        pass


class GoogleTranslator(TranslationEngine):
    """Google Translate engine (requires googletrans or requests)."""

    def __init__(self, api_key: str = "", api_secret: str = ""):
        self.api_key = api_key
        self.api_secret = api_secret
        self._translator = None
        self._init_translator()

    def _init_translator(self):
        """Initialize the translator."""
        try:
            # Try googletrans first (free, unofficial)
            from googletrans import Translator
            self._translator = Translator()
            self._use_official = False
        except ImportError:
            self._translator = None
            self._use_official = True

    def translate(self, text: str, source_lang: str, target_lang: str) -> TranslationResult:
        if not text.strip():
            return TranslationResult(
                source_text=text,
                translated_text="",
                source_language=source_lang,
                target_language=target_lang,
                engine=self.name
            )

        try:
            if self._translator and not self._use_official:
                # Use googletrans
                result = self._translator.translate(text, src=source_lang, dest=target_lang)
                return TranslationResult(
                    source_text=text,
                    translated_text=result.text,
                    source_language=result.src,
                    target_language=result.dest,
                    engine=self.name,
                    confidence=0.9
                )
            else:
                # Fallback: return original text with note
                return TranslationResult(
                    source_text=text,
                    translated_text=f"[Translation unavailable: {text}]",
                    source_language=source_lang,
                    target_language=target_lang,
                    engine=self.name,
                    confidence=0.0
                )
        except Exception as e:
            return TranslationResult(
                source_text=text,
                translated_text=f"[Error: {str(e)}]",
                source_language=source_lang,
                target_language=target_lang,
                engine=self.name,
                confidence=0.0
            )

    def get_supported_languages(self) -> Dict[str, str]:
        return {
            "auto": "Auto Detect",
            "ja": "Japanese",
            "en": "English",
            "zh": "Chinese",
            "ko": "Korean",
            "fr": "French",
            "de": "German",
            "es": "Spanish",
            "ru": "Russian",
            "pt": "Portuguese",
            "it": "Italian",
        }

    @property
    def name(self) -> str:
        return "Google Translate"


class DeepLTranslator(TranslationEngine):
    """DeepL Translator engine (requires API key)."""

    def __init__(self, api_key: str = ""):
        self.api_key = api_key
        self._translator = None
        self._init_translator()

    def _init_translator(self):
        """Initialize DeepL translator."""
        if self.api_key:
            try:
                import deepl
                self._translator = deepl.Translator(self.api_key)
            except ImportError:
                self._translator = None

    def translate(self, text: str, source_lang: str, target_lang: str) -> TranslationResult:
        if not text.strip() or not self._translator:
            return TranslationResult(
                source_text=text,
                translated_text=text if not self._translator else "[DeepL not configured]",
                source_language=source_lang,
                target_language=target_lang,
                engine=self.name,
                confidence=0.0
            )

        try:
            # DeepL uses different language codes
            lang_map = {"ja": "JA", "en": "EN-US", "zh": "ZH", "ko": "KO"}
            src = lang_map.get(source_lang, source_lang.upper())
            tgt = lang_map.get(target_lang, target_lang.upper())

            result = self._translator.translate_text(text, source_lang=src, target_lang=tgt)
            return TranslationResult(
                source_text=text,
                translated_text=result.text,
                source_language=result.detected_source_lang.lower(),
                target_language=target_lang,
                engine=self.name,
                confidence=0.95
            )
        except Exception as e:
            return TranslationResult(
                source_text=text,
                translated_text=f"[DeepL Error: {str(e)}]",
                source_language=source_lang,
                target_language=target_lang,
                engine=self.name,
                confidence=0.0
            )

    def get_supported_languages(self) -> Dict[str, str]:
        return {
            "ja": "Japanese",
            "en": "English",
            "zh": "Chinese",
            "ko": "Korean",
            "fr": "French",
            "de": "German",
            "es": "Spanish",
            "ru": "Russian",
            "pt": "Portuguese",
            "it": "Italian",
            "pl": "Polish",
            "nl": "Dutch",
        }

    @property
    def name(self) -> str:
        return "DeepL"


class LibreTranslateEngine(TranslationEngine):
    """LibreTranslate engine (self-hosted or public API)."""

    def __init__(self, api_url: str = "https://libretranslate.de/translate", api_key: str = ""):
        self.api_url = api_url
        self.api_key = api_key

    def translate(self, text: str, source_lang: str, target_lang: str) -> TranslationResult:
        if not text.strip():
            return TranslationResult(
                source_text=text,
                translated_text="",
                source_language=source_lang,
                target_language=target_lang,
                engine=self.name,
                confidence=0.0
            )

        try:
            import requests
            payload = {
                "q": text,
                "source": source_lang if source_lang != "auto" else "auto",
                "target": target_lang,
                "format": "text",
            }
            if self.api_key:
                payload["api_key"] = self.api_key

            response = requests.post(self.api_url, data=payload, timeout=30)
            response.raise_for_status()
            result = response.json()

            return TranslationResult(
                source_text=text,
                translated_text=result.get("translatedText", text),
                source_language=result.get("detectedLanguage", source_lang),
                target_language=target_lang,
                engine=self.name,
                confidence=0.85
            )
        except Exception as e:
            return TranslationResult(
                source_text=text,
                translated_text=f"[LibreTranslate Error: {str(e)}]",
                source_language=source_lang,
                target_language=target_lang,
                engine=self.name,
                confidence=0.0
            )

    def get_supported_languages(self) -> Dict[str, str]:
        return {
            "auto": "Auto Detect",
            "ja": "Japanese",
            "en": "English",
            "zh": "Chinese",
            "ko": "Korean",
            "fr": "French",
            "de": "German",
            "es": "Spanish",
            "ru": "Russian",
            "ar": "Arabic",
            "hi": "Hindi",
        }

    @property
    def name(self) -> str:
        return "LibreTranslate"


class MockTranslator(TranslationEngine):
    """Mock translator for testing without API keys."""

    def translate(self, text: str, source_lang: str, target_lang: str) -> TranslationResult:
        # Simple mock: reverse the text or add a prefix
        mock_translations = {
            ("ja", "en"): f"[EN] {text}",
            ("zh", "en"): f"[EN] {text}",
            ("ko", "en"): f"[EN] {text}",
            ("en", "ja"): f"[JA] {text}",
        }
        key = (source_lang, target_lang)
        translated = mock_translations.get(key, f"[{target_lang.upper()}] {text}")

        return TranslationResult(
            source_text=text,
            translated_text=translated,
            source_language=source_lang,
            target_language=target_lang,
            engine=self.name,
            confidence=0.5
        )

    def get_supported_languages(self) -> Dict[str, str]:
        return {
            "auto": "Auto Detect",
            "ja": "Japanese",
            "en": "English",
            "zh": "Chinese",
            "ko": "Korean",
        }

    @property
    def name(self) -> str:
        return "Mock (Testing)"


class TranslationCache:
    """Simple in-memory + disk cache for translations."""

    def __init__(self, cache_dir: Optional[Path] = None, max_size: int = 10000):
        self.cache_dir = cache_dir or Path.home() / ".cache" / "MangaTranslator"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.cache_dir / "translation_cache.json"
        self.max_size = max_size
        self.memory_cache: Dict[str, TranslationResult] = {}
        self._load_cache()

    def _load_cache(self):
        """Load cache from disk."""
        try:
            if self.cache_file.exists():
                import json
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for key, value in data.items():
                        self.memory_cache[key] = TranslationResult(**value)
        except Exception:
            pass

    def _save_cache(self):
        """Save cache to disk."""
        try:
            import json
            # Limit cache size
            if len(self.memory_cache) > self.max_size:
                # Remove oldest entries
                keys = list(self.memory_cache.keys())
                for key in keys[:len(keys) - self.max_size]:
                    del self.memory_cache[key]

            data = {k: v.__dict__ for k, v in self.memory_cache.items()}
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _make_key(self, text: str, source_lang: str, target_lang: str, engine: str) -> str:
        """Generate cache key."""
        content = f"{engine}:{source_lang}:{target_lang}:{text}"
        return hashlib.sha256(content.encode()).hexdigest()[:32]

    def get(self, text: str, source_lang: str, target_lang: str, engine: str) -> Optional[TranslationResult]:
        """Get cached translation."""
        key = self._make_key(text, source_lang, target_lang, engine)
        result = self.memory_cache.get(key)
        if result:
            result.cached = True
        return result

    def put(self, result: TranslationResult, engine: str):
        """Store translation in cache."""
        key = self._make_key(result.source_text, result.source_language, result.target_language, engine)
        self.memory_cache[key] = result
        self._save_cache()


class TranslatorManager(QObject):
    """Manages translation engines and operations."""

    translation_finished = pyqtSignal(TranslationResult)
    translation_error = pyqtSignal(str)
    batch_progress = pyqtSignal(int, int)  # current, total

    def __init__(self, config_manager: ConfigManager):
        super().__init__()
        self.config = config_manager
        self.logger = get_logger("TranslatorManager")
        self.engines: Dict[str, TranslationEngine] = {}
        self.current_engine: Optional[TranslationEngine] = None
        self.cache = TranslationCache()
        self._init_engines()

    def _init_engines(self):
        """Initialize available translation engines."""
        # Always available mock engine for testing
        self.engines["mock"] = MockTranslator()

        # Google Translate
        self.engines["google"] = GoogleTranslator()

        # DeepL (if API key provided)
        api_key = self.config.get("translation.api_key", "")
        if api_key:
            self.engines["deepl"] = DeepLTranslator(api_key)

        # LibreTranslate
        self.engines["libretranslate"] = LibreTranslateEngine()

        # LLM translation (reuses BookerGptTool prompts; config from env vars)
        try:
            from manga_translator.core.llm_translator import LLMTranslator
            self.engines["llm"] = LLMTranslator(
                self.config.get("translation.source_language", "auto"),
                self.config.get("translation.target_language", "en"),
                rounds=int(self.config.get("translation.llm_rounds", 1)),
            )
        except Exception as ex:
            self.logger.debug(f"LLM translator unavailable: {ex}")

        # Set current engine
        engine_name = self.config.get("translation.engine", "google")
        self.set_engine(engine_name)

    def set_engine(self, engine_name: str) -> bool:
        """Set the active translation engine."""
        if engine_name == "llm":
            # Rebuild so source/target languages and rounds stay current.
            from manga_translator.core.llm_translator import LLMTranslator
            self.engines["llm"] = LLMTranslator(
                self.config.get("translation.source_language", "auto"),
                self.config.get("translation.target_language", "en"),
                rounds=int(self.config.get("translation.llm_rounds", 1)),
            )
        if engine_name in self.engines:
            self.current_engine = self.engines[engine_name]
            self.config.set("translation.engine", engine_name)
            self.logger.info(f"Translation engine set to: {engine_name}")
            return True
        return False

    def get_available_engines(self) -> List[str]:
        """Get list of available engine names."""
        return list(self.engines.keys())

    def get_current_engine(self) -> Optional[TranslationEngine]:
        """Get the current translation engine."""
        return self.current_engine

    def translate(self, text: str, source_lang: str = None, target_lang: str = None) -> TranslationResult:
        """Translate text using current engine."""
        if not self.current_engine:
            return TranslationResult(
                source_text=text,
                translated_text="[No translation engine available]",
                source_language=source_lang or "auto",
                target_language=target_lang or "en",
                engine="none",
                confidence=0.0
            )

        source_lang = source_lang or self.config.get("translation.source_language", "auto")
        target_lang = target_lang or self.config.get("translation.target_language", "en")

        # Check cache
        if self.config.get("translation.use_cache", True):
            cached = self.cache.get(text, source_lang, target_lang, self.current_engine.name)
            if cached:
                self.logger.debug(f"Cache hit for: {text[:50]}...")
                return cached

        # Perform translation
        self.logger.debug(f"Translating: {text[:50]}... ({source_lang} -> {target_lang})")
        result = self.current_engine.translate(text, source_lang, target_lang)

        # Cache result
        if self.config.get("translation.use_cache", True) and result.confidence > 0:
            self.cache.put(result, self.current_engine.name)

        return result

    def translate_batch(self, texts: List[str], source_lang: str = None, target_lang: str = None) -> List[TranslationResult]:
        """Translate multiple texts."""
        results = []
        total = len(texts)
        for i, text in enumerate(texts):
            result = self.translate(text, source_lang, target_lang)
            results.append(result)
            self.batch_progress.emit(i + 1, total)
        return results

    def get_supported_languages(self) -> Dict[str, str]:
        """Get supported languages for current engine."""
        if self.current_engine:
            return self.current_engine.get_supported_languages()
        return {}

    def set_api_key(self, engine: str, api_key: str, api_secret: str = ""):
        """Set API key for an engine."""
        if engine == "deepl" and api_key:
            self.engines["deepl"] = DeepLTranslator(api_key)
            if self.current_engine and self.current_engine.name == "DeepL":
                self.current_engine = self.engines["deepl"]
        elif engine == "google":
            self.config.set("translation.api_key", api_key)
            self.config.set("translation.api_secret", api_secret)
        elif engine == "libretranslate":
            self.config.set("translation.api_key", api_key)
        self.config.save()