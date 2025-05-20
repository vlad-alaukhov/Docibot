import os
import asyncio
import traceback
from pprint import pprint

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.enums import ParseMode
from rag_processor import DBConstructor
from dotenv import load_dotenv

class Config:
    os.environ.clear()
    load_dotenv(".venv/.env")
    FAISS_ROOT = os.path.join(os.getcwd(), "DB_FAISS")
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    DEFAULT_K = 4

# config = Config()
bot = Bot(token=Config.BOT_TOKEN)
dp = Dispatcher()
processor = DBConstructor()
user_sessions = {}

# --------------------- Инициализация ---------------------
async def on_startup(bot: Bot):
    print("🔄 Запуск инициализации эмбеддингов...")

    try:
        set_embs_result = processor.set_embeddings(Config.FAISS_ROOT, verbose=True)
        processor.db_metadata = set_embs_result["result"]["metadata"]
        print(processor.db_metadata["is_e5_model"])

        if not set_embs_result["success"]:
            error_msg = set_embs_result.get("result", {}).get("Error", "Неизвестная ошибка")
            print(f"❌ Ошибка инициализации: {error_msg}")
            return

        print("✅ Эмбеддинги успешно загружены")

    except Exception as e:
        print(f"💥 Критическая ошибка при запуске: {str(e)}")
        raise

# --------------------- Команда /start ---------------------
@dp.message(Command("start"))
async def start(message: types.Message):
    try:
        categories = [
            d for d in os.listdir(Config.FAISS_ROOT)
            if os.path.isdir(os.path.join(Config.FAISS_ROOT, d))
        ]

        if not categories:
            await message.answer("⚠️ Базы данных не найдены!")
            return

        keyboard = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [types.InlineKeyboardButton(
                    text=category,
                    callback_data=f"category_{category}"
                )]
                for category in categories
            ]
        )

        await message.answer("📂 Выберите категорию документов:", reply_markup=keyboard)

    except Exception as e:
        await message.answer("⚠️ Ошибка при загрузке категорий")
        print(f"❗ Ошибка в /start: {e}")

# --------------------- Обработка категории ---------------------
@dp.callback_query(F.data.startswith("category_"))
async def handle_category(callback: types.CallbackQuery):
    try:
        user_id = callback.from_user.id
        category = callback.data.split("_", 1)[1]  # Исправлено разделение

        # Инициализация сессии
        user_sessions[user_id] = {
            "faiss_indexes": [],  # Будет заполнено
            "query_prefix": "",
            "last_results": []  # Важно: создаем ключ заранее
        }

        # Убедимся, что путь существует
        category_path = os.path.join(Config.FAISS_ROOT, category)
        if not os.path.exists(category_path):
            await callback.answer("❌ Категория не найдена", show_alert=True)
            return

        # Показываем статус "Загрузка..."
        await callback.answer("⏳ Загрузка...")

        # Асинхронная загрузка баз
        faiss_indexes = []
        faiss_paths = [d for d, _, files in os.walk(category_path) for file in files if file.endswith(".faiss")]

        print(faiss_paths)

        # Прогресс-бар
        progress_msg = await callback.message.answer("🔄 Прогресс: 0%")

        for idx, faiss_dir in enumerate(faiss_paths):
            # Загрузка в отдельном потоке
            load_result = await asyncio.to_thread(
                processor.faiss_loader,
                faiss_dir,
                hybrid_mode=False
            )

            if load_result["success"]:
                faiss_indexes.append(load_result["db"])

            # Обновление прогресса
            progress = (idx + 1) / len(faiss_paths) * 100
            await progress_msg.edit_text(f"🔄 Прогресс: {int(progress)}%")

        # Сохраняем результат
        user_sessions[user_id] = {
            "faiss_indexes": faiss_indexes,
            "query_prefix": "query: " if processor.db_metadata.get("is_e5_model", False) else ""
        }

        user_sessions[user_id].update({
            "faiss_indexes": faiss_indexes,
            "query_prefix": "query: " if processor.db_metadata.get("is_e5_model", False) else ""
        })

        # Удаляем сообщения
        await progress_msg.delete()
        await callback.message.answer(f"✅ База '{category}' готова к поиску!")

    except Exception as e:
        await callback.answer("⚠️ Ошибка загрузки", show_alert=True)
        print(f"❗ Ошибка: {str(e)}")
        traceback.print_exc()
# --------------------- Обработка запроса ---------------------
@dp.message(F.text)
async def handle_query(message: types.Message):
    try:
        user_id = message.from_user.id
        if user_id not in user_sessions:
            await message.answer("❌ Сначала выберите категорию через /start")
            return

        # Получаем контекст пользователя
        session = user_sessions[user_id]

        # Выполняем поиск
        raw_results = await processor.multi_async_search(
            query=session["query_prefix"] + message.text,
            indexes=session["faiss_indexes"],
            search_function=processor.aformatted_scored_sim_search_by_cos,
            k=Config.DEFAULT_K
        )

        # Сортировка и фильтрация
        sorted_results = sorted(
            raw_results,
            key=lambda x: x["score"],
            reverse=True
        )[:3]  # Топ-3 результата

        # Сохраняем результаты в сессии
        user_sessions[user_id]["last_results"] = sorted_results  # Добавлено

        response = "\n\n".join(
            f"📄 Результат {i + 1} (Точность: {res['score']:.0%}):\n"
            f"*{res['metadata']['_title']}*\n{res['content'][:200].replace('passage:', '').strip()}..."
            for i, res in enumerate(sorted_results)
        )

        # Создаем кнопки
        builder = InlineKeyboardBuilder()
        for idx in range(len(sorted_results)):
            builder.button(
                text=f"Результат {idx + 1} ({sorted_results[idx]['score']:.0%})",
                callback_data=f"show_result_{idx}"
            )
        builder.adjust(1)  # Вертикальное расположение

        await message.answer(
            f"🔍 Найдены результаты.\n {response}\n\nВыберите для просмотра:",
            reply_markup=builder.as_markup()
        )

    except Exception as e:
        await message.answer("⚠️ Ошибка при обработке запроса")
        print(f"ERROR: {str(e)}")
        traceback.print_exc()

@dp.callback_query(F.data.startswith("show_result_"))
async def handle_result_selection(callback: types.CallbackQuery):
    try:
        user_id = callback.from_user.id
        session = user_sessions.get(user_id)

        if not session or "last_results" not in session:
            await callback.answer("❌ Сессия устарела. Выполните новый поиск.")
            return

        result_idx = int(callback.data.split("_")[-1])
        results = session["last_results"]

        if result_idx >= len(results):
            await callback.answer("⚠️ Результат не найден")
            return

        main_chunk = results[result_idx]

        # Собираем полный текст/таблицу
        full_content = await assemble_full_content(
            main_chunk=main_chunk,
            faiss_indexes=session["faiss_indexes"]
        )

        # Форматируем заголовок
        header = (
            f"📄 Документ: {main_chunk['metadata'].get('_title', 'Без названия')}\n"
            f"🔗 Тип: {'таблица' if main_chunk['metadata']['element_type'] == 'table' else 'текст'}\n"
            f"📏 Всего частей: "
        )

        # Отправляем
        await callback.message.answer(header)
        await send_long_message(callback.message, full_content, 3000)
        await callback.answer()

    except Exception as e:
        await callback.answer("⚠️ Ошибка при загрузке")
        print(f"CALLBACK ERROR: {str(e)}")

async def assemble_full_content(main_chunk: dict, faiss_indexes: list) -> str:
    """Сборка полного контента из связанных чанков"""
    chunks = []
    visited = set()
    queue = [main_chunk["metadata"]["chunk_id"]]

    while queue:
        chunk_id = queue.pop(0)
        if chunk_id in visited:
            continue

        # Поиск чанка во всех индексах
        chunk = None
        for index in faiss_indexes:
            chunk = next(
                (doc for doc in index.docstore._dict.values()
                 if doc.metadata["chunk_id"] == chunk_id),
                None
            )
            if chunk:
                break

        if chunk:
            chunks.append(chunk)
            visited.add(chunk_id)
            queue.extend(
                linked_id
                for linked_id in chunk.metadata.get("linked", [])
                if linked_id not in visited
            )

    # Сортировка по порядку chunk_id (пример: doc1_p1, doc1_p2)
    chunks.sort(key=lambda x: x.metadata["chunk_id"])

    # Сборка контента
    return "\n\n".join(
        chunk.page_content.replace("passage:", "").strip()
        for chunk in chunks
    )


def format_response(main_chunk: dict, content: str) -> str:
    """Форматирование в зависимости от типа"""
    header = f"📄 Документ: {main_chunk['metadata'].get('_title', 'Без названия')}\n"
    element_type = main_chunk["metadata"].get("element_type", "text")

    if element_type == "table":
        return f"{header}📊 Таблица:\n{content}"

    if len(content) > 4000:
        content = content[:3900] + "\n[...текст сокращен...]"

    return f"{header}{content}"


async def send_long_message(
        message: types.Message,
        text: str,
        max_length: int = 4096,
        delimiter: str = "\n\n"
) -> None:
    """Отправляет текст частями с точным соблюдением лимита"""
    parts = []

    # Разбиваем текст на безопасные части
    while text:
        # Вычисляем максимальный доступный размер для текущей части
        available_size = max_length - (len("📖 Часть X/X\n\n") if parts else 0)
        chunk = text[:available_size]

        # Ищем последний перенос строки или пробел для красивого разрыва
        last_break = max(
            chunk.rfind('\n'),
            chunk.rfind(' '),
            chunk.rfind('. ')
        )

        if last_break != -1 and len(chunk) > 100:
            chunk = chunk[:last_break + 1]

        parts.append(chunk)
        text = text[len(chunk):]

    # Отправляем части
    total = len(parts)
    for i, part in enumerate(parts, 1):
        header = f"📖 Часть {i}/{total}\n\n" if total > 1 else ""
        await message.answer(header + part)

# --------------------- Запуск
if __name__ == "__main__":
    dp.startup.register(on_startup)  # Явная регистрация обработчика

    print("=== Старт бота ===")
    print(f"🔑 Токен бота: {'установлен' if Config.BOT_TOKEN else 'отсутствует!'}")
    print(f"📁 Путь к базам: {Config.FAISS_ROOT}")

    try:
        asyncio.run(dp.start_polling(
            bot,
            skip_updates=True,
            allowed_updates=dp.resolve_used_update_types()
        ))
    except KeyboardInterrupt:
        print("\n🛑 Бот остановлен пользователем")
    except Exception as e:
        print(f"\n💥 Критическая ошибка: {str(e)}")