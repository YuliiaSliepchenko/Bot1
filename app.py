from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import httpx
from fastapi.responses import RedirectResponse
from urllib.parse import urlencode
from datetime import datetime, timezone
from dotenv import load_dotenv
from db import init_db, save_lead, save_google_tokens, get_google_tokens, delete_google_tokens

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
    "https://www.googleapis.com/auth/drive.file",
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