import asyncio
import os
import json
import re
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from db import (
    init_db, 
    get_or_create_session, 
    get_session, 
    update_session,
    save_chat_message_new,
    save_application
)

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise ValueError("Не знайдено BOT_TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Завантаження бази знань
with open("knowledge_base.json", "r", encoding="utf-8") as f:
    KB = json.load(f)

COURSES = {course["id"]: course for course in KB["courses"]}
AGE_GROUPS = KB["age_groups"]
MSG = KB["messages"]
MANAGER_PHONE = KB["school"]["manager_phone"]


def get_manager_button():
    """Кнопка для контакту з менеджером"""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📞 Контакт менеджера")]],
        resize_keyboard=True
    )


def get_courses_keyboard(course_ids):
    """Генерує клавіатуру з доступними курсами"""
    buttons = []
    for course_id in course_ids:
        if course_id in COURSES:
            course = COURSES[course_id]
            buttons.append([KeyboardButton(text=course["name"])])
    
    buttons.append([KeyboardButton(text="📞 Контакт менеджера")])
    
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def get_confirmation_keyboard():
    """Клавіатура для підтвердження"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Так, записати"), KeyboardButton(text="❌ Змінити дані")],
            [KeyboardButton(text="📞 Контакт менеджера")]
        ],
        resize_keyboard=True
    )


def get_recommended_courses(age: int) -> list:
    """Отримати рекомендовані курси за віком"""
    if age < 6:
        return []
    elif age <= 8:
        return AGE_GROUPS["6_8"]
    elif age <= 10:
        return AGE_GROUPS["8_10"]
    elif age <= 12:
        return AGE_GROUPS["10_12"]
    elif age <= 16:
        return AGE_GROUPS["12_16"]
    else:
        return AGE_GROUPS["16_18"]


async def show_manager_contact(message: types.Message):
    """Показати контакт менеджера"""
    await message.answer(
        f"📞 Контакт менеджера школи:\n{MANAGER_PHONE}\n\n"
        f"Натисніть номер, щоб зателефонувати, або залиште свій номер — менеджер зв'яжеться з Вами.",
        reply_markup=get_manager_button()
    )
    user_id = f"telegram:{message.chat.id}"
    save_chat_message_new(user_id, "запит контакту менеджера", MSG["manager_contact"])


@dp.message(CommandStart())
async def start(message: types.Message):
    """Початок розмови"""
    user_id = f"telegram:{message.chat.id}"
    get_or_create_session(user_id, "telegram")
    update_session(user_id, "telegram", current_stage="age_ask")
    
    await message.answer(
        MSG["greeting"],
        reply_markup=get_manager_button()
    )
    save_chat_message_new(user_id, "/start", MSG["greeting"])
    
    await message.answer(
        MSG["ask_age"],
        reply_markup=get_manager_button()
    )


@dp.message(F.text == "📞 Контакт менеджера")
async def handle_manager_contact(message: types.Message):
    """Обробити запит контакту менеджера"""
    await show_manager_contact(message)


@dp.message(Command("reset"))
async def reset_session(message: types.Message):
    """Скинути сесію"""
    user_id = f"telegram:{message.chat.id}"
    update_session(user_id, "telegram", current_stage="greeting")
    await start(message)


@dp.message()
async def handle_message(message: types.Message):
    """Головний обробник повідомлень"""
    user_id = f"telegram:{message.chat.id}"
    text = message.text.strip()
    
    # Отримати сесію
    session = get_session(user_id, "telegram")
    if not session:
        await start(message)
        return
    
    stage = session["current_stage"]
    
    # Якщо тискнув "Змінити дані", повернутися до початку
    if text == "❌ Змінити дані":
        update_session(user_id, "telegram", current_stage="age_ask")
        await message.answer(
            MSG["ask_age"],
            reply_markup=get_manager_button()
        )
        return
    
    # ===== ЕТАП: Запит віку =====
    if stage == "age_ask":
        try:
            age = int(text)
            if 5 <= age <= 99:
                update_session(user_id, "telegram", current_stage="interests_ask", child_age=age)
                save_chat_message_new(user_id, text, MSG["ask_interests"])
                await message.answer(
                    MSG["ask_interests"],
                    reply_markup=get_manager_button()
                )
            else:
                await message.answer(
                    "❌ Будь ласка, введіть вік від 5 до 99 років.",
                    reply_markup=get_manager_button()
                )
        except ValueError:
            await message.answer(
                "❌ Введіть цифру, будь ласка.",
                reply_markup=get_manager_button()
            )
    
    # ===== ЕТАП: Запит інтересів =====
    elif stage == "interests_ask":
        interests = text.lower()
        age = session["child_age"]
        recommended = get_recommended_courses(age)
        
        if recommended:
            update_session(
                user_id, "telegram",
                current_stage="course_select",
                interests=interests
            )
            save_chat_message_new(user_id, text, MSG["ask_course"])
            
            # Формуємо повідомлення з курсами
            course_text = "📚 Рекомендовані курси для дитини:\n\n"
            for course_id in recommended:
                course = COURSES[course_id]
                course_text += f"{course['name']}\n{course['description']}\n\n"
            
            await message.answer(
                course_text,
                reply_markup=get_courses_keyboard(recommended)
            )
        else:
            await message.answer(
                "❌ На жаль, немає курсів для цього віку.",
                reply_markup=get_manager_button()
            )
    
    # ===== ЕТАП: Вибір курсу =====
    elif stage == "course_select":
        # Знаходимо курс за назвою
        selected_course = None
        for course_id, course in COURSES.items():
            if course["name"] in text:
                selected_course = course["name"]
                break
        
        if selected_course:
            update_session(
                user_id, "telegram",
                current_stage="name_ask",
                selected_course=selected_course
            )
            save_chat_message_new(user_id, text, MSG["ask_name"])
            await message.answer(
                MSG["ask_name"],
                reply_markup=get_manager_button()
            )
        else:
            await message.answer(
                "❌ Будь ласка, оберіть один з запропонованих курсів.",
                reply_markup=get_courses_keyboard([c for c in COURSES.keys()])
            )
    
    # ===== ЕТАП: Запит імені дитини =====
    elif stage == "name_ask":
        if len(text) >= 2:
            update_session(
                user_id, "telegram",
                current_stage="phone_ask",
                child_name=text
            )
            save_chat_message_new(user_id, text, MSG["ask_phone"])
            await message.answer(
                MSG["ask_phone"],
                reply_markup=get_manager_button()
            )
        else:
            await message.answer(
                "❌ Будь ласка, введіть повне ім'я дитини.",
                reply_markup=get_manager_button()
            )
    
    # ===== ЕТАП: Запит телефону =====
    elif stage == "phone_ask":
        phone = re.sub(r"[^0-9+]", "", text)
        if len(phone) >= 10:
            update_session(
                user_id, "telegram",
                current_stage="time_ask",
                parent_phone=phone
            )
            save_chat_message_new(user_id, text, MSG["ask_preferred_time"])
            await message.answer(
                MSG["ask_preferred_time"],
                reply_markup=get_manager_button()
            )
        else:
            await message.answer(
                "❌ Введіть коректний номер телефону.",
                reply_markup=get_manager_button()
            )
    
    # ===== ЕТАП: Запит часу =====
    elif stage == "time_ask":
        update_session(
            user_id, "telegram",
            current_stage="confirmation",
            preferred_time=text
        )
        
        # Отримати останню версію сесії
        session = get_session(user_id, "telegram")
        
        confirmation_text = MSG["ask_confirmation"].format(
            child_name=session["child_name"],
            child_age=session["child_age"],
            selected_course=session["selected_course"],
            parent_phone=session["parent_phone"],
            preferred_time=text
        )
        
        save_chat_message_new(user_id, text, confirmation_text)
        await message.answer(
            confirmation_text,
            reply_markup=get_confirmation_keyboard()
        )
    
    # ===== ЕТАП: Підтвердження =====
    elif stage == "confirmation":
        if text == "✅ Так, записати":
            session = get_session(user_id, "telegram")
            
            # Збереження заявки в базу
            app_id = save_application(
                user_id,
                session["child_name"],
                session["child_age"],
                session["selected_course"],
                session["preferred_date"],
                session["preferred_time"],
                session["parent_phone"]
            )
            
            update_session(
                user_id, "telegram",
                current_stage="completed",
                application_status="submitted"
            )
            
            save_chat_message_new(user_id, text, MSG["success"])
            await message.answer(
                MSG["success"],
                reply_markup=get_manager_button()
            )
            
            # Повідомити адміністратора
            print(f"✅ New application #{app_id} from {user_id}")
        else:
            update_session(user_id, "telegram", current_stage="age_ask")
            await message.answer(
                "Давайте почнемо заново!\n\n" + MSG["ask_age"],
                reply_markup=get_manager_button()
            )


async def main():
    init_db()
    await bot.delete_webhook(drop_pending_updates=True)
    me = await bot.get_me()
    print(f"✅ Bot started @{me.username}")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
