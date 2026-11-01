
import os
import sqlite3
import logging
from pathlib import Path
from datetime import datetime
from crypto_utils import encrypt_token, decrypt_token

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")

DB_FILE = "gamemaker.db"
LOG_FILE = "gamemaker.log"

# Logging
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger("GameMaker")


def db():
    return sqlite3.connect(DB_FILE)


def setup_database():
    with db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_seen TEXT
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS bots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                game TEXT,
                bot_name TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT
            )
        """)

        columns = {
            row[1]
            for row in conn.execute(
                "PRAGMA table_info(bots)"
            ).fetchall()
        }

        if "encrypted_token" not in columns:
            conn.execute(
                "ALTER TABLE bots ADD COLUMN encrypted_token TEXT"
            )

        conn.execute("""
            CREATE TABLE IF NOT EXISTS games (
                game_id TEXT PRIMARY KEY,
                name TEXT,
                enabled INTEGER DEFAULT 1
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                setting TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        games = [
            ("xo", "❌ X va O"),
            ("chess", "♟️ Shaxmat"),
            ("rps", "✊ Tosh-qaychi-qog‘oz"),
        ]

        for game_id, name in games:
            conn.execute(
                "INSERT OR IGNORE INTO games (game_id, name) VALUES (?, ?)",
                (game_id, name),
            )

        conn.execute("""
            INSERT OR IGNORE INTO settings (setting, value)
            VALUES ('maintenance', '0')
        """)


def is_admin(user_id):
    return ADMIN_ID and str(user_id) == str(ADMIN_ID)


def maintenance_enabled():
    with db() as conn:
        result = conn.execute(
            "SELECT value FROM settings WHERE setting='maintenance'"
        ).fetchone()

    return result and result[0] == "1"


def register_user(user):
    with db() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO users (user_id, username, first_seen)
            VALUES (?, ?, ?)
            """,
            (
                user.id,
                user.username or "",
                datetime.now().isoformat(timespec="seconds"),
            ),
        )

        conn.execute(
            "UPDATE users SET username=? WHERE user_id=?",
            (user.username or "", user.id),
        )


def user_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "🎮 O‘yin botini yaratish",
            callback_data="create"
        )],
        [InlineKeyboardButton(
            "🤖 Mening botlarim",
            callback_data="mybots"
        )],
        [InlineKeyboardButton(
            "ℹ️ Yordam",
            callback_data="help"
        )],
    ])


def admin_menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "👥 Foydalanuvchilar",
                callback_data="admin_users"
            ),
            InlineKeyboardButton(
                "🤖 Botlar",
                callback_data="admin_bots"
            ),
        ],
        [
            InlineKeyboardButton(
                "📊 Statistika",
                callback_data="admin_stats"
            ),
            InlineKeyboardButton(
                "🎮 O‘yinlar",
                callback_data="admin_games"
            ),
        ],
        [
            InlineKeyboardButton(
                "💾 Backup",
                callback_data="admin_backup"
            ),
            InlineKeyboardButton(
                "📋 Logs",
                callback_data="admin_logs"
            ),
        ],
        [
            InlineKeyboardButton(
                "🛠 Maintenance",
                callback_data="admin_maintenance"
            )
        ],
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if not user:
        return

    if maintenance_enabled() and not is_admin(user.id):
        await update.message.reply_text(
            "🛠 GameMaker hozir texnik xizmat rejimida. "
            "Keyinroq qayta urinib ko‘ring."
        )
        return

    register_user(user)
    logger.info("User started: %s", user.id)

    await update.message.reply_text(
        "🎮 GameMaker botiga xush kelibsiz!\n\n"
        "Bu platformada o‘zingizning Telegram o‘yin botlaringizni "
        "yaratishingiz mumkin.",
        reply_markup=user_menu(),
    )


async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if not user or not is_admin(user.id):
        await update.message.reply_text(
            "⛔ Bu bo‘lim faqat admin uchun."
        )
        return

    await update.message.reply_text(
        "⚙️ GAMEMAKER ADMIN PANEL\n\n"
        "Kerakli bo‘limni tanlang:",
        reply_markup=admin_menu(),
    )


async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    data = query.data or ""

    if maintenance_enabled() and not is_admin(user_id):
        await query.edit_message_text(
            "🛠 GameMaker texnik xizmat rejimida."
        )
        return

    if data.startswith("admin_") and not is_admin(user_id):
        await query.edit_message_text("⛔ Ruxsat yo‘q.")
        logger.warning(
            "Unauthorized admin access attempt: %s",
            user_id
        )
        return

    if data == "create":
        with db() as conn:
            games = conn.execute(
                "SELECT game_id, name FROM games WHERE enabled=1"
            ).fetchall()

        keyboard = [
            [
                InlineKeyboardButton(
                    name,
                    callback_data=f"game_{game_id}"
                )
            ]
            for game_id, name in games
        ]

        await query.edit_message_text(
            "Qaysi o‘yin botini yaratmoqchisiz?",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    elif data.startswith("game_"):
        game_id = data.replace("game_", "", 1)

        with db() as conn:
            game = conn.execute(
                "SELECT name FROM games WHERE game_id=? AND enabled=1",
                (game_id,),
            ).fetchone()

            count = conn.execute(
                "SELECT COUNT(*) FROM bots WHERE user_id=?",
                (user_id,),
            ).fetchone()[0]

        if not game:
            await query.edit_message_text(
                "Bu o‘yin hozir mavjud emas."
            )
            return

        if count >= 5:
            await query.edit_message_text(
                "⛔ Siz 5 ta bot yaratish limitiga yetdingiz."
            )
            return

        await query.edit_message_text(
            f"✅ Tanlangan o‘yin: {game[0]}\n\n"
            "Bot yaratishning keyingi bosqichi hali ishlab "
            "chiqilmoqda. Tez orada token ulash va botni "
            "sozlash imkoniyati qo‘shiladi."
        )

    elif data == "mybots":
        with db() as conn:
            bots = conn.execute(
                """
                SELECT game, bot_name, status
                FROM bots
                WHERE user_id=?
                """,
                (user_id,),
            ).fetchall()

        if not bots:
            await query.edit_message_text(
                "Sizda hali yaratilgan botlar yo‘q."
            )
        else:
            lines = ["🤖 Mening botlarim:"]

            for game, name, status in bots:
                lines.append(f"• {name or game} — {status}")

            await query.edit_message_text("\n".join(lines))

    elif data == "help":
        await query.edit_message_text(
            "ℹ️ GameMaker yordam bo‘limi\n\n"
            "Bu yerda o‘zingizning Telegram o‘yin "
            "botlaringizni yaratishingiz mumkin."
        )

    elif data == "admin_stats":
        with db() as conn:
            users = conn.execute(
                "SELECT COUNT(*) FROM users"
            ).fetchone()[0]

            total_bots = conn.execute(
                "SELECT COUNT(*) FROM bots"
            ).fetchone()[0]

            active_bots = conn.execute(
                "SELECT COUNT(*) FROM bots WHERE status='running'"
            ).fetchone()[0]

            today_users = conn.execute(
                """
                SELECT COUNT(*) FROM users
                WHERE date(first_seen)=date('now','localtime')
                """
            ).fetchone()[0]

        await query.edit_message_text(
            "📊 GAMEMAKER STATISTIKASI\n\n"
            f"👥 Jami foydalanuvchilar: {users}\n"
            f"🆕 Bugungi foydalanuvchilar: {today_users}\n"
            f"🤖 Jami yaratilgan botlar: {total_bots}\n"
            f"🟢 Ishlayotgan botlar: {active_bots}",
            reply_markup=admin_menu(),
        )

    elif data == "admin_users":
        with db() as conn:
            users = conn.execute(
                """
                SELECT user_id, username
                FROM users
                ORDER BY first_seen DESC
                LIMIT 15
                """
            ).fetchall()

        lines = ["👥 OXIRGI FOYDALANUVCHILAR:"]

        for uid, username in users:
            lines.append(
                f"• {uid} — @{username}"
                if username else f"• {uid}"
            )

        await query.edit_message_text(
            "\n".join(lines),
            reply_markup=admin_menu(),
        )

    elif data == "admin_bots":
        with db() as conn:
            total = conn.execute(
                "SELECT COUNT(*) FROM bots"
            ).fetchone()[0]

        await query.edit_message_text(
            f"🤖 Jami botlar: {total}\n\n"
            "Mustaqil botlarni ishga tushirish tizimi "
            "keyingi bosqichda ulanadi.",
            reply_markup=admin_menu(),
        )

    elif data == "admin_games":
        with db() as conn:
            games = conn.execute(
                "SELECT game_id, name, enabled FROM games"
            ).fetchall()

        lines = ["🎮 O‘YINLAR:"]

        for game_id, name, enabled in games:
            status = "🟢 Yoqilgan" if enabled else "🔴 O‘chirilgan"
            lines.append(f"{name}: {status}")

        await query.edit_message_text(
            "\n".join(lines),
            reply_markup=admin_menu(),
        )

    elif data == "admin_backup":
        backup_path = "gamemaker_backup.db"

        source = sqlite3.connect(DB_FILE)
        destination = sqlite3.connect(backup_path)

        try:
            source.backup(destination)
        finally:
            destination.close()
            source.close()

        try:
            with open(backup_path, "rb") as backup_file:
                await query.message.reply_document(
                    document=backup_file,
                    filename="gamemaker_backup.db",
                    caption="💾 GameMaker ma’lumotlar bazasi zaxirasi",
                )
        finally:
            Path(backup_path).unlink(missing_ok=True)

        logger.info("Admin created a database backup")

    elif data == "admin_logs":
        if not Path(LOG_FILE).exists():
            await query.message.reply_text(
                "Hozircha log fayli mavjud emas."
            )
            return

        with open(LOG_FILE, "rb") as log_file:
            await query.message.reply_document(
                document=log_file,
                filename="gamemaker.log",
                caption="📋 GameMaker faoliyat va xatolar loglari",
            )

    elif data == "admin_maintenance":
        with db() as conn:
            result = conn.execute(
                "SELECT value FROM settings WHERE setting='maintenance'"
            ).fetchone()

            current = result[0] if result else "0"
            new_value = "0" if current == "1" else "1"

            conn.execute(
                """
                INSERT OR REPLACE INTO settings (setting, value)
                VALUES ('maintenance', ?)
                """,
                (new_value,),
            )

        status = (
            "YOQILDI 🛠"
            if new_value == "1"
            else "O‘CHIRILDI ✅"
        )

        logger.info(
            "Maintenance changed to %s by admin",
            new_value
        )

        await query.edit_message_text(
            f"Maintenance rejimi: {status}",
            reply_markup=admin_menu(),
        )


def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN topilmadi!")

    if not ADMIN_ID or not ADMIN_ID.isdigit():
        raise RuntimeError(
            "ADMIN_ID noto‘g‘ri yoki kiritilmagan!"
        )

    setup_database()

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CallbackQueryHandler(buttons))

    logger.info("GameMaker started")

    app.run_polling()


if __name__ == "__main__":
    main()
