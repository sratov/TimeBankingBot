from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List

class UserBase(BaseModel):
    username: str
    balance: float
    earned_hours: float
    spent_hours: float

class UserProfile(UserBase):
    id: int
    telegram_id: int
    avatar: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class ListingBase(BaseModel):
    title: str
    description: str
    hours: float
    listing_type: str

class ListingCreate(ListingBase):
    user_id: int

class Listing(ListingBase):
    id: int
    user_id: int
    worker_id: Optional[int] = None
    status: str
    created_at: datetime
    prepayment_transaction_id: Optional[int] = None
    creator: Optional[UserProfile] = None
    worker: Optional[UserProfile] = None

    class Config:
        from_attributes = True

class TransactionBase(BaseModel):
    hours: float
    description: str

class TransactionCreate(TransactionBase):
    from_user_id: int
    to_user_id: int
    transaction_type: str = "payment"

class Transaction(TransactionBase):
    id: int
    from_user_id: int
    to_user_id: int
    transaction_type: str
    created_at: datetime
    from_user: Optional[UserProfile] = None
    to_user: Optional[UserProfile] = None

    class Config:
        from_attributes = True

class FriendBase(BaseModel):
    friend_id: int

class FriendCreate(FriendBase):
    pass

class Friend(FriendBase):
    id: int
    user_id: int
    status: str
    created_at: datetime
    user: Optional[UserProfile] = None
    friend: Optional[UserProfile] = None

    class Config:
        from_attributes = True

Listing.model_rebuild() 