import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

TOKEN = os.getenv("BOT_TOKEN")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🎮 O‘yin botini yaratish", callback_data="create")],
        [InlineKeyboardButton("👤 Mening botlarim", callback_data="mybots")],
        [InlineKeyboardButton("ℹ️ Yordam", callback_data="help")],
    ]

    await update.message.reply_text(
        "🎮 GameMaker botiga xush kelibsiz!\n\n"
        "Bu yerda o‘zingizning Telegram o‘yin botingizni yaratishingiz mumkin.",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "create":
        keyboard = [
            [InlineKeyboardButton("❌ X va O", callback_data="game_xo")],
            [InlineKeyboardButton("♟️ Shaxmat", callback_data="game_chess")],
            [InlineKeyboardButton("✊ Tosh-qaychi-qog‘oz", callback_data="game_rps")],
        ]

        await query.edit_message_text(
            "Qaysi o‘yinni yaratmoqchisiz?",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    elif query.data.startswith("game_"):
        games = {
            "game_xo": "X va O",
            "game_chess": "Shaxmat",
            "game_rps": "Tosh-qaychi-qog‘oz",
        }

        game = games[query.data]

        await query.edit_message_text(
            f"✅ Tanlangan o‘yin: {game}\n\n"
            "Keyingi bosqichda o‘z botingizni ulaysiz."
        )

    elif query.data == "mybots":
        await query.edit_message_text("Siz yaratgan botlar hozircha mavjud emas.")

    elif query.data == "help":
        await query.edit_message_text(
            "GameMaker orqali o‘z Telegram o‘yin botingizni yaratishingiz mumkin."
        )


def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN topilmadi!")

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buttons))
    app.run_polling()


if __name__ == "__main__":
    main()
