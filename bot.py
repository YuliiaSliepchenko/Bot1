import asyncio
import os
import httpx
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise ValueError("Не знайдено BOT_TOKEN")


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

async def ask_api(question):
    async with httpx.AsyncClient() as client:
        r = await client.post(
            "https://sitechat-production.up.railway.app/chat",
            json={"message": question}
        )
    return r.json()["response"]

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
        answer = await ask_api(question)
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