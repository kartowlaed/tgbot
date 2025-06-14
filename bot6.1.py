import telebot
from telebot import types 
from types import SimpleNamespace
from datetime import datetime, timedelta
import json
import os
import re
import random
import uuid  
from telebot.apihelper import ApiTelegramException
import logging
from telebot.types import InputMediaPhoto
from collections import OrderedDict


TOKEN = "7315526767:AAGDugQsy0cb7Sj9pBBfFhE80ubgdA2ypkc"
ADMIN_ID = 827377121           # Для покупок, разбана и регистрации

bot = telebot.TeleBot(TOKEN)


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Пути к файлам
DATA_FILE = os.path.join(BASE_DIR, "data.json")

# Global dictionary for user states
user_states = {}  # { user_id: { "state": ..., "temp_data": { ... } } }

with open(DATA_FILE, "r", encoding="utf-8") as f:
    data = json.load(f)

def get_root_path(filename):
    base_dir = os.path.dirname(os.path.abspath(__file__))  # путь к корню бота
    return os.path.join(base_dir, filename)    
# Global dictionary for user states
user_states = {}  # { user_id: { "state": ..., "temp_data": { ... } } }

# Изменённые цены на эмодзи
emoji_details = [
    {"name": "Каменные эмодзи", "price": 30, "quantity": 14, 
     "image": "stone.png",
     "description": "Базовые эмодзи, прочные как камень 🪨. На картинке 14 эмодзи с уникальными номерами."},
    {"name": "Железные эмодзи", "price": 50, "quantity": 17, 
     "image": "iron.png",
     "description": "Надежные эмодзи, как железный блок ⚙️. На картинке 17 эмодзи с номерами."},
    {"name": "Золотые эмодзи", "price": 85, "quantity": 21, 
     "image": "gold.png",
     "description": "Сияющие эмодзи, как золотой блеск ✨. На изображении 21 эмодзи с номерами."},
    {"name": "Алмазные эмодзи", "price": 115, "quantity": 28, 
     "image": "diamond.png",
     "description": "Редкие и роскошные эмодзи, как алмазы 💎. На изображении 27 эмодзи с номерами."},
    {"name": "Незеритовые эмодзи", "price": 159, "quantity": 27, 
     "image": "nether.png",
     "description": "Эмодзи высшего класса, уникальные и эксклюзивные 🔥. На картинке 28 эмодзи с номерами."}
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
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(default_data, f, indent=4)
        try:
            bot.send_message(ADMIN_ID, f"❗ Ошибка загрузки data.json: {e}. Файл восстановлен.")
        except Exception as send_err:
            print(f"[Ошибка при уведомлении админа]: {send_err}")
        return default_data


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

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



# ------------------- Markup definitions -------------------
def get_main_menu_markup(user_id):
    data = load_data()
    user = data["users"].get(user_id, {})
    status = user.get("status", "user")

    markup = types.InlineKeyboardMarkup()

    # 📛 Забанен
    if status == "banned":
        markup.add(types.InlineKeyboardButton("🔓 Разбан за 500₽", callback_data="request_unban"))
        markup.add(types.InlineKeyboardButton("👤 Профиль", callback_data="menu_profile"))
        return markup

    # ⛔ Несовершеннолетний без прохода
    if status == "minor" and not user.get("full_access"):
        markup.add(types.InlineKeyboardButton("🧸 Пропуск (250₽)", callback_data="buy_minor_pass"))
        markup.add(types.InlineKeyboardButton("👤 Профиль", callback_data="menu_profile"))
        return markup

    # ✅ Обычный пользователь
    # Ряд 1 — Профиль
    markup.row(types.InlineKeyboardButton("👤 Профиль", callback_data="menu_profile"))

    # Ряд 2 — Маркет + Трайбы
    btn_market = types.InlineKeyboardButton("🛒 Маркет", callback_data="market_main")
    btn_tribes = types.InlineKeyboardButton("🆕 Трайбы", callback_data="community_tribes")  # <-- исправлено
    markup.row(btn_market, btn_tribes)

    # Ряд 3 — Уведомления
    btn_notify = types.InlineKeyboardButton(
        "🔊 Увед" if user.get("subscribed", False) else "🔇 Увед",
        callback_data="toggle_subscription"
    )
    markup.row(btn_notify)

    return markup

def minor_get_welcome_markup(user_id):
    # Если требуется отдельное меню для несовершеннолетних, настройте здесь кнопки;
    # пока возвращаем стандартное главное меню.
    return get_welcome_markup(user_id)

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

@bot.callback_query_handler(func=lambda call: call.data == "toggle_subscription")
def toggle_subscription(call):
    user_id = str(call.from_user.id)
    data = load_data()
    user = data["users"].get(user_id, {})
    # Переключаем статус уведомлений
    current_status = user.get("subscribed", False)
    user["subscribed"] = not current_status
    save_data(data)
    status_text = "включены" if user["subscribed"] else "выключены"
    bot.answer_callback_query(call.id, f"Уведомления {status_text}.")
    # Обновляем главное меню с новым статусом
    bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=get_main_menu_markup(user_id))
def get_welcome_markup(user_id):
    # Для удобства можно переиспользовать основное меню
    return get_main_menu_markup(user_id)

def profile_menu_markup():
    markup = types.InlineKeyboardMarkup()
    btn_topup = types.InlineKeyboardButton("Пополнить 💳", callback_data="profile_topup")
    btn_history = types.InlineKeyboardButton("История 📜", callback_data="profile_history")
    btn_promo = types.InlineKeyboardButton("Промокод 🎫", callback_data="activate_promo_welcome")
    btn_back = types.InlineKeyboardButton("Назад 🔙", callback_data="get_welcome_markup")
    markup.row(btn_topup, btn_history)
    markup.row(btn_promo)
    markup.row(btn_back)
    return markup

def welcome_markup():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("Главное меню"))
    return markup

@bot.callback_query_handler(func=lambda call: call.data == "get_welcome_markup")
def return_welcome(call):
    user_id = str(call.from_user.id)
    send_main_menu(user_id, call.message.chat.id)



@bot.callback_query_handler(func=lambda call: call.data.startswith("profile_"))
def handle_profile(call):
    user_id = str(call.from_user.id)
    data = load_data()
    if user_id not in data["users"]:
        bot.answer_callback_query(call.id, "Вы не зарегистрированы.")
        return

    # Обработка перехода к списку трайбов из профиля
    if call.data == "tribe_join_menu":
        handle_tribe_join_menu(call)
        return

    if call.data == "profile_history":
        user = data["users"][user_id]
        history_text = "История:\n"
        for p in user.get("purchases", []):
            history_text += f"{p['date']}: {p['item']} - {p['price']}₽\n"
        if "referral_history" in user and user["referral_history"]:
            history_text += "\nРеферальные зачисления:\n"
            for r in user["referral_history"]:
                history_text += f"{r['date']}: {r['item']} - {r['amount']}₽\n"
        bot.send_message(call.message.chat.id, history_text, reply_markup=profile_menu_markup())

    elif call.data == "profile_topup":
        bot.send_message(
            call.message.chat.id,
            "⏳ Пополнение через донейшен.\nПлатежи могут обрабатываться до 48 часов.\n"
            "Отправьте донейшен и укажите свой ник:\nhttps://www.donationalerts.com/r/bedrockvalley",
            reply_markup=types.InlineKeyboardMarkup().add(
                types.InlineKeyboardButton("Назад 🔙", callback_data="profile_menu")
            )
        )

    elif call.data == "activate_promo_welcome":
        msg = bot.send_message(call.message.chat.id, "Введите промокод для активации:")
        bot.register_next_step_handler(msg, process_profile_promo)

    else:
        user = data["users"][user_id]
        reg_date = user.get("registration_date", "").split()[0] if user.get("registration_date") else ""
        bv_status = "активна" if user.get("bv_plus") else "неактивна"
        profile_text = (
            f"Профиль:\n"
            f"Никнейм: {user.get('nickname', 'Неизвестно')}\n"
            f"Дата регистрации: {reg_date}\n"
            f"Баланс: {user.get('balance', 0)}₽\n"
            f"BV# - {bv_status}\n\n"
            f"Эмодзи:\n"
        )
        emojis = user.get("emojis", {})
        if not emojis:
            profile_text += "Пока тут пусто"
        else:
            for cat_key, nums in emojis.items():
                cat_index = int(cat_key)
                cat_name = emoji_details[cat_index]["name"]
                nums_str = ", ".join(str(n) for n in nums)
                profile_text += f"{cat_name}: {nums_str}\n"
        bot.send_message(call.message.chat.id, profile_text, reply_markup=profile_menu_markup())


def market_main_markup():
    markup = types.InlineKeyboardMarkup()
    # Кнопки основных разделов магазина, располагаем их в одном ряду
    btn_bv = types.InlineKeyboardButton("BV# ⭐", callback_data="subscribe_bv_plus_market")
    btn_custom = types.InlineKeyboardButton("Кастомизация 🖌️", callback_data="customization")
    btn_top = types.InlineKeyboardButton("Доп услуги ⭐", callback_data="top_services")
    markup.row(btn_bv, btn_custom, btn_top)
    
    # Отдельный ряд для кнопки "Подарок" — она будет большой (растянется на всю ширину)
    btn_gift = types.InlineKeyboardButton("Подарок 🎁", callback_data="daily_gift")
    markup.row(btn_gift)
    
    # Отдельный ряд для кнопки "Назад"
    btn_back = types.InlineKeyboardButton("Назад 🔙", callback_data="get_welcome_markup")
    markup.row(btn_back)
    
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
        reply_markup=get_welcome_markup(user_id)
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
    bot.send_message(chat_id, main_text, reply_markup=get_welcome_markup(user_id))


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
# ------------------- Новый блок админского меню -------------------
def get_admin_markup_new():
    markup = types.InlineKeyboardMarkup(row_width=1)
    btn_promos = types.InlineKeyboardButton("Промокоды", callback_data="admin_promos")
    btn_notifications = types.InlineKeyboardButton("Оповещения", callback_data="admin_notifications")
    btn_roles = types.InlineKeyboardButton("Роль", callback_data="admin_roles")
    btn_bans = types.InlineKeyboardButton("Баны", callback_data="admin_bans")
    markup.add(btn_promos, btn_notifications, btn_roles, btn_bans)

    return markup

@bot.message_handler(commands=["admin"])
def admin_menu(message):
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "Нет прав доступа.")
        return
    bot.send_message(message.chat.id, "Админское меню:", reply_markup=get_admin_markup_new())

# Подменю для промокодов
@bot.callback_query_handler(func=lambda call: call.data == "admin_promos")
def admin_promos_menu(call):
    print("admin_promos вызван")
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_addpromo = types.InlineKeyboardButton("Добавить промокод", callback_data="admin_add_promo")
    btn_viewpromos = types.InlineKeyboardButton("Посмотреть промокоды", callback_data="admin_view_promos")
    btn_delpromo = types.InlineKeyboardButton("Удалить промокод", callback_data="admin_del_promo")
    btn_credit = types.InlineKeyboardButton("Начислить средства", callback_data="admin_credit_funds")
    markup.add(btn_addpromo, btn_viewpromos, btn_delpromo, btn_credit)
    try:
        bot.edit_message_text("Меню промокодов:", call.message.chat.id, call.message.message_id, reply_markup=markup)
    except Exception as e:
        print(f'[ERROR] Ошибка редактирования сообщения: {e}')

# Подменю для оповещений
@bot.callback_query_handler(func=lambda call: call.data == "admin_notifications")
def admin_notifications_menu(call):
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_announcement = types.InlineKeyboardButton("Сделать новость", callback_data="admin_announcement")
    btn_update = types.InlineKeyboardButton("Создать обновление", callback_data="admin_update")
    markup.add(btn_announcement, btn_update)
    try:
        bot.edit_message_text(
            "Меню оповещений:",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=markup
        )
    except Exception as e:
        print(f"[ERROR] Ошибка редактирования сообщения в admin_notifications: {e}")
        # Если редактирование не удалось – отправляем новое сообщение
        bot.send_message(call.message.chat.id, "Меню оповещений:", reply_markup=markup)


# Подменю для управления ролями
@bot.callback_query_handler(func=lambda call: call.data == "admin_roles")
def admin_roles_menu(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Нет прав доступа.")
        return
    markup = types.InlineKeyboardMarkup(row_width=3)
    btn_add = types.InlineKeyboardButton("Добавить роль", callback_data="admin_add_role")
    btn_modify = types.InlineKeyboardButton("Изменить роль", callback_data="admin_modify_role")
    btn_del = types.InlineKeyboardButton("Удалить роль", callback_data="admin_del_role")
    markup.add(btn_add, btn_modify, btn_del)
    try:
        bot.edit_message_text(
            "Меню управления ролями:",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=markup
        )
    except Exception as e:
        print(f"[ERROR] Ошибка редактирования сообщения в admin_roles: {e}")
        # Если редактирование не удалось – отправляем новое сообщение
        bot.send_message(call.message.chat.id, "Меню управления ролями:", reply_markup=markup)


# Начисление средств через username
@bot.callback_query_handler(func=lambda call: call.data == "admin_credit_funds")
def admin_credit_funds(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Нет прав доступа.")
        return
    msg = bot.send_message(call.message.chat.id,
                           "Введите username пользователя, количество монет и сообщение за что начисляются монеты через символ |.\n"
                           "Например: @user123|500|Пополнение за участие в мероприятии")
    bot.register_next_step_handler(msg, process_credit_funds)

def process_credit_funds(message):
    try:
        parts = message.text.split("|")
        if len(parts) != 3:
            raise ValueError
        target_username = parts[0].strip()
        if target_username.startswith("@"):
            target_username = target_username[1:]
        amount = int(parts[1].strip())
        reason = parts[2].strip()
    except Exception:
        bot.send_message(message.chat.id, "Неверный формат. Попробуйте снова.")
        return
    data = load_data()
    target_user_id = None
    for uid, user in data["users"].items():
        if user.get("telegram_username", "").lower() == target_username.lower():
            target_user_id = uid
            break
    if not target_user_id:
        bot.send_message(message.chat.id, "Пользователь не найден.")
        return
    data["users"][target_user_id]["balance"] = data["users"][target_user_id].get("balance", 0) + amount
    if "purchases" not in data["users"][target_user_id]:
        data["users"][target_user_id]["purchases"] = []
    data["users"][target_user_id]["purchases"].append({
        "item": f"Начисление средств: {reason}",
        "price": amount,
        "date": datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    })
    save_data(data)
    try:
        bot.send_message(target_user_id, f"На ваш счет начислено {amount}₽.\nПричина: {reason}\n(@{target_username})")
    except Exception:
        pass
    bot.send_message(message.chat.id, f"На счет пользователя @{target_username} начислено {amount}₽.\nПричина: {reason}")


# Обработчик для создания промокода
@bot.callback_query_handler(func=lambda call: call.data == "admin_add_promo")
def admin_add_promo_handler(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Нет прав доступа.")
        return
    msg = bot.send_message(call.message.chat.id,
                           "Введите промокод, бонус и число использований через пробел (например, PROMO 100 10):")
    bot.register_next_step_handler(msg, process_addpromo)

def process_addpromo(message):
    try:
        parts = message.text.split()
        if len(parts) != 3:
            raise ValueError
        code, bonus, max_uses = parts[0], int(parts[1]), int(parts[2])
    except Exception:
        bot.send_message(message.chat.id, "Неверный формат. Попробуйте снова.")
        return
    data = load_data()
    data["promo_codes"][code] = {"bonus": bonus, "max_uses": max_uses, "uses": 0}
    save_data(data)
    bot.send_message(message.chat.id, f"Промокод {code} добавлен: бонус {bonus}₽, {max_uses} использований.")

# Обработчик для просмотра промокодов
@bot.callback_query_handler(func=lambda call: call.data == "admin_view_promos")
def admin_view_promos_handler(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Нет прав доступа.")
        return
    data = load_data()
    promo_list = "Промокоды:\n"
    for code, promo in data["promo_codes"].items():
        promo_list += f"{code}: {promo['bonus']}₽, использовано {promo['uses']}/{promo['max_uses']}\n"
    bot.send_message(call.message.chat.id, promo_list)

# Обработчик для удаления промокода
@bot.callback_query_handler(func=lambda call: call.data == "admin_del_promo")
def admin_del_promo_handler(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Нет прав доступа.")
        return
    msg = bot.send_message(call.message.chat.id, "Введите промокод для удаления:")
    bot.register_next_step_handler(msg, process_delpromo)

def process_delpromo(message):
    code = message.text.strip()
    data = load_data()
    if code in data["promo_codes"]:
        data["promo_codes"].pop(code)
        save_data(data)
        bot.send_message(message.chat.id, f"Промокод {code} удалён.")
    else:
        bot.send_message(message.chat.id, "Промокод не найден.")

# Обработчики для управления ролями
@bot.callback_query_handler(func=lambda call: call.data == "admin_add_role")
def admin_add_role_prompt(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Нет прав доступа.")
        return
    msg = bot.send_message(call.message.chat.id, "Введите данные в формате: @username|Название роли")
    bot.register_next_step_handler(msg, process_add_role)

def process_add_role(message):
    try:
        username, role = message.text.split("|", 1)
        username = username.strip()
        role = role.strip()
    except Exception:
        bot.send_message(message.chat.id, "Неверный формат. Попробуйте снова.")
        return
    data = load_data()
    target_user_id = None
    for uid, user in data["users"].items():
        if user.get("telegram_username", "").lower() == username.replace("@", "").lower():
            target_user_id = uid
            break
    if not target_user_id:
        bot.send_message(message.chat.id, "Пользователь не найден.")
        return
    data["users"][target_user_id]["role"] = role
    save_data(data)
    bot.send_message(message.chat.id, f"Роль пользователя {username} назначена как '{role}'.")

@bot.callback_query_handler(func=lambda call: call.data == "admin_modify_role")
def admin_modify_role_prompt(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Нет прав доступа.")
        return
    msg = bot.send_message(call.message.chat.id, "Введите данные в формате: @username|Новое название роли")
    bot.register_next_step_handler(msg, process_modify_role)

def process_modify_role(message):
    try:
        username, role = message.text.split("|", 1)
        username = username.strip()
        role = role.strip()
    except Exception:
        bot.send_message(message.chat.id, "Неверный формат. Попробуйте снова.")
        return
    data = load_data()
    target_user_id = None
    for uid, user in data["users"].items():
        if user.get("telegram_username", "").lower() == username.replace("@", "").lower():
            target_user_id = uid
            break
    if not target_user_id:
        bot.send_message(message.chat.id, "Пользователь не найден.")
        return
    data["users"][target_user_id]["role"] = role
    save_data(data)
    bot.send_message(message.chat.id, f"Роль пользователя {username} изменена на '{role}'.")

@bot.callback_query_handler(func=lambda call: call.data == "admin_del_role")
def admin_del_role_prompt(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Нет прав доступа.")
        return
    msg = bot.send_message(call.message.chat.id, "Введите @username пользователя, у которого нужно удалить роль (сброс до 'игрок'):")
    bot.register_next_step_handler(msg, process_del_role)

def process_del_role(message):
    try:
        username = message.text.strip()
    except Exception:
        bot.send_message(message.chat.id, "Неверный формат. Попробуйте снова.")
        return
    data = load_data()
    target_user_id = None
    for uid, user in data["users"].items():
        if user.get("telegram_username", "").lower() == username.replace("@", "").lower():
            target_user_id = uid
            break
    if not target_user_id:
        bot.send_message(message.chat.id, "Пользователь не найден.")
        return
    data["users"][target_user_id]["role"] = "игрок"
    save_data(data)
    bot.send_message(message.chat.id, f"Роль пользователя {username} сброшена до 'игрок'.")




# ------------------- Функция "Сделать новость" -------------------
@bot.callback_query_handler(func=lambda call: call.data == "admin_announcement")
def admin_announcement(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Нет прав доступа.")
        return
    msg = bot.send_message(call.message.chat.id, 
                           "Введите текст новости.\nЕсли хотите добавить картинку, пришлите фото с подписью (текст подписи будет новостью).")
    bot.register_next_step_handler(msg, process_announcement)

def process_announcement(message):
    announcement_text = ""
    photo = None
    if message.content_type == "photo":
        photo = message.photo[-1].file_id  # Берем самое большое фото
        announcement_text = message.caption if message.caption else ""
    else:
        announcement_text = message.text
    data = load_data()
    # Рассылаем новость всем зарегистрированным игрокам
    for uid in data["users"]:
        try:
            if photo:
                bot.send_photo(uid, photo, caption=announcement_text)
            else:
                bot.send_message(uid, announcement_text)
        except Exception as e:
            print(f"Не удалось отправить новость пользователю {uid}: {e}")
    bot.send_message(message.chat.id, "Новость отправлена всем зарегистрированным игрокам.")

def process_update(message):
    update_text = ""
    photo = None
    if message.content_type == "photo":
        photo = message.photo[-1].file_id
        update_text = message.caption if message.caption else ""
    else:
        update_text = message.text

    data = load_data()
    delivered = 0

    for uid, user in data["users"].items():
        if user.get("subscribed", False):
            try:
                # Отправляем обновление
                if photo:
                    bot.send_photo(uid, photo, caption=update_text)
                else:
                    bot.send_message(uid, update_text)

                # Начисляем 1₽
                user["balance"] = user.get("balance", 0) + 1
                delivered += 1

            except Exception as e:
                print(f"Не удалось отправить обновление пользователю {uid}: {e}")

    save_data(data)

    bot.send_message(
        message.chat.id,
        f"✅ Обновление отправлено <b>{delivered}</b> подписанным на уведомления.\n"
        f"💸 Всем начислено по <b>+1₽</b>.",
        parse_mode="HTML"
    )

    # 🔽 Отправляем в тему Telegram-группы
    send_to_topic(
        chat_id=-1002353421985,
        thread_id=3,
        text=f"📢 <b>Обновление:</b>\n{update_text}",
        parse_mode="HTML"
    )


@bot.message_handler(commands=["ban"])
def handle_ban(message):
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "Нет доступа.")
        return

    try:
        _, identifier, reason = message.text.split(maxsplit=2)
    except ValueError:
        bot.send_message(message.chat.id, "Формат: /ban <ник или @username> <причина>")
        return

    data = load_data()
    identifier = identifier.strip().lower().lstrip("@")
    target_id = None

    for uid, user in data["users"].items():
        if identifier == user.get("nickname", "").lower() or identifier == user.get("telegram_username", "").lower():
            target_id = uid
            break

    if not target_id:
        bot.send_message(message.chat.id, "Пользователь не найден.")
        return

    user_data = data["users"].pop(target_id)
    data["banned_users"][target_id] = {
        "nickname": user_data.get("nickname", ""),
        "telegram_username": user_data.get("telegram_username", ""),
        "reason": reason,
        "ban_date": datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    }

    save_data(data)
    try:
        bot.send_message(int(target_id), f"⛔ Вы были забанены.\nПричина: {reason}")
    except:
        pass
    bot.send_message(message.chat.id, f"✅ Пользователь {target_id} забанен.")

@bot.message_handler(commands=["unban"])
def handle_unban(message):
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "Нет доступа.")
        return

    try:
        # Ожидается, что команда будет выглядеть как: /unban <ник или @username>
        _, identifier = message.text.split(maxsplit=1)
    except ValueError:
        bot.send_message(message.chat.id, "Формат: /unban <ник или @username>")
        return

    data = load_data()
    identifier = identifier.strip().lower().lstrip("@")
    target_id = None

    # Ищем пользователя в бан-листе по никнейму или telegram_username (приводим к нижнему регистру)
    for uid, user in data["banned_users"].items():
        if (identifier == user.get("nickname", "").lower() or 
            identifier == user.get("telegram_username", "").lower()):
            target_id = uid
            break

    if not target_id:
        bot.send_message(message.chat.id, "Пользователь не найден в бан-листе.")
        return

    # Извлекаем данные о разбане и добавляем пользователя обратно в "users"
    unbanned = data["banned_users"].pop(target_id)
    data["users"][target_id] = {
        "nickname": unbanned.get("nickname", ""),
        "telegram_username": unbanned.get("telegram_username", ""),
        "role": "игрок",
        "balance": 0,
        "purchases": [],
        "emojis": {},
        "approved": True,
        "registration_date": datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    }

    save_data(data)
    try:
        # Если target_id можно преобразовать в int (если требуется), иначе использовать target_id напрямую
        bot.send_message(target_id, "✅ Вы были разбанены.")
    except Exception as e:
        print(f"[ERROR] При отправке сообщения разбаненному пользователю: {e}")
    bot.send_message(message.chat.id, f"✅ Пользователь {target_id} разбанен.")


@bot.callback_query_handler(func=lambda call: call.data == "admin_bans")
def admin_bans_menu(call):
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("🔒 Забанить", callback_data="admin_ban_user"),
        types.InlineKeyboardButton("🔓 Разбанить", callback_data="admin_unban_user")
    )
    try:
        bot.edit_message_text("Меню управления банами:", call.message.chat.id,
                              call.message.message_id, reply_markup=markup)
    except Exception as e:
        print(f"[ERROR] Ошибка редактирования сообщения (admin_bans_menu): {e}")

@bot.callback_query_handler(func=lambda call: call.data == "admin_ban_user")
def admin_ban_prompt(call):
    msg = bot.send_message(call.message.chat.id, "Введите <b>@username|причина</b> для бана:", parse_mode="HTML")
    bot.register_next_step_handler(msg, process_admin_ban)

def process_admin_ban(message):
    try:
        identifier, reason = message.text.split("|", 1)
        identifier = identifier.strip().lower().lstrip("@")
        reason = reason.strip()
    except:
        bot.send_message(message.chat.id, "❌ Неверный формат. Пример: @user123|спам в чате")
        return

    data = load_data()
    target_id = None

    for uid, user in data["users"].items():
        if identifier == user.get("nickname", "").lower() or identifier == user.get("telegram_username", "").lower():
            target_id = uid
            break

    if not target_id:
        bot.send_message(message.chat.id, "❌ Пользователь не найден.")
        return

    user_data = data["users"].pop(target_id)
    data["banned_users"][target_id] = {
        "nickname": user_data.get("nickname", ""),
        "telegram_username": user_data.get("telegram_username", ""),
        "reason": reason,
        "ban_date": datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    }

    save_data(data)
    bot.send_message(message.chat.id, f"✅ Забанен @{identifier} по причине: {reason}")
    try:
        bot.send_message(int(target_id), f"⛔ Вы были забанены.\nПричина: {reason}")
    except:
        pass

@bot.callback_query_handler(func=lambda call: call.data == "admin_unban_user")
def admin_unban_prompt(call):
    msg = bot.send_message(call.message.chat.id, "Введите <b>@username</b> или ник для разбанивания:", parse_mode="HTML")
    bot.register_next_step_handler(msg, process_admin_unban)

def process_admin_unban(message):
    identifier = message.text.strip().lower().lstrip("@")
    data = load_data()
    target_id = None

    for uid, user in data["banned_users"].items():
        if identifier == user.get("nickname", "").lower() or identifier == user.get("telegram_username", "").lower():
            target_id = uid
            break

    if not target_id:
        bot.send_message(message.chat.id, "❌ Пользователь не найден в бан-листе.")
        return

    unbanned = data["banned_users"].pop(target_id)
    data["users"][target_id] = {
        "nickname": unbanned.get("nickname", ""),
        "telegram_username": unbanned.get("telegram_username", ""),
        "role": "игрок",
        "balance": 0,
        "purchases": [],
        "emojis": {},
        "approved": True,
        "registration_date": datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    }

    save_data(data)
    bot.send_message(message.chat.id, f"✅ Пользователь @{identifier} разбанен.")
    try:
        bot.send_message(int(target_id), "✅ Вы были разбанены.")
    except:
        pass

# ------------------- Окно BV# -------------------
@bot.callback_query_handler(func=lambda call: call.data in ["subscribe_bv_plus", "subscribe_bv_plus_market"])
def show_bv_plus_window(call):
    bv_description = (
        "✨ <b>Подписка BV#</b> — выделяйся среди игроков и получай бонусы!\n\n"
        "💰 <b>Только сейчас:</b> первый месяц — <u>со скидкой</u> <b>169₽</b>, затем <b>199₽/мес</b>\n"
        "🎁 <b>Подарок:</b> кейс <i>«Командный блок»</i> за каждую покупку или продление\n"
        "🎨 <b>Цвет ника:</b> выбери <u>любой</u> цвет ника в Minecraft\n"
        "😎 <b>Эмодзи:</b> доступ ко <u>всем платным</u> эмодзи (кроме Незеритовых) <i>на время подписки</i>\n"
        "🌟 <b>Плюс:</b> навсегда получаешь <u>уникальный эмодзи</u>\n\n"
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
        bot.send_message(call.message.chat.id, "BV# уже активна!", reply_markup=get_welcome_markup(str(call.from_user.id)))
        return
    price = 169
    if user.get("balance", 0) < price:
        bot.send_message(call.message.chat.id, "Недостаточно средств для активации BV#.", reply_markup=get_welcome_markup(str(call.from_user.id)))
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
        reply_markup=get_welcome_markup(str(call.from_user.id))
    )


# ------------------- Логика выдачи эмодзи и кейсов -------------------
def award_emoji(user_id, category_index):
    data = load_data()
    user = data["users"].get(user_id)

    if not user:
        return None, "Пользователь не найден."
    if "emojis" not in user:
        user["emojis"] = {}
    cat_key = str(category_index)
    if cat_key not in user["emojis"]:
        user["emojis"][cat_key] = []
    owned = user["emojis"][cat_key]
    total = emoji_details[category_index]["quantity"]
    if len(owned) >= total:
        return None, f"Вы уже собрали все эмодзи в категории {emoji_details[category_index]['name']}."
    available = [num for num in range(1, total + 1) if num not in owned]
    awarded = random.choice(available)
    user["emojis"][cat_key].append(awarded)
    if "purchases" not in user:
        user["purchases"] = []
    user["purchases"].append({
        "item": f"Получено из кейса: {emoji_details[category_index]['name']} №{awarded}",
        "price": 0,
        "date": datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    })
    save_data(data)
    return awarded, None

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


def get_path(filename):
    return os.path.join(os.path.dirname(__file__), filename)

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
        "Добро пожаловать! Введите ваш никнейм для регистрации."
    )
    user_states[user_id] = {"state": "awaiting_nickname", "temp_data": {}}



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

@bot.message_handler(func=lambda message: str(message.from_user.id) in user_states 
                    and user_states[str(message.from_user.id)].get("state") == "awaiting_referral")
def handle_referral(message):
    user_id = str(message.from_user.id)
    text = message.text.strip()
    temp_data = user_states[user_id]["temp_data"]

    # Получаем данные пользователя (уже введённые или полученные с предыдущих шагов)
    user_nickname = temp_data.get("nickname", "").lower()  # введённый ник
    user_username = message.from_user.username.lower() if message.from_user.username else ""

    # Обработка ввода реферала
    if text.lower() == "пропустить":
        temp_data["referral"] = None
    else:
        # Если в реферале введено два значения через запятую
        if "," in text:
            parts = text.split(",", 1)
            ref_nick = parts[0].strip()
            ref_username = parts[1].strip()
            if ref_username.startswith("@"):
                ref_username = ref_username[1:]
            ref_nick_lower = ref_nick.lower()
            ref_username_lower = ref_username.lower()
            # Если игрок указывает себя (по нику или юзернейму)
            if (user_nickname and ref_nick_lower == user_nickname) or (user_username and ref_username_lower == user_username):
                bot.send_message(message.chat.id, 
                                 "Нельзя указывать себя в качестве реферала! Пожалуйста, введите ник другого игрока или напишите 'пропустить'.")
                return
            temp_data["referral"] = {"nickname": ref_nick, "telegram_username": ref_username}
        else:
            ref_input = text.lower()
            # Если введён один текст, сравниваем сразу с ником и юзернеймом
            if (user_nickname and ref_input == user_nickname) or (user_username and ref_input == user_username):
                bot.send_message(message.chat.id, 
                                 "Нельзя указывать себя в качестве реферала! Пожалуйста, введите ник другого игрока или напишите 'пропустить'.")
                return
            temp_data["referral"] = text

    bot.send_message(message.chat.id, "Реферальная информация принята.", reply_markup=types.ReplyKeyboardRemove())
    
    # Дополнительные данные пользователя
    temp_data["telegram_username"] = message.from_user.username if message.from_user.username else ""
    temp_data["registration_date"] = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    
    data = load_data()
    temp_data.setdefault("balance", 0)
    temp_data.setdefault("purchases", [])
    temp_data.setdefault("promo_codes_used", [])
    temp_data.setdefault("emojis", {})
    data["users"][user_id] = temp_data

    # Формирование строки для уведомления (referral_text)
    referral_info = temp_data.get("referral", "Нет")
    if isinstance(referral_info, dict):
        referral_text = f"{referral_info['nickname']} (@{referral_info['telegram_username']})"
    else:
        referral_text = referral_info

    # Если пользователь несовершеннолетний и не оформил полный доступ – регистрация с ограничениями
    if temp_data.get("is_minor") and not temp_data.get("full_access"):
        save_data(data)
        bot.send_message(
            message.chat.id,
            "Регистрация завершена с ограниченным доступом. Для получения полного доступа перейдите в меню и оформите проход за 250₽.",
            reply_markup=minor_get_welcome_markup(user_id)
        )
    else:
        # Для взрослых или несовершеннолетних с полным доступом – отправляем заявку админу
        data["registration_requests"].append({
            "user_id": user_id,
            "nickname": temp_data["nickname"],
            "age": temp_data["age"],
            "registration_date": temp_data["registration_date"],
            "referral": referral_text
        })
        save_data(data)
        bot.send_message(
            message.chat.id,
            "Ваша заявка отправлена на рассмотрение. Ожидайте ответа администрации.",
            reply_markup=get_welcome_markup(user_id)
        )
        admin_markup = types.InlineKeyboardMarkup()
        btn_approve = types.InlineKeyboardButton("Принять ✅", callback_data=f"approve_{user_id}")
        btn_reject = types.InlineKeyboardButton("Отклонить ❌", callback_data=f"reject_{user_id}")
        admin_markup.add(btn_approve, btn_reject)
        bot.send_message(
            ADMIN_ID,
            f"Новая заявка на регистрацию 😃:\nНикнейм: {temp_data['nickname']}\nВозраст: {temp_data['age']}\nЮзернейм: {temp_data['telegram_username']}\nРеферал: {referral_text}",
            reply_markup=admin_markup
        )
    user_states.pop(user_id, None)


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
        bot.send_message(int(user_id), welcome_text, reply_markup=get_welcome_markup(str(call.from_user.id)))
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
@bot.callback_query_handler(func=lambda call: call.data.startswith("menu_"))
def handle_main_menu(call):
    user_id = str(call.from_user.id)
    data = load_data()

    if user_id not in data["users"] or (not data["users"][user_id].get("approved", False) and not data["users"][user_id].get("is_minor", False)):
        bot.answer_callback_query(call.id, "Вы не зарегистрированы.")
        return

    if call.data == "menu_profile":
        user = data["users"][user_id]
        reg_date = user.get("registration_date", "").split()[0] if user.get("registration_date") else ""
        bv_status = "активна" if user.get("bv_plus") else "неактивна"
        role = user.get("role", "игрок")
        max_streak = user.get("max_login_streak", user.get("login_streak", 0))
        ender_eyes = user.get("ender_eyes", 0)

        profile_text = (
    f"👤 <b>Ваш профиль</b>\n"
    f"━━━━━━━━━━━━━━━━\n"
    f"⭐ <b>BV#</b>: {bv_status}\n"
    f"🏷️ <b>Ник</b>: {user.get('nickname', '')}\n"
    f"🙍 <b>Роль</b>: {role}\n"
    f"🏰 <b>Трайб</b>: {'Не состоит' if 'tribe' not in user else user['tribe']}\n"
    f"🔥 <b>Макс. стрик</b>: {max_streak} дней\n"
    f"🧿 Око эндера: {ender_eyes}\n"
    f"📅 <b>Регистрация</b>: {reg_date}\n\n"
    f"💰 <b>Баланс</b>: {user.get('balance', 0)}₽\n"
    f"😊 <b>Эмодзи</b>:\n"
     )


        emojis = user.get("emojis", {})
        if not emojis:
            profile_text += "Пока тут пусто"
        else:
            for cat_key, nums in emojis.items():
                cat_index = int(cat_key)
                cat_name = emoji_details[cat_index]["name"]
                nums_str = ", ".join(str(n) for n in nums)
                profile_text += f"{cat_name}: {nums_str}\n"

        bot.send_message(call.message.chat.id, profile_text, parse_mode="HTML", reply_markup=profile_menu_markup())

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
        send_or_edit_message(bot, call, MARKET_WELCOME_TEXT, market_main_markup())

    elif call.data in ["customization", "customization_back"]:
        send_or_edit_message(bot, call, CUSTOMIZATION_TEXT, customization_markup())

    elif call.data == "custom_emoji":
        show_emoji_info(call.message.chat.id, call.message.message_id, 0)

    elif call.data == "custom_case":
        show_case_info(call.message.chat.id, call.message.message_id, 0)

    elif call.data == "market_services":
        send_or_edit_message(bot, call, MARKET_SERVICES_TEXT, top_services_markup())


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

@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_emoji_"))
def handle_buy_emoji(call):
    user_id = str(call.from_user.id)
    index = int(call.data.split("_")[-1])
    user_states[user_id] = user_states.get(user_id, {})
    user_states[user_id]["buy_emoji_category"] = index
    bot.send_message(call.message.chat.id, "Введите номер эмодзи, который хотите приобрести:")

@bot.message_handler(func=lambda message: "buy_emoji_category" in user_states.get(str(message.from_user.id), {}))
def process_emoji_choice(message):
    user_id = str(message.from_user.id)
    try:
        choice = int(message.text.strip())
    except ValueError:
        bot.send_message(message.chat.id, "Введите корректный номер (число).")
        return
    category_index = user_states[user_id].pop("buy_emoji_category")
    total = emoji_details[category_index]["quantity"]
    if not (1 <= choice <= total):
        bot.send_message(message.chat.id, f"Номер должен быть от 1 до {total}. Попробуйте снова:")
        user_states[user_id]["buy_emoji_category"] = category_index
        return
    data = load_data()
    user = data["users"].get(user_id)
    if not user:
        bot.send_message(message.chat.id, "Ошибка: пользователь не найден.")
        return
    if "emojis" not in user:
        user["emojis"] = {}
    cat_key = str(category_index)
    if cat_key not in user["emojis"]:
        user["emojis"][cat_key] = []
    if choice in user["emojis"][cat_key]:
        bot.send_message(message.chat.id, f"Эмодзи №{choice} уже приобретён в категории {emoji_details[category_index]['name']}.")
        return
    cost = emoji_details[category_index]["price"]
    subscription_active = True if user.get("bv_plus") else False
    if subscription_active and category_index != 4:
        cost = 0
    if user.get("balance", 0) < cost:
        bot.send_message(message.chat.id, "Недостаточно средств.")
        return
    user["balance"] -= cost
    user["emojis"][cat_key].append(choice)
    if "purchases" not in user:
        user["purchases"] = []
    user["purchases"].append({
        "item": f"Куплено {emoji_details[category_index]['name']} №{choice}",
        "price": cost,
        "date": datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    })
    save_data(data)
    bot.send_message(message.chat.id, f"Вы успешно приобрели {emoji_details[category_index]['name']} №{choice} за {cost}₽.")
    
    # Отправляем уведомление админу
    nickname = user.get("nickname", "Неизвестный")
    admin_msg = f"Покупка эмодзи: Пользователь {nickname} приобрел {emoji_details[category_index]['name']} №{choice} за {cost}₽."
    bot.send_message(ADMIN_ID, admin_msg)
    
@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_case_"))
def handle_buy_case(call):
    user_id = str(call.from_user.id)
    data = load_data()
    if user_id not in data["users"]:
        bot.answer_callback_query(call.id, "Вы не зарегистрированы.")
        return
    index = int(call.data.split("_")[-1])
    case_item = case_details[index]
    if data["users"][user_id].get("balance", 0) < case_item["price"]:
        bot.answer_callback_query(call.id, "Недостаточно средств.")
        return
    data["users"][user_id]["balance"] -= case_item["price"]
    if "purchases" not in data["users"][user_id]:
        data["users"][user_id]["purchases"] = []
    data["users"][user_id]["purchases"].append({
        "item": f"Куплен {case_item['name']}",
        "price": case_item["price"],
        "date": datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    })
    save_data(data)
    bot.answer_callback_query(call.id, "Покупка успешна.")
    
    # Определяем результат кейса
    if index == 0:
        possible = [0, 1]
        bonus_chance = case_item["chance"]
    elif index == 1:
        possible = [1, 2]
        bonus_chance = case_item["chance"]
    elif index == 2:
        possible = [3, 4]
        bonus_chance = case_item["chance"]
    else:
        possible = []
        bonus_chance = 0
    cat_guaranteed = random.choice(possible)
    awarded1, err1 = award_emoji(user_id, cat_guaranteed)
    if err1:
        result_guaranteed = f"Ошибка: {err1}"
    else:
        result_guaranteed = f"{emoji_details[cat_guaranteed]['name']} №{awarded1}"
    message_text = f"Кейс куплен. Получено: {result_guaranteed}."
    if random.randint(1, 100) <= bonus_chance:
        if random.choice([True, False]):
            cat_bonus = random.choice(possible)
            awarded_bonus, err_bonus = award_emoji(user_id, cat_bonus)
            if awarded_bonus:
                message_text += f" Бонус: дополнительно получено 2 эмодзи из {emoji_details[cat_bonus]['name']}: №{awarded_bonus}."
        else:
            bonus_msgs = []
            for cat in possible:
                awarded_bonus, err_bonus = award_emoji(user_id, cat)
                if awarded_bonus:
                    bonus_msgs.append(f"{emoji_details[cat]['name']} №{awarded_bonus}")
            if bonus_msgs:
                message_text += " Бонус: получены эмодзи: " + ", ".join(bonus_msgs) + "."
    bot.send_message(call.message.chat.id, message_text)
    
    # Отправляем уведомление администратору
    user = data["users"][user_id]
    nickname = user.get("nickname", "Неизвестный")
    admin_msg = (f"Покупка кейса: Пользователь {nickname} купил {case_item['name']} за {case_item['price']}₽. "
                 f"Выпало: {result_guaranteed}.")
    bot.send_message(ADMIN_ID, admin_msg)



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
                reply_markup=get_welcome_markup(str(call.from_user.id))
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
    status = user.get("status", "user")
    role = user.get("role", "—")
    nickname = user.get("nickname", "—")
    bvtag = user.get("bvtag", "—")
    reg_date = user.get("registration_date", "—")
    max_streak = user.get("max_login_streak", 0)
    user_id = user.get("user_id", "—")
    tribe = user.get("tribe", "—")

    if status == "user":
        return (
            f"👤 <b>Профиль: {nickname}</b>\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"⭐ <b>BV#:</b> {bvtag}\n"
            f"🏷️ <b>Ник:</b> {nickname}\n"
            f"🎭 <b>Роль:</b> {role}\n"
            f"🏰 <b>Трайб:</b> {tribe}\n"
            f"🔥 <b>Макс. стрик:</b> {max_streak} дней\n"
            f"📅 <b>Регистрация:</b> {reg_date}"
        )
    elif status == "minor":
        return (
            f"🧒 <b>Несовершеннолетний:</b> {nickname}\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"⭐ <b>BV#:</b> {bvtag}\n"
            f"📛 <b>Ограничения:</b> до 14 лет\n"
            f"📅 <b>Регистрация:</b> {reg_date}"
        )
    elif status == "banned":
        reason = user.get("ban_reason", "не указана")
        return (
            f"🚫 <b>Забанен:</b> {nickname}\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"⭐ <b>BV#:</b> {bvtag}\n"
            f"📛 <b>Причина бана:</b> {reason}\n"
            f"📅 <b>Регистрация:</b> {reg_date}"
        )
    else:
        return f"⚠️ Неизвестный статус для игрока <code>{user_id}</code>"


@bot.callback_query_handler(func=lambda call: call.data == "search_players")
def search_players_prompt_new(call):
    msg = bot.send_message(call.message.chat.id, "🔍 Введите ник, юзернейм или ID:")
    bot.register_next_step_handler(msg, process_player_search)
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
    btn_back = types.InlineKeyboardButton("Назад 🔙", callback_data="get_welcome_markup")
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
        types.InlineKeyboardButton("📜 Все трайбы", callback_data="list_tribes"),
        types.InlineKeyboardButton("🧑‍🤝‍🧑 Игроки", callback_data="search_players")
    )
    keyboard.row(
        types.InlineKeyboardButton("🔙 Главное меню", callback_data="get_welcome_markup")
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
    for tribe in data.get("tribes", {}).values():
        for req in tribe.get("join_requests", []):
            if req["user_id"] == user_id:
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
        "join_requests": []
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
    data = load_data()
    tribes = list(data.get("tribes", {}).values())
    per_page = 5
    total_pages = (len(tribes) + per_page - 1) // per_page
    if not tribes:
        bot.edit_message_text("😔 Нет созданных трайбов.", call.message.chat.id, call.message.message_id)
        return
    if page < 0 or page >= total_pages:
        bot.answer_callback_query(call.id, "❌ Нет такой страницы.")
        return
    start = page * per_page
    end = start + per_page
    current_tribes = tribes[start:end]
    text = "📜 <b>Список трайбов:</b>\n━━━━━━━━━━━━━━━━\n"
    text += "Укажите <b>[ID]</b> нужного трайба после нажатия кнопки.\n\n"
    for i, tribe in enumerate(current_tribes, start=start+1):
        text += (f"{i}. <b>{tribe['name']}</b> [{tribe['id']}]\n"
                 f"   👥 Участников: {len(tribe['members'])}/{tribe.get('max_members', 10)}\n"
                 f"   📅 Создан: {tribe['date_created']}\n"
                 f"   📝 {tribe['desc'][:100]}...\n\n")
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
    try:
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="HTML")
    except Exception as e:
        print(f"[ERROR] Ошибка редактирования сообщения: {e}")

# -------------------- Подача заявки на вступление --------------------
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
    for tribe in data.get("tribes", {}).values():
        for req in tribe.get("join_requests", []):
            if req["user_id"] == user_id:
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
        types.InlineKeyboardButton("Изменить описание", callback_data="edit_tribe_desc"),
        types.InlineKeyboardButton("Изменить ID (50₽)", callback_data="edit_tribe_id"),
        types.InlineKeyboardButton("Назначить помощника", callback_data="assign_tribe_helper")
    )
    kb.row(types.InlineKeyboardButton("🔙 Назад", callback_data="view_tribe"))
    return kb

def clan_management_markup():
    kb = types.InlineKeyboardMarkup()
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
    tribe["desc"] = new_desc
    save_data(data)
    bot.send_message(message.chat.id, "✅ Описание трайба обновлено.", reply_markup=clan_edit_markup())

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
    text = (
        f"🏰 <b>Ваш трайб</b>\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"📛 <b>Название и ID:</b> {tribe['name']} [{tribe['id']}]\n"
        f"📝 <b>Описание:</b> {tribe['desc']}\n"
        f"📅 <b>Дата создания:</b> {tribe['date_created']}\n"
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



#--------------------Реферал---------------------------

@bot.message_handler(func=lambda message: str(message.from_user.id) in user_states and user_states[str(message.from_user.id)].get("state") == "awaiting_referral")
def handle_referral(message):
    user_id = str(message.from_user.id)
    text = message.text.strip()
    temp_data = user_states[user_id]["temp_data"]
    if text.lower() == "пропустить":
        temp_data["referral"] = None
    else:
        if "," in text:
            parts = text.split(",", 1)
            ref_nick = parts[0].strip()
            ref_username = parts[1].strip()
            if ref_username.startswith("@"):
                ref_username = ref_username[1:]
            temp_data["referral"] = {"nickname": ref_nick, "telegram_username": ref_username}
        else:
            temp_data["referral"] = text
    bot.send_message(message.chat.id, "Реферальная информация принята.", reply_markup=types.ReplyKeyboardRemove())
    temp_data["telegram_username"] = message.from_user.username if message.from_user.username else ""
    temp_data["registration_date"] = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    data = load_data()
    temp_data.setdefault("balance", 0)
    temp_data.setdefault("purchases", [])
    temp_data.setdefault("promo_codes_used", [])
    temp_data.setdefault("emojis", {})
    data["users"][user_id] = temp_data
    referral_info = temp_data.get("referral", "Нет")
    if isinstance(referral_info, dict):
        referral_text = f"{referral_info['nickname']} (@{referral_info['telegram_username']})"
    else:
        referral_text = referral_info
    data["registration_requests"].append({
        "user_id": user_id,
        "nickname": temp_data["nickname"],
        "age": temp_data["age"],
        "registration_date": temp_data["registration_date"],
        "referral": referral_text
    })
    save_data(data)

#------------------- Стрики ----------------------

@bot.message_handler(commands=["streak"])
def handle_streak(message):
    user_id = str(message.from_user.id)
    data = load_data()
    user = data["users"].get(user_id)

    if not user or not user.get("approved", False):
        bot.send_message(message.chat.id, "Вы не зарегистрированы или ваша заявка не одобрена.")
        return

    streak = user.get("login_streak", 0)
    max_streak = user.get("max_login_streak", 0)
    last_login = user.get("last_login", "никогда")
    # Определяем ранг
    if streak < 7:
        rank = "Новичок 🟢"
    elif streak < 15:
        rank = "Надежный 🔵"
    elif streak < 30:
        rank = "Упорный 🟡"
    else:
        rank = "Легенда 🔴"
    fire = "🔥" * min(streak % 10 if streak % 10 != 0 else 10, 10)
    bar = f"[{fire}{'▫️' * (10 - len(fire))}]"
    ender_eyes = user.get("ender_eyes", 0)

    bot.send_message(
        message.chat.id,
        f"<b>🔥 Ваш текущий стрик</b>\n"
        f"{bar}\n\n"
        f"📅 Последний вход: {last_login}\n"
        f"📈 Текущий стрик: {streak} дней\n"
        f"🏅 Ранг: {rank}\n"
        f"🔝 Макс. стрик: {max_streak} дней\n"
        f"🧿 Ока эндера: {ender_eyes}",
        parse_mode="HTML"
    )

def update_streak(user_id):
    """
    Обновлённая система стриков:
    🔹 Каждый день логина начисляется Око эндера: +1, 
       а каждые 10-й день дают +5 Ока эндера.
    🎲 5% шанс на удвоение награды (Ока эндера).
    ➕ Иногда дополнительно начисляются монеты за активность.
    🔥 Отправляется уведомление с прогресс-баром и рангом.
    """
    data = load_data()
    user = data["users"].get(user_id, {})

    today_str = datetime.now().strftime("%Y-%m-%d")
    yesterday_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    # Если пользователь уже заходил сегодня, ничего не начисляем
    if user.get("last_login") == today_str:
        return None, user.get("login_streak", 0)

    # Определяем текущий стрик
    if user.get("last_login") == yesterday_str:
        streak = user.get("login_streak", 0) + 1
    else:
        streak = 1

    user["login_streak"] = streak
    user["last_login"] = today_str
    if streak > user.get("max_login_streak", 0):
        user["max_login_streak"] = streak

    # -------------------------------
    # Награда – Око эндера (🧿):
    # Базовая награда: 1 за обычный день, 5 если стрик кратен 10
    ender_reward = 5 if streak % 10 == 0 else 1

    # 5% шанс удвоить награду
    if random.random() < 0.05:
        ender_reward *= 2
        bot.send_message(user_id, "🎉 Вам повезло! Двойная награда!")

    # Если у пользователя нет поля "ender_eyes", инициализируем его
    current_ender = user.get("ender_eyes", 0)
    user["ender_eyes"] = current_ender + ender_reward

    # -------------------------------
    # Дополнительная награда – монеты
    additional_coins = 0
    # Например, с 20% шансом начисляем от 1 до 5 монет
    if random.random() < 0.20:
        additional_coins = random.randint(1, 5)
        user["balance"] = user.get("balance", 0) + additional_coins

    # -------------------------------
    # Определяем ранг пользователя по стрику
    if streak < 7:
        rank = "Новичок 🟢"
    elif streak < 15:
        rank = "Надежный 🔵"
    elif streak < 30:
        rank = "Упорный 🟡"
    else:
        rank = "Легенда 🔴"

    # Отправляем уведомление, если еще не уведомляли сегодня
    if user.get("streak_notified_date") != today_str:
        fire = "🔥" * min(streak % 10 if streak % 10 != 0 else 10, 10)
        bar = f"[{fire}{'▫️' * (10 - len(fire))}]"
        reward_text = f"🧿 Награда: {ender_reward} Ока эндера"
        if additional_coins:
            reward_text += f" и 💰 {additional_coins} монет"
        bot.send_message(
            user_id,
            f"Ваш стрик продлен!\n{bar}\n"
            f"Текущий стрик: {streak} дней\n"
            f"Ранг: {rank}\n"
            f"{reward_text}"
        )
        user["streak_notified_date"] = today_str

    data["users"][user_id] = user
    save_data(data)
    return ender_reward, streak


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




#------------------- Подарок ----------------------
@bot.callback_query_handler(func=lambda call: call.data == "daily_gift")
def handle_daily_gift(call):
    user_id = str(call.from_user.id)
    data = load_data()
    if user_id not in data["users"]:
        bot.answer_callback_query(call.id, "Сначала зарегистрируйтесь, чтобы получать подарки!")
        return

    user = data["users"][user_id]
    today_str = datetime.now().strftime("%Y-%m-%d")

    # Проверяем, не получал ли пользователь подарок сегодня
    if user.get("last_daily_gift") == today_str:
        bot.answer_callback_query(call.id, "Вы уже получили подарок сегодня. Приходите завтра!")
        return

    # Если пользователь не получал подарок сегодня, выполняем логику выдачи:
    # Инициализируем, если ещё нет поля
    if "ender_eyes" not in user:
        user["ender_eyes"] = 0

    # Определяем награду случайным образом по следующим вероятностям:
    # Jackpot: 1% (0.01); Комбинированная: 9% (0.09); Только монеты: 20% (0.20); Только ОК эндера: 70%
    rnd = random.random()
    reward_text = ""
    # Jackpot награда
    if rnd < 0.01:
        if random.choice([True, False]):
            coins = 10
            user["balance"] = user.get("balance", 0) + coins
            reward_text = f"Jackpot! Вы получили {coins} 💰 монет!"
        else:
            eyes = 10
            user["ender_eyes"] += eyes
            reward_text = f"Jackpot! Вы получили {eyes} 🧿 Ока эндера!"
    # Комбинированная награда
    elif rnd < 0.01 + 0.09:
        eyes = random.randint(1, 5)
        coins = random.randint(1, 5)
        user["ender_eyes"] += eyes
        user["balance"] = user.get("balance", 0) + coins
        reward_text = f"Вам выпал комбинированный подарок!\n🧿 Ока эндера: {eyes}\n💰 Монет: {coins}"
    # Только монеты
    elif rnd < 0.01 + 0.09 + 0.20:
        coins = random.randint(1, 5)
        user["balance"] = user.get("balance", 0) + coins
        reward_text = f"Вы получили {coins} 💰 монет!"
    # Только ОК эндера
    else:
        eyes = random.randint(1, 5)
        user["ender_eyes"] += eyes
        reward_text = f"Вы получили {eyes} 🧿 Ока эндера!"

    # Обновляем дату последнего получения подарка
    user["last_daily_gift"] = today_str
    data["users"][user_id] = user
    save_data(data)

    bot.answer_callback_query(call.id, reward_text)
    bot.send_message(call.message.chat.id, f"🎁 {reward_text}", reply_markup=market_main_markup())

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


#------------------- Бот в группе ----------------------
@bot.message_handler(func=lambda m: m.chat.type in ["group", "supergroup"] and m.reply_to_message)
def handle_reply_logic(m):
    if m.chat.id != -1002353421985 or m.message_thread_id != 28:
        return

    text = m.text.strip().lower()

    # ===== "КТО ЭТО"
    if text in ["кто это", "кто он", "кто она", "кто такой", "кто такая"]:
        target_user = m.reply_to_message.from_user
        if not target_user:
            return

        target_id = str(target_user.id)
        data = load_data()

        if target_id not in data["users"]:
            bot.reply_to(m, "❌ Игрок не найден в базе.")
            return

        user = data["users"][target_id]
        user["status"] = "user"
        user["user_id"] = target_id
        msg = render_search_profile(user)
        bot.reply_to(m, msg, parse_mode="HTML")
        return

    # ===== "ПОДАРОК"
    if text in ["подарок", "/подарок", "дай подарок", "хочу подарок"]:
        user_id = str(m.from_user.id)
        data = load_data()
        user = data["users"].get(user_id)

        if not user:
            bot.send_message(m.chat.id, "❌ Вы не зарегистрированы.", message_thread_id=m.message_thread_id)
            return

        today_str = datetime.now().strftime("%Y-%m-%d")
        if user.get("last_daily_gift") == today_str:
            bot.send_message(m.chat.id, "🎁 Вы уже получили подарок сегодня.", message_thread_id=m.message_thread_id)
            return

        reward_text = ""
        rnd = random.random()
        if rnd < 0.01:
            if random.choice([True, False]):
                coins = 10
                user["balance"] += coins
                reward_text = f"Jackpot! {coins} 💰 монет"
            else:
                eyes = 10
                user["ender_eyes"] += eyes
                reward_text = f"Jackpot! {eyes} 🧿 Ока эндера"
        elif rnd < 0.10:
            eyes = random.randint(1, 5)
            coins = random.randint(1, 5)
            user["ender_eyes"] += eyes
            user["balance"] += coins
            reward_text = f"🎁 Комбинированный: {eyes} 🧿 и {coins} 💰"
        elif rnd < 0.30:
            coins = random.randint(1, 5)
            user["balance"] += coins
            reward_text = f"{coins} 💰 монет"
        else:
            eyes = random.randint(1, 5)
            user["ender_eyes"] += eyes
            reward_text = f"{eyes} 🧿 Ока эндера"

        user["last_daily_gift"] = today_str
        save_data(data)

        nickname = user.get("nickname", m.from_user.username or "Игрок")
        bot.send_message(m.chat.id, f"✅ Вы получили: {reward_text}", message_thread_id=m.message_thread_id)
        bot.send_message(m.chat.id, f"🎉 Подарок: {nickname} получил {reward_text}!", message_thread_id=m.message_thread_id)
        return

    # ===== "ТРАЙБЫ"
    if text in ["трайбы", "/трайбы", "список трайбов", "все трайбы"]:
        data = load_data()
        tribes = list(data.get("tribes", {}).values())

        if not tribes:
            bot.send_message(m.chat.id, "😔 Нет созданных трайбов.", message_thread_id=m.message_thread_id)
            return

        text = "📜 <b>Список трайбов:</b>\n━━━━━━━━━━━━━━━━\n"
        for tribe in tribes:
            name = tribe.get("name", "Без названия")
            tid = tribe.get("id", "???")
            members = len(tribe.get("members", []))
            desc = tribe.get("desc", "Без описания")
            created = tribe.get("date_created", "—")
            text += f"<b>{name}</b> [{tid}]\n👥 {members}/10 | 📅 {created}\n📝 {desc[:80]}...\n\n"

        bot.send_message(m.chat.id, text.strip(), parse_mode="HTML", message_thread_id=m.message_thread_id)

@bot.message_handler(commands=["тестновость"])
def test_news_topic(message):
    if message.chat.type != "private" or message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "⛔ Команда доступна только админу в ЛС.")
        return

    try:
        bot.send_message(
            chat_id=-1002353421985,
            message_thread_id=28,
            text="🧪 <b>Тестовая новость</b>\nЕсли ты это видишь — бот может писать в тему.",
            parse_mode="HTML"
        )
        bot.reply_to(message, "✅ Сообщение отправлено в тему 📢 Новости и обновления.")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка при отправке: {e}")


bot.infinity_polling(timeout=90, long_polling_timeout=45)





