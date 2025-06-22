import time
import telebot
from telebot import types 
from types import SimpleNamespace
from datetime import date, datetime, timedelta
import json
import os
import re
import random
import uuid  
from telebot.apihelper import ApiTelegramException
import logging
from telebot.types import InputMediaPhoto
from collections import OrderedDict
from random import choice
import math

TOKEN = "8170890381:AAEIX0qWiDnbCj_8794VZpIMEiS_feZQdAs"

ADMIN_ID = 827377121           # Для покупок, разбана и регистрации
BOT_VERSION = "7.0"            # Текущая версия бота

bot = telebot.TeleBot(TOKEN)

GIFT_EMOJIS = ["🎁", "🎉", "🏆", "🎊"]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Пути к файлам
DATA_FILE = os.path.join(BASE_DIR, "data.json")
# Единый файл со всеми бюрократическими данными (дела, штрафы и т.д.)
JOHN_FILE = os.path.join(BASE_DIR, "john.json")

# Global dictionary for user states
user_states = {}  # { user_id: { "state": ..., "temp_data": { ... } } }

# Файл с архивом сезонов
SEASONS_FILE = os.path.join(BASE_DIR, "seasons.json")

# Сезоны по умолчанию
DEFAULT_SEASONS = [
    {"number": 1, "name": "СБ1", "dates": "10.05.2020", "description": "", "pages": []},
    {"number": 2, "name": "СБКарантин(м)", "dates": "26.05.2020", "description": "", "pages": []},
    {"number": 3, "name": "СБ2", "dates": "02.02.2022", "description": "", "pages": []},
    {"number": 4, "name": "СБCreative", "dates": "19.08.2023", "description": "", "pages": []},
    {"number": 5, "name": "СБTravel", "dates": "13.06.2024", "description": "", "pages": []},
    {"number": 6, "name": "СБFIRE", "dates": "01.08.2024", "description": "", "pages": []},
    {"number": 7, "name": "BVMods(м)", "dates": "30.11.2024", "description": "", "pages": []},
    {"number": 8, "name": "BVNova", "dates": "29.12.2024", "description": "", "pages": []},
    {"number": 9, "name": "BVCastel(м)", "dates": "22.03.2025", "description": "", "pages": []},
    {"number": 10, "name": "BVSolar", "dates": "01.07.2025", "description": "", "pages": []},
]

# Пониженные цены на кейсы (скидка 15% с округлением до числа, заканчивающегося на 5, 9 или 0)
case_details = [
    {"name": "Деревянный сундук", "price": 69, "image": "wood.png", "chance": 35,
     "description": "Простой деревянный сундук 🌳. Может дать каменные и железные эмодзи."},
    {"name": "Шалкер", "price": 135, "image": "shulker.png", "chance": 20,
     "description": "Мистический шалкер 📦. Может дать железные и золотые эмодзи."},
    {"name": "Командный блок", "price": 169, "image": "command.png", "chance": 10,
     "description": "Легендарный командный блок 🚀. Может дать алмазные и незеритовые эмодзи."}
]

def minor_get_main_menu_markup(user_id):
    """
    Мини-меню для несовершеннолетних без полного доступа.
    Пока там только «Профиль», но можно расширить.
    """
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("👤 Профиль", callback_data="menu_profile"))
    return markup


def find_user_by_nick_or_username(nick, data):
    nick = nick.lstrip("@").lower()
    for uid, u in data.get("users", {}).items():
        if u.get("nickname", "").lower() == nick or u.get("telegram_username", "").lower() == nick:
            return uid
    return None


# ------------------- Функции загрузки/сохранения и валидации -------------------
def load_data():
    ordered_keys = [
        "users",
        "promo_codes",
        "tribes",
        "invalid_registrations",
        "banned_users",
        "registration_requests",
        "pending_requests"
    ]

    default_data = {
        "users": {},
        "promo_codes": {},
        "tribes": {},
        "invalid_registrations": [],
        "banned_users": {},
        "registration_requests": [],
        "pending_requests": {}
    }

    # Если файл не существует — создаём с нужным порядком
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(default_data, f, indent=4)
        return default_data

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Заполняем недостающие ключи
        for key in default_data:
            if key not in data:
                data[key] = default_data[key]

        # Назначаем роль "игрок" по умолчанию
        for uid, user in data["users"].items():
            if "role" not in user:
                user["role"] = "игрок"

        for lid, tribe in data.get("tribes", {}).items():
            tribe.setdefault("level", 1)
            tribe.setdefault("xp", 0)

        # Сохраняем в правильном порядке
        ordered_data = OrderedDict()
        for key in ordered_keys:
            if key in data:
                ordered_data[key] = data[key]

        # Добавляем всё остальное в конец
        for key in data:
            if key not in ordered_data:
                ordered_data[key] = data[key]

        # Сохраняем обратно, чтобы зафиксировать порядок
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(ordered_data, f, indent=4)

        return ordered_data

    except json.decoder.JSONDecodeError as e:
        # если файл битый, делаем резервную копию перед восстановлением
        try:
            backup_path = DATA_FILE + ".bak"
            if os.path.exists(DATA_FILE):
                os.replace(DATA_FILE, backup_path)
        except Exception as backup_err:
            print(f"[Ошибка бэкапа data.json]: {backup_err}")

        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(default_data, f, indent=4)
        try:
            msg = (
                f"❗ Ошибка загрузки data.json: {e}. Создан новый файл, старая версия сохранена как {os.path.basename(backup_path)}."
            )
            bot.send_message(ADMIN_ID, msg)
        except Exception as send_err:
            print(f"[Ошибка при уведомлении админа]: {send_err}")



def save_data(data):
    """Сохраняет данные атомарно, чтобы избежать повреждения файла."""
    tmp = DATA_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
    os.replace(tmp, DATA_FILE)


def add_user_notification_record(data, uid, text):
    user = data["users"].setdefault(uid, {})
    notes = user.setdefault("notifications", [])
    notes.append({
        "time": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "text": text
    })
    if len(notes) > 100:
        user["notifications"] = notes[-100:]

# ---------- Работа с архивом сезонов ----------
def load_seasons():
    if not os.path.exists(SEASONS_FILE):
        with open(SEASONS_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_SEASONS, f, indent=4)
        return DEFAULT_SEASONS
    try:
        with open(SEASONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.decoder.JSONDecodeError:
        return DEFAULT_SEASONS

def save_seasons(seasons):
    """Атомарно сохраняет архив сезонов."""
    tmp = SEASONS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(seasons, f, indent=4)
    os.replace(tmp, SEASONS_FILE)

# ---------- Судебные дела ----------
# ---------- Работа с john.json (дела и штрафы) ----------
def load_john():
    default = {
        "cases": {"last_id": 0, "active": [], "archive": []},
        "fines": {"last_id": 0, "active": [], "closed": []}
    }
    if not os.path.exists(JOHN_FILE):
        with open(JOHN_FILE, "w", encoding="utf-8") as f:
            json.dump(default, f, indent=4)
        return default
    try:
        with open(JOHN_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.decoder.JSONDecodeError:
        data = default
    for key in default:
        if key not in data:
            data[key] = default[key]
    return data


def save_john(data):
    tmp = JOHN_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
    os.replace(tmp, JOHN_FILE)


def load_cases():
    return load_john().get("cases", {"last_id": 0, "active": [], "archive": []})


def save_cases(cases):
    data = load_john()
    data["cases"] = cases
    save_john(data)


# ---------- Штрафы ----------
def load_fines():
    return load_john().get("fines", {"last_id": 0, "active": [], "closed": []})


def save_fines(fines):
    data = load_john()
    data["fines"] = fines
    save_john(data)


def add_fine(fine):
    fines = load_fines()
    fines["last_id"] += 1
    fine_id = f"{fines['last_id']:03d}"
    fine["id"] = fine_id
    fine["created_at"] = datetime.now().strftime("%d.%m.%Y %H:%M")
    fine["status"] = "open"
    fines["active"].append(fine)
    save_fines(fines)
    return fine_id


def close_fine(fine_id):
    fines = load_fines()
    fine = next((f for f in fines.get("active", []) if f["id"] == fine_id), None)
    if not fine:
        return False
    fine["status"] = "closed"
    fine["closed_at"] = datetime.now().strftime("%d.%m.%Y %H:%M")
    fines["active"] = [f for f in fines["active"] if f["id"] != fine_id]
    fines.setdefault("closed", []).append(fine)
    save_fines(fines)
    return True


def add_case(case):
    cases = load_cases()
    cases["last_id"] += 1
    case_id = f"{cases['last_id']:03d}"
    case["id"] = case_id
    case["created_at"] = datetime.now().strftime("%d.%m.%Y %H:%M")
    case["status"] = "open"
    cases["active"].append(case)
    save_cases(cases)
    return case_id


def user_has_court_access(user):
    return user.get("role") in ["Президент", "Мэр", "Прокурор"]

def user_has_fine_access(user):
    return user.get("role") in ["Министр Финансов", "Прокурор", "Президент", "Мэр"]

def valid_nickname(nickname):
    return bool(re.fullmatch(r"[A-Za-z0-9 _]{3,16}", nickname))

def valid_birthdate(birthdate):
    try:
        datetime.strptime(birthdate, "%d.%m.%Y")
        return True
    except ValueError:
        return False
   


def calculate_age(birthdate):
    birth_date = datetime.strptime(birthdate, "%d.%m.%Y")
    today = datetime.today()
    return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))

def migrate_minors_out(data):
    """
    Перенесём всех, у кого is_minor=True, из data['users'] в data['minors'].
    """
    data.setdefault("minors", {})
    for uid, user in list(data.get("users", {}).items()):
        if user.get("is_minor"):
            data["minors"][uid] = data["users"].pop(uid)
    return data

# где-то при старте бота:
data = load_data()
data = migrate_minors_out(data)
save_data(data)


# ------------------- Markup definitions -------------------
def get_main_menu_markup(user_id):
    data   = load_data()
    user   = data["users"].get(user_id, {})
    status = user.get("status", "user")

    markup = types.InlineKeyboardMarkup()

    # 📛 Забанен
    if status == "banned":
        markup.add(types.InlineKeyboardButton("🔓 Разбан за 500₽", callback_data="request_unban"))
        markup.add(types.InlineKeyboardButton("👤 Профиль",      callback_data="menu_profile"))
        return markup

    # ⛔ Несовершеннолетний без прохода
    if status == "minor" and not user.get("full_access"):
        markup.add(types.InlineKeyboardButton("🧸 Пропуск (250₽)", callback_data="buy_minor_pass"))
        markup.add(types.InlineKeyboardButton("👤 Профиль",        callback_data="menu_profile"))
        return markup

    # ✅ Обычный пользователь
    # ── Ряд 1: Профиль
    markup.row(
        types.InlineKeyboardButton("👤 Профиль", callback_data="menu_profile")
    )

    # ── Ряд 2: Маркет + Сообщество
    btn_market    = types.InlineKeyboardButton("🛒 Маркет",     callback_data="market_main")
    btn_community = types.InlineKeyboardButton("🆕 Сообщество", callback_data="community_menu")
    markup.row(btn_market, btn_community)

    # ── Ряд 2½: 📖 Гид  (показываем, пока не завершён и ещё не открыт)
    if not user.get("guide_completed") and user.get("guide_step", 0) == 0:
        markup.row(
            types.InlineKeyboardButton("📖 Гид", callback_data="open_guide")
        )

    # ── Ряд 3: Уведомления
    btn_notify = types.InlineKeyboardButton(
        "⚙️ Уведомления",
        callback_data="open_notifications"
    )
    markup.row(btn_notify)

    # ← вот это!
    return markup


@bot.callback_query_handler(func=lambda call: call.data == "request_unban")
def handle_unban_request(call):
    user_id = str(call.from_user.id)
    data = load_data()
    user = data["users"].get(user_id)

    if user_id not in data.get("banned_users", {}):
        bot.answer_callback_query(call.id, "Вы не забанены.")
        return

    if user.get("balance", 0) < 500:
        bot.send_message(call.message.chat.id, "❌ Недостаточно средств. Разбан стоит 500₽.")
        return

    user["balance"] -= 500
    user["status"] = "user"
    user["full_access"] = True
    user.setdefault("purchases", []).append({
        "item": "Разбан",
        "price": 500,
        "date": datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    })

    del data["banned_users"][user_id]

    save_data(data)
    bot.send_message(call.message.chat.id, "✅ Вы успешно разблокированы!", reply_markup=get_main_menu_markup(user_id))


@bot.callback_query_handler(func=lambda call: call.data == "buy_minor_pass")
def handle_minor_pass_purchase(call):
    user_id = str(call.from_user.id)
    data = load_data()
    user = data["users"].get(user_id)

    if user_id not in data.get("invalid_registrations", {}):
        bot.answer_callback_query(call.id, "Вы уже прошли проверку.")
        return

    if user.get("balance", 0) < 250:
        bot.send_message(call.message.chat.id, "❌ Недостаточно средств. Пропуск стоит 250₽.")
        return

    user["balance"] -= 250
    user["full_access"] = True
    user["status"] = "user"
    user.setdefault("purchases", []).append({
        "item": "Пропуск несовершеннолетнего",
        "price": 250,
        "date": datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    })

    del data["invalid_registrations"][user_id]

    save_data(data)
    bot.send_message(call.message.chat.id, "✅ Пропуск активирован! Добро пожаловать.", reply_markup=get_main_menu_markup(user_id))

# ─────────────────────────────────────────────────────────────
#                🔔 NOTIFICATIONS BLOCK
# ─────────────────────────────────────────────────────────────

# в начале файла, после импортов:
FLAG_MAP = {
    "bot_updates":   1 << 0,  # 1
    "technical":     1 << 1,  # 2
    "tribe":         1 << 2,  # 4
    "server_news":   1 << 3,  # 8
    "gov_news":      1 << 4,  # 16
}

NOTIFICATION_LABELS = {
    "bot_updates":   "Изменения в боте",
    "technical":     "Технические",
    "tribe":         "От трайба",
    "server_news":   "События сервера",
    "gov_news":      "Гос новости",
}

# Обработчик открытия меню оповещений
@bot.callback_query_handler(lambda c: c.data == "open_notifications")
def open_notifications(call):
    user_id = str(call.from_user.id)
    data    = load_data()
    user    = data["users"].setdefault(user_id, {})

    # Вычисляем сумму всех флагов
    all_mask = sum(FLAG_MAP.values())
    # Дефолт: если старый subscribed=True — все флаги,
    # иначе — всё кроме “Изменения в боте”
    if user.get("subscribed", False):
        default_mask = all_mask
    else:
        default_mask = all_mask & ~FLAG_MAP["bot_updates"]

    # При первом заходе устанавливаем default_mask
    if "notif_flags" not in user:
        user["notif_flags"] = default_mask

    # Удаляем устаревший ключ
    user.pop("subscribed", None)
    save_data(data)

    mask = user["notif_flags"]
    markup = types.InlineKeyboardMarkup(row_width=1)
    for key, label in NOTIFICATION_LABELS.items():
        is_on = bool(mask & FLAG_MAP[key])
        emoji = "🔊" if is_on else "🔇"
        markup.add(types.InlineKeyboardButton(
            f"{emoji} {label}",
            callback_data=f"toggle_notification:{key}"
        ))

    markup.add(types.InlineKeyboardButton("🗂️ Архив уведомлений", callback_data="notif_archive"))

    # Кнопка “Назад”
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="get_main_menu_markup"))

    bot.edit_message_text(
        "🔊 <b>Настройки оповещений</b>\n\n"
        "Нажми на нужную, чтобы включить или выключить:",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="HTML",
        reply_markup=markup
    )

# Обработчик переключения одной категории
@bot.callback_query_handler(lambda c: c.data.startswith("toggle_notification:"))
def toggle_notification(call):
    user_id  = str(call.from_user.id)
    category = call.data.split(":", 1)[1]

    data = load_data()
    user = data["users"].setdefault(user_id, {})

    mask = user.get("notif_flags", 0)
    flag = FLAG_MAP[category]

    # Переключаем бит
    mask ^= flag
    user["notif_flags"] = mask
    save_data(data)

    status = "включены" if (mask & flag) else "выключены"
    bot.answer_callback_query(call.id, f"{NOTIFICATION_LABELS[category]} — уведомления {status}.")

    # Обновляем меню
    open_notifications(call)


@bot.callback_query_handler(lambda c: c.data == "notif_archive")
def notif_archive(call):
    user_id = str(call.from_user.id)
    data = load_data()
    user = data["users"].setdefault(user_id, {})
    notes = user.get("notifications", [])
    if not notes:
        text = "Архив уведомлений пуст."
    else:
        lines = [f"{n['time']}: {n['text']}" for n in notes[-10:][::-1]]
        text = "\n\n".join(lines)
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="open_notifications"))
    bot.edit_message_text(text or "Архив уведомлений пуст.", call.message.chat.id, call.message.message_id, reply_markup=markup)



def profile_menu_markup():
    markup = types.InlineKeyboardMarkup()
    btn_topup = types.InlineKeyboardButton("Пополнить 💳", callback_data="profile_topup")
    btn_history = types.InlineKeyboardButton("История 📜", callback_data="profile_history")
    btn_promo = types.InlineKeyboardButton("Промокод 🎫", callback_data="activate_promo_welcome")
    btn_back = types.InlineKeyboardButton("Назад 🔙", callback_data="get_main_menu_markup")
    markup.row(btn_topup, btn_history)
    markup.row(btn_promo)
    markup.row(btn_back)
    return markup

def welcome_markup():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("Главное меню"))
    return markup

@bot.callback_query_handler(func=lambda call: call.data == "get_main_menu_markup")
def return_welcome(call):
    user_id = str(call.from_user.id)
    send_main_menu(user_id, call.message.chat.id)



# Префиксы для категорий эмодзи
EMOJI_PREFIXES = {
    "0":       "🪨",   # Каменные
    "1":       "⚙️",  # Железные 
    "2":       "✨",   # Золотые
    "3":       "💎",   # Алмазные
    "4":       "🔥",   # Незеритовые
    "event":   "🚩",  # Ивентовые 
    "special": "🙊",  # Особые 
}

@bot.callback_query_handler(func=lambda call: call.data.startswith("profile_"))
def handle_profile(call):
    user_id = str(call.from_user.id)
    data = load_data()
    if user_id not in data["users"]:
        bot.answer_callback_query(call.id, "Вы не зарегистрированы.")
        return

    # под‐меню профиля
    if call.data == "tribe_join_menu":
        handle_tribe_join_menu(call)
        return
    if call.data == "profile_history":
        user = data["users"][user_id]
        history_text = "История:\n"
        for p in user.get("purchases", []):
            history_text += f"{p['date']}: {p['item']} - {p['price']}₽\n"
        if user.get("referral_history"):
            history_text += "\nРеферальные зачисления:\n"
            for r in user["referral_history"]:
                history_text += f"{r['date']}: {r['item']} - {r['amount']}₽\n"
        bot.send_message(call.message.chat.id, history_text, reply_markup=profile_menu_markup())
        return
    if call.data == "profile_topup":
        bot.send_message(
            call.message.chat.id,
            "⏳ Пополнение через донейшен.\nПлатежи могут обрабатываться до 48 часов.\n"
            "Отправьте донейшен и укажите свой ник:\nhttps://www.donationalerts.com/r/bedrock_valley",
            reply_markup=types.InlineKeyboardMarkup().add(
                types.InlineKeyboardButton("Назад 🔙", callback_data="profile_menu")
            )
        )
        return
    if call.data == "activate_promo_welcome":
        msg = bot.send_message(call.message.chat.id, "Введите промокод для активации:")
        bot.register_next_step_handler(msg, process_profile_promo)
        return

    # основной профиль
    user = data["users"][user_id]
    reg_date  = user.get("registration_date", "").split()[0] or "—"
    bv_status = "активна" if user.get("bv_plus") else "неактивна"

    profile_text = (
        
    )

    # вставляем список эмодзи с префиксами
    emojis = ensure_user_emojis(user)
    save_data(data)

    if not any(emojis.values()):
        profile_text += "    — пока пусто\n"
    else:
        for cat_key, nums in emojis.items():
            if not nums:
                continue
            icon = EMOJI_PREFIXES.get(cat_key, "")
            if cat_key.isdigit():
                idx      = int(cat_key)
                cat_name = emoji_details[idx]["name"]
                count    = len(nums)
                profile_text += f"    {icon}{cat_name}: {count}\n"
            else:
                cat_name = EXTRA_CATEGORIES.get(cat_key, f"Категория {cat_key}")
                values   = ", ".join(nums)
                profile_text += f"    {icon}{cat_name}: {values}\n"

    bot.send_message(
        call.message.chat.id,
        profile_text,
        parse_mode="HTML",
        reply_markup=profile_menu_markup()
    )



MARKET_WELCOME_TEXT = (
    "🎮 Добро пожаловать в Маркет BedrockValley! 🎮\n"
    "Здесь ты найдёшь всё для выживания, стиля и крутых фишек на сервере!"
)

def get_daily_gift_label(user):
    """
    Возвращает текст для кнопки «подарок» в зависимости от того,
    забрал ли пользователь подарок сегодня.
    Если уже брал — показывает, сколько часов осталось до следующего.
    """
    today_str = date.today().isoformat()
    if user.get("last_daily_gift") == today_str:
        # время до завтрашнего дня
        now = datetime.now()
        tomorrow = datetime.combine(now.date() + timedelta(days=1), datetime.min.time())
        hours_left = (tomorrow - now).seconds // 3600
        return f"⏳ {hours_left}ч"
    else:
        return "🎁 Подарок"




def market_main_markup(user_id):
    """
    Меню Маркета:
    - BV#, Кастомизация, Доп. услуги
    - Динамическая кнопка подарка
    - Назад
    """
    data = load_data()
    user = data["users"].get(user_id, {})

    gift_label = get_daily_gift_label(user)

    markup = types.InlineKeyboardMarkup(row_width=3)
    btn_bv     = types.InlineKeyboardButton("BV# ⭐",            callback_data="subscribe_bv_plus_market")
    btn_custom = types.InlineKeyboardButton("Украшение ✨", callback_data="customization")
    btn_top    = types.InlineKeyboardButton("Доп услуги ➕",     callback_data="top_services")
    btn_gift   = types.InlineKeyboardButton(gift_label,         callback_data="daily_gift")
    btn_back   = types.InlineKeyboardButton("🔙 Назад",          callback_data="get_main_menu_markup")

    # Раскладка: 3 кнопки в первом ряду, подарок отдельно, затем Назад
    markup.add(btn_bv, btn_custom, btn_top)
    markup.add(btn_gift)
    markup.add(btn_back)
    return markup


def customization_markup():
    markup = types.InlineKeyboardMarkup()
    btn_emoji = types.InlineKeyboardButton("Эмодзи 😊", callback_data="custom_emoji")
    btn_case = types.InlineKeyboardButton("Кейсы 📦", callback_data="custom_case")
    btn_back = types.InlineKeyboardButton("Назад 🔙", callback_data="market_main")
    markup.add(btn_emoji, btn_case)
    markup.add(btn_back)
    return markup

def top_services_markup():
    markup = types.InlineKeyboardMarkup()
    btn_unban = types.InlineKeyboardButton("Разбан - 500₽ 🔓", callback_data="service_unban")
    btn_back = types.InlineKeyboardButton("Назад 🔙", callback_data="market_main")
    markup.add(btn_unban)
    markup.add(btn_back)
    return markup

def emoji_info_markup(index):
    markup = types.InlineKeyboardMarkup()
    btn_buy = types.InlineKeyboardButton("Купить 💰", callback_data=f"buy_emoji_{index}")
    nav_buttons = []
    if index > 0:
        nav_buttons.append(types.InlineKeyboardButton("◀️", callback_data=f"emoji_prev_{index}"))
    nav_buttons.append(types.InlineKeyboardButton(f"{index+1}/{len(emoji_details)}", callback_data="noop"))
    if index < len(emoji_details) - 1:
        nav_buttons.append(types.InlineKeyboardButton("▶️", callback_data=f"emoji_next_{index}"))
    btn_back = types.InlineKeyboardButton("Назад 🔙", callback_data="customization_back")
    markup.add(*nav_buttons)
    markup.add(btn_buy, btn_back)
    return markup

def case_info_markup(index):
    markup = types.InlineKeyboardMarkup()
    btn_buy = types.InlineKeyboardButton("Купить 💰", callback_data=f"buy_case_{index}")
    nav_buttons = []
    if index > 0:
        nav_buttons.append(types.InlineKeyboardButton("◀️", callback_data=f"case_prev_{index}"))
    nav_buttons.append(types.InlineKeyboardButton(f"{index+1}/{len(case_details)}", callback_data="noop"))
    if index < len(case_details) - 1:
        nav_buttons.append(types.InlineKeyboardButton("▶️", callback_data=f"case_next_{index}"))
    btn_back = types.InlineKeyboardButton("Назад 🔙", callback_data="customization_back")
    markup.add(*nav_buttons)
    markup.add(btn_buy, btn_back)
    return markup

# Универсальный механизм отмены текущего ввода
def cancel_pending_action(user_id):
    if user_id in user_states:
        user_states.pop(user_id, None)

@bot.callback_query_handler(func=lambda call: call.data == "cancel_input")
def cancel_input_handler(call):
    user_id = str(call.from_user.id)
    cancel_pending_action(user_id)
    bot.edit_message_text(
        "Действие отменено. Вы вернулись в главное меню.",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=get_main_menu_markup(user_id)
    )

# Функция отправки главного меню с случайным советом
def send_main_menu(user_id, chat_id):
    """
    Обновляет стрик и отправляет главное меню с случайным советом.
    """
    update_streak(user_id)  # Обновляем стрик (уведомление отправится один раз в день)
    
    tips = [
    "🧿 Око Эндера — твоя активность. Чем активнее, тем больше наград!",
    "🎁 Заходи в Маркет каждый день — там могут появиться подарки!",
    "🔥 Сохраняй стрик, чтобы получать больше Оков Эндера и бонусов!",
    "🎯 Выполняй любые действия в боте — за них ты получаешь 🧿 Око Эндера!",
    "🛒 Проверь магазин эмодзи — возможно, добавили новые!",
    "🎨 Загляни в кастомизацию — пора освежить стиль?",
    "🏰 Вступи в трайб или создай свой — ты готов к приключениям!",
    "📢 Включи Новости 🔊 от бота, чтобы не пропустить обновления!",
    "⭐ BV# даёт бонусы, кейсы и кастомные эмодзи — не упусти шанс!",
    "👥 Приглашай друзей и получай бонусы за каждого приглашённого!",
    "📅 Стрик — это 🔥 и 🧿. Не теряй прогресс!",
    "🎉 Око Эндера можно получить даже случайно. Будь активен!",
    "🔓 Некоторые фичи открываются только за 🧿 Око Эндера — копи с умом!",
    "🕹 Участвуй в ивентах, чтобы выбить редкие эмодзи и кейсы!",
    "🏆 Твой ник может попасть в топ активных — не упусти шанс!",
    "🌀 Ты — часть Bedrock Valley. Сделай своё имя громким!"
]


    chosen_tip = random.choice(tips)
    
    main_text = (
        "🎉 Главное меню 🎉\n\n"
        f"{chosen_tip}\n\n"
        "Подпишитесь: @bedrockvalley"
    )
    bot.send_message(chat_id, main_text, reply_markup=get_main_menu_markup(user_id))


@bot.message_handler(commands=['tribe'])
def cmd_tribe(message):
    call = SimpleNamespace(
        message=message,
        from_user=message.from_user,
        data="community_tribes"
    )
    try:
        tribe_main_menu(call)
    except Exception as e:
        print(f"[ERROR] Ошибка показа меню трайбов: {e}")
        try:
            bot.send_message(message.chat.id, "🏘 Меню трайбов")
        except Exception as err:
            print(f"[ERROR] Не удалось отправить fallback сообщение: {err}")


@bot.message_handler(commands=['streak'])
def cmd_streak(message):
    user_id = str(message.from_user.id)
    data = load_data()
    user = data["users"].get(user_id)
    if user:
        streak = user.get("login_streak", 0)
        bot.send_message(message.chat.id, f"🔥 Ваш текущий стрик: <b>{streak}</b> дней.", parse_mode="HTML")
    else:
        bot.send_message(message.chat.id, "❌ Вы не зарегистрированы.")
# ------------------- Обновлённый блок админского меню -------------------
from random import choice
from datetime import datetime

def get_admin_markup_new():
    markup = types.InlineKeyboardMarkup(row_width=1)
    btn_xp            = types.InlineKeyboardButton("👑 Добавить опыта",    callback_data="admin_add_xp")
    btn_promos        = types.InlineKeyboardButton("📣 Промокоды",         callback_data="admin_promos")
    btn_notifications = types.InlineKeyboardButton("🔔 Оповещения",        callback_data="admin_notifications")
    btn_roles         = types.InlineKeyboardButton("🎭 Роли",              callback_data="admin_roles")
    btn_bans          = types.InlineKeyboardButton("⛔ Баны",              callback_data="admin_bans")
    btn_emojis        = types.InlineKeyboardButton("🗂 Эмодзи",            callback_data="admin_emoji_manage")
    markup.add(btn_xp, btn_promos, btn_notifications, btn_roles, btn_bans, btn_emojis)
    return markup

@bot.message_handler(commands=["admin"])
def admin_menu(message):
    if message.from_user.id != ADMIN_ID:
        return bot.send_message(message.chat.id, "Нет прав доступа.")
    bot.send_message(
        message.chat.id,
        "🔧 <b>Админское меню</b>:",
        parse_mode="HTML",
        reply_markup=get_admin_markup_new()
    )

# ——— Расширяем кнопку «Добавить опыта» — теперь полноценная выдача нескольким игрокам ———
@bot.callback_query_handler(lambda c: c.data == "admin_add_xp")
def admin_add_xp(call):
    # Запрашиваем ввод: список ников и сумму XP
    msg = bot.send_message(
        call.message.chat.id,
        "Введите пользователей и количество XP в формате:\n"
        "<code>nick1,nick2,@user3|50</code>\n"
        "Где слева через запятую — никнеймы или @username, справа — число XP.\n"
        "Пример: <code>player1,player2|100</code>",
        parse_mode="HTML"
    )
    bot.register_next_step_handler(msg, process_admin_add_xp)

def process_admin_add_xp(message):
    # Защита: только админ
    if message.from_user.id != ADMIN_ID:
        return bot.send_message(message.chat.id, "❌ Нет прав доступа.")
    
    text = message.text.strip()
    if "|" not in text:
        return bot.send_message(message.chat.id, "❌ Неверный формат. Используйте <code>nick1,nick2|50</code>.", parse_mode="HTML")
    
    users_part, xp_part = text.split("|", 1)
    try:
        xp_amount = int(xp_part.strip())
    except ValueError:
        return bot.send_message(message.chat.id, "❌ Количество XP должно быть числом.")
    
    nicks = [n.strip() for n in users_part.split(",") if n.strip()]
    data = load_data()
    results = []
    
    for nick in nicks:
        uid = find_user_by_nick_or_username(nick, data)
        if not uid:
            results.append(f"❌ Пользователь «{nick}» не найден")
            continue
        
        user = data["users"][uid]
        add_user_xp(uid, xp_amount, data)
        update_xp(uid)
        
        # уведомляем игрока
        try:
            bot.send_message(
                int(uid),
                f"👑 Администратор начислил вам <b>+{xp_amount} XP</b>.\n"
                f"Ваш новый баланс опыта: {user['xp']} XP",
                parse_mode="HTML"
            )
        except:
            pass
        
        results.append(f"✅ {nick}: +{xp_amount} XP")
    
    save_data(data)

    bot.send_message(
        message.chat.id,
        "<b>Результаты выдачи XP:</b>\n" + "\n".join(results),
        parse_mode="HTML"
    )

# ——— Промокоды ———
@bot.callback_query_handler(lambda c: c.data == "admin_promos")
def admin_promos_menu(call):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("Добавить промокод",   callback_data="admin_add_promo"),
        types.InlineKeyboardButton("Посмотреть промокоды", callback_data="admin_view_promos"),
        types.InlineKeyboardButton("Удалить промокод",     callback_data="admin_del_promo"),
        types.InlineKeyboardButton("Начислить средства",   callback_data="admin_credit_funds")
    )
    bot.edit_message_text(
        "📣 <b>Меню промокодов</b>:",
        call.message.chat.id, call.message.message_id,
        parse_mode="HTML", reply_markup=markup
    )
# ——— Блок админских оповещений с начислением +10 XP каждому подписчику ———

@bot.callback_query_handler(lambda c: c.data == "admin_notifications")
def admin_notifications_menu(call):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("Сделать объявление",    callback_data="admin_announcement"),
        types.InlineKeyboardButton("Обновления бота",        callback_data="admin_notification_bot"),
        types.InlineKeyboardButton("Технические",            callback_data="admin_notification_technical"),
        types.InlineKeyboardButton("Новости сервера",        callback_data="admin_notification_server")
    )
    bot.edit_message_text(
        "🔔 <b>Меню оповещений</b>:",
        call.message.chat.id, call.message.message_id,
        parse_mode="HTML", reply_markup=markup
    )

@bot.callback_query_handler(lambda c: c.data == "admin_notification_bot")
def admin_notification_bot(call):
    msg = bot.send_message(call.message.chat.id, "Введите текст «Обновления бота»:")
    bot.register_next_step_handler(msg, process_admin_notification, "bot_updates")

@bot.callback_query_handler(lambda c: c.data == "admin_notification_technical")
def admin_notification_technical(call):
    msg = bot.send_message(call.message.chat.id, "Введите текст «Технических уведомлений»:")
    bot.register_next_step_handler(msg, process_admin_notification, "technical")

@bot.callback_query_handler(lambda c: c.data == "admin_notification_server")
def admin_notification_server(call):
    msg = bot.send_message(call.message.chat.id, "Введите текст «Новости сервера»:")
    bot.register_next_step_handler(msg, process_admin_notification, "server_news")

def process_admin_notification(message, category_key):
    data = load_data()
    hashtag_map = {
        "bot_updates": "#бот",
        "technical":   "#тех",
        "server_news": "#ньюс"
    }
    tag       = hashtag_map.get(category_key, "")
    full_text = f"{message.text}\n\n{tag}"
    sent      = 0

    # Шлём уведомление и начисляем +10 XP каждому подписчику выбранной категории
    for uid, u in data.get("users", {}).items():
        if u.get("notif_flags", 0) & FLAG_MAP.get(category_key, 0):
            try:
                bot.send_message(uid, full_text)
                add_user_xp(uid, 10, data)
                update_xp(uid)
                add_user_notification_record(data, uid, full_text)
                sent += 1
            except Exception:
                pass

    save_data(data)

    bot.send_message(
        message.chat.id,
        f"✅ Отправлено {sent} уведомлений «{category_key}» и начислено по +10 XP каждому.",
        parse_mode="HTML"
    )


# ——— Роли ———
@bot.callback_query_handler(lambda c: c.data == "admin_roles")
def admin_roles_menu(call):
    data = load_data()
    roles = {
        "PRES001": "Президент",
        "MAY002":  "Мэр",
        "CON003":  "Министр Строительства",
        "FIN004":  "Министр Финансов",
        "PROK005": "Прокурор"
    }
    text = "<b>🎭 Меню управления ролями</b>\n━━━━━━━━━━━━━━━━\n"
    for code, role in roles.items():
        owner = "<i>не назначено</i>"
        for uid, u in data["users"].items():
            if u.get("role") == role:
                nick = u.get("nickname", "—")
                uname = u.get("telegram_username", "")
                owner = nick if role == "Президент" else (
                    f"<a href='https://t.me/{uname}'>{nick}</a>" if uname else nick
                )
                break
        text += f"{code}: <b>{role}</b> — {owner}\n"
    markup = types.InlineKeyboardMarkup(row_width=3)
    markup.add(
        types.InlineKeyboardButton("Добавить роль",  callback_data="admin_add_role"),
        types.InlineKeyboardButton("Изменить роль",  callback_data="admin_modify_role"),
        types.InlineKeyboardButton("Удалить роль",   callback_data="admin_del_role")
    )
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                          parse_mode="HTML", reply_markup=markup)

# ——— Баны ———
@bot.callback_query_handler(lambda c: c.data == "admin_bans")
def admin_bans_menu(call):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🔒 Забанить",  callback_data="admin_ban_user"),
        types.InlineKeyboardButton("🔓 Разбанить", callback_data="admin_unban_user")
    )
    bot.edit_message_text(
        "⛔ <b>Меню банов</b>:",
        call.message.chat.id, call.message.message_id,
        parse_mode="HTML", reply_markup=markup
    )

# ——— Подменю «Эмодзи» с массовой выдачей/удалением по никам ———

def find_user_by_nick(nick, data):
    for uid, u in data.get("users", {}).items():
        if u.get("nickname") == nick or u.get("telegram_username") == nick:
            return uid
    return None

@bot.callback_query_handler(lambda c: c.data == "admin_emoji_manage")
def admin_emoji_manage(call):
    labels = {str(i): d["name"] for i, d in enumerate(emoji_details)}
    labels.update(EXTRA_CATEGORIES)
    markup = types.InlineKeyboardMarkup(row_width=1)
    for key, label in labels.items():
        markup.add(types.InlineKeyboardButton(label, callback_data=f"admin_emoji_cat:{key}"))
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="open_admin_menu"))
    bot.edit_message_text(
        "🗂 <b>Управление эмодзи</b>:\nВыберите категорию:",
        call.message.chat.id, call.message.message_id,
        parse_mode="HTML", reply_markup=markup
    )

@bot.callback_query_handler(lambda c: c.data.startswith("admin_emoji_cat:"))
def admin_emoji_cat(call):
    key = call.data.split(":", 1)[1]
    admin_id = str(call.from_user.id)
    data = load_data()
    data.setdefault("admin_ctx", {})[admin_id] = {"emoji_key": key}
    save_data(data)

    if key.isdigit():
        detail = emoji_details[int(key)]
        prompt = (
            f"🗂 <b>{detail['name']}</b>\n"
            "Формат: <code>nick1,nick2</code>|<code>±N</code>\n"
            "Пример: player1,player2|+3"
        )
    else:
        prompt = (
            f"🗂 <b>{EXTRA_CATEGORIES[key]}</b>\n"
            "Формат: <code>nick1,nick2</code>|<code>name1,name2,-name3</code>\n"
            "Пример: player1,player2|Firework,-Pumpkin"
        )

    msg = bot.send_message(call.message.chat.id, prompt, parse_mode="HTML")
    bot.register_next_step_handler(msg, process_admin_emoji)

def process_admin_emoji(message):
    admin_id = str(message.from_user.id)
    data = load_data()
    ctx = data.get("admin_ctx", {}).get(admin_id, {})
    key = ctx.get("emoji_key")
    if not key:
        return bot.send_message(message.chat.id, "Контекст утерян, начните заново.")

    try:
        left, right = message.text.strip().split("|", 1)
    except ValueError:
        return bot.send_message(message.chat.id, "Неверный формат. Используйте «nick1,nick2|…»")

    nicks = [n.strip() for n in left.split(",") if n.strip()]
    response = []

    if key.isdigit():
        cnt = int(right.strip())
        detail = emoji_details[int(key)]
        for nick in nicks:
            uid = find_user_by_nick(nick, data)
            if not uid:
                response.append(f"❌ Пользователь «{nick}» не найден")
                continue
            user = data["users"].setdefault(uid, {})
            packs = ensure_user_emojis(user)[key]
            if cnt > 0:
                owned, cap = len(packs), detail["quantity"]
                to_add = min(cnt, cap - owned)
                for i in range(to_add):
                    packs.append(owned + i + 1)
                response.append(f"✅ {to_add} эмодзи выдано {nick}")
            else:
                to_remove = min(-cnt, len(packs))
                for _ in range(to_remove):
                    packs.pop()
                response.append(f"✅ {to_remove} эмодзи удалено у {nick}")
    else:
        ops = [o.strip() for o in right.split(",") if o.strip()]
        for nick in nicks:
            uid = find_user_by_nick(nick, data)
            if not uid:
                response.append(f"❌ Пользователь «{nick}» не найден")
                continue
            user = data["users"].setdefault(uid, {})
            packs = ensure_user_emojis(user)[key]
            added = removed = 0
            for op in ops:
                if op.startswith("-"):
                    name = op[1:]
                    if name in packs:
                        packs.remove(name)
                        removed += 1
                else:
                    name = op
                    if name not in packs:
                        packs.append(name)
                        added += 1
            response.append(f"🗂 {nick}: +{added}, −{removed}")

    data["admin_ctx"].pop(admin_id, None)
    save_data(data)

    bot.send_message(message.chat.id, "\n".join(response))

# ------------------- Окно BV# -------------------
@bot.callback_query_handler(func=lambda call: call.data in ["subscribe_bv_plus", "subscribe_bv_plus_market"])
def show_bv_plus_window(call):
    bv_description = (
    "✨ <b>Подписка BV#</b> — выделяйся среди игроков и получай бонусы!\n\n"
    "💰 <b>Только сейчас:</b> первый месяц — <u>со скидкой</u> <b>169₽</b>, затем <b>199₽/мес</b>\n"
    "🎁 <b>Подарок:</b> кейс <i>«Командный блок»</i> за каждую покупку или продление\n"
    "🎨 <b>Цвет ника:</b> выбери <u>любой</u> цвет ника в Minecraft\n"
    "😎 <b>Эмодзи:</b> доступ ко <u>всем платным</u> эмодзи (кроме Незеритовых) <i>на время подписки</i>\n"
    "🌟 <b>Плюс:</b> навсегда получаешь <u>уникальный эмодзи</u>\n"
    "⚡ <b>Опыт:</b> получай <u>1.5×</u> опыта за все действия\n\n"
    "👇 Нажмите кнопку <b>«Оформить подписку ⭐»</b>, чтобы активировать BV# и начать выделяться!"
)


    markup = types.InlineKeyboardMarkup()
    btn_subscribe = types.InlineKeyboardButton("Оформить подписку ⭐", callback_data="activate_bv_plus")
    btn_back = types.InlineKeyboardButton("Назад 🔙", callback_data="market_main")
    markup.add(btn_subscribe, btn_back)

    image_path = get_path("subscription.png")

    try:
        with open(image_path, "rb") as photo:
            media = types.InputMediaPhoto(media=photo, caption=bv_description, parse_mode="HTML")
            bot.edit_message_media(
                media=media,
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=markup
            )
    except FileNotFoundError:
        bot.send_message(
            call.message.chat.id,
            bv_description + "\n\n⚠️ Картинка подписки не найдена.",
            reply_markup=markup,
            parse_mode="HTML"
        )
    except Exception as e:
        print(f"[ERROR] show_bv_plus_window: {e}")
        bot.send_message(
            call.message.chat.id,
            bv_description + "\n\n⚠️ Ошибка при показе подписки.",
            reply_markup=markup,
            parse_mode="HTML"
        )


@bot.callback_query_handler(func=lambda call: call.data == "activate_bv_plus")
def activate_bv_plus(call):
    user_id = str(call.from_user.id)
    data = load_data()
    if user_id not in data["users"]:
        bot.answer_callback_query(call.id, "Пользователь не найден.")
        return
    user = data["users"][user_id]
    if user.get("bv_plus"):
        bot.send_message(call.message.chat.id, "BV# уже активна!", reply_markup=get_main_menu_markup(str(call.from_user.id)))
        return
    price = 169
    if user.get("balance", 0) < price:
        bot.send_message(call.message.chat.id, "Недостаточно средств для активации BV#.", reply_markup=get_main_menu_markup(str(call.from_user.id)))
        return
    user["balance"] -= price
    user["bv_plus"] = True
    user["bv_plus_expiry"] = (datetime.now() + timedelta(days=30)).strftime("%d.%m.%Y %H:%M:%S")
    if "purchases" not in user:
        user["purchases"] = []
    user["purchases"].append({
        "item": "BV# подписка (первый месяц со скидкой)",
        "price": price,
        "date": datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    })
    save_data(data)
    bot.send_message(
        call.message.chat.id,
        f"BV# успешно активирована! Подписка действует до {user['bv_plus_expiry']}.",
        reply_markup=get_main_menu_markup(str(call.from_user.id))
    )


# ------------------- Просмотр информации об эмодзи -------------------
def get_path(filename):
    return os.path.join(os.path.dirname(__file__), filename)

def show_emoji_info(chat_id, message_id, index):
    emoji_item = emoji_details[index]

    text = (
        f"🌟 <b>{emoji_item['name']}</b>\n"
        f"💰 Цена: <b>{emoji_item['price']}</b> монет\n"
        f"📦 Кол-во эмодзи: <b>{emoji_item['quantity']}</b>\n"
        f"ℹ️ {emoji_item['description']}"
    )

    image_path = get_path(emoji_item["image"])

    try:
        with open(image_path, "rb") as photo:
            bot.send_photo(chat_id, photo, caption=text, parse_mode="HTML", reply_markup=emoji_info_markup(index))
    except FileNotFoundError:
        bot.send_message(chat_id, text + "\n\n⚠️ Изображение не найдено.", parse_mode="HTML", reply_markup=emoji_info_markup(index))


# ------------------- Просмотр информации о кейсе -------------------

def show_case_info(chat_id, message_id, index):
    case_item = case_details[index]

    text = (
        f"📦 <b>{case_item['name']}</b>\n"
        f"💰 Цена: <b>{case_item['price']}₽</b>\n"
        f"🎁 Шанс получить 2 эмодзи: <b>{case_item['chance']}%</b>\n"
        f"ℹ️ {case_item['description']}\n\n"
        "Нажмите <b>Купить</b>, чтобы открыть кейс."
    )

    image_path = get_path(case_item["image"])

    try:
        with open(image_path, 'rb') as photo:
            media = types.InputMediaPhoto(photo, caption=text, parse_mode="HTML")
            bot.edit_message_media(
                chat_id=chat_id,
                message_id=message_id,
                media=media,
                reply_markup=case_info_markup(index)
            )
    except FileNotFoundError:
        safe_edit_message_text(text + "\n\n⚠️ Изображение не найдено.", chat_id, message_id, reply_markup=case_info_markup(index))

# ------------------- Обработка регистрации -------------------
@bot.message_handler(commands=["start"])
def handle_start(message):
    user_id = str(message.from_user.id)
    data = load_data()
    # Если пользователь уже зарегистрирован:
    if user_id in data["users"]:
        user = data["users"][user_id]
        if user.get("approved", False):
            # Перенаправляем в главное меню (с обновлением стрика и случайным советом)
            send_main_menu(user_id, message.chat.id)
            return
        else:
            bot.send_message(
                message.chat.id,
                "Ваша заявка на регистрацию находится на рассмотрении. Ожидайте ответа администрации."
            )
            return
    # Если пользователь не зарегистрирован – стандартная процедура регистрации:
    if message.from_user.username:
        for rec in data["invalid_registrations"]:
            if rec.get("telegram_username", "").lower() == message.from_user.username.lower():
                bot.send_message(
                    message.chat.id,
                    "Вы уже зарегистрированы как несовершеннолетний и повторная регистрация невозможна."
                )
                return
    bot.send_message(
        message.chat.id,
        f"Добро пожаловать! Вы используете версию {BOT_VERSION}. \nВведите ваш никнейм для регистрации."
    )
    user_states[user_id] = {"state": "awaiting_nickname", "temp_data": {}}

def register_new_user(user_id, info):
    data = load_data()
    # допустим, info["age"] уже есть
    if info.get("age", 0) < 18:
        # сохраняем в отдельный словарь
        data.setdefault("minors", {})[user_id] = info
    else:
        # совершеннолетние — в data["users"]
        data.setdefault("users", {})[user_id] = info
    save_data(data)


@bot.message_handler(func=lambda message: str(message.from_user.id) in user_states and user_states[str(message.from_user.id)].get("state") == "awaiting_nickname")
def handle_nickname(message):
    user_id = str(message.from_user.id)
    nickname = message.text.strip()
    if not valid_nickname(nickname):
        bot.send_message(message.chat.id, "Некорректный никнейм. Попробуйте снова:")
        return
    user_states[user_id]["temp_data"]["nickname"] = nickname
    user_states[user_id]["state"] = "awaiting_age"
    bot.send_message(message.chat.id, "Введите ваш возраст (числом):")

@bot.message_handler(func=lambda message: str(message.from_user.id) in user_states and 
                     user_states[str(message.from_user.id)].get("state") == "awaiting_age")
def handle_age(message):
    user_id = str(message.from_user.id)
    try:
        age = int(message.text.strip())
        if age > 99:
            bot.send_message(message.chat.id, "Возраст не может быть больше 99. Введите корректный возраст:")
            return
        if age < 14:
            # Для несовершеннолетних: сохраняем возраст и флаг, затем предлагаем выбор:
            user_states[user_id]["temp_data"]["age"] = age
            user_states[user_id]["temp_data"]["is_minor"] = True
            user_states[user_id]["state"] = "awaiting_minor_choice"
            markup = types.InlineKeyboardMarkup()
            btn_purchase = types.InlineKeyboardButton("Оформить проход за 250₽", callback_data="activate_minor_access")
            btn_skip = types.InlineKeyboardButton("Пропустить", callback_data="skip_minor")
            markup.add(btn_purchase, btn_skip)
            bot.send_message(
                message.chat.id,
                ("Вы зарегистрированы как несовершеннолетний.\n"
                 "В целях безопасности нашего проекта для таких аккаунтов доступны только базовые функции.\n\n"
                 "Чтобы получить полный доступ (игра, маркет, покупки и т.д.), оформите специальный проход за 250₽.\n\n"
                 "Нажмите «Оформить проход за 250₽» для оплаты или «Пропустить», чтобы продолжить регистрацию с ограниченным доступом."),
                reply_markup=markup
            )
            return
    except ValueError:
        bot.send_message(message.chat.id, "Введите корректное число для возраста.")
        return
    # Для пользователей от 14 лет:
    user_states[user_id]["temp_data"]["age"] = age
    user_states[user_id]["state"] = "awaiting_referral"
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    btn_skip = types.KeyboardButton("Пропустить")
    markup.add(btn_skip)
    bot.send_message(
        message.chat.id,
        "Введите никнейм реферала (в формате: Ник Minecraft или @Юзернейм) чтобы пропустить  нажмите 'Пропустить':",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data == "activate_minor_access")
def activate_minor_access(call):
    user_id = str(call.from_user.id)
    data = load_data()
    if user_id not in data["users"]:
        data["users"][user_id] = user_states[user_id]["temp_data"]
        data["users"][user_id].setdefault("balance", 0)
        data["users"][user_id].setdefault("purchases", [])
    user = data["users"][user_id]
    price = 250
    if user.get("balance", 0) < price:
        bot.answer_callback_query(call.id, "Недостаточно средств для оформления прохода.")
        return
    user["balance"] -= price
    user["full_access"] = True  # Теперь у пользователя полный доступ
    user.setdefault("purchases", []).append({
         "item": "Оформление прохода для полного доступа (несовершеннолетний)",
         "price": price,
         "date": datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    })
    save_data(data)
    bot.answer_callback_query(call.id, "Проход успешно оформлен! Теперь у вас полный доступ.")
    # После успешной оплаты переходим к следующему шагу регистрации – запросу реферала
    user_states[user_id]["temp_data"]["full_access"] = True
    user_states[user_id]["state"] = "awaiting_referral"
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    btn_skip = types.KeyboardButton("Пропустить")
    markup.add(btn_skip)
    bot.send_message(
        call.message.chat.id,
        "Введите никнейм реферала (в формате: Ник, @Юзернейм) или нажмите 'Пропустить':",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data == "skip_minor")
def skip_minor(call):
    user_id = str(call.from_user.id)
    bot.answer_callback_query(call.id, "Вы продолжаете регистрацию с ограниченным доступом.")
    user_states[user_id]["state"] = "awaiting_referral"
    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    btn_skip = types.KeyboardButton("Пропустить")
    markup.add(btn_skip)
    bot.send_message(
        call.message.chat.id,
        "Введите никнейм реферала (в формате: Ник, @Юзернейм) или нажмите 'Пропустить':",
        reply_markup=markup
    )

@bot.message_handler(
    func=lambda message: str(message.from_user.id) in user_states
    and user_states[str(message.from_user.id)].get("state") == "awaiting_referral"
)
def handle_referral(message):
    user_id = str(message.from_user.id)
    text    = message.text.strip()
    temp    = user_states[user_id]["temp_data"]

    # уже введённые данные
    user_nick  = temp.get("nickname", "").lower()
    user_uname = message.from_user.username.lower() if message.from_user.username else ""

    # 1) обрабатываем сам ввод реферала
    if text.lower() == "пропустить":
        temp["referral"] = None
    else:
        if "," in text:
            nick_part, uname_part = [p.strip() for p in text.split(",",1)]
            if uname_part.startswith("@"):
                uname_part = uname_part[1:]
            # проверяем, не указал ли сам себя
            if nick_part.lower() == user_nick or uname_part.lower() == user_uname:
                return bot.send_message(
                    message.chat.id,
                    "Нельзя указать себя в качестве реферала! Введите другой ник или 'пропустить'."
                )
            temp["referral"] = {"nickname": nick_part, "telegram_username": uname_part}
        else:
            inp = text.lower()
            if inp == user_nick or inp == user_uname:
                return bot.send_message(
                    message.chat.id,
                    "Нельзя указать себя в качестве реферала! Введите другой ник или 'пропустить'."
                )
            temp["referral"] = text

    bot.send_message(
        message.chat.id,
        "Реферальная информация принята.",
        reply_markup=types.ReplyKeyboardRemove()
    )

    # 2) доп. поля регистрации
    temp["telegram_username"]  = message.from_user.username or ""
    temp["registration_date"]  = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    temp.setdefault("balance", 0)
    temp.setdefault("purchases", [])
    temp.setdefault("promo_codes_used", [])
    temp.setdefault("emojis", {})
    temp.setdefault("xp", 0)  # инициализируем xp
    temp.setdefault("level", 1)

    data = load_data()

    # 3) выдаём xp за реферал, если он есть
    ref = temp.get("referral")
    if ref:
        # новичку +100 xp
        temp["xp"] += 100
        # пригласивший +150 xp
        inviter_id = None
        if isinstance(ref, dict):
            # ищем по telegram_username или никнейму
            for uid, u in data.get("users", {}).items():
                if (u.get("telegram_username","").lower() == ref["telegram_username"].lower()
                    or u.get("nickname","").lower() == ref["nickname"].lower()):
                    inviter_id = uid
                    break
        else:
            # только ник указан
            for uid, u in data.get("users", {}).items():
                if u.get("nickname","").lower() == str(ref).lower():
                    inviter_id = uid
                    break
        if inviter_id:
            inviter = data["users"][inviter_id]
            add_user_xp(inviter_id, 150, data)
            update_xp(inviter_id)
            # можно добавить запись в историю покупок/наград:
            inviter.setdefault("purchases", []).append({
                "item": f"Реферальная награда за {temp['nickname']}",
                "price": 0,
                "date": datetime.now().strftime("%d.%m.%Y %H:%M:%S")
            })

    # 4) сохраняем профиль пользователя
    data.setdefault("users", {})[user_id] = temp

    # 5) далее — проверка возраста / отправка в minors или на модерацию
    if temp.get("is_minor") and not temp.get("full_access"):
        save_data(data)
        bot.send_message(
            message.chat.id,
            "Регистрация завершена с ограниченным доступом. Для полного доступа воспользуйтесь меню.",
            reply_markup=minor_get_main_menu_markup(user_id)
        )
    else:
        # формируем текст заявки
        referral_text = (
            f"{ref['nickname']} (@{ref['telegram_username']})"
            if isinstance(ref, dict) else (ref or "Нет")
        )
        data.setdefault("registration_requests", []).append({
            "user_id":          user_id,
            "nickname":         temp["nickname"],
            "age":              temp["age"],
            "registration_date": temp["registration_date"],
            "referral":         referral_text
        })
        # флаг, чтобы после одобрения открыть гид
        data["users"][user_id]["requires_guide"] = True
        save_data(data)

        # отправляем пользователю кнопку гида
        bot.send_message(
            message.chat.id,
            "Ваша заявка отправлена. Пройдите краткий гид для начала работы:",
            reply_markup=types.InlineKeyboardMarkup().add(
                types.InlineKeyboardButton("📖 Пройти гид", callback_data="open_guide")
            )
        )
        # уведомляем админа
        admin_kb = types.InlineKeyboardMarkup()
        admin_kb.row(
            types.InlineKeyboardButton("Принять ✅", callback_data=f"approve_{user_id}"),
            types.InlineKeyboardButton("Отклонить ❌", callback_data=f"reject_{user_id}")
        )
        bot.send_message(
            ADMIN_ID,
            (
                f"Новая заявка:\n"
                f"Никнейм: {temp['nickname']}\n"
                f"Возраст: {temp['age']}\n"
                f"Юзернейм: {temp['telegram_username']}\n"
                f"Реферал: {referral_text}"
            ),
            reply_markup=admin_kb
        )

    user_states.pop(user_id, None)
    save_data(data)


@bot.callback_query_handler(func=lambda call: call.data.startswith("approve_") or call.data.startswith("reject_"))
def handle_admin_approval(call):
    admin_id = str(call.from_user.id)
    if int(admin_id) != ADMIN_ID:
        bot.answer_callback_query(call.id, "Нет прав.")
        return
    action, user_id = call.data.split("_", 1)
    data = load_data()
    if user_id not in data["users"]:
        bot.answer_callback_query(call.id, "Пользователь не найден.")
        return
    if action == "approve":
        user_data = data["users"][user_id]
        user_data["balance"] = user_data.get("balance", 0)
        user_data["purchases"] = user_data.get("purchases", [])
        ref_nick = user_data.get("referral")
        if isinstance(ref_nick, dict):
            ref_nick_str = ref_nick.get("nickname", "")
        else:
            ref_nick_str = ref_nick
        if ref_nick_str:
            for uid, u in data["users"].items():
                if u.get("nickname", "").lower() == ref_nick_str.lower() and u.get("approved", False):
                    # Новый игрок получает 10₽
                    user_data["balance"] += 10
                    # Реферал получает 15₽
                    u["balance"] = u.get("balance", 0) + 15
                    user_data["purchases"].append({
                        "item": "Бонус за регистрацию (новый игрок)",
                        "price": 10,
                        "date": datetime.now().strftime("%d.%m.%Y %H:%M:%S")
                    })
                    u.setdefault("purchases", []).append({
                        "item": f"Бонус за реферала: {user_data['nickname']}",
                        "price": 15,
                        "date": datetime.now().strftime("%d.%m.%Y %H:%M:%S")
                    })
                    bot.send_message(uid, f"Спасибо, что привели нового игрока {user_data['nickname']}! Вам начислено 15₽ за реферала.")
                    break
        user_data["approved"] = True
        data["registration_requests"] = [req for req in data["registration_requests"] if req["user_id"] != user_id]
        save_data(data)
        welcome_text = (
            "Ваша заявка одобрена! Добро пожаловать в Bedrock Valley! 😊\n\n"
            "📖 Помощь по боту Bedrock Valley\n\n"
            "🔹 Как зайти на сервер:\n1️⃣ Подайте заявку в нашу беседу: https://t.me/+5eOzp1m8MbE5MWEy\n"
            "2️⃣ После принятия напишите свой ник в первый канал #Начало\n"
            "3️⃣ Через некоторое время вас добавят в вайтлист, и вы сможете подключиться по IP и порту из закреплённого сообщения.\n\n"
            "Если возникнут вопросы, обращайтесь к администратору.\n🔗 Подпишитесь: @bedrockvalley"
        )
        bot.send_message(int(user_id), welcome_text, reply_markup=get_main_menu_markup(str(call.from_user.id)))
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
        bot.answer_callback_query(call.id, "Заявка одобрена.")
    elif action == "reject":
        data["users"].pop(user_id, None)
        data["registration_requests"] = [req for req in data["registration_requests"] if req["user_id"] != user_id]
        save_data(data)
        bot.send_message(int(user_id), "Ваша заявка отклонена.")
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
        bot.answer_callback_query(call.id, "Заявка отклонена.")

@bot.message_handler(commands=["help"])
def handle_help(message):
    user_id = str(message.from_user.id)
    data = load_data()
    if user_id in data["users"] and data["users"][user_id].get("approved", False):
        help_text = (
            "📖 Помощь по боту Bedrock Valley\n\n"
            "🔹 Как зайти на сервер:\n1️⃣ Подайте заявку в нашу беседу: https://t.me/+5eOzp1m8MbE5MWEy\n"
            "2️⃣ После принятия напишите свой ник в первый канал #Начало\n"
            "3️⃣ Через некоторое время вас добавят в вайтлист, и вы сможете подключиться по IP и порту из закреплённого сообщения.\n\n"
            "Если возникнут вопросы, обращайтесь к администратору."
        )
        bot.send_message(message.chat.id, help_text)
    else:
        bot.send_message(message.chat.id, "Вы не зарегистрированы. Пожалуйста, зарегистрируйтесь с помощью /start.")

# 📦 Универсальная отправка/редактирование
def send_or_edit_message(bot, call, text, markup):
    try:
        if call.message.photo:
            bot.edit_message_caption(call.message.chat.id, call.message.message_id,
                                     caption=text, reply_markup=markup)
        else:
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                                  reply_markup=markup)
    except Exception:
        bot.send_message(call.message.chat.id, text, reply_markup=markup)

# 📂 Основные тексты
MARKET_WELCOME_TEXT = (
    "🎮 Добро пожаловать в Маркет BedrockValley! 🎮\n"
    "Здесь ты найдёшь всё для выживания, стиля и крутых фишек на сервере!"
)

CUSTOMIZATION_TEXT = "Кастомизация (Эмодзи и Кейсы):"
MARKET_SERVICES_TEXT = "Дополнительные услуги:"

# 🧭 Главное меню
# Префиксы для категорий эмодзи
EMOJI_PREFIXES = {
    "0":       "🪨",   # Каменные
    "1":       "⚙️",  # Железные 
    "2":       "✨",   # Золотые
    "3":       "💎",   # Алмазные
    "4":       "🔥",   # Незеритовые
    "event":   "🚩",  # Ивентовые 
    "special": "🙊",  # Особые 
}

@bot.callback_query_handler(func=lambda call: call.data.startswith("menu_"))
def handle_main_menu(call):
    user_id = str(call.from_user.id)
    data    = load_data()
    user    = data["users"].get(user_id)
    if not user or (not user.get("approved") and not user.get("is_minor")):
        return bot.answer_callback_query(call.id, "Вы не зарегистрированы.")

    if call.data == "menu_profile":
        # ─── Сборка шапки профиля ───────────────────────────────────────
        reg_date   = user.get("registration_date", "").split()[0] or "—"
        bv_status  = "активна" if user.get("bv_plus") else "неактивна"
        role       = user.get("role", "игрок")
        tribe      = user.get("tribe", "Не состоит")
        max_streak = user.get("max_login_streak", user.get("login_streak", 0))
        eyes       = user.get("ender_eyes", 0)

        # ─── Расчёт уровня и прогресса ─────────────────────────────────
        level      = user.get("level", 1)
        xp_current = user.get("xp", 0)
        # вместо 100 + level*25 вызываем функцию-порог
        xp_needed  = xp_to_next(level)
        filled     = int(min(xp_current, xp_needed) / xp_needed * 10)
        bar        = "[" + "🟩" * filled + "⬜" * (10 - filled) + "]"

        # ─── Формируем текст профиля ──────────────────────────────────
        profile_text = (
            "👤 <b>Ваш профиль</b>\n"
            "━━━━━━━━━━━━━━━━\n"
            f"⭐ <b>BV#</b>: {bv_status}\n"
            f"💰 <b>Баланс</b>: {user.get('balance',0)}₽\n"
            f"🏷️ <b>Ник</b>: {user.get('nickname','—')}\n"
            f"🙍 <b>Роль</b>: {role}\n"
            f"🏰 <b>Трайб</b>: {tribe}\n"
            f"🔥 <b>Макс. стрик</b>: {max_streak} дн.\n"
            f"🧿 <b>Око Эндера</b>: {eyes}\n"
            f"📅 <b>Регистрация</b>: {reg_date}\n\n"
            # ─── Используем динамический порог ────────────────────────────
            f"🏆 <b>LVL</b>: {level} ({xp_current}/{xp_needed})\n"
            f"{bar}\n\n"
            f"😊 <b>Эмодзи</b>:\n"
        )

        # ─── Вставляем список эмодзи с префиксами и отступами ─────────
        emojis = ensure_user_emojis(user)
        save_data(data)

        if not any(emojis.values()):
            profile_text += "    — пока пусто\n"
        else:
            for cat_key, items in emojis.items():
                if not items:
                    continue
                icon = EMOJI_PREFIXES.get(cat_key, "")
                if cat_key.isdigit():
                    name     = emoji_details[int(cat_key)]["name"]
                    nums_str = ", ".join(str(n) for n in sorted(items))
                    profile_text += f"    {icon}{name}: {nums_str}\n"
                else:
                    name     = EXTRA_CATEGORIES.get(cat_key, cat_key)
                    vals     = ", ".join(items)
                    profile_text += f"    {icon}{name}: {vals}\n"

        bot.send_message(
            call.message.chat.id,
            profile_text,
            parse_mode="HTML",
            reply_markup=profile_menu_markup()
        )
        return

    # ─── Обработка других menu_*…
    bot.edit_message_text(
        "👋 Добро пожаловать! Выберите раздел:",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="HTML",
        reply_markup=get_main_menu_markup(user_id)
    )


@bot.callback_query_handler(func=lambda call: call.data == "back_main")
def handle_back(call):
    user_id = str(call.from_user.id)
    send_main_menu(user_id, call.message.chat.id)

# 🛍️ Маркет и кастомизация
@bot.callback_query_handler(func=lambda call: call.data in [
    "market_main", "customization", "customization_back", "custom_emoji", "custom_case", "market_services"
])
def handle_market_navigation(call):
    if call.data == "market_main":
        user_id = str(call.from_user.id)
        send_or_edit_message(bot, call, MARKET_WELCOME_TEXT, market_main_markup(user_id))

    elif call.data in ["customization", "customization_back"]:
        send_or_edit_message(bot, call, CUSTOMIZATION_TEXT, customization_markup())

    elif call.data == "custom_emoji":
        show_emoji_info(call.message.chat.id, call.message.message_id, 0)

    elif call.data == "custom_case":
        show_case_info(call.message.chat.id, call.message.message_id, 0)

    elif call.data == "market_services":
        send_or_edit_message(bot, call, MARKET_SERVICES_TEXT, top_services_markup())

# ——— Команда /convert_eyes_xp — единоразово конвертирует 80% Ender Eyes в XP ———
@bot.message_handler(commands=["convert_eyes_xp"])
def admin_convert_eyes_xp(message):
    # Только администратор может запустить эту команду
    if message.from_user.id != ADMIN_ID:
        return bot.send_message(message.chat.id, "❌ Нет прав доступа.")
    
    data = load_data()
    converted_count = 0

    for uid, u in data.get("users", {}).items():
        eyes = u.get("ender_eyes", 0)
        if eyes <= 0:
            continue

        # конвертируем 80% Ender Eyes
        to_convert = int(eyes * 0.8)
        xp_gain    = to_convert * 10

        # уменьшаем Ender Eyes и добавляем XP
        u["ender_eyes"] = eyes - to_convert
        add_user_xp(uid, xp_gain, data)
        update_xp(uid)

        # уведомляем пользователя
        try:
            bot.send_message(
                int(uid),
                "🔄 В связи с изменением баланса и добавлением новых функций бота "
                "была произведена единоразовая конвертация:\n"
                f"• Конвертировано: {to_convert} 🧿 Эндера\n"
                f"• Начислено: {xp_gain} XP"
            )
        except:
            pass

        converted_count += 1

    save_data(data)

    # отчёт админу
    bot.send_message(
        message.chat.id,
        f"✅ Конвертация Ender Eyes завершена.\n"
        f"Обработано пользователей: {converted_count}."
    )


@bot.callback_query_handler(func=lambda call: call.data == "top_services")
def handle_top_services(call):
    try:
        if call.message.photo:
            bot.edit_message_caption(call.message.chat.id, call.message.message_id,
                                     caption="Доп услуги:", reply_markup=top_services_markup())
        else:
            bot.edit_message_text("Доп услуги:", call.message.chat.id, call.message.message_id,
                                  reply_markup=top_services_markup())
    except Exception:
        bot.send_message(call.message.chat.id, "Доп услуги:", reply_markup=top_services_markup())

@bot.callback_query_handler(func=lambda call: call.data.startswith("emoji_prev_") or call.data.startswith("emoji_next_"))
def handle_emoji_navigation(call):
    parts = call.data.split("_")
    direction = parts[1]
    current_index = int(parts[2])
    if direction == "prev" and current_index > 0:
        new_index = current_index - 1
    elif direction == "next" and current_index < len(emoji_details) - 1:
        new_index = current_index + 1
    else:
        new_index = current_index
    show_emoji_info(call.message.chat.id, call.message.message_id, new_index)

@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_emoji_"))
def handle_buy_emoji(call):
    user_id = str(call.from_user.id)
    index = int(call.data.split("_")[-1])
    user_states.setdefault(user_id, {})["buy_emoji_category"] = index
    detail = emoji_details[index]
    msg = bot.send_message(call.message.chat.id,
                           f"Введите номер эмодзи из категории \"{detail['name']}\" (1-{detail['quantity']}):")
    bot.register_next_step_handler(msg, process_emoji_choice)

@bot.callback_query_handler(func=lambda call: call.data.startswith("case_prev_") or call.data.startswith("case_next_"))
def handle_case_navigation(call):
    parts = call.data.split("_")
    direction = parts[1]
    current_index = int(parts[2])
    if direction == "prev" and current_index > 0:
        new_index = current_index - 1
    elif direction == "next" and current_index < len(case_details) - 1:
        new_index = current_index + 1
    else:
        new_index = current_index
    show_case_info(call.message.chat.id, call.message.message_id, new_index)

# ----------------------------
# 1) Покупка конкретного эмодзи
# ----------------------------
@bot.message_handler(func=lambda m: "buy_emoji_category" in user_states.get(str(m.from_user.id), {}))
def process_emoji_choice(message):
    user_id = str(message.from_user.id)
    state   = user_states[user_id]
    cat_idx = state.pop("buy_emoji_category")
    text    = message.text.strip()

    if not text.isdigit():
        state["buy_emoji_category"] = cat_idx
        return bot.send_message(message.chat.id, "Пожалуйста, введите число.")

    choice_num = int(text)
    detail     = emoji_details[cat_idx]
    total      = detail["quantity"]
    if not (1 <= choice_num <= total):
        state["buy_emoji_category"] = cat_idx
        return bot.send_message(
            message.chat.id,
            f"Номер должен быть от 1 до {total}. Попробуйте ещё раз:"
        )

    data   = load_data()
    user   = data["users"].setdefault(user_id, {})
    emojis = ensure_user_emojis(user)

    cat_key = str(cat_idx)
    if choice_num in emojis.get(cat_key, []):
        return bot.send_message(
            message.chat.id,
            f"Эмодзи №{choice_num} уже есть в «{detail['name']}»."
        )

    # вычисляем стоимость с учётом BV#
    cost = detail["price"]
    if user.get("bv_plus") and cat_idx != 4:
        cost = 0

    if user.get("balance", 0) < cost:
        return bot.send_message(message.chat.id, "Недостаточно средств.")

    # списываем средства и выдаём эмодзи
    user["balance"] -= cost
    emojis.setdefault(cat_key, []).append(choice_num)
    user.setdefault("purchases", []).append({
        "item":  f"Куплено {detail['name']} №{choice_num}",
        "price": cost,
        "date":  datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    })

    # начисляем XP только если это не “бесплатная” эмодзи
    if cost > 0:
        add_user_xp(user_id, cost, data)
        update_xp(user_id)
        bot.send_message(
            message.chat.id,
            f"✅ Вы приобрели {detail['name']} №{choice_num} за {cost}₽.\n🥇 +{cost} XP за покупку!"
        )
    else:
        bot.send_message(
            message.chat.id,
            f"✅ Вы приобрели {detail['name']} №{choice_num} бесплатно (BV#).\nXP не начисляется."
        )

    save_data(data)

    save_data(data)
    update_xp(user_id)

    # уведомляем админа
    nickname = user.get("nickname", "Неизвестный")
    bot.send_message(
        ADMIN_ID,
        f"Покупка эмодзи: {nickname} купил {detail['name']} №{choice_num} за {cost}₽."
    )


# ----------------------------
# 2) Покупка и открытие кейса
# ----------------------------
@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_case_"))
def handle_buy_case(call):
    user_id = str(call.from_user.id)
    data    = load_data()
    if user_id not in data["users"]:
        return bot.answer_callback_query(call.id, "Вы не зарегистрированы.")

    index = int(call.data.split("_")[-1])
    case  = case_details[index]
    user  = data["users"][user_id]

    if user.get("balance", 0) < case["price"]:
        return bot.answer_callback_query(call.id, "Недостаточно средств.")

    # списываем деньги
    user["balance"] -= case["price"]
    user.setdefault("purchases", []).append({
        "item":  f"Куплен {case['name']}",
        "price": case["price"],
        "date":  datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    })

    # начисляем XP только если кейс не бесплатный (здесь кейсы всегда платные,
    # но на случай промо или будущих фич)
    if case["price"] > 0:
        add_user_xp(user_id, case["price"], data)
        update_xp(user_id)
        xp_text = f"\n🥇 +{case['price']} XP за покупку кейса!"
    else:
        xp_text = "\nXP не начисляется (промо/бесплатный кейс)."

    save_data(data)

    save_data(data)
    update_xp(user_id)

    bot.answer_callback_query(call.id, "Кейс куплен!")

    # основной результат
    possible = []
    if index == 0: possible = [0,1]
    elif index == 1: possible = [1,2]
    elif index == 2: possible = [3,4]

    if possible:
        cat_guar = choice(possible)
        awarded  = award_emoji(user_id, str(cat_guar))
        main_res = f"{emoji_details[cat_guar]['name']} №{awarded}" if awarded else "нет новых эмодзи"
    else:
        main_res = "—"

    text = f"🎉 Получено: {main_res}.{xp_text}"
    bot.send_message(call.message.chat.id, text)

    # уведомляем админа
    nickname = user.get("nickname", "Неизвестный")
    bot.send_message(
        ADMIN_ID,
        f"Покупка кейса: {nickname} купил {case['name']} за {case['price']}₽. Выпало: {main_res}."
    )


# ------------------- Обработка сервисов (услуги) -------------------
@bot.callback_query_handler(func=lambda call: call.data.startswith("service_"))
def handle_services(call):
    user_id = str(call.from_user.id)
    data = load_data()

    if call.data == "service_unban":
        success, msg = process_purchase(user_id, 500, "Разбан")
        bot.answer_callback_query(call.id, msg)
        if success:
            bot.send_message(call.message.chat.id, "Вы получили услугу разбана.")
            user = data["users"].get(user_id, {})
            nickname = user.get("nickname", "Неизвестный")
            bot.send_message(ADMIN_ID, f"✅ Игрок {nickname} купил разбан.")

    elif call.data == "service_bv":
        bot.answer_callback_query(call.id, "Переход к BV# подписке.")
        try:
            bot.edit_message_text(
                "Переход к BV# подписке:",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=get_main_menu_markup(str(call.from_user.id))
            )
        except Exception as e:
            print(f'[ERROR] Ошибка редактирования сообщения: {e}')
#-------------Общение---------------

def process_player_search(message):
    query = message.text.strip().lower()
    data = load_data()
    found = False

    # Здесь "users" и "banned_users" – словари, а "invalid_registrations" – список.
    all_categories = {
        "users": data.get("users", {}),
        "banned_users": data.get("banned_users", {}),
        "invalid_registrations": data.get("invalid_registrations", [])
    }

    for category, group in all_categories.items():
        # Если группа – словарь, итерируем по её элементам
        if isinstance(group, dict):
            iterator = group.items()
        # Если группа – список, превращаем её в список кортежей (uid будет None)
        elif isinstance(group, list):
            iterator = [(None, user) for user in group]
        else:
            continue

        for uid, user in iterator:
            nickname = user.get("nickname", "").lower()
            username = user.get("telegram_username", "").lower()
            bvtag = str(user.get("bvtag", "")).lower()

            if (query in nickname or query in username or query in bvtag or (uid is not None and query == str(uid))):
                # Добавляем статус в зависимости от категории
                if category == "users":
                    user["status"] = "user"
                elif category == "banned_users":
                    user["status"] = "banned"
                else:
                    user["status"] = "minor"
                # Если uid отсутствует, используем placeholder
                user["user_id"] = uid if uid is not None else "N/A"
                text = render_search_profile(user)
                bot.send_message(message.chat.id, text, parse_mode="HTML")
                found = True
                break
        if found:
            break

    if not found:
        bot.send_message(message.chat.id, "❌ Игрок не найден.")


def render_search_profile(user):
    status     = user.get("status", "user")
    role       = user.get("role", "—")
    nickname   = user.get("nickname", "—")
    bvtag      = user.get("bvtag", "—")
    reg_date   = user.get("registration_date", "—")
    max_streak = user.get("max_login_streak", 0)
    tribe      = user.get("tribe", "—")
    level      = user.get("level", 1)

    if status == "user":
        return (
            f"👤 <b>Профиль: {nickname}</b>\n"
            "━━━━━━━━━━━━━━━━\n"
            f"⭐ <b>BV#:</b> {bvtag}\n"
            f"🏆 <b>LVL:</b> {level} уровень\n"
            f"🏷️ <b>Ник:</b> {nickname}\n"
            f"🎭 <b>Роль:</b> {role}\n"
            f"🏰 <b>Трайб:</b> {tribe}\n"
            f"🔥 <b>Макс. стрик:</b> {max_streak} дней\n"
            f"📅 <b>Регистрация:</b> {reg_date}"
        )
    elif status == "minor":
        return (
            f"🧒 <b>Несовершеннолетний:</b> {nickname}\n"
            "━━━━━━━━━━━━━━━━\n"
            f"⭐ <b>BV#:</b> {bvtag}\n"
            f"🏆 <b>LVL:</b> {level} уровень\n"
            f"📛 <b>Ограничения:</b> до 14 лет\n"
            f"📅 <b>Регистрация:</b> {reg_date}"
        )
    elif status == "banned":
        reason = user.get("ban_reason", "не указана")
        return (
            f"🚫 <b>Забанен:</b> {nickname}\n"
            "━━━━━━━━━━━━━━━━\n"
            f"⭐ <b>BV#:</b> {bvtag}\n"
            f"🏆 <b>LVL:</b> {level} уровень\n"
            f"📛 <b>Причина бана:</b> {reason}\n"
            f"📅 <b>Регистрация:</b> {reg_date}"
        )
    else:
        return f"⚠️ Неизвестный статус для игрока <code>{user.get('user_id','—')}</code>"



@bot.callback_query_handler(func=lambda call: call.data == "search_players")
def search_players_prompt_new(call):
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🎭 Роли", callback_data="show_roles"))
    kb.add(types.InlineKeyboardButton("🔙 Назад", callback_data="community_menu"))
    msg = bot.send_message(
        call.message.chat.id,
        "🔍 Введите никнейм или @username игрока:",
        reply_markup=kb,
    )
    bot.register_next_step_handler(msg, process_player_search)


@bot.callback_query_handler(func=lambda call: call.data == "community_menu")
def community_menu(call):
    user_id = str(call.from_user.id)
    data    = load_data()
    user    = data["users"].get(user_id, {})

    # динамичная кнопка трайба
    if user.get("tribe"):
        btn_tribe = types.InlineKeyboardButton("🏰 Мой трайб", callback_data="tribe_menu")
    else:
        btn_tribe = types.InlineKeyboardButton("🏰 Трайбы", callback_data="tribe_menu")

    btn_players = types.InlineKeyboardButton("👤 Игроки", callback_data="search_players")
    btn_stats   = types.InlineKeyboardButton("📊 Статистика", callback_data="stats_menu")
    btn_law     = types.InlineKeyboardButton("⚖️ Право",       callback_data="law_menu")
    btn_guide   = types.InlineKeyboardButton("📖 Гид",         callback_data="open_guide")

    markup = types.InlineKeyboardMarkup(row_width=3)
    markup.row(btn_tribe)
    markup.row(btn_law, btn_stats, btn_players)
    markup.row(btn_guide)

    # кнопка «Назад» в конец
    btn_back = types.InlineKeyboardButton("🔙 Назад", callback_data="get_main_menu_markup")
    markup.add(btn_back)

    # пробуем отредактировать существующее сообщение
    try:
        bot.edit_message_text(
            "🆕 <b>Сообщество</b>: выбери раздел",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=markup,
            parse_mode="HTML"
        )
    except Exception:
        bot.send_message(
            call.message.chat.id,
            "🆕 <b>Сообщество</b>: выбери раздел",
            reply_markup=markup,
            parse_mode="HTML"
        )


@bot.callback_query_handler(func=lambda call: call.data == "stats_menu")
def stats_menu(call):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("🏆 Топ уровней", callback_data="top_levels"))
    markup.add(types.InlineKeyboardButton("🔥 Топ стриков", callback_data="top_streaks"))
    markup.add(types.InlineKeyboardButton("🛡 Рейтинг трайбов", callback_data="top_tribes"))
    markup.add(types.InlineKeyboardButton("🗓️ Сезоны", callback_data="season_archive"))
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="community_menu"))
    bot.edit_message_text(
        "📊 <b>Рейтинги</b>: выбери категорию",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="HTML",
        reply_markup=markup,
    )


@bot.callback_query_handler(func=lambda call: call.data == "law_menu")
def law_menu(call):
    user_id = str(call.from_user.id)
    data = load_data()
    user = data["users"].get(user_id, {})
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton("📩 Подать дело", callback_data="create_case"))
    row = []
    if user_has_court_access(user):
        row.append(types.InlineKeyboardButton("⚖️ Судебные дела", callback_data="law_cases"))
    row.append(types.InlineKeyboardButton("🗄️ Архив дел", callback_data="law_archive"))
    markup.row(*row)
    markup.add(types.InlineKeyboardButton("💸 Штрафы", callback_data="fines_menu"))
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="community_menu"))
    bot.edit_message_text(
        "⚖️ <b>Право</b>: выбери раздел",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="HTML",
        reply_markup=markup,
    )


@bot.callback_query_handler(func=lambda call: call.data == "create_case")
def start_create_case(call):
    user_id = str(call.from_user.id)
    user_states[user_id] = {"state": "court_title", "temp_data": {}}
    bot.send_message(call.message.chat.id, "Введите название дела:")


@bot.message_handler(func=lambda m: str(m.from_user.id) in user_states and user_states[str(m.from_user.id)].get("state") == "court_title")
def case_set_title(m):
    uid = str(m.from_user.id)
    user_states[uid]["temp_data"]["title"] = m.text.strip()
    user_states[uid]["state"] = "court_brief"
    bot.send_message(m.chat.id, "Краткое описание:")


@bot.message_handler(func=lambda m: str(m.from_user.id) in user_states and user_states[str(m.from_user.id)].get("state") == "court_brief")
def case_set_brief(m):
    uid = str(m.from_user.id)
    user_states[uid]["temp_data"]["brief"] = m.text.strip()
    user_states[uid]["state"] = "court_accused"
    bot.send_message(m.chat.id, "На кого подаёте в суд? Укажите ник или @username:")


@bot.message_handler(func=lambda m: str(m.from_user.id) in user_states and user_states[str(m.from_user.id)].get("state") == "court_accused")
def case_set_accused(m):
    uid = str(m.from_user.id)
    nick = m.text.strip()
    if nick.lower() == "неизвестный":
        user_states[uid]["temp_data"]["accused"] = "Неизвестный"
        user_states[uid]["state"] = "court_description"
        bot.send_message(m.chat.id, "Полное описание дела:")
        return
    data = load_data()
    if not find_user_by_nick_or_username(nick, data):
        bot.send_message(m.chat.id, "Игрок не найден. Введите корректный ник или отправьте 'Неизвестный'.")
        return
    user_states[uid]["temp_data"]["accused"] = nick
    user_states[uid]["state"] = "court_description"
    bot.send_message(m.chat.id, "Полное описание дела:")


@bot.message_handler(func=lambda m: str(m.from_user.id) in user_states and user_states[str(m.from_user.id)].get("state") == "court_description")
def case_set_description(m):
    uid = str(m.from_user.id)
    user_states[uid]["temp_data"]["description"] = m.text.strip()
    user_states[uid]["state"] = "court_screens"
    bot.send_message(m.chat.id, "Пришлите до 4 скриншотов одним сообщением:")


@bot.message_handler(content_types=["photo"], func=lambda m: str(m.from_user.id) in user_states and user_states[str(m.from_user.id)].get("state") == "court_screens")
def case_set_screens(m):
    uid = str(m.from_user.id)
    photos = [p.file_id for p in m.photo]
    user_states[uid]["temp_data"]["screens"] = photos
    user_states[uid]["state"] = "court_compensation"
    bot.send_message(m.chat.id, "Какую компенсацию требуете?")


@bot.message_handler(func=lambda m: str(m.from_user.id) in user_states and user_states[str(m.from_user.id)].get("state") == "court_compensation")
def case_set_comp(m):
    uid = str(m.from_user.id)
    user_states[uid]["temp_data"]["compensation"] = m.text.strip()
    data = user_states[uid]["temp_data"]
    summary = (
        f"Название: {data['title']}\n"
        f"Кратко: {data['brief']}\n"
        f"Обвиняемый: {data['accused']}\n"
        f"Описание: {data['description']}\n"
        f"Компенсация: {data['compensation']}"
    )
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("Создать дело", callback_data="confirm_case"))
    kb.add(types.InlineKeyboardButton("Отмена", callback_data="cancel_case"))
    user_states[uid]["state"] = "court_confirm"
    bot.send_message(m.chat.id, summary, reply_markup=kb)


@bot.callback_query_handler(func=lambda call: call.data in ["confirm_case", "cancel_case"])
def finalize_case(call):
    uid = str(call.from_user.id)
    if call.data == "cancel_case":
        user_states.pop(uid, None)
        bot.edit_message_text("Создание дела отменено.", call.message.chat.id, call.message.message_id)
        return
    info = user_states.pop(uid, {}).get("temp_data", {})
    info["creator_id"] = uid
    case_id = add_case(info)
    bot.edit_message_text(f"✅ Дело №{case_id} создано.", call.message.chat.id, call.message.message_id)


@bot.callback_query_handler(func=lambda call: call.data == "law_cases")
def show_active_cases(call):
    user_id = str(call.from_user.id)
    data = load_data()
    user = data["users"].get(user_id, {})
    if not user_has_court_access(user):
        bot.answer_callback_query(call.id, "Нет доступа")
        return
    cases = load_cases().get("active", [])
    markup = types.InlineKeyboardMarkup()
    for c in cases:
        markup.add(types.InlineKeyboardButton(f"№{c['id']} {c['title']}", callback_data=f"open_case_{c['id']}"))
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="law_menu"))
    text = "Активных дел нет." if not cases else "Выберите дело:" 
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith("open_case_"))
def open_case_details(call):
    case_id = call.data.split("_")[2]
    cases = load_cases()
    case = next((c for c in cases.get("active", []) if c["id"] == case_id), None)
    if not case:
        bot.answer_callback_query(call.id, "Не найдено")
        return
    user_id = str(call.from_user.id)
    data = load_data()
    user = data["users"].get(user_id, {})
    text = (
        f"<b>Дело №{case['id']}</b>\n"
        f"Название: {case['title']}\n"
        f"Кратко: {case['brief']}\n"
        f"Обвиняемый: {case['accused']}\n"
        f"Описание: {case['description']}\n"
        f"Компенсация: {case['compensation']}"
    )
    markup = types.InlineKeyboardMarkup()
    if user.get("role") in ["Президент", "Прокурор"]:
        markup.add(types.InlineKeyboardButton("Вынести вердикт", callback_data=f"verdict_{case_id}"))
        markup.add(types.InlineKeyboardButton("Отклонить", callback_data=f"reject_{case_id}"))
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="law_cases"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)
    if case.get("screens"):
        media = [InputMediaPhoto(p) for p in case["screens"]]
        bot.send_media_group(call.message.chat.id, media)


@bot.callback_query_handler(func=lambda call: call.data.startswith("verdict_"))
def verdict_start(call):
    case_id = call.data.split("_")[1]
    uid = str(call.from_user.id)
    user_states[uid] = {"state": "set_verdict", "case_id": case_id}
    bot.send_message(call.message.chat.id, "Введите текст вердикта:")


@bot.message_handler(func=lambda m: str(m.from_user.id) in user_states and user_states[str(m.from_user.id)].get("state") == "set_verdict")
def verdict_receive(m):
    uid = str(m.from_user.id)
    case_id = user_states[uid]["case_id"]
    verdict = m.text.strip()
    cases = load_cases()
    case = next((c for c in cases.get("active", []) if c["id"] == case_id), None)
    if case:
        case["status"] = "closed"
        case["verdict"] = verdict
        cases["active"] = [c for c in cases["active"] if c["id"] != case_id]
        cases.setdefault("archive", []).append(case)
        save_cases(cases)
    if case and case.get("compensation"):
        user_states[uid] = {"state": "fine_amount", "temp_data": {"case_id": case_id, "target": case["accused"]}}
        bot.send_message(m.chat.id, f"Дело №{case_id} закрыто. Введите сумму штрафа:")
        return
    user_states.pop(uid, None)
    bot.send_message(m.chat.id, f"Дело №{case_id} закрыто вердиктом.")


@bot.callback_query_handler(func=lambda call: call.data.startswith("reject_"))
def reject_case(call):
    case_id = call.data.split("_")[1]
    cases = load_cases()
    case = next((c for c in cases.get("active", []) if c["id"] == case_id), None)
    if case:
        case["status"] = "rejected"
        cases["active"] = [c for c in cases["active"] if c["id"] != case_id]
        cases.setdefault("archive", []).append(case)
        save_cases(cases)
    bot.answer_callback_query(call.id, "Дело отклонено")
    bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)


@bot.callback_query_handler(func=lambda call: call.data == "law_archive")
def law_show_archive(call):
    cases = load_cases().get("archive", [])
    markup = types.InlineKeyboardMarkup()
    for c in cases:
        markup.add(types.InlineKeyboardButton(f"№{c['id']} {c['title']}", callback_data=f"arch_{c['id']}"))
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="law_menu"))
    text = "Архив пуст." if not cases else "Выберите дело:"
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("arch_"))
def law_open_archived(call):
    case_id = call.data.split("_")[1]
    cases = load_cases()
    case = next((c for c in cases.get("archive", []) if c["id"] == case_id), None)
    if not case:
        bot.answer_callback_query(call.id, "Не найдено")
        return
    text = (
        f"<b>Дело №{case['id']}</b>\n"
        f"Название: {case['title']}\n"
        f"Кратко: {case['brief']}\n"
        f"Обвиняемый: {case['accused']}\n"
        f"Описание: {case['description']}\n"
        f"Компенсация: {case['compensation']}\n"
        f"Вердикт: {case.get('verdict','-')}"
    )
    markup = types.InlineKeyboardMarkup().add(
        types.InlineKeyboardButton("🔙 Назад", callback_data="law_archive")
    )
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=markup)
    if case.get("screens"):
        media = [InputMediaPhoto(p) for p in case["screens"]]
        bot.send_media_group(call.message.chat.id, media)


@bot.callback_query_handler(func=lambda call: call.data == "fines_menu")
def fines_menu(call):
    user_id = str(call.from_user.id)
    data = load_data()
    user = data["users"].get(user_id, {})
    if not user_has_fine_access(user):
        bot.answer_callback_query(call.id, "Нет доступа")
        return
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("📄 Посмотреть штрафы", callback_data="fines_list"))
    markup.add(types.InlineKeyboardButton("➕ Создать штраф", callback_data="fine_create"))
    markup.add(types.InlineKeyboardButton("✅ Закрыть штраф", callback_data="fine_close"))
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="law_menu"))
    bot.edit_message_text(
        "💸 <b>Штрафы</b>: выбери действие",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="HTML",
        reply_markup=markup,
    )


@bot.callback_query_handler(func=lambda call: call.data == "fines_list")
def fines_list(call):
    fines = load_fines().get("active", [])
    if not fines:
        text = "Активных штрафов нет."
    else:
        lines = [
            f"#{f['id']} {f.get('target','?')} - {f.get('amount','?')} до {f.get('due','?')} ({f.get('reason','')})"
            for f in fines
        ]
        text = "Активные штрафы:\n" + "\n".join(lines)
    markup = types.InlineKeyboardMarkup().add(
        types.InlineKeyboardButton("🔙 Назад", callback_data="fines_menu")
    )
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == "fine_create")
def fine_create_start(call):
    uid = str(call.from_user.id)
    user_states[uid] = {"state": "fine_target", "temp_data": {}}
    bot.send_message(call.message.chat.id, "На кого выписывается штраф?")


@bot.message_handler(func=lambda m: str(m.from_user.id) in user_states and user_states[str(m.from_user.id)].get("state") == "fine_target")
def fine_set_target(m):
    uid = str(m.from_user.id)
    nick = m.text.strip()
    data = load_data()
    if not find_user_by_nick_or_username(nick, data):
        bot.send_message(m.chat.id, "Игрок не найден. Попробуйте снова:")
        return
    user_states[uid]["temp_data"]["target"] = nick
    user_states[uid]["state"] = "fine_amount"
    bot.send_message(m.chat.id, "Сумма штрафа:")


@bot.message_handler(func=lambda m: str(m.from_user.id) in user_states and user_states[str(m.from_user.id)].get("state") == "fine_amount")
def fine_set_amount(m):
    uid = str(m.from_user.id)
    user_states[uid]["temp_data"]["amount"] = m.text.strip()
    user_states[uid]["state"] = "fine_due"
    bot.send_message(m.chat.id, "Срок оплаты (дд.мм.гггг):")


@bot.message_handler(func=lambda m: str(m.from_user.id) in user_states and user_states[str(m.from_user.id)].get("state") == "fine_due")
def fine_set_due(m):
    uid = str(m.from_user.id)
    due_text = m.text.strip()
    try:
        due_date = datetime.strptime(due_text, "%d.%m.%Y").date()
        if due_date < date.today():
            raise ValueError
    except ValueError:
        bot.send_message(m.chat.id, "Некорректная дата. Укажите будущую дату в формате дд.мм.гггг:")
        return
    user_states[uid]["temp_data"]["due"] = due_text
    user_states[uid]["state"] = "fine_reason"
    bot.send_message(m.chat.id, "Причина штрафа:")


@bot.message_handler(func=lambda m: str(m.from_user.id) in user_states and user_states[str(m.from_user.id)].get("state") == "fine_reason")
def fine_set_reason(m):
    uid = str(m.from_user.id)
    info = user_states.pop(uid, {}).get("temp_data", {})
    info["reason"] = m.text.strip()
    info["creator_id"] = uid
    fine_id = add_fine(info)
    bot.send_message(m.chat.id, f"Штраф #{fine_id} создан.")


@bot.callback_query_handler(func=lambda call: call.data == "fine_close")
def fine_close_start(call):
    uid = str(call.from_user.id)
    user_states[uid] = {"state": "fine_close"}
    bot.send_message(call.message.chat.id, "Введите номер штрафа для закрытия:")


@bot.message_handler(func=lambda m: str(m.from_user.id) in user_states and user_states[str(m.from_user.id)].get("state") == "fine_close")
def fine_close_finish(m):
    uid = str(m.from_user.id)
    fine_id = m.text.strip()
    success = close_fine(fine_id)
    user_states.pop(uid, None)
    if success:
        bot.send_message(m.chat.id, "Штраф закрыт.")
    else:
        bot.send_message(m.chat.id, "Штраф не найден.")


## ---------------- Tribe System (Final Version) ----------------

def get_user_tribe(user_id, data):
    """
    Возвращает (leader_id, tribe) для пользователя,
    если он состоит в трайбе, иначе (None, None).
    """
    user = data["users"].get(user_id)
    if not user or not user.get("tribe"):
        return None, None
    tribe_name = user["tribe"]
    for leader_id, tribe in data.get("tribes", {}).items():
        if tribe["name"] == tribe_name:
            return leader_id, tribe
    return None, None

def recalc_tribe_level(leader_id, data):
    """Гарантирует наличие полей уровня и XP у трайба."""
    tribe = data.get("tribes", {}).get(leader_id)
    if tribe:
        tribe.setdefault("level", 1)
        tribe.setdefault("xp", 0)

def update_user_tribe_level(user_id, data):
    leader_id, tribe = get_user_tribe(user_id, data)
    if tribe:
        recalc_tribe_level(leader_id, data)

def handle_tribe_join_menu(call):
    """
    Обработчик для перехода в меню вступления в трайб.
    В данном примере мы просто вызываем уже определённый обработчик join_tribe_menu.
    """
    join_tribe_menu(call)  # вызовите существующую функцию для обработки заявки на вступление в трайб

def tribe_menu_markup(user):
    """
    Клавиатура главного меню трайбов.
    Если пользователь не состоит в трайбе, показываются две кнопки:
    «Вступить в трайб 📝» и «Создать трайб 🏰».
    Если уже состоит – – «Мой трайб 🏰» и «Список трайбов 🏯».
    """
    markup = types.InlineKeyboardMarkup()
    if not user.get("tribe"):
        btn_join = types.InlineKeyboardButton("Вступить в трайб 📝", callback_data="tribe_join_menu")
        btn_create = types.InlineKeyboardButton("Создать трайб 🏰", callback_data="create_tribe")
        markup.row(btn_join, btn_create)
    else:
        btn_view = types.InlineKeyboardButton("Мой трайб 🏰", callback_data="view_tribe")
        btn_list = types.InlineKeyboardButton("Список трайбов 🏯", callback_data="list_tribes")
        markup.row(btn_view, btn_list)
    btn_back = types.InlineKeyboardButton("Назад 🔙", callback_data="get_main_menu_markup")
    markup.row(btn_back)
    return markup

@bot.message_handler(commands=["tribe"])
def handle_tribe_command(message):
    user_id = str(message.from_user.id)
    update_streak(user_id)
    data = load_data()
    user = data["users"].get(user_id, {})
    kb = tribe_menu_markup(user)
    bot.send_message(message.chat.id, "🏘 Выберите действие:", reply_markup=kb, parse_mode="HTML")

# -------------------- Главный экран трайбов --------------------
@bot.callback_query_handler(func=lambda call: call.data == "tribe_menu")
def tribe_main_menu(call):
    user_id = str(call.from_user.id)
    data = load_data()
    user = data["users"].get(user_id, {})
    
    if user.get("tribe"):
        tribe_btn = types.InlineKeyboardButton("🛡 Мой трайб", callback_data="view_tribe")
    else:
        tribe_btn = types.InlineKeyboardButton("🛡 Вступить в трайб", callback_data="tribe_join_menu")
    
    keyboard = types.InlineKeyboardMarkup()
    keyboard.row(tribe_btn)
    keyboard.row(
        types.InlineKeyboardButton("📜 Все трайбы", callback_data="list_tribes")
    )
    keyboard.row(
        types.InlineKeyboardButton("🔙 Главное меню", callback_data="get_main_menu_markup")
    )
    
    text = "🏘 <b>Меню трайбов</b>\nВыберите нужное действие:"
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=keyboard, parse_mode="HTML")
    except Exception as e:
        print(f"[ERROR] Editing tribe menu: {e}")
        bot.send_message(call.message.chat.id, text, reply_markup=keyboard, parse_mode="HTML")


# -------------------- Вступление в трайб --------------------
@bot.callback_query_handler(func=lambda call: call.data == "tribe_join_menu")
def join_tribe_menu(call):
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("📩 Подать заявку на вступление", callback_data="submit_tribe_request"))
    kb.add(types.InlineKeyboardButton("🏰 Создать трайб", callback_data="create_tribe"))
    kb.add(types.InlineKeyboardButton("🔙 Назад", callback_data="tribe_menu"))
    bot.edit_message_text("Выберите действие:", call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data == "submit_tribe_request")
def tribe_join_request(call):
    msg = bot.send_message(call.message.chat.id,
        "Введите <b>[ID]</b> трайба, в который хотите вступить (указан рядом с названием):",
        parse_mode="HTML")
    bot.register_next_step_handler(msg, process_join_request)

def process_join_request(message):
    user_id = str(message.from_user.id)
    req_id = message.text.strip().upper()
    data = load_data()
    target_tribe = None
    target_leader = None
    for leader_id, tribe in data.get("tribes", {}).items():
        if tribe["id"] == req_id:
            target_tribe = tribe
            target_leader = leader_id
            break
    if not target_tribe:
        bot.send_message(message.chat.id, "❌ Трайб с таким [ID] не найден.")
        return
    if data["users"].get(user_id, {}).get("tribe"):
        bot.send_message(message.chat.id, "❌ Вы уже состоите в трайбе.")
        return
    # Проверяем, не подал ли заявку уже пользователь (без KeyError)
    for tribe in data.get("tribes", {}).values():
        for req in tribe.get("join_requests", []):
            if req.get("user_id") == user_id:
                bot.send_message(message.chat.id, "❗ Вы уже подали заявку.")
                return
    if len(target_tribe.get("members", [])) >= target_tribe.get("max_members", 10):
        bot.send_message(message.chat.id, "❌ В этом трайбе достигнут максимум участников.")
        return
    user_record = data["users"].get(user_id, {})
    join_req = {
        "user_id": user_id,
        "nickname": user_record.get("nickname", ""),
        "telegram_username": user_record.get("telegram_username", ""),
        "registration_date": user_record.get("registration_date", "")
    }
    target_tribe.setdefault("join_requests", []).append(join_req)
    save_data(data)
    req_text = (
        f"<b>📩 Заявка в трайб</b>\n"
        f"👤 Ник: {join_req['nickname']}\n"
        f"🔗 Telegram: @{join_req['telegram_username']}\n"
        f"📅 Дата: {join_req['registration_date']}"
    )
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton("✅ Принять", callback_data=f"join_accept_{user_id}_{target_leader}"),
        types.InlineKeyboardButton("❌ Отклонить", callback_data=f"join_reject_{user_id}_{target_leader}")
    )
    bot.send_message(target_leader, req_text, reply_markup=kb, parse_mode="HTML")
    bot.send_message(message.chat.id, "✅ Ваша заявка отправлена Главе трайба.")

# -------------------- Создание трайба --------------------
@bot.callback_query_handler(func=lambda call: call.data == "create_tribe")
def create_tribe_start(call):
    user_id = str(call.from_user.id)
    data = load_data()
    if data["users"].get(user_id, {}).get("tribe"):
        bot.answer_callback_query(call.id, "Вы уже состоите в трайбе.")
        return
    user_states[user_id] = {"state": "awaiting_tribe_name", "temp_data": {}}
    bot.send_message(call.message.chat.id, "🛠 <b>Создание трайба</b>\nВведите название трайба (до 20 символов):", parse_mode="HTML")

@bot.message_handler(func=lambda m: str(m.from_user.id) in user_states and user_states[str(m.from_user.id)].get("state") == "awaiting_tribe_name")
def tribe_name_handler(m):
    user_id = str(m.from_user.id)
    tribe_name = m.text.strip()
    if len(tribe_name) > 20:
        bot.send_message(m.chat.id, "❗ Название слишком длинное. Введите до 20 символов:")
        return
    user_states[user_id]["temp_data"]["tribe_name"] = tribe_name
    user_states[user_id]["state"] = "awaiting_tribe_id"
    bot.send_message(m.chat.id, "Введите идентификатор трайба (ровно 3 символа, например, BVC):")

@bot.message_handler(func=lambda m: str(m.from_user.id) in user_states and user_states[str(m.from_user.id)].get("state") == "awaiting_tribe_id")
def tribe_id_handler(m):
    user_id = str(m.from_user.id)
    tribe_id = m.text.strip()
    if len(tribe_id) != 3:
        bot.send_message(m.chat.id, "❗ Идентификатор должен быть ровно 3 символа. Попробуйте снова:")
        return
    user_states[user_id]["temp_data"]["tribe_id"] = tribe_id.upper()
    user_states[user_id]["state"] = "awaiting_tribe_desc"
    bot.send_message(m.chat.id, "Введите описание трайба (до 50 символов):")

@bot.message_handler(func=lambda m: str(m.from_user.id) in user_states and user_states[str(m.from_user.id)].get("state") == "awaiting_tribe_desc")
def tribe_desc_handler(m):
    user_id = str(m.from_user.id)
    desc = m.text.strip()
    if len(desc) > 50:
        bot.send_message(m.chat.id, "❗ Описание слишком длинное. Введите до 50 символов:")
        return
    user_states[user_id]["temp_data"]["tribe_desc"] = desc
    user_states[user_id]["state"] = "awaiting_tribe_chat"
    bot.send_message(m.chat.id, "Введите ссылку на беседу трайба:")

@bot.message_handler(func=lambda m: str(m.from_user.id) in user_states and user_states[str(m.from_user.id)].get("state") == "awaiting_tribe_chat")
def tribe_chat_handler(m):
    user_id = str(m.from_user.id)
    chat_link = m.text.strip()
    temp = user_states[user_id]["temp_data"]
    temp["tribe_chat"] = chat_link
    confirmation = (
        f"Проверьте данные трайба:\n"
        f"🛡 Название: {temp['tribe_name']}\n"
        f"🔢 ID: {temp['tribe_id']}\n"
        f"📝 Описание: {temp['tribe_desc']}\n"
        f"💬 Ссылка: {temp['tribe_chat']}\n\n"
        "Нажмите ✅ для создания или ❌ для отмены."
    )
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("✅ Создать", callback_data="confirm_create_tribe"))
    kb.add(types.InlineKeyboardButton("❌ Отмена", callback_data="cancel_create_tribe"))
    bot.send_message(m.chat.id, confirmation, reply_markup=kb, parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data in ["confirm_create_tribe", "cancel_create_tribe"])
def tribe_create_confirm(call):
    user_id = str(call.from_user.id)
    if call.data == "cancel_create_tribe":
        user_states.pop(user_id, None)
        bot.edit_message_text("❌ Создание трайба отменено.", call.message.chat.id, call.message.message_id)
        return
    data = load_data()
    user = data["users"].get(user_id, {})
    cost = 0  # Создание бесплатно
    if user.get("balance", 0) < cost:
        bot.answer_callback_query(call.id, "❗ Недостаточно средств для создания трайба.")
        return
    user["balance"] -= cost
    temp = user_states[user_id]["temp_data"]
    tribe = {
        "name": temp["tribe_name"],
        "id": temp["tribe_id"],
        "desc": temp["tribe_desc"],
        "last_desc_change": datetime.now().strftime("%Y-%m-%d"),
        "date_created": datetime.now().strftime("%d.%m.%Y"),
        "chat_link": temp["tribe_chat"],
        "leader": user_id,
        "members": [{
            "user_id": user_id,
            "nickname": user.get("nickname", ""),
            "telegram_username": user.get("telegram_username", ""),
            "role": "Глава"
        }],
        "max_members": 10,
        "join_requests": [],
        "level": 1,
        "xp": 0
    }
    data.setdefault("tribes", {})
    data["tribes"][user_id] = tribe
    user["tribe"] = tribe["name"]
    save_data(data)
    user_states.pop(user_id, None)
    bot.edit_message_text(f"🎉 Трайб <b>{tribe['name']}</b> успешно создан!", call.message.chat.id, call.message.message_id, parse_mode="HTML")

# -------------------- Список трайбов с навигацией --------------------
@bot.callback_query_handler(func=lambda call: call.data == "list_tribes")
def tribe_list(call):
    call.data = "list_tribes_page_0"
    handle_tribes_page_safe(call)

@bot.callback_query_handler(func=lambda call: call.data.startswith("list_tribes_page_"))
def handle_tribes_page(call):
    handle_tribes_page_safe(call)

def handle_tribes_page_safe(call):
    try:
        page = int(call.data.split("_")[-1])
    except Exception:
        page = 0

    data   = load_data()
    tribes = list(data.get("tribes", {}).values())
    random.shuffle(tribes)
    per_page    = 5
    total_pages = (len(tribes) + per_page - 1)//per_page

    if not tribes:
        bot.edit_message_text("😔 Нет созданных трайбов.", call.message.chat.id, call.message.message_id)
        return

    if page < 0 or page >= total_pages:
        bot.answer_callback_query(call.id, "❌ Нет такой страницы.")
        return

    start = page*per_page
    end   = start+per_page
    current = tribes[start:end]

    text = "📜 <b>Список трайбов:</b>\n━━━━━━━━━━━━━━━━\n" \
           "Укажите <b>[ID]</b> нужного трайба после нажатия кнопки.\n\n"
    for i, tribe in enumerate(current, start=start+1):
        level = tribe.get('level', 1)
        text += (
            f"{i}. <b>{tribe['name']}</b> [{tribe['id']}]\n"
            f"   👥 {len(tribe['members'])}/{tribe.get('max_members', 10)}\n"
            f"   📅 {tribe['date_created']}\n"
            f"   🏅 LVL {level}\n"
            f"   📝 {tribe['desc'][:100]}...\n\n"
        )

    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("📑 Подать заявку", callback_data="submit_tribe_request"))
    nav = []
    if page > 0:
        nav.append(types.InlineKeyboardButton("⬅️ Назад", callback_data=f"list_tribes_page_{page-1}"))
    if page < total_pages - 1:
        nav.append(types.InlineKeyboardButton("➡️ Далее", callback_data=f"list_tribes_page_{page+1}"))
    if nav:
        kb.row(*nav)
    kb.add(types.InlineKeyboardButton("🔙 В меню трайбов", callback_data="community_tribes"))

    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="HTML", reply_markup=kb)


# ===== Обработчик команды «трайбы» через текст сообщения
@bot.message_handler(func=lambda m: m.text and m.text.lower() in ["трайбы", "/трайбы", "список трайбов", "все трайбы"])
def handle_tribes_list(m):
    chat_id = m.chat.id
    thread_id = getattr(m, "message_thread_id", None)

    data = load_data()
    tribes = list(data.get("tribes", {}).values())
    if not tribes:
        # Если нет ни одного трайба
        bot.send_message(
            chat_id,
            "😔 Нет созданных трайбов.",
            message_thread_id=thread_id
        )
        return

    # Перемешиваем порядок трайбов
    random.shuffle(tribes)

    # Формируем текст
    output = ["📜 <b>Список трайбов:</b>\n━━━━━━━━━━━━━━━━"]
    for tribe in tribes:
        name    = tribe.get("name", "Без названия")
        tid     = tribe.get("id", "???")
        members = len(tribe.get("members", []))
        desc    = tribe.get("desc", "Без описания")
        created = tribe.get("date_created", "—")
        level = tribe.get('level', 1)
        output.append(
            f"<b>{name}</b> [{tid}]\n"
            f"👥 {members}/10 | 📅 {created} | 🏅 LVL {level}\n"
            f"📝 {desc[:80]}..."
        )
    text = "\n\n".join(output)

    # Отправляем пользователю
    bot.send_message(
        chat_id,
        text,
        parse_mode="HTML",
        message_thread_id=thread_id
    )

# ─────────────────────────────────────────────────────────────
#               🗂 EMOJI PACKS & DETAILS BLOCK (ИТОГ)
# ─────────────────────────────────────────────────────────────


# 1) Подробности по каждому базовому паку
emoji_details = [
    {"name": "Каменные эмодзи",   "price": 30,  "quantity": 14, "image": "stone.png",
     "description": "Базовые эмодзи, прочные как камень 🪨."},
    {"name": "Железные эмодзи",    "price": 50,  "quantity": 17, "image": "iron.png",
     "description": "Надёжные эмодзи, как железный блок ⚙️."},
    {"name": "Золотые эмодзи",     "price": 85,  "quantity": 21, "image": "gold.png",
     "description": "Сияющие эмодзи, как золотой блеск ✨."},
    {"name": "Алмазные эмодзи",    "price": 115, "quantity": 28, "image": "diamond.png",
     "description": "Редкие и роскошные эмодзи, как алмазы 💎."},
    {"name": "Незеритовые эмодзи", "price": 159, "quantity": 27, "image": "nether.png",
     "description": "Эмодзи высшего класса, уникальные и эксклюзивные 🔥."},
]

# 2) Дополнительные (именованные) категории
EXTRA_CATEGORIES = {
    "event":   "Ивентовые эмодзи",
    "special": "Особые эмодзи",
}

# 3) Ключи всех категорий — цифровые 0–4 и event/special
EMOJI_CATEGORY_KEYS = [str(i) for i in range(len(emoji_details))] + list(EXTRA_CATEGORIES.keys())

# 4) Инициализация / миграция старого хранилища
def ensure_user_emojis(user):
    # 1) Миграция старого поля
    if "emoji_packs" in user and "emojis" not in user:
        user["emojis"] = user.pop("emoji_packs")

    # 2) Если ещё нет — создаём пустой словарь со всеми категориями
    if "emojis" not in user:
        user["emojis"] = {key: [] for key in EMOJI_CATEGORY_KEYS}
    else:
        # 3) Дополняем недостающие категории (event, special и т.д.)
        for key in EMOJI_CATEGORY_KEYS:
            user["emojis"].setdefault(key, [])

    return user["emojis"]

# 5) Функция выдачи случайной эмодзи из цифровых паков
def award_emoji(user_id: str, cat_key: str):

    data = load_data()
    user = data["users"].setdefault(user_id, {})
    packs = ensure_user_emojis(user)

    # Цифровые пакеты
    if cat_key.isdigit():
        detail = emoji_details[int(cat_key)]
        all_nums = set(range(1, detail["quantity"] + 1))
        owned    = set(packs[cat_key])
        available = list(all_nums - owned)
        if not available:
            return None
        chosen = choice(available)
        packs[cat_key].append(chosen)
        save_data(data)
        return chosen

    # Для именованных пока нет автоматической выдачи
    return None

# -------------------- Обработка заявки (для Главы) --------------------
@bot.callback_query_handler(func=lambda call: call.data.startswith("join_accept_") or call.data.startswith("join_reject_"))
def handle_join_response(call):
    parts = call.data.split("_")
    action = "_".join(parts[:2])
    applicant_id = parts[2]
    leader_id = parts[3]
    data = load_data()
    tribe = data["tribes"].get(leader_id)
    if not tribe:
        bot.answer_callback_query(call.id, "❌ Трайб не найден.")
        return
    req_index = None
    for idx, req in enumerate(tribe.get("join_requests", [])):
        if req["user_id"] == applicant_id:
            req_index = idx
            break
    if req_index is None:
        bot.answer_callback_query(call.id, "❌ Заявка не найдена.")
        return
    if action == "join_accept":
        applicant = tribe["join_requests"].pop(req_index)
        tribe["members"].append({
            "user_id": applicant["user_id"],
            "nickname": applicant["nickname"],
            "telegram_username": applicant["telegram_username"],
            "role": "Участник"
        })
        if applicant["user_id"] in data["users"]:
            user = data["users"][applicant["user_id"]]
            user["tribe"] = tribe["name"]
            # 🎁 Выдаём бонус за вступление (раз в 3 дня)
            process_tribe_login_rewards(applicant["user_id"])
        recalc_tribe_level(leader_id, data)
        save_data(data)
        bot.send_message(leader_id, f"✅ Заявка от {applicant['nickname']} принята.")
        bot.send_message(applicant["user_id"], f"🎉 Ваша заявка на вступление в трайб '{tribe['name']}' принята!")
    else:
        tribe["join_requests"].pop(req_index)
        save_data(data)
        bot.send_message(leader_id, "❌ Заявка отклонена.")
        bot.send_message(applicant_id, f"Ваша заявка на вступление в трайб '{tribe['name']}' отклонена.")
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data == "community_tribes")
def handle_community_tribes(call):
    tribe_main_menu(call)

# -------------------- Выход из трайба (для не-Лидера) --------------------
@bot.callback_query_handler(func=lambda call: call.data == "leave_tribe")
def leave_tribe(call):
    user_id = str(call.from_user.id)
    data = load_data()
    found = None
    for leader_id, tribe in data.get("tribes", {}).items():
        for member in tribe["members"]:
            if member["user_id"] == user_id:
                found = (leader_id, tribe)
                break
        if found:
            break
    if not found:
        bot.answer_callback_query(call.id, "❌ Вы не состоите в трайбе.")
        return
    leader_id, tribe = found
    if leader_id == user_id:
        bot.answer_callback_query(call.id, "❌ Как Глава, вы не можете покинуть трайб без распуска.")
        return
    tribe["members"] = [m for m in tribe["members"] if m["user_id"] != user_id]
    if user_id in data["users"]:
        data["users"][user_id].pop("tribe", None)
    recalc_tribe_level(leader_id, data)
    save_data(data)
    bot.answer_callback_query(call.id, "✅ Вы покинули трайб.")
    bot.send_message(call.message.chat.id, f"Вы успешно покинули трайб '{tribe['name']}'.")
    tribe_main_menu(call)

# -------------------- Функция распуска трайба --------------------
def disband_tribe(leader_id, data):
    tribe = data["tribes"].pop(leader_id, None)
    if tribe:
        for member in tribe["members"]:
            uid = member["user_id"]
            if uid in data["users"]:
                data["users"][uid].pop("tribe", None)
        save_data(data)

@bot.callback_query_handler(func=lambda call: call.data == "disband_tribe")
def disband_tribe_handler(call):
    user_id = str(call.from_user.id)
    data = load_data()
    leader_id, tribe = get_user_tribe(user_id, data)
    if not tribe:
        bot.answer_callback_query(call.id, "❗ Вы не состоите в трайбе.")
        return
    if leader_id != user_id:
        bot.answer_callback_query(call.id, "❗ Только Глава может распустить трайб.")
        return
    if len(tribe["members"]) == 1:
        disband_tribe(user_id, data)
        bot.edit_message_text("✅ Ваш трайб успешно распущен.", call.message.chat.id, call.message.message_id)
    else:
        bot.answer_callback_query(call.id, "Распуск возможен только, если вы единственный участник или по итогам голосования.")

# -------------------- Управление трайбом: Редактирование и Назначение --------------------
def clan_edit_markup():
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton("Переименовать", callback_data="edit_tribe_name"),
        types.InlineKeyboardButton("Изменить описание", callback_data="edit_tribe_desc")
    )
    kb.row(
        types.InlineKeyboardButton("Изменить ID (50₽)", callback_data="edit_tribe_id"),
        types.InlineKeyboardButton("Назначить помощника", callback_data="assign_tribe_helper")
    )
    kb.row(types.InlineKeyboardButton("🔙 Назад", callback_data="view_tribe"))
    return kb

def clan_management_markup():
    kb = types.InlineKeyboardMarkup()
    kb.row(types.InlineKeyboardButton("⚙️ Редактировать", callback_data="edit_tribe"))
    kb.row(
        types.InlineKeyboardButton("Кикнуть участника", callback_data="kick_tribe_member"),
        types.InlineKeyboardButton("Создать объявление", callback_data="create_tribe_announcement")
    )
    kb.row(types.InlineKeyboardButton("🔙 Назад", callback_data="view_tribe"))
    return kb

@bot.callback_query_handler(func=lambda call: call.data == "edit_tribe")
def edit_tribe_menu(call):
    kb = clan_edit_markup()
    try:
        bot.edit_message_text("⚙️ Редактирование трайба:", call.message.chat.id, call.message.message_id, reply_markup=kb)
    except Exception as e:
        print(f"[ERROR] Редактирование трайба: {e}")

def create_tribe_announcement(leader_id: str, announcement_text: str):
    """
    Рассылает объявление всем участникам трайба, 
    у которых включены уведомления 'От трайба' (FLAG_MAP['tribe']).
    """
    data = load_data()
    tribe = data["tribes"].get(leader_id)
    if not tribe:
        return  # нет такого трайба

    # Собираем список user_id, которым слать
    recipients = []
    for member in tribe.get("members", []):
        uid = member["user_id"]
        user = data["users"].get(uid, {})
        # проверяем бит 'tribe'
        if user.get("notif_flags", 0) & FLAG_MAP["tribe"]:
            recipients.append(uid)

    # Формируем текст объявления
    title = tribe.get("name", "Ваш трайб")
    msg = (
        f"🏰 <b>Объявление от трайба «{title}»</b>\n\n"
        f"{announcement_text}"
    )

    # Шлём каждому подписчику
    delivered = 0
    for uid in recipients:
        try:
            bot.send_message(uid, msg, parse_mode="HTML")
            delivered += 1
        except Exception as e:
            print(f"[ERROR] Не удалось отправить tribe-уведомление {uid}: {e}")

    return delivered

@bot.callback_query_handler(func=lambda c: c.data == "admin_tribe_announce")
def admin_tribe_announce(call):
    leader_id = str(call.from_user.id)
    msg = bot.send_message(call.message.chat.id, "Введите текст объявления для вашего трайба:")
    bot.register_next_step_handler(msg, lambda m: _send_tribe_announce(leader_id, m.text, call))
    
def _send_tribe_announce(leader_id, text, call):
    delivered = create_tribe_announcement(leader_id, text)
    bot.send_message(
        call.message.chat.id,
        f"✅ Объявление отправлено {delivered} участникам."
    )

@bot.callback_query_handler(func=lambda c: c.data == "create_tribe_announcement")
def cb_create_tribe_announcement(call):
    leader_id = str(call.from_user.id)
    msg = bot.send_message(call.message.chat.id, "Введите текст объявления для вашего трайба:")
    bot.register_next_step_handler(msg, lambda m: _send_tribe_announce(leader_id, m.text, call))

@bot.callback_query_handler(func=lambda call: call.data == "manage_tribe")
def manage_tribe_menu(call):
    kb = clan_management_markup()
    try:
        bot.edit_message_text("👥 Управление трайбом:", call.message.chat.id, call.message.message_id, reply_markup=kb)
    except Exception as e:
        print(f"[ERROR] Управление трайбом: {e}")

@bot.callback_query_handler(func=lambda call: call.data == "edit_tribe_desc")
def edit_tribe_desc_prompt(call):
    msg = bot.send_message(call.message.chat.id, "Введите новое описание трайба (до 50 символов):")
    bot.register_next_step_handler(msg, process_edit_tribe_desc)

def process_edit_tribe_desc(message):
    user_id = str(message.from_user.id)
    new_desc = message.text.strip()
    if len(new_desc) > 50:
        bot.send_message(message.chat.id, "❗ Описание слишком длинное. Попробуйте снова:")
        return
    data = load_data()
    tribe = data["tribes"].get(user_id)
    if not tribe:
        bot.send_message(message.chat.id, "❌ Трайб не найден.")
        return
    last_change = tribe.get("last_desc_change")
    if last_change:
        try:
            last_date = datetime.strptime(last_change, "%Y-%m-%d")
            if (datetime.now() - last_date).days < 3:
                bot.send_message(message.chat.id, "❗ Описание можно менять раз в три дня.")
                return
        except Exception:
            pass
    tribe["desc"] = new_desc
    tribe["last_desc_change"] = datetime.now().strftime("%Y-%m-%d")
    save_data(data)
    bot.send_message(message.chat.id, "✅ Описание трайба обновлено.", reply_markup=clan_edit_markup())

@bot.callback_query_handler(func=lambda call: call.data == "edit_tribe_name")
def edit_tribe_name_prompt(call):
    msg = bot.send_message(call.message.chat.id, "Введите новое название трайба (до 20 символов):")
    bot.register_next_step_handler(msg, process_edit_tribe_name)

def process_edit_tribe_name(message):
    user_id = str(message.from_user.id)
    new_name = message.text.strip()
    if len(new_name) > 20:
        bot.send_message(message.chat.id, "❗ Название слишком длинное. Попробуйте снова:")
        return
    data = load_data()
    tribe = data["tribes"].get(user_id)
    if not tribe:
        bot.send_message(message.chat.id, "❌ Трайб не найден.")
        return
    user = data["users"].get(user_id, {})
    cost = 0 if user.get("bv_plus") else 250
    if user.get("balance", 0) < cost:
        bot.send_message(message.chat.id, "❗ Недостаточно монет для переименования.")
        return
    user["balance"] -= cost
    tribe["name"] = new_name
    for member in tribe.get("members", []):
        uid = member.get("user_id")
        if uid in data.get("users", {}):
            data["users"][uid]["tribe"] = new_name
    save_data(data)
    bot.send_message(
        message.chat.id,
        "✅ Название трайба обновлено." + (f" Списано {cost} монет." if cost else ""),
        reply_markup=clan_edit_markup(),
    )

@bot.callback_query_handler(func=lambda call: call.data == "edit_tribe_id")
def edit_tribe_id_prompt(call):
    user_id = str(call.from_user.id)
    data = load_data()
    user = data["users"].get(user_id, {})
    cost = 0 if user.get("bv_plus") else 50
    msg = bot.send_message(call.message.chat.id, f"Введите новый ID трайба (3 символа). Стоимость: {cost}₽:")
    bot.register_next_step_handler(msg, process_edit_tribe_id)

def process_edit_tribe_id(message):
    user_id = str(message.from_user.id)
    new_id = message.text.strip()
    if len(new_id) != 3:
        bot.send_message(message.chat.id, "❗ ID должен быть ровно 3 символа. Попробуйте снова:")
        return
    data = load_data()
    tribe = data["tribes"].get(user_id)
    if not tribe:
        bot.send_message(message.chat.id, "❌ Трайб не найден.")
        return
    user = data["users"].get(user_id, {})
    cost = 0 if user.get("bv_plus") else 50
    if user.get("balance", 0) < cost:
        bot.send_message(message.chat.id, "❗ Недостаточно средств для изменения ID.")
        return
    user["balance"] -= cost
    tribe["id"] = new_id.upper()
    save_data(data)
    bot.send_message(message.chat.id, "✅ ID трайба изменён.", reply_markup=clan_edit_markup())

@bot.callback_query_handler(func=lambda call: call.data == "assign_tribe_helper")
def assign_helper_prompt(call):
    msg = bot.send_message(call.message.chat.id, "Введите никнейм или @username участника для назначения помощником:")
    bot.register_next_step_handler(msg, process_assign_helper)

def process_assign_helper(message):
    user_id = str(message.from_user.id)
    query = message.text.strip().lower()
    data = load_data()
    tribe = data["tribes"].get(user_id)
    if not tribe:
        bot.send_message(message.chat.id, "❌ Трайб не найден.")
        return
    found = None
    for member in tribe["members"]:
        if query == member.get("nickname", "").lower() or query == member.get("telegram_username", "").lower() or query in member.get("nickname", "").lower():
            found = member
            break
    if not found:
        bot.send_message(message.chat.id, "❗ Участник не найден в вашем трайбе.")
        return
    found["role"] = "Помощник"
    save_data(data)
    bot.send_message(message.chat.id, f"✅ {found['nickname']} назначен(а) помощником.", reply_markup=clan_edit_markup())

# -------------------- Обработчик "Мой трайб" --------------------
@bot.callback_query_handler(func=lambda call: call.data == "view_tribe")
def view_tribe(call):
    user_id = str(call.from_user.id)
    data = load_data()
    leader_id, tribe = get_user_tribe(user_id, data)
    if not tribe:
        bot.answer_callback_query(call.id, "Вы не состоите в трайбе.")
        return
    members_info = ""
    for member in tribe["members"]:
        uid = member["user_id"]
        role = member.get("role", "")
        role_emoji = "👑" if role == "Глава" else ("✍️" if role == "Помощник" else "")
        user_data = data["users"].get(uid, {})
        star = "⭐" if user_data.get("bv_plus") else ""
        username = member.get("telegram_username", "")
        if username:
            members_info += f"{member['nickname']} {role_emoji}{star} (@{username})\n"
        else:
            members_info += f"{member['nickname']} {role_emoji}{star}\n"
    level = tribe.get("level", 1)
    xp_cur = tribe.get("xp", 0)
    xp_needed = tribe_xp_to_next(level)
    filled = int(min(xp_cur, xp_needed) / xp_needed * 10)
    bar = "[" + "🟦" * filled + "⬜" * (10 - filled) + "]"
    xp_info = f"({xp_cur}/{xp_needed})"

    text = (
        f"🏰 <b>Ваш трайб</b>\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"📛 <b>Название и ID:</b> {tribe['name']} [{tribe['id']}]\n"
        f"📝 <b>Описание:</b> {tribe['desc']}\n"
        f"📅 <b>Дата создания:</b> {tribe['date_created']}\n"
        f"🏆 <b>LVL:</b> {level} {xp_info}\n"
        f"{bar}\n"
        f"👥 <b>Участников:</b> {len(tribe['members'])}/10\n\n"
        f"👤 <b>Состав:</b>\n{members_info}\n"
        f"🔗 <b>Беседа:</b> {tribe['chat_link'] or '—'}"
    )
    if tribe["leader"] == user_id:
        kb = types.InlineKeyboardMarkup()
        kb.row(
            types.InlineKeyboardButton("⚙️ Управлять", callback_data="manage_tribe"),
            types.InlineKeyboardButton("💥 Распустить", callback_data="disband_tribe")
        )
        kb.row(
            types.InlineKeyboardButton("📜 Список трайбов", callback_data="list_tribes"),
            types.InlineKeyboardButton("🔙 Назад", callback_data="tribe_menu")
        )
    else:
        kb = types.InlineKeyboardMarkup()
        kb.row(
            types.InlineKeyboardButton("🚪 Покинуть", callback_data="leave_tribe"),
            types.InlineKeyboardButton("📜 Список трайбов", callback_data="list_tribes")
        )
        kb.row(types.InlineKeyboardButton("🔙 Назад", callback_data="tribe_menu"))
    try:
        bot.send_message(call.message.chat.id, text, reply_markup=kb, parse_mode="HTML")
    except Exception as e:
        print(f"[ERROR] При отображении трайба: {e}")
        bot.send_message(call.message.chat.id, text, reply_markup=kb, parse_mode="HTML")

#----------------Промокоды-------------------


def process_promo_code(message):
    user_id = str(message.from_user.id)
    code_input = message.text.strip()
    data = load_data()

    promo_codes = data.get("promo_codes", {})
    promo_key = next((key for key in promo_codes if key.lower() == code_input.lower()), None)

    if not promo_key:
        bot.send_message(message.chat.id, "❌ Такого промокода не существует.", reply_markup=get_main_menu_markup(user_id))
        return

    promo = promo_codes[promo_key]

    # Проверка срока действия
    expires_at = promo.get("expires_at")
    if expires_at:
        try:
            expiration = datetime.strptime(expires_at, "%Y-%m-%dT%H:%M:%S")
            if datetime.now() > expiration:
                bot.send_message(message.chat.id, "⌛ Срок действия промокода истёк.", reply_markup=get_main_menu_markup(user_id))
                return
        except Exception as e:
            print(f"[promo expiration parse error]: {e}")

    # Проверка лимита использований
    used_by = promo.setdefault("used_by", [])
    if len(used_by) >= promo.get("max_uses", 1):
        bot.send_message(message.chat.id, "🚫 Промокод уже использован максимальное число раз.", reply_markup=get_main_menu_markup(user_id))
        return

    # Проверка уникальности
    if promo.get("unique", True) and int(user_id) in used_by:
        bot.send_message(message.chat.id, "⚠️ Вы уже использовали этот промокод.", reply_markup=get_main_menu_markup(user_id))
        return

    # 💰 Деньги
    money = promo.get("bonus", 0)
    user = data["users"].setdefault(user_id, {})
    user.setdefault("balance", 0)
    user.setdefault("promo_codes_used", [])
    user.setdefault("purchases", [])

    if isinstance(money, int) and money > 0:
        user["balance"] += money
        user["purchases"].append({
            "item": f"Промокод {promo_key}",
            "price": money,
            "date": datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        })

    if int(user_id) not in used_by:
        used_by.append(int(user_id))
    if promo_key not in user["promo_codes_used"]:
        user["promo_codes_used"].append(promo_key)

    # Удаление промокода если одноразовый
    if promo.get("delete_after_use") and promo.get("max_uses", 1) <= len(used_by):
        del data["promo_codes"][promo_key]

    save_data(data)

    print(f"[PROMO] {user_id} активировал {promo_key} — {money}₽")
    bot.send_message(message.chat.id, f"✅ Промокод применён!\n💰 Начислено: {money}₽", reply_markup=get_main_menu_markup(user_id))

def process_profile_promo(message):
    """
    Функция для обработки ввода промокода из профиля.
    В данном случае можно переиспользовать общую логику обработки промокода.
    """
    process_promo_code(message)  # если логика совпадает, можно вызвать уже реализованную функцию



@bot.callback_query_handler(func=lambda call: call.data == "activate_promo_welcome")
def handle_activate_promo(call):
    msg = bot.send_message(call.message.chat.id, "🎟 Введите промокод для активации:")
    bot.register_next_step_handler(msg, process_promo_code)

def create_promo(code, reward, max_uses=1, unique=True, expires_at=None, delete_after_use=False):
    data = load_data()
    data.setdefault("promo_codes", {})
    data["promo_codes"][code] = {
        "reward": reward,
        "max_uses": max_uses,
        "unique": unique,
        "expires_at": expires_at,  # формат: "2025-04-01T00:00:00"
        "used_by": [],
        "delete_after_use": delete_after_use
    }
    save_data(data)





#------------------- Стрики ----------------------

@bot.message_handler(commands=["streak"])
def handle_streak(message):
    user_id = str(message.from_user.id)

    # Сначала обновляем стрик (и автоматически XP/уровень)
    xp_reward, streak = update_streak(user_id)

    # Достаём свежие данные
    data   = load_data()
    user   = data["users"].get(user_id)
    if not user or not user.get("approved", False):
        return bot.send_message(
            message.chat.id,
            "Вы не зарегистрированы или ваша заявка не одобрена."
        )

    # Параметры для вывода
    streak     = user.get("login_streak", 0)
    max_streak = user.get("max_login_streak", 0)
    last_login = user.get("last_login", "никогда")
    ender_eyes = user.get("ender_eyes", 0)

    # Ранг по стрику
    if streak < 7:
        rank = "Новичок 🟢"
    elif streak < 15:
        rank = "Надёжный 🔵"
    elif streak < 30:
        rank = "Упорный 🟡"
    else:
        rank = "Легенда 🔴"

    # Прогресс-бар: до 10 дней
    fire_count = min(streak, 10)
    fire       = "🔥" * fire_count
    empty      = "▫️" * (10 - fire_count)
    bar        = f"[{fire}{empty}]"

    # Отправляем профиль стрика
    bot.send_message(
        message.chat.id,
        (
            f"<b>🔥 Ваш текущий стрик</b>\n"
            f"{bar}\n\n"
            f"📅 Последний вход: {last_login}\n"
            f"📈 Текущий стрик: {streak} дн.\n"
            f"🏅 Ранг: {rank}\n"
            f"🔝 Макс. стрик: {max_streak} дн.\n"
            f"🧿 Око Эндера: {ender_eyes}"
        ),
        parse_mode="HTML"
    )


def update_streak(user_id: str):
    """
    При вызове:
     – обновляет login_streak & max_login_streak,
     – начисляет случайное XP (25–125) + 1.5× бонус BV#,
     – даёт 5% шанс на +1 🧿,
     – даёт 20% шанс на +1–5 💰,
     – сохраняет и автоматически прокачивает уровень через update_xp().
    Возвращает (xp_reward, streak) или (None, old_streak), если уже заходил сегодня.
    """
    data = load_data()
    user = data["users"].get(user_id)
    if not user:
        return None, 0

    today     = datetime.now().strftime("%Y-%m-%d")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    # Уже заходил?
    if user.get("last_login") == today:
        return None, user.get("login_streak", 0)

    # Вычисляем новый стрик
    if user.get("last_login") == yesterday:
        streak = user.get("login_streak", 0) + 1
    else:
        streak = 1

    user["login_streak"]     = streak
    user["last_login"]       = today
    user["max_login_streak"] = max(user.get("max_login_streak", 0), streak)

    # ——— XP за вход: 25–125, перекос вниз ———
    base_xp   = int((random.random() ** 2) * 100) + 25
    # бонус BV#
    multiplier = 1.5 if user.get("bv_plus") else 1.0
    xp_reward  = int(base_xp * multiplier)
    add_user_xp(user_id, xp_reward, data)
    update_xp(user_id)

    # ——— Шанс на 1 🧿 ———
    if random.random() < 0.05:
        user["ender_eyes"] = user.get("ender_eyes", 0) + 1
        eye_reward = 1
    else:
        eye_reward = 0

    # ——— Шанс на 1–5 💰 ———
    if random.random() < 0.20:
        coin_reward = random.randint(1, 5)
        user["balance"] = user.get("balance", 0) + coin_reward
    else:
        coin_reward = 0

    # Сохраняем изменения по стрику и XP
    save_data(data)

    # Автоматически проверяем и прокачиваем уровень
    update_xp(user_id)

    # Уведомление о награде за вход
    msg = f"🎁 За вход сегодня: +{xp_reward} XP"
    if eye_reward:
        msg += f", +{eye_reward} 🧿"
    if coin_reward:
        msg += f", +{coin_reward} 💰"
    bot.send_message(user_id, msg)

    return xp_reward, streak



@bot.callback_query_handler(func=lambda call: call.data == "top_streaks")
def show_top_streaks(call):
    data = load_data().get("users", {})
    sorted_users = sorted(
        data.items(),
        key=lambda item: item[1].get("login_streak", 0),
        reverse=True
    )
    top5 = sorted_users[:5]

    if not top5:
        text = "😕 Пока нет данных по стрикам."
    else:
        text = "🔥 *Топ‑5 игроков по стрику:*\n"
        for i, (uid, u) in enumerate(top5, 1):
            nick   = u.get("nickname", "—")
            streak = u.get("login_streak", 0)
            text  += f"{i}. {nick} — {streak} дн.\n"

    back_btn = types.InlineKeyboardButton("🔙 Назад", callback_data="stats_menu")
    back_markup = types.InlineKeyboardMarkup().add(back_btn)

    bot.edit_message_text(
        text,
        call.message.chat.id,
        call.message.message_id,
        parse_mode="Markdown",
        reply_markup=back_markup
    )

@bot.callback_query_handler(func=lambda call: call.data == "top_levels")
def show_top_levels(call):
    data = load_data().get("users", {})
    sorted_users = sorted(
        data.items(),
        key=lambda item: item[1].get("level", 0),
        reverse=True
    )
    top5 = sorted_users[:5]

    if not top5:
        text = "😕 Пока нет данных по уровням."
    else:
        text = "🏆 <b>Топ-5 игроков по уровню:</b>\n"
        for i, (uid, u) in enumerate(top5, 1):
            nick  = u.get("nickname", "—")
            level = u.get("level", 0)
            text += f"{i}. {nick} — {level} ур.\n"

    markup = types.InlineKeyboardMarkup().add(
        types.InlineKeyboardButton("🔙 Назад", callback_data="stats_menu")
    )
    bot.edit_message_text(
        text,
        call.message.chat.id,
        call.message.message_id,
        parse_mode="HTML",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data == "top_tribes")
def show_top_tribes(call):
    data = load_data().get("tribes", {})
    sorted_tribes = sorted(
        data.values(),
        key=lambda t: t.get("level", 0),
        reverse=True
    )
    top5 = sorted_tribes[:5]

    if not top5:
        text = "😕 Пока нет данных по трайбам."
    else:
        text = "🛡 <b>Топ-5 трайбов:</b>\n"
        for i, tribe in enumerate(top5, 1):
            name = tribe.get("name", "—")
            level = tribe.get("level", 1)
            text += f"{i}. {name} — {level} ур.\n"

    markup = types.InlineKeyboardMarkup().add(
        types.InlineKeyboardButton("🔙 Назад", callback_data="stats_menu")
    )
    bot.edit_message_text(
        text,
        call.message.chat.id,
        call.message.message_id,
        parse_mode="HTML",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data == "season_archive")
def show_season_archive(call):
    seasons = load_seasons()
    text = "🗂 <b>Архив сезонов</b>"
    if seasons:
        for s in seasons:
            number = s.get("number", "")
            name = s.get("name", f"Сезон {number}")
            dates = s.get("dates", "")
            text += f"\n{number}. {name} ({dates})"
    else:
        text += "\nАрхив сезонов пуст."

    markup = types.InlineKeyboardMarkup()
    if call.from_user.id == ADMIN_ID:
        markup.add(types.InlineKeyboardButton("➕ Добавить сезон", callback_data="season_add"))
    markup.add(types.InlineKeyboardButton("🔙 Назад", callback_data="stats_menu"))
    bot.edit_message_text(
        text,
        call.message.chat.id,
        call.message.message_id,
        parse_mode="HTML",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("season_view_"))
def show_season_detail(call):
    try:
        number = int(call.data.split("_")[-1])
    except ValueError:
        bot.answer_callback_query(call.id, "Ошибка номера сезона")
        return
    seasons = load_seasons()
    season = next((s for s in seasons if s.get("number") == number), None)
    if not season:
        bot.answer_callback_query(call.id, "Сезон не найден")
        return
    text = (
        f"<b>{season.get('name', 'Сезон')} - {season.get('number')}</b>\n"
        f"{season.get('dates', '')}\n\n"
        f"{season.get('description', '')}"
    )
    pages = season.get("pages") or []
    if pages:
        text += "\n\n" + "\n".join(f"- {p}" for p in pages)
    markup = types.InlineKeyboardMarkup().add(
        types.InlineKeyboardButton("🔙 К сезонам", callback_data="season_archive")
    )
    bot.edit_message_text(
        text,
        call.message.chat.id,
        call.message.message_id,
        parse_mode="HTML",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data == "season_add")
def add_season_start(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Нет доступа")
        return
    msg = bot.send_message(call.message.chat.id, "Введите название сезона:")
    user_states[str(call.from_user.id)] = {"state": "awaiting_season_title", "temp_data": {}}
    bot.register_next_step_handler(msg, process_season_title)

@bot.message_handler(commands=["add_season"])
def cmd_add_season(message):
    if message.from_user.id != ADMIN_ID:
        return
    msg = bot.send_message(message.chat.id, "Введите название сезона:")
    user_states[str(message.from_user.id)] = {"state": "awaiting_season_title", "temp_data": {}}
    bot.register_next_step_handler(msg, process_season_title)

@bot.message_handler(func=lambda m: str(m.from_user.id) in user_states and user_states[str(m.from_user.id)].get("state") == "awaiting_season_title")
def process_season_title(message):
    if message.from_user.id != ADMIN_ID:
        return
    user_states[str(message.from_user.id)]["temp_data"]["title"] = message.text.strip()
    user_states[str(message.from_user.id)]["state"] = "awaiting_season_dates"
    msg = bot.send_message(message.chat.id, "Введите даты сезона (например 01.2023 - 06.2023):")
    bot.register_next_step_handler(msg, process_season_dates)

@bot.message_handler(func=lambda m: str(m.from_user.id) in user_states and user_states[str(m.from_user.id)].get("state") == "awaiting_season_dates")
def process_season_dates(message):
    if message.from_user.id != ADMIN_ID:
        return
    user_states[str(message.from_user.id)]["temp_data"]["dates"] = message.text.strip()
    user_states[str(message.from_user.id)]["state"] = "awaiting_season_desc"
    msg = bot.send_message(message.chat.id, "Введите описание сезона:")
    bot.register_next_step_handler(msg, process_season_desc)

@bot.message_handler(func=lambda m: str(m.from_user.id) in user_states and user_states[str(m.from_user.id)].get("state") == "awaiting_season_desc")
def process_season_desc(message):
    if message.from_user.id != ADMIN_ID:
        return
    info = user_states.pop(str(message.from_user.id), {}).get("temp_data", {})
    info["description"] = message.text.strip()
    seasons = load_seasons()
    number = len(seasons) + 1
    season = {
        "number": number,
        "name": info.get("title", f"Сезон {number}"),
        "dates": info.get("dates", ""),
        "description": info.get("description", ""),
        "pages": []
    }
    seasons.append(season)
    save_seasons(seasons)
    bot.send_message(message.chat.id, f"Сезон '{season['name']}' добавлен.")

#------------------- Око Эндера ----------------------

def add_ender_eye(user_id, amount):
    data = load_data()
    user = data["users"].get(user_id)
    if user is None:
        return False  # пользователь не найден
    # Получаем текущее значение или 0 по умолчанию
    current = user.get("ender_eyes", 0)
    user["ender_eyes"] = current + amount
    save_data(data)
    return True

def award_beta_tribe_bonus():
    data = load_data()
    for uid, user in data["users"].items():
        if user.get("tribe") and not user.get("beta_tribe_bonus_given", False):
            user["ender_eyes"] = user.get("ender_eyes", 0) + 5
            user["beta_tribe_bonus_given"] = True
            try:
                bot.send_message(uid, "🎁 Награда бета запуска: Вы состоите в трайбе, вам выдано +5 🧿 ОК эндера!")
            except Exception as e:
                print(f"Ошибка отправки сообщения пользователю {uid}: {e}")
    save_data(data)

@bot.message_handler(commands=["award_beta"])
def cmd_award_beta(message):
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "Нет прав доступа.")
        return
    award_beta_tribe_bonus()
    bot.send_message(message.chat.id, "Бонусы для текущих участников трайба успешно выданы!")

def process_tribe_login_rewards(user_id):
    data = load_data()
    user = data["users"].get(user_id)
    if not user or "tribe" not in user:
        return  # игрок не состоит в трайбе

    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    last_bonus_str = user.get("last_tribe_join_bonus")

    give_bonus = False
    if last_bonus_str:
        try:
            last_bonus_date = datetime.strptime(last_bonus_str, "%Y-%m-%d")
            if (now - last_bonus_date).days >= 3:
                give_bonus = True
        except Exception:
            give_bonus = True  # если дата битая — всё равно выдаём
    else:
        give_bonus = True

    if give_bonus:
        user["ender_eyes"] = user.get("ender_eyes", 0) + 5
        user["last_tribe_join_bonus"] = today
        try:
            bot.send_message(user_id, "🎁 За вступление в трайб: +5 🧿 Око Эндера!")
        except Exception as e:
            print(f"[ERROR] Не удалось отправить бонус за трайб игроку {user_id}: {e}")

    save_data(data)




# ------------------- Подарок -------------------
@bot.callback_query_handler(func=lambda call: call.data == "daily_gift")
def handle_daily_gift(call):
    user_id = str(call.from_user.id)
    data    = load_data()
    user    = data["users"].get(user_id)
    if not user:
        return bot.answer_callback_query(call.id, "Сначала зарегистрируйтесь!")

    today = datetime.now().date().isoformat()
    # Проверяем, не брал ли уже сегодня
    if user.get("last_daily_gift") == today:
        now = datetime.now()
        nxt = datetime.combine(now.date() + timedelta(days=1), datetime.min.time())
        delta = nxt - now
        hrs, mins = delta.seconds // 3600, (delta.seconds % 3600) // 60
        return bot.answer_callback_query(call.id,
            f"🎁 Вы уже брали подарок. Приходите через {hrs}ч{mins}м."
        )

    # Рандомим приз
    r = random.random()
    # расчёт XP: от 5 до 35, с перекосом в малые значения
    xp_amount = int((random.random()**2) * 30) + 5
    text = ""

    if r < 0.05:
        # комбо-подарок: XP + монетка
        coins = random.randint(1, 3)
        add_user_xp(user_id, xp_amount, data)
        user["balance"] = user.get("balance", 0) + coins
        text = f"Комбоподарок! +{xp_amount} XP, +{coins}💰"
    elif r < 0.10:
        # один глаз Эндера
        user["ender_eyes"] = user.get("ender_eyes", 0) + 1
        text = "+1 🧿 Око Эндера"
    elif r < 0.20:
        # только монеты
        coins = random.randint(1, 5)
        user["balance"] = user.get("balance", 0) + coins
        text = f"+{coins}💰 монет"
    else:
        # только XP
        add_user_xp(user_id, xp_amount, data)
        text = f"+{xp_amount} XP"

    # отмечаем, что сегодня подарок взят
    user["last_daily_gift"] = today
    save_data(data)

    save_data(data)
    update_xp(user_id)

    # отвечаем пользователю
    bot.answer_callback_query(call.id, text)
    bot.send_message(call.message.chat.id, f"🎁 {text}")

    # обновляем кнопку (если у вас меню в том же сообщении)
    try:
        kb = market_main_markup(user_id)
        bot.edit_message_reply_markup(
            call.message.chat.id,
            call.message.message_id,
            reply_markup=kb
        )
    except:
        pass

# Проверка наличия пользователя и его одобрения
def is_user_approved(user_id):
    data = load_data()
    return user_id in data["users"] and data["users"][user_id].get("approved", False)


# Сообщение о нехватке средств
def insufficient_funds_bv(message):
    bot.send_message(message.chat.id, "Недостаточно средств для активации BV+.", reply_markup=welcome_markup())

def safe_edit_message_text(text, chat_id, message_id, reply_markup=None):
    """
    Попытка отредактировать сообщение; если редактирование не удаётся – отправляет новое сообщение.
    """
    try:
        bot.edit_message_text(text, chat_id, message_id, reply_markup=reply_markup, parse_mode="HTML")
    except Exception as e:
        print(f"[ERROR] safe_edit_message_text: {e}")
        bot.send_message(chat_id, text, reply_markup=reply_markup, parse_mode="HTML")

def process_purchase(user_id, price, item):
    """
    Проверяет, достаточно ли средств у пользователя для покупки,
    списывает указанную сумму, записывает покупку и возвращает статус.
    """
    data = load_data()
    user = data["users"].get(user_id)
    if not user:
        return False, "Пользователь не найден."
    if user.get("balance", 0) < price:
        return False, "Недостаточно средств."
    user["balance"] -= price
    user.setdefault("purchases", []).append({
        "item": item,
        "price": price,
        "date": datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    })
    save_data(data)
    return True, f"Услуга {item} успешно приобретена."


# ------------------- Бот в группе (с «кто это», «трайбы», «подарок» и «роли») -------------------
@bot.message_handler(func=lambda m: 
    m.chat.type in ["group", "supergroup"] and
    m.chat.id == -1002353421985 and
    m.message_thread_id == 28 and
    (
        # если реплаят на сообщение и одна из allowed_texts
        (m.reply_to_message and 
         m.text and 
         m.text.strip().lower() in [
             "кто это", "кто он", "кто она", "кто такой", "кто такая",
             "трайбы", "/трайбы", "список трайбов", "все трайбы",
             "подарок", "/подарок", "дай подарок", "хочу подарок"
         ]
        )
        # или просто команда ролей
        or
        (m.text and m.text.strip().lower() in ["роли", "/роли", "список ролей", "актуальные роли"])
    )
)
def handle_group_commands(m):
    text = m.text.strip().lower()

    # ===== "КТО ЭТО"
    if m.reply_to_message and text in ["кто это", "кто он", "кто она", "кто такой", "кто такая"]:
        target_user = m.reply_to_message.from_user
        if not target_user:
            return
        data = load_data()
        uid = str(target_user.id)
        if uid not in data["users"]:
            bot.reply_to(m, "❌ Игрок не найден в базе.")
            return
        user = data["users"][uid]
        msg = render_search_profile(user)
        bot.reply_to(m, msg, parse_mode="HTML")
        return

    # ===== "ТРАЙБЫ"
    if m.reply_to_message and text in ["трайбы", "/трайбы", "список трайбов", "все трайбы"]:
        # вызываем ваш существующий список трайбов
        tribe_list(SimpleNamespace(message=m, from_user=m.from_user, data="list_tribes"))
        return

    # ===== "ПОДАРОК"
    if m.reply_to_message and text in ["подарок", "/подарок", "дай подарок", "хочу подарок"]:
        bot.send_message(
            m.chat.id,
            "🎁 Теперь ежедневный подарок можно получить только во вкладке *Маркет* внутри бота.",
            message_thread_id=m.message_thread_id,
            parse_mode="Markdown"
        )
        return

    # ===== "РОЛИ"
    if text in ["роли", "/роли", "список ролей", "актуальные роли"]:
     data = load_data()
     users = data.get("users", {})
     roles_list = {
        "PRES001": "Президент",
        "MAY002":  "Мэр",
        "CON003":  "Министр Строительства",
        "FIN004":  "Министр Финансов",
        "PRO005":  "Прокурор",              # ← добавили
    }

    msg_text = "<b>🎭 Актуальные роли:</b>\n━━━━━━━━━━━━━━━━\n"
    for _, role_name in roles_list.items():
        owner = None
        for uid, u in users.items():
            if u.get("role") == role_name:
                nick  = u.get("nickname", "—")
                uname = u.get("telegram_username", "")
                if role_name == "Президент":
                    owner = nick
                else:
                    owner = f"<a href='https://t.me/{uname}'>{nick}</a>" if uname else nick
                break
        if owner:
            msg_text += f"▪️ <b>{role_name}</b> — {owner}\n"
        else:
            msg_text += f"▪️ <b>{role_name}</b> — <i>не назначено</i>\n"

    bot.send_message(
        m.chat.id,
        msg_text,
        parse_mode="HTML",
        disable_web_page_preview=True,
        message_thread_id=m.message_thread_id
    )
    return




#----------Роли------
@bot.callback_query_handler(func=lambda call: call.data == "show_roles")
def show_roles(call):
    data = load_data()
    users = data.get("users", {})

    # Фиксированный список ролей: код -> название
    roles_list = {
        "PRES001": "Президент",
        "MAY002":  "Мэр",
        "CON003":  "Министр Строительства",
        "FIN004":  "Министр Финансов",
        "PRO005":  "Прокурор",              # ← добавили
    }

    text = "<b>🎭 Актуальные роли:</b>\n━━━━━━━━━━━━━━━━\n"

    for _, role_name in roles_list.items():
        owner = None
        for uid, user in users.items():
            if user.get("role") == role_name:
                nickname = user.get("nickname", "—")
                username = user.get("telegram_username", "")
                if role_name == "Президент":
                    owner = nickname
                else:
                    owner = f"<a href='https://t.me/{username}'>{nickname}</a>" if username else nickname
                break
        if owner:
            text += f"▪️ <b>{role_name}</b> — {owner}\n"
        else:
            text += f"▪️ <b>{role_name}</b> — <i>не назначено</i>\n"

    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🔙 Назад", callback_data="search_players"))

    try:
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=kb,
            parse_mode="HTML",
            disable_web_page_preview=True
        )
    except Exception as e:
        print(f"[ERROR] show_roles: {e}")
        bot.send_message(call.message.chat.id, text, reply_markup=kb, parse_mode="HTML")

# ─────────────────────────────────────────────────────────────
#                       📖  GUIDE  BLOCK
# ─────────────────────────────────────────────────────────────
GUIDE_STEPS = [
    {
        "title": "Добро пожаловать в Bedrock Valley!",
        "text": (
            "Это приватный Minecraft Bedrock-сервер, где мы строим и кайфуем без грифа и токсичности.\n\n"
            "Нажимай ▶️, чтобы узнать, как здесь всё устроено."
        )
    },
    {
        "title": "Базовые правила 🛡",
        "text": (
            "- Не гриферить и не красть.\n"
            "- PvP — только по взаимному согласию.\n"
            "- Уважать чужие постройки.\n"
            "- Без читов и эксплойтов.\n"
            "- Никакой токсичности.\n"
            "- Стройте в пределах своего участка.\n\n"
            "Полный свод правил: https://telegra.ph/Rules-BV-12-22"
        )
    },
    {
        "title": "Маркет 🛒",
        "text": (
            "Заходи в «🛒 Маркет» каждый день:\n"
            "• 🎁 Ежедневный подарок\n"
            "• 😊 Пакеты эмодзи и кейсы\n"
            "• ✨ Кастомизация ника и прочие плюшки\n"
            "• Подписка BVSharp"
        )
    },
    {
        "title": "Подписка BV# ⭐",
        "text": (
            "Самый выгодный апгрейд:\n"
            "• Первый месяц — 169 ₽ (дальше 199 ₽/мес)\n"
            "• 🎁 Кейс «Командный блок» при каждой оплате\n"
            "• Неограниченный доступ ко всем эмодзи (кроме Незеритовых)\n"
            "• Любой цвет ника в Minecraft"
        )
    },
    {
        "title": "Око Эндера 🧿 и Стрик 🔥",
        "text": (
            "Заходи каждый день и поддерживай стрик, чтобы получать больше опыта.\n"
            "Око Эндера выдаётся за повышение уровня и тратится в Маркете на ценные награды."
        )
    },
    {
        "title": "Сообщество и Трайбы 🏰",
        "text": (
            "Через «Сообщество» открывается меню вашего трайба.\n"
            "Здесь можно вступить или создать клан, а также подать заявку.\n"
            "Доступен список должностей, поиск игроков и подача дела в суд.\n"
            "При повышении LVL трайба все участники получают +10 🧿."
        )
    },
    {
        "title": "Поиск игроков и роли 🎯",
        "text": (
            "Ищи игроков по нику или Telegram.\n"
            "Тут же можно посмотреть актуальные должности сервера."
        )
    },
    {
        "title": "Рейтинги и сезоны 📊",
        "text": (
            "Следи за топами игроков и трайбов в разделе «Статистика».\n"
            "Архив прошедших сезонов ищи в «Архиве сезонов»."
        )
    },
    {
        "title": "Готово! 🎉",
        "text": (
            "Ты просмотрел гид до конца.\n"
            "На твой счёт начислено +10 🧿 Око Эндера.\n"
            "Вернуться к гайду можно через команду /guide\n"
            "Пропиши /start чтобы вернуться обратно"
        )
    }
]

GUIDE_REWARD_EYES = 10  # награда даётся ровно один раз


# ───── вспомогательные setters/getters ─────
def get_user_guide_step(user):
    return user.get("guide_step", 0)

def set_user_guide_step(user, step):
    user["guide_step"] = step


# ───── основное открытие гида ─────
def open_guide(chat_id, user_id, reset=False):
    data = load_data()
    user = data["users"].setdefault(user_id, {})
    step = 0 if reset else get_user_guide_step(user)
    if step >= len(GUIDE_STEPS):
        step = len(GUIDE_STEPS) - 1
    show_guide_step(chat_id, user_id, step)
    save_data(data)


# ───── показ одного шага ─────
def show_guide_step(chat_id, user_id, step):
    data = load_data()
    user = data["users"][user_id]

    title = GUIDE_STEPS[step]["title"]
    text  = GUIDE_STEPS[step]["text"]

    # навигационная клавиатура
    markup = types.InlineKeyboardMarkup()
    nav = []
    if step > 0:
        nav.append(types.InlineKeyboardButton("◀️", callback_data=f"guide_prev_{step}"))
    nav.append(types.InlineKeyboardButton(f"{step+1}/{len(GUIDE_STEPS)}", callback_data="noop"))
    if step < len(GUIDE_STEPS) - 1:
        nav.append(types.InlineKeyboardButton("▶️", callback_data=f"guide_next_{step}"))
    markup.row(*nav)

    # «Пропустить» только в начале
    if step == 0:
        markup.add(types.InlineKeyboardButton("Пропустить", callback_data="guide_skip"))

    bot.send_message(chat_id, f"<b>{title}</b>\n\n{text}",
                     parse_mode="HTML", reply_markup=markup)

    # сохраняем прогресс
    set_user_guide_step(user, step)

    # финальная награда
    if step == len(GUIDE_STEPS) - 1 and not user.get("guide_completed"):
        user["guide_completed"] = True
        user["ender_eyes"] = user.get("ender_eyes", 0) + GUIDE_REWARD_EYES
        user.setdefault("purchases", []).append({
            "item": "Награда за прохождение гида",
            "price": f"+{GUIDE_REWARD_EYES}🧿",
            "date": datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        })

    save_data(data)


# ───── команды/колбэки ─────
@bot.message_handler(commands=["guide"])
def cmd_guide(message):
    open_guide(message.chat.id, str(message.from_user.id), reset=False)

@bot.callback_query_handler(func=lambda c: c.data.startswith("open_guide"))
def cb_open_guide(call):
    user_id = str(call.from_user.id)
    reset = call.data == "open_guide_reset"
    open_guide(call.message.chat.id, user_id, reset=reset)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data.startswith(("guide_prev_", "guide_next_")))
def guide_nav(call):
    user_id = str(call.from_user.id)
    direction, cur = call.data.split("_")[1], int(call.data.split("_")[2])
    step = cur - 1 if direction == "prev" else cur + 1
    show_guide_step(call.message.chat.id, user_id, step)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda c: c.data == "guide_skip")
def guide_skip(call):
    bot.answer_callback_query(call.id, "Гид пропущен. Можно вернуться через /guide.")
    bot.delete_message(call.message.chat.id, call.message.message_id)
    data = load_data()
    user = data["users"][str(call.from_user.id)]
    user["guide_step"] = 0
    save_data(data)


# ─────────── Блок работы с XP и уровнями ───────────

def xp_to_next(level: int) -> int:
    """
    Возвращает, сколько XP нужно, чтобы перейти
    с уровня `level` на `level+1`.
    0→1:100, 1→2:125, 2→3:150 и т.д.
    """
    return 100 + 25 * level

def tribe_xp_to_next(level: int) -> int:
    """Возвращает XP, необходимый трайбу для перехода на следующий уровень."""
    return 150 + 100 * level

def add_tribe_xp(leader_id: str, amount: int, data: dict):
    tribe = data.get("tribes", {}).get(leader_id)
    if not tribe:
        return
    tribe.setdefault("level", 1)
    tribe.setdefault("xp", 0)
    tribe["xp"] += amount
    leveled = False
    while tribe["xp"] >= tribe_xp_to_next(tribe["level"]):
        tribe["xp"] -= tribe_xp_to_next(tribe["level"])
        tribe["level"] += 1
        leveled = True
    if leveled:
        for member in tribe.get("members", []):
            uid = member.get("user_id")
            if uid in data.get("users", {}):
                usr = data["users"][uid]
                usr["ender_eyes"] = usr.get("ender_eyes", 0) + 10
                try:
                    bot.send_message(uid,
                                     f"🎉 Трайб {tribe['name']} поднял уровень! +10 🧿 всем участникам.")
                except Exception as e:
                    print(f"[WARN] notify tribe level up {uid}: {e}")

def add_user_xp(user_id: str, amount: int, data: dict):
    user = data["users"].setdefault(user_id, {})
    user.setdefault("xp", 0)
    user["xp"] += amount
    leader_id, tribe = get_user_tribe(user_id, data)
    if tribe:
        add_tribe_xp(leader_id, amount, data)
    return amount

def level_up(user_id: str, data: dict):
    """
    Поднимает пользователя на все уровни, которые он «проскочил»,
    выдаёт по 5 🧿 за каждый уровень (по 10 🧿, если уровень кратен 5),
    сохраняет данные и шлёт одно итоговое сообщение.
    """
    user = data["users"][user_id]
    total_reward = 0

    # Цикл: пока хватает XP на следующий уровень
    while user["xp"] >= xp_to_next(user["level"]):
        user["xp"]    -= xp_to_next(user["level"])
        user["level"] += 1

        reward = 10 if (user["level"] % 5 == 0) else 5
        user["ender_eyes"] = user.get("ender_eyes", 0) + reward
        total_reward += reward

    if total_reward > 0:
        save_data(data)
        bot.send_message(
            user_id,
            (
                f"🎉 Поздравляем! Вы достигли <b>{user['level']}</b>-го уровня.\n"
                f"Вы получили всего +{total_reward} 🧿 Око Эндера.\n"
                f"Текущий прогресс: {user['xp']}/{xp_to_next(user['level'])} XP"
            ),
            parse_mode="HTML"
        )

def update_xp(user_id: str):
    """
    Вызывается сразу после save_data(data) в любом месте, где
    вы добавляете XP пользователю. Если XP дошёл до порога—
    делегирует всю работу в level_up().
    """
    data = load_data()
    user = data["users"].get(user_id)
    if not user:
        return

    # Гарантируем поля
    user.setdefault("level", 0)
    user.setdefault("xp", 0)
    user.setdefault("ender_eyes", 0)

    # Если XP достиг порога — апаем
    if user["xp"] >= xp_to_next(user["level"]):
        level_up(user_id, data)

def award_xp(user: dict, base_xp: int) -> int:
    """
    Ваша старая функция начисления базового XP (с учётом 1.5× бонуса BV#).
    Просто назовите её так же. В конце не создаёт уведомление по уровню.
    """
    multiplier = 1.5 if user.get("bv_plus") else 1.0
    xp_add = int(base_xp * multiplier)
    user.setdefault("xp", 0)
    user["xp"] += xp_add
    return xp_add

# ───────────── Конец блока XP ─────────────


bot.infinity_polling(timeout=90, long_polling_timeout=45)





