import unittest
import os
import sys
import logging
import json
import requests
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
 
# Настройка логирования
log_dir = "test_logs"
os.makedirs(log_dir, exist_ok=True)
 
# Настройка логгера
logger = logging.getLogger("test_frontend")
logger.setLevel(logging.DEBUG)
 
# Обработчик для консоли
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_format = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
console_handler.setFormatter(console_format)
logger.addHandler(console_handler)
 
# Обработчик для файла
file_handler = logging.FileHandler(os.path.join(log_dir, "test_frontend.log"), mode="w")
file_handler.setLevel(logging.DEBUG)
file_format = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
file_handler.setFormatter(file_format)
logger.addHandler(file_handler)
 
# URL фронтенда и бэкенда
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")
API_URL = os.environ.get("API_URL", "http://localhost:8000")
 
# Мок данные для Telegram WebApp
TELEGRAM_MOCK_DATA = {
    "id": 12345,
    "username": "test_user",
    "first_name": "Test",
    "last_name": "User",
    "language_code": "ru",
    "allows_write_to_pm": True,
}
 
 
class TestTimeBankingFrontend(unittest.TestCase):
    """Тесты для фронтенд-части приложения Time Banking"""
 
    @classmethod
    def setUpClass(cls):
        """Настройка перед всеми тестами класса"""
        logger.info("=" * 80)
        logger.info("НАЧАЛО ТЕСТИРОВАНИЯ ФРОНТЕНДА")
        logger.info("=" * 80)
 
        # Настройка Selenium WebDriver
        try:
            chrome_options = Options()
            chrome_options.add_argument(
                "--headless"
            )  # Запуск браузера в режиме без GUI
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
 
            cls.driver = webdriver.Chrome(options=chrome_options)
            cls.driver.implicitly_wait(10)  # Неявное ожидание для всех элементов
            logger.info("WebDriver initialized successfully")
        except WebDriverException as e:
            logger.error(f"Failed to initialize WebDriver: {str(e)}")
            raise
 
    @classmethod
    def tearDownClass(cls):
        """Действия после всех тестов класса"""
        if hasattr(cls, "driver"):
            cls.driver.quit()
            logger.info("WebDriver closed")
        logger.info("=" * 80)
        logger.info("ЗАВЕРШЕНИЕ ТЕСТИРОВАНИЯ ФРОНТЕНДА")
        logger.info("=" * 80)
 
    def setUp(self):
        """Подготовка перед каждым тестом"""
        logger.info("=" * 80)
        logger.info(f"НАЧАЛО ТЕСТА: {self._testMethodName}")
        logger.info("=" * 80)
 
        # Инъекция моков для Telegram WebApp
        self.inject_telegram_mock()
 
    def tearDown(self):
        """Действия после каждого теста"""
        logger.info("=" * 80)
        logger.info(f"ЗАВЕРШЕНИЕ ТЕСТА: {self._testMethodName}")
        logger.info("=" * 80)
        logger.info("\n\n")
 
        # Удаляем все куки после каждого теста
        self.driver.delete_all_cookies()
 
    def inject_telegram_mock(self):
        """Инъекция мока объекта Telegram.WebApp для тестирования"""
        auth_date = str(int(time.time()))
        user_info = json.dumps(TELEGRAM_MOCK_DATA)
 
        script = """
        window.Telegram = {
            WebApp: {
                initData: "query_id=test_query_id&user=" + encodeURIComponent(%s) + "&auth_date=%s&test_mode=true&hash=test_hash",
                initDataUnsafe: {
                    query_id: "test_query_id",
                    user: %s,
                    auth_date: %s,
                    test_mode: true,
                    hash: "test_hash"
                },
                ready: function() { console.log("Telegram.WebApp.ready called"); },
                expand: function() { console.log("Telegram.WebApp.expand called"); },
                close: function() { console.log("Telegram.WebApp.close called"); },
                showPopup: function(params) { console.log("Telegram.WebApp.showPopup called with:", params); },
                showAlert: function(message) { console.log("Telegram.WebApp.showAlert called with:", message); },
                showConfirm: function(message) { console.log("Telegram.WebApp.showConfirm called with:", message); },
                enableClosingConfirmation: function() { console.log("Telegram.WebApp.enableClosingConfirmation called"); },
                disableClosingConfirmation: function() { console.log("Telegram.WebApp.disableClosingConfirmation called"); },
                setHeaderColor: function(color) { console.log("Telegram.WebApp.setHeaderColor called with:", color); },
                setBackgroundColor: function(color) { console.log("Telegram.WebApp.setBackgroundColor called with:", color); },
                isExpanded: true,
                viewportHeight: 800,
                viewportStableHeight: 800,
                platform: "web",
                colorScheme: "light",
                themeParams: {
                    bg_color: "#ffffff",
                    text_color: "#000000",
                    hint_color: "#999999",
                    link_color: "#2481cc",
                    button_color: "#2481cc",
                    button_text_color: "#ffffff"
                }
            }
        };
        console.log("Telegram WebApp mock injected:", window.Telegram);
        """ % (
            user_info,
            auth_date,
            user_info,
            auth_date,
        )
 
        self.driver.execute_script(script)
        logger.debug("Telegram WebApp mock injected")
 
    def test_01_frontend_loads(self):
        """Тест загрузки фронтенда"""
        logger.info(f"Testing frontend loading at URL: {FRONTEND_URL}")
        try:
            self.driver.get(FRONTEND_URL)
 
            # Ожидаем загрузки страницы
            WebDriverWait(self.driver, 30).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
 
            # Проверяем наличие основных элементов интерфейса
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "card"))
            )
 
            # Делаем скриншот
            screenshot_path = os.path.join(log_dir, "frontend_loaded.png")
            self.driver.save_screenshot(screenshot_path)
            logger.info(f"Screenshot saved to {screenshot_path}")
 
            self.assertTrue(True, "Frontend loaded successfully")
            logger.info("Frontend loaded successfully")
        except Exception as e:
            logger.error(f"Frontend loading failed: {str(e)}")
            self.fail(f"Frontend loading failed: {str(e)}")
 
    def test_02_authentication_flow(self):
        """Тест процесса аутентификации"""
        logger.info("Testing authentication flow")
        try:
            self.driver.get(FRONTEND_URL)
 
            # Ожидаем инициализации приложения
            time.sleep(5)  # Даем время для аутентификации
 
            # Проверяем, что приложение выполнило аутентификацию
            try:
                error_message = WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located(
                        (By.XPATH, "//div[contains(text(), 'Ошибка авторизации')]")
                    )
                )
                logger.error("Authentication error found on page")
                self.fail("Authentication error found on page")
            except TimeoutException:
                # Если сообщение об ошибке не найдено, это хорошо
                logger.info("No authentication error found")
 
            # Проверяем наличие профиля пользователя
            try:
                profile_element = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located(
                        (
                            By.XPATH,
                            "//div[contains(@class, 'card')]//h3[contains(text(), '@')]",
                        )
                    )
                )
                logger.info(f"Found profile element: {profile_element.text}")
            except TimeoutException:
                logger.error("Profile element not found")
                self.fail("Profile element not found")
 
            # Делаем скриншот
            screenshot_path = os.path.join(log_dir, "authentication_flow.png")
            self.driver.save_screenshot(screenshot_path)
            logger.info(f"Screenshot saved to {screenshot_path}")
 
            logger.info("Authentication flow test completed")
        except Exception as e:
            logger.error(f"Authentication flow test failed: {str(e)}")
            self.fail(f"Authentication flow test failed: {str(e)}")
 
    def test_03_main_menu(self):
        """Тест главного меню"""
        logger.info("Testing main menu")
        try:
            self.driver.get(FRONTEND_URL)
 
            # Ожидаем загрузки меню
            time.sleep(5)
 
            # Проверяем наличие кнопок меню
            create_button = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located(
                    (By.XPATH, "//button[contains(text(), 'Создать заявку')]")
                )
            )
            logger.info("Create listing button found")
 
            view_listings_button = WebDriverWait(self.driver, 3).until(
                EC.presence_of_element_located(
                    (By.XPATH, "//button[contains(text(), 'Просмотр заявок')]")
                )
            )
            logger.info("View listings button found")
 
            profile_button = WebDriverWait(self.driver, 3).until(
                EC.presence_of_element_located(
                    (By.XPATH, "//button[contains(text(), 'Мой профиль')]")
                )
            )
            logger.info("Profile button found")
 
            # Делаем скриншот
            screenshot_path = os.path.join(log_dir, "main_menu.png")
            self.driver.save_screenshot(screenshot_path)
            logger.info(f"Screenshot saved to {screenshot_path}")
 
            logger.info("Main menu test completed successfully")
        except Exception as e:
            logger.error(f"Main menu test failed: {str(e)}")
            self.fail(f"Main menu test failed: {str(e)}")
 
    def test_04_create_listing_form(self):
        """Тест формы создания заявки"""
        logger.info("Testing create listing form")
        try:
            self.driver.get(FRONTEND_URL)
 
            # Ожидаем загрузки меню и нажимаем на кнопку создания заявки
            create_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//button[contains(text(), 'Создать заявку')]")
                )
            )
            create_button.click()
            logger.info("Clicked on Create listing button")
 
            # Ожидаем загрузки формы
            form_title = WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located(
                    (By.XPATH, "//h2[contains(text(), 'Создать заявку')]")
                )
            )
            logger.info("Create listing form loaded")
 
            # Проверяем наличие полей формы
            title_input = self.driver.find_element(
                By.XPATH, "//input[@placeholder='Название']"
            )
            description_input = self.driver.find_element(
                By.XPATH, "//textarea[@placeholder='Описание']"
            )
            hours_input = self.driver.find_element(
                By.XPATH, "//input[@placeholder='Часы']"
            )
 
            # Делаем скриншот
            screenshot_path = os.path.join(log_dir, "create_listing_form.png")
            self.driver.save_screenshot(screenshot_path)
            logger.info(f"Screenshot saved to {screenshot_path}")
 
            logger.info("Create listing form test completed successfully")
        except Exception as e:
            logger.error(f"Create listing form test failed: {str(e)}")
            self.fail(f"Create listing form test failed: {str(e)}")
 
    def test_05_view_listings(self):
        """Тест просмотра заявок"""
        logger.info("Testing view listings")
        try:
            self.driver.get(FRONTEND_URL)
 
            # Ожидаем загрузки меню и нажимаем на кнопку просмотра заявок
            view_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//button[contains(text(), 'Просмотр заявок')]")
                )
            )
            view_button.click()
            logger.info("Clicked on View listings button")
 
            # Ожидаем загрузки списка заявок
            listings_title = WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located(
                    (By.XPATH, "//h2[contains(text(), 'Доступные заявки')]")
                )
            )
            logger.info("Listings page loaded")
 
            # Проверяем наличие заявок или сообщения об их отсутствии
            try:
                listings = self.driver.find_elements(
                    By.XPATH, "//div[contains(@class, 'card')]"
                )
                if listings:
                    logger.info(f"Found {len(listings)} listings")
 
                    # Логируем информацию о первой заявке
                    if len(listings) > 0:
                        first_listing = listings[0]
                        listing_title = first_listing.find_element(
                            By.XPATH, ".//h3"
                        ).text
                        listing_hours = first_listing.find_element(
                            By.XPATH, ".//span[contains(@class, 'text-lg')]"
                        ).text
                        logger.info(
                            f"First listing: Title={listing_title}, Hours={listing_hours}"
                        )
                else:
                    logger.info("No listings found")
            except Exception as e:
                logger.warning(f"Error while checking listings: {str(e)}")
 
            # Делаем скриншот
            screenshot_path = os.path.join(log_dir, "view_listings.png")
            self.driver.save_screenshot(screenshot_path)
            logger.info(f"Screenshot saved to {screenshot_path}")
 
            logger.info("View listings test completed successfully")
        except Exception as e:
            logger.error(f"View listings test failed: {str(e)}")
            self.fail(f"View listings test failed: {str(e)}")
 
    def test_06_profile_view(self):
        """Тест просмотра профиля"""
        logger.info("Testing profile view")
        try:
            self.driver.get(FRONTEND_URL)
 
            # Ожидаем загрузки меню и нажимаем на кнопку профиля
            profile_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//button[contains(text(), 'Мой профиль')]")
                )
            )
            profile_button.click()
            logger.info("Clicked on Profile button")
 
            # Ожидаем загрузки профиля
            profile_title = WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located(
                    (By.XPATH, "//h2[contains(text(), 'Мой профиль')]")
                )
            )
            logger.info("Profile page loaded")
 
            # Проверяем наличие информации о профиле
            username_element = self.driver.find_element(
                By.XPATH,
                "//div[contains(@class, 'profile-info')]//p[contains(text(), '@')]",
            )
            username = username_element.text
            logger.info(f"Profile username: {username}")
 
            # Проверяем наличие информации о балансе
            balance_element = self.driver.find_element(
                By.XPATH, "//div[contains(text(), 'Баланс')]"
            )
            balance = balance_element.text
            logger.info(f"Profile balance info: {balance}")
 
            # Делаем скриншот
            screenshot_path = os.path.join(log_dir, "profile_view.png")
            self.driver.save_screenshot(screenshot_path)
            logger.info(f"Screenshot saved to {screenshot_path}")
 
            logger.info("Profile view test completed successfully")
        except Exception as e:
            logger.error(f"Profile view test failed: {str(e)}")
            self.fail(f"Profile view test failed: {str(e)}")
 
    def test_07_navigation_flow(self):
        """Тест навигации между разделами"""
        logger.info("Testing navigation flow")
        try:
            self.driver.get(FRONTEND_URL)
 
            # Ожидаем загрузки меню
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located(
                    (By.XPATH, "//button[contains(text(), 'Создать заявку')]")
                )
            )
            logger.info("Main menu loaded")
 
            # Переходим к просмотру заявок
            view_button = self.driver.find_element(
                By.XPATH, "//button[contains(text(), 'Просмотр заявок')]"
            )
            view_button.click()
            logger.info("Navigated to listings view")
 
            # Ожидаем загрузки страницы заявок
            WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located(
                    (By.XPATH, "//h2[contains(text(), 'Доступные заявки')]")
                )
            )
 
            # Возвращаемся назад
            back_button = self.driver.find_element(
                By.XPATH, "//button[contains(text(), 'Назад')]"
            )
            back_button.click()
            logger.info("Clicked back button to return to menu")
 
            # Ожидаем загрузки меню
            WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located(
                    (By.XPATH, "//button[contains(text(), 'Создать заявку')]")
                )
            )
            logger.info("Returned to main menu")
 
            # Переходим к профилю
            profile_button = self.driver.find_element(
                By.XPATH, "//button[contains(text(), 'Мой профиль')]"
            )
            profile_button.click()
            logger.info("Navigated to profile view")
 
            # Ожидаем загрузки профиля
            WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located(
                    (By.XPATH, "//h2[contains(text(), 'Мой профиль')]")
                )
            )
 
            # Делаем скриншот
            screenshot_path = os.path.join(log_dir, "navigation_flow.png")
            self.driver.save_screenshot(screenshot_path)
            logger.info(f"Screenshot saved to {screenshot_path}")
 
            logger.info("Navigation flow test completed successfully")
        except Exception as e:
            logger.error(f"Navigation flow test failed: {str(e)}")
            self.fail(f"Navigation flow test failed: {str(e)}")
 
 
if __name__ == "__main__":
    # Выводим информацию о запуске тестов
    logger.info("\n")
    logger.info("=" * 80)
    logger.info("ЗАПУСК ТЕСТИРОВАНИЯ ФРОНТЕНДА TIME BANKING APP")
    logger.info(f"Frontend URL: {FRONTEND_URL}")
    logger.info(f"API URL: {API_URL}")
    logger.info(f"Время запуска: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 80)
    logger.info("\n")
 
    # Запускаем тесты
    unittest.main(verbosity=2)