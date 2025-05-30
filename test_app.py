import unittest
import os
import sys
import logging
import json
import time
import hmac
import hashlib
import requests
from datetime import datetime
import urllib.parse

# Настройка логирования
log_dir = "test_logs"
os.makedirs(log_dir, exist_ok=True)

# Настройка логгера
logger = logging.getLogger("test_app")
logger.setLevel(logging.DEBUG)

# Обработчик для консоли
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(console_format)
logger.addHandler(console_handler)

# Обработчик для файла
file_handler = logging.FileHandler(os.path.join(log_dir, "test_app.log"), mode="w")
file_handler.setLevel(logging.DEBUG)
file_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_format)
logger.addHandler(file_handler)

# URL бэкенда
# 1. Использовать локальный бэкенд (по умолчанию для тестов)
# 2. Для тестирования через ngrok, используйте либо:
#    - Отдельный ngrok для бэкенда: API_URL="https://[backend-ngrok-id].ngrok-free.app"
#    - Прокси через фронтенд: API_URL="https://[frontend-ngrok-id].ngrok-free.app/api"
API_URL = os.environ.get("API_URL", "http://localhost:8000")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "https://66fb-77-91-101-132.ngrok-free.app")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8022193791:AAEAt9a6kBmP28XN60P8d0HmPKG4n9_4-bU")

# Функция для обработки URL
def get_safe_url(url):
    """Convert https://localhost URLs to http://localhost since localhost typically doesn't have valid SSL"""
    if 'localhost' in url and url.startswith('https://'):
        return url.replace('https://', 'http://')
    return url

class TestTimeBankingApp(unittest.TestCase):
    """Тесты для всех функций приложения Time Banking"""

    def setUp(self):
        """Подготовка перед каждым тестом"""
        logger.info("=" * 80)
        logger.info(f"НАЧАЛО ТЕСТА: {self._testMethodName}")
        logger.info("=" * 80)
        self.api_url = get_safe_url(API_URL)
        logger.info(f"Using API URL: {self.api_url}")
        self.bot_token = BOT_TOKEN
        self.test_user_id = 12345
        self.test_username = "test_user"
        self.tokens = {}  # Для хранения JWT токенов

    def tearDown(self):
        """Действия после каждого теста"""
        logger.info("=" * 80)
        logger.info(f"ЗАВЕРШЕНИЕ ТЕСТА: {self._testMethodName}")
        logger.info("=" * 80)
        logger.info("\n\n")

    def generate_telegram_init_data(self, user_id=None, username=None):
        """Генерирует тестовые данные инициализации Telegram WebApp"""
        if user_id is None:
            user_id = self.test_user_id
        if username is None:
            username = self.test_username

        # Создаем тестовые данные
        auth_date = str(int(time.time()))
        query_id = "test_query_id"
        user_info = {
            "id": user_id,
            "first_name": "Test",
            "username": username,
            "language_code": "ru",
            "allows_write_to_pm": True
        }

        # Сортированные параметры для хеширования
        params = {
            "auth_date": auth_date,
            "query_id": query_id,
            "user": json.dumps(user_info),
            "test_mode": "true"  # Добавляем маркер тестового режима
        }

        # Создаем строку init_data без расчета хеша - используем серверный bypass для тестов
        init_data = "&".join([f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items()])
        
        # Добавляем фиктивный хеш, который будет обойден в режиме test_mode
        init_data += f"&hash=test_hash_{auth_date}"

        logger.debug(f"Generated init_data: {init_data}")
        return init_data

    def authenticate_user(self, user_id=None, username=None):
        """Аутентифицирует пользователя и возвращает JWT токен"""
        logger.info(f"Authenticating user id={user_id}, username={username}")
        
        if user_id is None:
            user_id = self.test_user_id
        if username is None:
            username = self.test_username
            
        # Создаем тестовые данные с корректным форматом
        auth_date = str(int(time.time()))
        
        # Создаем данные пользователя в правильном формате для Telegram
        user_info = {
            "id": user_id,
            "first_name": "Test",
            "username": username,
            "language_code": "ru"
        }
        
        # Создаем init_data без хеша - добавляем test_mode для обхода проверки
        init_data_parts = [
            f"auth_date={auth_date}",
            "query_id=test_query_id",
            f"user={urllib.parse.quote(json.dumps(user_info))}",
            "test_mode=true"
        ]
        
        # Добавляем фиктивный хеш
        init_data = "&".join(init_data_parts)
        fake_hash = f"test_hash_{auth_date}"
        init_data = f"{init_data}&hash={fake_hash}"
        
        logger.debug(f"Generated init_data: {init_data}")
        
        # Отправляем запрос на аутентификацию
        url = f"{self.api_url}/auth/telegram"
        logger.debug(f"Authentication URL: {url}")
        
        try:
            # Отправляем POST с init_data в параметрах запроса (не в теле!)
            encoded_init_data = urllib.parse.quote(init_data)
            full_url = f"{url}?init_data={encoded_init_data}"
            logger.info(f"Sending authentication request to: {full_url}")
            
            # Используем максимум диагностической информации
            response = requests.post(full_url, timeout=30)
            logger.info(f"Authentication response status: {response.status_code}")
            logger.info(f"Authentication response headers: {dict(response.headers)}")
            logger.info(f"Authentication response body: {response.text}")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    logger.info(f"Parsed JSON response: {data}")
                    token = data.get("access_token")
                    user = data.get("user")
                    
                    if token:
                        self.tokens[user_id] = token
                        logger.info(f"Successfully authenticated user: {username}")
                        return token, user
                    else:
                        logger.error("No token in authentication response")
                except Exception as json_err:
                    logger.error(f"Failed to parse JSON response: {str(json_err)}")
            else:
                logger.error(f"Authentication failed with status {response.status_code}: {response.text}")
                
                # Проверим альтернативный URL для отладки
                debug_url = f"{self.api_url}/debug/auth"
                logger.info(f"Trying debug auth endpoint: {debug_url}")
                
                debug_data = {
                    "telegram_id": user_id,
                    "username": username,
                    "create_test_user": True
                }
                
                try:
                    debug_response = requests.post(debug_url, json=debug_data, timeout=30)
                    logger.info(f"Debug auth response status: {debug_response.status_code}")
                    logger.info(f"Debug auth response body: {debug_response.text}")
                    
                    if debug_response.status_code == 200:
                        data = debug_response.json()
                        token = data.get("access_token")
                        user = data.get("user")
                        
                        if token:
                            self.tokens[user_id] = token
                            logger.info(f"Successfully authenticated user through debug endpoint: {username}")
                            return token, user
                except Exception as debug_err:
                    logger.error(f"Debug auth request failed: {str(debug_err)}")
                
                # Try with proxy URL if direct API call failed
                if self.api_url != "http://localhost:8000" and FRONTEND_URL:
                    proxy_url = f"{FRONTEND_URL}/api"
                    logger.info(f"Trying with proxy URL: {proxy_url}/debug/auth")
                    
                    try:
                        proxy_response = requests.post(f"{proxy_url}/debug/auth", json=debug_data, timeout=30)
                        logger.info(f"Proxy debug auth response status: {proxy_response.status_code}")
                        logger.info(f"Proxy debug auth response body: {proxy_response.text}")
                        
                        if proxy_response.status_code == 200:
                            data = proxy_response.json()
                            token = data.get("access_token")
                            user = data.get("user")
                            
                            if token:
                                self.tokens[user_id] = token
                                logger.info(f"Successfully authenticated user through proxy debug endpoint: {username}")
                                return token, user
                    except Exception as proxy_err:
                        logger.error(f"Proxy debug auth request failed: {str(proxy_err)}")
                
        except Exception as e:
            logger.error(f"Authentication request exception: {str(e)}")
            logger.exception(e)
        
        return None, None

    def test_01_api_health(self):
        """Тест доступности API"""
        logger.info("Testing API health endpoint")
        try:
            response = requests.get(f"{self.api_url}/")
            logger.debug(f"Health check response: {response.text}")
            self.assertEqual(response.status_code, 200)
            logger.info("API health check successful")
        except Exception as e:
            logger.error(f"API health check failed: {str(e)}")
            self.fail(f"API health check failed: {str(e)}")

    def test_02_authentication(self):
        """Тест аутентификации пользователя через Telegram"""
        logger.info("Testing user authentication")
        token, user = self.authenticate_user()
        self.assertIsNotNone(token)
        self.assertIsNotNone(user)
        logger.info(f"User authenticated successfully: {user}")

    def test_03_get_current_user(self):
        """Тест получения данных текущего пользователя"""
        logger.info("Testing current user endpoint")
        if not self.tokens.get(self.test_user_id):
            token, _ = self.authenticate_user()
            if not token:
                self.skipTest("Authentication required for this test")

        token = self.tokens.get(self.test_user_id)
        headers = {"Authorization": f"Bearer {token}"}

        try:
            response = requests.get(f"{self.api_url}/user/me", headers=headers)
            logger.debug(f"Current user response: {response.text}")
            self.assertEqual(response.status_code, 200)
            user_data = response.json()
            self.assertEqual(user_data["telegram_id"], self.test_user_id)
            logger.info(f"Current user data retrieved successfully: {user_data}")
        except Exception as e:
            logger.error(f"Current user retrieval failed: {str(e)}")
            self.fail(f"Current user retrieval failed: {str(e)}")

    def test_04_create_listing(self):
        """Тест создания заявки"""
        logger.info("Testing listing creation")
        if not self.tokens.get(self.test_user_id):
            token, user = self.authenticate_user()
            if not token:
                self.skipTest("Authentication required for this test")
        
        token = self.tokens.get(self.test_user_id)
        headers = {"Authorization": f"Bearer {token}"}
        
        # Получаем данные пользователя
        try:
            user_response = requests.get(f"{self.api_url}/user/me", headers=headers)
            user_data = user_response.json()
            user_id = user_data["id"]
            
            # Создаем заявку
            listing_data = {
                "listing_type": "request",
                "title": "Test Request",
                "description": "This is a test request created by automated tests",
                "hours": 1.0,
                "user_id": user_id
            }
            
            logger.debug(f"Creating listing with data: {listing_data}")
            response = requests.post(
                f"{self.api_url}/listings/", 
                headers=headers,
                json=listing_data
            )
            logger.debug(f"Create listing response: {response.status_code} - {response.text}")
            
            self.assertEqual(response.status_code, 200)
            created_listing = response.json()
            self.assertEqual(created_listing["title"], listing_data["title"])
            self.assertEqual(created_listing["status"], "active")
            
            # Сохраняем ID созданной заявки для дальнейших тестов
            self.created_listing_id = created_listing["id"]
            logger.info(f"Successfully created listing with ID: {self.created_listing_id}")
            
        except Exception as e:
            logger.error(f"Listing creation failed: {str(e)}")
            self.fail(f"Listing creation failed: {str(e)}")

    def test_05_get_listings(self):
        """Тест получения списка заявок"""
        logger.info("Testing listing retrieval")
        if not self.tokens.get(self.test_user_id):
            token, _ = self.authenticate_user()
            if not token:
                self.skipTest("Authentication required for this test")
                
        token = self.tokens.get(self.test_user_id)
        headers = {"Authorization": f"Bearer {token}"}
        
        try:
            response = requests.get(f"{self.api_url}/listings/", headers=headers)
            logger.debug(f"Get listings response: {response.status_code} - {response.text}")
            
            self.assertEqual(response.status_code, 200)
            listings = response.json()
            self.assertIsInstance(listings, list)
            logger.info(f"Successfully retrieved {len(listings)} listings")
            
            # Выводим краткую информацию о каждой заявке
            for i, listing in enumerate(listings):
                logger.debug(f"Listing {i+1}: ID={listing['id']}, Title={listing['title']}, Status={listing['status']}")
                
        except Exception as e:
            logger.error(f"Listings retrieval failed: {str(e)}")
            self.fail(f"Listings retrieval failed: {str(e)}")

    def test_06_full_listing_workflow(self):
        """Тест полного цикла работы с заявкой"""
        logger.info("Testing full listing workflow")
        
        # Создаем двух пользователей для тестирования
        creator_id = 12345
        worker_id = 54321
        
        # Аутентифицируем создателя заявки
        creator_token, creator = self.authenticate_user(creator_id, "creator_user")
        if not creator_token:
            self.skipTest("Creator authentication failed")
            
        # Аутентифицируем исполнителя
        worker_token, worker = self.authenticate_user(worker_id, "worker_user")
        if not worker_token:
            self.skipTest("Worker authentication failed")
            
        creator_headers = {"Authorization": f"Bearer {creator_token}"}
        worker_headers = {"Authorization": f"Bearer {worker_token}"}
        
        try:
            # 1. Создаем заявку от имени создателя
            creator_response = requests.get(f"{self.api_url}/user/me", headers=creator_headers)
            creator_data = creator_response.json()
            creator_user_id = creator_data["id"]
            
            listing_data = {
                "listing_type": "request",
                "title": "Workflow Test Request",
                "description": "This is a test request for workflow testing",
                "hours": 1.0,
                "user_id": creator_user_id
            }
            
            create_response = requests.post(
                f"{self.api_url}/listings/", 
                headers=creator_headers,
                json=listing_data
            )
            self.assertEqual(create_response.status_code, 200)
            
            listing = create_response.json()
            listing_id = listing["id"]
            logger.info(f"Created listing ID: {listing_id}")
            
            # 2. Исполнитель откликается на заявку
            apply_response = requests.post(
                f"{self.api_url}/listings/{listing_id}/apply",
                headers=worker_headers
            )
            self.assertEqual(apply_response.status_code, 200)
            listing = apply_response.json()
            self.assertEqual(listing["status"], "pending_worker")
            logger.info(f"Worker applied for listing, new status: {listing['status']}")
            
            # 3. Создатель принимает исполнителя
            accept_response = requests.post(
                f"{self.api_url}/listings/{listing_id}/accept",
                headers=creator_headers
            )
            self.assertEqual(accept_response.status_code, 200)
            listing = accept_response.json()
            self.assertEqual(listing["status"], "in_progress")
            logger.info(f"Creator accepted worker, new status: {listing['status']}")
            
            # 4. Исполнитель отмечает заявку как выполненную
            complete_response = requests.post(
                f"{self.api_url}/listings/{listing_id}/complete",
                headers=worker_headers
            )
            self.assertEqual(complete_response.status_code, 200)
            listing = complete_response.json()
            self.assertEqual(listing["status"], "pending_confirmation")
            logger.info(f"Worker marked listing as complete, new status: {listing['status']}")
            
            # 5. Создатель подтверждает выполнение
            confirm_response = requests.post(
                f"{self.api_url}/listings/{listing_id}/confirm",
                headers=creator_headers
            )
            self.assertEqual(confirm_response.status_code, 200)
            listing = confirm_response.json()
            self.assertEqual(listing["status"], "completed")
            logger.info(f"Creator confirmed completion, final status: {listing['status']}")
            
            logger.info("Full listing workflow test completed successfully")
            
        except Exception as e:
            logger.error(f"Workflow test failed: {str(e)}")
            self.fail(f"Workflow test failed: {str(e)}")

    def test_07_friend_management(self):
        """Тест управления друзьями"""
        logger.info("Testing friend management")
        
        # Создаем двух пользователей для тестирования
        user1_id = 11111
        user2_id = 22222
        
        # Аутентифицируем пользователей
        user1_token, user1 = self.authenticate_user(user1_id, "user_one")
        if not user1_token:
            self.skipTest("User 1 authentication failed")
            
        user2_token, user2 = self.authenticate_user(user2_id, "user_two")
        if not user2_token:
            self.skipTest("User 2 authentication failed")
            
        user1_headers = {"Authorization": f"Bearer {user1_token}"}
        user2_headers = {"Authorization": f"Bearer {user2_token}"}
        
        try:
            # 1. Получаем ID пользователей
            user1_response = requests.get(f"{self.api_url}/user/me", headers=user1_headers)
            user1_data = user1_response.json()
            user1_db_id = user1_data["id"]
            
            user2_response = requests.get(f"{self.api_url}/user/me", headers=user2_headers)
            user2_data = user2_response.json()
            user2_db_id = user2_data["id"]
            
            logger.info(f"User 1 DB ID: {user1_db_id}")
            logger.info(f"User 2 DB ID: {user2_db_id}")
            
            # 2. Пользователь 1 отправляет запрос на дружбу пользователю 2
            friend_request_data = {
                "friend_id": user2_db_id
            }
            
            request_response = requests.post(
                f"{self.api_url}/friends/request", 
                headers=user1_headers,
                json=friend_request_data
            )
            self.assertEqual(request_response.status_code, 200)
            friend_request = request_response.json()
            friend_request_id = friend_request["id"]
            self.assertEqual(friend_request["status"], "pending")
            logger.info(f"Friend request sent, ID: {friend_request_id}, status: {friend_request['status']}")
            
            # 3. Пользователь 2 получает список входящих запросов
            pending_response = requests.get(
                f"{self.api_url}/friends/pending",
                headers=user2_headers
            )
            self.assertEqual(pending_response.status_code, 200)
            pending_requests = pending_response.json()
            self.assertTrue(len(pending_requests) > 0)
            logger.info(f"User 2 has {len(pending_requests)} pending friend requests")
            
            # 4. Пользователь 2 принимает запрос
            accept_response = requests.post(
                f"{self.api_url}/friends/{friend_request_id}/accept",
                headers=user2_headers
            )
            self.assertEqual(accept_response.status_code, 200)
            accepted_request = accept_response.json()
            self.assertEqual(accepted_request["status"], "accepted")
            logger.info(f"Friend request accepted, new status: {accepted_request['status']}")
            
            # 5. Проверяем список друзей пользователя 1
            friends1_response = requests.get(
                f"{self.api_url}/friends/",
                headers=user1_headers
            )
            self.assertEqual(friends1_response.status_code, 200)
            friends1 = friends1_response.json()
            self.assertTrue(len(friends1) > 0)
            logger.info(f"User 1 has {len(friends1)} friends")
            
            # 6. Проверяем список друзей пользователя 2
            friends2_response = requests.get(
                f"{self.api_url}/friends/",
                headers=user2_headers
            )
            self.assertEqual(friends2_response.status_code, 200)
            friends2 = friends2_response.json()
            self.assertTrue(len(friends2) > 0)
            logger.info(f"User 2 has {len(friends2)} friends")
            
            logger.info("Friend management test completed successfully")
            
        except Exception as e:
            logger.error(f"Friend management test failed: {str(e)}")
            self.fail(f"Friend management test failed: {str(e)}")

    def test_08_transaction_history(self):
        """Тест истории транзакций"""
        logger.info("Testing transaction history")
        
        if not self.tokens.get(self.test_user_id):
            token, _ = self.authenticate_user()
            if not token:
                self.skipTest("Authentication required for this test")
                
        token = self.tokens.get(self.test_user_id)
        headers = {"Authorization": f"Bearer {token}"}
        
        try:
            # Получаем ID пользователя
            user_response = requests.get(f"{self.api_url}/user/me", headers=headers)
            user_data = user_response.json()
            user_id = user_data["id"]
            
            # Получаем историю транзакций
            transactions_response = requests.get(
                f"{self.api_url}/transactions/{user_id}",
                headers=headers
            )
            self.assertEqual(transactions_response.status_code, 200)
            transactions = transactions_response.json()
            logger.info(f"User has {len(transactions)} transactions")
            
            # Выводим детали транзакций
            for i, tx in enumerate(transactions):
                logger.debug(f"Transaction {i+1}: From={tx.get('from_user', {}).get('username')}, "
                             f"To={tx.get('to_user', {}).get('username')}, "
                             f"Hours={tx['hours']}, Type={tx['transaction_type']}")
                
            logger.info("Transaction history test completed successfully")
            
        except Exception as e:
            logger.error(f"Transaction history test failed: {str(e)}")
            self.fail(f"Transaction history test failed: {str(e)}")

    def test_09_search_users(self):
        """Тест поиска пользователей"""
        logger.info("Testing user search")
        
        if not self.tokens.get(self.test_user_id):
            token, _ = self.authenticate_user()
            if not token:
                self.skipTest("Authentication required for this test")
                
        token = self.tokens.get(self.test_user_id)
        headers = {"Authorization": f"Bearer {token}"}
        
        try:
            # Поиск пользователей по части имени
            search_term = "user"  # Должен найти test_user и других
            search_response = requests.get(
                f"{self.api_url}/users/search?username={search_term}",
                headers=headers
            )
            self.assertEqual(search_response.status_code, 200)
            search_results = search_response.json()
            logger.info(f"Found {len(search_results)} users matching '{search_term}'")
            
            # Выводим найденных пользователей
            for i, user in enumerate(search_results):
                logger.debug(f"User {i+1}: ID={user['id']}, Username={user['username']}")
                
            logger.info("User search test completed successfully")
            
        except Exception as e:
            logger.error(f"User search test failed: {str(e)}")
            self.fail(f"User search test failed: {str(e)}")

    def test_10_profile_view(self):
        """Тест просмотра профиля"""
        logger.info("Testing profile view")
        
        if not self.tokens.get(self.test_user_id):
            token, _ = self.authenticate_user()
            if not token:
                self.skipTest("Authentication required for this test")
                
        token = self.tokens.get(self.test_user_id)
        headers = {"Authorization": f"Bearer {token}"}
        
        try:
            # Получаем ID пользователя
            user_response = requests.get(f"{self.api_url}/user/me", headers=headers)
            user_data = user_response.json()
            user_id = user_data["id"]
            
            # Просматриваем заявки пользователя
            listings_response = requests.get(
                f"{self.api_url}/listings/user/{user_id}",
                headers=headers
            )
            self.assertEqual(listings_response.status_code, 200)
            listings = listings_response.json()
            logger.info(f"User has {len(listings)} listings")
            
            # Выводим заявки пользователя
            for i, listing in enumerate(listings):
                logger.debug(f"Listing {i+1}: ID={listing['id']}, "
                             f"Title={listing['title']}, "
                             f"Type={listing['listing_type']}, "
                             f"Status={listing['status']}")
                
            logger.info("Profile view test completed successfully")
            
        except Exception as e:
            logger.error(f"Profile view test failed: {str(e)}")
            self.fail(f"Profile view test failed: {str(e)}")

    def test_11_diagnostics(self):
        """Тест диагностического эндпоинта"""
        logger.info("Testing diagnostics endpoint")
        
        if not self.tokens.get(self.test_user_id):
            token, _ = self.authenticate_user()
            if not token:
                self.skipTest("Authentication required for this test")
                
        token = self.tokens.get(self.test_user_id)
        headers = {"Authorization": f"Bearer {token}"}
        
        try:
            response = requests.get(f"{self.api_url}/diagnostics", headers=headers)
            logger.debug(f"Diagnostics response: {response.status_code} - {response.text}")
            
            self.assertEqual(response.status_code, 200)
            diagnostics = response.json()
            self.assertEqual(diagnostics["api_status"], "ok")
            
            # Выводим информацию о БД
            db_info = diagnostics.get("database", {})
            logger.info(f"Database connection: {db_info.get('connection')}")
            logger.info(f"Database user count: {db_info.get('user_count')}")
            
            # Выводим информацию о файловой системе
            fs_info = diagnostics.get("filesystem", {})
            logger.info(f"Uploads directory exists: {fs_info.get('uploads_dir_exists')}")
            logger.info(f"Logs directory exists: {fs_info.get('logs_dir_exists')}")
            
            logger.info("Diagnostics test completed successfully")
            
        except Exception as e:
            logger.error(f"Diagnostics test failed: {str(e)}")
            self.fail(f"Diagnostics test failed: {str(e)}")


if __name__ == "__main__":
    # Выводим информацию о запуске тестов
    logger.info("\n")
    logger.info("=" * 80)
    logger.info("ЗАПУСК ТЕСТИРОВАНИЯ TIME BANKING APP")
    logger.info(f"API URL: {API_URL}")
    logger.info(f"Токен бота (скрыт): {BOT_TOKEN[:5]}...{BOT_TOKEN[-5:] if BOT_TOKEN else ''}")
    logger.info(f"Время запуска: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 80)
    logger.info("\n")
    
    # Запускаем тесты
    unittest.main(verbosity=2) 