import json
import re
from pathlib import Path
from uuid import uuid4

from db import create_trial_lead, get_conversation_state, update_conversation_state


KNOWLEDGE = json.loads((Path(__file__).with_name("courses.json")).read_text(encoding="utf-8"))
COURSES = KNOWLEDGE["courses"]
PHONE = KNOWLEDGE["school"]["manager_phone_display"]

INTEREST_BUTTONS = [
    ("games", "🎮 Ігри"), ("ai", "🤖 Штучний інтелект"),
    ("programming", "💻 Програмування"), ("design", "🎨 Дизайн / 3D"),
    ("blogging", "🎥 YouTube / TikTok"), ("computer", "🖥 Комп'ютери"),
    ("unsure", "🤷 Ще не визначились")
]


def buttons(*items):
    return {"type": "buttons", "items": [{"id": item[0], "label": item[1]} for item in items]}


def answer(text, state, *items, **extra):
    result = {
        "response": text,
        "message": text,
        "state": state,
        "buttons": [{"id": item[0], "text": item[1]} for item in items],
        "actions": buttons(*items)
    }
    result.update(extra)
    return result


def normalize_phone(text):
    match = re.search(r"(?:\+?38)?[\s().-]*0?\d(?:[\s().-]*\d){8}", text)
    if not match:
        return None
    digits = re.sub(r"\D", "", match.group())
    if len(digits) == 10 and digits.startswith("0"):
        digits = "38" + digits
    elif len(digits) == 12 and digits.startswith("380"):
        pass
    else:
        return None
    return "+" + digits


def extract_age(text):
    match = re.search(r"(?<!\d)([6-9]|1[0-8])(?!\d)", text)
    return int(match.group(1)) if match else None


def detect_course(text):
    value = text.lower()
    aliases = {
        "roblox": ["roblox", "роблокс", "lua", "ігри", "games"],
        "python": ["python", "пітон", "код", "математ", "логік", "programming"],
        "ai": ["штучн", "chatgpt", "ai", "нейромереж", "картин", "copilot"],
        "blender": ["blender", "3d", "3д", "модел", "дизайн", "design"],
        "blogging": ["youtube", "tiktok", "ютуб", "тікток", "блог", "відео", "blogging"],
        "computer": ["комп'ют", "комп’ют", "windows", "грамот", "computer"]
    }
    for course_id, words in aliases.items():
        if any(word in value for word in words):
            return course_id
    return None


def course_summary(course_id, include_price=False):
    course = COURSES[course_id]
    text = f"{course['name']} — {', '.join(course['topics'][:5])}.\n\nРезультат: {course['result']}."
    if include_price:
        prices = []
        if course.get("group_price"):
            prices.append(f"групові — {course['group_price']} грн/заняття")
        if course.get("individual_price"):
            prices.append(f"індивідуальні — {course['individual_price']} грн/заняття")
        text += "\n\nВартість: " + "; ".join(prices) + "."
    return text


def confirmation_text(state):
    return (
        "Перевірте заявку 👇\n\n"
        f"👦 Дитина: {state['child_name']}\n"
        f"🎂 Вік: {state['child_age']} років\n"
        f"🎓 Напрям: {COURSES[state['selected_course']]['name']}\n"
        f"📅 Бажаний день: {state['preferred_date']}\n"
        f"🕐 Бажаний час: {state['preferred_time']}\n"
        f"📞 Телефон: {state['parent_phone']}\n\nВсе правильно?"
    )


def manager_response(state_name="MANAGER_REQUEST"):
    return answer(
        f"Менеджер ItEnAi School\n\n📞 {PHONE}\n\nНатисніть на номер, щоб зателефонувати, або залиште свій телефон — менеджер зв'яжеться з Вами.",
        state_name,
        ("tel:+380931480343", "📞 Зателефонувати"),
        ("leave_phone", "☎️ Залишити мій номер"),
        ("back", "↩️ Повернутися до чату")
    )


def handle_chat(session_id, message, source="website_chat"):
    text = message.strip()
    lower = text.lower()
    state = get_conversation_state(session_id)
    current = state["state"]
    phone = normalize_phone(text)

    manager_words = ["менеджер", "оператор", "людин", "адміністратор", "дайте номер", "зв'язатися", "зв’язатися", "консультац"]
    if any(word in lower for word in manager_words) or lower == "manager":
        if phone:
            state = update_conversation_state(session_id, parent_phone=phone, pending_callback=1, state="CONFIRMING_CALLBACK")
            return answer(f"Передати номер {phone} менеджеру ItEnAi School?", state["state"], ("confirm_callback", "✅ Так, передати"), ("manager", "❌ Ні"))
        update_conversation_state(session_id, state="MANAGER_REQUEST")
        return manager_response()

    if current == "MANAGER_REQUEST":
        if lower in {"leave_phone", "залишити мій номер"}:
            update_conversation_state(session_id, state="ASKING_CALLBACK_PHONE", pending_callback=1)
            return answer("Напишіть, будь ласка, номер телефону — менеджер зв'яжеться з Вами.", "ASKING_CALLBACK_PHONE")
        if lower == "back":
            update_conversation_state(session_id, state="IDLE")
            return answer("Повертаємося до консультації 😊 Скільки років дитині?", "ASKING_AGE", ("manager", "📞 Зв'язатися з менеджером"))

    if current == "ASKING_CALLBACK_PHONE":
        if not phone:
            return answer("Не вдалося розпізнати номер. Напишіть його, наприклад: 093 148 03 43.", current)
        update_conversation_state(session_id, parent_phone=phone, state="CONFIRMING_CALLBACK")
        return answer(f"Передати номер {phone} менеджеру ItEnAi School?", "CONFIRMING_CALLBACK", ("confirm_callback", "✅ Так, передати"), ("manager", "❌ Ні"))

    if current == "CONFIRMING_CALLBACK" and lower in {"confirm_callback", "так", "підтвердити", "да"}:
        token = state.get("confirmation_token") or str(uuid4())
        state = update_conversation_state(session_id, confirmation_token=token)
        lead_code, _ = create_trial_lead(session_id, token, state, source, manager_callback=1)
        update_conversation_state(session_id, state="APPLICATION_CREATED", pending_callback=0)
        return answer(f"✅ Запит передано менеджеру. Номер звернення: {lead_code}. Ми зв'яжемося з Вами найближчим часом.", "APPLICATION_CREATED", ("manager", "📞 Зв'язатися з менеджером"), lead_id=lead_code)

    if lower in {"trial", "записатися", "так, записатися", "хочу записатися"} or (current == "OFFERING_TRIAL" and lower in {"так", "да", "хочу"}):
        next_state = "ASKING_CHILD_NAME" if not state.get("child_name") else "ASKING_CHILD_AGE" if not state.get("child_age") else "ASKING_COURSE" if not state.get("selected_course") else "ASKING_DATE"
        update_conversation_state(session_id, state=next_state)
        prompts = {"ASKING_CHILD_NAME": "Супер 🚀 Як звати дитину?", "ASKING_CHILD_AGE": "Скільки років дитині?", "ASKING_COURSE": "Який напрям обираємо?", "ASKING_DATE": "Який день Вам буде зручний?"}
        return answer(prompts[next_state], next_state, ("manager", "📞 Зв'язатися з менеджером"))

    if current == "ASKING_CHILD_NAME":
        name = re.sub(r"[^A-Za-zА-Яа-яІіЇїЄєҐґ'’ -]", "", text).strip().title()
        if len(name) < 2:
            return answer("Напишіть, будь ласка, ім'я дитини.", current)
        state = update_conversation_state(session_id, child_name=name, state="ASKING_CHILD_AGE" if not state.get("child_age") else "ASKING_DATE")
        question = "Скільки років дитині?" if state["state"] == "ASKING_CHILD_AGE" else "Який день Вам буде зручний?"
        return answer(question, state["state"], ("manager", "📞 Зв'язатися з менеджером"))

    if current in {"IDLE", "ASKING_AGE"}:
        age = extract_age(text)
        course_id = detect_course(text)
        if age:
            state = update_conversation_state(session_id, child_age=age, selected_course=course_id or state.get("selected_course"), state="ASKING_INTERESTS")
            return answer("Чудово 😊 А що дитині найбільше подобається?", "ASKING_INTERESTS", *INTEREST_BUTTONS, ("manager", "📞 Зв'язатися з менеджером"))
        if course_id:
            state = update_conversation_state(session_id, selected_course=course_id, state="COURSE_INFO")
            price = any(word in lower for word in ["ціна", "вартість", "скільки"])
            return answer(course_summary(course_id, price) + "\n\nСкільки років дитині?", "ASKING_AGE", ("manager", "📞 Зв'язатися з менеджером"))
        update_conversation_state(session_id, state="ASKING_AGE")
        return answer("Вітаю 👋 Допоможу підібрати IT-напрям або записати дитину на пробне заняття. Скільки років дитині?", "ASKING_AGE", ("manager", "📞 Зв'язатися з менеджером"))

    if current == "ASKING_CHILD_AGE":
        age = extract_age(text)
        if not age:
            return answer("Вкажіть, будь ласка, вік дитини від 6 до 18 років.", current)
        state = update_conversation_state(session_id, child_age=age, state="ASKING_DATE" if state.get("selected_course") else "ASKING_COURSE")
        return answer("Який день Вам буде зручний?" if state["state"] == "ASKING_DATE" else "Який напрям обираємо?", state["state"])

    if current in {"ASKING_INTERESTS", "ASKING_COURSE"}:
        course_id = detect_course(text)
        if not course_id:
            return answer("Підкажіть, що ближче дитині: ігри, AI, програмування, 3D, блогінг чи основи роботи з комп'ютером?", current, *INTEREST_BUTTONS)
        state = update_conversation_state(session_id, interests=text, selected_course=course_id, state="OFFERING_TRIAL")
        return answer(f"Я рекомендую {course_summary(course_id)}\n\nХочете підібрати день і час для пробного заняття?", "OFFERING_TRIAL", ("trial", "✅ Так, записатися"), ("ask", "💬 Спочатку хочу запитати"), ("manager", "📞 Зв'язатися з менеджером"))

    if current == "ASKING_DATE":
        state = update_conversation_state(session_id, preferred_date=text, state="ASKING_TIME")
        return answer("А приблизно який час Вам буде зручний?", "ASKING_TIME", ("manager", "📞 Зв'язатися з менеджером"))

    if current == "ASKING_TIME":
        state = update_conversation_state(session_id, preferred_time=text, state="ASKING_PHONE")
        return answer("Залиште, будь ласка, номер телефону одного з батьків. Менеджер перевірить вільний час і підтвердить заняття.", "ASKING_PHONE", ("manager", "📞 Зв'язатися з менеджером"))

    if current == "ASKING_PHONE":
        if not phone:
            return answer("Не вдалося розпізнати номер. Напишіть його, наприклад: +380 93 148 03 43.", current)
        token = str(uuid4())
        state = update_conversation_state(session_id, parent_phone=phone, confirmation_token=token, state="CONFIRMING_APPLICATION")
        return answer(confirmation_text(state), "CONFIRMING_APPLICATION", ("confirm", "✅ Підтвердити запис"), ("edit", "✏️ Змінити дані"), ("cancel", "❌ Скасувати"))

    if current == "CONFIRMING_APPLICATION":
        if lower in {"confirm", "підтвердити", "так", "все правильно", "да"}:
            lead_code, _ = create_trial_lead(session_id, state["confirmation_token"], state, source)
            update_conversation_state(session_id, state="APPLICATION_CREATED")
            return answer(f"✅ Готово! Заявку {lead_code} отримано. Менеджер ItEnAi School перевірить можливий час і зв'яжеться з Вами для підтвердження заняття 🚀", "APPLICATION_CREATED", ("manager", "📞 Зв'язатися з менеджером"), lead_id=lead_code)
        if lower in {"cancel", "скасувати", "ні"}:
            update_conversation_state(session_id, state="IDLE", confirmation_token=None)
            return answer("Заявку скасовано. Якщо захочете повернутися — я допоможу 😊", "IDLE", ("manager", "📞 Зв'язатися з менеджером"))
        if lower in {"edit", "змінити", "редагувати"}:
            update_conversation_state(session_id, state="ASKING_CHILD_NAME")
            return answer("Добре, почнемо уточнення. Як звати дитину?", "ASKING_CHILD_NAME")
        return answer(confirmation_text(state), current, ("confirm", "✅ Підтвердити запис"), ("edit", "✏️ Змінити дані"), ("cancel", "❌ Скасувати"))

    course_id = detect_course(text)
    if course_id:
        return answer(course_summary(course_id, any(word in lower for word in ["ціна", "вартість"])), current, ("trial", "✅ Записатися на пробне"), ("manager", "📞 Зв'язатися з менеджером"))
    return answer("Можу розповісти про курс або допомогти із записом на пробне заняття. Що Вас цікавить?", current, ("trial", "✅ Записатися на пробне"), ("manager", "📞 Зв'язатися з менеджером"))
