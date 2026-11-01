
import logging
import sqlite3

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

from crypto_utils import decrypt_token

logger = logging.getLogger("GameMaker.BotManager")

DB_FILE = "gamemaker.db"

# Ishlayotgan botlar xotirada saqlanadi.
running_bots = {}


def get_saved_bots():
    """Ishga tushirilishi kerak bo'lgan botlarni bazadan oladi."""

    with sqlite3.connect(DB_FILE) as conn:
        return conn.execute(
            """
            SELECT id, encrypted_token, bot_name
            FROM bots
            WHERE encrypted_token IS NOT NULL
            AND status IN ('validated', 'running')
            """
        ).fetchall()


async def child_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """Yaratilgan mustaqil botning /start buyrug'i."""

    await update.message.reply_text(
        "🎮 Salom! Bu GameMaker orqali yaratilgan "
        "mustaqil o'yin botidir.\n\n"
        "O'yin funksiyalari keyingi bosqichda ulanadi."
    )


async def start_child_bot(bot_id, encrypted_token):
    """Bitta mustaqil botni ishga tushiradi."""

    if bot_id in running_bots:
        return True

    try:
        token = decrypt_token(encrypted_token)

        app = (
            Application.builder()
            .token(token)
            .build()
        )

        app.add_handler(
            CommandHandler("start", child_start)
        )

        await app.initialize()
        await app.start()
        await app.updater.start_polling()

        running_bots[bot_id] = app

        with sqlite3.connect(DB_FILE) as conn:
            conn.execute(
                "UPDATE bots SET status='running' WHERE id=?",
                (bot_id,),
            )

        logger.info("Child bot started: ID %s", bot_id)
        return True

    except Exception:
        logger.error("Child bot startup failed: ID %s", bot_id)

        with sqlite3.connect(DB_FILE) as conn:
            conn.execute(
                "UPDATE bots SET status='error' WHERE id=?",
                (bot_id,),
            )

        return False


async def start_all_child_bots():
    """Bazadagi barcha saqlangan botlarni ishga tushiradi."""

    bots = get_saved_bots()

    logger.info("Found %s saved child bots", len(bots))

    for bot_id, encrypted_token, bot_name in bots:
        await start_child_bot(bot_id, encrypted_token)


async def stop_all_child_bots():
    """Barcha mustaqil botlarni to'xtatadi."""

    for bot_id, app in list(running_bots.items()):
        try:
            if app.updater and app.updater.running:
                await app.updater.stop()

            await app.stop()
            await app.shutdown()

            logger.info("Child bot stopped: ID %s", bot_id)

        except Exception:
            logger.error("Child bot shutdown failed: ID %s", bot_id)

    running_bots.clear()
