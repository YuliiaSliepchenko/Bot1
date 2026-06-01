from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import httpx
from fastapi.responses import RedirectResponse
from urllib.parse import urlencode
from dotenv import load_dotenv
from db import init_db, save_lead, save_google_tokens, get_google_tokens

load_dotenv()

app = FastAPI()

init_db()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL = "openai/gpt-4o-mini"
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")

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
        "scope": "https://www.googleapis.com/auth/gmail.readonly https://www.googleapis.com/auth/userinfo.email",
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

    return {
        "success": True,
        "message": "Google акаунт підключено",
        "email": email
    }