from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import httpx
from dotenv import load_dotenv
from db import init_db, save_lead

load_dotenv()

app = FastAPI()

init_db()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL = "openai/gpt-4o-mini"

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


    import random

    confirm = ["Супер 👍", "Чудово 🙌", "Домовились 🔥", "Окей 👌"]

    details_intro = [
        "Коротко поясню 👇",
        "Ось як проходить курс 👇",
        "Що буде на заняттях 👇"
    ]

    cta = [
        "Хочеш записатися на пробний урок? 👇",
        "Записуємо? 👇",
        "Оформляємо? 👇"
    ]

    evening = [
        "Можемо підібрати вечірній час 👍",
        "Є зручні вечірні заняття",
        "Підлаштуємось під ваш графік 👌"
    ]

    # 🎮 ROBLOX
    if any(x in msg_lower for x in ["roblox", "роблокс", "lua"]):
        return {
            "response": (
                f"{random.choice(confirm)}\n\n"
                "🎮 Курс Roblox\n\n"
                f"{random.choice(details_intro)}\n"
                "• створення ігор\n"
                "• програмування на Lua\n"
                "• власні проекти\n\n"
                "💰 250 грн (група)\n"
                "💰 450 грн (індивідуально)\n\n"
                f"{random.choice(evening)}\n\n"
                f"{random.choice(cta)}"
            )
        }

    # 💻 PYTHON
    if any(x in msg_lower for x in ["python", "пітон"]):
        return {
            "response": (
                f"{random.choice(confirm)}\n\n"
                "💻 Курс Python\n\n"
                f"{random.choice(details_intro)}\n"
                "• програмування\n"
                "• логіка\n"
                "• створення проєктів\n\n"
                "💰 250 грн (група)\n"
                "💰 450 грн (індивідуально)\n\n"
                f"{random.choice(evening)}\n\n"
                f"{random.choice(cta)}"
            )
        }

    # 🤖 AI
    if any(x in msg_lower for x in ["ai", "штучний"]):
        return {
            "response": (
                f"{random.choice(confirm)}\n\n"
                "🤖 Курс AI\n\n"
                f"{random.choice(details_intro)}\n"
                "• робота з нейромережами\n"
                "• створення AI-проєктів\n"
                "• генерація текстів і зображень\n\n"
                "💰 250 грн (група)\n"
                "💰 450 грн (індивідуально)\n\n"
                f"{random.choice(evening)}\n\n"
                f"{random.choice(cta)}"
            )
        }

    # 🎨 3D
    if any(x in msg_lower for x in ["3d", "блендер"]):
        return {
            "response": (
                f"{random.choice(confirm)}\n\n"
                "🎨 Курс 3D моделювання\n\n"
                f"{random.choice(details_intro)}\n"
                "• робота в Blender\n"
                "• створення моделей\n"
                "• власні проєкти\n\n"
                "💰 250 грн (група)\n"
                "💰 450 грн (індивідуально)\n\n"
                f"{random.choice(evening)}\n\n"
                f"{random.choice(cta)}"
            )
        }

    # 📹 БЛОГІНГ
    if any(x in msg_lower for x in ["блог", "відео", "ютуб"]):
        return {
            "response": (
                f"{random.choice(confirm)}\n\n"
                "📹 Курс блогінгу\n\n"
                f"{random.choice(details_intro)}\n"
                "• зйомка відео\n"
                "• монтаж\n"
                "• розвиток каналу\n\n"
                "💰 250 грн (група)\n"
                "💰 450 грн (індивідуально)\n\n"
                f"{random.choice(evening)}\n\n"
                f"{random.choice(cta)}"
            )
        }

    # 💻 КОМП'ЮТЕРНА ГРАМОТНІСТЬ
    if any(x in msg_lower for x in ["комп", "пк", "комп'ютер", "грамот", "кг"]):
        return {
            "response": (
                f"{random.choice(confirm)}\n\n"
                "💻 Курс комп'ютерної грамотності\n\n"
                f"{random.choice(details_intro)}\n"
                "• базова робота з комп’ютером\n"
                "• інтернет і безпека\n"
                "• робота з файлами\n"
                "• основи програм\n\n"
                "💰 250 грн (група)\n"
                "💰 450 грн (індивідуально)\n\n"
                f"{random.choice(evening)}\n\n"
                f"{random.choice(cta)}"
            )
        }

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
                f"{random.choice(confirm)}\n\n"
                "Фіксую заявку 👍\n\n"
                "Підберемо зручний час 👇"
            )
        }

    if msg_lower in ["так", "да", "ага", "ок", "окей"]:
        return {
            "response": (
                f"{random.choice(confirm)}\n\n"
                "Давайте запишемо дитину на пробний урок 👇\n\n"
                "Напишіть:\n"
                "• ім’я\n"
                "• вік\n\n"
                "і підберемо зручний час (можна навіть ввечері) 👍"
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
    if "час" in msg_lower or "коли" in msg_lower:
        return {
            "response": (
                "Маємо зручні варіанти 👇\n\n"
                "🕓 вдень: 15:00–18:00\n"
                "🌙 ввечері: 18:00–20:00\n\n"
                "Можемо записати вже на завтра 👍\n\n"
                "Який варіант вам підходить?"
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