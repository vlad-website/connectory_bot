import aiohttp
import os
import logging

logger = logging.getLogger(__name__)

# Храни ключ в env-переменных (но можно и просто вписать его)
DEEPL_API_KEY = os.getenv("DEEPL_API_KEY", "3395f8ae-54a4-47ee-8508-424cad3fe67c:fx")

DEEPL_LANG_MAP = {
    "ru": "RU",
    "uk": "UK",
    "en": "EN",
    "es": "ES",
    "fr": "FR",
    "de": "DE",
}

async def translate_text(text: str, source_lang: str, target_lang: str) -> str:
    target_lang = DEEPL_LANG_MAP.get(target_lang.lower(), target_lang.upper())
    source_lang = DEEPL_LANG_MAP.get(source_lang.lower(), source_lang.upper())
    """Попробовать перевести через DeepL, fallback — LibreTranslate."""
    text = text.strip()
    if not text:
        return ""

    # --- DeepL ---
    if DEEPL_API_KEY:
        url = "https://api-free.deepl.com/v2/translate"
        data = {
            "auth_key": DEEPL_API_KEY,
            "text": text,
            "source_lang": source_lang.upper(),
            "target_lang": target_lang.upper(),
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=data, timeout=10) as resp:
                    result = await resp.json()
                    if "translations" in result:
                        return result["translations"][0]["text"]
                    logger.warning("DeepL API error: %s", result)
        except Exception as e:
            logger.warning("DeepL translation failed: %s", e)

    # --- LibreTranslate fallback ---
    try:
        url = "https://translate.argosopentech.com/translate"
        data = {
            "q": text,
            "source": source_lang.lower(),
            "target": target_lang.lower(),
            "format": "text",
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data, timeout=10) as resp:
                result = await resp.json()
                return result.get("translatedText", "⚠️ Ошибка перевода")
    except Exception as e:
        logger.warning("LibreTranslate failed: %s", e)
        return "⚠️ Перевод временно недоступен"
