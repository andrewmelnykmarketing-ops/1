import os
import random
from datetime import time
from collections import defaultdict

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# Токен беремо з змінної середовища
TOKEN = os.getenv("BOT_TOKEN")

# Юзери, які підписались на нагадування
subscribed_users = set()

# Стан по кожному юзеру на сьогодні:
# has_taken – чи натиснули "Так" сьогодні
# reminders_sent – скільки 20-хв нагадувань уже було
user_state = defaultdict(lambda: {"has_taken": False, "reminders_sent": 0})

# Список побажань для рандомної відповіді
good_wishes = [
    "Гарного тобі дня 🌿",
    "Хай сьогодні буде світло всередині",
    "Нехай думки будуть тихими і спокійними",
    "Хай твоє серце відчує тепло",
    "Бажаю тобі ясності",
    "Нехай усе складеться найкращим чином",
    "Хай сьогодні буде легко",
    "Бажаю рівноваги",
    "Хай день принесе приємні новини",
    "Нехай всередині буде тиша",
    "Бажаю добрих сил",
    "Хай у твоєму просторі буде мир",
    "Нехай усе буде м’яко й спокійно",
    "Бажаю теплих людей поруч",
    "Хай прийде відповідь на те, що шукаєш",
    "Нехай всесвіт тримає тебе ніжно",
    "Бажаю відчути себе впевнено",
    "Хай твоє серце трохи відпочине",
    "Бажаю внутрішнього затишку",
    "Нехай день буде добрим до тебе",
    "Хай прийде легкість у думки",
    "Бажаю світлого настрою",
    "Нехай усе непотрібне відпаде саме",
    "Хай буде спокій у твоєму домі",
    "Бажаю гармонії",
    "Хай сьогоднішній день принесе усмішку",
    "Нехай знайдеться щось добре навіть у дрібницях",
    "Бажаю тихої радості",
    "Хай тебе огорне спокій",
    "Нехай сили приходять рівно настільки, наскільки потрібно",
    "Бажаю внутрішньої опори",
    "Хай серце стане теплішим",
    "Нехай думки будуть ясними",
    "Бажаю приємної миті тиші",
    "Хай у тебе все буде вчасно",
    "Бажаю добрих емоцій",
    "Нехай день буде лагідним",
    "Хай твої кроки будуть впевненими",
    "Нехай спокій прийде без зусиль",
    "Бажаю бути в ресурсі",
    "Хай всередині стане світліше",
    "Нехай тебе оточує м’якість",
    "Бажаю приємного відчуття рівноваги",
    "Хай твоє серце не поспішатиме",
    "Нехай турбота знайде тебе",
    "Бажаю теплого моменту для себе",
    "Хай прийде відповідь у потрібний момент",
    "Нехай день повернеться до тебе добром",
    "Бажаю відчути підтримку всередині",
    "Хай у тобі живе спокій",
]


def pill_keyboard() -> InlineKeyboardMarkup:
    """Кнопка 'Так' під нагадуванням."""
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("Так", callback_data="pill_taken")]]
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start – підписує юзера на щоденні нагадування."""
    if update.message is None:
        return

    user_id = update.effective_user.id
    subscribed_users.add(user_id)

    await update.message.reply_text(
        "Привіт! Я буду щодня о 11:00 нагадувати тобі про таблетку 💊"
    )


async def say_random_wish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Відповідь на будь-яке текстове повідомлення – рандомне побажання."""
    if update.message is None:
        return

    wish = random.choice(good_wishes)
    await update.message.reply_text(wish)


async def send_daily_first_reminder(context: ContextTypes.DEFAULT_TYPE):
    """
    Щоденний тригер:
    – скидаємо стан на сьогодні
    – шлемо перше повідомлення "Ти випила таблетку?"
    – запускаємо 20-хв нагадування для кожного юзера
    """
    print("Running daily job")

    for user_id in list(subscribed_users):
        # скидаємо стан на новий день
        user_state[user_id]["has_taken"] = False
        user_state[user_id]["reminders_sent"] = 0

        try:
            await context.bot.send_message(
                chat_id=user_id,
                text="Ти випила таблетку?",
                reply_markup=pill_keyboard(),
            )
        except Exception as e:
            print(f"Error sending first reminder to {user_id}: {e}")
            continue

        # запускаємо нагадування кожні 20 хв, максимум 12 разів
        context.job_queue.run_repeating(
            pill_followup_reminder,
            interval=20 * 60,           # 20 хв у секундах
            first=20 * 60,              # перше нагадування через 20 хв
            name=f"reminder_{user_id}",
            data={"user_id": user_id},
        )


async def pill_followup_reminder(context: ContextTypes.DEFAULT_TYPE):
    """
    Нагадування кожні 20 хв:
    – якщо натиснули "Так" або вже 12 разів – зупиняємо job
    – інакше шлемо "Ну шо? Випила таблетку?"
    """
    job = context.job
    if job is None:
        return

    user_id = job.data["user_id"]
    state = user_state[user_id]

    if state["has_taken"]:
        job.schedule_removal()
        return

    if state["reminders_sent"] >= 12:
        job.schedule_removal()
        return

    state["reminders_sent"] += 1

    try:
        await context.bot.send_message(
            chat_id=user_id,
            text="Ну шо? Випила таблетку?",
            reply_markup=pill_keyboard(),
        )
    except Exception as e:
        print(f"Error sending followup to {user_id}: {e}")
        job.schedule_removal()


async def pill_taken_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обробка натискання кнопки "Так":
    – ставимо has_taken = True
    – обнуляємо лічильник нагадувань
    – прибираємо всі jobs з нагадуваннями для цього юзера
    """
    query = update.callback_query
    if query is None:
        return

    await query.answer()

    user_id = query.from_user.id
    user_state[user_id]["has_taken"] = True
    user_state[user_id]["reminders_sent"] = 0

    try:
        await query.edit_message_text(
            "Молодець 💊 Побачимось завтра о 11:00 😉"
        )
    except Exception as e:
        print(f"Error editing message for {user_id}: {e}")

    # зупиняємо всі jobs з нагадуваннями для цього юзера
    for job in context.job_queue.get_jobs_by_name(f"reminder_{user_id}"):
        job.schedule_removal()


async def testpill(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Тестова команда – щоб не чекати 11:00.
    Викликає такий самий процес, як щоденний джоб.
    """
    if update.message is None:
        return

    await update.message.reply_text("Тестово запускаю нагадування 💊")
    await send_daily_first_reminder(context)


def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN env var is not set")

    app = ApplicationBuilder().token(TOKEN).build()

    # Хендлери
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("testpill", testpill))
    app.add_handler(
        CallbackQueryHandler(pill_taken_button, pattern="^pill_taken$")
    )
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, say_random_wish)
    )

    # ВАЖЛИВО: Render за замовчуванням працює в UTC.
    # Якщо ти в Іспанії (CET = UTC+1 зараз восени),
    # то щоб отримати 11:00 за місцевим – ставимо 10:00 UTC.
    app.job_queue.run_daily(
        send_daily_first_reminder,
        time=time(hour=10, minute=0),  # 10:00 UTC ≈ 11:00 в Іспанії взимку
        name="daily_pill_job",
    )

    print("Bot started")
    app.run_polling()


if __name__ == "__main__":
    main()
