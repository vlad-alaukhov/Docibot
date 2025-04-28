import os
import time
from typing import Dict, Any
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler
)
from rag_processor import *

# Загрузка переменных окружения
load_dotenv(".venv/.env")
TOKEN = os.getenv('TG_TOKEN')
FAISS_BASE_DIR = "DB_FAISS"


# Состояния диалога
SELECTING_DB, PROCESSING_QUERY = range(2)

# Хранилище сессий пользователей
user_sessions: Dict[int, dict] = {}

# Глобальное хранилище (db_name -> db_result)
preloaded_dbs: Dict[str, Dict[str, Any]] = {}


def preload_databases():
    """Загружает все базы при старте бота"""
    global preloaded_dbs
    processor = DBConstructor()

    for db_name in os.listdir(FAISS_BASE_DIR):
        db_path = os.path.join(FAISS_BASE_DIR, db_name)
        if os.path.isdir(db_path):
            db_result = processor.faiss_loader(db_path, hybrid_mode=True)
            if db_result["success"]:
                preloaded_dbs[db_name] = db_result

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Инициализация выбора базы знаний"""
    user_id = update.effective_user.id

    # Получаем список доступных баз
    databases = [d for d in os.listdir(FAISS_BASE_DIR)
                 if os.path.isdir(os.path.join(FAISS_BASE_DIR, d))]

    # Создаем клавиатуру с кнопками
    keyboard = [[db] for db in databases]
    reply_markup = ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        one_time_keyboard=True
    )

    await update.message.reply_text(
        "🔍 Выберите базу знаний из списка ниже:",
        reply_markup=reply_markup
    )

    user_sessions[user_id] = {"status": SELECTING_DB}
    return SELECTING_DB


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    help_text = """
📚 Доступные команды:
/start - Выбор базы знаний
/help - Справка по использованию
/cancel - Сброс текущей сессии

🔎 Бот работает на поиск отрывков документов по вопросу пользователя пока без генерации ответа.
    Перед началом выберите базу знаний из списка под строкой ввода сообщений и задавайте вопросы по контексту.
    В ответ бот выдаст отрезки текста и фрагменты таблиц. Ответ может быть ограничен 4000 символов: это ограничение Telegram.
    После выбора базы задавайте вопросы в свободной форме. Бот найдет релевантные фрагменты документов.
    """
    await update.message.reply_text(help_text)


async def handle_database_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    selected_db = update.message.text

    if selected_db not in preloaded_dbs:
        await update.message.reply_text("❌ База не найдена в кэше")
        return ConversationHandler.END

    user_sessions[user_id] = {
        "db_name": selected_db,  # Только имя базы, не путь
        "status": PROCESSING_QUERY
    }

    await update.message.reply_text(
        f"✅ База '{selected_db}' готова к поиску!\nЗадавайте вопрос:",
        reply_markup=ReplyKeyboardRemove()
    )
    return PROCESSING_QUERY


async def handle_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_sessions:
        await update.message.reply_text("⚠️ Сначала выберите базу через /start")
        return

    query = update.message.text
    db_name = user_sessions[user_id]["db_name"]

    try:
        msg = await update.message.reply_text("🔍 Ищу информацию...")

        # Получаем предзагруженную базу
        db_result = preloaded_dbs.get(db_name)
        if not db_result:
            await msg.edit_text("❌ База не загружена")
            return

        # Используем новый метод поиска
        processor = DBConstructor()
        results = processor.mmr_search(
            query=query,
            db_result=db_result,
            k=5,
            lambda_mult=0.3
        )

        # Форматирование результатов (ваш текущий код)
        response = format_results(results)
        await msg.edit_text(response[:4000])

    except Exception as e:
        await update.message.reply_text(f"⚠️ Ошибка: {str(e)}")

def format_results(docs: List[LangDoc]) -> str:
    """Ваш текущий код форматирования из handle_query"""
    response = []
    current_doc = None
    for doc in docs:
        if doc.metadata.get("document_title") != current_doc:
            current_doc = doc.metadata.get("document_title")
            response.append(f"\n📄 **{current_doc}**\n")
        response.append(f"• {doc.page_content[:250]}...\n")
    return '\n'.join(response)


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сброс текущей сессии"""
    user_id = update.effective_user.id
    user_sessions.pop(user_id, None)
    await update.message.reply_text(
        "Сессия сброшена. Для начала работы используйте /start",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END


def main():
    """Инициализация и запуск бота"""
    # Предзагрузка всех баз при старте
    preload_databases()
    print(f"✅ Предзагружено баз: {len(preloaded_dbs)}")

    app = Application.builder().token(TOKEN).build()

    # Настройка обработчиков диалога
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            SELECTING_DB: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_database_selection),
                CommandHandler('help', help_command),
                CommandHandler('cancel', cancel)
            ],
            PROCESSING_QUERY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_query),
                CommandHandler('help', help_command),
                CommandHandler('cancel', cancel)
            ]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    # Регистрация обработчиков
    app.add_handler(conv_handler)
    app.add_handler(CommandHandler('help', help_command))

    app.run_polling()


if __name__ == "__main__":
    main()