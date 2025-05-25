import sqlite3
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def update_schema():
    """Обновляет схему базы данных, добавляя недостающие колонки."""
    try:
        # Подключение к базе данных
        conn = sqlite3.connect("time_banking.db")
        cursor = conn.cursor()
        
        # Проверяем, есть ли колонка prepayment_transaction_id в таблице listings
        cursor.execute("PRAGMA table_info(listings)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if "prepayment_transaction_id" not in columns:
            logger.info("Добавляем колонку prepayment_transaction_id в таблицу listings")
            cursor.execute("ALTER TABLE listings ADD COLUMN prepayment_transaction_id INTEGER REFERENCES transactions(id)")
            conn.commit()
            logger.info("Колонка успешно добавлена")
        else:
            logger.info("Колонка prepayment_transaction_id уже существует в таблице listings")
        
        conn.close()
        logger.info("Обновление схемы базы данных завершено успешно")
        return True
    except Exception as e:
        logger.error(f"Ошибка при обновлении схемы базы данных: {str(e)}")
        return False

if __name__ == "__main__":
    update_schema() 