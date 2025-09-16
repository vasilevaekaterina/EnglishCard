import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton
from telebot.types import ReplyKeyboardRemove
import random
import logging
from settings import BOT_TOKEN
from database import Database

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)


class VocabularyBot:
    """Основной класс бота с инъекцией зависимостей"""

    def __init__(self, db):
        self.bot = telebot.TeleBot(BOT_TOKEN)
        self.db = db
        self.user_sessions = {}

        # Регистрируем обработчики
        self.register_handlers()

    def register_handlers(self):
        """Регистрация обработчиков сообщений"""
        @self.bot.message_handler(commands=['start'])
        def handle_start(message):
            self.handle_start(message)

        @self.bot.message_handler(func=lambda message: True)
        def handle_message(message):
            self.handle_message(message)

    # Вспомогательные функции
    def get_random_word(self, user_id):
        """Получение случайного слова"""
        words = self.db.get_all_words(user_id)
        return random.choice(words) if words else None

    def get_wrong_options(self, correct_answer, user_id):
        """Получение неправильных вариантов ответов"""
        words = self.db.get_all_words(user_id)
        english_words = [word[1] for word in words
                         if word[1].lower() != correct_answer.lower()]

        # Если слов недостаточно, добавляем некоторые стандартные варианты
        if len(english_words) < 3:
            standard_options = [
                'apple',
                'book',
                'car',
                'dog',
                'cat',
                'house',
                'tree',
                'water'
                ]
            additional_options = [opt for opt in standard_options
                                  if opt.lower() != correct_answer.lower()]
            english_words.extend(additional_options)

        # Убираем дубликаты и выбираем 3 случайных варианта
        english_words = list(set(english_words))
        return random.sample(english_words, min(3, len(english_words)))

    # Функции создания клавиатур
    def create_main_keyboard(self):
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        keyboard.add(
            KeyboardButton("Начать тренировку 🚀"),
            KeyboardButton("Мои слова 📝"),
            KeyboardButton("Статистика 📊"),
            KeyboardButton("Добавить слово ➕"),
            KeyboardButton("Удалить слово 🔙")
        )
        return keyboard

    def create_options_keyboard(self, options):
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)

        # Добавляем варианты ответов
        for i in range(0, len(options), 2):
            if i + 1 < len(options):
                keyboard.add(KeyboardButton(options[i]),
                             KeyboardButton(options[i + 1]))
            else:
                keyboard.add(KeyboardButton(options[i]))

        # Добавляем кнопки управления под вариантами ответов
        keyboard.add(
            KeyboardButton("Добавить слово ➕"),
            KeyboardButton("Удалить слово 🔙")
        )
        keyboard.add(KeyboardButton("В главное меню 🏠"))

        return keyboard

    def create_control_keyboard(self):
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        keyboard.add(
            KeyboardButton("Добавить слово ➕"),
            KeyboardButton("Удалить слово 🔙")
        )
        keyboard.add(KeyboardButton("Следующее слово ➡️"))
        keyboard.add(KeyboardButton("В главное меню 🏠"))
        return keyboard

    def create_stats_keyboard(self):
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        keyboard.add(
            KeyboardButton("Общая статистика 📈"),
            KeyboardButton("Сегодняшняя статистика 📅"),
            KeyboardButton("Недельная статистика 📆")
        )
        keyboard.add(KeyboardButton("В главное меню 🏠"))
        return keyboard

    # Обработка сообщений
    def handle_start(self, message):
        welcome_text = """
Привет 👋 Давай попрактикуемся в английском языке.
Тренировки можешь проходить в удобном для себя темпе.
У тебя есть возможность использовать тренажёр, как конструктор,
и собирать свою собственную базу для обучения.
Для этого воспользуйся инструментами:

добавить слово ➕,
удалить слово 🔙.

Ну что, начнём ⬇️
"""

        self.bot.send_message(message.chat.id, welcome_text,
                              reply_markup=self.create_main_keyboard())
        logger.info(f"Пользователь {message.from_user.id} начал работу")

    def handle_message(self, message):
        user_id = message.from_user.id
        text = message.text

        if text == "Начать тренировку 🚀":
            self.ask_question(message.chat.id, user_id)
        elif text == "Добавить слово ➕":
            msg = self.bot.send_message(
                message.chat.id,
                """Введите слово в формате: русское слово - английское слово\n
                Например: стол - table""",
                reply_markup=ReplyKeyboardRemove()
            )
            self.bot.register_next_step_handler(msg, self.process_add_word,
                                                user_id)
        elif text == "Удалить слово 🔙":
            msg = self.bot.send_message(
                message.chat.id,
                "Введите английское слово для удаления:",
                reply_markup=ReplyKeyboardRemove()
            )
            self.bot.register_next_step_handler(msg, self.process_delete_word,
                                                user_id)
        elif text == "Мои слова 📝":
            self.show_my_words(message.chat.id, user_id)
        elif text == "Статистика 📊":
            self.show_stats_options(message.chat.id)
        elif text == "Общая статистика 📈":
            self.show_general_stats(message.chat.id, user_id)
        elif text == "Сегодняшняя статистика 📅":
            self.show_today_stats(message.chat.id, user_id)
        elif text == "Недельная статистика 📆":
            self.show_weekly_stats(message.chat.id, user_id)
        elif text == "В главное меню 🏠":
            self.bot.send_message(message.chat.id, "Главное меню:",
                                  reply_markup=self.create_main_keyboard())
        elif text == "Следующее слово ➡️":
            self.ask_question(message.chat.id, user_id)
        else:
            # Проверяем, является ли сообщение ответом на вопрос
            if user_id in self.user_sessions and ('current_correct' in
                                                  self.user_sessions[user_id]):
                self.check_answer(message)
            else:
                self.bot.send_message(message.chat.id,
                                      "Используйте кнопки для навигации.",
                                      reply_markup=self.create_main_keyboard())

    def process_add_word(self, message, user_id):
        try:
            if ' - ' not in message.text:
                self.bot.send_message(message.chat.id,
                                      """Используйте формат: русское слово -
                                      английское слово""")
                self.bot.send_message(message.chat.id, "Выберите действие:",
                                      reply_markup=self.create_main_keyboard())
                return

            russian, english = map(str.strip, message.text.split(' - ', 1))

            # Проверяем, существует ли уже такое слово
            if self.db.word_exists(user_id, english):
                self.bot.send_message(message.chat.id,
                                      f"""Слово '{english}' уже существует в
                                      вашем словаре!""")
            else:
                if self.db.add_user_word(user_id, russian, english):
                    self.bot.send_message(message.chat.id,
                                          f"""Слово '{russian} -
                                          {english}' добавлено! ✅""")
                else:
                    self.bot.send_message(message.chat.id,
                                          """Не удалось добавить слово.
                                          Возможно, оно уже существует.""")

            self.bot.send_message(message.chat.id, "Выберите действие:",
                                  reply_markup=self.create_main_keyboard())

        except Exception as e:
            self.bot.send_message(message.chat.id,
                                  """Ошибка при добавлении слова.
                                  Попробуйте снова.""")
            logger.error(f"Error adding word: {e}")
            self.bot.send_message(message.chat.id,
                                  "Выберите действие:",
                                  reply_markup=self.create_main_keyboard())

    def process_delete_word(self, message, user_id):
        english_word = message.text.strip()

        # Проверяем, существует ли слово у пользователя
        user_words = self.db.get_user_words(user_id)
        user_english_words = [word['english'] for word in user_words]

        if english_word in user_english_words:
            if self.db.delete_user_word(user_id, english_word):
                self.bot.send_message(message.chat.id,
                                      f"Слово '{english_word}' удалено! ✅")
            else:
                self.bot.send_message(message.chat.id,
                                      "Не удалось удалить слово.")
        else:
            self.bot.send_message(message.chat.id,
                                  f"""Слово '{english_word}'
                                  не найдено в вашем словаре.""")

        self.bot.send_message(message.chat.id,
                              "Выберите действие:",
                              reply_markup=self.create_main_keyboard())

    def show_my_words(self, chat_id, user_id):
        user_words = self.db.get_user_words(user_id)
        if user_words:
            words_text = "📝 Ваши слова:\n\n"
            for i, word in enumerate(user_words, 1):
                accuracy = round(
                    (word['correct_answers'] / word['total_attempts'] * 100)
                    if word['total_attempts'] > 0
                    else 0,
                    1
                    )
                words_text += f"{i}. {word['russian']} - {word['english']}\n"
                words_text += (f"📊 Правильно: {word['correct_answers']}/"
                               f"{word['total_attempts']} ({accuracy}%)\n\n")

            words_text += f"Всего слов: {len(user_words)}"
            self.bot.send_message(chat_id, words_text)
        else:
            self.bot.send_message(chat_id,
                                  """У вас пока нет своих слов.
                                  Добавьте их с помощью кнопки
                                  'Добавить слово ➕'""")

        self.bot.send_message(chat_id,
                              "Выберите действие:",
                              reply_markup=self.create_main_keyboard())

    def show_stats_options(self, chat_id):
        self.bot.send_message(chat_id,
                              "Выберите тип статистики:",
                              reply_markup=self.create_stats_keyboard())

    def show_general_stats(self, chat_id, user_id):
        stats = self.db.get_user_stats(user_id)

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
                stats_text += f"""📆 Последняя практика:
                {stats['last_practice_date'].strftime('%d.%m.%Y')}"""
        else:
            stats_text = "Статистика пока недоступна. Начните тренировку!"

        self.bot.send_message(chat_id,
                              stats_text,
                              reply_markup=self.create_stats_keyboard())

    def show_today_stats(self, chat_id, user_id):
        today_stats = self.db.get_today_stats(user_id)

        stats_text = f"""
📅 Сегодняшняя статистика:
✅ Правильных ответов:
{today_stats['total_correct_today']}/{today_stats['total_attempts_today']}
"""
        if today_stats['total_attempts_today'] > 0:
            correct = today_stats['total_correct_today']
            attempts = today_stats['total_attempts_today']
            percentage = (correct / attempts * 100) if attempts > 0 else 0
            accuracy = round(percentage, 1)
            stats_text += f"🎯 Точность: {accuracy}%"
        else:
            stats_text += "Сегодня вы еще не тренировались!"

        self.bot.send_message(chat_id,
                              stats_text,
                              reply_markup=self.create_stats_keyboard())

    def show_weekly_stats(self, chat_id, user_id):
        weekly_stats = self.db.get_weekly_stats(user_id)

        if weekly_stats:
            stats_text = "📆 Статистика за последние 7 дней:\n\n"
            for day in weekly_stats:
                stats_text += f"📅 {day['date'].strftime('%d.%m')}: "
                f"{day['correct_answers']}/{day['total_attempts']} "
                f"({day['accuracy']}%)\n"

            total_correct = sum(day['correct_answers'] for day in weekly_stats)
            total_attempts = sum(day['total_attempts'] for day in weekly_stats)
            weekly_accuracy = round(
                (total_correct / total_attempts * 100)
                if total_attempts > 0
                else 0,
                1
                )

            stats_text += f"""\n📊 Итого за неделю:
            {total_correct}/{total_attempts} ({weekly_accuracy}%)"""
        else:
            stats_text = "За последнюю неделю тренировок не было."

        self.bot.send_message(chat_id, stats_text,
                              reply_markup=self.create_stats_keyboard())

    def ask_question(self, chat_id, user_id):
        word = self.get_random_word(user_id)
        if not word:
            self.bot.send_message(chat_id,
                                  """Нет слов для тренировки.
                                  Добавьте слова сначала.""")
            self.bot.send_message(chat_id,
                                  "Выберите действие:",
                                  reply_markup=self.create_main_keyboard())
            return

        russian, correct_answer = word
        wrong_answers = self.get_wrong_options(correct_answer, user_id)

        # Создаем варианты ответов
        options = wrong_answers + [correct_answer]
        random.shuffle(options)

        # Сохраняем правильный ответ в сессии пользователя
        self.user_sessions[user_id] = {
            'current_correct': correct_answer,
            'current_russian': russian
        }

        # Отправляем вопрос с вариантами ответов и кнопками управления
        self.bot.send_message(
            chat_id,
            f"Как переводится слово '{russian}'?",
            reply_markup=self.create_options_keyboard(options)
        )

    def check_answer(self, message):
        user_id = message.from_user.id
        user_answer = message.text

        if user_id not in self.user_sessions:
            self.bot.send_message(message.chat.id,
                                  "Сессия истекла. Начните заново.",
                                  reply_markup=self.create_main_keyboard())
            return

        correct_answer = self.user_sessions[user_id]['current_correct']
        russian_word = self.user_sessions[user_id]['current_russian']
        is_correct = user_answer.lower() == correct_answer.lower()

        # Обновляем статистику
        self.db.update_user_stats(user_id, is_correct)

        # Обновляем статистику слова (если это пользовательское слово)
        self.db.update_word_stats(user_id, correct_answer, is_correct)

        if is_correct:
            response_text = (f"Правильно! ✅\nСлово '{russian_word}' "
                             f"переводится как '{correct_answer}'")
            self.bot.send_message(message.chat.id,
                                  response_text,
                                  reply_markup=self.create_control_keyboard())
        else:
            response_text = (
                f"Неправильно ❌\n"
                f"Правильный ответ: '{correct_answer}'\n"
                f"Слово '{russian_word}' переводится как '{correct_answer}'"
            )
            self.bot.send_message(message.chat.id,
                                  response_text,
                                  reply_markup=self.create_control_keyboard())

        # Очищаем сессию после ответа
        if user_id in self.user_sessions:
            del self.user_sessions[user_id]

    def run(self):
        try:
            # Инициализация базы данных
            self.db.init_database()
            print("База данных инициализирована успешно")

            # Запуск бота
            print("Бот запущен...")
            self.bot.infinity_polling()

        except Exception as e:
            logger.error(f"Ошибка запуска бота: {e}")
            print(f"Ошибка запуска бота: {e}")
        finally:
            # Закрытие соединения с базой данных
            self.db.close()


def main():
    db = Database()
    bot = VocabularyBot(db)
    bot.run()


if __name__ == "__main__":
    main()
