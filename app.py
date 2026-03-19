from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import httpx
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

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
Ти ввічливий AI-менеджер онлайн-школи ItEnAi School.
Відповідай українською мовою.
Відповідай коротко, чітко, дружньо і по суті.

Інформація про школу:
- Це онлайн-школа для дітей і підлітків.
- Є курси: Roblox, Python, AI, 3D-моделювання, блогінг.
- Формат навчання: індивідуальні онлайн-заняття.
- Стандартний курс: 24 уроки + фінальний проєкт.
- Після завершення курсу учень отримує сертифікат.
- Якщо користувач питає про точну ціну, скажи: "Щоб дізнатися актуальну вартість, напишіть менеджеру."
- Якщо не вистачає даних, не вигадуй, а чесно скажи, що треба уточнити.
"""

class ChatRequest(BaseModel):
    message: str

@app.get("/")
def root():
    return {"ok": True, "message": "ItEnAi chat API is running"}

@app.post("/chat")
async def chat(req: ChatRequest):
    if not OPENROUTER_API_KEY:
        return {"response": "Помилка сервера: не налаштовано OPENROUTER_API_KEY"}

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://itenaischool.com",
        "X-OpenRouter-Title": "itenai_site_chat"
    }

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": req.message}
        ],
        "temperature": 0.4
    }

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload
            )

        if r.status_code != 200:
            return {"response": f"Помилка OpenRouter: {r.status_code}"}

        data = r.json()

        if "choices" not in data:
            return {"response": "Сталася помилка AI. Спробуйте ще раз трохи пізніше."}

        text = data["choices"][0]["message"]["content"]
        return {"response": text}

    except Exception:
        return {"response": "Сервер тимчасово недоступний. Спробуйте ще раз пізніше."}