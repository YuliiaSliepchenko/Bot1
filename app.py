from fastapi import FastAPI
from pydantic import BaseModel
import os
import httpx

app = FastAPI()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL = "openai/gpt-4o-mini"

SYSTEM_PROMPT = """
Ти — ввічливий AI-менеджер онлайн-школи ItEnAi School.
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
    return {"ok": True}

@app.post("/chat")
async def chat(req: ChatRequest):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost",
        "X-OpenRouter-Title": "easy_bot"
    }

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": req.message}
        ],
        "temperature": 0.4
    }

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload
        )

    print("STATUS:", r.status_code)
    print("TEXT:", r.text)

    if r.status_code != 200:
        return {"response": f"Помилка OpenRouter: {r.status_code}\n{r.text[:500]}"}

    data = r.json()

    if "choices" not in data:
        return {"response": f"Некоректна відповідь AI: {data}"}

    text = data["choices"][0]["message"]["content"]
    return {"response": text}