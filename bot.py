# Pill reminder bot – GitHub Actions version (3h window, max 12 reminders)

import os
import json
from datetime import datetime, time
from zoneinfo import ZoneInfo

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
# ВСТАВ СВІЙ РЕАЛЬНИЙ ТОКЕН СЮДИ
BOT_TOKEN = "8513409579:AAE9yAxqjq6_QekGvb30GRKezOW5-uKMFrc"
# <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<

DATA_FILE = "users.json"
TZ = ZoneInfo("Europe/Madrid")

MAX_REMINDERS = 12          # максимум нагадувань за день
REMINDER_INTERVAL = 15 * 60 # 15 хв у секундах
END_TIME = time(hour=14, minute=0, tzinfo=TZ)  # після 14:00 не шлемо нічого


def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start – підписує юзера на нагадування."""
    user_id = str(update.effective_user.id)
    data = load_data()

    if user_id not in data:
        data[user_id] = {
            "confirmed_today": False,
            "reminders_sent": 0,
            "date": datetime.now(TZ).date().isoformat(),
        }
        save_data(data)

    await update.message.reply_text(
        "Гаразд, я буду щодня об 11:00 нагадувати про таблетку 😊"
    )


def _keyboard():
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("Так", callback_data="confirm_yes")]]
    )


async def send_first_prompt(context: ContextTypes.DEFAULT_TYPE):
    """Перший пуш о 11:00 – обнуляємо лічильники та питаємо про таблетку."""
    data = load_data()
    now = datetime.now(TZ)
    today = now.date().isoformat()
    kb = _keyboard()

    for user_id in data.keys():
        data[user_id]["confirmed_today"] = False
        data[user_id]["reminders_sent"] = 0
        data[user_id]["date"] = today

        await context.bot.send_message(
            chat_id=int(user_id),
            text="Ти випила таблетку?",
            reply_markup=kb,
        )

    save_data(data)


async def send_reminder(context: ContextTypes.DEFAULT_TYPE):
    """
    Кожні 15 хв відправляємо нагадування:
    – тільки до 14:00
    – максимум 12 разів на день на користувача
    – зупиняємось для юзера, коли він натиснув 'Так'
    """
    now = datetime.now(TZ)
    if now.time() > END_TIME:
        return

    data = load_data()
    kb = _keyboard()
    today = now.date().isoformat()

    for user_id, info in data.items():
        # якщо дата в записі стара – скидаємо стан
        if info.get("date") != today:
            info["confirmed_today"] = False
            info["reminders_sent"] = 0
            info["date"] = today

        if info.get("confirmed_today"):
            continue

        if info.get("reminders_sent", 0) >= MAX_REMINDERS:
            continue

        await context.bot.send_message(
            chat_id=int(user_id),
            text="Ну шо? Випила таблетку?",
            reply_markup=kb,
        )
        info["reminders_sent"] = info.get("reminders_sent", 0) + 1

    save_data(data)


async def reset_day(context: ContextTypes.DEFAULT_TYPE):
    """Опівночі скидаємо стан на новий день."""
    data = load_data()
    today = datetime.now(TZ).date().isoformat()

    for user_id in data.keys():
        data[user_id]["confirmed_today"] = False
        data[user_id]["reminders_sent"] = 0
        data[user_id]["date"] = today

    save_data(data)


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробка натискання кнопки 'Так'."""
    query = update.callback_query
    await query.answer()

    user_id = str(query.from_user.id)
    data = load_data()

    if user_id not in data:
        data[user_id] = {
            "confirmed_today": True,
            "reminders_sent": 0,
            "date": datetime.now(TZ).date().isoformat(),
        }
    else:
        data[user_id]["confirmed_today"] = True

    save_data(data)

    await query.edit_message_text("Добре! На сьогодні більше нагадувань не буде 👍")


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Хендлери
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))

    # Планувальник
    jq = app.job_queue

    # Щоденний перший пуш о 11:00
    jq.run_daily(
        send_first_prompt,
        time=time(hour=11, minute=0, tzinfo=TZ),
    )

    # Щоденний ресет опівночі
    jq.run_daily(
        reset_day,
        time=time(hour=0, minute=0, tzinfo=TZ),
    )

    # Кожні 15 хв протягом дня – перевірка та нагадування (до 14:00, макс 12)
    jq.run_repeating(
        send_reminder,
        interval=REMINDER_INTERVAL,
        first=REMINDER_INTERVAL,  # перше нагадування через 15 хв після 11:00
    )

    print("Bot started...")
    app.run_polling()


if __name__ == "__main__":
    main()
