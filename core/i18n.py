TEXTS = {
    "ru": {
        "choose_lang": "🌍 Пожалуйста, выберите язык:",
        "welcome_back": "👋 С возвращением, {name}!",
        "enter_nick": "👋 Привет! Введи свой ник:",
        "pick_theme": "Выбери интересующую тему:",
        "found": "🎉 Собеседник найден!\nТема: {theme}\nПодтема: {sub}\nЯзык собеседника: {lang}",
        # кнопки
        "btn_start": "Начать",
        "btn_search": "🔍 Начать поиск",
        "btn_stop": "⛔ Остановить поиск",
        "btn_change_sub": "Изменить подтему",
        "btn_main_menu": "🏠 Главное меню",
        "btn_support": "❤️ Поддержать проект",
    },
    "uk": {
        "choose_lang": "🌍 Будь ласка, оберіть мову:",
        "welcome_back": "👋 З поверненням, {name}!",
        "enter_nick": "👋 Привіт! Введи свій нік:",
        "pick_theme": "Обери тему:",
        "found": "🎉 Співрозмовника знайдено!\nТема: {theme}\nПідтема: {sub}\nМова співрозмовника: {lang}",
        "btn_start": "Почати",
        "btn_search": "🔍 Почати пошук",
        "btn_stop": "⛔ Зупинити пошук",
        "btn_change_sub": "Змінити підтему",
        "btn_main_menu": "🏠 Головне меню",
        "btn_support": "❤️ Підтримати проект",
    },
    "en": {
        "choose_lang": "🌍 Please choose your language:",
        "welcome_back": "👋 Welcome back, {name}!",
        "enter_nick": "👋 Hi! Enter your nickname:",
        "pick_theme": "Choose a topic:",
        "found": "🎉 Partner found!\nTopic: {theme}\nSubtopic: {sub}\nPartner language: {lang}",
        "btn_start": "Start",
        "btn_search": "🔍 Start search",
        "btn_stop": "⛔ Stop search",
        "btn_change_sub": "Change subtopic",
        "btn_main_menu": "🏠 Main menu",
        "btn_support": "❤️ Support the project",
    },
    "es": {
        "choose_lang": "🌍 Por favor, elige un idioma:",
        "welcome_back": "👋 ¡Bienvenido de nuevo, {name}!",
        "enter_nick": "👋 ¡Hola! Escribe tu apodo:",
        "pick_theme": "Elige un tema:",
        "found": "🎉 ¡Pareja encontrada!\nTema: {theme}\nSubtema: {sub}\nIdioma del interlocutor: {lang}",
        "btn_start": "Comenzar",
        "btn_search": "🔍 Buscar",
        "btn_stop": "⛔ Detener búsqueda",
        "btn_change_sub": "Cambiar subtema",
        "btn_main_menu": "🏠 Menú principal",
        "btn_support": "❤️ Apoyar el proyecto",
    },
    "fr": {
        "choose_lang": "🌍 Veuillez choisir votre langue :",
        "welcome_back": "👋 Bon retour, {name} !",
        "enter_nick": "👋 Salut ! Entrez votre pseudo :",
        "pick_theme": "Choisissez un thème :",
        "found": "🎉 Partenaire trouvé !\nThème : {theme}\nSous‑thème : {sub}\nLangue du partenaire : {lang}",
        "btn_start": "Commencer",
        "btn_search": "🔍 Lancer la recherche",
        "btn_stop": "⛔ Arrêter la recherche",
        "btn_change_sub": "Changer le sous‑thème",
        "btn_main_menu": "🏠 Menu principal",
        "btn_support": "❤️ Soutenir le projet",
    },
    "de": {
        "choose_lang": "🌍 Bitte wähle eine Sprache:",
        "welcome_back": "👋 Willkommen zurück, {name}!",
        "enter_nick": "👋 Hallo! Gib deinen Nick ein:",
        "pick_theme": "Wähle ein Thema:",
        "found": "🎉 Gesprächspartner gefunden!\nThema: {theme}\nUnterthema: {sub}\nSprache des Partners: {lang}",
        "btn_start": "Start",
        "btn_search": "🔍 Suche starten",
        "btn_stop": "⛔ Suche stoppen",
        "btn_change_sub": "Unterthema ändern",
        "btn_main_menu": "🏠 Hauptmenü",
        "btn_support": "❤️ Projekt unterstützen",
    },
}

def tr_lang(lang: str, key: str, **kw) -> str:
    lang = lang if lang in TEXTS else "ru"
    return TEXTS[lang].get(key, key).format(**kw)

async def tr(user, key: str, **kw) -> str:
    # user может быть dict (из get_user) или telegram.User
    lang = "ru"
    if isinstance(user, dict):
        lang = user.get("lang", "ru")
    elif hasattr(user, "id"):
        from db.user_queries import get_user
        row = await get_user(user.id)
        if row:
            lang = row.get("lang", "ru")
    return tr_lang(lang, key, **kw)
