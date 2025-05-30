from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
import models
import schemas
from database import SessionLocal, engine
import os
import shutil
from pathlib import Path
from auth import verify_telegram_hash, create_access_token, verify_token
from config import BOT_TOKEN, JWT_ALGORITHM, JWT_ACCESS_TOKEN_EXPIRE_MINUTES
import logging
import sys
import traceback
from logging.handlers import RotatingFileHandler
from datetime import datetime
import uuid
import time

# Ensure logs directory exists
os.makedirs('logs', exist_ok=True)

# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout  # Ensure logs go to stdout for console visibility
)

# Set up specific loggers
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Clear existing handlers
logger.handlers = []

# Add a stream handler for console output
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.DEBUG)
console_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)

# Add multiple file handlers for different log levels
# Debug log - для всех сообщений
debug_file_handler = RotatingFileHandler(
    'logs/debug.log',
    maxBytes=10*1024*1024,  # 10MB
    backupCount=10
)
debug_file_handler.setLevel(logging.DEBUG)
debug_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
debug_file_handler.setFormatter(debug_formatter)
logger.addHandler(debug_file_handler)

# Error log - только для ошибок
error_file_handler = RotatingFileHandler(
    'logs/error.log',
    maxBytes=10*1024*1024,  # 10MB
    backupCount=10
)
error_file_handler.setLevel(logging.ERROR)
error_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s\n%(pathname)s:%(lineno)d\n%(message)s\n')
error_file_handler.setFormatter(error_formatter)
logger.addHandler(error_file_handler)

# Специальный лог для запросов пользователей
requests_file_handler = RotatingFileHandler(
    'logs/requests.log',
    maxBytes=10*1024*1024,  # 10MB
    backupCount=10
)
requests_file_handler.setLevel(logging.INFO)
requests_formatter = logging.Formatter('%(asctime)s - %(message)s')
requests_file_handler.setFormatter(requests_formatter)
logger.addHandler(requests_file_handler)

# Специальный лог для аутентификации
auth_file_handler = RotatingFileHandler(
    'logs/auth.log',
    maxBytes=10*1024*1024,  # 10MB
    backupCount=10
)
auth_file_handler.setLevel(logging.DEBUG)
auth_formatter = logging.Formatter('%(asctime)s - AUTH - %(levelname)s - %(message)s')
auth_file_handler.setFormatter(auth_formatter)
logger.addHandler(auth_file_handler)

# Also configure the auth logger
auth_logger = logging.getLogger('auth')
auth_logger.setLevel(logging.DEBUG)
auth_logger.handlers = []  # Clear existing handlers
auth_logger.addHandler(console_handler)
auth_logger.addHandler(debug_file_handler)
auth_logger.addHandler(error_file_handler)
auth_logger.addHandler(auth_file_handler)

# Log startup information
logger.info("="*80)
logger.info("Starting Time Banking API")
logger.info("="*80)
logger.info(f"Bot token: {BOT_TOKEN[:5]}...{BOT_TOKEN[-5:]} (length: {len(BOT_TOKEN)})")

# Configure CORS
app = FastAPI()

# Middleware для логирования всех запросов и ответов
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """
    Middleware для логирования всех HTTP-запросов и ответов
    """
    request_id = str(uuid.uuid4())
    client_host = request.client.host if request.client else "unknown"
    client_port = request.client.port if request.client else "unknown"
    
    # Логируем информацию о запросе
    logger.info(f"[{request_id}] Request from {client_host}:{client_port} - {request.method} {request.url.path}")
    
    # Логируем query параметры
    if request.query_params:
        logger.info(f"[{request_id}] Query params: {dict(request.query_params)}")
    
    # Попытка получить тело запроса (не всегда возможно)
    try:
        body = await request.body()
        if body:
            logger.info(f"[{request_id}] Request body: {body.decode()}")
    except Exception as e:
        logger.debug(f"[{request_id}] Could not log request body: {str(e)}")
    
    # Замеряем время выполнения запроса
    start_time = time.time()
    
    try:
        # Выполняем запрос
        response = await call_next(request)
        
        # Логируем информацию об ответе
        process_time = time.time() - start_time
        logger.info(f"[{request_id}] Response status: {response.status_code} - Completed in {process_time:.4f}s")
        
        return response
    except Exception as e:
        # Логируем ошибку, если она произошла
        process_time = time.time() - start_time
        logger.error(f"[{request_id}] Error during request processing: {str(e)}")
        logger.error(f"[{request_id}] Error details: {traceback.format_exc()}")
        logger.error(f"[{request_id}] Failed after {process_time:.4f}s")
        raise

# Добавляем обработчики исключений
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Обрабатывает все необработанные исключения и логирует их"""
    error_msg = f"Unhandled exception: {str(exc)}"
    logger.error(error_msg)
    logger.error(traceback.format_exc())
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error, check logs for details"},
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Обрабатывает ошибки валидации запросов"""
    error_msg = f"Validation error: {str(exc)}"
    logger.error(error_msg)
    return JSONResponse(
        status_code=422,
        content={"detail": error_msg},
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Обрабатывает HTTP исключения и логирует их"""
    logger.error(f"HTTP exception: {exc.status_code} - {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Разрешаем все домены для работы через прокси
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "Time Banking API is running"}

# Create uploads directory if it doesn't exist
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

models.Base.metadata.create_all(bind=engine)

# Create test user if not exists
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
                spent_hours=0.0
            )
            db.add(test_user)
            db.commit()
    finally:
        db.close()

create_test_user()

# Mount uploads directory
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Теперь диагностический маршрут будет ПОСЛЕ определения get_db
@app.get("/diagnostics")
async def diagnostics(db: Session = Depends(get_db)):
    """
    Диагностический эндпоинт для проверки состояния системы
    """
    try:
        # Проверка соединения с БД
        db_connection_ok = False
        db_error = None
        user_count = 0
        
        try:
            # Попытка выполнить запрос
            user_count = db.query(models.User).count()
            db_connection_ok = True
        except Exception as e:
            db_error = str(e)
            logger.error(f"Database connection error: {e}")
        
        # Проверка конфигурации авторизации
        auth_config = {
            "jwt_algorithm": JWT_ALGORITHM,
            "jwt_expiry_minutes": JWT_ACCESS_TOKEN_EXPIRE_MINUTES,
            "bot_token_length": len(BOT_TOKEN) if BOT_TOKEN else 0,
            "bot_token_first_chars": BOT_TOKEN[:4] if BOT_TOKEN else None,
            "bot_token_last_chars": BOT_TOKEN[-4:] if BOT_TOKEN else None,
        }
        
        # Проверка файловой системы
        fs_status = {
            "uploads_dir_exists": os.path.exists("uploads"),
            "logs_dir_exists": os.path.exists("logs"),
            "db_file_exists": os.path.exists("time_banking.db"),
            "db_file_size": os.path.getsize("time_banking.db") if os.path.exists("time_banking.db") else 0,
        }
        
        # Возвращаем полную диагностику
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

@app.get("/user/me", response_model=schemas.UserProfile)
def get_current_user(
    token_data: dict = Depends(verify_token),
    db: Session = Depends(get_db)
):
    user = db.query(models.User).filter(
        models.User.id == int(token_data["sub"])
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@app.get("/listings/", response_model=List[schemas.Listing])
def get_listings(
    skip: int = 0,
    limit: int = 5,
    status: Optional[str] = None,
    listing_type: Optional[str] = None,
    db: Session = Depends(get_db),
    token_data: dict = Depends(verify_token)
):
    query = db.query(models.Listing).options(
        joinedload(models.Listing.creator),
        joinedload(models.Listing.worker)
    )
    
    if status:
        query = query.filter(models.Listing.status == status)
    if listing_type:
        query = query.filter(models.Listing.listing_type == listing_type)
    
    listings = query.order_by(models.Listing.created_at.desc()).offset(skip).limit(limit).all()
    return listings

@app.post("/listings/", response_model=schemas.Listing)
def create_listing(
    listing: schemas.ListingCreate,
    db: Session = Depends(get_db),
    token_data: dict = Depends(verify_token)
):
    # Verify that the user is creating a listing for themselves
    if int(token_data["sub"]) != listing.user_id:
        raise HTTPException(status_code=403, detail="Cannot create listing for another user")
    
    # Get user by ID to ensure they exist
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

@app.post("/listings/{listing_id}/apply")
def apply_for_listing(
    listing_id: int,
    db: Session = Depends(get_db),
    token_data: dict = Depends(verify_token)
):
    listing = db.query(models.Listing).filter(models.Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    
    if listing.status != "active":
        raise HTTPException(status_code=400, detail="Listing is not active")
    
    # Check if worker has sufficient balance for offers
    if listing.listing_type == "offer":
        worker = db.query(models.User).filter(models.User.id == int(token_data["sub"])).first()
        if worker.balance < listing.hours:
            raise HTTPException(status_code=400, detail="Insufficient balance")
    
    listing.status = "pending_worker"
    listing.worker_id = int(token_data["sub"])
    db.commit()
    db.refresh(listing)
    return listing

@app.post("/listings/{listing_id}/accept")
def accept_worker(
    listing_id: int,
    db: Session = Depends(get_db),
    token_data: dict = Depends(verify_token)
):
    listing = db.query(models.Listing).filter(models.Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    
    if listing.user_id != int(token_data["sub"]):
        raise HTTPException(status_code=403, detail="Only listing creator can accept workers")
    
    if listing.status != "pending_worker":
        raise HTTPException(status_code=400, detail="Listing is not pending worker acceptance")
    
    # Create prepayment transaction (33% of total) for both request and offer types
    prepayment_hours = round(listing.hours * 0.33, 1)  # 33% предоплата, округленная до 1 знака
    
    # Получаем пользователей для обновления баланса
    creator = db.query(models.User).filter(models.User.id == listing.user_id).first()
    worker = db.query(models.User).filter(models.User.id == listing.worker_id).first()
    
    if listing.listing_type == "request":
        # Для запросов помощи - платит создатель заявки
        payer_id = listing.user_id
        receiver_id = listing.worker_id
        payer = creator
        receiver = worker
        description = f"Предоплата (33%) за помощь: {listing.title}"
    else:  # offer
        # Для предложений помощи - платит тот, кто принимает предложение (worker)
        payer_id = listing.worker_id
        receiver_id = listing.user_id
        payer = worker
        receiver = creator
        description = f"Предоплата (33%) за услугу: {listing.title}"
    
    # Проверяем достаточно ли средств у плательщика
    if payer.balance < prepayment_hours:
        raise HTTPException(status_code=400, detail="Недостаточно средств для предоплаты")
    
    # Обновляем балансы
    payer.balance -= prepayment_hours
    receiver.balance += prepayment_hours
    
    transaction = models.Transaction(
        from_user_id=payer_id,
        to_user_id=receiver_id,
        hours=prepayment_hours,
        description=description,
        transaction_type="prepayment"
    )
    db.add(transaction)
    db.commit()
    
    # Update listing with prepayment
    listing.prepayment_transaction_id = transaction.id
    listing.status = "in_progress"
    
    db.commit()
    db.refresh(listing)
    return listing

@app.post("/listings/{listing_id}/reject")
def reject_worker(
    listing_id: int,
    db: Session = Depends(get_db),
    token_data: dict = Depends(verify_token)
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

@app.post("/listings/{listing_id}/pay")
def make_payment(
    listing_id: int,
    db: Session = Depends(get_db),
    token_data: dict = Depends(verify_token)
):
    listing = db.query(models.Listing).filter(models.Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    
    # Проверяем, что оплату делает исполнитель для предложений помощи
    if listing.worker_id != int(token_data["sub"]):
        raise HTTPException(status_code=403, detail="Only worker can make payment")
    
    if listing.status != "pending_payment":
        raise HTTPException(status_code=400, detail="Listing is not pending payment")
    
    # Create prepayment transaction (33% of total)
    prepayment_hours = round(listing.hours * 0.33, 1)  # 33% предоплата, округленная до 1 знака
    
    # Получаем пользователей для обновления баланса
    creator = db.query(models.User).filter(models.User.id == listing.user_id).first()
    worker = db.query(models.User).filter(models.User.id == listing.worker_id).first()
    
    # Для предложений помощи - платит тот, кто принимает предложение (worker)
    payer_id = listing.worker_id
    receiver_id = listing.user_id
    payer = worker
    receiver = creator
    description = f"Предоплата (33%) за услугу: {listing.title}"
    
    # Проверяем достаточно ли средств у плательщика
    if payer.balance < prepayment_hours:
        raise HTTPException(status_code=400, detail="Недостаточно средств для предоплаты")
    
    # Обновляем балансы
    payer.balance -= prepayment_hours
    receiver.balance += prepayment_hours
    
    transaction = models.Transaction(
        from_user_id=payer_id,
        to_user_id=receiver_id,
        hours=prepayment_hours,
        description=description,
        transaction_type="prepayment"
    )
    db.add(transaction)
    db.commit()
    
    # Update listing with prepayment
    listing.prepayment_transaction_id = transaction.id
    listing.status = "in_progress"
    
    db.commit()
    db.refresh(listing)
    return listing

@app.post("/listings/{listing_id}/complete")
def complete_listing(
    listing_id: int,
    db: Session = Depends(get_db),
    token_data: dict = Depends(verify_token)
):
    listing = db.query(models.Listing).filter(models.Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    
    # Для запросов помощи отмечает исполнитель, для предложений - создатель
    if listing.listing_type == "request":
        if listing.worker_id != int(token_data["sub"]):
            raise HTTPException(status_code=403, detail="Only worker can mark request as complete")
    else:  # offer
        if listing.user_id != int(token_data["sub"]):
            raise HTTPException(status_code=403, detail="Only creator can mark offer as complete")
    
    if listing.status != "in_progress":
        raise HTTPException(status_code=400, detail="Listing is not in progress")
    
    listing.status = "pending_confirmation"
    db.commit()
    db.refresh(listing)
    return listing

@app.post("/listings/{listing_id}/confirm")
def confirm_completion(
    listing_id: int,
    db: Session = Depends(get_db),
    token_data: dict = Depends(verify_token)
):
    listing = db.query(models.Listing).filter(models.Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    
    # Для запросов помощи подтверждает создатель, для предложений - исполнитель
    if listing.listing_type == "request":
        if listing.user_id != int(token_data["sub"]):
            raise HTTPException(status_code=403, detail="Only listing creator can confirm request completion")
    else:  # offer
        if listing.worker_id != int(token_data["sub"]):
            raise HTTPException(status_code=403, detail="Only worker can confirm offer completion")
    
    if listing.status != "pending_confirmation":
        raise HTTPException(status_code=400, detail="Listing is not pending confirmation")
    
    # Update balances
    creator = db.query(models.User).filter(models.User.id == listing.user_id).first()
    worker = db.query(models.User).filter(models.User.id == listing.worker_id).first()
    
    # Вычисляем оставшиеся 67% оплаты
    prepayment_transaction = db.query(models.Transaction).filter(models.Transaction.id == listing.prepayment_transaction_id).first()
    prepayment_amount = prepayment_transaction.hours if prepayment_transaction else 0
    remaining_hours = listing.hours - prepayment_amount
    
    if listing.listing_type == "request":
        # Для запросов помощи - платит создатель заявки
        payer_id = listing.user_id
        receiver_id = listing.worker_id
        payer = creator
        receiver = worker
        description = f"Окончательная оплата (67%) за помощь: {listing.title}"
        
        # Обновляем статистику
        receiver_earned = worker
        payer_spent = creator
    else:  # offer
        # Для предложений помощи - платит тот, кто принимает предложение (worker)
        payer_id = listing.worker_id
        receiver_id = listing.user_id
        payer = worker
        receiver = creator
        description = f"Окончательная оплата (67%) за услугу: {listing.title}"
        
        # Обновляем статистику
        receiver_earned = creator
        payer_spent = worker
    
    # Проверяем достаточно ли средств у плательщика для окончательной оплаты
    if payer.balance < remaining_hours:
        raise HTTPException(status_code=400, detail="Недостаточно средств для окончательной оплаты")
    
    # Обновляем балансы для оставшейся суммы
    payer.balance -= remaining_hours
    receiver.balance += remaining_hours
    
    # Создаем транзакцию для оставшейся суммы
    final_transaction = models.Transaction(
        from_user_id=payer_id,
        to_user_id=receiver_id,
        hours=remaining_hours,
        description=description,
        transaction_type="payment"
    )
    db.add(final_transaction)
    db.commit()
    
    # Обновляем статистику пользователей
    receiver_earned.earned_hours += listing.hours
    payer_spent.spent_hours += listing.hours
    
    listing.status = "completed"
    db.commit()
    db.refresh(listing)
    return listing

@app.post("/listings/{listing_id}/cancel")
def cancel_listing(
    listing_id: int,
    db: Session = Depends(get_db),
    token_data: dict = Depends(verify_token)
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

@app.get("/friends/", response_model=List[schemas.Friend])
def get_friends(
    db: Session = Depends(get_db),
    token_data: dict = Depends(verify_token)
):
    user_id = int(token_data["sub"])
    friends = db.query(models.Friend).filter(
        ((models.Friend.user_id == user_id) | (models.Friend.friend_id == user_id)) &
        (models.Friend.status == "accepted")
    ).options(
        joinedload(models.Friend.user),
        joinedload(models.Friend.friend)
    ).all()
    
    # Convert to response model
    return [
        schemas.Friend(
            id=friend.id,
            user_id=friend.user_id,
            friend_id=friend.friend_id,
            status=friend.status,
            created_at=friend.created_at,
            user=friend.user,
            friend=friend.friend
        ) for friend in friends
    ]

@app.post("/friends/request", response_model=schemas.Friend)
def send_friend_request(
    friend_request: schemas.FriendCreate,
    db: Session = Depends(get_db),
    token_data: dict = Depends(verify_token)
):
    user_id = int(token_data["sub"])
    friend_id = friend_request.friend_id
    
    # Check if friend request already exists
    existing_request = db.query(models.Friend).filter(
        ((models.Friend.user_id == user_id) & (models.Friend.friend_id == friend_id)) |
        ((models.Friend.user_id == friend_id) & (models.Friend.friend_id == user_id))
    ).first()
    
    if existing_request:
        raise HTTPException(status_code=400, detail="Friend request already exists")
    
    # Create new friend request
    friend = models.Friend(
        user_id=user_id,
        friend_id=friend_id,
        status="pending"
    )
    db.add(friend)
    db.commit()
    db.refresh(friend)
    
    # Load relationships
    db.refresh(friend.user)
    db.refresh(friend.friend)
    
    return friend

@app.post("/friends/{friend_id}/accept")
def accept_friend_request(
    friend_id: int,
    db: Session = Depends(get_db),
    token_data: dict = Depends(verify_token)
):
    friend_request = db.query(models.Friend).filter(models.Friend.id == friend_id).first()
    if not friend_request:
        raise HTTPException(status_code=404, detail="Friend request not found")
    
    if friend_request.friend_id != int(token_data["sub"]):
        raise HTTPException(status_code=403, detail="Only the recipient can accept friend request")
    
    if friend_request.status != "pending":
        raise HTTPException(status_code=400, detail="Friend request is not pending")
    
    friend_request.status = "accepted"
    db.commit()
    db.refresh(friend_request)
    return friend_request

@app.post("/friends/{friend_id}/reject")
def reject_friend_request(
    friend_id: int,
    db: Session = Depends(get_db),
    token_data: dict = Depends(verify_token)
):
    friend_request = db.query(models.Friend).filter(models.Friend.id == friend_id).first()
    if not friend_request:
        raise HTTPException(status_code=404, detail="Friend request not found")
    
    if friend_request.friend_id != int(token_data["sub"]):
        raise HTTPException(status_code=403, detail="Only the recipient can reject friend request")
    
    if friend_request.status != "pending":
        raise HTTPException(status_code=400, detail="Friend request is not pending")
    
    db.delete(friend_request)
    db.commit()
    return {"status": "rejected"}

@app.get("/transactions/{user_id}", response_model=List[schemas.Transaction])
def get_transactions(
    user_id: int,
    db: Session = Depends(get_db),
    token_data: dict = Depends(verify_token)
):
    # Verify that the user is accessing their own transactions
    if int(token_data["sub"]) != user_id:
        raise HTTPException(status_code=403, detail="Cannot view transactions for another user")
    
    transactions = db.query(models.Transaction).filter(
        (models.Transaction.from_user_id == user_id) | 
        (models.Transaction.to_user_id == user_id)
    ).options(
        joinedload(models.Transaction.from_user),
        joinedload(models.Transaction.to_user)
    ).order_by(models.Transaction.created_at.desc()).all()
    return transactions

@app.post("/profile/{user_id}/avatar")
async def upload_avatar(
    user_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    token_data: dict = Depends(verify_token)
):
    # Verify that the user is uploading their own avatar
    if int(token_data["sub"]) != user_id:
        raise HTTPException(status_code=403, detail="Cannot upload avatar for another user")
    
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Create user directory if it doesn't exist
    user_upload_dir = UPLOAD_DIR / str(user_id)
    user_upload_dir.mkdir(exist_ok=True)

    # Save the file
    file_path = user_upload_dir / file.filename
    with file_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Update user's avatar URL
    avatar_url = f"/uploads/{user_id}/{file.filename}"
    user.avatar = avatar_url
    db.commit()

    return {"avatar_url": avatar_url}

@app.get("/listings/user/{user_id}", response_model=List[schemas.Listing])
def get_user_listings(
    user_id: int,
    db: Session = Depends(get_db),
    token_data: dict = Depends(verify_token)
):
    # Проверяем, что пользователь запрашивает свои заявки или является другом
    current_user_id = int(token_data["sub"])
    if current_user_id != user_id:
        # Проверяем дружбу
        friendship = db.query(models.Friend).filter(
            ((models.Friend.user_id == current_user_id) & (models.Friend.friend_id == user_id)) |
            ((models.Friend.user_id == user_id) & (models.Friend.friend_id == current_user_id))
        ).filter(models.Friend.status == "accepted").first()
        
        if not friendship:
            raise HTTPException(status_code=403, detail="You can only view listings of yourself or your friends")
    
    # Получаем заявки пользователя
    listings = db.query(models.Listing).filter(
        (models.Listing.user_id == user_id) | (models.Listing.worker_id == user_id)
    ).options(
        joinedload(models.Listing.creator),
        joinedload(models.Listing.worker)
    ).order_by(models.Listing.created_at.desc()).all()
    
    return listings

@app.get("/users/search", response_model=List[schemas.UserProfile])
def search_users(
    username: str,
    db: Session = Depends(get_db),
    token_data: dict = Depends(verify_token)
):
    """
    Поиск пользователей по имени пользователя
    """
    current_user_id = int(token_data["sub"])
    
    # Ищем пользователей, чье имя содержит указанную строку
    users = db.query(models.User).filter(
        models.User.username.ilike(f"%{username}%") & 
        (models.User.id != current_user_id)  # Исключаем текущего пользователя
    ).limit(10).all()
    
    return users

@app.get("/friends/pending", response_model=List[schemas.Friend])
def get_pending_friend_requests(
    db: Session = Depends(get_db),
    token_data: dict = Depends(verify_token)
):
    """
    Получение входящих запросов в друзья
    """
    user_id = int(token_data["sub"])
    
    # Получаем запросы, где текущий пользователь является получателем
    pending_requests = db.query(models.Friend).filter(
        (models.Friend.friend_id == user_id) & 
        (models.Friend.status == "pending")
    ).options(
        joinedload(models.Friend.user),
        joinedload(models.Friend.friend)
    ).all()
    
    return pending_requests

@app.get("/users/transactions", response_model=List[schemas.UserProfile])
def get_transaction_partners(
    db: Session = Depends(get_db),
    token_data: dict = Depends(verify_token)
):
    """
    Получение списка пользователей, с которыми были сделки
    """
    user_id = int(token_data["sub"])
    
    # Находим все заявки, где пользователь был либо создателем, либо исполнителем
    listings = db.query(models.Listing).filter(
        ((models.Listing.user_id == user_id) | (models.Listing.worker_id == user_id)) & 
        (models.Listing.status == "completed")
    ).all()
    
    # Собираем ID пользователей, с которыми были сделки
    partner_ids = set()
    for listing in listings:
        if listing.user_id == user_id and listing.worker_id:
            partner_ids.add(listing.worker_id)
        elif listing.worker_id == user_id:
            partner_ids.add(listing.user_id)
    
    # Получаем информацию о пользователях
    partners = db.query(models.User).filter(models.User.id.in_(partner_ids)).all()
    
    return partners

@app.get("/debug/auth")
async def debug_auth(request: Request):
    """
    Диагностический эндпоинт для отладки авторизации Telegram
    """
    logger.info("\n\n" + "*"*80)
    logger.info("=== Starting Auth Debug ===")
    logger.info("*"*80)
    
    # Информация о запросе
    headers = dict(request.headers)
    cookies = request.cookies
    query_params = dict(request.query_params)
    
    # Информация о конфигурации
    config_info = {
        "bot_token_length": len(BOT_TOKEN),
        "bot_token_start": BOT_TOKEN[:5] if BOT_TOKEN else None,
        "bot_token_end": BOT_TOKEN[-5:] if BOT_TOKEN else None,
    }
    
    # Проверка соединения с БД
    db_status = {}
    try:
        db = SessionLocal()
        try:
            # Проверяем количество пользователей
            user_count = db.query(models.User).count()
            db_status["user_count"] = user_count
            
            # Выводим список всех пользователей для диагностики
            users = db.query(models.User).all()
            db_status["users"] = [
                {
                    "id": user.id,
                    "telegram_id": user.telegram_id,
                    "username": user.username,
                    "created_at": user.created_at.isoformat() if user.created_at else None
                }
                for user in users
            ]
            
            db_status["status"] = "ok"
        except Exception as e:
            db_status["status"] = "error"
            db_status["error"] = str(e)
        finally:
            db.close()
    except Exception as e:
        db_status["status"] = "connection_error"
        db_status["error"] = str(e)
    
    # Информация о файловой системе
    fs_info = {
        "uploads_dir_exists": os.path.exists("uploads"),
        "logs_dir_exists": os.path.exists("logs"),
        "db_file_exists": os.path.exists("time_banking.db"),
        "db_file_size": os.path.getsize("time_banking.db") if os.path.exists("time_banking.db") else 0,
    }
    
    # Отладка init_data из Telegram
    telegram_debug = {}
    if "init_data" in query_params:
        init_data = query_params["init_data"]
        telegram_debug["init_data"] = init_data
        
        # Парсим параметры из init_data
        try:
            pairs = [s.split("=", 1) for s in init_data.split("&") if "=" in s]
            data = {k: v for k, v in pairs}
            telegram_debug["parsed_data"] = data
            
            # Проверяем наличие хеша
            if "hash" in data:
                hash_value = data["hash"]
                telegram_debug["hash"] = hash_value
                
                # Симулируем проверку хеша, но не возвращаем результат клиенту
                try:
                    verification_result = verify_telegram_hash(init_data, hash_value)
                    # Не включаем результат в ответ, только логируем
                    logger.info(f"Hash verification result: {verification_result}")
                except Exception as e:
                    logger.error(f"Hash verification error: {str(e)}")
            else:
                telegram_debug["hash_missing"] = True
            
            # Проверяем наличие данных пользователя
            if "user" in data:
                try:
                    import urllib.parse
                    import json
                    
                    user_json = urllib.parse.unquote(data["user"])
                    user_info = json.loads(user_json)
                    telegram_debug["user_info"] = {
                        "id": user_info.get("id"),
                        "username": user_info.get("username"),
                        "has_photo": "photo_url" in user_info
                    }
                except Exception as e:
                    telegram_debug["user_parse_error"] = str(e)
        except Exception as e:
            telegram_debug["parse_error"] = str(e)
    
    # Собираем информацию
    debug_info = {
        "timestamp": datetime.utcnow().isoformat(),
        "request": {
            "headers": {k: v for k, v in headers.items() if k.lower() not in ["authorization"]},
            "cookies": {k: v for k, v in cookies.items()},
            "query_params": {k: v for k, v in query_params.items() if k != "init_data"},
            "has_init_data": "init_data" in query_params
        },
        "config": config_info,
        "database": db_status,
        "filesystem": fs_info,
        "telegram_debug": telegram_debug
    }
    
    logger.info(f"Auth debug complete: {debug_info}")
    logger.info("=== Auth Debug Completed ===")
    logger.info("*"*80 + "\n\n")
    
    return debug_info

@app.get("/admin/logs/{log_name}")
async def view_logs(
    log_name: str,
    lines: int = Query(100, ge=1, le=1000),
    token_data: dict = Depends(verify_token)
):
    """
    Просмотр логов приложения.
    Доступные логи: debug, error, auth, requests
    """
    # Проверка, что log_name допустим
    valid_logs = ["debug", "error", "auth", "requests"]
    if log_name not in valid_logs:
        raise HTTPException(status_code=400, detail=f"Invalid log name. Available logs: {', '.join(valid_logs)}")
    
    # Путь к файлу лога
    log_path = f"logs/{log_name}.log"
    
    # Проверка существования файла
    if not os.path.exists(log_path):
        return {"status": "empty", "message": f"Log file {log_name}.log does not exist yet"}
    
    # Чтение последних N строк
    try:
        # Используем tail для больших файлов (работает быстрее чем readlines)
        result = []
        with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
            # Быстрый алгоритм чтения последних строк
            try:
                f.seek(0, os.SEEK_END)
                file_size = f.tell()
                
                if file_size == 0:
                    return {"status": "empty", "message": f"Log file {log_name}.log is empty"}
                
                # Начинаем с последних 8KB и увеличиваем при необходимости
                bytes_to_read = min(8192, file_size)
                lines_found = 0
                chunks = []
                
                while lines_found < lines and bytes_to_read <= file_size:
                    # Смещаемся от конца файла
                    f.seek(-bytes_to_read, os.SEEK_END)
                    chunk = f.read(bytes_to_read)
                    lines_in_chunk = chunk.count('\n')
                    
                    if lines_in_chunk >= lines:
                        # Достаточно строк в текущем чанке
                        chunks.append(chunk)
                        break
                    else:
                        # Нужно прочитать больше
                        chunks.append(chunk)
                        lines_found += lines_in_chunk
                        bytes_to_read *= 2
                        if bytes_to_read > file_size:
                            # Если превышаем размер файла, читаем с начала
                            f.seek(0)
                            chunks = [f.read()]
                            break
                
                # Объединяем чанки и берем последние N строк
                content = ''.join(chunks)
                all_lines = content.split('\n')
                result = all_lines[-lines-1:] if all_lines[-1] else all_lines[-lines-2:]
            except Exception as e:
                logger.error(f"Error reading log file {log_name}.log: {str(e)}")
                # Если оптимизированный метод не сработал, используем простой
                f.seek(0)
                result = f.readlines()[-lines:]
        
        return {
            "status": "success",
            "log_name": log_name,
            "lines_count": len(result),
            "content": result
        }
    except Exception as e:
        logger.error(f"Error retrieving logs: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving logs: {str(e)}")

@app.post("/auth/telegram")
async def telegram_auth(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Authenticate user with Telegram WebApp data.
    Gets raw init_data from query params without any decoding.
    """
    try:
        logger.info("\n\n" + "*"*80)
        logger.info("=== Starting Telegram Authentication ===")
        logger.info("*"*80)
        
        # Log all request headers for debugging
        logger.debug("Request headers:")
        for header, value in request.headers.items():
            logger.debug(f"  {header}: {value}")
            
        # Log all query parameters
        logger.debug("Query parameters:")
        for param, value in request.query_params.items():
            logger.debug(f"  {param}: {value}")
        
        # Get raw init_data without any decoding
        raw_init_data = request.query_params.get("init_data", "")
        # Decode URL-encoded init_data
        from urllib.parse import unquote_plus
        raw_init_data = unquote_plus(raw_init_data)
        logger.debug("Raw init_data (repr): %r", raw_init_data)
        
        if not raw_init_data:
            logger.error("No init_data parameter provided in request")
            raise HTTPException(status_code=400, detail="Missing init_data parameter")
        
        # Extract hash before any parsing/decoding
        pairs = [s.split("=", 1) for s in raw_init_data.split("&") if "=" in s]
        data = {k: v for k, v in pairs}
        
        logger.debug("Parsed data parameters:")
        for key, value in data.items():
            logger.debug(f"  {key}: {value}")
        
        hash_value = data.get('hash')
        if not hash_value:
            logger.error("No hash parameter found in init_data")
            raise HTTPException(status_code=400, detail="No hash provided")
            
        logger.debug("Extracted hash value: %s", hash_value)
            
        # Verify hash with raw init_data
        logger.info("Verifying Telegram hash...")
        hash_verified = verify_telegram_hash(raw_init_data, hash_value)
        if not hash_verified:
            logger.warning("Hash verification failed")
            # In development mode, we bypass hash verification errors
            # Uncomment the line below to enable strict hash verification in production
            # raise HTTPException(status_code=401, detail="Invalid hash")
        else:
            logger.info("Hash verification successful")
            
        # Parse user data from the request
        try:
            logger.info("Parsing user data...")
            user_data = data.get('user', '')
            logger.debug("Raw user data: %s", user_data)
            
            # If no user data found, use test user for development
            if not user_data:
                logger.warning("No user data found, using test user as fallback")
                user_info = {
                    "id": 12345,
                    "username": "test_user",
                    "first_name": "Test"
                }
                logger.debug("Using test user_info: %s", user_info)
            else:
                # Parse user data from URL-encoded JSON
                import json
                import urllib.parse
                
                try:
                    user_json = urllib.parse.unquote(user_data)
                    logger.debug("URL-decoded user data: %s", user_json)
                    user_info = json.loads(user_json)
                    logger.debug("Parsed user_info: %s", user_info)
                except Exception as e:
                    logger.error(f"Error parsing user JSON: {str(e)}")
                    # Try to clean the JSON if parsing fails
                    user_json = urllib.parse.unquote(user_data).replace("'", '"')
                    logger.debug("Cleaned user JSON: %s", user_json)
                    user_info = json.loads(user_json)
                    logger.debug("Parsed user_info after cleaning: %s", user_info)
            
            # Убедимся что telegram_id это целое число
            try:
                telegram_id = int(user_info.get('id'))
                logger.debug(f"Converted telegram_id to int: {telegram_id} (type: {type(telegram_id)})")
            except (TypeError, ValueError) as e:
                logger.error(f"Error converting telegram_id to int: {str(e)}")
                telegram_id = None
            
            if not telegram_id:
                logger.error("No valid telegram_id found in user_info")
                raise ValueError("No valid telegram_id in user data")
                
        except Exception as e:
            logger.error(f"Error parsing user data: {str(e)}", exc_info=True)
            raise HTTPException(status_code=400, detail=f"Invalid user data format: {str(e)}")
            
        # Get or create user with proper error handling for concurrent requests
        try:
            logger.info(f"Looking up user with telegram_id: {telegram_id}")
            
            # Используем блокировку транзакции, чтобы избежать гонок при создании пользователей
            from sqlalchemy.exc import IntegrityError
            
            # Попытка найти пользователя
            user = db.query(models.User).filter(models.User.telegram_id == telegram_id).first()
            
            # Если пользователь не найден, создаем нового
            if not user:
                logger.info(f"Creating new user with telegram_id: {telegram_id}")
                
                # Get username or first_name
                username = user_info.get('username')
                if not username:
                    username = user_info.get('first_name', f"user_{telegram_id}")
                logger.debug(f"Using username: {username}")
                
                # Создаем нового пользователя в блоке try-except для обработки возможных конфликтов
                try:
                    user = models.User(
                        telegram_id=telegram_id,
                        username=username,
                        avatar=user_info.get('photo_url'),
                        balance=5.0,
                        earned_hours=0.0,
                        spent_hours=0.0
                    )
                    db.add(user)
                    db.commit()
                    db.refresh(user)
                    logger.info(f"New user created: {user.username} (ID: {user.id}, Telegram ID: {user.telegram_id})")
                except IntegrityError:
                    # Если возникла ошибка уникальности, значит пользователь был создан в другом потоке
                    logger.warning(f"Concurrent user creation detected. Rolling back and retrying query.")
                    db.rollback()
                    # Повторяем запрос
                    user = db.query(models.User).filter(models.User.telegram_id == telegram_id).first()
                    if not user:
                        logger.error("Failed to find or create user after integrity error")
                        raise HTTPException(status_code=500, detail="User creation failed")
                    logger.info(f"Found user after concurrent creation: {user.username} (ID: {user.id}, Telegram ID: {user.telegram_id})")
            else:
                logger.info(f"Found existing user: {user.username} (ID: {user.id}, Telegram ID: {user.telegram_id})")
                
                # Update user data if changed
                changes_made = False
                
                if user_info.get('username') and user_info.get('username') != user.username:
                    old_username = user.username
                    user.username = user_info.get('username')
                    changes_made = True
                    logger.info(f"Updated username from {old_username} to: {user.username}")
                
                if user_info.get('photo_url') and user_info.get('photo_url') != user.avatar:
                    user.avatar = user_info.get('photo_url')
                    changes_made = True
                    logger.info(f"Updated avatar URL to: {user.avatar}")
                
                # Коммитим только если были изменения
                if changes_made:
                    try:
                        db.commit()
                    except IntegrityError:
                        logger.warning("Integrity error during user update, rolling back")
                        db.rollback()
                    
        except Exception as e:
            logger.error(f"Database error: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail="Database error")
            
        # Create JWT token
        try:
            logger.info(f"Creating JWT token for user: {user.username}")
            token_data = {
                "sub": str(user.id),
                "telegram_id": str(telegram_id),  # Convert to string to avoid JSON serialization issues
                "username": user.username
            }
            logger.debug(f"Token data: {token_data}")
            
            token = create_access_token(token_data)
            logger.info(f"JWT token created successfully")
        except Exception as e:
            logger.error(f"Error creating token: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail="Error creating authentication token")
        
        logger.info("=== Authentication Successful ===")
        logger.info("*"*80 + "\n\n")
        
        return {
            "access_token": token,
            "token_type": "bearer",
            "user": user
        }
        
    except HTTPException:
        logger.error("Authentication failed with HTTPException")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in auth: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}") 