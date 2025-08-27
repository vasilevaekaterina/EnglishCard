import psycopg2
import logging
from datetime import date
from settings import DB_CONFIG

# Настройка логирования
logger = logging.getLogger(__name__)


class Database:
    """Класс для работы с базой данных"""
    def __init__(self):
        self.connection = None
        self.connect()

    def connect(self):
        """Установка соединения с базой данных"""
        try:
            self.connection = psycopg2.connect(**DB_CONFIG)
            logger.info("Успешное подключение к базе данных")
        except Exception as e:
            logger.error(f"Ошибка подключения к базе данных: {e}")
            raise

    def get_connection(self):
        """Получение соединения с базой данных"""
        if self.connection is None or self.connection.closed:
            self.connect()
        return self.connection

    def init_database(self):
        """Инициализация структуры базы данных"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            # Таблица общих слов
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS common_words (
                id SERIAL PRIMARY KEY,
                russian TEXT NOT NULL,
                english TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')

            # Таблица пользовательских слов (со статистикой)
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_words (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                russian TEXT NOT NULL,
                english TEXT NOT NULL,
                correct_answers INTEGER DEFAULT 0,
                total_attempts INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_practiced TIMESTAMP,
                UNIQUE(user_id, english)
            )
            ''')

            # Таблица статистики пользователей
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_stats (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL UNIQUE,
                total_words INTEGER DEFAULT 0,
                total_correct INTEGER DEFAULT 0,
                total_attempts INTEGER DEFAULT 0,
                current_streak INTEGER DEFAULT 0,
                max_streak INTEGER DEFAULT 0,
                last_practice_date DATE,
                total_practice_days INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')

            # Проверяем, есть ли уже базовые слова
            cursor.execute("SELECT COUNT(*) FROM common_words")
            if cursor.fetchone()[0] == 0:
                # Добавляем базовые слова
                basic_words = [
                    ('красный', 'red'),
                    ('синий', 'blue'),
                    ('зеленый', 'green'),
                    ('желтый', 'yellow'),
                    ('черный', 'black'),
                    ('я', 'I'),
                    ('ты', 'you'),
                    ('он', 'he'),
                    ('она', 'she'),
                    ('оно', 'it'),
                    ('кошка', 'cat'),
                    ('собака', 'dog'),
                    ('птица', 'bird'),
                    ('рыба', 'fish'),
                    ('лошадь', 'horse'),
                    ('яблоко', 'apple'),
                    ('хлеб', 'bread'),
                    ('вода', 'water'),
                    ('молоко', 'milk'),
                    ('сыр', 'cheese'),
                    ('мама', 'mother'),
                    ('папа', 'father'),
                    ('брат', 'brother'),
                    ('сестра', 'sister'),
                    ('друг', 'friend')
                ]

                insert_query = "INSERT INTO common_words (russian, english) VALUES (%s, %s)"
                cursor.executemany(insert_query, basic_words)
                logger.info("Добавлены базовые слова в common_words")

            conn.commit()
            logger.info("База данных успешно инициализирована")

        except Exception as e:
            conn.rollback()
            logger.error(f"Ошибка инициализации базы данных: {e}")
            raise
        finally:
            cursor.close()

    # Методы для работы со словами
    def get_all_words(self, user_id):
        """Получение всех слов пользователя (общих и пользовательских)"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            # Получаем общие слова
            cursor.execute("SELECT russian, english FROM common_words")
            common_words = cursor.fetchall()

            # Получаем пользовательские слова
            cursor.execute("SELECT russian, english FROM user_words WHERE user_id = %s", (user_id,))
            user_words = cursor.fetchall()

            return common_words + user_words
        except Exception as e:
            logger.error(f"Ошибка получения слов для пользователя {user_id}: {e}")
            return []
        finally:
            cursor.close()

    def is_user_word(self, user_id, english):
        """Проверяет, является ли слово пользовательским"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT 1 FROM user_words WHERE user_id = %s AND english = %s", (user_id, english))
            return cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"Ошибка проверки пользовательского слова: {e}")
            return False
        finally:
            cursor.close()

    def add_user_word(self, user_id, russian, english):
        """Добавление пользовательского слова"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """INSERT INTO user_words (user_id, russian, english)
                VALUES (%s, %s, %s)
                ON CONFLICT (user_id, english) DO NOTHING""",
                (user_id, russian, english)
            )
            conn.commit()
            success = cursor.rowcount > 0

            if success:
                logger.info(f"Пользователь {user_id} добавил слово: {russian} - {english}")
                # Обновляем статистику количества слов
                self._update_user_stats_words(user_id)

            return success
        except Exception as e:
            conn.rollback()
            logger.error(f"Ошибка добавления слова для пользователя {user_id}: {e}")
            return False
        finally:
            cursor.close()

    def delete_user_word(self, user_id, english):
        """Удаление пользовательского слова"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                "DELETE FROM user_words WHERE user_id = %s AND english = %s",
                (user_id, english)
            )
            conn.commit()
            success = cursor.rowcount > 0

            if success:
                logger.info(f"Пользователь {user_id} удалил слово: {english}")
                # Обновляем статистику количества слов
                self._update_user_stats_words(user_id)

            return success
        except Exception as e:
            conn.rollback()
            logger.error(f"Ошибка удаления слова для пользователя {user_id}: {e}")
            return False
        finally:
            cursor.close()

    def word_exists(self, user_id, english):
        """Проверка существования слова"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            # Проверяем в общих словах
            cursor.execute("SELECT 1 FROM common_words WHERE english = %s", (english,))
            common_exists = cursor.fetchone() is not None

            # Проверяем в пользовательских словах
            cursor.execute("SELECT 1 FROM user_words WHERE user_id = %s AND english = %s", (user_id, english))
            user_exists = cursor.fetchone() is not None

            return common_exists or user_exists
        except Exception as e:
            logger.error(f"Ошибка проверки существования слова: {e}")
            return False
        finally:
            cursor.close()

    def get_user_words(self, user_id):
        """Получение слов пользователя"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT russian, english, correct_answers, total_attempts, last_practiced
                FROM user_words
                WHERE user_id = %s
                ORDER BY created_at DESC
            """, (user_id,))

            results = cursor.fetchall()
            user_words = []
            for result in results:
                user_words.append({
                    'russian': result[0],
                    'english': result[1],
                    'correct_answers': result[2] or 0,
                    'total_attempts': result[3] or 0,
                    'last_practiced': result[4]
                })
            return user_words
        except Exception as e:
            logger.error(f"Ошибка получения слов пользователя {user_id}: {e}")
            return []
        finally:
            cursor.close()

    def update_word_stats(self, user_id, english, is_correct):
        """Обновление статистики слова (только для пользовательских слов)"""
        # Проверяем, является ли слово пользовательским
        if not self.is_user_word(user_id, english):
            return True  # Для общих слов статистика не обновляется

        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            if is_correct:
                cursor.execute("""
                    UPDATE user_words
                    SET correct_answers = correct_answers + 1,
                        total_attempts = total_attempts + 1,
                        last_practiced = CURRENT_TIMESTAMP
                    WHERE user_id = %s AND english = %s
                """, (user_id, english))
            else:
                cursor.execute("""
                    UPDATE user_words
                    SET total_attempts = total_attempts + 1,
                        last_practiced = CURRENT_TIMESTAMP
                    WHERE user_id = %s AND english = %s
                """, (user_id, english))

            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            conn.rollback()
            logger.error(f"Ошибка обновления статистики слова: {e}")
            return False
        finally:
            cursor.close()

    # Методы для работы со статистикой пользователей
    def _update_user_stats_words(self, user_id):
        """Обновление количества слов пользователя"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT COUNT(*) FROM user_words WHERE user_id = %s", (user_id,))
            word_count = cursor.fetchone()[0]

            cursor.execute("""
                INSERT INTO user_stats (user_id, total_words, updated_at)
                VALUES (%s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (user_id)
                DO UPDATE SET total_words = %s, updated_at = CURRENT_TIMESTAMP
            """, (user_id, word_count, word_count))

            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Ошибка обновления статистики слов пользователя {user_id}: {e}")
        finally:
            cursor.close()

    def update_user_stats(self, user_id, is_correct):
        """Обновление общей статистики пользователя"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            today = date.today()

            # Получаем текущую статистику
            cursor.execute("SELECT last_practice_date, current_streak FROM user_stats WHERE user_id = %s", (user_id,))
            result = cursor.fetchone()

            last_practice_date = result[0] if result else None
            current_streak = result[1] if result else 0

            # Проверяем streak (последовательные дни практики)
            new_streak = current_streak
            if last_practice_date:
                days_diff = (today - last_practice_date).days
                if days_diff == 1:  # Практика в consecutive day
                    new_streak += 1
                elif days_diff > 1:  # Пропуск дня - сбрасываем streak
                    new_streak = 1
            else:
                new_streak = 1

            # Обновляем максимальный streak
            max_streak = new_streak
            if result and result[1] > new_streak:
                max_streak = result[1]

            # Обновляем общую статистику
            cursor.execute("""
                INSERT INTO user_stats
                (user_id, total_correct, total_attempts, current_streak, max_streak,
                 last_practice_date, total_practice_days, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s,
                        CASE WHEN %s THEN 1 ELSE 0 END, CURRENT_TIMESTAMP)
                ON CONFLICT (user_id)
                DO UPDATE SET
                    total_correct = user_stats.total_correct + %s,
                    total_attempts = user_stats.total_attempts + 1,
                    current_streak = %s,
                    max_streak = GREATEST(user_stats.max_streak, %s),
                    last_practice_date = %s,
                    total_practice_days = user_stats.total_practice_days +
                                         CASE WHEN user_stats.last_practice_date != %s THEN 1 ELSE 0 END,
                    updated_at = CURRENT_TIMESTAMP
            """, (
                user_id,
                1 if is_correct else 0, 1, new_streak, max_streak, today, last_practice_date != today,
                1 if is_correct else 0, new_streak, max_streak, today, today
            ))

            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            logger.error(f"Ошибка обновления статистики пользователя {user_id}: {e}")
            return False
        finally:
            cursor.close()

    def get_user_stats(self, user_id):
        """Получение статистики пользователя"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT total_words, total_correct, total_attempts,
                       current_streak, max_streak, total_practice_days,
                       last_practice_date
                FROM user_stats
                WHERE user_id = %s
            """, (user_id,))

            result = cursor.fetchone()
            if result:
                total_correct = result[1] or 0
                total_attempts = result[2] or 0
                accuracy = round((total_correct / total_attempts * 100) if total_attempts > 0 else 0, 1)

                return {
                    'total_words': result[0] or 0,
                    'total_correct': total_correct,
                    'total_attempts': total_attempts,
                    'accuracy': accuracy,
                    'current_streak': result[3] or 0,
                    'max_streak': result[4] or 0,
                    'total_practice_days': result[5] or 0,
                    'last_practice_date': result[6]
                }
            return None
        except Exception as e:
            logger.error(f"Ошибка получения статистики пользователя {user_id}: {e}")
            return None
        finally:
            cursor.close()

    def get_today_stats(self, user_id):
        """Получение статистики за сегодня"""
        try:
            # Для сегодняшней статистики используем общую статистику
            stats = self.get_user_stats(user_id)
            if stats and stats['last_practice_date'] == date.today():
                return {
                    'total_correct_today': stats['total_correct'],
                    'total_attempts_today': stats['total_attempts']
                }
            return {'total_correct_today': 0, 'total_attempts_today': 0}
        except Exception as e:
            logger.error(f"Ошибка получения сегодняшней статистики пользователя {user_id}: {e}")
            return {'total_correct_today': 0, 'total_attempts_today': 0}

    def close(self):
        """Закрытие соединения с базой данных"""
        if self.connection and not self.connection.closed:
            self.connection.close()
            logger.info("Соединение с базой данных закрыто")


# Создаем глобальный экземпляр БД
db = Database()
