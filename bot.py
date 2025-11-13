# Pill reminder bot – v3 (token inside code, 12 reminders max between 11:00–14:00)

import os
import json
import asyncio
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# ВСТАВ СВІЙ СПРАВЖНІЙ ТОКЕН ТУТ (ЦЕ ПРИКЛАД, ЗАМІНИ ЙОГО)
BOT_TOKEN = "8513409579:AAE9yAxqjq6_QekGvb30GRKezOW5-uKMFrc"

DATA_FILE = "users.json"
TZ = ZoneInfo("Europe/Madrid")  # CET/CEST

MAX_REMINDERS_PER_DAY = 12       # максимум 12 нагадувань на користувача
END_HOUR = 14                    # після 14:00 за Мадридом не шлемо нічого
REMINDER_INTERVAL_SECONDS = 15 * 60  # 15 хвилин


def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r") as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)


def reset_for_today():
    """
    Очищаємо денний статус для всіх користувачів.
    Викликається 1 раз на старті скрипта (один запуск на день).
    """
    data = load_data()
    for user_id in data.keys():
        data[user_id]["confirmed_today"] = False
        data[user_id]["reminders_sent_today"] = 0
    save_data(data)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /start – реєструє користувача в users.json, якщо його там ще немає.
    """
    user_id = str(update.effective_user.id)
    data = load_data()
    if user_id not in data:
        data[user_id] = {
            "confirmed_today": False,
            "reminders_sent_today": 0,
        }
        save_data(data)

    await update.message.reply_text(
        "Гаразд, я буду нагадувати щодня о 11:00 CET 😊"
    )


async def send_first_prompt(context: ContextTypes.DEFAULT_TYPE):
    """
    Перший запуск одразу після старту скрипта (о 11:00):
    шлемо початкове нагадування всім користувачам.
    """
    data = load_data()

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Так", callback_data="confirm_yes")]
    ])

    for user_id, info in data.items():
        # На старті дня всі confirmed_today = False, reminders_sent_today = 0
        await context.bot.send_message(
            chat_id=int(user_id),
            text="Ти прийняла таблетку?",
            reply_markup=keyboard
        )
        info["reminders_sent_today"] = 1

    save_data(data)


async def reminder_loop(context: ContextTypes.DEFAULT_TYPE):
    """
    Кожні 15 хвилин:
    – не шлемо нічого після 14:00
    – не шлемо, якщо already confirmed_today
    – не шлемо, якщо reminders_sent_today >= 12
    """
    now = datetime.now(TZ)
    if now.hour >= END_HOUR:
        # Після 14:00 – просто не робимо нічого
        return

    data = load_data()
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Так", callback_data="confirm_yes")]
    ])

    for user_id, info in data.items():
        confirmed = info.get("confirmed_today", False)
        count = info.get("reminders_sent_today", 0)

        if confirmed:
            continue  # юзер уже натиснув "Так" сьогодні

        if count >= MAX_REMINDERS_PER_DAY:
            continue  # досягли ліміту нагадувань

        # Надсилаємо чергове нагадування
        await context.bot.send_message(
            chat_id=int(user_id),
            text="Нагадування: ти прийняла таблетку?",
            reply_markup=keyboard
        )

        info["reminders_sent_today"] = count + 1

    save_data(data)


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обробка натискання кнопки "Так".
    """
    query = update.callback_query
    await query.answer()

    user_id = str(query.from_user.id)
    data = load_data()

    if user_id not in data:
        data[user_id] = {
            "confirmed_today": True,
            "reminders_sent_today": 0,
        }
    else:
        data[user_id]["confirmed_today"] = True

    save_data(data)

    await query.edit_message_text("Добре! На сьогодні більше нагадувань не буде 👍")


async def main():
    # Один запуск скрипта = один день → перед стартом обнуляємо денний статус
    reset_for_today()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Хендлери
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))

    job_queue = app.job_queue

    # Одразу після старту (GitHub Actions ти запускаєш о 11:00 CET)
    # – шлемо перше нагадування всім зареєстрованим користувачам
    job_queue.run_once(send_first_prompt, when=0)

    # Далі – кожні 15 хвилин до 14:00, максимум 12 нагадувань
    job_queue.run_repeating(
        reminder_loop,
        interval=REMINDER_INTERVAL_SECONDS,
        first=REMINDER_INTERVAL_SECONDS,
    )

    print("Bot started...")
    await app.run_polling()


if __name__ == "__main__":
    asyncio.run(main())
