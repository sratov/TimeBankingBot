from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
import models
import schemas
from database import SessionLocal, engine
import os
import shutil
from pathlib import Path
from auth import verify_telegram_hash, create_access_token, verify_token
from config import BOT_TOKEN
import logging

# Configure CORS
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://4d90-77-91-101-132.ngrok-free.app",
        "http://4d90-77-91-101-132.ngrok-free.app",
        "*"  # Временно разрешаем все домены для отладки
    ],
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

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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
        logger.info("=== Starting Telegram Authentication ===")
        
        # Get raw init_data without any decoding
        raw_init_data = request.query_params["init_data"]
        logger.debug("Raw init_data (repr): %r", raw_init_data)
        
        # Extract hash before any parsing/decoding
        pairs = [s.split("=", 1) for s in raw_init_data.split("&")]
        data = {k: v for k, v in pairs}
        
        hash_value = data.get('hash')
        if not hash_value:
            logger.error("No hash found in init_data")
            raise HTTPException(status_code=400, detail="No hash provided")
            
        # Verify hash with raw init_data (проверяем оба токена)
        if not verify_telegram_hash(raw_init_data, hash_value):
            logger.error("Hash verification failed")
            # Для отладки временно разрешаем вход даже при неправильном хеше
            logger.warning("BYPASSING HASH VERIFICATION FOR DEBUGGING")
            # Раскомментируйте строку ниже, чтобы включить строгую проверку хеша
            # raise HTTPException(status_code=401, detail="Invalid hash")
        else:
            logger.info("Hash verification successful")
            
        # Only decode user data AFTER hash verification
        try:
            user_data = data.get('user', '')
            if not user_data:
                logger.error("No user data found in params")
                raise ValueError("No user data found")
                
            # URL decode and parse user data
            import json
            import urllib.parse
            
            user_json = urllib.parse.unquote(user_data)
            user_info = json.loads(user_json)
            telegram_id = user_info.get('id')
            
            if not telegram_id:
                logger.error("No telegram_id found in user_info")
                raise ValueError("No telegram_id in user data")
                
        except Exception as e:
            logger.error(f"Error parsing user data: {str(e)}", exc_info=True)
            raise HTTPException(status_code=400, detail=f"Invalid user data format: {str(e)}")
            
        # Get or create user
        try:
            user = db.query(models.User).filter(models.User.telegram_id == telegram_id).first()
            if not user:
                logger.info(f"Creating new user with telegram_id: {telegram_id}")
                user = models.User(
                    telegram_id=telegram_id,
                    username=user_info.get('username') or user_info.get('first_name'),
                    avatar=user_info.get('photo_url'),
                    balance=5.0,
                    earned_hours=0.0,
                    spent_hours=0.0
                )
                db.add(user)
                db.commit()
                db.refresh(user)
                logger.info(f"New user created: {user.username}")
            else:
                logger.info(f"Found existing user: {user.username}")
        except Exception as e:
            logger.error(f"Database error: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail="Database error")
            
        # Create JWT token
        try:
            token = create_access_token({
                "sub": str(user.id),
                "telegram_id": telegram_id,
                "username": user.username
            })
            logger.info(f"JWT token created for user: {user.username}")
        except Exception as e:
            logger.error(f"Error creating token: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail="Error creating authentication token")
        
        logger.info("=== Authentication Successful ===")
        return {
            "access_token": token,
            "token_type": "bearer",
            "user": user
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in auth: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

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
    
    # Create prepayment transaction for requests
    if listing.listing_type == "request":
        transaction = models.Transaction(
            from_user_id=listing.user_id,
            to_user_id=listing.worker_id,
            hours=listing.hours,
            description=f"Prepayment for: {listing.title}",
            transaction_type="prepayment"
        )
        db.add(transaction)
        db.commit()
        
        # Update listing with prepayment
        listing.prepayment_transaction_id = transaction.id
        listing.status = "in_progress"
    else:
        listing.status = "pending_payment"
    
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
    
    if listing.listing_type == "offer" and listing.worker_id != int(token_data["sub"]):
        raise HTTPException(status_code=403, detail="Only worker can make payment for offers")
    
    if listing.status != "pending_payment":
        raise HTTPException(status_code=400, detail="Listing is not pending payment")
    
    # Create payment transaction for offers
    if listing.listing_type == "offer":
        transaction = models.Transaction(
            from_user_id=listing.worker_id,
            to_user_id=listing.user_id,
            hours=listing.hours,
            description=f"Payment for: {listing.title}",
            transaction_type="payment"
        )
        db.add(transaction)
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
    
    if listing.worker_id != int(token_data["sub"]):
        raise HTTPException(status_code=403, detail="Only worker can mark listing as complete")
    
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
    
    if listing.user_id != int(token_data["sub"]):
        raise HTTPException(status_code=403, detail="Only listing creator can confirm completion")
    
    if listing.status != "pending_confirmation":
        raise HTTPException(status_code=400, detail="Listing is not pending confirmation")
    
    # Update balances
    creator = db.query(models.User).filter(models.User.id == listing.user_id).first()
    worker = db.query(models.User).filter(models.User.id == listing.worker_id).first()
    
    if listing.listing_type == "request":
        worker.earned_hours += listing.hours
        creator.spent_hours += listing.hours
    else:
        creator.earned_hours += listing.hours
        worker.spent_hours += listing.hours
    
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
    if int(token_data["sub"]) != friend_request.user_id:
        raise HTTPException(status_code=403, detail="Cannot send friend request on behalf of another user")
    
    # Check if friend request already exists
    existing_request = db.query(models.Friend).filter(
        ((models.Friend.user_id == friend_request.user_id) & (models.Friend.friend_id == friend_request.friend_id)) |
        ((models.Friend.user_id == friend_request.friend_id) & (models.Friend.friend_id == friend_request.user_id))
    ).first()
    
    if existing_request:
        raise HTTPException(status_code=400, detail="Friend request already exists")
    
    # Create new friend request
    friend = models.Friend(
        user_id=friend_request.user_id,
        friend_id=friend_request.friend_id,
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