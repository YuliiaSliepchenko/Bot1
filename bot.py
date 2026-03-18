import asyncio
import httpx
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

TOKEN = "8314866079:AAEK299qO8elmLQ5WklZj-kYSLt-W9WlD5k"
OPENROUTER_KEY = "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"

MODEL = "openai/gpt-4o-mini"

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

Відповідай коротко і зрозуміло.
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
        "Content-Type": "application/json"
    }

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question}
        ]
    }

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload
        )

    data = r.json()
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
        await message.answer(f"Помилка AI: {e}")

async def main():

    me = await bot.get_me()
    print(f"Bot started @{me.username}")

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())