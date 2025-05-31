import os
import shutil
import time
import json
import logging
import sys
import traceback
import uuid
import jwt  # Убедитесь, что установлен PyJWT
from jwt import ExpiredSignatureError, InvalidTokenError
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

from fastapi import (
    FastAPI,
    HTTPException,
    Depends,
    UploadFile,
    File,
    Query,
    Request,
    Response,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.requests import ClientDisconnect
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError
from pydantic import ValidationError

from . import models, schemas
from .database import SessionLocal, engine
from .auth import verify_telegram_hash, create_access_token, verify_token, get_current_user
from .config import (
    BOT_TOKEN,
    JWT_ALGORITHM,
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES,
    JWT_SECRET_KEY,
    ENVIRONMENT,
    IS_DEVELOPMENT,
)

# ========================================================================
# Константы и директории
# ========================================================================
BASE_DIR = Path(__file__).parent  # Папка "backend"

# Убедимся, что директории static/avatars существуют
STATIC_DIR = BASE_DIR / "static"
AVATAR_DIR = STATIC_DIR / "avatars"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
AVATAR_DIR.mkdir(parents=True, exist_ok=True)

# Создаём логи, если не существует
os.makedirs(BASE_DIR.parent / "logs", exist_ok=True)

# ========================================================================
# Конфигурация логирования
# ========================================================================
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.handlers = []

# Консольный обработчик
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.DEBUG)
console_formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)

# Файл-обработчик debug.log
debug_file_handler = logging.handlers.RotatingFileHandler(
    BASE_DIR.parent / "logs" / "debug.log",
    maxBytes=10 * 1024 * 1024,
    backupCount=10,
)
debug_file_handler.setLevel(logging.DEBUG)
debug_file_handler.setFormatter(console_formatter)
logger.addHandler(debug_file_handler)

# Файл-обработчик error.log
error_file_handler = logging.handlers.RotatingFileHandler(
    BASE_DIR.parent / "logs" / "error.log",
    maxBytes=10 * 1024 * 1024,
    backupCount=10,
)
error_file_handler.setLevel(logging.ERROR)
error_formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s\n%(pathname)s:%(lineno)d\n%(message)s\n"
)
error_file_handler.setFormatter(error_formatter)
logger.addHandler(error_file_handler)

# Файл-обработчик requests.log
requests_file_handler = logging.handlers.RotatingFileHandler(
    BASE_DIR.parent / "logs" / "requests.log",
    maxBytes=10 * 1024 * 1024,
    backupCount=10,
)
requests_file_handler.setLevel(logging.INFO)
requests_formatter = logging.Formatter("%(asctime)s - %(message)s")
requests_file_handler.setFormatter(requests_formatter)
logger.addHandler(requests_file_handler)

# Файл-обработчик auth.log
auth_file_handler = logging.handlers.RotatingFileHandler(
    BASE_DIR.parent / "logs" / "auth.log",
    maxBytes=10 * 1024 * 1024,
    backupCount=10,
)
auth_file_handler.setLevel(logging.DEBUG)
auth_formatter = logging.Formatter("%(asctime)s - AUTH - %(levelname)s - %(message)s")
auth_file_handler.setFormatter(auth_formatter)
logger.addHandler(auth_file_handler)

logger.propagate = False

# Логгер модуля auth
auth_logger = logging.getLogger("auth")
auth_logger.setLevel(logging.DEBUG)
auth_logger.handlers = []
auth_logger.addHandler(console_handler)
auth_logger.addHandler(auth_file_handler)
auth_logger.propagate = False

# Логируем запуск сервиса
logger.info("=" * 80)
logger.info("Starting Time Banking API")
logger.info("=" * 80)
logger.info(f"Bot token: {BOT_TOKEN[:5]}...{BOT_TOKEN[-5:]} (length: {len(BOT_TOKEN)})")

# ========================================================================
# Инициализация FastAPI
# ========================================================================
app = FastAPI(
    title="Time Banking API",
    description="API for Time Banking service",
    version="1.0.0",
)

# ========================================================================
# CORS Middleware
# ========================================================================
origins = [
    "http://localhost:3000",
    "https://localhost:3000",
    "http://localhost:8000",
    "https://localhost:8000",
    "https://66fb-77-91-101-132.ngrok-free.app",
    "http://66fb-77-91-101-132.ngrok-free.app",
    "https://0e4c-77-91-101-132.ngrok-free.app",
    "http://0e4c-77-91-101-132.ngrok-free.app",
    "*",  # для разработки
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ========================================================================
# Монтирование статических файлов (avatars, css и т.д.)
# ========================================================================
app.mount(
    "/static",
    StaticFiles(directory=STATIC_DIR),
    name="static",
)

# ========================================================================
# Зависимость: доступ к сессии БД
# ========================================================================
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ========================================================================
# Middleware для логирования всех входящих запросов и ответов
# ========================================================================
@app.middleware("http")
async def log_requests(request: Request, call_next):
    request_id = str(uuid.uuid4())
    client_host = request.client.host if request.client else "unknown"
    client_port = request.client.port if request.client else "unknown"

    logger.info(f"[{request_id}] Request from {client_host}:{client_port} - {request.method} {request.url.path}")

    if request.query_params:
        logger.info(f"[{request_id}] Query params: {dict(request.query_params)}")

    if request.method not in ("POST", "PUT", "PATCH"):
        try:
            body = await request.body()
            if body:
                logger.info(f"[{request_id}] Request body: {body.decode()}")
        except Exception as e:
            logger.debug(f"[{request_id}] Could not log request body: {str(e)}")
    else:
        logger.info(f"[{request_id}] Request body for {request.method} will be processed by endpoint.")

    start_time = time.time()

    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        logger.info(f"[{request_id}] Response status: {response.status_code} - Completed in {process_time:.4f}s")
        return response
    except Exception as e:
        process_time = time.time() - start_time
        logger.error(f"[{request_id}] Error during request processing: {str(e)}")
        logger.error(f"[{request_id}] Error details: {traceback.format_exc()}")
        logger.error(f"[{request_id}] Failed after {process_time:.4f}s")
        raise


# ========================================================================
# Обработчики исключений
# ========================================================================
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    error_msg = f"Unhandled exception: {str(exc)}"
    logger.error(error_msg)
    logger.error(traceback.format_exc())
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error, check logs for details"},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    error_msg = f"Validation error: {str(exc)}"
    logger.error(error_msg)
    return JSONResponse(
        status_code=422,
        content={"detail": error_msg},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    logger.error(f"HTTP exception: {exc.status_code} - {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


# ========================================================================
# Роуты
# ========================================================================
@app.get("/")
async def root():
    return {"message": "Time Banking API is running"}


# --------------------------------------------------
# Инициализация базы, создание тестового пользователя
# --------------------------------------------------
UPLOAD_DIR = BASE_DIR.parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

models.Base.metadata.create_all(bind=engine)


def create_test_user():
    db = SessionLocal()
    try:
        user = db.query(models.User).filter(models.User.telegram_id == 12345).first()
        if not user:
            test_user = models.User(
                telegram_id=12345,
                username="test_user",
                balance=10.0,
                earned_hours=5.0,
                spent_hours=0.0,
            )
            db.add(test_user)
            db.commit()
    finally:
        db.close()


create_test_user()


# --------------------------------------------------
# Диагностический эндпоинт
# --------------------------------------------------
@app.get("/diagnostics")
async def diagnostics(db: Session = Depends(get_db)):
    """
    Диагностический эндпоинт для проверки состояния системы.
    """
    try:
        db_connection_ok = False
        db_error = None
        user_count = 0

        try:
            user_count = db.query(models.User).count()
            db_connection_ok = True
        except Exception as e:
            db_error = str(e)
            logger.error(f"Database connection error: {e}")

        auth_config = {
            "jwt_algorithm": JWT_ALGORITHM,
            "jwt_expiry_minutes": JWT_ACCESS_TOKEN_EXPIRE_MINUTES,
            "bot_token_length": len(BOT_TOKEN) if BOT_TOKEN else 0,
            "bot_token_first_chars": BOT_TOKEN[:4] if BOT_TOKEN else None,
            "bot_token_last_chars": BOT_TOKEN[-4:] if BOT_TOKEN else None,
        }

        fs_status = {
            "uploads_dir_exists": os.path.exists(BASE_DIR.parent / "uploads"),
            "logs_dir_exists": os.path.exists(BASE_DIR.parent / "logs"),
            "db_file_exists": os.path.exists(BASE_DIR.parent / "time_banking.db"),
            "db_file_size": os.path.getsize(BASE_DIR.parent / "time_banking.db")
            if os.path.exists(BASE_DIR.parent / "time_banking.db")
            else 0,
        }

        return {
            "api_status": "ok",
            "database": {
                "connection": db_connection_ok,
                "error": db_error,
                "user_count": user_count,
            },
            "auth_config": auth_config,
            "filesystem": fs_status,
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Diagnostics endpoint error: {e}")
        return {
            "api_status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
        }


# --------------------------------------------------
# Получить профиль текущего пользователя
# --------------------------------------------------
@app.get("/user/me/", response_model=schemas.UserProfile)
def get_user_me(
    response: Response,
    token_data: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    logger.debug("[GetUserMe] Attempting to get current user.")
    if not token_data:
        logger.error("[GetUserMe] No token data received from get_current_user.")
        raise HTTPException(status_code=401, detail="Not authenticated (no token data)")

    user_id = token_data.get("sub")
    logger.debug(f"[GetUserMe] Token SUB: {user_id}. Fetching user from DB.")

    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if db_user is None:
        logger.warning(f"[GetUserMe] User ID {user_id} from token not found in DB.")
        raise HTTPException(status_code=404, detail="User from token not found")

    logger.info(
        f"[GetUserMe] User {db_user.username} (ID: {db_user.id}) found. "
        f"Avatar path from DB to be returned: '{db_user.avatar}'"
    )

    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, proxy-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    response.headers["Surrogate-Control"] = "no-store"

    return db_user


# --------------------------------------------------
# Получить список всех листингов
# --------------------------------------------------
@app.get("/listings/", response_model=List[schemas.Listing])
def get_listings(
    request: Request,
    skip: int = 0,
    limit: int = 5,
    status: Optional[str] = None,
    listing_type: Optional[str] = None,
    db: Session = Depends(get_db),
):
    # Пытаемся аутентифицировать, но не требуем
    try:
        # Вместо get_current_user(request, db) — всего лишь request
        get_current_user(request)
    except HTTPException:
        pass

    query = db.query(models.Listing).options(
        joinedload(models.Listing.creator), joinedload(models.Listing.worker)
    )

    if status:
        query = query.filter(models.Listing.status == status)
    if listing_type:
        query = query.filter(models.Listing.listing_type == listing_type)

    listings = (
        query.order_by(models.Listing.created_at.desc()).offset(skip).limit(limit).all()
    )
    return listings


# --------------------------------------------------
# Создать новый листинг
# --------------------------------------------------
@app.post("/listings/", response_model=schemas.Listing)
def create_listing(
    listing: schemas.ListingCreate,
    db: Session = Depends(get_db),
    token_data: dict = Depends(get_current_user),
):
    if int(token_data["sub"]) != listing.user_id:
        raise HTTPException(status_code=403, detail="Cannot create listing for another user")

    user = db.query(models.User).filter(models.User.id == listing.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if listing.listing_type == "request" and user.balance < listing.hours:
        raise HTTPException(status_code=400, detail="Insufficient balance")

    db_listing = models.Listing(**listing.dict())
    db.add(db_listing)
    db.commit()
    db.refresh(db_listing)
    return db_listing


# --------------------------------------------------
# Откликнуться на листинг
# --------------------------------------------------
@app.post("/listings/{listing_id}/apply/")
def apply_for_listing(
    listing_id: int,
    db: Session = Depends(get_db),
    token_data: dict = Depends(get_current_user),
):
    listing = db.query(models.Listing).filter(models.Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    if listing.status != "active":
        raise HTTPException(status_code=400, detail="Listing is not active")

    if listing.listing_type == "offer":
        worker = db.query(models.User).filter(models.User.id == int(token_data["sub"])).first()
        if worker.balance < listing.hours:
            raise HTTPException(status_code=400, detail="Insufficient balance")

    listing.status = "pending_worker"
    listing.worker_id = int(token_data["sub"])
    db.commit()
    db.refresh(listing)
    return listing


# --------------------------------------------------
# Принять исполнителя
# --------------------------------------------------
@app.post("/listings/{listing_id}/accept/")
def accept_worker(
    listing_id: int,
    db: Session = Depends(get_db),
    token_data: dict = Depends(get_current_user),
):
    listing = db.query(models.Listing).filter(models.Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    if listing.user_id != int(token_data["sub"]):
        raise HTTPException(status_code=403, detail="Only listing creator can accept workers")

    if listing.status != "pending_worker":
        raise HTTPException(status_code=400, detail="Listing is not pending worker acceptance")

    prepayment_hours = round(listing.hours * 0.33, 1)

    creator = db.query(models.User).filter(models.User.id == listing.user_id).first()
    worker = db.query(models.User).filter(models.User.id == listing.worker_id).first()

    if listing.listing_type == "request":
        payer_id = listing.user_id
        receiver_id = listing.worker_id
        payer = creator
        receiver = worker
        description = f"Предоплата (33%) за помощь: {listing.title}"
    else:
        payer_id = listing.worker_id
        receiver_id = listing.user_id
        payer = worker
        receiver = creator
        description = f"Предоплата (33%) за услугу: {listing.title}"

    if payer.balance < prepayment_hours:
        raise HTTPException(status_code=400, detail="Недостаточно средств для предоплаты")

    payer.balance -= prepayment_hours
    receiver.balance += prepayment_hours

    transaction = models.Transaction(
        from_user_id=payer_id,
        to_user_id=receiver_id,
        hours=prepayment_hours,
        description=description,
        transaction_type="prepayment",
    )
    db.add(transaction)
    db.commit()

    listing.prepayment_transaction_id = transaction.id
    listing.status = "in_progress"

    db.commit()
    db.refresh(listing)
    return listing


# --------------------------------------------------
# Отклонить отклик исполнителя
# --------------------------------------------------
@app.post("/listings/{listing_id}/reject/")
def reject_worker(
    listing_id: int,
    db: Session = Depends(get_db),
    token_data: dict = Depends(get_current_user),
):
    listing = db.query(models.Listing).filter(models.Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    if listing.user_id != int(token_data["sub"]):
        raise HTTPException(status_code=403, detail="Only listing creator can reject workers")

    if listing.status != "pending_worker":
        raise HTTPException(status_code=400, detail="Listing is not pending worker acceptance")

    listing.status = "active"
    listing.worker_id = None
    db.commit()
    db.refresh(listing)
    return listing


# --------------------------------------------------
# Предоплата для offer-типов
# --------------------------------------------------
@app.post("/listings/{listing_id}/pay/")
def make_payment(
    listing_id: int,
    db: Session = Depends(get_db),
    token_data: dict = Depends(get_current_user),
):
    listing = db.query(models.Listing).filter(models.Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    if listing.worker_id != int(token_data["sub"]):
        raise HTTPException(status_code=403, detail="Only worker can make payment")

    if listing.status != "pending_payment":
        raise HTTPException(status_code=400, detail="Listing is not pending payment")

    prepayment_hours = round(listing.hours * 0.33, 1)

    creator = db.query(models.User).filter(models.User.id == listing.user_id).first()
    worker = db.query(models.User).filter(models.User.id == listing.worker_id).first()

    payer_id = listing.worker_id
    receiver_id = listing.user_id
    payer = worker
    receiver = creator
    description = f"Предоплата (33%) за услугу: {listing.title}"

    if payer.balance < prepayment_hours:
        raise HTTPException(status_code=400, detail="Недостаточно средств для предоплаты")

    payer.balance -= prepayment_hours
    receiver.balance += prepayment_hours

    transaction = models.Transaction(
        from_user_id=payer_id,
        to_user_id=receiver_id,
        hours=prepayment_hours,
        description=description,
        transaction_type="prepayment",
    )
    db.add(transaction)
    db.commit()

    listing.prepayment_transaction_id = transaction.id
    listing.status = "in_progress"

    db.commit()
    db.refresh(listing)
    return listing


# --------------------------------------------------
# Завершение листинга (worker/creator ставят “complete”)
# --------------------------------------------------
@app.post("/listings/{listing_id}/complete/")
def complete_listing(
    listing_id: int,
    db: Session = Depends(get_db),
    token_data: dict = Depends(get_current_user),
):
    listing = db.query(models.Listing).filter(models.Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    if listing.listing_type == "request":
        if listing.worker_id != int(token_data["sub"]):
            raise HTTPException(status_code=403, detail="Only worker can mark request as complete")
    else:
        if listing.user_id != int(token_data["sub"]):
            raise HTTPException(status_code=403, detail="Only creator can mark offer as complete")

    if listing.status != "in_progress":
        raise HTTPException(status_code=400, detail="Listing is not in progress")

    listing.status = "pending_confirmation"
    db.commit()
    db.refresh(listing)
    return listing


# --------------------------------------------------
# Подтверждение завершения (creator/worker ставят “confirm”)
# --------------------------------------------------
@app.post("/listings/{listing_id}/confirm/")
def confirm_completion(
    listing_id: int,
    db: Session = Depends(get_db),
    token_data: dict = Depends(get_current_user),
):
    listing = db.query(models.Listing).filter(models.Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    if listing.listing_type == "request":
        if listing.user_id != int(token_data["sub"]):
            raise HTTPException(status_code=403, detail="Only listing creator can confirm request completion")
    else:
        if listing.worker_id != int(token_data["sub"]):
            raise HTTPException(status_code=403, detail="Only worker can confirm offer completion")

    if listing.status != "pending_confirmation":
        raise HTTPException(status_code=400, detail="Listing is not pending confirmation")

    creator = db.query(models.User).filter(models.User.id == listing.user_id).first()
    worker = db.query(models.User).filter(models.User.id == listing.worker_id).first()

    prepayment_transaction = db.query(models.Transaction).filter(
        models.Transaction.id == listing.prepayment_transaction_id
    ).first()
    prepayment_amount = prepayment_transaction.hours if prepayment_transaction else 0
    remaining_hours = listing.hours - prepayment_amount

    if listing.listing_type == "request":
        payer_id = listing.user_id
        receiver_id = listing.worker_id
        payer = creator
        receiver = worker
        description = f"Окончательная оплата (67%) за помощь: {listing.title}"

        receiver_earned = worker
        payer_spent = creator
    else:
        payer_id = listing.worker_id
        receiver_id = listing.user_id
        payer = worker
        receiver = creator
        description = f"Окончательная оплата (67%) за услугу: {listing.title}"

        receiver_earned = creator
        payer_spent = worker

    if payer.balance < remaining_hours:
        raise HTTPException(status_code=400, detail="Недостаточно средств для окончательной оплаты")

    payer.balance -= remaining_hours
    receiver.balance += remaining_hours

    final_transaction = models.Transaction(
        from_user_id=payer_id,
        to_user_id=receiver_id,
        hours=remaining_hours,
        description=description,
        transaction_type="payment",
    )
    db.add(final_transaction)
    db.commit()

    receiver_earned.earned_hours += listing.hours
    payer_spent.spent_hours += listing.hours

    listing.status = "completed"
    db.commit()
    db.refresh(listing)
    return listing


# --------------------------------------------------
# Отмена листинга
# --------------------------------------------------
@app.post("/listings/{listing_id}/cancel/")
def cancel_listing(
    listing_id: int,
    db: Session = Depends(get_db),
    token_data: dict = Depends(get_current_user),
):
    listing = db.query(models.Listing).filter(models.Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    if listing.user_id != int(token_data["sub"]):
        raise HTTPException(status_code=403, detail="Only listing creator can cancel listing")

    if listing.status not in ["active", "pending_worker"]:
        raise HTTPException(status_code=400, detail="Cannot cancel listing in current status")

    listing.status = "cancelled"
    listing.worker_id = None
    db.commit()
    db.refresh(listing)
    return listing


# --------------------------------------------------
# Получить список друзей
# --------------------------------------------------
@app.get("/friends/", response_model=List[schemas.Friend])
def get_friends(db: Session = Depends(get_db), token_data: dict = Depends(get_current_user)):
    user_id = int(token_data["sub"])
    friends = (
        db.query(models.Friend)
        .filter(
            ((models.Friend.user_id == user_id) | (models.Friend.friend_id == user_id))
            & (models.Friend.status == "accepted")
        )
        .options(joinedload(models.Friend.user), joinedload(models.Friend.friend))
        .all()
    )

    return [
        schemas.Friend(
            id=friend.id,
            user_id=friend.user_id,
            friend_id=friend.friend_id,
            status=friend.status,
            created_at=friend.created_at,
            user=friend.user,
            friend=friend.friend,
        )
        for friend in friends
    ]


# --------------------------------------------------
# Отправить запрос в друзья
# --------------------------------------------------
@app.post("/friends/request/", response_model=schemas.Friend)
def send_friend_request(
    friend_request: schemas.FriendCreate,
    db: Session = Depends(get_db),
    token_data: dict = Depends(get_current_user),
):
    sender_id = int(token_data["sub"])
    friend_id = friend_request.friend_id

    existing_request = (
        db.query(models.Friend)
        .filter(
            ((models.Friend.user_id == sender_id) & (models.Friend.friend_id == friend_id))
            | ((models.Friend.user_id == friend_id) & (models.Friend.friend_id == sender_id))
        )
        .first()
    )

    if existing_request:
        raise HTTPException(status_code=400, detail="Friend request already exists")

    friend = models.Friend(user_id=sender_id, friend_id=friend_id, status="pending")
    db.add(friend)
    db.commit()
    db.refresh(friend)

    db.refresh(friend.user)
    db.refresh(friend.friend)

    return friend


# --------------------------------------------------
# Принять запрос в друзья
# --------------------------------------------------
@app.post("/friends/{friend_id}/accept/")
def accept_friend_request(
    friend_id: int,
    db: Session = Depends(get_db),
    token_data: dict = Depends(get_current_user),
):
    current_user_id = int(token_data["sub"])
    friend_request = db.query(models.Friend).filter(models.Friend.id == friend_id).first()
    if not friend_request:
        raise HTTPException(status_code=404, detail="Friend request not found")

    if friend_request.friend_id != current_user_id:
        raise HTTPException(status_code=403, detail="Only the recipient can accept friend request")

    if friend_request.status != "pending":
        raise HTTPException(status_code=400, detail="Friend request is not pending")

    friend_request.status = "accepted"
    db.commit()
    db.refresh(friend_request)
    return friend_request


# --------------------------------------------------
# Отклонить запрос в друзья
# --------------------------------------------------
@app.post("/friends/{friend_id}/reject/")
def reject_friend_request(
    friend_id: int,
    db: Session = Depends(get_db),
    token_data: dict = Depends(get_current_user),
):
    current_user_id = int(token_data["sub"])
    friend_request = db.query(models.Friend).filter(models.Friend.id == friend_id).first()
    if not friend_request:
        raise HTTPException(status_code=404, detail="Friend request not found")

    if friend_request.friend_id != current_user_id:
        raise HTTPException(status_code=403, detail="Only the recipient can reject friend request")

    if friend_request.status != "pending":
        raise HTTPException(status_code=400, detail="Friend request is not pending")

    db.delete(friend_request)
    db.commit()
    return {"status": "rejected"}


# --------------------------------------------------
# Получить транзакции пользователя
# --------------------------------------------------
@app.get("/transactions/{user_id}/", response_model=List[schemas.Transaction])
def get_transactions(
    user_id: int, db: Session = Depends(get_db), token_data: dict = Depends(get_current_user)
):
    if int(token_data["sub"]) != user_id:
        raise HTTPException(status_code=403, detail="Cannot view transactions for another user")

    transactions = (
        db.query(models.Transaction)
        .filter(
            (models.Transaction.from_user_id == user_id)
            | (models.Transaction.to_user_id == user_id)
        )
        .options(
            joinedload(models.Transaction.from_user), joinedload(models.Transaction.to_user)
        )
        .order_by(models.Transaction.created_at.desc())
        .all()
    )
    return transactions


# --------------------------------------------------
# Загрузка аватара пользователя
# --------------------------------------------------
@app.post("/profile/{user_id}/avatar/")
async def upload_avatar(
    user_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),                # <- Обязательно Depends(get_db)
    token_data: dict = Depends(get_current_user),  # <- Данные токена
):
    """
    Загружает аватар пользователя:
    1. Проверяем, что токен принадлежит этому user_id
    2. Сохраняем файл в backend/static/avatars/
    3. Сохраняем относительный URL (/static/avatars/...) в БД
    """
    if token_data.get("sub") != str(user_id):
        raise HTTPException(status_code=403, detail="Not authorized")

    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    # Статические файлы уже созданы ранее
    file_extension = Path(file.filename).suffix
    timestamp = int(time.time())
    filename_stem = f"user_{user_id}_avatar_{timestamp}{file_extension}"
    avatar_path_on_disk = AVATAR_DIR / filename_stem

    try:
        with avatar_path_on_disk.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not save avatar file: {e}")
    finally:
        file.file.close()

    avatar_url = f"/static/avatars/{filename_stem}"
    db_user.avatar = avatar_url

    try:
        db.commit()
        db.refresh(db_user)
    except Exception as e:
        db.rollback()
        try:
            os.remove(str(avatar_path_on_disk))
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Could not update user avatar in DB: {e}")

    return {"avatar_url": avatar_url}


# --------------------------------------------------
# Получить все листинги пользователя (creator или worker)
# --------------------------------------------------
@app.get("/listings/user/{user_id}/", response_model=List[schemas.Listing])
def get_user_listings(
    user_id: int, db: Session = Depends(get_db), token_data: dict = Depends(get_current_user)
):
    current_user_id = int(token_data["sub"])
    if current_user_id != user_id:
        friendship = (
            db.query(models.Friend)
            .filter(
                ((models.Friend.user_id == current_user_id) & (models.Friend.friend_id == user_id))
                | ((models.Friend.user_id == user_id) & (models.Friend.friend_id == current_user_id))
            )
            .filter(models.Friend.status == "accepted")
            .first()
        )
        if not friendship:
            raise HTTPException(
                status_code=403, detail="You can only view listings of yourself or your friends"
            )

    listings = (
        db.query(models.Listing)
        .filter((models.Listing.user_id == user_id) | (models.Listing.worker_id == user_id))
        .options(joinedload(models.Listing.creator), joinedload(models.Listing.worker))
        .order_by(models.Listing.created_at.desc())
        .all()
    )

    return listings


# --------------------------------------------------
# Поиск пользователей по username
# --------------------------------------------------
@app.get("/users/search/", response_model=List[schemas.UserProfile])
def search_users(username: str, db: Session = Depends(get_db), token_data: dict = Depends(get_current_user)):
    current_user_id = int(token_data["sub"])

    users = (
        db.query(models.User)
        .filter(
            models.User.username.ilike(f"%{username}%") & (models.User.id != current_user_id)
        )
        .limit(10)
        .all()
    )

    return users


# --------------------------------------------------
# Получить входящие запросы в друзья
# --------------------------------------------------
@app.get("/friends/pending/", response_model=List[schemas.Friend])
def get_pending_friend_requests(db: Session = Depends(get_db), token_data: dict = Depends(get_current_user)):
    user_id = int(token_data["sub"])

    pending_requests = (
        db.query(models.Friend)
        .filter((models.Friend.friend_id == user_id) & (models.Friend.status == "pending"))
        .options(joinedload(models.Friend.user), joinedload(models.Friend.friend))
        .all()
    )

    return pending_requests


# --------------------------------------------------
# Получить список партнеров по завершённым сделкам
# --------------------------------------------------
@app.get("/users/transactions/", response_model=List[schemas.UserProfile])
def get_transaction_partners(db: Session = Depends(get_db), token_data: dict = Depends(get_current_user)):
    user_id = int(token_data["sub"])
    logger.info(f"[GetTransactionPartners] Fetching transaction partners for user_id: {user_id}")

    listings = (
        db.query(models.Listing)
        .filter(
            ((models.Listing.user_id == user_id) | (models.Listing.worker_id == user_id))
            & (models.Listing.status == "completed")
        )
        .all()
    )
    logger.info(f"[GetTransactionPartners] Found {len(listings)} completed listings involving user {user_id}")

    partner_ids = set()
    for listing in listings:
        if listing.user_id == user_id and listing.worker_id:
            partner_ids.add(listing.worker_id)
            logger.debug(
                f"[GetTransactionPartners] Added partner_id {listing.worker_id} "
                f"(from listing {listing.id}, user was creator)"
            )
        elif listing.worker_id == user_id and listing.user_id:
            partner_ids.add(listing.user_id)
            logger.debug(
                f"[GetTransactionPartners] Added partner_id {listing.user_id} "
                f"(from listing {listing.id}, user was worker)"
            )

    logger.info(f"[GetTransactionPartners] Collected partner_ids: {partner_ids}")

    if not partner_ids:
        logger.info("[GetTransactionPartners] No partner IDs found, returning empty list.")
        return []

    partners = db.query(models.User).filter(models.User.id.in_(partner_ids)).all()
    logger.info(f"[GetTransactionPartners] Fetched {len(partners)} partner user objects from DB.")

    if partners:
        for p_idx, partner_user in enumerate(partners):
            logger.debug(
                f"[GetTransactionPartners] Returning partner {p_idx + 1}: ID={partner_user.id}, "
                f"Username={partner_user.username}"
            )
    else:
        logger.debug("[GetTransactionPartners] No partner objects to return after DB query.")

    return partners


# --------------------------------------------------
# Отладочный POST для создания тестового пользователя и получения токенов
# --------------------------------------------------
@app.post("/debug/auth/")
async def debug_auth_post(request: Request, response: Response, db: Session = Depends(get_db)):
    """
    Создаёт тестового пользователя и возвращает access+refresh токены в cookies.
    Работает только в режиме разработки (IS_DEVELOPMENT=True).
    """
    if not IS_DEVELOPMENT:
        logger.warning("Debug auth POST requested but server is in production mode - rejecting")
        raise HTTPException(status_code=403, detail="Debug endpoints are not allowed in production")

    logger.warning("\n\n" + "*" * 80)
    logger.warning("=== Starting Debug Auth POST ===")
    logger.warning("*" * 80)

    body_str = None
    data = None

    try:
        logger.debug("Attempting to read request body for /debug/auth POST...")
        body_bytes = await asyncio.wait_for(request.body(), timeout=10.0)

        if not body_bytes:
            logger.error("Request body is empty for /debug/auth POST")
            raise HTTPException(status_code=400, detail="Request body is empty for debug auth")

        body_str = body_bytes.decode("utf-8")
        logger.info(f"Successfully read body for /debug/auth POST, length: {len(body_str)}")
        logger.debug(f"Raw request body for /debug/auth POST: {body_str[:500]}...")

        data = json.loads(body_str)
        logger.debug(f"Parsed JSON data for /debug/auth POST: {data}")

    except asyncio.TimeoutError:
        logger.error("Timeout (10s) reading request body for /debug/auth POST")
        raise HTTPException(status_code=408, detail="Request timeout reading body for debug auth")
    except ClientDisconnect:
        logger.error("ClientDisconnect while reading request body for /debug/auth POST")
        raise HTTPException(status_code=400, detail="Client disconnected during debug auth request")
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error for /debug/auth POST: {str(e)}. Body was: {body_str[:200]}...")
        raise HTTPException(status_code=400, detail=f"Invalid JSON body for debug auth: {str(e)}")
    except Exception as e:
        logger.error(f"Error processing request body for /debug/auth POST: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Invalid request body for debug auth: {str(e)}")

    if not data or "telegram_id" not in data or "username" not in data:
        logger.error(f"Missing telegram_id or username in parsed data for /debug/auth: {data}")
        raise HTTPException(status_code=400, detail="telegram_id and username are required in JSON body for debug auth")

    telegram_id = data["telegram_id"]
    username = data["username"]

    logger.warning(f"Creating/fetching test user for /debug/auth: telegram_id={telegram_id}, username={username}")

    user = db.query(models.User).filter(models.User.telegram_id == telegram_id).first()

    if not user:
        logger.warning(f"User {telegram_id} not found, creating new user")
        user = models.User(
            telegram_id=telegram_id,
            username=username,
            first_name="Test",
            balance=100.0,
            role="user",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        logger.warning(f"User {telegram_id} found in database, using existing user")

    access_token = create_access_token(
        data={"sub": str(user.id), "telegram_id": user.telegram_id, "type": "access"}
    )
    refresh_token_val = create_access_token(
        {
            "sub": str(user.id),
            "telegram_id": str(user.telegram_id),
            "username": user.username,
            "type": "refresh",
            "exp": datetime.utcnow() + timedelta(days=7),
        }
    )

    response = JSONResponse(
        content={
            "success": True,
            "user": {
                "id": user.id,
                "telegram_id": user.telegram_id,
                "username": user.username,
                "balance": user.balance,
            },
            "test_mode": True,
        }
    )

    cookie_options = {"httponly": True, "secure": True, "samesite": "none", "path": "/"}

    response.set_cookie(
        key="access_token",
        value=access_token,
        max_age=JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        **cookie_options,
    )

    response.set_cookie(
        key="refresh_token", value=refresh_token_val, max_age=60 * 60 * 24 * 7, **cookie_options
    )

    return response


# --------------------------------------------------
# Отладочный GET для проверки auth-данных
# --------------------------------------------------
@app.get("/debug/auth/")
async def debug_auth(request: Request, db: Session = Depends(get_db)):
    """
    Диагностика Telegram-auth: собираем заголовки, куки, query params,
    выводим состояние БД и файловой системы.
    Работает только в режиме разработки.
    """
    if not IS_DEVELOPMENT:
        logger.warning("Debug auth endpoint requested but server is in production mode - rejecting")
        raise HTTPException(status_code=403, detail="Debug endpoints are not allowed in production")

    logger.info("\n\n" + "*" * 80)
    logger.info("=== Starting Auth Debug ===")
    logger.info("*" * 80)

    headers = dict(request.headers)
    cookies = request.cookies
    query_params = dict(request.query_params)

    config_info = {
        "bot_token_length": len(BOT_TOKEN),
        "bot_token_start": BOT_TOKEN[:5] if BOT_TOKEN else None,
        "bot_token_end": BOT_TOKEN[-5:] if BOT_TOKEN else None,
    }

    db_status = {}
    try:
        db_session = SessionLocal()
        try:
            user_count = db_session.query(models.User).count()
            db_status["user_count"] = user_count

            users = db_session.query(models.User).all()
            db_status["users"] = [
                {
                    "id": user.id,
                    "telegram_id": user.telegram_id,
                    "username": user.username,
                    "created_at": user.created_at.isoformat() if user.created_at else None,
                }
                for user in users
            ]

            db_status["status"] = "ok"
        except Exception as e:
            db_status["status"] = "error"
            db_status["error"] = str(e)
        finally:
            db_session.close()
    except Exception as e:
        db_status["status"] = "connection_error"
        db_status["error"] = str(e)

    fs_info = {
        "uploads_dir_exists": os.path.exists(BASE_DIR.parent / "uploads"),
        "logs_dir_exists": os.path.exists(BASE_DIR.parent / "logs"),
        "db_file_exists": os.path.exists(BASE_DIR.parent / "time_banking.db"),
        "db_file_size": os.path.getsize(BASE_DIR.parent / "time_banking.db")
        if os.path.exists(BASE_DIR.parent / "time_banking.db")
        else 0,
    }

    telegram_debug = {}
    if "init_data" in query_params:
        init_data = query_params["init_data"]
        telegram_debug["init_data"] = init_data

        try:
            pairs = [s.split("=", 1) for s in init_data.split("&") if "=" in s]
            data = {k: v for k, v in pairs}
            telegram_debug["parsed_data"] = data

            if "hash" in data:
                hash_value = data["hash"]
                telegram_debug["hash"] = hash_value

                try:
                    verification_result = verify_telegram_hash(init_data, hash_value)
                    logger.info(f"Hash verification result: {verification_result}")
                except Exception as e:
                    logger.error(f"Hash verification error: {str(e)}")
            else:
                telegram_debug["hash_missing"] = True

            if "user" in data:
                try:
                    import urllib.parse

                    user_json = urllib.parse.unquote(data["user"])
                    user_info = json.loads(user_json)
                    telegram_debug["user_info"] = {
                        "id": user_info.get("id"),
                        "username": user_info.get("username"),
                        "has_photo": "photo_url" in user_info,
                    }
                except Exception as e:
                    telegram_debug["user_parse_error"] = str(e)
        except Exception as e:
            telegram_debug["parse_error"] = str(e)

    debug_info = {
        "timestamp": datetime.utcnow().isoformat(),
        "request": {
            "headers": {k: v for k, v in headers.items() if k.lower() not in ["authorization"]},
            "cookies": {k: v for k, v in cookies.items()},
            "query_params": {k: v for k, v in query_params.items() if k != "init_data"},
            "has_init_data": "init_data" in query_params,
        },
        "config": config_info,
        "database": db_status,
        "filesystem": fs_info,
        "telegram_debug": telegram_debug,
    }

    logger.info(f"Auth debug complete: {debug_info}")
    logger.info("=== Auth Debug Completed ===")
    logger.info("*" * 80 + "\n\n")

    return debug_info


# --------------------------------------------------
# Просмотр логов (admin)
# --------------------------------------------------
@app.get("/admin/logs/{log_name}/")
async def view_logs(
    log_name: str, lines: int = Query(100, ge=1, le=1000), db: Session = Depends(get_current_user)
):
    """
    Просмотр логов приложения (debug, error, auth, requests).
    """
    valid_logs = ["debug", "error", "auth", "requests"]
    if log_name not in valid_logs:
        raise HTTPException(status_code=400, detail=f"Invalid log name. Available logs: {', '.join(valid_logs)}")

    log_path = BASE_DIR.parent / "logs" / f"{log_name}.log"
    if not os.path.exists(log_path):
        return {"status": "empty", "message": f"Log file {log_name}.log does not exist yet"}

    try:
        result = []
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            try:
                f.seek(0, os.SEEK_END)
                file_size = f.tell()
                if file_size == 0:
                    return {"status": "empty", "message": f"Log file {log_name}.log is empty"}

                bytes_to_read = min(8192, file_size)
                lines_found = 0
                chunks = []

                while lines_found < lines and bytes_to_read <= file_size:
                    f.seek(-bytes_to_read, os.SEEK_END)
                    chunk = f.read(bytes_to_read)
                    lines_in_chunk = chunk.count("\n")

                    if lines_in_chunk >= lines:
                        chunks.append(chunk)
                        break
                    else:
                        chunks.append(chunk)
                        lines_found += lines_in_chunk
                        bytes_to_read *= 2
                        if bytes_to_read > file_size:
                            f.seek(0)
                            chunks = [f.read()]
                            break

                content = "".join(chunks)
                all_lines = content.split("\n")
                result = all_lines[-lines - 1 :] if all_lines[-1] else all_lines[-lines - 2 :]
            except Exception as e:
                logger.error(f"Error reading log file {log_name}.log: {str(e)}")
                f.seek(0)
                result = f.readlines()[-lines:]

        return {
            "status": "success",
            "log_name": log_name,
            "lines_count": len(result),
            "content": result,
        }
    except Exception as e:
        logger.error(f"Error retrieving logs: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving logs: {str(e)}")


# --------------------------------------------------
# Аутентификация через Telegram WebApp
# --------------------------------------------------
@app.get("/auth/telegram/")
@app.post("/auth/telegram/")
async def telegram_auth(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),  # только DB, без Depends(get_current_user)
):
    import urllib.parse

    try:
        logger.info("\n\n" + "*" * 80)
        logger.info("=== Starting Telegram Authentication ===")
        logger.info("*" * 80)

        logger.debug("Request headers:")
        for header, value in request.headers.items():
            logger.debug(f"  {header}: {value}")

        logger.debug(f"Request method: {request.method}")

        raw_init_data = None
        test_mode = False

        if request.method == "GET":
            if "init_data" in request.query_params:
                raw_init_data = request.query_params.get("init_data", "")
                logger.debug("Got init_data from query params (GET)")
        else:
            raw_init_data = None
            body_str = None

            logger.debug("POST request to /auth/telegram. Processing body...")
            try:
                logger.debug("Attempt 1: Reading entire request body for POST with timeout...")
                body_bytes = await asyncio.wait_for(request.body(), timeout=10.0)

                if body_bytes:
                    body_str = body_bytes.decode("utf-8")
                    logger.info(f"Successfully read entire body (POST), length: {len(body_str)}")
                    logger.debug(f"Raw request body (POST): {body_str[:500]}...")

                    try:
                        json_data = json.loads(body_str)
                        logger.debug(f"Parsed JSON data: {json_data}")

                        if "init_data" in json_data:
                            raw_init_data = json_data.get("init_data")
                            test_mode = json_data.get("test_mode", False)
                            logger.info(f"Got init_data from JSON body (POST), test_mode={test_mode}")

                            # Обработка тестового режима
                            if test_mode:
                                logger.warning("Test mode detected in /auth/telegram! Creating test user...")
                                if not IS_DEVELOPMENT:
                                    logger.error(
                                        "Test mode for /auth/telegram requested but server is in production mode - rejecting"
                                    )
                                    raise HTTPException(
                                        status_code=403,
                                        detail="Test mode for /auth/telegram is not allowed in production",
                                    )

                                test_user = db.query(models.User).filter(models.User.telegram_id == 12345).first()
                                if not test_user:
                                    logger.info("Creating test user with id 12345 for /auth/telegram")
                                    test_user = models.User(
                                        telegram_id=12345,
                                        username="test_user",
                                        balance=100.0,
                                        earned_hours=0.0,
                                        spent_hours=0.0,
                                    )
                                    db.add(test_user)
                                    db.commit()
                                    db.refresh(test_user)
                                else:
                                    logger.info("Found existing test user for /auth/telegram")

                                access_token = create_access_token(
                                    {"sub": str(test_user.id), "telegram_id": str(test_user.telegram_id), "username": test_user.username, "type": "access"}
                                )
                                refresh_token_val = create_access_token(
                                    {
                                        "sub": str(test_user.id),
                                        "telegram_id": str(test_user.telegram_id),
                                        "username": test_user.username,
                                        "type": "refresh",
                                        "exp": datetime.utcnow() + timedelta(days=7),
                                    }
                                )

                                cookie_options = {"httponly": True, "secure": True, "samesite": "none", "path": "/"}
                                response.set_cookie(
                                    key="access_token",
                                    value=access_token,
                                    max_age=JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                                    **cookie_options,
                                )
                                response.set_cookie(
                                    key="refresh_token", value=refresh_token_val, max_age=60 * 60 * 24 * 7, **cookie_options
                                )

                                logger.info("Returning test user data and token in cookies for /auth/telegram (test_mode=true)")
                                return {"success": True, "user": test_user, "test_mode": True}

                    except json.JSONDecodeError:
                        logger.warning(f"Body (POST) was not valid JSON. Content starts with: {body_str[:200]}...")
                else:
                    logger.warning("Attempt 1: Request body (POST) was empty after reading.")

            except asyncio.TimeoutError:
                logger.error("Attempt 1: Timeout (10s) reading request body (POST).")
            except ClientDisconnect:
                logger.error("Attempt 1: ClientDisconnect while reading request body (POST).")
            except Exception as e:
                logger.error(f"Attempt 1: Error reading request body (POST): {str(e)}", exc_info=True)

            if not raw_init_data:
                logger.info("Attempt 2: init_data not found in JSON body or body read failed/was not JSON. Trying to read as form data...")
                try:
                    form_data = await asyncio.wait_for(request.form(), timeout=5.0)
                    if "init_data" in form_data:
                        raw_init_data = form_data.get("init_data", "")
                        test_mode_form = str(form_data.get("test_mode", "false")).lower() == "true"
                        if test_mode_form and not test_mode:
                            test_mode = True
                        logger.info(f"Got init_data from form data (POST), test_mode from form: {test_mode}")
                    elif form_data:
                        logger.warning(f"Attempt 2: init_data not in form data. Form fields: {list(form_data.keys())}")
                    else:
                        logger.warning("Attempt 2: Form data (POST) is empty.")
                except asyncio.TimeoutError:
                    logger.error("Attempt 2: Timeout (5s) reading form data (POST).")
                except ClientDisconnect:
                    logger.error("Attempt 2: ClientDisconnect while reading form data (POST).")
                except Exception as form_error:
                    logger.error(f"Attempt 2: Error reading form data (POST): {str(form_error)}", exc_info=True)

        if not raw_init_data:
            logger.error("No init_data found in request")
            raise HTTPException(status_code=400, detail="Missing init_data parameter")

        logger.debug(f"Raw init_data: {raw_init_data}")

        # Тестовый режим: сразу выдаём токены и пользователя
        if test_mode:
            if not IS_DEVELOPMENT:
                logger.warning("Test mode requested but server is in production mode - rejecting")
                raise HTTPException(status_code=403, detail="Test mode is not allowed in production")

            logger.warning("Test mode active - bypassing hash verification")
            try:
                test_user = db.query(models.User).filter(models.User.telegram_id == 12345).first()
                if not test_user:
                    logger.info("Creating test user with id 12345")
                    test_user = models.User(
                        telegram_id=12345,
                        username="test_user",
                        balance=100.0,
                        earned_hours=0.0,
                        spent_hours=0.0,
                    )
                    db.add(test_user)
                    db.commit()
                    db.refresh(test_user)
                else:
                    logger.info("Found existing test user for /auth/telegram")

                access_token = create_access_token(
                    {"sub": str(test_user.id), "telegram_id": str(test_user.telegram_id), "username": test_user.username, "type": "access"}
                )
                refresh_token = create_access_token(
                    {
                        "sub": str(test_user.id),
                        "telegram_id": str(test_user.telegram_id),
                        "username": test_user.username,
                        "type": "refresh",
                        "exp": datetime.utcnow() + timedelta(days=7),
                    }
                )

                cookie_options = {"httponly": True, "secure": True, "samesite": "none", "path": "/"}
                response.set_cookie(
                    key="access_token", value=access_token, max_age=JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60, **cookie_options
                )
                response.set_cookie(
                    key="refresh_token", value=refresh_token, max_age=60 * 60 * 24 * 7, **cookie_options
                )

                logger.info("Returning test user data and token in cookies")
                return {"success": True, "user": test_user, "test_mode": True}
            except Exception as test_error:
                logger.error(f"Error in test mode: {str(test_error)}")
                logger.exception(test_error)
                raise HTTPException(status_code=500, detail="Error in test mode")

        # ---------------------------------------------
        # Проверяем, что в raw_init_data есть "hash="
        # ---------------------------------------------
        if "hash=" not in raw_init_data:
            logger.error("No hash parameter found in init_data")
            raise HTTPException(status_code=400, detail="No hash provided")

        pairs = [s.split("=", 1) for s in raw_init_data.split("&") if "=" in s]
        data = {k: v for k, v in pairs}

        logger.debug(f"Parsed data parameters count: {len(data)}")
        for key in data:
            if key not in ["hash", "user"]:
                logger.debug(f"  {key}: {data[key]}")
            else:
                logger.debug(f"  {key}: [hidden for security]")

        hash_value = data.get("hash")
        if not hash_value:
            logger.error("No hash parameter found in parsed data")
            raise HTTPException(status_code=400, detail="No hash provided")

        logger.debug(f"Extracted hash value length: {len(hash_value) if hash_value else 0}")

        # ---------------------------------------------
        # Верифицируем hash через auth.verify_telegram_hash
        # ---------------------------------------------
        logger.info("Verifying Telegram hash...")
        hash_verified = verify_telegram_hash(raw_init_data, hash_value)

        if not hash_verified:
            logger.warning("Hash verification failed")
            raise HTTPException(status_code=401, detail="Invalid hash")
        else:
            logger.info("Hash verification successful")

        # ---------------------------------------------
        # Извлекаем user_info из data["user"]
        # ---------------------------------------------
        try:
            logger.info("Parsing user data...")
            user_data = data.get("user", "")
            logger.debug(f"Raw user data length: {len(user_data) if user_data else 0}")

            if not user_data:
                logger.error("No user data found in init_data")
                raise HTTPException(status_code=400, detail="Missing user data in init_data")
            else:
                user_json = urllib.parse.unquote(user_data)
                logger.debug(f"URL-decoded user data length: {len(user_json)}")
                try:
                    user_info = json.loads(user_json)
                    logger.debug(f"Parsed user_info: ID={user_info.get('id')}, username={user_info.get('username')}")
                except Exception as e:
                    logger.error(f"Error parsing user JSON: {str(e)}")
                    user_json = user_json.replace("'", '"')
                    logger.debug(f"Cleaned user JSON length: {len(user_json)}")
                    user_info = json.loads(user_json)
                    logger.debug(f"Parsed user_info after cleaning: ID={user_info.get('id')}, username={user_info.get('username')}")

            try:
                telegram_id = int(user_info.get("id"))
                logger.debug(f"Converted telegram_id to int: {telegram_id} (type: {type(telegram_id)})")
            except (TypeError, ValueError) as e:
                logger.error(f"Error converting telegram_id to int: {str(e)}")
                raise HTTPException(status_code=400, detail="Invalid user ID in data")

            if not telegram_id:
                logger.error("No valid telegram_id found in user_info")
                raise HTTPException(status_code=400, detail="Missing user ID in data")
        except Exception as e:
            logger.error(f"Error parsing user data: {str(e)}", exc_info=True)
            raise HTTPException(status_code=400, detail=f"Invalid user data format: {str(e)}")

        # ---------------------------------------------
        # Ищем или создаём пользователя в БД
        # ---------------------------------------------
        try:
            logger.info(f"Looking up user with telegram_id: {telegram_id}")
            user = db.query(models.User).filter(models.User.telegram_id == telegram_id).first()

            if not user:
                logger.info(f"Creating new user with telegram_id: {telegram_id}")
                username = user_info.get("username") or user_info.get("first_name") or f"user_{telegram_id}"
                logger.debug(f"Using username: {username}")

                try:
                    user = models.User(
                        telegram_id=telegram_id,
                        username=username,
                        avatar=user_info.get("photo_url"),
                        balance=5.0,
                        earned_hours=0.0,
                        spent_hours=0.0,
                    )
                    db.add(user)
                    db.commit()
                    db.refresh(user)
                    logger.info(
                        f"New user created: {user.username} "
                        f"(ID: {user.id}, Telegram ID: {user.telegram_id})"
                    )
                except IntegrityError:
                    logger.warning("Concurrent user creation detected. Rolling back and retrying query.")
                    db.rollback()
                    user = db.query(models.User).filter(models.User.telegram_id == telegram_id).first()
                    if not user:
                        logger.error("Failed to find or create user after integrity error")
                        raise HTTPException(status_code=500, detail="User creation failed")
                    logger.info(
                        f"Found user after concurrent creation: {user.username} "
                        f"(ID: {user.id}, Telegram ID: {user.telegram_id})"
                    )
            else:
                logger.info(f"Found existing user: {user.username} (ID: {user.id}, Telegram ID: {user.telegram_id})")
                changes_made = False

                if user_info.get("username") and user_info.get("username") != user.username:
                    old_username = user.username
                    user.username = user_info.get("username")
                    changes_made = True
                    logger.info(f"Updated username from {old_username} to: {user.username}")

                if user_info.get("photo_url") and user_info.get("photo_url") != user.avatar:
                    user.avatar = user_info.get("photo_url")
                    changes_made = True
                    logger.info(f"Updated avatar URL to: {user.avatar}")

                if changes_made:
                    try:
                        db.commit()
                    except IntegrityError:
                        logger.warning("Integrity error during user update, rolling back")
                        db.rollback()

        except Exception as e:
            logger.error(f"Database error: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail="Database error")

        # ---------------------------------------------
        # Создаем JWT-токены (access + refresh)
        # ---------------------------------------------
        try:
            logger.info(f"Creating JWT tokens for user: {user.username}")
            access_token_data = {
                "sub": str(user.id),
                "telegram_id": str(telegram_id),
                "username": user.username,
                "type": "access",
            }
            access_token = create_access_token(access_token_data)

            refresh_token_data = {
                "sub": str(user.id),
                "telegram_id": str(telegram_id),
                "username": user.username,
                "type": "refresh",
                "exp": datetime.utcnow() + timedelta(days=7),
            }
            refresh_token = create_access_token(refresh_token_data)

            cookie_options = {"httponly": True, "secure": True, "samesite": "none", "path": "/"}

            response.set_cookie(
                key="access_token",
                value=access_token,
                max_age=JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                **cookie_options,
            )

            response.set_cookie(
                key="refresh_token", value=refresh_token, max_age=60 * 60 * 24 * 7, **cookie_options
            )
        except Exception as e:
            logger.error(f"Error creating tokens: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail="Error creating authentication tokens")

        logger.info("=== Authentication Successful ===")
        logger.info("*" * 80 + "\n\n")

        return {"success": True, "user": user}

    except HTTPException:
        logger.error("Authentication failed with HTTPException")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in auth: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# --------------------------------------------------
# Обновление токена (refresh)
# --------------------------------------------------
@app.get("/auth/refresh/")
async def refresh_token(request: Request, response: Response, db: Session = Depends(get_db)):
    """
    Обновление access token, используя refresh token из cookies.
    """
    try:
        logger.info("=== Starting Token Refresh ===")

        refresh_token = request.cookies.get("refresh_token")
        if not refresh_token:
            logger.error("No refresh token in cookies")
            raise HTTPException(status_code=401, detail="No refresh token")

        try:
            payload = jwt.decode(refresh_token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])

            if payload.get("type") != "refresh":
                logger.error("Invalid token type in refresh token")
                raise HTTPException(status_code=401, detail="Invalid token type")

            user_id = payload.get("sub")
            if not user_id:
                logger.error("No user ID in refresh token")
                raise HTTPException(status_code=401, detail="Invalid token")

            user = db.query(models.User).filter(models.User.id == int(user_id)).first()
            if not user:
                logger.error(f"User with ID {user_id} not found")
                raise HTTPException(status_code=404, detail="User not found")

            access_token_data = {
                "sub": str(user.id),
                "telegram_id": str(user.telegram_id),
                "username": user.username,
                "type": "access",
            }
            new_access_token = create_access_token(access_token_data)

            refresh_token_data = {
                "sub": str(user.id),
                "telegram_id": str(user.telegram_id),
                "username": user.username,
                "type": "refresh",
                "exp": datetime.utcnow() + timedelta(days=7),
            }
            new_refresh_token = create_access_token(refresh_token_data)

            cookie_options = {"httponly": True, "secure": True, "samesite": "none", "path": "/"}

            response.set_cookie(
                key="access_token",
                value=new_access_token,
                max_age=JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                **cookie_options,
            )

            response.set_cookie(
                key="refresh_token", value=new_refresh_token, max_age=60 * 60 * 24 * 7, **cookie_options
            )

            logger.info(f"Tokens refreshed for user {user.username}")

            return {"success": True, "user": user}

        except ExpiredSignatureError:
            logger.error("Refresh token expired")
            raise HTTPException(status_code=401, detail="Refresh token expired")
        except InvalidTokenError as e:
            logger.error(f"Invalid refresh token: {str(e)}")
            raise HTTPException(status_code=401, detail="Invalid refresh token")

    except HTTPException:
        response.delete_cookie(key="access_token")
        response.delete_cookie(key="refresh_token")
        raise
    except Exception as e:
        logger.error(f"Error refreshing token: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


# --------------------------------------------------
# Защищённый маршрут, проверка access/refresh токена
# --------------------------------------------------
@app.get("/auth/protected/")
async def protected_route(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    token_data: dict = Depends(get_current_user),
):
    """
    Пример защищённого маршрута.
    Проверяет access token; если он истёк, пытается использовать refresh token.
    """
    try:
        access_token = request.cookies.get("access_token")
        refresh_token = request.cookies.get("refresh_token")

        if not access_token and not refresh_token:
            logger.error("No tokens in cookies")
            raise HTTPException(status_code=401, detail="Authentication required")

        # Сначала проверяем access token
        if access_token:
            try:
                payload = jwt.decode(access_token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
                # Если токен валиден, отдаем подтверждение
                return {"authenticated": True}
            except ExpiredSignatureError:
                logger.info("Access token expired, trying refresh token")
            except InvalidTokenError as e:
                logger.error(f"JWT error in access token: {str(e)}")

        # Если access невалиден или отсутствует, проверяем refresh
        if refresh_token:
            try:
                payload = jwt.decode(refresh_token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])

                if payload.get("type") != "refresh":
                    logger.error("Invalid token type in refresh token")
                    raise HTTPException(status_code=401, detail="Invalid token type")

                user_id = payload.get("sub")
                if not user_id:
                    logger.error("No user ID in refresh token")
                    raise HTTPException(status_code=401, detail="Invalid token")

                user = db.query(models.User).filter(models.User.id == int(user_id)).first()
                if not user:
                    logger.error(f"User with ID {user_id} not found")
                    raise HTTPException(status_code=404, detail="User not found")

                access_token_data = {
                    "sub": str(user.id),
                    "telegram_id": str(user.telegram_id),
                    "username": user.username,
                    "type": "access",
                }
                new_access_token = create_access_token(access_token_data)

                refresh_token_data = {
                    "sub": str(user.id),
                    "telegram_id": str(user.telegram_id),
                    "username": user.username,
                    "type": "refresh",
                    "exp": datetime.utcnow() + timedelta(days=7),
                }
                new_refresh_token = create_access_token(refresh_token_data)

                cookie_options = {"httponly": True, "secure": True, "samesite": "none", "path": "/"}

                response.set_cookie(
                    key="access_token",
                    value=new_access_token,
                    max_age=JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                    **cookie_options,
                )

                response.set_cookie(
                    key="refresh_token", value=new_refresh_token, max_age=60 * 60 * 24 * 7, **cookie_options
                )

                logger.info(f"Tokens refreshed for user {user.username}")
                return {"authenticated": True, "refreshed": True, "user": user}

            except ExpiredSignatureError:
                logger.error("Refresh token expired")
                response.delete_cookie(key="access_token")
                response.delete_cookie(key="refresh_token")
                raise HTTPException(status_code=401, detail="Refresh token expired")
            except InvalidTokenError as e:
                logger.error(f"JWT error in refresh token: {str(e)}")
                response.delete_cookie(key="access_token")
                response.delete_cookie(key="refresh_token")
                raise HTTPException(status_code=401, detail="Invalid refresh token")

        # Если оба невалидны
        raise HTTPException(status_code=401, detail="Authentication required")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in protected route: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


# --------------------------------------------------
# Logout: удаляем куки
# --------------------------------------------------
@app.post("/auth/logout/")
async def logout(response: Response):
    """
    Logout пользователя: очищаем access_token и refresh_token в cookies.
    """
    response.delete_cookie(key="access_token")
    response.delete_cookie(key="refresh_token")
    return {"success": True, "message": "Logged out successfully"}
