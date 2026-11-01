
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

running_bots = {}


def get_saved_bots():
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
    await update.message.reply_text(
        "🎮 Salom! Bu GameMaker orqali yaratilgan "
        "mustaqil bot.\n\n"
        "Bot sozlamalari keyingi bosqichda ulanadi."
    )


async def start_child_bot(bot_id, encrypted_token):
    if bot_id in running_bots:
        return True

    app = None

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
        await app.updater.start_polling()
        await app.start()

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

        if app is not None:
            try:
                if app.updater and app.updater.running:
                    await app.updater.stop()
                await app.stop()
                await app.shutdown()
            except Exception:
                logger.error("Child bot cleanup failed: ID %s", bot_id)

        with sqlite3.connect(DB_FILE) as conn:
            conn.execute(
                "UPDATE bots SET status='error' WHERE id=?",
                (bot_id,),
            )

        return False


async def start_all_child_bots(application):
    bots = get_saved_bots()

    logger.info("Found %s saved child bots", len(bots))

    for bot_id, encrypted_token, bot_name in bots:
        await start_child_bot(bot_id, encrypted_token)


async def stop_all_child_bots(application):
    for bot_id, app in list(running_bots.items()):
        try:
            if app.updater and app.updater.running:
                await app.updater.stop()

            await app.stop()
            await app.shutdown()

            with sqlite3.connect(DB_FILE) as conn:
                conn.execute(
                    "UPDATE bots SET status='validated' WHERE id=?",
                    (bot_id,),
                )

            logger.info("Child bot stopped: ID %s", bot_id)

        except Exception:
            logger.error("Child bot shutdown failed: ID %s", bot_id)

    running_bots.clear()
