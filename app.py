from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import time
import httpx
import base64
from fastapi.responses import RedirectResponse, Response
from urllib.parse import urlencode
from datetime import datetime, timezone
from dotenv import load_dotenv
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
    get_meta_pages
)

load_dotenv()

app = FastAPI()

init_db()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL = "openai/gpt-4o-mini"
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")
CRM_URL = os.getenv("CRM_URL", "http://127.0.0.1:5500/index.html")
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/presentations",
    "https://www.googleapis.com/auth/drive",
]

META_APP_ID = os.getenv("META_APP_ID", "")
META_APP_SECRET = os.getenv("META_APP_SECRET", "")
META_REDIRECT_URI = os.getenv(
    "META_REDIRECT_URI",
    "https://sitechat-production.up.railway.app/api/meta/callback"
)
META_VERIFY_TOKEN = os.getenv("META_VERIFY_TOKEN", "itenai_meta_verify_2026")

META_GRAPH_VERSION = os.getenv("META_GRAPH_VERSION", "v25.0")
META_GRAPH_URL = f"https://graph.facebook.com/{META_GRAPH_VERSION}"

META_SCOPES = [
    "public_profile",
    "email",
    "business_management",
    "ads_read",
    "ads_management",
    "pages_show_list",
    "pages_read_engagement",
    "pages_manage_ads",

    "instagram_basic",
    "instagram_manage_comments",
    "instagram_manage_insights",
    "instagram_manage_messages",
    "instagram_content_publish"
]

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
- Не починай діалог заново
- Не вітайся повторно
- Якщо клієнт вже відповів — продовжуй розмову

Не вигадуй курси.
Використовуй тільки ці напрямки:
Roblox, Python, AI, 3D, Блогінг.
"""

class ChatRequest(BaseModel):
    message: str

@app.post("/chat")
async def chat(req: ChatRequest):

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
    course_roblox = any(x in msg_lower for x in ["roblox", "роблокс", "lua"])
    course_python = any(x in msg_lower for x in ["python", "пітон"])
    course_3d = any(x in msg_lower for x in ["3d", "блендер", "моделювання", "3д"])
    course_ai = any(x in msg_lower for x in ["ai", "штучний", "інтелект"])
    course_blog = any(x in msg_lower for x in ["блог", "відео", "зйомка"])
    course_pc = any(x in msg_lower for x in ["комп", "грамот", "пк", "кг"])


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
                "Напишіть:\n• ім’я\n• вік\n\n"
                "і підберемо час 👇"
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
        return {"response": "🎮 Roblox\n• створення вланих проєктів, ігор, також цікаві карти\n• Lua програмування де можна кодувати на рівні про\n• проекти, задачі\n💰 250 / 450 грн"}

    if course_python and not ("що" in msg_lower or "чому" in msg_lower):
        return {"response": "💻 Python\n• програмування на базі пайтон\n• логіка, цікаві візуальні ігри\n• проекти, завдання\n💰 250 / 450 грн"}

    if course_3d and not ("що" in msg_lower or "чому" in msg_lower):
        return {"response": "🎨 3D\n• Blender\n• моделі, свої персонажі\n• проекти, персоналі задачі по створенню моделей\n💰 250 / 450 грн"}

    if course_ai and not ("що" in msg_lower or "чому" in msg_lower):
        return {"response": "🤖 AI\n• нейромережі, їх поведінка їхні задачі та завдання\n• проекти, навчанню штучного інтелекту, як з ним комунікувати правильно\n💰 250 / 450 грн"}

    if course_blog and not ("що" in msg_lower or "чому" in msg_lower):
        return {"response": "📹 Блогінг\n• відео, уроки\n• монтаж, навчання правильного монтажу\n💰 250 / 450 грн"}

    if course_pc and not ("що" in msg_lower or "чому" in msg_lower):
        return {"response": "💻 Комп’ютерна грамотність, навчання базовим навичкам користування пк\n• Що таке персональний комп'ютер\n• інтернет та передача данних\n• безпека і боротьба з зловмисним ПЗ\n💰 250 / 450 грн"}


    # 📚 СПИСОК КУРСІВ
    if "курси" in msg_lower or "список" in msg_lower or "що є" in msg_lower:
        return {
            "response": (
                "🎮 Roblox — створення ігор + програмування на Lua\n"
                "💻 Python — програмування, логіка, створення проєктів\n"
                "🤖 AI — робота зі штучним інтелектом\n"
                "🎨 3D — моделювання в Blender\n"
                "📹 Блогінг — створення відео, монтаж, розвиток каналу\n"
                "💻 Комп'ютерна грамотність — основи роботи з ПК\n\n"
                "Можеш сказати, що більше подобається — і я підкажу найкращий варіант 👍"
            )
        }

    # 💰 ЦІНА
    if "скільки" in msg_lower or "ціна" in msg_lower or "вартість" in msg_lower:
        return {
            "response": (
                "💰 Вартість навчання:\n"
                "• Групові заняття — 250 грн\n"
                "• Індивідуальні — 450 грн\n\n"
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
            "response": "Трохи не зрозумів 🙂 Напишіть, що саме цікавить: курс, ціна чи запис 👇"
        }

    # 🤷 НЕ ЗНАЄ
    if "не знаю" in msg_lower:
        return {
            "response": (
                "Нічого страшного 🙂\n\n"
                "Якщо коротко:\n"
                "🎮 ігри → Roblox\n"
                "💻 програмування → Python\n"
                "🤖 щось сучасне → AI\n\n"
                "Що ближче?"
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
    if any(x in msg_lower for x in ["19", "18", "20", ":"]):
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

class GoogleDocCreateRequest(BaseModel):
    title: str = "ItEnAi CRM Документ"
    text: str = ""


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
    hub_mode: str = None,
    hub_challenge: str = None,
    hub_verify_token: str = None
):
    if hub_mode == "subscribe" and hub_verify_token == META_VERIFY_TOKEN:
        return Response(content=hub_challenge or "", media_type="text/plain")

    raise HTTPException(status_code=403, detail="Meta webhook verification failed")


@app.post("/api/meta/webhook")
async def meta_webhook_receive(payload: dict):
    print("META WEBHOOK PAYLOAD:", payload)

    return {
        "success": True
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