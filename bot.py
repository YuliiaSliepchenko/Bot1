import asyncio
import os
import httpx
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL = "openai/gpt-4o-mini"

if not TOKEN:
    raise ValueError("Не знайдено BOT_TOKEN")
if not OPENROUTER_KEY:
    raise ValueError("Не знайдено OPENROUTER_API_KEY")

bot = Bot(token=TOKEN)
dp = Dispatcher()

keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📚 Курси"), KeyboardButton(text="💰 Ціна")],
        [KeyboardButton(text="💻 Python"), KeyboardButton(text="🎮 Roblox")],
        [KeyboardButton(text="🤖 AI"), KeyboardButton(text="🎨 3D")],
        [KeyboardButton(text="📹 Блогінг"), KeyboardButton(text="❌ Вийти")]
    ],
    resize_keyboard=True
)

SYSTEM_PROMPT = """
Ти менеджер онлайн школи ItEnAi School.

Інформація:
- школа для дітей
- курси: Roblox, Python, AI, 3D, блогінг
- формат: онлайн
- курс: 24 уроки + фінальний проєкт
- після курсу видається сертифікат

Відповідай коротко і зрозуміло українською мовою.
"""

def normalize(text):
    mapping = {
        "📚 курси": "які курси є у школі",
        "💰 ціна": "яка вартість навчання",
        "💻 python": "розкажи про курс python",
        "🎮 roblox": "розкажи про курс roblox",
        "🤖 ai": "розкажи про курс штучного інтелекту",
        "🎨 3d": "розкажи про курс 3d моделювання",
        "📹 блогінг": "розкажи про курс блогінгу"
    }
    return mapping.get(text.lower(), text)

async def ask_ai(question):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost",
        "X-OpenRouter-Title": "itenai_bot"
    }

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question}
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

    if r.status_code != 200:
        return f"Помилка OpenRouter: {r.status_code}\n{r.text[:300]}"

    data = r.json()

    if "choices" not in data:
        return f"Некоректна відповідь AI: {data}"

    return data["choices"][0]["message"]["content"]

@dp.message(CommandStart())
async def start(message: types.Message):
    await message.answer(
        "👋 Вітаю в ItEnAi School\n\nОберіть кнопку або напишіть питання",
        reply_markup=keyboard
    )

@dp.message()
async def handle(message: types.Message):
    text = message.text.strip()

    if text == "❌ Вийти":
        await message.answer("Чат очищено. Напишіть /start", reply_markup=None)
        return

    question = normalize(text)

    try:
        answer = await ask_ai(question)
        await message.answer(answer, reply_markup=keyboard)
    except Exception as e:
        print("ERROR:", e)
        await message.answer(f"Помилка AI: {e}")

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    me = await bot.get_me()
    print(f"Bot started @{me.username}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())