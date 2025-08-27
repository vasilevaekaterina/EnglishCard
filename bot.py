import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
import random
import logging
from settings import BOT_TOKEN
from database import db

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)

bot = telebot.TeleBot(BOT_TOKEN)


# Вспомогательные функции
def get_random_word(user_id):
    """Получение случайного слова"""
    words = db.get_all_words(user_id)
    return random.choice(words) if words else None


def get_wrong_options(correct_answer, user_id):
    """Получение неправильных вариантов ответов"""
    words = db.get_all_words(user_id)
    english_words = [word[1] for word in words if word[1].lower() != correct_answer.lower()]

    # Если слов недостаточно, добавляем некоторые стандартные варианты
    if len(english_words) < 3:
        standard_options = ['apple', 'book', 'car', 'dog', 'cat', 'house', 'tree', 'water']
        additional_options = [opt for opt in standard_options if opt.lower() != correct_answer.lower()]
        english_words.extend(additional_options)

    # Убираем дубликаты и выбираем 3 случайных варианта
    english_words = list(set(english_words))
    return random.sample(english_words, min(3, len(english_words)))


# Функции создания клавиатур
def create_main_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    keyboard.add(
        KeyboardButton("Начать тренировку 🚀"),
        KeyboardButton("Мои слова 📝"),
        KeyboardButton("Статистика 📊"),
        KeyboardButton("Добавить слово ➕"),
        KeyboardButton("Удалить слово 🔙")
    )
    return keyboard


def create_options_keyboard(options):
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)

    # Добавляем варианты ответов
    for i in range(0, len(options), 2):
        if i + 1 < len(options):
            keyboard.add(KeyboardButton(options[i]), KeyboardButton(options[i + 1]))
        else:
            keyboard.add(KeyboardButton(options[i]))

    # Добавляем кнопки управления под вариантами ответов
    keyboard.add(
        KeyboardButton("Добавить слово ➕"),
        KeyboardButton("Удалить слово 🔙")
    )
    keyboard.add(KeyboardButton("В главное меню 🏠"))

    return keyboard


def create_control_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    keyboard.add(
        KeyboardButton("Добавить слово ➕"),
        KeyboardButton("Удалить слово 🔙")
    )
    keyboard.add(KeyboardButton("Следующее слово ➡️"))
    keyboard.add(KeyboardButton("В главное меню 🏠"))
    return keyboard


def create_stats_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    keyboard.add(
        KeyboardButton("Общая статистика 📈"),
        KeyboardButton("Сегодняшняя статистика 📅")
    )
    keyboard.add(KeyboardButton("В главное меню 🏠"))
    return keyboard


# Обработка сообщений
@bot.message_handler(commands=['start'])
def handle_start(message):
    welcome_text = """
Привет 👋 Давай попрактикуемся в английском языке. Тренировки можешь проходить в удобном для себя темпе.

У тебя есть возможность использовать тренажёр, как конструктор, и собирать свою собственную базу для обучения. Для этого воспользуйся инструментами:

добавить слово ➕,
удалить слово 🔙.

Ну что, начнём ⬇️
"""

    bot.send_message(message.chat.id, welcome_text, reply_markup=create_main_keyboard())
    logger.info(f"Пользователь {message.from_user.id} начал работу с ботом")


@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_id = message.from_user.id
    text = message.text

    if text == "Начать тренировку 🚀":
        ask_question(message.chat.id, user_id)
    elif text == "Добавить слово ➕":
        msg = bot.send_message(
            message.chat.id,
            "Введите слово в формате: русское слово - английское слово\nНапример: стол - table",
            reply_markup=ReplyKeyboardRemove()
        )
        bot.register_next_step_handler(msg, process_add_word, user_id)
    elif text == "Удалить слово 🔙":
        msg = bot.send_message(
            message.chat.id,
            "Введите английское слово для удаления:",
            reply_markup=ReplyKeyboardRemove()
        )
        bot.register_next_step_handler(msg, process_delete_word, user_id)
    elif text == "Мои слова 📝":
        show_my_words(message.chat.id, user_id)
    elif text == "Статистика 📊":
        show_stats_options(message.chat.id)
    elif text == "Общая статистика 📈":
        show_general_stats(message.chat.id, user_id)
    elif text == "Сегодняшняя статистика 📅":
        show_today_stats(message.chat.id, user_id)
    elif text == "В главное меню 🏠":
        bot.send_message(message.chat.id, "Главное меню:", reply_markup=create_main_keyboard())
    elif text == "Следующее слово ➡️":
        ask_question(message.chat.id, user_id)
    else:
        # Проверяем, является ли сообщение ответом на вопрос
        if hasattr(bot, 'user_sessions') and user_id in bot.user_sessions and 'current_correct' in bot.user_sessions[user_id]:
            check_answer(message)
        else:
            bot.send_message(message.chat.id, "Используйте кнопки для навигации.", reply_markup=create_main_keyboard())


def process_add_word(message, user_id):
    try:
        if ' - ' not in message.text:
            bot.send_message(message.chat.id, "Используйте формат: русское слово - английское слово")
            bot.send_message(message.chat.id, "Выберите действие:", reply_markup=create_main_keyboard())
            return

        russian, english = map(str.strip, message.text.split(' - ', 1))

        # Проверяем, существует ли уже такое слово
        if db.word_exists(user_id, english):
            bot.send_message(message.chat.id, f"Слово '{english}' уже существует в вашем словаре!")
        else:
            if db.add_user_word(user_id, russian, english):
                bot.send_message(message.chat.id, f"Слово '{russian} - {english}' добавлено! ✅")
            else:
                bot.send_message(message.chat.id, "Не удалось добавить слово. Возможно, оно уже существует.")

        bot.send_message(message.chat.id, "Выберите действие:", reply_markup=create_main_keyboard())

    except Exception as e:
        bot.send_message(message.chat.id, "Ошибка при добавлении слова. Попробуйте снова.")
        logger.error(f"Error adding word: {e}")
        bot.send_message(message.chat.id, "Выберите действие:", reply_markup=create_main_keyboard())


def process_delete_word(message, user_id):
    english_word = message.text.strip()

    # Проверяем, существует ли слово у пользователя
    user_words = db.get_user_words(user_id)
    user_english_words = [word['english'] for word in user_words]

    if english_word in user_english_words:
        if db.delete_user_word(user_id, english_word):
            bot.send_message(message.chat.id, f"Слово '{english_word}' удалено! ✅")
        else:
            bot.send_message(message.chat.id, "Не удалось удалить слово.")
    else:
        bot.send_message(message.chat.id, f"Слово '{english_word}' не найдено в вашем словаре.")

    bot.send_message(message.chat.id, "Выберите действие:", reply_markup=create_main_keyboard())


def show_my_words(chat_id, user_id):
    user_words = db.get_user_words(user_id)
    if user_words:
        words_text = "📝 Ваши слова:\n\n"
        for i, word in enumerate(user_words, 1):
            accuracy = round((word['correct_answers'] / word['total_attempts'] * 100) if word['total_attempts'] > 0 else 0, 1)
            words_text += f"{i}. {word['russian']} - {word['english']}\n"
            words_text += f"   📊 Правильно: {word['correct_answers']}/{word['total_attempts']} ({accuracy}%)\n\n"

        words_text += f"Всего слов: {len(user_words)}"
        bot.send_message(chat_id, words_text)
    else:
        bot.send_message(chat_id, "У вас пока нет своих слов. Добавьте их с помощью кнопки 'Добавить слово ➕'")

    bot.send_message(chat_id, "Выберите действие:", reply_markup=create_main_keyboard())


def show_stats_options(chat_id):
    bot.send_message(chat_id, "Выберите тип статистики:", reply_markup=create_stats_keyboard())


def show_general_stats(chat_id, user_id):
    stats = db.get_user_stats(user_id)

    if stats:
        stats_text = f"""
📊 Общая статистика:

📝 Всего слов: {stats['total_words']}
✅ Правильных ответов: {stats['total_correct']}/{stats['total_attempts']}
🎯 Точность: {stats['accuracy']}%
🔥 Текущая серия: {stats['current_streak']} дней
🏆 Максимальная серия: {stats['max_streak']} дней
📅 Дней практики: {stats['total_practice_days']}
"""
        if stats['last_practice_date']:
            stats_text += f"📆 Последняя практика: {stats['last_practice_date'].strftime('%d.%m.%Y')}"
        else:
            stats_text = "Статистика пока недоступна. Начните тренировку!"

    bot.send_message(chat_id, stats_text, reply_markup=create_stats_keyboard())


def show_today_stats(chat_id, user_id):
    today_stats = db.get_today_stats(user_id)

    stats_text = f"""
📅 Сегодняшняя статистика:
✅ Правильных ответов: {today_stats['total_correct_today']}/{today_stats['total_attempts_today']}
"""
    if today_stats['total_attempts_today'] > 0:
        accuracy = round((today_stats['total_correct_today'] / today_stats['total_attempts_today'] * 100), 1)
        stats_text += f"🎯 Точность: {accuracy}%"
    else:
        stats_text += "Сегодня вы еще не тренировались!"

    bot.send_message(chat_id, stats_text, reply_markup=create_stats_keyboard())


def ask_question(chat_id, user_id):
    word = get_random_word(user_id)
    if not word:
        bot.send_message(chat_id, "Нет слов для тренировки. Добавьте слова сначала.")
        bot.send_message(chat_id, "Выберите действие:", reply_markup=create_main_keyboard())
        return

    russian, correct_answer = word
    wrong_answers = get_wrong_options(correct_answer, user_id)

    # Создаем варианты ответов
    options = wrong_answers + [correct_answer]
    random.shuffle(options)

    # Сохраняем правильный ответ в сессии пользователя
    if not hasattr(bot, 'user_sessions'):
        bot.user_sessions = {}

    bot.user_sessions[user_id] = {
        'current_correct': correct_answer,
        'current_russian': russian
    }

    # Отправляем вопрос с вариантами ответов и кнопками управления
    bot.send_message(
        chat_id,
        f"Как переводится слово '{russian}'?",
        reply_markup=create_options_keyboard(options)
    )


def check_answer(message):
    user_id = message.from_user.id
    user_answer = message.text

    if user_id not in bot.user_sessions:
        bot.send_message(message.chat.id, "Сессия истекла. Начните заново.", reply_markup=create_main_keyboard())
        return

    correct_answer = bot.user_sessions[user_id]['current_correct']
    russian_word = bot.user_sessions[user_id]['current_russian']
    is_correct = user_answer.lower() == correct_answer.lower()

    # Обновляем статистику
    db.update_user_stats(user_id, is_correct)

    # Обновляем статистику слова (если это пользовательское слово)
    db.update_word_stats(user_id, correct_answer, is_correct)

    if is_correct:
        response_text = f"Правильно! ✅\nСлово '{russian_word}' переводится как '{correct_answer}'"
        bot.send_message(message.chat.id, response_text, reply_markup=create_control_keyboard())
    else:
        response_text = (
            f"Неправильно ❌\n"
            f"Правильный ответ: '{correct_answer}'\n"
            f"Слово '{russian_word}' переводится как '{correct_answer}'"
        )
        bot.send_message(message.chat.id, response_text, reply_markup=create_control_keyboard())

    # Очищаем сессию после ответа
    if user_id in bot.user_sessions:
        del bot.user_sessions[user_id]


# Основная функция
def main():
    try:
        # Инициализация базы данных
        db.init_database()
        print("База данных инициализирована успешно")

        # Запуск бота
        print("Бот запущен...")
        bot.infinity_polling()

    except Exception as e:
        logger.error(f"Ошибка запуска бота: {e}")
        print(f"Ошибка запуска бота: {e}")
    finally:
        # Закрытие соединения с базой данных
        db.close()


if __name__ == "__main__":
    main()
