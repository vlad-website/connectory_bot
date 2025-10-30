import aiohttp
import os
import logging

logger = logging.getLogger(__name__)

# 🔹 Ключ DeepL
DEEPL_API_KEY = os.getenv("DEEPL_API_KEY", "3395f8ae-54a4-47ee-8508-424cad3fe67c:fx")

# 🔹 Соответствие кодов языков → DeepL
DEEPL_LANG_MAP = {
    "ru": "RU",
    "uk": "UK",
    "en": "EN",
    "es": "ES",
    "fr": "FR",
    "de": "DE",
    "it": "IT",
    "pl": "PL",
    "pt": "PT-PT",
    "br": "PT-BR",
}


async def translate_text(text: str, source_lang: str, target_lang: str) -> str:
    """
    Перевод текста через DeepL, fallback — LibreTranslate.
    """
    if not text or not text.strip():
        return "⚠️ Нет текста для перевода"

    text = text.strip()

    # Нормализуем коды языков
    target_lang = DEEPL_LANG_MAP.get(target_lang.lower(), target_lang.upper())
    source_lang = DEEPL_LANG_MAP.get(source_lang.lower(), source_lang.upper())

    # --- Попытка через DeepL ---
    if DEEPL_API_KEY:
        url = "https://api-free.deepl.com/v2/translate"
        data = {
            "auth_key": DEEPL_API_KEY,
            "text": text,
            "target_lang": target_lang,
        }

        # Добавляем source_lang, если он не совпадает с target_lang
        if source_lang and source_lang != target_lang:
            data["source_lang"] = source_lang

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=data, timeout=10) as resp:
                    result = await resp.json()

                    if "translations" in result:
                        translated = result["translations"][0]["text"]
                        logger.debug("DeepL translated %s→%s OK", source_lang, target_lang)
                        return translated

                    logger.warning("DeepL API error: %s", result)
        except Exception as e:
            logger.warning("DeepL translation failed: %s", e)

    # --- Попытка через LibreTranslate ---
    try:
        url = "https://translate.argosopentech.com/translate"
        payload = {
            "q": text,
            "source": source_lang.lower() if source_lang else "auto",
            "target": target_lang.lower(),
            "format": "text",
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=10) as resp:
                result = await resp.json()
                translated = result.get("translatedText")
                if translated:
                    logger.debug("LibreTranslate translated %s→%s OK", source_lang, target_lang)
                    return translated
                logger.warning("LibreTranslate error: %s", result)
    except Exception as e:
        logger.warning("LibreTranslate failed: %s", e)

    return "⚠️ Перевод временно недоступен"
