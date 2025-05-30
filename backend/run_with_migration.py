"""
Скрипт для запуска сервера с предварительной миграцией базы данных.
"""
import os
import sys
import subprocess
import logging
import time

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('migration_and_startup.log')
    ]
)
logger = logging.getLogger(__name__)

def run_migration():
    """Выполняет скрипт миграции базы данных"""
    logger.info("Запуск миграции базы данных...")
    try:
        import update_telegram_id
        update_telegram_id.main()
        logger.info("Миграция успешно завершена")
        return True
    except Exception as e:
        logger.error(f"Ошибка при выполнении миграции: {e}", exc_info=True)
        return False

def run_server():
    """Запускает сервер FastAPI"""
    logger.info("Запуск сервера...")
    cmd = ["uvicorn", "main:app", "--reload", "--log-level", "debug", "--host", "0.0.0.0", "--port", "8000"]
    
    try:
        process = subprocess.Popen(cmd)
        logger.info(f"Сервер запущен с PID: {process.pid}")
        
        # Ожидаем запуска сервера
        time.sleep(2)
        
        # Проверяем, что процесс все еще жив
        if process.poll() is None:
            logger.info("Сервер успешно запущен")
            return process
        else:
            logger.error(f"Сервер остановился с кодом: {process.returncode}")
            return None
    except Exception as e:
        logger.error(f"Ошибка при запуске сервера: {e}", exc_info=True)
        return None

def main():
    """Основная функция скрипта"""
    logger.info("=" * 80)
    logger.info("Запуск приложения Time Banking с миграцией")
    logger.info("=" * 80)
    
    # Выполняем миграцию
    migration_success = run_migration()
    if not migration_success:
        logger.warning("Миграция не выполнена, но продолжаем запуск сервера")
    
    # Запускаем сервер
    server_process = run_server()
    
    if server_process:
        try:
            # Ожидаем завершения процесса сервера
            server_process.wait()
        except KeyboardInterrupt:
            logger.info("Получен сигнал прерывания, останавливаем сервер...")
            server_process.terminate()
            try:
                # Ждем корректного завершения
                server_process.wait(timeout=5)
                logger.info("Сервер успешно остановлен")
            except subprocess.TimeoutExpired:
                logger.warning("Сервер не остановился по таймауту, принудительно убиваем процесс")
                server_process.kill()
    else:
        logger.error("Не удалось запустить сервер")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 