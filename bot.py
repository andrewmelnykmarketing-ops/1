import os
from telegram.ext import ApplicationBuilder, MessageHandler, filters

TOKEN = os.getenv("BOT_TOKEN")  # токен беремо з змінної середовища

async def say_hi(update, context):
    # відповідаємо "привіт" на будь-яке текстове повідомлення
    if update.message:
        await update.message.reply_text("привіт")

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    # Ловимо всі повідомлення
    app.add_handler(MessageHandler(filters.ALL, say_hi))

    # Запускаємо бота у режимі polling
    app.run_polling()

if __name__ == "__main__":
    main()
