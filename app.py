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

    # 📚 СПИСОК КУРСІВ
    if "курси" in msg_lower or "список" in msg_lower or "що є" in msg_lower:
        return {
            "response": (
                "Ось наші курси 👇\n\n"
                "🎮 Roblox — створення ігор + програмування на Lua\n"
                "💻 Python — програмування, логіка, створення проєктів\n"
                "🤖 AI — робота зі штучним інтелектом\n"
                "🎨 3D — моделювання в Blender\n"
                "📹 Блогінг — створення відео, монтаж, розвиток каналу\n\n"
                "Можеш сказати, що більше подобається — і я підкажу 👍"
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