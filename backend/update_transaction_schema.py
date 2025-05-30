import sqlite3
from database import engine

def update_transaction_schema():
    # Используем прямое подключение к SQLite для изменения схемы
    conn = sqlite3.connect('time_banking.db')
    cursor = conn.cursor()
    
    try:
        # Проверяем, существует ли колонка transaction_type
        cursor.execute("PRAGMA table_info(transactions)")
        columns = cursor.fetchall()
        column_names = [column[1] for column in columns]
        
        if 'transaction_type' not in column_names:
            print("Добавляем колонку transaction_type в таблицу transactions...")
            cursor.execute("ALTER TABLE transactions ADD COLUMN transaction_type TEXT DEFAULT 'payment'")
            conn.commit()
            print("Колонка transaction_type успешно добавлена!")
        else:
            print("Колонка transaction_type уже существует!")
            
    except Exception as e:
        print(f"Ошибка при обновлении схемы: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    update_transaction_schema() 