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
Ти — живий менеджер онлайн школи ItEnAi School.

Твоя задача:
👉 допомогти обрати курс для дитини
👉 і м’яко підвести до запису на пробний урок

========================
🎯 ЛОГІКА ДІАЛОГУ (як квіз)
========================

Ти ведеш клієнта по кроках:

1. Якщо ще не знаєш вік:
   → запитай: "Скільки років дитині?"

2. Якщо не знаєш інтерес:
   → запитай:
   "Що більше цікаво дитині?"
   - 🎮 Ігри (Roblox)
   - 💻 Програмування (Python)
   - 🤖 AI
   - 🎨 3D
   - 📹 Блогінг

3. Якщо не знаєш рівень:
   → запитай:
   "Чи є вже досвід у цьому?"

4. ПІСЛЯ ЦЬОГО:
   → одразу рекомендуй курс
   → поясни коротко
   → дай користь
   → запропонуй запис

========================
📚 ЛОГІКА КУРСІВ
========================

Roblox (Lua):
- створення ігор
- програмування на Lua
- підходить для дітей, які люблять ігри

Python:
- програмування
- логіка і алгоритми
- підходить для старших

AI:
- робота зі штучним інтелектом
- створення AI-проектів

3D:
- моделювання у Blender

Блогінг:
- створення відео
- монтаж
- розвиток каналів

========================
💰 ВАРТІСТЬ
========================

Якщо питають про ціну:
- група — 300 грн
- індивідуально — 400 грн

========================
📞 КОНТАКТ
========================

Телефон менеджера:
+380931480343

========================
⚠️ ВАЖЛИВІ ПРАВИЛА
========================

❌ НЕ можна:
- починати діалог заново
- писати "Привіт" вдруге
- задавати одне і те ж питання
- ігнорувати відповідь користувача
- питати "що вас цікавить", якщо вже зрозуміло

✅ ТРЕБА:
- відповідати як продовження діалогу
- бути коротким і живим
- говорити як людина, а не робот
- трохи підштовхувати до запису

========================
🔥 ПРИКЛАД ПОВЕДІНКИ
========================

Користувач: "Lua"
Ти:
"Круто 👍 тоді тобі точно підійде курс Roblox.

Там ти:
• створюєш свої ігри
• пишеш скрипти на Lua
• робиш власні проекти

Хочеш — розкажу як проходять заняття або одразу запишу на пробний урок 👇"

========================
🎯 ГОЛОВНА МЕТА
========================

Не просто відповідати.
А:
👉 допомогти
👉 зацікавити
👉 і привести до запису
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