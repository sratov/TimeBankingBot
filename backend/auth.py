from jose import jwt
from fastapi import HTTPException, Security, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from datetime import datetime, timedelta
import hmac
import hashlib
import time
import logging
import sys
from logging.handlers import RotatingFileHandler
from typing import Dict, Union
from config import (
    JWT_SECRET_KEY,
    JWT_ALGORITHM,
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES,
    BOT_TOKEN,
)
import re
import urllib.parse

# ---------------------------------------------------------------------------
# logging setup
# ---------------------------------------------------------------------------
# Create logs directory if it doesn't exist
import os
os.makedirs('logs', exist_ok=True)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Clear existing handlers
if logger.handlers:
    logger.handlers = []

# Add console handler
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.DEBUG)
console_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)

# Add file handler
file_handler = RotatingFileHandler(
    'logs/auth.log',
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5
)
file_handler.setLevel(logging.DEBUG)
file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

logger.info("="*80)
logger.info("Authentication module initialized")
logger.info(f"BOT_TOKEN: {BOT_TOKEN[:5]}...{BOT_TOKEN[-5:]} (length: {len(BOT_TOKEN)})")
logger.info("="*80)

security = HTTPBearer()

# ---------------------------------------------------------------------------
# Telegram Web‑App hash verification
# ---------------------------------------------------------------------------

def verify_telegram_hash(init_data: str, received_hash: str) -> bool:
    """Validate init_data received from Telegram Mini‑app.
    https://core.telegram.org/bots/webapps#validating-data-received-via-the-web-app
    """
    try:
        logger.debug("\n" + "="*50)
        logger.debug("Starting Telegram WebApp hash verification")
        logger.debug("="*50)
        
        # Debug BOT_TOKEN for hidden whitespace
        logger.debug("BOT_TOKEN (repr): %r", BOT_TOKEN)
        logger.debug("BOT_TOKEN length: %d", len(BOT_TOKEN))
        logger.debug("init_data (repr): %r", init_data)
        logger.debug("received_hash: %s", received_hash)
        
        # Check for empty values
        if not init_data:
            logger.error("Empty init_data provided")
            return False
            
        if not received_hash:
            logger.error("Empty received_hash provided")
            return False
            
        if not BOT_TOKEN:
            logger.error("BOT_TOKEN is empty or not configured")
            return False
        
        # 1. Проверяем что hash присутствует в данных
        if "hash=" not in init_data:
            logger.error("No hash found in init_data")
            return False
        
        # 2. Разбиваем строку на пары key=value
        pairs = init_data.split('&')
        data_dict = {}
        
        for pair in pairs:
            if "=" in pair:
                key, value = pair.split("=", 1)
                data_dict[key] = value
        
        logger.debug("Parsed data dict: %s", {k: v for k, v in data_dict.items() if k != "hash"})
        
        # 3. Получаем значение хеша из словаря
        if "hash" not in data_dict:
            logger.error("No hash key in parsed data")
            return False
            
        dict_hash_value = data_dict["hash"]
        logger.debug("Hash from dictionary: %s", dict_hash_value)
        
        # Проверяем соответствие хеша в словаре и полученного хеша
        if dict_hash_value != received_hash:
            logger.warning(f"Hash mismatch: dictionary hash ({dict_hash_value}) != received hash ({received_hash})")
            # Используем хеш из словаря как более надежный источник
            received_hash = dict_hash_value
            logger.debug("Using hash from parsed data for verification")
        
        # 4. Prepare pairs for data_check_string, URL-decoding values
        data_check_components = []
        for pair_str in pairs:
            if pair_str.startswith("hash="):
                continue
            
            # Ensure there is an '=' to split on
            if "=" not in pair_str:
                logger.warning(f"Skipping malformed pair in init_data: {pair_str}")
                continue

            key, value_encoded = pair_str.split("=", 1)
            value_decoded = urllib.parse.unquote(value_encoded)
            data_check_components.append(f"{key}={value_decoded}")
            
        # 5. Сортируем компоненты в лексикографическом порядке
        data_check_components.sort()
        
        # 6. Соединяем через \n
        data_check_string = "\n".join(data_check_components)
        logger.debug("Data check string (values URL-decoded): %s", data_check_string)
        
        # 7. Создаем секретный ключ согласно документации Telegram
        # secret_key is the HMAC-SHA-256 signature of the bot's token with the label "WebAppData"
        web_app_data_key = hmac.new("WebAppData".encode(), BOT_TOKEN.encode(), hashlib.sha256).digest()
        logger.debug("Secret key created using HMAC_SHA256(<bot_token>, \"WebAppData\") (first 5 bytes): %r", web_app_data_key[:5])
        
        # 8. Вычисляем HMAC-SHA-256 хеш от data_check_string с использованием созданного ключа
        calculated_hash = hmac.new(
            web_app_data_key,
            data_check_string.encode(),
            hashlib.sha256
        ).hexdigest()
        logger.debug("Calculated hash: %s", calculated_hash)
        
        # 9. Сравниваем вычисленный хеш с полученным
        result = calculated_hash == received_hash
        logger.debug("Hash verification result: %s", result)
        
        if not result:
            logger.warning(f"Hash verification failed: calculated ({calculated_hash}) != received ({received_hash})")
            
            # Альтернативный метод проверки был удален, так как он стал идентичен основному
            # после предыдущих исправлений и не помогал с URL-декодированием.
            # Если основная проверка с URL-декодированием не сработает, 
            # нужно будет глубже анализировать формат данных от Telegram.
        
        logger.debug("="*50 + "\n")
        return result
    except Exception as e:
        logger.error("Error during hash verification: %s", str(e))
        logger.exception(e)
        return False


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------

def create_access_token(data: Dict) -> str:
    """Generate signed JWT access token."""
    expire = datetime.utcnow() + timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {**data, "exp": expire}
    token = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    logger.debug("JWT created for %s (exp %s)", data.get("username"), expire)
    return token


def verify_token(token: str) -> dict:
    """
    Функция для проверки JWT токена.
    Принимает строку с токеном.
    Возвращает payload из токена или вызывает исключение.
    """
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated (empty token string)")
        
    try:
        # Проверяем и декодируем токен
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Token verification failed: {str(e)}")


def get_current_user(request: Request) -> dict:
    """
    Проверяет наличие токена доступа в заголовке запроса.
    Возвращает данные пользователя из токена.
    """
    token = None
    
    # Сначала проверяем в cookie
    if "access_token" in request.cookies:
        token = request.cookies.get("access_token")
    
    # Если нет в cookie, проверяем в заголовке
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.replace("Bearer ", "")
    
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    return verify_token(token)
