#!/usr/bin/env python3
"""
Скрипт для запуска всех тестов приложения Time Banking
"""
import os
import sys
import logging
import unittest
import argparse
import time
from datetime import datetime
import subprocess

# Настройка логирования
log_dir = "test_logs"
os.makedirs(log_dir, exist_ok=True)

# Настройка логгера
logger = logging.getLogger("test_runner")
logger.setLevel(logging.DEBUG)

# Обработчик для консоли
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(console_format)
logger.addHandler(console_handler)

# Обработчик для файла
file_handler = logging.FileHandler(os.path.join(log_dir, "test_run.log"), mode="w")
file_handler.setLevel(logging.DEBUG)
file_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_format)
logger.addHandler(file_handler)


def run_backend_tests():
    """Запуск тестов бэкенда"""
    logger.info("=" * 80)
    logger.info("ЗАПУСК ТЕСТОВ БЭКЕНДА")
    logger.info("=" * 80)
    
    try:
        # Запускаем тесты бэкенда
        logger.info("Запуск файла test_app.py")
        start_time = time.time()
        result = subprocess.run(
            [sys.executable, "test_app.py"],
            capture_output=True,
            text=True,
            check=False
        )
        duration = time.time() - start_time
        
        # Логируем результаты
        logger.info(f"Тесты бэкенда завершены за {duration:.2f} секунд")
        logger.info(f"Статус выполнения: {'успешно' if result.returncode == 0 else 'с ошибками'}")
        
        # Логируем вывод
        if result.stdout:
            logger.debug("Вывод тестов бэкенда:")
            for line in result.stdout.splitlines():
                logger.debug(line)
        
        # Логируем ошибки
        if result.stderr:
            logger.error("Ошибки при выполнении тестов бэкенда:")
            for line in result.stderr.splitlines():
                logger.error(line)
        
        return result.returncode == 0
        
    except Exception as e:
        logger.error(f"Ошибка при запуске тестов бэкенда: {str(e)}")
        return False


def run_frontend_tests():
    """Запуск тестов фронтенда"""
    logger.info("=" * 80)
    logger.info("ЗАПУСК ТЕСТОВ ФРОНТЕНДА")
    logger.info("=" * 80)
    
    try:
        # Проверяем наличие Selenium
        try:
            import selenium
            logger.info(f"Selenium установлен, версия: {selenium.__version__}")
        except ImportError:
            logger.warning("Selenium не установлен. Установите его командой: pip install selenium")
            logger.warning("Тесты фронтенда будут пропущены")
            return False
        
        # Запускаем тесты фронтенда
        logger.info("Запуск файла test_frontend.py")
        start_time = time.time()
        result = subprocess.run(
            [sys.executable, "test_frontend.py"],
            capture_output=True,
            text=True,
            check=False
        )
        duration = time.time() - start_time
        
        # Логируем результаты
        logger.info(f"Тесты фронтенда завершены за {duration:.2f} секунд")
        logger.info(f"Статус выполнения: {'успешно' if result.returncode == 0 else 'с ошибками'}")
        
        # Логируем вывод
        if result.stdout:
            logger.debug("Вывод тестов фронтенда:")
            for line in result.stdout.splitlines():
                logger.debug(line)
        
        # Логируем ошибки
        if result.stderr:
            logger.error("Ошибки при выполнении тестов фронтенда:")
            for line in result.stderr.splitlines():
                logger.error(line)
        
        return result.returncode == 0
        
    except Exception as e:
        logger.error(f"Ошибка при запуске тестов фронтенда: {str(e)}")
        return False


def parse_args():
    parser = argparse.ArgumentParser(description="Run Time Banking tests")
    parser.add_argument(
        "--backend", 
        action="store_true", 
        help="Run backend tests"
    )
    parser.add_argument(
        "--frontend", 
        action="store_true", 
        help="Run frontend tests"
    )
    parser.add_argument(
        "--api-url", 
        help="API URL for tests", 
        default=os.environ.get("API_URL", "http://localhost:8000")
    )
    parser.add_argument(
        "--frontend-url", 
        help="Frontend URL for tests", 
        default=os.environ.get("FRONTEND_URL", "https://66fb-77-91-101-132.ngrok-free.app")
    )
    parser.add_argument(
        "--start-backend",
        action="store_true",
        help="Start backend server automatically before running tests"
    )
    parser.add_argument(
        "--test-data",
        action="store_true",
        help="Use simulated test data instead of real Telegram auth"
    )
    return parser.parse_args()


def main():
    # Parse command line arguments
    args = parse_args()
    
    # Set environment variables for tests
    os.environ["API_URL"] = args.api_url
    os.environ["FRONTEND_URL"] = args.frontend_url
    if args.test_data:
        os.environ["USE_TEST_DATA"] = "true"
    
    logger.info("=" * 80)
    logger.info("ЗАПУСК ТЕСТИРОВАНИЯ TIME BANKING APP")
    logger.info(f"Время запуска: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"API URL: {args.api_url}")
    logger.info(f"Frontend URL: {args.frontend_url}")
    logger.info("=" * 80)
    
    # Start backend if requested
    backend_process = None
    if args.start_backend:
        try:
            logger.info("Starting backend server...")
            backend_dir = os.path.join(os.path.dirname(__file__), "backend")
            backend_process = subprocess.Popen(
                ["python", "-m", "uvicorn", "main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"],
                cwd=backend_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            time.sleep(3)  # Give server time to start
            logger.info("Backend server started")
        except Exception as e:
            logger.error(f"Failed to start backend server: {str(e)}")
            return

    # Run tests
    success = True
    
    # Если не указаны конкретные тесты, запускаем все
    run_all = not (args.backend or args.frontend)
    
    backend_success = True
    frontend_success = True
    
    # Запускаем тесты бэкенда
    if args.backend or run_all:
        backend_success = run_backend_tests()
    
    # Запускаем тесты фронтенда
    if args.frontend or run_all:
        frontend_success = run_frontend_tests()
    
    # Выводим итоговый результат
    logger.info("=" * 80)
    logger.info("РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ")
    logger.info("=" * 80)
    
    if args.backend or run_all:
        logger.info(f"Тесты бэкенда: {'УСПЕШНО' if backend_success else 'ОШИБКА'}")
    
    if args.frontend or run_all:
        logger.info(f"Тесты фронтенда: {'УСПЕШНО' if frontend_success else 'ОШИБКА'}")
    
    overall_success = (backend_success if args.backend or run_all else True) and \
                     (frontend_success if args.frontend or run_all else True)
    
    logger.info(f"Общий результат: {'УСПЕШНО' if overall_success else 'ОШИБКА'}")
    logger.info(f"Время завершения: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 80)
    
    # Возвращаем статус выполнения
    sys.exit(0 if overall_success else 1)


if __name__ == "__main__":
    main() 