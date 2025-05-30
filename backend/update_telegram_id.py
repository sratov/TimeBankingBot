"""
Скрипт для обновления типа поля telegram_id в таблице users.
Этот скрипт выполняет следующие операции:
1. Создает резервную копию текущей таблицы users
2. Изменяет тип поля telegram_id с INTEGER на BIGINT
3. Перемещает данные из резервной копии в обновленную таблицу
"""

import sqlite3
import os
import shutil
from datetime import datetime

# Путь к базе данных
DB_PATH = "time_banking.db"

# Создаем резервную копию базы данных
def backup_database():
    """Создает резервную копию базы данных"""
    backup_path = f"time_banking_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    shutil.copy2(DB_PATH, backup_path)
    print(f"Создана резервная копия базы данных: {backup_path}")
    return backup_path

# Обновляем схему базы данных
def update_schema():
    """Обновляет схему таблицы users, изменяя тип поля telegram_id"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Создаем временную таблицу с новой схемой
        cursor.execute("""
        CREATE TABLE users_new (
            id INTEGER PRIMARY KEY,
            telegram_id BIGINT UNIQUE,
            username TEXT,
            avatar TEXT,
            balance REAL,
            earned_hours REAL,
            spent_hours REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # Копируем данные из старой таблицы в новую
        cursor.execute("""
        INSERT INTO users_new (id, telegram_id, username, avatar, balance, earned_hours, spent_hours, created_at)
        SELECT id, telegram_id, username, avatar, balance, earned_hours, spent_hours, created_at FROM users
        """)
        
        # Удаляем старую таблицу и переименовываем новую
        cursor.execute("DROP TABLE users")
        cursor.execute("ALTER TABLE users_new RENAME TO users")
        
        # Воссоздаем индексы
        cursor.execute("CREATE INDEX ix_users_telegram_id ON users (telegram_id)")
        cursor.execute("CREATE INDEX ix_users_username ON users (username)")
        
        conn.commit()
        print("Схема таблицы users успешно обновлена")
    except Exception as e:
        conn.rollback()
        print(f"Ошибка при обновлении схемы: {e}")
        raise
    finally:
        conn.close()

def main():
    """Основная функция скрипта"""
    # Проверяем существование базы данных
    if not os.path.exists(DB_PATH):
        print(f"Ошибка: файл базы данных {DB_PATH} не найден")
        return
    
    # Создаем резервную копию
    backup_path = backup_database()
    
    # Обновляем схему
    try:
        update_schema()
        print("Миграция успешно завершена")
    except Exception as e:
        print(f"Ошибка при выполнении миграции: {e}")
        print(f"Вы можете восстановить базу данных из резервной копии: {backup_path}")

if __name__ == "__main__":
    main() 