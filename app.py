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

    # 🤔 WHY BLOCKS (ЧОМУ)

    # 🎮 ROBLOX
    if "чому" in msg_lower and ("roblox" in msg_lower or "роблокс" in msg_lower):
        return {
            "response": (
                "Гарне питання 👍\n\n"
                "Roblox — це не просто гра 👇\n\n"
                "• дитина створює свої ігри\n"
                "• вчиться програмуванню\n"
                "• розвиває логіку і креативність\n\n"
                "Це найпростіший старт в IT 🔥\n\n"
                "Хочете спробувати пробне заняття? 👇"
            )
        }

    # 💻 PYTHON
    if "чому" in msg_lower and ("python" in msg_lower or "пітон" in msg_lower):
        return {
            "response": (
                "Python — це база програмування 👇\n\n"
                "• розвиток логіки\n"
                "• реальні навички\n"
                "• використання в IT і AI\n\n"
                "Дуже сильний напрям 🔥\n\n"
                "Хочете деталі? 👇"
            )
        }

    # 🤖 AI
    if "чому" in msg_lower and ("ai" in msg_lower or "штучний" in msg_lower):
        return {
            "response": (
                "AI — це майбутнє 👇\n\n"
                "• робота з нейромережами\n"
                "• створення AI-проєктів\n"
                "• сучасні навички\n\n"
                "Дуже перспективно 🔥\n\n"
                "Хочете спробувати? 👇"
            )
        }

    # 🎨 3D
    if "чому" in msg_lower and ("3d" in msg_lower or "блендер" in msg_lower):
        return {
            "response": (
                "3D — це творчість 👇\n\n"
                "• створення моделей\n"
                "• розвиток креативності\n"
                "• робота в Blender\n\n"
                "Дітям дуже заходить 🎨\n\n"
                "Хочете деталі? 👇"
            )
        }

    # 📹 БЛОГІНГ
    if "чому" in msg_lower and ("блог" in msg_lower or "відео"):
        return {
            "response": (
                "Блогінг — це сучасно 👇\n\n"
                "• відео і монтаж\n"
                "• розвиток впевненості\n"
                "• креативність\n\n"
                "Дуже актуально 📱\n\n"
                "Хочете більше деталей? 👇"
            )
        }

    # 💻 КОМП'ЮТЕРНА ГРАМОТНІСТЬ
    if "чому" in msg_lower and ("комп" in msg_lower or "грамот" in msg_lower or "кг"):
        return {
            "response": (
                "Це база 👇\n\n"
                "Комп’ютерна грамотність — фундамент\n\n"
                "• робота з ПК\n"
                "• інтернет і безпека\n"
                "• файли і програми\n\n"
                "Без цього складно далі 👍\n\n"
                "Хочете записатися? 👇"
            )
        }

    # 🔥 WHAT'S COOL (ЩО ЦІКАВОГО)

    # 🎨 3D / BLENDER
    if any(x in msg_lower for x in ["цікаво", "цікавого", "особливого"]) and ("3d" in msg_lower or "блендер" in msg_lower):
        return {
            "response": (
                "Ось що реально заходить дітям у 3D 👇\n\n"
                "• можна створювати свої персонажі і світи\n"
                "• як у іграх або мультиках 🎮\n"
                "• швидкий результат (вже на перших заняттях)\n"
                "• можна показувати друзям свої роботи 🔥\n\n"
                "Це дуже затягує і розвиває креативність\n\n"
                "Хочете спробувати пробне заняття? 👇"
            )
        }

    # 🎮 ROBLOX
    if any(x in msg_lower for x in ["цікаво", "цікавого", "особливого"]) and ("roblox" in msg_lower or "роблокс" in msg_lower):
        return {
            "response": (
                "Ось що дітям найбільше подобається в Roblox 👇\n\n"
                "• створюють свої ігри\n"
                "• додають персонажів і механіки\n"
                "• можуть дати друзям пограти 🎮\n"
                "• відчуття 'я зробив свою гру' 🔥\n\n"
                "Це дуже мотивує дітей\n\n"
                "Хочете спробувати? 👇"
            )
        }

    # 💻 PYTHON
    if any(x in msg_lower for x in ["цікаво", "цікавого"]) and ("python" in msg_lower or "пітон" in msg_lower):
        return {
            "response": (
                "Що цікавого в Python 👇\n\n"
                "• створення своїх програм\n"
                "• логічні задачі (як головоломки)\n"
                "• перші проекти вже на курсі\n"
                "• відчуття 'я програміст' 😎\n\n"
                "Це вже більш серйозний рівень\n\n"
                "Хочете деталі? 👇"
            )
        }

    # 🤖 AI
    if any(x in msg_lower for x in ["цікаво", "цікавого"]) and ("ai" in msg_lower or "штучний" in msg_lower):
        return {
            "response": (
                "Що реально круто в AI 👇\n\n"
                "• створення картинок і текстів\n"
                "• робота з нейромережами\n"
                "• ефект 'вау, це працює!' 🤯\n"
                "• сучасні технології\n\n"
                "Дітям дуже цікаво\n\n"
                "Хочете спробувати? 👇"
            )
        }

    # 📹 БЛОГІНГ
    if any(x in msg_lower for x in ["цікаво", "цікавого"]) and ("блог" in msg_lower or "відео"):
        return {
            "response": (
                "Що цікаво в блогінгу 👇\n\n"
                "• зйомка відео 🎥\n"
                "• монтаж і ефекти\n"
                "• створення свого контенту\n"
                "• розвиток впевненості\n\n"
                "Дітям це дуже подобається\n\n"
                "Хочете дізнатись більше? 👇"
            )
        }

    # 💻 КОМП'ЮТЕРНА ГРАМОТНІСТЬ
    if any(x in msg_lower for x in ["цікаво", "цікавого"]) and ("комп" in msg_lower or "грамот" in msg_lower or "кг"):
        return {
            "response": (
                "Що цікавого в цьому курсі 👇\n\n"
                "• дитина починає впевнено користуватись ПК\n"
                "• розуміє інтернет і безпеку\n"
                "• робить це швидко і без страху\n\n"
                "Це дає сильну базу для майбутнього 👍\n\n"
                "Хочете спробувати? 👇"
            )
        }

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
                "🕓 вдень: 11:00–17:00\n"
                "🌙 ввечері: 17:00–21:00\n\n"
                "Можемо записати вже на завтра 👍\n\n"
                "Який варіант вам підходить?"
            )
        }

    # 📅 ФІНАЛЬНЕ ЗАКРИТТЯ ЗАЯВКИ
    if any(x in msg_lower for x in ["завтра", "сьогодні", "на завтра"]):
        return {
            "response": (
                "Супер 👍\n\n"
                "Записали на пробний урок 👇\n\n"
                "📅 Завтра\n"
                "🕓 Час узгодимо додатково\n\n"
                "Менеджер зв’яжеться з вами для підтвердження 👍"
            )
        }

    # 🕓 КОНКРЕТНИЙ ЧАС
    if any(x in msg_lower for x in ["19", "18", "20", ":"]):
        return {
            "response": (
                "Чудово 🙌\n\n"
                "Записали на цей час 👍\n\n"
                "Менеджер підтвердить запис найближчим часом"
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