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
- Використовуй тільки ці напрямки: Roblox, Python, AI, 3D, Блогінг
"""

# Словник станів по sessionId
session_state = {}

class ChatRequest(BaseModel):
    message: str
    sessionId: str

@app.post("/chat")
async def chat(req: ChatRequest):
    msg = req.message.strip()
    session_id = req.sessionId

    if not session_id:
        return {"response": "Помилка: не передано sessionId"}

    if session_id not in session_state:
        session_state[session_id] = {
            "courses_shown": False,
            "asked_time": False
        }

    state = session_state[session_id]
    msg_lower = msg.lower()

    # --- Повідомлення про час ---
    if any(x in msg_lower for x in ["час", "коли", "година"]) and not state["asked_time"]:
        state["asked_time"] = True
        return {
            "response": "Маємо варіанти 👇\n🕓 11:00–17:00\n🌙 17:00–21:00\nВиберіть зручний для вас час."
        }

    # --- Список курсів один раз ---
    if ("курси" in msg_lower or "список" in msg_lower) and not state["courses_shown"]:
        state["courses_shown"] = True
        return {
            "response": (
                "🎮 Roblox — створення ігор та Lua\n"
                "💻 Python — програмування та логіка\n"
                "🤖 AI — робота зі штучним інтелектом\n"
                "🎨 3D — моделювання в Blender\n"
                "📹 Блогінг — створення відео та монтаж\n\n"
                "Який напрям вас цікавить найбільше?"
            )
        }

    # --- Відповіді на конкретні курси ---
    if "що таке" in msg_lower or "що це" in msg_lower:
        if "python" in msg_lower:
            return {"response": "Python — це мова програмування, на якій діти створюють ігри, програми та AI 🤖"}
        if "roblox" in msg_lower:
            return {"response": "Roblox — це платформа для створення власних ігор 🎮"}
        if "ai" in msg_lower:
            return {"response": "AI — це штучний інтелект 🤖, діти створюють свої AI-проекти"}
        if "3d" in msg_lower:
            return {"response": "3D-моделювання — створення об'ємних моделей у Blender 🎨"}
        if "блог" in msg_lower:
            return {"response": "Блогінг — створення відео, монтаж і розвиток каналу 📹"}

    # --- Фіксація відповіді користувача для збереження ---
    save_lead("site", msg, session_id=session_id)

    # --- Виклик OpenRouter API ---
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
        async with httpx.AsyncClient(timeout=60) as client:
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