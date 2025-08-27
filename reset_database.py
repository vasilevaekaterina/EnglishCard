from database import db


def reset_database():
    conn = db.get_connection()
    cursor = conn.cursor()
    
    try:
        # Удаляем все таблицы
        cursor.execute("DROP TABLE IF EXISTS user_stats CASCADE")
        cursor.execute("DROP TABLE IF EXISTS user_words CASCADE")
        cursor.execute("DROP TABLE IF EXISTS common_words CASCADE")
        
        conn.commit()
        print("База данных очищена успешно")
    except Exception as e:
        conn.rollback()
        print(f"Ошибка очистки базы данных: {e}")
    finally:
        cursor.close()

if __name__ == "__main__":
    reset_database()
