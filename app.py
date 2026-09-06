from fastapi import (
    FastAPI,
    HTTPException,
    Query,
    UploadFile,
    File,
    Form,
    Request
)
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import time
import httpx
import base64
import hashlib
from fastapi.responses import (
    RedirectResponse,
    Response,
    FileResponse
)
from urllib.parse import urlencode
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
import json
from pathlib import Path
from uuid import uuid4
from trial_chat import handle_chat
from typing import Optional
from db import (
    init_db,
    save_lead,
    save_google_tokens,
    get_google_tokens,
    delete_google_tokens,
    save_meta_tokens,
    get_meta_tokens,
    delete_meta_tokens,
    save_meta_pages,
    get_meta_pages,
    get_meta_page,
    save_meta_message,
    get_meta_conversations,
    get_meta_conversation,
    get_meta_messages,
    mark_meta_conversation_read,
    mark_meta_messages_delivered,
    mark_meta_messages_read,
    save_chat_message,
    get_chat_history,
    update_meta_conversation_profile,
    save_meta_message_reaction,
    delete_meta_message_reaction,
    get_meta_reactions_for_messages
)

load_dotenv()

DIRECT_UPLOAD_ROOT = Path(
    os.getenv(
        "RAILWAY_VOLUME_MOUNT_PATH",
        "."
    )
) / "direct_uploads"

DIRECT_UPLOAD_ROOT.mkdir(
    parents=True,
    exist_ok=True
)

DIRECT_FILE_MAX_BYTES = 25 * 1024 * 1024

DIRECT_BLOCKED_EXTENSIONS = {
    ".exe",
    ".bat",
    ".cmd",
    ".msi",
    ".sh",
    ".php",
    ".js"
}

DIRECT_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp"
}

DIRECT_IMAGE_MAX_BYTES = 8 * 1024 * 1024

APP_PUBLIC_URL = os.getenv(
    "APP_PUBLIC_URL",
    "https://sitechat-production.up.railway.app"
).rstrip("/")

app = FastAPI()

init_db()


@app.get("/chat-widget", include_in_schema=False)
async def chat_widget():
    return FileResponse(Path(__file__).with_name("chat_widget.html"))

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL = "openai/gpt-4o-mini"
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")
CRM_URL = os.getenv("CRM_URL", "http://127.0.0.1:5500/index.html")
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/userinfo.email",
    "https://mail.google.com/",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/presentations",
    "https://www.googleapis.com/auth/drive",
]

def get_direct_attachment_type(content_type: str, filename: str = ""):
    content_type = str(content_type or "").lower()
    filename = str(filename or "").lower()

    if content_type.startswith("image/"):
        return "image"

    if content_type.startswith("video/"):
        return "video"

    if content_type.startswith("audio/"):
        return "audio"

    return "file"


def get_direct_file_extension(filename: str, content_type: str = ""):
    filename = Path(str(filename or "")).name
    suffix = Path(filename).suffix.lower()

    if suffix and len(suffix) <= 12:
        return suffix

    content_type = str(content_type or "").lower()

    guessed = {
        "application/pdf": ".pdf",
        "application/zip": ".zip",
        "application/x-zip-compressed": ".zip",
        "application/x-rar-compressed": ".rar",
        "application/x-7z-compressed": ".7z",
        "text/plain": ".txt",
        "application/msword": ".doc",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
        "application/vnd.ms-excel": ".xls",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
        "application/vnd.ms-powerpoint": ".ppt",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx"
    }.get(content_type)

    return guessed or ".bin"


async def save_direct_upload_file(upload: UploadFile):
    original_name = Path(upload.filename or "file").name
    content_type = str(upload.content_type or "application/octet-stream").lower()

    extension = get_direct_file_extension(
        filename=original_name,
        content_type=content_type
    )

    if extension in DIRECT_BLOCKED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Цей тип файлу заблоковано з міркувань безпеки."
        )

    file_bytes = await upload.read()

    if not file_bytes:
        raise HTTPException(
            status_code=400,
            detail="Файл порожній."
        )

    if len(file_bytes) > DIRECT_FILE_MAX_BYTES:
        raise HTTPException(
            status_code=400,
            detail="Файл завеликий. Максимальний розмір — 25 МБ."
        )

    safe_original = safe_download_filename(
        original_name,
        f"direct-file{extension}"
    )

    if "." not in safe_original:
        safe_original += extension

    stored_filename = f"{uuid4().hex}_{safe_original}"
    stored_path = DIRECT_UPLOAD_ROOT / stored_filename

    stored_path.write_bytes(file_bytes)

    public_url = (
        f"{APP_PUBLIC_URL}"
        f"/api/meta/direct/media/"
        f"{stored_filename}"
    )

    return {
        "original_name": original_name,
        "stored_filename": stored_filename,
        "stored_path": stored_path,
        "url": public_url,
        "content_type": content_type,
        "size": len(file_bytes),
        "attachment_type": get_direct_attachment_type(
            content_type,
            original_name
        )
    }

META_APP_ID = os.getenv("META_APP_ID", "")
META_APP_SECRET = os.getenv("META_APP_SECRET", "")
META_REDIRECT_URI = os.getenv(
    "META_REDIRECT_URI",
    "https://sitechat-production.up.railway.app/api/meta/callback"
)
META_VERIFY_TOKEN = os.getenv("META_VERIFY_TOKEN", "itenai_meta_verify_2026")

META_GRAPH_VERSION = os.getenv("META_GRAPH_VERSION", "v25.0")
META_GRAPH_URL = f"https://graph.facebook.com/{META_GRAPH_VERSION}"

def build_meta_send_request_body(
    platform: str,
    page_id: str,
    participant_id: str,
    message_payload: dict
):
    conversation = get_meta_conversation(
        page_id=page_id,
        participant_id=participant_id,
        platform=platform
    )

    if not conversation:
        return None, {
            "success": False,
            "error": (
                "Діалог не знайдено в CRM. "
                "Спочатку клієнт має написати повідомлення."
            )
        }

    last_message_at = int(
        conversation.get("last_message_at") or 0
    )

    if last_message_at <= 0:
        return None, {
            "success": False,
            "error": (
                "Немає дати останнього повідомлення клієнта. "
                "Попросіть клієнта написати ще раз."
            )
        }

    now_ms = int(time.time() * 1000)
    age_ms = now_ms - last_message_at

    day_1_ms = 24 * 60 * 60 * 1000
    day_7_ms = 7 * 24 * 60 * 60 * 1000

    request_body = {
        "recipient": {
            "id": participant_id
        },
        "message": message_payload
    }

    if age_ms <= day_1_ms:
        request_body["messaging_type"] = "RESPONSE"
        return request_body, None

    if age_ms <= day_7_ms:
        request_body["messaging_type"] = "MESSAGE_TAG"
        request_body["tag"] = "HUMAN_AGENT"
        return request_body, None

    return None, {
        "success": False,
        "error": (
            "Вікно відповіді Meta закрите. "
            "Клієнт має написати першим, після цього знову можна буде "
            "відправляти повідомлення, фото та файли."
        )
    }

META_SCOPES = [
    "public_profile",
    "email",
    "business_management",
    "ads_read",
    "ads_management",

    "pages_show_list",
    "pages_read_engagement",
    "pages_read_user_content",
    "pages_manage_engagement",
    "pages_manage_metadata",
    "pages_messaging",
    "read_insights",
    "pages_manage_ads",

    "instagram_basic",
    "instagram_manage_comments",
    "instagram_manage_insights",
    "instagram_manage_messages",
    "instagram_content_publish"
]

class InstagramCommentReplyRequest(BaseModel):
    instagram_id: str
    comment_id: str
    message: str


class InstagramCommentVisibilityRequest(BaseModel):
    instagram_id: str
    comment_id: str
    hide: bool


class InstagramCommentDeleteRequest(BaseModel):
    instagram_id: str
    comment_id: str

class FacebookCommentReplyRequest(BaseModel):
    page_id: str
    comment_id: str
    message: str


class FacebookCommentVisibilityRequest(BaseModel):
    page_id: str
    comment_id: str
    hidden: bool


class FacebookCommentDeleteRequest(BaseModel):
    page_id: str
    comment_id: str

class MetaMessageReactionRequest(BaseModel):
    mid: str
    platform: str
    page_id: str
    participant_id: str
    reaction: str

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SYSTEM_PROMPT = """
Ти менеджер онлайн школи ItEnAi School.

Відповідай коротко, дружньо і по суті.
Допомагай підібрати курс і підводь до запису.

ВАЖЛИВО:
- Завжди звертайтесь до батьків формально — використовуйте форму "Ви", "Ваш", "Ваша", "Ваші".
- Пишіть грамотно літературною українською мовою.
- Починайте кожне речення з великої літери.
- Уникайте розмовних формулювань та сленгу.
- Не використовуйте частини речення з малої літери після знака питання або крапки.
- Не починайте діалог заново.
- Не вітайтесь повторно.
- Якщо клієнт уже відповів — продовжуйте розмову.

Не вигадуйте курси.
Використовуйте тільки ці напрямки:
Adobe Photoshop, Adobe After Effects, штучний інтелект, цифровий дизайн.

Ніколи не згадуйте користувачу базу знань, відсутність даних у базі або те, що Ви чогось не знаєте.
Якщо для точної відповіді бракує інформації, напишіть: «За більш детальною інформацією зверніться до менеджера» та запропонуйте зв'язатися з менеджером.

Якщо дитина цікавиться малюванням, ілюстраціями або обробкою фото — рекомендуйте Photoshop або цифровий дизайн.
Якщо дитина цікавиться анімацією, відео чи візуальними ефектами — рекомендуйте After Effects.

Додатково: не називайте вартість курсів у відповідях та описах, якщо користувач прямо не питає про ціну.
Якщо користувач запитує про ціну — надавайте інформацію лаконічно.
"""

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    source: str = "website_chat"

async def _chat_response(req: ChatRequest, history=None):

    msg = req.message
    msg_lower = msg.lower()

    # 🔍 ТИП ПИТАННЯ
    is_why = any(x in msg_lower for x in ["чому", "навіщо"])
    is_interest = any(x in msg_lower for x in ["цікаво", "цікавого", "цікавий", "чим цікавий"])
    is_price = any(x in msg_lower for x in ["ціна", "вартість", "скільки"])
    is_time = any(x in msg_lower for x in ["час", "коли", "наскільки"])
    words = msg_lower.split()

    is_signup = any(x in words for x in ["так", "да", "ок", "ага", "хочу", "запис", "записатись", "давайте"])

    # 🎯 ВИБІР КУРСУ
    course_photoshop = any(x in msg_lower for x in ["photoshop", "фотошоп", "малю", "ілюстрац", "обробк", "фото", "колаж"])
    course_after_effects = any(x in msg_lower for x in ["after effects", "aftereffects", "афтер ефект", "афтерефект", "моушн", "анімац", "відеоефект", "відео"])
    course_digital_design = any(x in msg_lower for x in ["цифровий дизайн", "графічн", "дизайн", "макет", "типограф"])
    course_roblox = False
    course_python = False
    course_3d = False
    course_ai = any(x in msg_lower for x in ["ai", "штучний", "інтелект"])
    course_blog = False
    course_pc = False

    if course_photoshop:
        return {"response": "🎨 Adobe Photoshop\n• цифрове малювання та ілюстрації\n• обробка фотографій і колажі\n• робота з кольором, шарами та масками\n\nЦей напрям добре підійде дитині, яка любить малювати та створювати візуальні роботи."}

    if course_after_effects:
        return {"response": "🎬 Adobe After Effects\n• анімація та моушн-дизайн\n• візуальні ефекти й титри\n• створення коротких відеопроєктів"}

    if course_digital_design:
        return {"response": "✨ Цифровий дизайн\n• композиція та робота з кольором\n• типографіка\n• створення цифрових макетів і власного портфоліо"}


    if "що таке" in msg_lower or "що це" in msg_lower:

        if course_python:
            return {"response": "Python — це мова програмування, на якій діти створюють ігри, програми та навіть AI 🤖"}

        if course_roblox:
            return {"response": "Roblox — це платформа де діти створюють свої ігри 🎮 та вчаться програмувати"}

        if course_ai:
            return {"response": "AI — це штучний інтелект 🤖 Діти вчаться створювати свої AI-проекти"}

        if course_3d:
            return {"response": "3D-моделювання — це створення об'ємних моделей у Blender 🎨"}

        if course_blog:
            return {"response": "Блогінг — це створення відео, монтаж і розвиток власного каналу 📹"}

    if is_why and course_roblox:
        return {"response": "Roblox — це не просто гра 👇\n\n• створення ігор\n• програмування\n• креативність\n\nЦе легкий старт в IT 🔥"}

    if is_why and course_python:
        return {"response": "Python — основа програмування 👇\n\n• логіка\n• реальні навички\n• IT напрям\n\nСильний фундамент 🔥"}

    if is_why and course_3d:
        return {"response": "3D — це творчість 👇\n\n• створення моделей\n• робота в Blender\n• креативність\n\nДітям дуже подобається 🎨"}

    if is_why and course_ai:
        return {"response": "AI — технології майбутнього 👇\n\n• нейромережі\n• генерація контенту\n• сучасні навички\n\nДуже перспективно 🔥"}

    if is_why and course_blog:
        return {"response": "Блогінг — сучасний навик 👇\n\n• відео\n• монтаж\n• впевненість\n\nДуже актуально 📱"}

    if is_why and course_pc:
        return {"response": "Комп’ютерна грамотність — база 👇\n\n• робота з ПК\n• інтернет\n• безпека\n\nФундамент 👍"}

    if is_signup and not (course_python or course_roblox or course_ai or course_3d or course_blog or course_pc):
        return {
            "response": (
                "Супер 👍\n\n"
                "Напишіть, будь ласка:\n• ім’я\n• вік\n\n"
                "і підберемо зручний час 👇"
            )
        }

    if is_interest and course_roblox:
        return {"response": "Дітям подобається 👇\n\n• створюють свої ігри\n• грають у свої проєкти\n• показують друзям 🔥"}

    if is_interest and course_python:
        return {"response": "Цікаво тим що 👇\n\n• створюєш програми\n• вирішуєш задачі\n• відчуваєш себе програмістом 😎"}

    if is_interest and course_3d:
        return {"response": "Найцікавіше 👇\n\n• створення персонажів\n• як у іграх\n• швидкий результат 🎮"}

    if is_interest and course_ai:
        return {"response": "Вау ефект 👇\n\n• генеруєш картинки\n• працюєш з AI\n• сучасні технології 🤯"}

    if is_interest and course_blog:
        return {"response": "Що подобається 👇\n\n• зйомка\n• монтаж\n• власний контент 🎥"}

    if is_interest and course_pc:
        return {"response": "Цікаво тим що 👇\n\n• швидко вчишся користуватись ПК\n• впевненість\n• практичні навички 👍"}

    if course_roblox and not ("що" in msg_lower or "чому" in msg_lower):
        return {"response": "🎮 Roblox\n• створення власних проєктів і ігор\n• цікаві карти та механіки\n• Lua-програмування для дітей\n• практичні завдання"}

    if course_python and not ("що" in msg_lower or "чому" in msg_lower):
        return {"response": "💻 Python\n• програмування на базі пайтон\n• логіка, цікаві візуальні ігри\n• проекти, завдання"}

    if course_3d and not ("що" in msg_lower or "чому" in msg_lower):
        return {"response": "🎨 3D\n• працюємо в Blender\n• створюємо моделі та персонажів\n• проєкти та персональні задачі зі створення моделей"}

    if course_ai and not ("що" in msg_lower or "чому" in msg_lower):
        return {"response": "🤖 AI\n• нейромережі, їх поведінка їхні задачі та завдання\n• проекти, навчанню штучного інтелекту, як з ним комунікувати правильно"}

    if course_blog and not ("що" in msg_lower or "чому" in msg_lower):
        return {"response": "📹 Блогінг\n• відео, уроки\n• монтаж, навчання правильного монтажу"}

    if course_pc and not ("що" in msg_lower or "чому" in msg_lower):
        return {"response": "💻 Комп’ютерна грамотність\n• навчання базовим навичкам роботи з ПК\n• що таке персональний комп'ютер\n• інтернет та передача даних\n• безпека та захист від шкідливого ПЗ"}


    # 📚 СПИСОК КУРСІВ
    if "курси" in msg_lower or "список" in msg_lower or "що є" in msg_lower:
        return {
            "response": (
                "🎨 Adobe Photoshop — цифрове малювання та обробка фото\n"
                "🎬 Adobe After Effects — анімація, відео та візуальні ефекти\n"
                "🤖 Штучний інтелект — робота з ChatGPT і нейромережами\n"
                "✨ Цифровий дизайн — композиція, колір і створення макетів\n\n"
                "Чи можете сказати, що більше подобається — і я підкажу найкращий варіант 👍"
            )
        }

    # 💰 ЦІНА
    if "скільки" in msg_lower or "ціна" in msg_lower or "вартість" in msg_lower:
        return {
            "response": (
                "💰 Вартість одного заняття:\n"
                "• Індивідуальне заняття — 450 грн\n"
                "• Заняття в мінігрупі до 4 учнів — 250 грн з учня\n\n"
                "Хочете — підкажу, який формат краще підійде саме для вашої дитини 👇"
            )
        }

    # 📞 ТЕЛЕФОН
    if "телефон" in msg_lower or "номер" in msg_lower or "контакт" in msg_lower:
        return {
            "response": (
                "📞 Менеджер школи:\n"
                "+380931480343\n\n"
                "Можете написати або подзвонити у зручний час 👍"
            )
        }

    # 🧾 ІМ'Я + ВІК
    if any(x in msg_lower for x in ["рок", "рік", "років"]):
        return {
            "response": (
                "Супер 👍\n\n"
                "Фіксую заявку 👍\n\n"
                "Підберемо зручний час 👇"
            )
        }

    # 🤔 НЕЗРОЗУМІЛО
    if len(msg_lower) < 3:
        return {
            "response": "Трохи не зрозуміли 🙂 Напишіть, що саме Вас цікавить: курс, ціна чи запис 👇"
        }

    # 🤷 НЕ ЗНАЄ
    if "не знаю" in msg_lower:
        return {
            "response": (
                "Нічого страшного 🙂\n\n"
                "Якщо коротко:\n"
                "🎨 малювання та фото → Photoshop\n"
                "🎬 анімація та відео → After Effects\n"
                "🤖 нейромережі → штучний інтелект\n"
                "✨ макети та візуальне оформлення → цифровий дизайн\n\n"
                "Що ближче?"
            )
        }

    # 🔄 ВЖЕ ПРОБУВАЛИ / ПРОХОДИЛИ
    if any(x in msg_lower for x in ["проходили", "вже пробували", "пробували"]):
        return {
            "response": (
                "Якщо один напрям уже пробували, можемо підібрати інший із доступних: "
                "Photoshop, After Effects, штучний інтелект або цифровий дизайн. "
                "Підкажіть, що дитині подобається найбільше?"
            )
        }

    # ⏰ ПРО ЧАС
    if is_time:
        return {
            "response": (
                "Маємо зручні варіанти 👇\n\n"
                "🕓 вдень: 11:00–17:00\n"
                "🌙 ввечері: 17:00–21:00\n\n"
                "Можемо записати вже на завтра 👍\n\n"
                "Який варіант вам підходить?"
            )
        }

    # 📅 ФІНАЛЬНЕ ЗАКРИТТЯ ЗАЯВКИ
    if any(x in msg_lower for x in ["завтра", "сьогодні", "на завтра"]):
        return {
            "response": (
                "Супер 👍\n\n"
                "Записали на пробний урок 👇\n\n"
                "📅 Завтра\n"
                "🕓 Час узгодимо додатково\n\n"
                "Менеджер зв’яжеться з вами для підтвердження 👍"
            )
        }

    # 🕓 КОНКРЕТНИЙ ЧАС
    import re
    if re.search(r"(?<!\d)(?:[01]?\d|2[0-3])(?:[:.]\d{2})?(?!\d)", msg_lower):
        return {
            "response": (
                "Чудово 🙌\n\n"
                "Записали на цей час 👍\n\n"
                "Менеджер підтвердить запис найближчим часом"
            )
        }

    # 💾 ЗБЕРЕЖЕННЯ
    save_lead("site", msg)

    # 🔑 перевірка ключа
    if not OPENROUTER_API_KEY:
        return {"response": "Помилка сервера: не налаштовано API ключ"}

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            *(history or []),
            {"role": "user", "content": msg}
        ]
    }

    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload
            )

        data = r.json()

        if "choices" not in data:
            return {"response": "Сталася помилка AI. Спробуйте ще раз."}

        return {"response": data["choices"][0]["message"]["content"]}

    except Exception:
        return {"response": "Сервер тимчасово недоступний. Спробуйте ще раз пізніше."}


async def _answer_school_question(message, history):
    if not OPENROUTER_API_KEY:
        return "Зараз AI-консультація тимчасово недоступна. Можу передати Ваше запитання менеджеру."
    knowledge = Path(__file__).with_name("ITENAISchool_knowledge_base_FULL.json").read_text(encoding="utf-8")
    manager_prompt = Path(__file__).with_name("ITENAISchool_AI_manager_prompt.txt").read_text(encoding="utf-8")
    prompt = f"{manager_prompt}\n\nСЛУЖБОВА БАЗА ЗНАНЬ:\n{knowledge}"
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": prompt},
            *(history or []),
            {"role": "user", "content": message}
        ]
    }
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            result = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"},
                json=payload
            )
        data = result.json()
        ai_answer = data["choices"][0]["message"]["content"]
        restricted_phrases = [
            "база знань", "базі знань", "у базі", "в базі",
            "немає інформації", "відсутня інформація",
            "не маю інформації", "не знаю"
        ]
        if any(phrase in ai_answer.lower() for phrase in restricted_phrases):
            return (
                "За більш детальною інформацією зверніться до менеджера. "
                "📞 +380 93 148 03 43"
            )
        return ai_answer
    except Exception:
        return "Не вдалося отримати відповідь AI. Спробуйте ще раз або зв'яжіться з менеджером."


@app.post("/chat")
async def chat(req: ChatRequest, request: Request, response: Response):
    forwarded_for = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
    client_ip = forwarded_for or (request.client.host if request.client else "unknown")
    fingerprint_source = "|".join([
        client_ip,
        request.headers.get("User-Agent", "unknown"),
        request.headers.get("Origin", "unknown")
    ])
    fallback_session_id = "web:" + hashlib.sha256(
        fingerprint_source.encode("utf-8")
    ).hexdigest()[:32]
    session_id = (
        req.session_id
        or request.headers.get("X-Chat-Session")
        or request.cookies.get("chat_session_id")
        or fallback_session_id
    )[:128]
    history = get_chat_history(session_id)
    result = handle_chat(session_id, req.message, req.source)
    if result.pop("needs_ai", False):
        ai_text = await _answer_school_question(req.message, history)
        result["response"] = ai_text
        result["message"] = ai_text
    save_chat_message(session_id, "user", req.message)
    save_chat_message(session_id, "assistant", result["response"])
    response.set_cookie(
        "chat_session_id",
        session_id,
        max_age=60 * 60 * 24 * 30,
        httponly=True,
        samesite="lax",
        secure=APP_PUBLIC_URL.startswith("https://")
    )
    result["session_id"] = session_id
    return result


@app.get("/api/google/status")
async def google_status():
    tokens = get_google_tokens()

    return {
        "configured": bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET and GOOGLE_REDIRECT_URI),
        "connected": bool(tokens),
        "email": tokens["email"] if tokens else None
    }


@app.get("/api/google/login")
async def google_login():
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET or not GOOGLE_REDIRECT_URI:
        return {"error": "Google OAuth змінні не налаштовані в Railway"}

    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(GOOGLE_SCOPES),
        "access_type": "offline",
        "prompt": "consent"
    }

    google_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)

    return RedirectResponse(google_url)


@app.get("/api/google/callback")
async def google_callback(code: str):
    async with httpx.AsyncClient() as client:
        token_res = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code"
            }
        )

        token_data = token_res.json()

        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token")

        if not access_token:
            return {
                "success": False,
                "error": "Не вдалося отримати access_token",
                "details": token_data
            }

        user_res = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={
                "Authorization": f"Bearer {access_token}"
            }
        )

        user_data = user_res.json()
        email = user_data.get("email", "unknown@gmail.com")

        save_google_tokens(
            email=email,
            access_token=access_token,
            refresh_token=refresh_token
        )

        redirect_url = CRM_URL + ("&" if "?" in CRM_URL else "?") + urlencode({
            "page": "integrations",
            "google": "connected",
            "open": "googlehub",
            "email": email
        })

        return RedirectResponse(redirect_url)

@app.post("/api/google/disconnect")
async def google_disconnect():
    delete_google_tokens()
    return {
        "success": True,
        "message": "Google акаунт відключено"
    }

def extract_gmail_header(headers_list, name):
    for item in headers_list or []:
        if item.get("name", "").lower() == name.lower():
            return item.get("value", "")
    return ""


async def get_valid_google_access_token():
    tokens = get_google_tokens()

    if not tokens:
        raise HTTPException(
            status_code=401,
            detail="Google акаунт не підключено"
        )

    access_token = tokens.get("access_token")
    refresh_token = tokens.get("refresh_token")
    email = tokens.get("email")

    if not refresh_token:
        return {
            "access_token": access_token,
            "email": email
        }

    async with httpx.AsyncClient(timeout=20) as client:
        refresh_res = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token"
            }
        )

    if refresh_res.status_code != 200:
        return {
            "access_token": access_token,
            "email": email
        }

    refresh_data = refresh_res.json()
    new_access_token = refresh_data.get("access_token")

    if new_access_token:
        save_google_tokens(
            email=email,
            access_token=new_access_token,
            refresh_token=refresh_token
        )

        return {
            "access_token": new_access_token,
            "email": email
        }

    return {
        "access_token": access_token,
        "email": email
    }


@app.get("/api/google/gmail/list")
async def google_gmail_list(max_results: int = 10, q: str = ""):
    auth = await get_valid_google_access_token()
    access_token = auth["access_token"]

    params = {
        "maxResults": max(1, min(max_results, 25))
    }

    if q:
        params["q"] = q

    async with httpx.AsyncClient(timeout=30) as client:
        list_res = await client.get(
            "https://gmail.googleapis.com/gmail/v1/users/me/messages",
            headers={
                "Authorization": f"Bearer {access_token}"
            },
            params=params
        )

        if list_res.status_code != 200:
            return {
                "success": False,
                "error": "Не вдалося отримати список Gmail",
                "details": list_res.json()
            }

        list_data = list_res.json()
        messages = list_data.get("messages", [])

        result = []

        for msg in messages:
            msg_id = msg.get("id")

            detail_res = await client.get(
                f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{msg_id}",
                headers={
                    "Authorization": f"Bearer {access_token}"
                },
                params={
                    "format": "metadata",
                    "metadataHeaders": ["From", "Subject", "Date"]
                }
            )

            if detail_res.status_code != 200:
                continue

            detail = detail_res.json()
            headers = detail.get("payload", {}).get("headers", [])

            result.append({
                "id": detail.get("id"),
                "threadId": detail.get("threadId"),
                "from": extract_gmail_header(headers, "From"),
                "subject": extract_gmail_header(headers, "Subject") or "(без теми)",
                "date": extract_gmail_header(headers, "Date"),
                "snippet": detail.get("snippet", "")
            })

    return {
        "success": True,
        "email": auth["email"],
        "messages": result
    }


@app.get("/api/google/calendar/list")
async def google_calendar_list(max_results: int = 20):
    auth = await get_valid_google_access_token()
    access_token = auth["access_token"]

    time_min = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.get(
            "https://www.googleapis.com/calendar/v3/calendars/primary/events",
            headers={
                "Authorization": f"Bearer {access_token}"
            },
            params={
                "timeMin": time_min,
                "singleEvents": "true",
                "orderBy": "startTime",
                "maxResults": max(1, min(max_results, 50))
            }
        )

    if res.status_code != 200:
        return {
            "success": False,
            "error": "Не вдалося отримати події календаря",
            "details": res.json()
        }

    events = []

    for item in res.json().get("items", []):
        events.append({
            "id": item.get("id"),
            "summary": item.get("summary", "(без назви)"),
            "description": item.get("description", ""),
            "location": item.get("location", ""),
            "start": item.get("start", {}),
            "end": item.get("end", {}),
            "htmlLink": item.get("htmlLink", "")
        })

    return {
        "success": True,
        "email": auth["email"],
        "events": events
    }


class HubTranslateRequest(BaseModel):
    text: str
    target: str = "uk"


@app.post("/api/google/translate")
async def hub_translate(req: HubTranslateRequest):
    if not OPENROUTER_API_KEY:
        return {
            "success": False,
            "error": "Не налаштовано OPENROUTER_API_KEY"
        }

    prompt = (
        f"Переклади текст мовою {req.target}. "
        f"Поверни тільки переклад без пояснень.\n\n"
        f"Текст:\n{req.text}"
    )

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "system",
                "content": "Ти професійний перекладач. Повертаєш тільки переклад."
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
    }

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload
            )

        data = r.json()

        if "choices" not in data:
            return {
                "success": False,
                "error": "AI-перекладач не повернув відповідь",
                "details": data
            }

        return {
            "success": True,
            "translation": data["choices"][0]["message"]["content"]
        }

    except Exception as e:
        return {
            "success": False,
            "error": "Помилка AI-перекладача",
            "details": str(e)
        }


class HubGeminiRequest(BaseModel):
    prompt: str


@app.post("/api/google/gemini")
async def hub_gemini(req: HubGeminiRequest):
    if not OPENROUTER_API_KEY:
        return {
            "success": False,
            "error": "Не налаштовано OPENROUTER_API_KEY"
        }

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Ти AI-помічник CRM школи ItEnAi. "
                    "Допомагай з листами, заявками, текстами, підсумками та відповідями клієнтам."
                )
            },
            {
                "role": "user",
                "content": req.prompt
            }
        ]
    }

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload
            )

        data = r.json()

        if "choices" not in data:
            return {
                "success": False,
                "error": "AI не повернув відповідь",
                "details": data
            }

        return {
            "success": True,
            "answer": data["choices"][0]["message"]["content"]
        }

    except Exception as e:
        return {
            "success": False,
            "error": "Помилка AI",
            "details": str(e)
        }


@app.get("/api/google/drive/files")
async def google_drive_files(type: str = "workspace", page_size: int = 50, search: str = ""):
    auth = await get_valid_google_access_token()
    access_token = auth["access_token"]

    mime_map = {
        "sheets": "application/vnd.google-apps.spreadsheet",
        "docs": "application/vnd.google-apps.document",
        "slides": "application/vnd.google-apps.presentation",
        "folders": "application/vnd.google-apps.folder",
        "pdf": "application/pdf"
    }

    query_parts = ["trashed = false"]

    if type in mime_map:
        query_parts.append(f"mimeType = '{mime_map[type]}'")

    elif type == "workspace":
        query_parts.append(
            "("
            "mimeType = 'application/vnd.google-apps.spreadsheet' "
            "or mimeType = 'application/vnd.google-apps.document' "
            "or mimeType = 'application/vnd.google-apps.presentation'"
            ")"
        )

    elif type == "images":
        query_parts.append("mimeType contains 'image/'")

    elif type == "all":
        pass

    else:
        pass

    if search:
        safe_search = search.replace("'", "\\'")
        query_parts.append(f"name contains '{safe_search}'")

    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.get(
            "https://www.googleapis.com/drive/v3/files",
            headers={
                "Authorization": f"Bearer {access_token}"
            },
            params={
                "q": " and ".join(query_parts),
                "pageSize": max(1, min(page_size, 100)),
                "orderBy": "modifiedTime desc",
                "fields": "files(id,name,mimeType,webViewLink,webContentLink,iconLink,createdTime,modifiedTime,size)"
            }
        )

    if res.status_code != 200:
        return {
            "success": False,
            "error": "Не вдалося отримати список Google Drive",
            "details": res.json()
        }

    files = res.json().get("files", [])

    return {
        "success": True,
        "email": auth["email"],
        "type": type,
        "files": files
    }


@app.get("/api/google/calendar/list")
async def google_calendar_list(max_results: int = 20):
    auth = await get_valid_google_access_token()
    access_token = auth["access_token"]

    time_min = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.get(
            "https://www.googleapis.com/calendar/v3/calendars/primary/events",
            headers={
                "Authorization": f"Bearer {access_token}"
            },
            params={
                "timeMin": time_min,
                "singleEvents": "true",
                "orderBy": "startTime",
                "maxResults": max(1, min(max_results, 50))
            }
        )

    if res.status_code != 200:
        return {
            "success": False,
            "error": "Не вдалося отримати події календаря",
            "details": res.json()
        }

    events = []

    for item in res.json().get("items", []):
        events.append({
            "id": item.get("id"),
            "summary": item.get("summary", "(без назви)"),
            "description": item.get("description", ""),
            "location": item.get("location", ""),
            "start": item.get("start", {}),
            "end": item.get("end", {}),
            "htmlLink": item.get("htmlLink", "")
        })

    return {
        "success": True,
        "email": auth["email"],
        "events": events
    }


class SheetCreateRequest(BaseModel):
    title: str = "ItEnAi CRM — Ліди"


@app.post("/api/google/sheets/create")
async def google_sheets_create(req: SheetCreateRequest):
    auth = await get_valid_google_access_token()
    access_token = auth["access_token"]

    payload = {
        "properties": {
            "title": req.title
        },
        "sheets": [
            {
                "properties": {
                    "title": "Ліди"
                }
            }
        ]
    }

    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.post(
            "https://sheets.googleapis.com/v4/spreadsheets",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            },
            json=payload
        )

    if res.status_code not in [200, 201]:
        return {
            "success": False,
            "error": "Не вдалося створити Google Sheet",
            "details": res.json()
        }

    sheet = res.json()
    spreadsheet_id = sheet.get("spreadsheetId")

    async with httpx.AsyncClient(timeout=30) as client:
        await client.put(
            f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/Ліди!A1:E1",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            },
            params={
                "valueInputOption": "USER_ENTERED"
            },
            json={
                "values": [[
                    "Дата",
                    "Імʼя",
                    "Телефон",
                    "Курс",
                    "Коментар"
                ]]
            }
        )

    return {
        "success": True,
        "spreadsheetId": spreadsheet_id,
        "spreadsheetUrl": sheet.get("spreadsheetUrl"),
        "title": req.title
    }


class CalendarCreateRequest(BaseModel):
    summary: str
    description: str = ""
    start: str
    end: str
    location: str = ""


@app.post("/api/google/calendar/create")
async def google_calendar_create(req: CalendarCreateRequest):
    auth = await get_valid_google_access_token()
    access_token = auth["access_token"]

    payload = {
        "summary": req.summary,
        "description": req.description,
        "location": req.location,
        "start": {
            "dateTime": req.start,
            "timeZone": "Europe/Kyiv"
        },
        "end": {
            "dateTime": req.end,
            "timeZone": "Europe/Kyiv"
        }
    }

    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.post(
            "https://www.googleapis.com/calendar/v3/calendars/primary/events",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            },
            json=payload
        )

    if res.status_code not in [200, 201]:
        return {
            "success": False,
            "error": "Не вдалося створити подію Google Calendar",
            "details": res.json()
        }

    event = res.json()

    return {
        "success": True,
        "message": "Подію створено в Google Calendar",
        "event": {
            "id": event.get("id"),
            "summary": event.get("summary"),
            "htmlLink": event.get("htmlLink"),
            "start": event.get("start"),
            "end": event.get("end")
        }
    }


def decode_gmail_body(data: str) -> str:
    if not data:
        return ""

    try:
        padding = "=" * (-len(data) % 4)
        decoded = base64.urlsafe_b64decode((data + padding).encode("utf-8"))
        return decoded.decode("utf-8", errors="ignore")
    except Exception:
        return ""


def find_gmail_body(payload: dict) -> str:
    if not payload:
        return ""

    mime_type = payload.get("mimeType", "")
    body_data = payload.get("body", {}).get("data")

    if body_data and ("text/plain" in mime_type or "text/html" in mime_type):
        return decode_gmail_body(body_data)

    for part in payload.get("parts", []) or []:
        found = find_gmail_body(part)
        if found:
            return found

    return ""


@app.get("/api/google/gmail/read/{message_id}")
async def google_gmail_read(message_id: str):
    auth = await get_valid_google_access_token()
    access_token = auth["access_token"]

    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.get(
            f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{message_id}",
            headers={
                "Authorization": f"Bearer {access_token}"
            },
            params={
                "format": "full"
            }
        )

    if res.status_code != 200:
        return {
            "success": False,
            "error": "Не вдалося прочитати лист Gmail",
            "details": res.json()
        }

    data = res.json()
    headers = data.get("payload", {}).get("headers", [])

    return {
        "success": True,
        "message": {
            "id": data.get("id"),
            "threadId": data.get("threadId"),
            "from": extract_gmail_header(headers, "From"),
            "to": extract_gmail_header(headers, "To"),
            "subject": extract_gmail_header(headers, "Subject") or "(без теми)",
            "date": extract_gmail_header(headers, "Date"),
            "snippet": data.get("snippet", ""),
            "body": find_gmail_body(data.get("payload", {}))
        }
    }

@app.delete("/api/google/gmail/delete/{message_id}")
async def google_gmail_delete(message_id: str):
    clean_message_id = str(message_id or "").strip()

    if not clean_message_id:
        return {
            "success": False,
            "error": "Не передано ID листа Gmail."
        }

    auth = await get_valid_google_access_token()
    access_token = auth["access_token"]

    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.post(
            f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{clean_message_id}/trash",
            headers={
                "Authorization": f"Bearer {access_token}"
            }
        )

    if res.status_code not in [200, 204]:
        try:
            details = res.json()
        except Exception:
            details = res.text

        return {
            "success": False,
            "error": "Не вдалося перенести лист у кошик Gmail.",
            "status_code": res.status_code,
            "details": details
        }

    return {
        "success": True,
        "message_id": clean_message_id,
        "deleted": True,
        "action": "moved_to_gmail_trash"
    }

class GoogleDocCreateRequest(BaseModel):
    title: str = "ItEnAi CRM Документ"
    text: str = ""

@app.delete("/api/google/gmail/delete-forever/{message_id}")
async def google_gmail_delete_forever(message_id: str):
    clean_message_id = str(message_id or "").strip()

    if not clean_message_id:
        return {
            "success": False,
            "error": "Не передано ID листа Gmail."
        }

    auth = await get_valid_google_access_token()
    access_token = auth["access_token"]

    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.delete(
            f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{clean_message_id}",
            headers={
                "Authorization": f"Bearer {access_token}"
            }
        )

    if res.status_code not in [200, 204]:
        try:
            details = res.json()
        except Exception:
            details = res.text

        return {
            "success": False,
            "error": "Не вдалося видалити лист назавжди.",
            "status_code": res.status_code,
            "details": details
        }

    return {
        "success": True,
        "message_id": clean_message_id,
        "deleted": True,
        "action": "permanently_deleted"
    }


@app.post("/api/google/docs/create")
async def google_docs_create(req: GoogleDocCreateRequest):
    auth = await get_valid_google_access_token()
    access_token = auth["access_token"]

    async with httpx.AsyncClient(timeout=30) as client:
        create_res = await client.post(
            "https://docs.googleapis.com/v1/documents",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            },
            json={
                "title": req.title
            }
        )

    if create_res.status_code not in [200, 201]:
        return {
            "success": False,
            "error": "Не вдалося створити Google Doc",
            "details": create_res.json()
        }

    doc = create_res.json()
    document_id = doc.get("documentId")

    if req.text:
        async with httpx.AsyncClient(timeout=30) as client:
            text_res = await client.post(
                f"https://docs.googleapis.com/v1/documents/{document_id}:batchUpdate",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                },
                json={
                    "requests": [
                        {
                            "insertText": {
                                "location": {
                                    "index": 1
                                },
                                "text": req.text
                            }
                        }
                    ]
                }
            )

        if text_res.status_code not in [200, 201]:
            return {
                "success": False,
                "error": "Документ створено, але текст не вдалося вставити",
                "documentUrl": f"https://docs.google.com/document/d/{document_id}/edit",
                "details": text_res.json()
            }

    return {
        "success": True,
        "documentId": document_id,
        "title": req.title,
        "documentUrl": f"https://docs.google.com/document/d/{document_id}/edit"
    }

class GoogleSlidesCreateRequest(BaseModel):
    title: str = "ItEnAi CRM Презентація"


@app.post("/api/google/slides/create")
async def google_slides_create(req: GoogleSlidesCreateRequest):
    auth = await get_valid_google_access_token()
    access_token = auth["access_token"]

    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.post(
            "https://slides.googleapis.com/v1/presentations",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            },
            json={
                "title": req.title
            }
        )

    if res.status_code not in [200, 201]:
        return {
            "success": False,
            "error": "Не вдалося створити Google Slides презентацію",
            "details": res.json()
        }

    presentation = res.json()
    presentation_id = presentation.get("presentationId")

    return {
        "success": True,
        "presentationId": presentation_id,
        "title": req.title,
        "presentationUrl": f"https://docs.google.com/presentation/d/{presentation_id}/edit"
    }


@app.get("/api/google/slides/export-pptx/{presentation_id}")
async def google_slides_export_pptx(presentation_id: str):
    auth = await get_valid_google_access_token()
    access_token = auth["access_token"]

    async with httpx.AsyncClient(timeout=60) as client:
        res = await client.get(
            f"https://www.googleapis.com/drive/v3/files/{presentation_id}/export",
            headers={
                "Authorization": f"Bearer {access_token}"
            },
            params={
                "mimeType": "application/vnd.openxmlformats-officedocument.presentationml.presentation"
            }
        )

    if res.status_code != 200:
        return {
            "success": False,
            "error": "Не вдалося експортувати презентацію у PowerPoint",
            "details": res.text
        }

    return Response(
        content=res.content,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={
            "Content-Disposition": f'attachment; filename="itenai-presentation-{presentation_id}.pptx"'
        }
    )

def safe_download_filename(name: str, fallback: str = "itenai-file"):
    raw = str(name or "").strip()

    safe = "".join(
        ch for ch in raw
        if ch.isascii() and (ch.isalnum() or ch in ["-", "_", ".", " "])
    ).strip()

    safe = safe.replace(" ", "-")

    if not safe:
        safe = fallback

    return safe[:90]


GOOGLE_EXPORT_FORMATS = {
    "docx": {
        "mime": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "ext": "docx",
        "label": "Word"
    },
    "xlsx": {
        "mime": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "ext": "xlsx",
        "label": "Excel"
    },
    "pptx": {
        "mime": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "ext": "pptx",
        "label": "PowerPoint"
    },
    "pdf": {
        "mime": "application/pdf",
        "ext": "pdf",
        "label": "PDF"
    }
}


@app.get("/api/google/drive/export/{file_id}")
async def google_drive_export(file_id: str, format: str = "pdf", name: str = "itenai-file"):
    auth = await get_valid_google_access_token()
    access_token = auth["access_token"]

    export_info = GOOGLE_EXPORT_FORMATS.get(format)

    if not export_info:
        return {
            "success": False,
            "error": "Невідомий формат експорту",
            "allowed": list(GOOGLE_EXPORT_FORMATS.keys())
        }

    async with httpx.AsyncClient(timeout=60) as client:
        res = await client.get(
            f"https://www.googleapis.com/drive/v3/files/{file_id}/export",
            headers={
                "Authorization": f"Bearer {access_token}"
            },
            params={
                "mimeType": export_info["mime"]
            }
        )

    if res.status_code != 200:
        return {
            "success": False,
            "error": f"Не вдалося експортувати файл у {export_info['label']}",
            "details": res.text
        }

    filename = safe_download_filename(name, f"itenai-{file_id}")

    return Response(
        content=res.content,
        media_type=export_info["mime"],
        headers={
            "Content-Disposition": f'attachment; filename="{filename}.{export_info["ext"]}"'
        }
    )


@app.get("/api/google/drive/download/{file_id}")
async def google_drive_download(file_id: str):
    auth = await get_valid_google_access_token()
    access_token = auth["access_token"]

    async with httpx.AsyncClient(timeout=60) as client:
        meta_res = await client.get(
            f"https://www.googleapis.com/drive/v3/files/{file_id}",
            headers={
                "Authorization": f"Bearer {access_token}"
            },
            params={
                "fields": "id,name,mimeType"
            }
        )

        if meta_res.status_code != 200:
            return {
                "success": False,
                "error": "Не вдалося отримати дані файлу",
                "details": meta_res.text
            }

        meta = meta_res.json()
        mime_type = meta.get("mimeType", "application/octet-stream")
        name = meta.get("name", f"itenai-{file_id}")

        if mime_type.startswith("application/vnd.google-apps."):
            return {
                "success": False,
                "error": "Це Google Workspace файл. Для нього треба використовувати export, а не download."
            }

        file_res = await client.get(
            f"https://www.googleapis.com/drive/v3/files/{file_id}",
            headers={
                "Authorization": f"Bearer {access_token}"
            },
            params={
                "alt": "media"
            }
        )

    if file_res.status_code != 200:
        return {
            "success": False,
            "error": "Не вдалося скачати файл з Google Drive",
            "details": file_res.text
        }

    filename = safe_download_filename(name, f"itenai-{file_id}")

    return Response(
        content=file_res.content,
        media_type=mime_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )


@app.delete("/api/google/drive/files/{file_id}")
async def google_drive_file_delete(file_id: str):
    auth = await get_valid_google_access_token()
    access_token = auth["access_token"]

    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.patch(
            f"https://www.googleapis.com/drive/v3/files/{file_id}",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            },
            params={
                "fields": "id,name,trashed"
            },
            json={
                "trashed": True
            }
        )

    if res.status_code != 200:
        return {
            "success": False,
            "error": "Не вдалося перемістити файл у кошик Google Drive",
            "details": res.text
        }

    return {
        "success": True,
        "message": "Файл переміщено в кошик Google Drive",
        "file": res.json()
    }

@app.get("/api/meta/status")
async def meta_status():
    tokens = get_meta_tokens()

    return {
        "configured": bool(META_APP_ID and META_APP_SECRET and META_REDIRECT_URI),
        "connected": bool(tokens),
        "name": tokens.get("name") if tokens else None,
        "email": tokens.get("email") if tokens else None,
        "facebook_user_id": tokens.get("facebook_user_id") if tokens else None
    }


@app.get("/api/meta/login")
async def meta_login():
    if not META_APP_ID or not META_APP_SECRET or not META_REDIRECT_URI:
        return {
            "success": False,
            "error": "Meta variables не налаштовані в Railway."
        }

    params = {
        "client_id": META_APP_ID,
        "redirect_uri": META_REDIRECT_URI,
        "scope": ",".join(META_SCOPES),
        "response_type": "code",
        "auth_type": "rerequest"
    }

    login_url = f"https://www.facebook.com/{META_GRAPH_VERSION}/dialog/oauth?{urlencode(params)}"

    return RedirectResponse(login_url)


@app.get("/api/meta/callback")
async def meta_callback(code: str = None, error: str = None, error_description: str = None):
    if error:
        redirect_url = CRM_URL + ("&" if "?" in CRM_URL else "?") + urlencode({
            "page": "integrations",
            "meta": "error",
            "message": error_description or error
        })
        return RedirectResponse(redirect_url)

    if not code:
        return {
            "success": False,
            "error": "Meta не повернула code."
        }

    async with httpx.AsyncClient(timeout=40) as client:
        token_res = await client.get(
            f"{META_GRAPH_URL}/oauth/access_token",
            params={
                "client_id": META_APP_ID,
                "client_secret": META_APP_SECRET,
                "redirect_uri": META_REDIRECT_URI,
                "code": code
            }
        )

        token_data = token_res.json()
        access_token = token_data.get("access_token")

        if not access_token:
            return {
                "success": False,
                "error": "Не вдалося отримати Meta access_token.",
                "details": token_data
            }

        long_token_res = await client.get(
            f"{META_GRAPH_URL}/oauth/access_token",
            params={
                "grant_type": "fb_exchange_token",
                "client_id": META_APP_ID,
                "client_secret": META_APP_SECRET,
                "fb_exchange_token": access_token
            }
        )

        long_token_data = long_token_res.json()

        if long_token_data.get("access_token"):
            access_token = long_token_data.get("access_token")
            expires_in = long_token_data.get("expires_in")
            token_type = long_token_data.get("token_type")
        else:
            expires_in = token_data.get("expires_in")
            token_type = token_data.get("token_type")

        expires_at = int(time.time()) + int(expires_in or 0) if expires_in else None

        user_res = await client.get(
            f"{META_GRAPH_URL}/me",
            params={
                "fields": "id,name,email",
                "access_token": access_token
            }
        )

        user_data = user_res.json()

        facebook_user_id = user_data.get("id")
        name = user_data.get("name", "Meta User")
        email = user_data.get("email", "")

        save_meta_tokens(
            facebook_user_id=facebook_user_id,
            name=name,
            email=email,
            access_token=access_token,
            token_type=token_type,
            expires_at=expires_at
        )

        pages_res = await client.get(
            f"{META_GRAPH_URL}/me/accounts",
            params={
                "fields": "id,name,category,access_token,tasks",
                "limit": 100,
                "access_token": access_token
            }
        )

        pages_data = pages_res.json()
        pages = pages_data.get("data", [])

        save_meta_pages(pages)

    redirect_url = CRM_URL + ("&" if "?" in CRM_URL else "?") + urlencode({
        "page": "integrations",
        "meta": "connected",
        "open": "metahub"
    })

    return RedirectResponse(redirect_url)


@app.post("/api/meta/disconnect")
async def meta_disconnect():
    delete_meta_tokens()

    return {
        "success": True,
        "message": "Meta акаунт відключено."
    }


@app.get("/api/meta/pages")
async def meta_pages():
    tokens = get_meta_tokens()

    if not tokens:
        return {
            "success": False,
            "error": "Meta акаунт не підключено.",
            "pages": []
        }

    access_token = tokens["access_token"]

    async with httpx.AsyncClient(timeout=40) as client:
        pages_res = await client.get(
            f"{META_GRAPH_URL}/me/accounts",
            params={
                "fields": "id,name,category,access_token,tasks",
                "limit": 100,
                "access_token": access_token
            }
        )

    pages_data = pages_res.json()

    if "error" in pages_data:
        return {
            "success": False,
            "error": "Не вдалося отримати Facebook Pages.",
            "details": pages_data
        }

    pages = pages_data.get("data", [])
    save_meta_pages(pages)

    return {
        "success": True,
        "pages": get_meta_pages()
    }

@app.get("/api/meta/facebook/posts-test")
async def meta_facebook_posts_test(page_id: str):
    tokens = get_meta_tokens()

    if not tokens:
        return {
            "success": False,
            "error": "Meta акаунт не підключено."
        }

    page_id = str(page_id or "").strip()

    if not page_id:
        return {
            "success": False,
            "error": "Не передано page_id."
        }

    user_access_token = tokens["access_token"]

    async with httpx.AsyncClient(timeout=60) as client:
        # Отримуємо сторінку та її Page Access Token
        pages_response = await client.get(
            f"{META_GRAPH_URL}/me/accounts",
            params={
                "fields": (
                    "id,"
                    "name,"
                    "access_token,"
                    "tasks"
                ),
                "limit": 100,
                "access_token": user_access_token
            }
        )

        pages_data = pages_response.json()

        if "error" in pages_data:
            return {
                "success": False,
                "stage": "me_accounts",
                "details": pages_data
            }

        selected_page = None

        for page in pages_data.get("data", []):
            if str(page.get("id")) == page_id:
                selected_page = page
                break

        if not selected_page:
            return {
                "success": False,
                "error": "Сторінку не знайдено в /me/accounts."
            }

        page_access_token = selected_page.get(
            "access_token"
        )

        results = {
            "page": {
                "id": selected_page.get("id"),
                "name": selected_page.get("name"),
                "tasks": selected_page.get("tasks", []),
                "page_token_received": bool(page_access_token)
            }
        }

        # Тест №1: мінімальний запит з Page Access Token
        if page_access_token:
            page_token_response = await client.get(
                f"{META_GRAPH_URL}/{page_id}/published_posts",
                params={
                    "fields": (
                        "id,"
                        "message,"
                        "created_time,"
                        "permalink_url"
                    ),
                    "limit": 3,
                    "access_token": page_access_token
                }
            )

            try:
                page_token_data = page_token_response.json()
            except Exception:
                page_token_data = {
                    "raw": page_token_response.text
                }

            results["page_token_test"] = {
                "status_code": page_token_response.status_code,
                "success": (
                    page_token_response.status_code < 400
                    and "error" not in page_token_data
                ),
                "response": page_token_data
            }

        # Тест №2: той самий мінімальний запит з User Access Token
        user_token_response = await client.get(
            f"{META_GRAPH_URL}/{page_id}/published_posts",
            params={
                "fields": (
                    "id,"
                    "message,"
                    "created_time,"
                    "permalink_url"
                ),
                "limit": 3,
                "access_token": user_access_token
            }
        )

        try:
            user_token_data = user_token_response.json()
        except Exception:
            user_token_data = {
                "raw": user_token_response.text
            }

        results["user_token_test"] = {
            "status_code": user_token_response.status_code,
            "success": (
                user_token_response.status_code < 400
                and "error" not in user_token_data
            ),
            "response": user_token_data
        }

    return {
        "success": True,
        "tests": results
    }

@app.get("/api/meta/facebook/posts")
async def meta_facebook_posts(
    page_id: str,
    limit: int = 25,
    after: str = ""
):
    tokens = get_meta_tokens()

    if not tokens:
        return {
            "success": False,
            "error": "Meta акаунт не підключено.",
            "posts": [],
            "count": 0
        }

    page_id = str(page_id or "").strip()

    if not page_id:
        return {
            "success": False,
            "error": "Не передано page_id.",
            "posts": [],
            "count": 0
        }

    user_access_token = tokens["access_token"]
    page_access_token = None
    facebook_page = None

    async with httpx.AsyncClient(timeout=60) as client:
        # 1. Отримуємо доступні Facebook Pages
        pages_response = await client.get(
            f"{META_GRAPH_URL}/me/accounts",
            params={
                "fields": (
                    "id,"
                    "name,"
                    "category,"
                    "access_token,"
                    "tasks"
                ),
                "limit": 100,
                "access_token": user_access_token
            }
        )

        pages_data = pages_response.json()

        if "error" in pages_data:
            return {
                "success": False,
                "error": "Не вдалося отримати Facebook Pages.",
                "details": pages_data,
                "posts": [],
                "count": 0
            }

        for page in pages_data.get("data", []):
            if str(page.get("id")) != page_id:
                continue

            page_access_token = (
                page.get("access_token")
                or user_access_token
            )

            facebook_page = {
                "id": page.get("id"),
                "name": page.get("name"),
                "category": page.get("category"),
                "tasks": page.get("tasks", [])
            }

            break

        if not page_access_token:
            return {
                "success": False,
                "error": (
                    "Facebook Page не знайдено "
                    "серед доступних сторінок."
                ),
                "posts": [],
                "count": 0
            }

        # 2. Отримуємо публікації, створені сторінкою
        params = {
            "fields": (
                "id,"
                "message,"
                "story,"
                "created_time,"
                "updated_time,"
                "permalink_url,"
                "full_picture,"
                "status_type,"
                "is_published,"
                "shares,"
                "reactions.limit(0).summary(true),"
                "comments.limit(0).summary(true)"
            ),
            "limit": max(1, min(limit, 100)),
            "access_token": page_access_token
        }

        if after:
            params["after"] = after

        posts_response = await client.get(
            f"{META_GRAPH_URL}/{page_id}/published_posts",
            params=params
        )

    posts_data = posts_response.json()

    if "error" in posts_data:
        return {
            "success": False,
            "error": (
                "Не вдалося отримати публікації "
                "Facebook Page."
            ),
            "details": posts_data,
            "posts": [],
            "count": 0
        }

    posts = []

    for item in posts_data.get("data", []):
        reactions_summary = (
            item.get("reactions", {})
            .get("summary", {})
        )

        comments_summary = (
            item.get("comments", {})
            .get("summary", {})
        )

        shares = item.get("shares") or {}

        posts.append({
            "id": item.get("id"),
            "message": item.get("message", ""),
            "story": item.get("story", ""),
            "created_time": item.get("created_time"),
            "updated_time": item.get("updated_time"),
            "permalink_url": item.get("permalink_url"),
            "full_picture": item.get("full_picture"),
            "status_type": item.get("status_type"),
            "is_published": item.get("is_published"),
            "shares_count": shares.get("count", 0),
            "reactions_count": reactions_summary.get(
                "total_count",
                0
            ),
            "comments_count": comments_summary.get(
                "total_count",
                0
            ),
            "attachments": (
                item.get("attachments", {})
                .get("data", [])
            )
        })

    return {
        "success": True,
        "facebook_page": facebook_page,
        "count": len(posts),
        "posts": posts,
        "paging": posts_data.get("paging", {})
    }

@app.get("/api/meta/facebook/post/insights")
async def meta_facebook_post_insights(
    page_id: str,
    post_id: str
):
    tokens = get_meta_tokens()

    if not tokens:
        return {
            "success": False,
            "error": "Meta акаунт не підключено."
        }

    page_id = str(page_id or "").strip()
    post_id = str(post_id or "").strip()

    if not page_id:
        return {
            "success": False,
            "error": "Не передано page_id."
        }

    if not post_id:
        return {
            "success": False,
            "error": "Не передано post_id."
        }

    user_access_token = tokens["access_token"]
    page_access_token = None
    facebook_page = None

    async with httpx.AsyncClient(timeout=60) as client:
        # 1. Знаходимо Facebook Page та Page Access Token
        pages_response = await client.get(
            f"{META_GRAPH_URL}/me/accounts",
            params={
                "fields": (
                    "id,"
                    "name,"
                    "category,"
                    "access_token,"
                    "tasks"
                ),
                "limit": 100,
                "access_token": user_access_token
            }
        )

        pages_data = pages_response.json()

        if "error" in pages_data:
            return {
                "success": False,
                "error": "Не вдалося отримати Facebook Pages.",
                "details": pages_data
            }

        for page in pages_data.get("data", []):
            if str(page.get("id")) != page_id:
                continue

            page_access_token = (
                page.get("access_token")
                or user_access_token
            )

            facebook_page = {
                "id": page.get("id"),
                "name": page.get("name"),
                "category": page.get("category"),
                "tasks": page.get("tasks", [])
            }

            break

        if not page_access_token:
            return {
                "success": False,
                "error": (
                    "Facebook Page не знайдено "
                    "серед доступних сторінок."
                )
            }

                # 2. Шукаємо вибраний допис через published_posts.
        # Це працює також для дописів, які є Facebook Reels.
        posts_response = await client.get(
            f"{META_GRAPH_URL}/{page_id}/published_posts",
            params={
                "fields": (
                    "id,"
                    "message,"
                    "story,"
                    "created_time,"
                    "updated_time,"
                    "permalink_url,"
                    "full_picture,"
                    "status_type,"
                    "is_published"
                ),
                "limit": 100,
                "access_token": page_access_token
            }
        )

        posts_data = posts_response.json()

        if "error" in posts_data:
            return {
                "success": False,
                "error": (
                    "Не вдалося отримати список "
                    "Facebook-публікацій."
                ),
                "details": posts_data
            }

        post_data = None

        for post_item in posts_data.get("data", []):
            if str(post_item.get("id")) == str(post_id):
                post_data = post_item
                break

        if not post_data:
            return {
                "success": False,
                "error": (
                    "Публікацію не знайдено серед "
                    "опублікованих дописів сторінки."
                ),
                "post_id": post_id
            }

        # 3. Запитуємо всі доступні Insights цього допису
        insights_response = await client.get(
            f"{META_GRAPH_URL}/{post_id}/insights",
            params={
                "access_token": page_access_token
            }
        )

        insights_data = insights_response.json()

    reactions_summary = (
        post_data.get("reactions", {})
        .get("summary", {})
    )

    comments_summary = (
        post_data.get("comments", {})
        .get("summary", {})
    )

    shares_data = post_data.get("shares") or {}

    normalized_insights = {}
    available_metric_names = []
    insights_error = None

    if "error" in insights_data:
        insights_error = insights_data.get("error")
    else:
        for metric_item in insights_data.get("data", []):
            metric_name = metric_item.get("name")

            if not metric_name:
                continue

            metric_value = None

            total_value = metric_item.get("total_value")

            if isinstance(total_value, dict):
                metric_value = total_value.get("value")

            if metric_value is None:
                values = metric_item.get("values")

                if isinstance(values, list) and values:
                    metric_value = values[-1].get("value")

            available_metric_names.append(metric_name)

            normalized_insights[metric_name] = {
                "value": metric_value,
                "title": metric_item.get("title"),
                "description": metric_item.get(
                    "description"
                ),
                "period": metric_item.get("period"),
                "raw_values": metric_item.get(
                    "values",
                    []
                ),
                "total_value": metric_item.get(
                    "total_value"
                )
            }

    return {
        "success": True,
        "facebook_page": facebook_page,
        "post": {
            "id": post_data.get("id"),
            "message": post_data.get("message", ""),
            "story": post_data.get("story", ""),
            "created_time": post_data.get(
                "created_time"
            ),
            "updated_time": post_data.get(
                "updated_time"
            ),
            "permalink_url": post_data.get(
                "permalink_url"
            ),
            "full_picture": post_data.get(
                "full_picture"
            ),
            "status_type": post_data.get(
                "status_type"
            ),
            "is_published": post_data.get(
                "is_published"
            ),
            "is_reel": (
                "/reel/" in str(
                    post_data.get("permalink_url") or ""
                )
            ),
            "attachments": (
                post_data.get("attachments", {})
                .get("data", [])
            ),
            "shares_count": shares_data.get(
                "count",
                0
            ),
            "reactions_count": reactions_summary.get(
                "total_count",
                0
            ),
            "comments_count": comments_summary.get(
                "total_count",
                0
            )
        },
        "available_metric_names": (
            available_metric_names
        ),
        "insights": normalized_insights,
        "insights_error": insights_error
    }

async def get_facebook_page_access_token(
    client: httpx.AsyncClient,
    page_id: str,
    user_access_token: str
):
    pages_response = await client.get(
        f"{META_GRAPH_URL}/me/accounts",
        params={
            "fields": (
                "id,"
                "name,"
                "category,"
                "access_token,"
                "tasks"
            ),
            "limit": 100,
            "access_token": user_access_token
        }
    )

    try:
        pages_data = pages_response.json()
    except Exception:
        pages_data = {
            "raw": pages_response.text
        }

    if (
        pages_response.status_code >= 400
        or "error" in pages_data
    ):
        return None, None, pages_data

    for page in pages_data.get("data", []):
        if str(page.get("id")) != str(page_id):
            continue

        page_access_token = (
            page.get("access_token")
            or user_access_token
        )

        facebook_page = {
            "id": page.get("id"),
            "name": page.get("name"),
            "category": page.get("category"),
            "tasks": page.get("tasks", [])
        }

        return (
            page_access_token,
            facebook_page,
            None
        )

    return (
        None,
        None,
        {
            "message": (
                "Facebook Page не знайдено "
                "серед доступних сторінок."
            )
        }
    )

@app.get("/api/meta/facebook/comments")
async def meta_facebook_comments(
    page_id: str,
    post_id: str,
    limit: int = 50,
    after: str = ""
):
    tokens = get_meta_tokens()

    if not tokens:
        return {
            "success": False,
            "error": "Meta акаунт не підключено.",
            "comments": [],
            "count": 0
        }

    page_id = str(page_id or "").strip()
    post_id = str(post_id or "").strip()

    if not page_id:
        return {
            "success": False,
            "error": "Не передано page_id.",
            "comments": [],
            "count": 0
        }

    if not post_id:
        return {
            "success": False,
            "error": "Не передано post_id.",
            "comments": [],
            "count": 0
        }

    user_access_token = tokens["access_token"]
    page_access_token = None
    facebook_page = None

    async with httpx.AsyncClient(timeout=60) as client:
        # 1. Знаходимо Facebook Page та Page Access Token
        pages_response = await client.get(
            f"{META_GRAPH_URL}/me/accounts",
            params={
                "fields": (
                    "id,"
                    "name,"
                    "category,"
                    "access_token,"
                    "tasks"
                ),
                "limit": 100,
                "access_token": user_access_token
            }
        )

        pages_data = pages_response.json()

        if "error" in pages_data:
            return {
                "success": False,
                "error": "Не вдалося отримати Facebook Pages.",
                "details": pages_data,
                "comments": [],
                "count": 0
            }

        for page in pages_data.get("data", []):
            if str(page.get("id")) != page_id:
                continue

            page_access_token = (
                page.get("access_token")
                or user_access_token
            )

            facebook_page = {
                "id": page.get("id"),
                "name": page.get("name"),
                "category": page.get("category"),
                "tasks": page.get("tasks", [])
            }

            break

        if not page_access_token:
            return {
                "success": False,
                "error": (
                    "Facebook Page не знайдено "
                    "серед доступних сторінок."
                ),
                "comments": [],
                "count": 0
            }

        # 2. Отримуємо коментарі до допису або Reel
        params = {
            "fields": (
                "id,"
                "message,"
                "created_time,"
                "like_count,"
                "is_hidden,"
                "can_hide,"
                "can_remove,"
                "can_comment,"
                "comment_count,"
                "from{id,name},"
                "replies.limit(20){"
                    "id,"
                    "message,"
                    "created_time,"
                    "like_count,"
                    "is_hidden,"
                    "from{id,name}"
                "}"
            ),
            "limit": max(1, min(limit, 100)),
            "access_token": page_access_token
        }

        if after:
            params["after"] = after

        comments_response = await client.get(
            f"{META_GRAPH_URL}/{post_id}/comments",
            params=params
        )

    try:
        comments_data = comments_response.json()
    except Exception:
        comments_data = {
            "raw": comments_response.text
        }

    if (
        comments_response.status_code >= 400
        or "error" in comments_data
    ):
        return {
            "success": False,
            "error": (
                "Не вдалося отримати коментарі "
                "Facebook-публікації."
            ),
            "details": comments_data,
            "comments": [],
            "count": 0
        }

    comments = []

    async with httpx.AsyncClient(timeout=40) as replies_client:
        for item in comments_data.get("data", []):
            author = item.get("from") or {}
            comment_id = item.get("id")

            replies = []

            # Спочатку беремо вкладені replies,
            # якщо Meta їх повернула одразу
            reply_items = (
                item.get("replies", {})
                .get("data", [])
            )

            # Додатково окремо запитуємо відповіді
            # конкретного Facebook-коментаря
            if comment_id:
                replies_response = await replies_client.get(
                    f"{META_GRAPH_URL}/{comment_id}/comments",
                    params={
                        "fields": (
                            "id,"
                            "message,"
                            "created_time,"
                            "like_count,"
                            "is_hidden,"
                            "from{id,name}"
                        ),
                        "limit": 50,
                        "access_token": page_access_token
                    }
                )

                try:
                    replies_data = replies_response.json()
                except Exception:
                    replies_data = {
                        "raw": replies_response.text
                    }

                if (
                    replies_response.status_code < 400
                    and "error" not in replies_data
                ):
                    reply_items = replies_data.get(
                        "data",
                        []
                    )

            for reply_item in reply_items:
                reply_author = (
                    reply_item.get("from") or {}
                )

                replies.append({
                    "id": reply_item.get("id"),
                    "message": reply_item.get(
                        "message",
                        ""
                    ),
                    "created_time": reply_item.get(
                        "created_time"
                    ),
                    "like_count": reply_item.get(
                        "like_count",
                        0
                    ),
                    "is_hidden": reply_item.get(
                        "is_hidden",
                        False
                    ),
                    "author": {
                        "id": reply_author.get("id"),
                        "name": reply_author.get("name")
                    }
                })

            comments.append({
                "id": comment_id,
                "message": item.get("message", ""),
                "created_time": item.get(
                    "created_time"
                ),
                "like_count": item.get(
                    "like_count",
                    0
                ),
                "is_hidden": item.get(
                    "is_hidden",
                    False
                ),
                "can_hide": item.get(
                    "can_hide",
                    False
                ),
                "can_remove": item.get(
                    "can_remove",
                    False
                ),
                "can_comment": item.get(
                    "can_comment",
                    True
                ),
                "comment_count": max(
                    item.get("comment_count", 0),
                    len(replies)
                ),
                "author": {
                    "id": author.get("id"),
                    "name": author.get("name")
                },
                "replies": replies
            })

    return {
        "success": True,
        "facebook_page": facebook_page,
        "post_id": post_id,
        "count": len(comments),
        "comments": comments,
        "paging": comments_data.get("paging", {})
    }

@app.post("/api/meta/facebook/comments/reply")
async def meta_facebook_comment_reply(
    payload: FacebookCommentReplyRequest
):
    tokens = get_meta_tokens()

    if not tokens:
        return {
            "success": False,
            "error": "Meta акаунт не підключено."
        }

    page_id = payload.page_id.strip()
    comment_id = payload.comment_id.strip()
    message = payload.message.strip()

    if not page_id:
        return {
            "success": False,
            "error": "Не передано page_id."
        }

    if not comment_id:
        return {
            "success": False,
            "error": "Не передано comment_id."
        }

    if not message:
        return {
            "success": False,
            "error": "Текст відповіді порожній."
        }

    user_access_token = tokens["access_token"]

    async with httpx.AsyncClient(timeout=40) as client:
        (
            page_access_token,
            facebook_page,
            token_error
        ) = await get_facebook_page_access_token(
            client=client,
            page_id=page_id,
            user_access_token=user_access_token
        )

        if not page_access_token:
            return {
                "success": False,
                "error": (
                    "Не вдалося отримати "
                    "Page Access Token."
                ),
                "details": token_error
            }

        response = await client.post(
            f"{META_GRAPH_URL}/{comment_id}/comments",
            data={
                "message": message,
                "access_token": page_access_token
            }
        )

    try:
        data = response.json()
    except Exception:
        data = {
            "raw": response.text
        }

    if (
        response.status_code >= 400
        or "error" in data
    ):
        return {
            "success": False,
            "error": (
                "Не вдалося відповісти "
                "на Facebook-коментар."
            ),
            "details": data
        }

    return {
        "success": True,
        "message": "Відповідь опублікована.",
        "page_id": page_id,
        "comment_id": comment_id,
        "reply_id": data.get("id"),
        "facebook_page": facebook_page,
        "result": data
    }


@app.post("/api/meta/facebook/comments/visibility")
async def meta_facebook_comment_visibility(
    payload: FacebookCommentVisibilityRequest
):
    tokens = get_meta_tokens()

    if not tokens:
        return {
            "success": False,
            "error": "Meta акаунт не підключено."
        }

    page_id = payload.page_id.strip()
    comment_id = payload.comment_id.strip()

    if not page_id:
        return {
            "success": False,
            "error": "Не передано page_id."
        }

    if not comment_id:
        return {
            "success": False,
            "error": "Не передано comment_id."
        }

    user_access_token = tokens["access_token"]

    async with httpx.AsyncClient(timeout=40) as client:
        (
            page_access_token,
            facebook_page,
            token_error
        ) = await get_facebook_page_access_token(
            client=client,
            page_id=page_id,
            user_access_token=user_access_token
        )

        if not page_access_token:
            return {
                "success": False,
                "error": (
                    "Не вдалося отримати "
                    "Page Access Token."
                ),
                "details": token_error
            }

        response = await client.post(
            f"{META_GRAPH_URL}/{comment_id}",
            data={
                "is_hidden": str(
                    payload.hidden
                ).lower(),
                "access_token": page_access_token
            }
        )

    try:
        data = response.json()
    except Exception:
        data = {
            "raw": response.text
        }

    if (
        response.status_code >= 400
        or "error" in data
    ):
        return {
            "success": False,
            "error": (
                "Не вдалося змінити видимість "
                "Facebook-коментаря."
            ),
            "details": data
        }

    return {
        "success": True,
        "hidden": payload.hidden,
        "message": (
            "Коментар приховано."
            if payload.hidden
            else "Коментар знову показується."
        ),
        "page_id": page_id,
        "comment_id": comment_id,
        "facebook_page": facebook_page,
        "result": data
    }


@app.delete("/api/meta/facebook/comments")
async def meta_facebook_comment_delete(
    payload: FacebookCommentDeleteRequest
):
    tokens = get_meta_tokens()

    if not tokens:
        return {
            "success": False,
            "error": "Meta акаунт не підключено."
        }

    page_id = payload.page_id.strip()
    comment_id = payload.comment_id.strip()

    if not page_id:
        return {
            "success": False,
            "error": "Не передано page_id."
        }

    if not comment_id:
        return {
            "success": False,
            "error": "Не передано comment_id."
        }

    user_access_token = tokens["access_token"]

    async with httpx.AsyncClient(timeout=40) as client:
        (
            page_access_token,
            facebook_page,
            token_error
        ) = await get_facebook_page_access_token(
            client=client,
            page_id=page_id,
            user_access_token=user_access_token
        )

        if not page_access_token:
            return {
                "success": False,
                "error": (
                    "Не вдалося отримати "
                    "Page Access Token."
                ),
                "details": token_error
            }

        response = await client.delete(
            f"{META_GRAPH_URL}/{comment_id}",
            params={
                "access_token": page_access_token
            }
        )

    try:
        data = response.json()
    except Exception:
        data = {
            "raw": response.text
        }

    if (
        response.status_code >= 400
        or "error" in data
    ):
        return {
            "success": False,
            "error": (
                "Не вдалося видалити "
                "Facebook-коментар."
            ),
            "details": data
        }

    return {
        "success": True,
        "message": "Facebook-коментар видалено.",
        "page_id": page_id,
        "comment_id": comment_id,
        "facebook_page": facebook_page,
        "result": data
    }

@app.get("/api/meta/facebook/video/insights")
async def meta_facebook_video_insights(
    page_id: str,
    video_id: str
):
    tokens = get_meta_tokens()

    if not tokens:
        return {
            "success": False,
            "error": "Meta акаунт не підключено."
        }

    page_id = str(page_id or "").strip()
    video_id = str(video_id or "").strip()

    if not page_id:
        return {
            "success": False,
            "error": "Не передано page_id."
        }

    if not video_id:
        return {
            "success": False,
            "error": "Не передано video_id."
        }

    user_access_token = tokens["access_token"]
    page_access_token = None
    facebook_page = None

    async with httpx.AsyncClient(timeout=60) as client:
        # 1. Знаходимо Facebook Page та її токен
        pages_response = await client.get(
            f"{META_GRAPH_URL}/me/accounts",
            params={
                "fields": (
                    "id,"
                    "name,"
                    "category,"
                    "access_token,"
                    "tasks"
                ),
                "limit": 100,
                "access_token": user_access_token
            }
        )

        pages_data = pages_response.json()

        if "error" in pages_data:
            return {
                "success": False,
                "error": "Не вдалося отримати Facebook Pages.",
                "details": pages_data
            }

        for page in pages_data.get("data", []):
            if str(page.get("id")) != page_id:
                continue

            page_access_token = (
                page.get("access_token")
                or user_access_token
            )

            facebook_page = {
                "id": page.get("id"),
                "name": page.get("name"),
                "category": page.get("category"),
                "tasks": page.get("tasks", [])
            }

            break

        if not page_access_token:
            return {
                "success": False,
                "error": (
                    "Facebook Page не знайдено "
                    "серед доступних сторінок."
                )
            }

        # 2. Основні дані Reel / відео
        video_response = await client.get(
            f"{META_GRAPH_URL}/{video_id}",
            params={
                "fields": (
                    "id,"
                    "description,"
                    "created_time,"
                    "updated_time,"
                    "permalink_url,"
                    "length"
                ),
                "access_token": page_access_token
            }
        )

        try:
            video_data = video_response.json()
        except Exception:
            video_data = {
                "raw": video_response.text
            }

        if (
            video_response.status_code >= 400
            or "error" in video_data
        ):
            return {
                "success": False,
                "error": (
                    "Не вдалося отримати дані "
                    "Facebook Reel."
                ),
                "details": video_data
            }

        # 3. Усі доступні метрики відео / Reel
        insights_response = await client.get(
            f"{META_GRAPH_URL}/{video_id}/video_insights",
            params={
                "access_token": page_access_token
            }
        )

        try:
            insights_data = insights_response.json()
        except Exception:
            insights_data = {
                "raw": insights_response.text
            }

    normalized_insights = {}
    available_metric_names = []
    insights_error = None

    if (
        insights_response.status_code >= 400
        or "error" in insights_data
    ):
        insights_error = insights_data.get(
            "error",
            insights_data
        )
    else:
        for metric_item in insights_data.get("data", []):
            metric_name = metric_item.get("name")

            if not metric_name:
                continue

            metric_value = None
            values = metric_item.get("values")

            if isinstance(values, list) and values:
                metric_value = values[-1].get("value")

            available_metric_names.append(metric_name)

            normalized_insights[metric_name] = {
                "value": metric_value,
                "title": metric_item.get("title"),
                "description": metric_item.get(
                    "description"
                ),
                "period": metric_item.get("period")
            }

    return {
        "success": True,
        "facebook_page": facebook_page,
        "video": {
            "id": video_data.get("id"),
            "description": video_data.get(
                "description",
                ""
            ),
            "created_time": video_data.get(
                "created_time"
            ),
            "updated_time": video_data.get(
                "updated_time"
            ),
            "permalink_url": video_data.get(
                "permalink_url"
            ),
            "length": video_data.get("length"),
            "is_reel": True
        },
        "available_metric_names": (
            available_metric_names
        ),
        "insights": normalized_insights,
        "insights_error": insights_error
    }

@app.get("/api/meta/adaccounts")
async def meta_adaccounts():
    tokens = get_meta_tokens()

    if not tokens:
        return {
            "success": False,
            "error": "Meta акаунт не підключено.",
            "accounts": []
        }

    access_token = tokens["access_token"]
    all_accounts = []
    raw_debug = {}

    async with httpx.AsyncClient(timeout=40) as client:
        # 1. Рекламні кабінети, доступні напряму користувачу
        me_adaccounts_res = await client.get(
            f"{META_GRAPH_URL}/me/adaccounts",
            params={
                "fields": "id,name,account_id,currency,timezone_name,account_status,business",
                "limit": 100,
                "access_token": access_token
            }
        )

        me_adaccounts_data = me_adaccounts_res.json()
        raw_debug["me_adaccounts"] = me_adaccounts_data

        if "data" in me_adaccounts_data:
            all_accounts.extend(me_adaccounts_data["data"])

        # 2. Бізнеси користувача
        businesses_res = await client.get(
            f"{META_GRAPH_URL}/me/businesses",
            params={
                "fields": "id,name,verification_status",
                "limit": 100,
                "access_token": access_token
            }
        )

        businesses_data = businesses_res.json()
        raw_debug["businesses"] = businesses_data

        businesses = businesses_data.get("data", [])

        # 3. Рекламні кабінети всередині кожного бізнесу
        for business in businesses:
            business_id = business.get("id")

            if not business_id:
                continue

            owned_res = await client.get(
                f"{META_GRAPH_URL}/{business_id}/owned_ad_accounts",
                params={
                    "fields": "id,name,account_id,currency,timezone_name,account_status,business",
                    "limit": 100,
                    "access_token": access_token
                }
            )

            client_res = await client.get(
                f"{META_GRAPH_URL}/{business_id}/client_ad_accounts",
                params={
                    "fields": "id,name,account_id,currency,timezone_name,account_status,business",
                    "limit": 100,
                    "access_token": access_token
                }
            )

            owned_data = owned_res.json()
            client_data = client_res.json()

            raw_debug[f"business_{business_id}_owned_ad_accounts"] = owned_data
            raw_debug[f"business_{business_id}_client_ad_accounts"] = client_data

            if "data" in owned_data:
                all_accounts.extend(owned_data["data"])

            if "data" in client_data:
                all_accounts.extend(client_data["data"])

    # Прибираємо дублікати
    unique_accounts = []
    seen = set()

    for account in all_accounts:
        account_id = account.get("id")

        if account_id and account_id not in seen:
            seen.add(account_id)
            unique_accounts.append(account)

    return {
        "success": True,
        "count": len(unique_accounts),
        "accounts": unique_accounts,
        "debug": raw_debug
    }

@app.get("/api/meta/instagram/accounts")
async def meta_instagram_accounts():
    tokens = get_meta_tokens()

    if not tokens:
        return {
            "success": False,
            "error": "Meta акаунт не підключено.",
            "accounts": [],
            "count": 0
        }

    user_access_token = tokens["access_token"]
    instagram_accounts = []

    async with httpx.AsyncClient(timeout=40) as client:
        # 1. Отримуємо Facebook Pages, доступні користувачу
        pages_response = await client.get(
            f"{META_GRAPH_URL}/me/accounts",
            params={
                "fields": "id,name,access_token",
                "limit": 100,
                "access_token": user_access_token
            }
        )

        pages_data = pages_response.json()

        if "error" in pages_data:
            return {
                "success": False,
                "error": "Не вдалося отримати Facebook Pages.",
                "details": pages_data,
                "accounts": [],
                "count": 0
            }

        pages = pages_data.get("data", [])

        # 2. Для кожної Facebook Page шукаємо прив'язаний Instagram
        for page in pages:
            page_id = page.get("id")
            page_name = page.get("name")
            page_access_token = (
                page.get("access_token")
                or user_access_token
            )

            if not page_id:
                continue

            connection_response = await client.get(
                f"{META_GRAPH_URL}/{page_id}",
                params={
                    "fields": "instagram_business_account",
                    "access_token": page_access_token
                }
            )

            connection_data = connection_response.json()

            instagram_connection = connection_data.get(
                "instagram_business_account"
            )

            if not instagram_connection:
                continue

            instagram_id = instagram_connection.get("id")

            if not instagram_id:
                continue

            # 3. Отримуємо дані Instagram-профілю
            profile_response = await client.get(
                f"{META_GRAPH_URL}/{instagram_id}",
                params={
                    "fields": (
                        "id,"
                        "username,"
                        "name,"
                        "profile_picture_url,"
                        "followers_count,"
                        "media_count"
                    ),
                    "access_token": page_access_token
                }
            )

            profile_data = profile_response.json()

            if "error" in profile_data:
                instagram_accounts.append({
                    "instagram_id": instagram_id,
                    "facebook_page_id": page_id,
                    "facebook_page_name": page_name,
                    "profile_error": profile_data
                })
                continue

            instagram_accounts.append({
                "id": profile_data.get("id"),
                "username": profile_data.get("username"),
                "name": profile_data.get("name"),
                "profile_picture_url": profile_data.get(
                    "profile_picture_url"
                ),
                "followers_count": profile_data.get(
                    "followers_count"
                ),
                "media_count": profile_data.get("media_count"),
                "facebook_page_id": page_id,
                "facebook_page_name": page_name
            })

    return {
        "success": True,
        "count": len(instagram_accounts),
        "accounts": instagram_accounts
    }

@app.get("/api/meta/instagram/media")
async def meta_instagram_media(
    instagram_id: str,
    limit: int = 25,
    after: str = ""
):
    tokens = get_meta_tokens()

    if not tokens:
        return {
            "success": False,
            "error": "Meta акаунт не підключено.",
            "media": [],
            "count": 0
        }

    if not instagram_id:
        return {
            "success": False,
            "error": "Не передано instagram_id.",
            "media": [],
            "count": 0
        }

    user_access_token = tokens["access_token"]
    page_access_token = None
    facebook_page = None

    async with httpx.AsyncClient(timeout=40) as client:
        # 1. Отримуємо Facebook Pages і шукаємо сторінку,
        # до якої прив'язаний потрібний Instagram.
        pages_response = await client.get(
            f"{META_GRAPH_URL}/me/accounts",
            params={
                "fields": (
                    "id,"
                    "name,"
                    "access_token,"
                    "instagram_business_account"
                ),
                "limit": 100,
                "access_token": user_access_token
            }
        )

        pages_data = pages_response.json()

        if "error" in pages_data:
            return {
                "success": False,
                "error": "Не вдалося отримати Facebook Pages.",
                "details": pages_data,
                "media": [],
                "count": 0
            }

        for page in pages_data.get("data", []):
            connected_instagram = page.get(
                "instagram_business_account"
            ) or {}

            if str(connected_instagram.get("id")) == str(instagram_id):
                page_access_token = (
                    page.get("access_token")
                    or user_access_token
                )

                facebook_page = {
                    "id": page.get("id"),
                    "name": page.get("name")
                }

                break

        if not page_access_token:
            return {
                "success": False,
                "error": (
                    "Instagram не знайдений серед акаунтів, "
                    "прив’язаних до доступних Facebook Pages."
                ),
                "media": [],
                "count": 0
            }

        # 2. Отримуємо публікації Instagram.
        params = {
            "fields": (
                "id,"
                "caption,"
                "media_type,"
                "media_product_type,"
                "media_url,"
                "thumbnail_url,"
                "permalink,"
                "timestamp,"
                "username"
            ),
            "limit": max(1, min(limit, 100)),
            "access_token": page_access_token
        }

        if after:
            params["after"] = after

        media_response = await client.get(
            f"{META_GRAPH_URL}/{instagram_id}/media",
            params=params
        )

    media_data = media_response.json()

    if "error" in media_data:
        return {
            "success": False,
            "error": "Не вдалося отримати публікації Instagram.",
            "details": media_data,
            "media": [],
            "count": 0
        }

    media_items = media_data.get("data", [])

    return {
        "success": True,
        "instagram_id": instagram_id,
        "facebook_page": facebook_page,
        "count": len(media_items),
        "media": media_items,
        "paging": media_data.get("paging", {})
    }

@app.get("/api/meta/instagram/media/insights")
async def meta_instagram_media_insights(
    instagram_id: str,
    media_id: str
):
    tokens = get_meta_tokens()

    if not tokens:
        return {
            "success": False,
            "error": "Meta акаунт не підключено."
        }

    if not instagram_id or not media_id:
        return {
            "success": False,
            "error": "Не передано instagram_id або media_id."
        }

    user_access_token = tokens["access_token"]
    page_access_token = None

    async with httpx.AsyncClient(timeout=40) as client:
        # Знаходимо Facebook Page, до якої прив’язаний Instagram
        pages_response = await client.get(
            f"{META_GRAPH_URL}/me/accounts",
            params={
                "fields": (
                    "id,"
                    "name,"
                    "access_token,"
                    "instagram_business_account"
                ),
                "limit": 100,
                "access_token": user_access_token
            }
        )

        pages_data = pages_response.json()

        if "error" in pages_data:
            return {
                "success": False,
                "error": "Не вдалося отримати Facebook Pages.",
                "details": pages_data
            }

        for page in pages_data.get("data", []):
            connected_instagram = (
                page.get("instagram_business_account") or {}
            )

            if str(connected_instagram.get("id")) == str(instagram_id):
                page_access_token = (
                    page.get("access_token")
                    or user_access_token
                )
                break

        if not page_access_token:
            return {
                "success": False,
                "error": (
                    "Не знайдено Facebook Page, "
                    "прив’язану до цього Instagram."
                )
            }

        # Основна інформація про публікацію
        media_response = await client.get(
            f"{META_GRAPH_URL}/{media_id}",
            params={
                "fields": (
                    "id,"
                    "caption,"
                    "media_type,"
                    "media_product_type,"
                    "media_url,"
                    "thumbnail_url,"
                    "permalink,"
                    "timestamp,"
                    "like_count,"
                    "comments_count"
                ),
                "access_token": page_access_token
            }
        )

        media_data = media_response.json()

        if "error" in media_data:
            return {
                "success": False,
                "error": "Не вдалося отримати дані публікації.",
                "details": media_data
            }

        # Запитуємо метрики окремо:
        # якщо конкретна метрика не підтримується типом поста,
        # інші метрики все одно завантажаться
        metric_names = [
            "views",
            "reach",
            "saved",
            "shares"
        ]

        metrics = {}
        metric_errors = {}

        for metric_name in metric_names:
            metric_response = await client.get(
                f"{META_GRAPH_URL}/{media_id}/insights",
                params={
                    "metric": metric_name,
                    "access_token": page_access_token
                }
            )

            metric_data = metric_response.json()

            if "error" in metric_data:
                metric_errors[metric_name] = metric_data["error"]
                continue

            metric_items = metric_data.get("data", [])

            if not metric_items:
                metrics[metric_name] = None
                continue

            metric_item = metric_items[0]
            metric_value = None

            values = metric_item.get("values")

            if isinstance(values, list) and values:
                metric_value = values[-1].get("value")
            elif "total_value" in metric_item:
                total_value = metric_item.get("total_value") or {}
                metric_value = total_value.get("value")

            metrics[metric_name] = metric_value

    return {
        "success": True,
        "instagram_id": instagram_id,
        "media_id": media_id,
        "media": media_data,
        "metrics": metrics,
        "metric_errors": metric_errors
    }

async def get_instagram_page_access_token(
    client: httpx.AsyncClient,
    instagram_id: str,
    user_access_token: str
):
    """
    Знаходить Facebook Page, до якої прив'язаний Instagram,
    і повертає Page Access Token.
    """

    pages_response = await client.get(
        f"{META_GRAPH_URL}/me/accounts",
        params={
            "fields": (
                "id,"
                "name,"
                "access_token,"
                "instagram_business_account"
            ),
            "limit": 100,
            "access_token": user_access_token
        }
    )

    pages_data = pages_response.json()

    if "error" in pages_data:
        return None, None, pages_data

    for page in pages_data.get("data", []):
        connected_instagram = (
            page.get("instagram_business_account") or {}
        )

        if str(connected_instagram.get("id")) != str(instagram_id):
            continue

        page_access_token = (
            page.get("access_token")
            or user_access_token
        )

        facebook_page = {
            "id": page.get("id"),
            "name": page.get("name")
        }

        return page_access_token, facebook_page, None

    return (
        None,
        None,
        {
            "message": (
                "Не знайдено Facebook Page, "
                "прив’язану до цього Instagram."
            )
        }
    )

def get_instagram_insights_date_range(date_preset: str):
    now = datetime.now(timezone.utc)

    allowed_presets = {
        "last_7d",
        "last_30d",
        "this_month",
        "last_month"
    }

    if date_preset not in allowed_presets:
        date_preset = "last_30d"

    if date_preset == "last_7d":
        start = now - timedelta(days=7)
        end = now

    elif date_preset == "this_month":
        start = datetime(
            now.year,
            now.month,
            1,
            tzinfo=timezone.utc
        )
        end = now

    elif date_preset == "last_month":
        current_month_start = datetime(
            now.year,
            now.month,
            1,
            tzinfo=timezone.utc
        )

        end = current_month_start - timedelta(seconds=1)

        start = datetime(
            end.year,
            end.month,
            1,
            tzinfo=timezone.utc
        )

    else:
        start = now - timedelta(days=30)
        end = now

    return {
        "date_preset": date_preset,
        "since": int(start.timestamp()),
        "until": int(end.timestamp()),
        "since_iso": start.isoformat(),
        "until_iso": end.isoformat()
    }


def extract_instagram_insight_value(metric_item: dict):
    total_value = metric_item.get("total_value")

    if isinstance(total_value, dict):
        return {
            "value": total_value.get("value"),
            "breakdowns": total_value.get(
                "breakdowns",
                []
            )
        }

    values = metric_item.get("values")

    if isinstance(values, list) and values:
        latest_value = values[-1].get("value")

        return {
            "value": latest_value,
            "breakdowns": []
        }

    return {
        "value": None,
        "breakdowns": []
    }


@app.get("/api/meta/instagram/account/insights")
async def meta_instagram_account_insights(
    instagram_id: str,
    date_preset: str = "last_30d"
):
    tokens = get_meta_tokens()

    if not tokens:
        return {
            "success": False,
            "error": "Meta акаунт не підключено."
        }

    instagram_id = str(instagram_id or "").strip()

    if not instagram_id:
        return {
            "success": False,
            "error": "Не передано instagram_id."
        }

    user_access_token = tokens["access_token"]

    date_range = get_instagram_insights_date_range(
        date_preset
    )

    metric_names = [
        "views",
        "reach",
        "accounts_engaged",
        "total_interactions",
        "profile_links_taps",
        "follows_and_unfollows"
    ]

    metrics = {}
    metric_details = {}
    metric_errors = {}

    async with httpx.AsyncClient(timeout=60) as client:
        (
            page_access_token,
            facebook_page,
            token_error
        ) = await get_instagram_page_access_token(
            client=client,
            instagram_id=instagram_id,
            user_access_token=user_access_token
        )

        if not page_access_token:
            return {
                "success": False,
                "error": (
                    "Не вдалося отримати токен "
                    "Facebook Page."
                ),
                "details": token_error
            }

        profile_response = await client.get(
            f"{META_GRAPH_URL}/{instagram_id}",
            params={
                "fields": (
                    "id,"
                    "username,"
                    "name,"
                    "profile_picture_url,"
                    "followers_count,"
                    "media_count"
                ),
                "access_token": page_access_token
            }
        )

        profile_data = profile_response.json()

        if "error" in profile_data:
            return {
                "success": False,
                "error": (
                    "Не вдалося отримати "
                    "Instagram-профіль."
                ),
                "details": profile_data
            }

        for metric_name in metric_names:
            params = {
                "metric": metric_name,
                "period": "day",
                "metric_type": "total_value",
                "since": date_range["since"],
                "until": date_range["until"],
                "access_token": page_access_token
            }

            if metric_name == "follows_and_unfollows":
                params["breakdown"] = "follow_type"

            metric_response = await client.get(
                f"{META_GRAPH_URL}/{instagram_id}/insights",
                params=params
            )

            metric_data = metric_response.json()

            if "error" in metric_data:
                metrics[metric_name] = None
                metric_errors[metric_name] = (
                    metric_data.get("error")
                )
                continue

            metric_items = metric_data.get("data", [])

            if not metric_items:
                metrics[metric_name] = None
                metric_details[metric_name] = {
                    "value": None,
                    "breakdowns": []
                }
                continue

            metric_item = metric_items[0]

            extracted = extract_instagram_insight_value(
                metric_item
            )

            metrics[metric_name] = extracted["value"]

            metric_details[metric_name] = {
                "id": metric_item.get("id"),
                "name": metric_item.get("name"),
                "title": metric_item.get("title"),
                "description": metric_item.get(
                    "description"
                ),
                "period": metric_item.get("period"),
                "value": extracted["value"],
                "breakdowns": extracted["breakdowns"]
            }

    return {
        "success": True,
        "instagram_id": instagram_id,
        "facebook_page": facebook_page,
        "profile": {
            "id": profile_data.get("id"),
            "username": profile_data.get("username"),
            "name": profile_data.get("name"),
            "profile_picture_url": profile_data.get(
                "profile_picture_url"
            ),
            "followers_count": profile_data.get(
                "followers_count"
            ),
            "media_count": profile_data.get(
                "media_count"
            )
        },
        "date_preset": date_range["date_preset"],
        "since": date_range["since_iso"],
        "until": date_range["until_iso"],
        "metrics": metrics,
        "metric_details": metric_details,
        "metric_errors": metric_errors
    }

@app.get("/api/meta/instagram/comments")
async def meta_instagram_comments(
    instagram_id: str,
    media_id: str,
    limit: int = 50,
    after: str = ""
):
    tokens = get_meta_tokens()

    if not tokens:
        return {
            "success": False,
            "error": "Meta акаунт не підключено.",
            "comments": [],
            "count": 0
        }

    if not instagram_id or not media_id:
        return {
            "success": False,
            "error": "Не передано instagram_id або media_id.",
            "comments": [],
            "count": 0
        }

    user_access_token = tokens["access_token"]
    page_access_token = None

    async with httpx.AsyncClient(timeout=40) as client:
        # Знаходимо Facebook Page, до якої прив’язаний Instagram
        pages_response = await client.get(
            f"{META_GRAPH_URL}/me/accounts",
            params={
                "fields": (
                    "id,"
                    "name,"
                    "access_token,"
                    "instagram_business_account"
                ),
                "limit": 100,
                "access_token": user_access_token
            }
        )

        pages_data = pages_response.json()

        if "error" in pages_data:
            return {
                "success": False,
                "error": "Не вдалося отримати Facebook Pages.",
                "details": pages_data,
                "comments": [],
                "count": 0
            }

        for page in pages_data.get("data", []):
            connected_instagram = (
                page.get("instagram_business_account") or {}
            )

            if str(connected_instagram.get("id")) == str(instagram_id):
                page_access_token = (
                    page.get("access_token")
                    or user_access_token
                )
                break

        if not page_access_token:
            return {
                "success": False,
                "error": (
                    "Не знайдено Facebook Page, "
                    "прив’язану до цього Instagram."
                ),
                "comments": [],
                "count": 0
            }

        params = {
            "fields": (
                "id,"
                "text,"
                "username,"
                "timestamp,"
                "like_count,"
                "hidden,"
                "replies.limit(20){"
                    "id,"
                    "text,"
                    "username,"
                    "timestamp,"
                    "like_count,"
                    "hidden"
                "}"
            ),
            "limit": max(1, min(limit, 100)),
            "access_token": page_access_token
        }

        if after:
            params["after"] = after

        comments_response = await client.get(
            f"{META_GRAPH_URL}/{media_id}/comments",
            params=params
        )

    comments_data = comments_response.json()

    if "error" in comments_data:
        return {
            "success": False,
            "error": "Не вдалося отримати коментарі Instagram.",
            "details": comments_data,
            "comments": [],
            "count": 0
        }

    comments = comments_data.get("data", [])

    return {
        "success": True,
        "instagram_id": instagram_id,
        "media_id": media_id,
        "count": len(comments),
        "comments": comments,
        "paging": comments_data.get("paging", {})
    }

@app.post("/api/meta/instagram/comments/reply")
async def meta_instagram_comment_reply(
    payload: InstagramCommentReplyRequest
):
    tokens = get_meta_tokens()

    if not tokens:
        return {
            "success": False,
            "error": "Meta акаунт не підключено."
        }

    instagram_id = payload.instagram_id.strip()
    comment_id = payload.comment_id.strip()
    message = payload.message.strip()

    if not instagram_id:
        return {
            "success": False,
            "error": "Не передано instagram_id."
        }

    if not comment_id:
        return {
            "success": False,
            "error": "Не передано comment_id."
        }

    if not message:
        return {
            "success": False,
            "error": "Текст відповіді порожній."
        }

    user_access_token = tokens["access_token"]

    async with httpx.AsyncClient(timeout=40) as client:
        (
            page_access_token,
            facebook_page,
            token_error
        ) = await get_instagram_page_access_token(
            client=client,
            instagram_id=instagram_id,
            user_access_token=user_access_token
        )

        if not page_access_token:
            return {
                "success": False,
                "error": "Не вдалося отримати токен Facebook Page.",
                "details": token_error
            }

        response = await client.post(
            f"{META_GRAPH_URL}/{comment_id}/replies",
            data={
                "message": message,
                "access_token": page_access_token
            }
        )

    try:
        data = response.json()
    except Exception:
        data = {
            "raw": response.text
        }

    if response.status_code >= 400 or "error" in data:
        return {
            "success": False,
            "error": "Не вдалося відповісти на коментар.",
            "details": data
        }

    return {
        "success": True,
        "message": "Відповідь опублікована.",
        "reply_id": data.get("id"),
        "instagram_id": instagram_id,
        "comment_id": comment_id,
        "facebook_page": facebook_page,
        "result": data
    }

@app.post("/api/meta/instagram/comments/visibility")
async def meta_instagram_comment_visibility(
    payload: InstagramCommentVisibilityRequest
):
    tokens = get_meta_tokens()

    if not tokens:
        return {
            "success": False,
            "error": "Meta акаунт не підключено."
        }

    instagram_id = payload.instagram_id.strip()
    comment_id = payload.comment_id.strip()

    if not instagram_id:
        return {
            "success": False,
            "error": "Не передано instagram_id."
        }

    if not comment_id:
        return {
            "success": False,
            "error": "Не передано comment_id."
        }

    user_access_token = tokens["access_token"]

    async with httpx.AsyncClient(timeout=40) as client:
        (
            page_access_token,
            facebook_page,
            token_error
        ) = await get_instagram_page_access_token(
            client=client,
            instagram_id=instagram_id,
            user_access_token=user_access_token
        )

        if not page_access_token:
            return {
                "success": False,
                "error": "Не вдалося отримати токен Facebook Page.",
                "details": token_error
            }

        response = await client.post(
            f"{META_GRAPH_URL}/{comment_id}",
            data={
                "hide": str(payload.hide).lower(),
                "access_token": page_access_token
            }
        )

    try:
        data = response.json()
    except Exception:
        data = {
            "raw": response.text
        }

    if response.status_code >= 400 or "error" in data:
        return {
            "success": False,
            "error": "Не вдалося змінити видимість коментаря.",
            "details": data
        }

    return {
        "success": True,
        "hidden": payload.hide,
        "message": (
            "Коментар приховано."
            if payload.hide
            else "Коментар знову показується."
        ),
        "instagram_id": instagram_id,
        "comment_id": comment_id,
        "facebook_page": facebook_page,
        "result": data
    }

@app.delete("/api/meta/instagram/comments")
async def meta_instagram_comment_delete(
    payload: InstagramCommentDeleteRequest
):
    tokens = get_meta_tokens()

    if not tokens:
        return {
            "success": False,
            "error": "Meta акаунт не підключено."
        }

    instagram_id = payload.instagram_id.strip()
    comment_id = payload.comment_id.strip()

    if not instagram_id:
        return {
            "success": False,
            "error": "Не передано instagram_id."
        }

    if not comment_id:
        return {
            "success": False,
            "error": "Не передано comment_id."
        }

    user_access_token = tokens["access_token"]

    async with httpx.AsyncClient(timeout=40) as client:
        (
            page_access_token,
            facebook_page,
            token_error
        ) = await get_instagram_page_access_token(
            client=client,
            instagram_id=instagram_id,
            user_access_token=user_access_token
        )

        if not page_access_token:
            return {
                "success": False,
                "error": "Не вдалося отримати токен Facebook Page.",
                "details": token_error
            }

        response = await client.delete(
            f"{META_GRAPH_URL}/{comment_id}",
            params={
                "access_token": page_access_token
            }
        )

    try:
        data = response.json()
    except Exception:
        data = {
            "raw": response.text
        }

    if response.status_code >= 400 or "error" in data:
        return {
            "success": False,
            "error": "Не вдалося видалити коментар.",
            "details": data
        }

    return {
        "success": True,
        "message": "Коментар видалено.",
        "instagram_id": instagram_id,
        "comment_id": comment_id,
        "facebook_page": facebook_page,
        "result": data
    }

@app.get("/api/meta/campaigns")
async def meta_campaigns(ad_account_id: str, limit: int = 50):
    tokens = get_meta_tokens()

    if not tokens:
        return {
            "success": False,
            "error": "Meta акаунт не підключено.",
            "campaigns": []
        }

    if not ad_account_id:
        return {
            "success": False,
            "error": "Не передано ad_account_id.",
            "campaigns": []
        }

    access_token = tokens["access_token"]

    # Meta очікує формат act_123456789
    account_node = ad_account_id if ad_account_id.startswith("act_") else f"act_{ad_account_id}"

    async with httpx.AsyncClient(timeout=40) as client:
        res = await client.get(
            f"{META_GRAPH_URL}/{account_node}/campaigns",
            params={
                "fields": (
                    "id,"
                    "name,"
                    "status,"
                    "effective_status,"
                    "objective,"
                    "buying_type,"
                    "daily_budget,"
                    "lifetime_budget,"
                    "start_time,"
                    "stop_time,"
                    "created_time,"
                    "updated_time"
                ),
                "limit": max(1, min(limit, 100)),
                "access_token": access_token
            }
        )

    data = res.json()

    if "error" in data:
        return {
            "success": False,
            "error": "Не вдалося отримати кампанії Meta Ads.",
            "details": data,
            "campaigns": []
        }

    return {
        "success": True,
        "ad_account_id": account_node,
        "count": len(data.get("data", [])),
        "campaigns": data.get("data", []),
        "paging": data.get("paging", {})
    }

@app.get("/api/meta/campaign/insights")
async def meta_campaign_insights(campaign_id: str, date_preset: str = "last_30d"):
    tokens = get_meta_tokens()

    if not tokens:
        return {
            "success": False,
            "error": "Meta акаунт не підключено.",
            "insights": []
        }

    if not campaign_id:
        return {
            "success": False,
            "error": "Не передано campaign_id.",
            "insights": []
        }

    access_token = tokens["access_token"]

    async with httpx.AsyncClient(timeout=60) as client:
        res = await client.get(
            f"{META_GRAPH_URL}/{campaign_id}/insights",
            params={
                "fields": (
                    "campaign_id,"
                    "campaign_name,"
                    "spend,"
                    "impressions,"
                    "reach,"
                    "clicks,"
                    "cpc,"
                    "cpm,"
                    "ctr,"
                    "frequency,"
                    "actions"
                ),
                "date_preset": date_preset,
                "access_token": access_token
            }
        )

    data = res.json()

    if "error" in data:
        return {
            "success": False,
            "error": "Не вдалося отримати статистику кампанії.",
            "details": data,
            "insights": []
        }

    return {
        "success": True,
        "campaign_id": campaign_id,
        "date_preset": date_preset,
        "insights": data.get("data", []),
        "paging": data.get("paging", {})
    }


@app.get("/api/meta/webhook")
async def meta_webhook_verify(
    hub_mode: str = Query(
        default=None,
        alias="hub.mode"
    ),
    hub_challenge: str = Query(
        default=None,
        alias="hub.challenge"
    ),
    hub_verify_token: str = Query(
        default=None,
        alias="hub.verify_token"
    )
):
    if (
        hub_mode == "subscribe"
        and hub_verify_token == META_VERIFY_TOKEN
    ):
        return Response(
            content=hub_challenge or "",
            media_type="text/plain"
        )

    raise HTTPException(
        status_code=403,
        detail="Meta webhook verification failed"
    )


async def get_meta_participant_profile(
    page_id: str,
    participant_id: str
):
    """
    Отримує ім'я та аватар клієнта Messenger.
    Якщо Meta не поверне профіль, повідомлення все одно збережеться.
    """

    page = get_meta_page(page_id)

    if not page:
        return {}

    page_access_token = page.get("access_token")

    if not page_access_token:
        return {}

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                f"{META_GRAPH_URL}/{participant_id}",
                params={
                    "fields": "first_name,last_name,profile_pic",
                    "access_token": page_access_token
                }
            )

        if response.status_code != 200:
            print(
                "META PROFILE ERROR:",
                response.status_code,
                response.text
            )
            return {}

        data = response.json()

        first_name = str(
            data.get("first_name") or ""
        ).strip()

        last_name = str(
            data.get("last_name") or ""
        ).strip()

        full_name = " ".join(
            part
            for part in [first_name, last_name]
            if part
        ).strip()

        return {
            "name": full_name,
            "avatar": data.get("profile_pic")
        }

    except Exception as error:
        print(
            "META PROFILE EXCEPTION:",
            repr(error)
        )
        return {}

async def get_instagram_participant_profile(
    instagram_id: str,
    participant_id: str
):
    fallback = {
        "name": None,
        "avatar": None
    }

    access_data = await get_instagram_direct_access_data(
        instagram_id
    )

    if not access_data:
        print(
            "INSTAGRAM PROFILE NO ACCESS DATA:",
            {
                "instagram_id": instagram_id,
                "participant_id": participant_id
            }
        )
        return fallback

    page_access_token = access_data.get("page_access_token")

    if not page_access_token:
        print(
            "INSTAGRAM PROFILE NO PAGE TOKEN:",
            access_data
        )
        return fallback

    field_variants = [
        "name,username,profile_pic",
        "name,profile_pic"
    ]

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            for fields in field_variants:
                response = await client.get(
                    f"{META_GRAPH_URL}/{participant_id}",
                    params={
                        "fields": fields,
                        "access_token": page_access_token
                    }
                )

                try:
                    data = response.json()
                except Exception:
                    data = {
                        "raw": response.text
                    }

                if (
                    response.status_code >= 400
                    or "error" in data
                ):
                    print(
                        "INSTAGRAM PROFILE ERROR:",
                        {
                            "fields": fields,
                            "status_code": response.status_code,
                            "data": data
                        }
                    )
                    continue

                username = str(
                    data.get("username") or ""
                ).strip()

                name = str(
                    data.get("name") or ""
                ).strip()

                display_name = (
                    f"@{username}"
                    if username
                    else name
                )

                avatar = (
                    data.get("profile_pic")
                    or data.get("profile_picture_url")
                )

                return {
                    "name": display_name or None,
                    "avatar": avatar
                }

        return fallback

    except Exception as error:
        print(
            "INSTAGRAM PROFILE EXCEPTION:",
            repr(error)
        )
        return fallback


@app.post("/api/meta/webhook")
async def meta_webhook_receive(payload: dict):
    print("META WEBHOOK PAYLOAD:", payload)

    saved_messages = 0
    ignored_events = 0

    try:
        object_type = str(
            payload.get("object") or ""
        ).lower()

        if object_type not in ["page", "instagram"]:
            return {
                "success": True,
                "saved_messages": 0,
                "ignored_events": 0
            }

        platform = (
            "instagram"
            if object_type == "instagram"
            else "facebook"
        )

        entries = payload.get("entry") or []

        for entry in entries:
            entry_page_id = str(
                entry.get("id") or ""
            ).strip()

            messaging_events = (
                entry.get("messaging") or []
            )

            for event in messaging_events:
                try:
                    sender_id = str(
                        event.get("sender", {}).get("id")
                        or ""
                    ).strip()

                    recipient_id = str(
                        event.get("recipient", {}).get("id")
                        or ""
                    ).strip()

                    # Повідомлення доставлено клієнту
                    delivery = event.get("delivery")

                    if delivery:
                        page_id = (
                            entry_page_id
                            or recipient_id
                        )

                        participant_id = sender_id

                        if page_id and participant_id:
                            mark_meta_messages_delivered(
                                page_id=page_id,
                                participant_id=participant_id,
                                watermark=delivery.get(
                                    "watermark",
                                    0
                                ),
                                mids=delivery.get(
                                    "mids",
                                    []
                                ),
                                platform=platform
                            )

                        print(
                            "META MESSAGE DELIVERED:",
                            {
                                "page_id": page_id,
                                "participant_id": participant_id,
                                "watermark": delivery.get(
                                    "watermark"
                                )
                            }
                        )

                        continue

                    # Клієнт прочитав повідомлення
                    read_event = event.get("read")

                    if read_event:
                        page_id = (
                            entry_page_id
                            or recipient_id
                        )

                        participant_id = sender_id

                        if page_id and participant_id:
                            mark_meta_messages_read(
                                page_id=page_id,
                                participant_id=participant_id,
                                watermark=(
                                    read_event.get("watermark")
                                    or event.get("timestamp")
                                    or 0
                                ),
                                platform=platform
                            )

                        print(
                            "META MESSAGE READ:",
                            {
                                "page_id": page_id,
                                "participant_id": participant_id,
                                "watermark": read_event.get(
                                    "watermark"
                                )
                            }
                        )

                        continue

                    message = event.get("message")

                    if not message:
                        ignored_events += 1
                        continue

                    is_echo = bool(
                        message.get("is_echo")
                    )

                    if is_echo:
                        # Повідомлення було відправлено сторінкою
                        page_id = (
                            entry_page_id
                            or sender_id
                        )

                        participant_id = recipient_id
                        direction = "out"

                    else:
                        # Повідомлення надійшло від клієнта
                        page_id = (
                            entry_page_id
                            or recipient_id
                        )

                        participant_id = sender_id
                        direction = "in"

                    if not page_id or not participant_id:
                        print(
                            "META MESSAGE IGNORED: "
                            "немає page_id або participant_id",
                            event
                        )

                        ignored_events += 1
                        continue

                    timestamp = int(
                        event.get("timestamp")
                        or int(time.time() * 1000)
                    )

                    mid = str(
                        message.get("mid")
                        or (
                            f"{page_id}:"
                            f"{participant_id}:"
                            f"{timestamp}:"
                            f"{direction}"
                        )
                    )

                    text = str(
                        message.get("text") or ""
                    ).strip()

                    message_type = "text"
                    attachment_url = None

                    attachments = (
                        message.get("attachments") or []
                    )

                    if attachments:
                        first_attachment = attachments[0]

                        message_type = str(
                            first_attachment.get("type")
                            or "attachment"
                        )

                        attachment_payload = (
                            first_attachment.get("payload")
                            or {}
                        )

                        attachment_url = (
                            attachment_payload.get("url")
                        )

                        if not text:
                            attachment_labels = {
                                "image": "📷 Фото",
                                "video": "🎥 Відео",
                                "audio": "🎵 Аудіо",
                                "file": "📎 Файл",
                                "location": "📍 Геолокація",
                                "fallback": "🔗 Вкладення"
                            }

                            text = attachment_labels.get(
                                message_type,
                                "📎 Вкладення"
                            )

                    if not text:
                        text = "Повідомлення без тексту"

                    participant_name = None
                    participant_avatar = None

                    if direction == "in":
                        if platform == "instagram":
                            profile = await get_instagram_participant_profile(
                                page_id,
                                participant_id
                            )

                            participant_name = (
                                profile.get("name")
                                or ("Instagram клієнт " + participant_id[-6:])
                            )

                            participant_avatar = profile.get("avatar")

                        else:
                            profile = await get_meta_participant_profile(
                                page_id,
                                participant_id
                            )

                            participant_name = profile.get("name")
                            participant_avatar = profile.get("avatar")

                    inserted = save_meta_message(
                        mid=mid,
                        platform=platform,
                        page_id=page_id,
                        participant_id=participant_id,
                        direction=direction,
                        text=text,
                        timestamp=timestamp,
                        message_type=message_type,
                        attachment_url=attachment_url,
                        status=(
                            "sent"
                            if direction == "out"
                            else "received"
                        ),
                        raw_payload=event,
                        participant_name=participant_name,
                        participant_avatar=participant_avatar
                    )

                    if inserted:
                        saved_messages += 1

                    print(
                        "META MESSAGE SAVED:",
                        {
                            "inserted": inserted,
                            "platform": platform,
                            "page_id": page_id,
                            "participant_id": participant_id,
                            "direction": direction,
                            "text": text
                        }
                    )

                except Exception as event_error:
                    print(
                        "META MESSAGE SAVE ERROR:",
                        repr(event_error)
                    )

        return {
            "success": True,
            "saved_messages": saved_messages,
            "ignored_events": ignored_events
        }

    except Exception as error:
        # Meta повинна отримати 200 OK,
        # інакше буде багаторазово повторювати webhook.
        print(
            "META WEBHOOK ERROR:",
            repr(error)
        )

        return {
            "success": True,
            "saved_messages": saved_messages,
            "ignored_events": ignored_events,
            "processing_error": str(error)
        }

@app.get("/api/meta/direct/conversations")
async def meta_direct_conversations(
    page_id: str = "",
    limit: int = 100
):
    tokens = get_meta_tokens()

    if not tokens:
        return {
            "success": False,
            "error": "Meta акаунт не підключено.",
            "conversations": []
        }

    clean_page_id = str(page_id or "").strip()

    conversations = get_meta_conversations(
        page_id=clean_page_id or None,
        platform="facebook",
        limit=limit
    )

    return {
        "success": True,
        "page_id": clean_page_id or None,
        "count": len(conversations),
        "conversations": conversations
    }


@app.get("/api/meta/direct/messages")
async def meta_direct_messages(
    page_id: str,
    participant_id: str,
    limit: int = 200
):
    tokens = get_meta_tokens()

    if not tokens:
        return {
            "success": False,
            "error": "Meta акаунт не підключено.",
            "messages": []
        }

    clean_page_id = str(page_id or "").strip()
    clean_participant_id = str(
        participant_id or ""
    ).strip()

    if not clean_page_id:
        return {
            "success": False,
            "error": "Не передано page_id.",
            "messages": []
        }

    if not clean_participant_id:
        return {
            "success": False,
            "error": "Не передано participant_id.",
            "messages": []
        }

    messages = get_meta_messages(
        page_id=clean_page_id,
        participant_id=clean_participant_id,
        platform="facebook",
        limit=limit
    )

    message_ids = [
        str(message.get("mid") or "")
        for message in messages
        if message.get("mid")
    ]

    reactions_map = get_meta_reactions_for_messages(
        message_ids
    )

    for message in messages:
        mid = str(message.get("mid") or "")
        message["reactions"] = reactions_map.get(mid, [])

    return {
        "success": True,
        "page_id": clean_page_id,
        "participant_id": clean_participant_id,
        "count": len(messages),
        "messages": messages
    }


@app.post("/api/meta/direct/read")
async def meta_direct_mark_read(
    page_id: str,
    participant_id: str
):
    tokens = get_meta_tokens()

    if not tokens:
        return {
            "success": False,
            "error": "Meta акаунт не підключено."
        }

    clean_page_id = str(page_id or "").strip()
    clean_participant_id = str(
        participant_id or ""
    ).strip()

    if not clean_page_id:
        return {
            "success": False,
            "error": "Не передано page_id."
        }

    if not clean_participant_id:
        return {
            "success": False,
            "error": "Не передано participant_id."
        }

    mark_meta_conversation_read(
        page_id=clean_page_id,
        participant_id=clean_participant_id,
        platform="facebook"
    )

    return {
        "success": True,
        "message": "Діалог позначено прочитаним.",
        "page_id": clean_page_id,
        "participant_id": clean_participant_id
    }

@app.post("/api/meta/direct/reaction")
async def meta_direct_reaction(
    payload: MetaMessageReactionRequest
):
    mid = str(payload.mid or "").strip()
    platform = str(payload.platform or "").strip().lower()
    page_id = str(payload.page_id or "").strip()
    participant_id = str(payload.participant_id or "").strip()
    reaction = str(payload.reaction or "").strip()

    if not mid:
        return {
            "success": False,
            "error": "Не передано mid повідомлення."
        }

    if platform not in ["facebook", "instagram"]:
        return {
            "success": False,
            "error": "platform має бути facebook або instagram."
        }

    if not page_id:
        return {
            "success": False,
            "error": "Не передано page_id / instagram_id."
        }

    if not participant_id:
        return {
            "success": False,
            "error": "Не передано participant_id."
        }

    return save_meta_message_reaction(
        mid=mid,
        platform=platform,
        page_id=page_id,
        participant_id=participant_id,
        reaction=reaction,
        reacted_by="manager"
    )


@app.delete("/api/meta/direct/reaction")
async def meta_direct_reaction_delete(
    mid: str
):
    clean_mid = str(mid or "").strip()

    if not clean_mid:
        return {
            "success": False,
            "error": "Не передано mid повідомлення."
        }

    return delete_meta_message_reaction(
        mid=clean_mid,
        reacted_by="manager"
    )

@app.get("/api/meta/instagram/direct/conversations")
async def meta_instagram_direct_conversations(
    instagram_id: str = "",
    limit: int = 100
):
    tokens = get_meta_tokens()

    if not tokens:
        return {
            "success": False,
            "error": "Meta акаунт не підключено.",
            "conversations": []
        }

    clean_instagram_id = str(
        instagram_id or ""
    ).strip()

    conversations = get_meta_conversations(
        page_id=clean_instagram_id or None,
        platform="instagram",
        limit=limit
    )

    for conversation in conversations:
        old_name = str(
            conversation.get("participant_name") or ""
        ).strip()

        old_avatar = str(
            conversation.get("participant_avatar") or ""
        ).strip()

        needs_profile = (
            not old_avatar
            or not old_name
            or old_name.startswith("Instagram клієнт")
        )

        if not needs_profile:
            continue

        profile = await get_instagram_participant_profile(
            instagram_id,
            conversation.get("participant_id")
        )

        new_name = profile.get("name")
        new_avatar = profile.get("avatar")

        if new_name or new_avatar:
            update_meta_conversation_profile(
                platform="instagram",
                page_id=instagram_id,
                participant_id=conversation.get("participant_id"),
                participant_name=new_name,
                participant_avatar=new_avatar
            )

            if new_name:
                conversation["participant_name"] = new_name

            if new_avatar:
                conversation["participant_avatar"] = new_avatar

    return {
        "success": True,
        "instagram_id": clean_instagram_id or None,
        "count": len(conversations),
        "conversations": conversations
    }


@app.get("/api/meta/instagram/direct/messages")
async def meta_instagram_direct_messages(
    instagram_id: str,
    participant_id: str,
    limit: int = 200
):
    tokens = get_meta_tokens()

    if not tokens:
        return {
            "success": False,
            "error": "Meta акаунт не підключено.",
            "messages": []
        }

    clean_instagram_id = str(
        instagram_id or ""
    ).strip()

    clean_participant_id = str(
        participant_id or ""
    ).strip()

    if not clean_instagram_id:
        return {
            "success": False,
            "error": "Не передано instagram_id.",
            "messages": []
        }

    if not clean_participant_id:
        return {
            "success": False,
            "error": "Не передано participant_id.",
            "messages": []
        }

    messages = get_meta_messages(
        page_id=clean_instagram_id,
        participant_id=clean_participant_id,
        platform="instagram",
        limit=limit
    )

    message_ids = [
        str(message.get("mid") or "")
        for message in messages
        if message.get("mid")
    ]

    reactions_map = get_meta_reactions_for_messages(
        message_ids
    )

    for message in messages:
        mid = str(message.get("mid") or "")
        message["reactions"] = reactions_map.get(mid, [])

    return {
        "success": True,
        "instagram_id": clean_instagram_id,
        "participant_id": clean_participant_id,
        "count": len(messages),
        "messages": messages
    }


@app.post("/api/meta/instagram/direct/read")
async def meta_instagram_direct_mark_read(
    instagram_id: str,
    participant_id: str
):
    tokens = get_meta_tokens()

    if not tokens:
        return {
            "success": False,
            "error": "Meta акаунт не підключено."
        }

    clean_instagram_id = str(
        instagram_id or ""
    ).strip()

    clean_participant_id = str(
        participant_id or ""
    ).strip()

    if not clean_instagram_id:
        return {
            "success": False,
            "error": "Не передано instagram_id."
        }

    if not clean_participant_id:
        return {
            "success": False,
            "error": "Не передано participant_id."
        }

    mark_meta_conversation_read(
        page_id=clean_instagram_id,
        participant_id=clean_participant_id,
        platform="instagram"
    )

    return {
        "success": True,
        "message": "Instagram-діалог позначено прочитаним.",
        "instagram_id": clean_instagram_id,
        "participant_id": clean_participant_id
    }

@app.get("/api/meta/direct/media/{filename}")
async def meta_direct_media(
    filename: str,
    download: bool = False
):
    safe_filename = Path(filename).name

    if safe_filename != filename:
        raise HTTPException(
            status_code=400,
            detail="Некоректне ім’я файлу."
        )

    file_path = DIRECT_UPLOAD_ROOT / safe_filename

    if not file_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="Файл не знайдено."
        )

    if download:
        return FileResponse(
            file_path,
            filename=safe_filename,
            media_type="application/octet-stream"
        )

    return FileResponse(file_path)

@app.get("/d/{filename}")
async def meta_direct_short_download(filename: str):
    return await meta_direct_media(
        filename=filename,
        download=True
    )

class MetaInstagramDirectSendRequest(BaseModel):
    instagram_id: str
    participant_id: str
    message: str


async def get_instagram_direct_access_data(instagram_id: str):
    tokens = get_meta_tokens()

    if not tokens:
        return None

    user_access_token = tokens.get("access_token")

    if not user_access_token:
        return None

    async with httpx.AsyncClient(timeout=40) as client:
        (
            page_access_token,
            facebook_page,
            token_error
        ) = await get_instagram_page_access_token(
            client=client,
            instagram_id=instagram_id,
            user_access_token=user_access_token
        )

    if not page_access_token or not facebook_page:
        print(
            "INSTAGRAM DIRECT ACCESS ERROR:",
            token_error
        )
        return None

    facebook_page_id = str(
        facebook_page.get("id") or ""
    ).strip()

    if not facebook_page_id:
        return None

    return {
        "facebook_page_id": facebook_page_id,
        "facebook_page_name": facebook_page.get("name"),
        "page_access_token": page_access_token
    }

class MetaInstagramDirectSendRequest(BaseModel):
    instagram_id: str
    participant_id: str
    message: str


@app.post("/api/meta/instagram/direct/send")
async def meta_instagram_direct_send(
    payload: MetaInstagramDirectSendRequest
):
    tokens = get_meta_tokens()

    if not tokens:
        return {
            "success": False,
            "error": "Meta акаунт не підключено."
        }

    instagram_id = str(
        payload.instagram_id or ""
    ).strip()

    participant_id = str(
        payload.participant_id or ""
    ).strip()

    message_text = str(
        payload.message or ""
    ).strip()

    if not instagram_id:
        return {
            "success": False,
            "error": "Не передано instagram_id."
        }

    if not participant_id:
        return {
            "success": False,
            "error": "Не передано participant_id."
        }

    if not message_text:
        return {
            "success": False,
            "error": "Повідомлення порожнє."
        }

    access_data = await get_instagram_direct_access_data(
        instagram_id
    )

    if not access_data:
        return {
            "success": False,
            "error": (
                "Не знайдено Facebook Page Access Token "
                "для цього Instagram акаунта."
            )
        }

    page_access_token = access_data.get(
        "page_access_token"
    )

    facebook_page_id = str(
        access_data.get("facebook_page_id") or ""
    ).strip()

    if not facebook_page_id:
        return {
            "success": False,
            "error": (
                "Не знайдено Facebook Page ID "
                "для цього Instagram акаунта."
            ),
            "details": access_data
        }

    request_body, policy_error = build_meta_send_request_body(
        platform="instagram",
        page_id=instagram_id,
        participant_id=participant_id,
        message_payload={
            "text": message_text
        }
    )

    if policy_error:
        return policy_error

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{META_GRAPH_URL}/{facebook_page_id}/messages",
                params={
                    "access_token": page_access_token
                },
                json=request_body
            )

        try:
            data = response.json()
        except Exception:
            data = {
                "raw": response.text
            }

        if (
            response.status_code >= 400
            or "error" in data
        ):
            return {
                "success": False,
                "error": (
                    "Meta не дозволила надіслати "
                    "Instagram Direct повідомлення."
                ),
                "details": data
            }

        timestamp = int(
            time.time() * 1000
        )

        message_id = str(
            data.get("message_id")
            or (
                f"crm-instagram:"
                f"{instagram_id}:"
                f"{participant_id}:"
                f"{timestamp}"
            )
        )

        save_meta_message(
            mid=message_id,
            platform="instagram",
            page_id=instagram_id,
            participant_id=participant_id,
            direction="out",
            text=message_text,
            timestamp=timestamp,
            message_type="text",
            attachment_url=None,
            status="sent",
            raw_payload={
                "source": "crm",
                "meta_response": data,
                "instagram_id": instagram_id,
                "facebook_page_id": facebook_page_id
            }
        )

        return {
            "success": True,
            "message": "Instagram Direct повідомлення надіслано.",
            "message_id": message_id,
            "instagram_id": instagram_id,
            "participant_id": participant_id,
            "text": message_text
        }

    except Exception as error:
        print(
            "INSTAGRAM DIRECT SEND ERROR:",
            repr(error)
        )

        return {
            "success": False,
            "error": "Помилка надсилання Instagram Direct.",
            "details": str(error)
        }

class MetaDirectSendRequest(BaseModel):
    page_id: str
    participant_id: str
    message: str

@app.get("/api/meta/instagram/direct/profile-debug")
async def meta_instagram_direct_profile_debug(
    instagram_id: str,
    participant_id: str
):
    access_data = await get_instagram_direct_access_data(
        instagram_id
    )

    if not access_data:
        return {
            "success": False,
            "error": "Не знайдено access data для Instagram.",
            "instagram_id": instagram_id,
            "participant_id": participant_id
        }

    page_access_token = access_data.get("page_access_token")

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(
            f"{META_GRAPH_URL}/{participant_id}",
            params={
                "fields": "id,name,username,profile_pic",
                "access_token": page_access_token
            }
        )

    try:
        data = response.json()
    except Exception:
        data = {
            "raw": response.text
        }

    return {
        "success": response.status_code < 400 and "error" not in data,
        "status_code": response.status_code,
        "instagram_id": instagram_id,
        "participant_id": participant_id,
        "access_data": {
            "facebook_page_id": access_data.get("facebook_page_id"),
            "has_page_token": bool(page_access_token)
        },
        "meta_response": data
    }


@app.post("/api/meta/direct/send")
async def meta_direct_send(
    payload: MetaDirectSendRequest
):
    tokens = get_meta_tokens()

    if not tokens:
        return {
            "success": False,
            "error": "Meta акаунт не підключено."
        }

    page_id = str(
        payload.page_id or ""
    ).strip()

    participant_id = str(
        payload.participant_id or ""
    ).strip()

    message_text = str(
        payload.message or ""
    ).strip()

    if not page_id:
        return {
            "success": False,
            "error": "Не передано page_id."
        }

    if not participant_id:
        return {
            "success": False,
            "error": "Не передано participant_id."
        }

    if not message_text:
        return {
            "success": False,
            "error": "Повідомлення порожнє."
        }

    page = get_meta_page(page_id)

    if not page:
        return {
            "success": False,
            "error": "Facebook-сторінку не знайдено в базі."
        }

    page_access_token = page.get(
        "access_token"
    )

    if not page_access_token:
        return {
            "success": False,
            "error": "У сторінки немає Page Access Token."
        }

    request_body, policy_error = build_meta_send_request_body(
        platform="facebook",
        page_id=page_id,
        participant_id=participant_id,
        message_payload={
            "text": message_text
        }
    )

    if policy_error:
        return policy_error

    try:
        async with httpx.AsyncClient(
            timeout=30
        ) as client:
            response = await client.post(
                f"{META_GRAPH_URL}/{page_id}/messages",
                params={
                    "access_token": page_access_token
                },
                json=request_body
            )

        try:
            data = response.json()
        except Exception:
            data = {
                "raw": response.text
            }

        if (
            response.status_code >= 400
            or "error" in data
        ):
            return {
                "success": False,
                "error": (
                    "Meta не дозволила "
                    "надіслати повідомлення."
                ),
                "details": data
            }

        timestamp = int(
            time.time() * 1000
        )

        message_id = str(
            data.get("message_id")
            or (
                f"crm:{page_id}:"
                f"{participant_id}:"
                f"{timestamp}"
            )
        )

        save_meta_message(
            mid=message_id,
            platform="facebook",
            page_id=page_id,
            participant_id=participant_id,
            direction="out",
            text=message_text,
            timestamp=timestamp,
            message_type="text",
            attachment_url=None,
            status="sent",
            raw_payload={
                "source": "crm",
                "meta_response": data
            }
        )

        return {
            "success": True,
            "message": "Повідомлення надіслано.",
            "message_id": message_id,
            "page_id": page_id,
            "participant_id": participant_id,
            "text": message_text
        }

    except Exception as error:
        print(
            "META DIRECT SEND ERROR:",
            repr(error)
        )

        return {
            "success": False,
            "error": "Помилка надсилання повідомлення.",
            "details": str(error)
        }

@app.post("/api/meta/direct/send-image")
async def meta_direct_send_image(
    page_id: str = Form(...),
    participant_id: str = Form(...),
    image: UploadFile = File(...)
):
    clean_page_id = str(page_id or "").strip()
    clean_participant_id = str(participant_id or "").strip()

    if not clean_page_id:
        return {
            "success": False,
            "error": "Не передано page_id."
        }

    if not clean_participant_id:
        return {
            "success": False,
            "error": "Не передано participant_id."
        }

    content_type = str(image.content_type or "").lower()
    extension = DIRECT_IMAGE_TYPES.get(content_type)

    if not extension:
        return {
            "success": False,
            "error": "Підтримуються тільки JPG, PNG та GIF."
        }

    image_bytes = await image.read()

    if not image_bytes:
        return {
            "success": False,
            "error": "Файл порожній."
        }

    if len(image_bytes) > DIRECT_IMAGE_MAX_BYTES:
        return {
            "success": False,
            "error": "Фото завелике. Максимальний розмір — 8 МБ."
        }

    page = get_meta_page(clean_page_id)

    if not page:
        return {
            "success": False,
            "error": "Facebook-сторінку не знайдено в базі."
        }

    page_access_token = page.get("access_token")

    if not page_access_token:
        return {
            "success": False,
            "error": "У сторінки немає Page Access Token."
        }

    stored_filename = f"{uuid4().hex}{extension}"
    stored_path = DIRECT_UPLOAD_ROOT / stored_filename
    stored_path.write_bytes(image_bytes)

    attachment_url = (
        f"{APP_PUBLIC_URL}"
        f"/api/meta/direct/media/"
        f"{stored_filename}"
    )

    request_body = {
        "messaging_type": "RESPONSE",
        "recipient": {
            "id": clean_participant_id
        },
        "message": {
            "attachment": {
                "type": "image",
                "payload": {
                    "url": attachment_url
                }
            }
        }
    }

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            send_response = await client.post(
                f"{META_GRAPH_URL}/{clean_page_id}/messages",
                params={
                    "access_token": page_access_token
                },
                json=request_body
            )

        try:
            send_result = send_response.json()
        except Exception:
            send_result = {
                "raw": send_response.text
            }

        if (
            send_response.status_code >= 400
            or "error" in send_result
        ):
            return {
                "success": False,
                "error": (
                    send_result.get("error", {}).get("message")
                    or "Meta не дозволила надіслати фото."
                ),
                "details": send_result
            }

        timestamp = int(time.time() * 1000)

        message_id = str(
            send_result.get("message_id")
            or (
                f"crm-image:"
                f"{clean_page_id}:"
                f"{clean_participant_id}:"
                f"{timestamp}"
            )
        )

        save_meta_message(
            mid=message_id,
            platform="facebook",
            page_id=clean_page_id,
            participant_id=clean_participant_id,
            direction="out",
            text="📷 Фото",
            timestamp=timestamp,
            message_type="image",
            attachment_url=attachment_url,
            status="sent",
            raw_payload={
                "source": "crm",
                "attachment_url": attachment_url,
                "meta_response": send_result
            },
            participant_name=None,
            participant_avatar=None
        )

        return {
            "success": True,
            "message": "Фото надіслано.",
            "message_id": message_id,
            "attachment_url": attachment_url
        }

    except Exception as error:
        print(
            "META DIRECT IMAGE ERROR:",
            repr(error)
        )

        return {
            "success": False,
            "error": "Помилка надсилання фото.",
            "details": str(error)
        }

@app.post("/api/meta/instagram/direct/send-image")
async def meta_instagram_direct_send_image(
    instagram_id: str = Form(...),
    participant_id: str = Form(...),
    image: UploadFile = File(...)
):
    clean_instagram_id = str(
        instagram_id or ""
    ).strip()

    clean_participant_id = str(
        participant_id or ""
    ).strip()

    if not clean_instagram_id:
        return {
            "success": False,
            "error": "Не передано instagram_id."
        }

    if not clean_participant_id:
        return {
            "success": False,
            "error": "Не передано participant_id."
        }

    content_type = str(
        image.content_type or ""
    ).lower()

    extension = DIRECT_IMAGE_TYPES.get(
        content_type
    )

    if not extension:
        return {
            "success": False,
            "error": "Підтримуються тільки JPG, PNG та GIF."
        }

    image_bytes = await image.read()

    if not image_bytes:
        return {
            "success": False,
            "error": "Файл порожній."
        }

    if len(image_bytes) > DIRECT_IMAGE_MAX_BYTES:
        return {
            "success": False,
            "error": "Фото завелике. Максимальний розмір — 8 МБ."
        }

    access_data = await get_instagram_direct_access_data(
        clean_instagram_id
    )

    if not access_data:
        return {
            "success": False,
            "error": (
                "Не знайдено Facebook Page Access Token "
                "для цього Instagram акаунта."
            )
        }

    page_access_token = access_data.get(
        "page_access_token"
    )

    facebook_page_id = str(
        access_data.get("facebook_page_id") or ""
    ).strip()

    if not facebook_page_id:
        return {
            "success": False,
            "error": (
                "Не знайдено Facebook Page ID "
                "для цього Instagram акаунта."
            ),
            "details": access_data
        }

    stored_filename = f"{uuid4().hex}{extension}"
    stored_path = DIRECT_UPLOAD_ROOT / stored_filename
    stored_path.write_bytes(image_bytes)

    attachment_url = (
        f"{APP_PUBLIC_URL}"
        f"/api/meta/direct/media/"
        f"{stored_filename}"
    )

    request_body = {
        "messaging_type": "RESPONSE",
        "recipient": {
            "id": clean_participant_id
        },
        "message": {
            "attachment": {
                "type": "image",
                "payload": {
                    "url": attachment_url
                }
            }
        }
    }

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{META_GRAPH_URL}/{facebook_page_id}/messages",
                params={
                    "access_token": page_access_token
                },
                json=request_body
            )

        try:
            data = response.json()
        except Exception:
            data = {
                "raw": response.text
            }

        if response.status_code >= 400 or "error" in data:
            return {
                "success": False,
                "error": (
                    data.get("error", {}).get("message")
                    or "Meta не дозволила надіслати фото в Instagram Direct."
                ),
                "details": data
            }

        timestamp = int(time.time() * 1000)

        message_id = str(
            data.get("message_id")
            or (
                f"crm-instagram-image:"
                f"{clean_instagram_id}:"
                f"{clean_participant_id}:"
                f"{timestamp}"
            )
        )

        save_meta_message(
            mid=message_id,
            platform="instagram",
            page_id=clean_instagram_id,
            participant_id=clean_participant_id,
            direction="out",
            text="📷 Фото",
            timestamp=timestamp,
            message_type="image",
            attachment_url=attachment_url,
            status="sent",
            raw_payload={
                "source": "crm",
                "instagram_id": clean_instagram_id,
                "facebook_page_id": facebook_page_id,
                "attachment_url": attachment_url,
                "meta_response": data
            }
        )

        return {
            "success": True,
            "message": "Фото в Instagram Direct надіслано.",
            "message_id": message_id,
            "instagram_id": clean_instagram_id,
            "participant_id": clean_participant_id,
            "attachment_url": attachment_url
        }

    except Exception as error:
        print(
            "INSTAGRAM DIRECT IMAGE ERROR:",
            repr(error)
        )

        return {
            "success": False,
            "error": "Помилка надсилання фото в Instagram Direct.",
            "details": str(error)
        }

@app.post("/api/meta/direct/send-file")
async def meta_direct_send_file(
    page_id: str = Form(...),
    participant_id: str = Form(...),
    file: UploadFile = File(...)
):
    clean_page_id = str(page_id or "").strip()
    clean_participant_id = str(participant_id or "").strip()

    if not clean_page_id:
        return {
            "success": False,
            "error": "Не передано page_id."
        }

    if not clean_participant_id:
        return {
            "success": False,
            "error": "Не передано participant_id."
        }

    try:
        saved_file = await save_direct_upload_file(file)
    except HTTPException as error:
        return {
            "success": False,
            "error": error.detail
        }

    page = get_meta_page(clean_page_id)

    if not page:
        return {
            "success": False,
            "error": "Facebook-сторінку не знайдено в базі."
        }

    page_access_token = page.get("access_token")

    if not page_access_token:
        return {
            "success": False,
            "error": "У сторінки немає Page Access Token."
        }

    attachment_type = saved_file.get("attachment_type") or "file"

    if attachment_type not in ["image", "video", "audio", "file"]:
        attachment_type = "file"

    request_body = {
        "messaging_type": "RESPONSE",
        "recipient": {
            "id": clean_participant_id
        },
        "message": {
            "attachment": {
                "type": attachment_type,
                "payload": {
                    "url": saved_file["url"]
                }
            }
        }
    }

    timestamp = int(time.time() * 1000)

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            send_response = await client.post(
                f"{META_GRAPH_URL}/{clean_page_id}/messages",
                params={
                    "access_token": page_access_token
                },
                json=request_body
            )

        try:
            send_result = send_response.json()
        except Exception:
            send_result = {
                "raw": send_response.text
            }

        sent_to_meta = (
            send_response.status_code < 400
            and "error" not in send_result
        )

        if not sent_to_meta:
            error_obj = (
                send_result.get("error")
                if isinstance(send_result, dict)
                else None
            )

            if isinstance(error_obj, dict):
                meta_error = error_obj.get("message")
            elif isinstance(error_obj, str):
                meta_error = error_obj
            else:
                meta_error = None

            if not meta_error and isinstance(send_result, dict):
                meta_error = (
                    send_result.get("message")
                    or send_result.get("raw")
                )

            meta_error = (
                meta_error
                or "Meta не прийняла файл для надсилання клієнту."
            )

            return {
                "success": False,
                "sent_to_meta": False,
                "error": meta_error,
                "details": send_result
            }

        message_id = str(
            send_result.get("message_id")
            or (
                f"crm-file:"
                f"{clean_page_id}:"
                f"{clean_participant_id}:"
                f"{timestamp}"
            )
        )

        save_meta_message(
            mid=message_id,
            platform="facebook",
            page_id=clean_page_id,
            participant_id=clean_participant_id,
            direction="out",
            text=f"📎 {saved_file['original_name']}",
            timestamp=timestamp,
            message_type=attachment_type,
            attachment_url=saved_file["url"],
            status="sent",
            raw_payload={
                "source": "crm",
                "file": {
                    "name": saved_file["original_name"],
                    "url": saved_file["url"],
                    "content_type": saved_file["content_type"],
                    "size": saved_file["size"],
                    "attachment_type": attachment_type
                },
                "meta_response": send_result
            }
        )

        return {
            "success": True,
            "sent_to_meta": True,
            "message": "Файл надіслано.",
            "message_id": message_id,
            "file": {
                "name": saved_file["original_name"],
                "url": saved_file["url"],
                "download_url": saved_file["url"] + "?download=1"
            }
        }

    except Exception as error:
        print(
            "META DIRECT FILE ERROR:",
            repr(error)
        )

        return {
            "success": False,
            "error": "Помилка надсилання файлу.",
            "details": str(error)
        }

@app.post("/api/meta/instagram/direct/send-file")
async def meta_instagram_direct_send_file(
    instagram_id: str = Form(...),
    participant_id: str = Form(...),
    file: UploadFile = File(...)
):
    clean_instagram_id = str(instagram_id or "").strip()
    clean_participant_id = str(participant_id or "").strip()

    if not clean_instagram_id:
        return {
            "success": False,
            "error": "Не передано instagram_id."
        }

    if not clean_participant_id:
        return {
            "success": False,
            "error": "Не передано participant_id."
        }

    try:
        saved_file = await save_direct_upload_file(file)
    except HTTPException as error:
        return {
            "success": False,
            "error": error.detail
        }

    access_data = await get_instagram_direct_access_data(
        clean_instagram_id
    )

    if not access_data:
        return {
            "success": False,
            "error": "Не знайдено Facebook Page Access Token для цього Instagram акаунта."
        }

    page_access_token = access_data.get("page_access_token")
    facebook_page_id = str(
        access_data.get("facebook_page_id") or ""
    ).strip()

    if not facebook_page_id:
        return {
            "success": False,
            "error": "Не знайдено Facebook Page ID для цього Instagram акаунта.",
            "details": access_data
        }

    attachment_type = saved_file.get("attachment_type") or "file"
    timestamp = int(time.time() * 1000)

    # ✅ Instagram нормально відправляємо як attachment тільки медіа
    can_send_as_attachment = attachment_type in ["image", "video", "audio"]

    try:
        async with httpx.AsyncClient(timeout=60) as client:

            if can_send_as_attachment:
                request_body = {
                    "messaging_type": "RESPONSE",
                    "recipient": {
                        "id": clean_participant_id
                    },
                    "message": {
                        "attachment": {
                            "type": attachment_type,
                            "payload": {
                                "url": saved_file["url"]
                            }
                        }
                    }
                }

                response = await client.post(
                    f"{META_GRAPH_URL}/{facebook_page_id}/messages",
                    params={
                        "access_token": page_access_token
                    },
                    json=request_body
                )

            else:
                # ✅ Для pdf/docx/pptx/zip тощо відправляємо посилання текстом
                file_link = f"{APP_PUBLIC_URL}/d/{saved_file['stored_filename']}"

                request_body = {
                    "messaging_type": "RESPONSE",
                    "recipient": {
                        "id": clean_participant_id
                    },
                    "message": {
                        "text": (
                            f"📎 Файл: {saved_file['original_name']}\n"
                            f"{file_link}"
                        )
                    }
                }

                response = await client.post(
                    f"{META_GRAPH_URL}/{facebook_page_id}/messages",
                    params={
                        "access_token": page_access_token
                    },
                    json=request_body
                )

        try:
            data = response.json()
        except Exception:
            data = {
                "raw": response.text
            }

        sent_to_meta = (
            response.status_code < 400
            and "error" not in data
        )

        message_id = str(
            data.get("message_id")
            or (
                f"crm-instagram-file:"
                f"{clean_instagram_id}:"
                f"{clean_participant_id}:"
                f"{timestamp}"
            )
        )

        save_meta_message(
            mid=message_id,
            platform="instagram",
            page_id=clean_instagram_id,
            participant_id=clean_participant_id,
            direction="out",
            text=f"📎 {saved_file['original_name']}",
            timestamp=timestamp,
            message_type=attachment_type,
            attachment_url=saved_file["url"],
            status="sent" if sent_to_meta else "local",
            raw_payload={
                "source": "crm",
                "instagram_id": clean_instagram_id,
                "facebook_page_id": facebook_page_id,
                "file": {
                    "name": saved_file["original_name"],
                    "url": saved_file["url"],
                    "content_type": saved_file["content_type"],
                    "size": saved_file["size"],
                    "attachment_type": attachment_type
                },
                "meta_response": data
            }
        )

        if not sent_to_meta:
            return {
                "success": False,
                "error": "Meta не дозволила надіслати файл в Instagram Direct.",
                "details": data,
                "saved_local": True
            }

        return {
            "success": True,
            "message": "Файл надіслано в Instagram Direct.",
            "message_id": message_id,
            "instagram_id": clean_instagram_id,
            "participant_id": clean_participant_id,
            "attachment_url": saved_file["url"],
            "attachment_type": attachment_type,
            "filename": saved_file["original_name"]
        }

    except Exception as error:
        print("INSTAGRAM DIRECT FILE SEND ERROR:", repr(error))

        return {
            "success": False,
            "error": "Помилка надсилання файлу в Instagram Direct.",
            "details": str(error)
        }

@app.get("/api/meta/debug")
async def meta_debug():
    tokens = get_meta_tokens()

    if not tokens:
        return {
            "success": False,
            "error": "Meta акаунт не підключено."
        }

    access_token = tokens["access_token"]

    async with httpx.AsyncClient(timeout=40) as client:
        permissions_res = await client.get(
            f"{META_GRAPH_URL}/me/permissions",
            params={
                "access_token": access_token
            }
        )

        me_res = await client.get(
            f"{META_GRAPH_URL}/me",
            params={
                "fields": "id,name,email",
                "access_token": access_token
            }
        )

        accounts_res = await client.get(
            f"{META_GRAPH_URL}/me/accounts",
            params={
                "fields": "id,name,category,tasks",
                "limit": 100,
                "access_token": access_token
            }
        )

        businesses_res = await client.get(
            f"{META_GRAPH_URL}/me/businesses",
            params={
                "fields": "id,name,verification_status",
                "limit": 100,
                "access_token": access_token
            }
        )

        businesses_data = businesses_res.json()
        businesses = businesses_data.get("data", [])

        business_pages = []

        for business in businesses:
            business_id = business.get("id")

            owned_pages_res = await client.get(
                f"{META_GRAPH_URL}/{business_id}/owned_pages",
                params={
                    "fields": "id,name,category,access_token",
                    "limit": 100,
                    "access_token": access_token
                }
            )

            client_pages_res = await client.get(
                f"{META_GRAPH_URL}/{business_id}/client_pages",
                params={
                    "fields": "id,name,category,access_token",
                    "limit": 100,
                    "access_token": access_token
                }
            )

            business_pages.append({
                "business": business,
                "owned_pages": owned_pages_res.json(),
                "client_pages": client_pages_res.json()
            })

    return {
        "success": True,
        "me": me_res.json(),
        "permissions": permissions_res.json(),
        "me_accounts": accounts_res.json(),
        "businesses": businesses_data,
        "business_pages": business_pages
    }
