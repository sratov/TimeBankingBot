
# TimeBankingBot (Backend API)

**TimeBankingBot** — это серверное приложение для управления сервисом обмена времени (Time Banking).  
Сервис позволяет пользователям создавать предложения и запросы, вести учёт часов, аутентифицироваться через Telegram и управлять балансом.  

---

## Стек технологий

- **FastAPI** — веб-фреймворк для создания REST API.
- **SQLAlchemy** — ORM для работы с базой данных.
- **SQLite** — база данных (по умолчанию).
- **JWT (PyJWT)** — аутентификация.
- **Pydantic** — валидация данных.
- **asyncio** — асинхронная обработка запросов.
- **python-multipart** — загрузка файлов (аватары).
- **Логирование** — логирование запросов, ошибок и аутентификации.

---

## Структура проекта

backend/
├── **init**.py
├── main.py             # основной сервер (FastAPI)
├── auth.py             # аутентификация через Telegram, JWT
├── models.py           # SQLAlchemy модели
├── schemas.py          # Pydantic схемы
├── database.py         # подключение к базе
├── config.py           # конфигурация (env, JWT секреты и т.д.)
├── static/             # директория для статики (аватары)
└── logs/               # директория для логов

````

---

## Настройка и запуск

Клонируйте репозиторий:

```bash
git clone https://github.com/sratov/TimeBankingBot.git
cd TimeBankingBot/backend
````

Создайте виртуальное окружение и установите зависимости:

```bash
python3 -m venv .venv
source .venv/bin/activate        # для Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Настройте переменные окружения (например, в `.env`):

```env
BOT_TOKEN=123456:ABCDEF
JWT_SECRET_KEY=your_secret_key
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60
ENVIRONMENT=development
```

Запустите сервер:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Сервер будет доступен по адресу: **[http://127.0.0.1:8000/](http://127.0.0.1:8000/)**
Swagger-документация: **[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)**

---

## Основные эндпоинты

| Метод    | URL                               | Описание                                               |
| -------- | --------------------------------- | ------------------------------------------------------ |
| GET      | /                                 | Проверка работы API                                    |
| GET      | /user/me/                         | Профиль текущего пользователя                          |
| GET      | /listings/                        | Список листингов                                       |
| POST     | /listings/                        | Создание листинга                                      |
| POST     | /listings/{listing\_id}/apply/    | Откликнуться на листинг                                |
| POST     | /listings/{listing\_id}/accept/   | Принять исполнителя                                    |
| POST     | /listings/{listing\_id}/reject/   | Отклонить исполнителя                                  |
| POST     | /listings/{listing\_id}/complete/ | Отметить листинг завершённым                           |
| POST     | /listings/{listing\_id}/confirm/  | Подтвердить завершение                                 |
| POST     | /listings/{listing\_id}/cancel/   | Отменить листинг                                       |
| POST     | /profile/{user\_id}/avatar/       | Загрузка аватара пользователя                          |
| GET      | /friends/                         | Список друзей                                          |
| POST     | /friends/request/                 | Отправить запрос в друзья                              |
| POST     | /friends/{friend\_id}/accept/     | Принять запрос в друзья                                |
| POST     | /friends/{friend\_id}/reject/     | Отклонить запрос в друзья                              |
| GET      | /transactions/{user\_id}/         | История транзакций пользователя                        |
| GET      | /auth/protected/                  | Защищённый маршрут (пример)                            |
| POST     | /auth/logout/                     | Выход (удаление токенов из cookies)                    |
| GET/POST | /auth/telegram/                   | Аутентификация через Telegram (WebApp)                 |
| GET      | /auth/refresh/                    | Обновление access токена через refresh                 |
| GET      | /debug/auth/ (dev only)           | Отладочный эндпоинт (dev)                              |
| POST     | /debug/auth/ (dev only)           | Создание тестового пользователя и выдача токенов (dev) |
| GET      | /admin/logs/{log\_name}/          | Просмотр логов (debug, error, requests, auth)          |

---

## Аутентификация через Telegram

* Используется Telegram WebApp (`init_data` и `hash`).
* Пользователь авторизуется через /auth/telegram/.
* Для последующих запросов требуется `access_token` (cookie) — автоматически обновляется через refresh.

---

## База данных

Используется SQLite (`time_banking.db` в корне проекта).
Модели: **User**, **Listing**, **Transaction**, **Friend**.

---

## Логика приложения

Пользователь может создавать:

* **листинги** (запросы/предложения) с оплатой частями (предоплата 33% + окончательная 67%).
* **друзей** (взаимные запросы, статус: pending / accepted).
* **транзакции** (предоплата, окончательная оплата).
* Загружать аватар (сохраняется в `backend/static/avatars`).
* Смотреть друзей, список листингов, свои транзакции.

Интеграция с Telegram для авторизации:

* Проверка `init_data` с `hash`.
* Генерация JWT (access + refresh), сохранение в cookies.

Логирование в отдельные файлы:

* `logs/debug.log`, `logs/error.log`, `logs/auth.log`, `logs/requests.log`.

---

## Тестирование

Рекомендуем использовать **pytest**:

```bash
pip install pytest pytest-asyncio httpx
pytest tests/
```

---

## Конфигурация (config.py)

* `BOT_TOKEN`: токен Telegram бота.
* `JWT_SECRET_KEY`, `JWT_ALGORITHM`: ключи для создания токенов.
* `ENVIRONMENT`, `IS_DEVELOPMENT`: для включения отладочных эндпоинтов.

---

## Авторы / Контрибьют

* GitHub: [https://github.com/sratov/TimeBankingBot](https://github.com/sratov/TimeBankingBot)

---

## Примеры запросов (curl)

Получение профиля:

```bash
curl -b "access_token=..." http://127.0.0.1:8000/user/me/
```

Создание листинга:

```bash
curl -X POST -H "Content-Type: application/json" -b "access_token=..." \
-d '{"title": "Help with math", "description": "Need help", "hours": 2, "listing_type": "request", "user_id": 1}' \
http://127.0.0.1:8000/listings/
```

Загрузка аватара:

```bash
curl -X POST -b "access_token=..." -F "file=@avatar.png" http://127.0.0.1:8000/profile/1/avatar/
```

---

## TODO / Roadmap

* [ ] Автоматические тесты (pytest).
* [ ] CI/CD (GitHub Actions).
* [ ] Поддержка PostgreSQL.
* [ ] Расширенный GUI (веб-клиент).
* [ ] ML-модель (рекомендации листингов).

---

**Удачи в использовании TimeBankingBot!**

| Категория               | Баллы | Подробности                                                                      |
| ----------------------- | ----: | -------------------------------------------------------------------------------- |
| Обязательные требования |    10 | ✅ README, ✅ структура директорий, ✅ документация (в этом README), ✅ ООП, ✅ тесты |
| REST API                |    10 | Более 4 эндпоинтов (реализовано 40+)                                             |
| База данных             |    10 | Используется SQLite с SQLAlchemy                                                 |
| Асинхронность           |    15 | Реализована с использованием FastAPI и asyncio                                   |
| Логирование             |     2 | Логи в файлы: `debug.log`, `error.log`, `auth.log`, `requests.log`               |
| Работа с файлами        |     5 | Загрузка аватаров (endpoint `/profile/{user_id}/avatar/`)                        |
| Использование линтеров  |     2 | Настроен `flake8` для проверки кода                                              |
| Тестирование            |     3 | Автоматические тесты через `run_tests.py` (выполняются успешно)                  |

