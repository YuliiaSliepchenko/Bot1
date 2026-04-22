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

Твоя задача:
- допомогти обрати курс
- коротко пояснити
- відповісти на питання
- м’яко підвести до запису

ПРАВИЛА:
- не задавай одне і те ж питання кілька разів
- якщо користувач не хоче відповідати — не тисни
- не веди квіз
- відповідай просто і по суті
- будь як жива людина

СТИЛЬ:
- коротко
- дружньо
- без формальності
"""

class ChatRequest(BaseModel):
    message: str

@app.post("/chat")
async def chat(req: ChatRequest):

    msg = req.message
    msg_lower = msg.lower()

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

    if "курси" in msg_lower or "що є" in msg_lower or "чек" in msg_lower:
    return {
        "response": (
            "Ось наші основні напрямки 👇\n\n"
            "🎮 Roblox — створення ігор + Lua\n"
            "💻 Python — програмування і логіка\n"
            "🤖 AI — робота з штучним інтелектом\n"
            "🎨 3D — моделювання в Blender\n"
            "📹 Блогінг — створення відео\n\n"
            "Можеш просто сказати, що більше подобається — і я підкажу 👍"
        )
    }

    if "9" in msg_lower or msg_lower.isdigit():
    return {
        "response": (
            "Супер 👍\n\n"
            "Для такого віку добре заходить:\n"
            "🎮 Roblox (створення ігор)\n"
            "або 💻 Python (якщо хоче серйозніше програмування)\n\n"
            "Що ближче?"
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