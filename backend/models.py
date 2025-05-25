from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from database import Base
import enum

class ListingType(str, enum.Enum):
    request = "request"
    offer = "offer"

class ListingStatus(str, enum.Enum):
    active = "active"
    pending_worker = "pending_worker"  # When worker applied but not yet accepted
    pending_payment = "pending_payment"  # When worker is accepted but payment not made
    in_progress = "in_progress"  # When payment is made and work is in progress
    pending_confirmation = "pending_confirmation"  # When work is done but not confirmed
    completed = "completed"
    cancelled = "cancelled"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(Integer, unique=True, index=True)
    username = Column(String, index=True)
    avatar = Column(String, nullable=True)  # URL to avatar image
    balance = Column(Float, default=5.0)
    earned_hours = Column(Float, default=0.0)
    spent_hours = Column(Float, default=0.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Listings where user is the creator
    created_listings = relationship("Listing", back_populates="creator", foreign_keys="[Listing.user_id]")
    # Listings where user is the worker
    working_listings = relationship("Listing", back_populates="worker", foreign_keys="[Listing.worker_id]")
    
    transactions_sent = relationship("Transaction", foreign_keys="[Transaction.from_user_id]", back_populates="from_user")
    transactions_received = relationship("Transaction", foreign_keys="[Transaction.to_user_id]", back_populates="to_user")

    # Friends relationships
    friends_as_user = relationship("Friend", foreign_keys="[Friend.user_id]", back_populates="user")
    friends_as_friend = relationship("Friend", foreign_keys="[Friend.friend_id]", back_populates="friend")

class Friend(Base):
    __tablename__ = "friends"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    friend_id = Column(Integer, ForeignKey("users.id"))
    status = Column(String, default="pending")  # pending, accepted, blocked
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", foreign_keys=[user_id], back_populates="friends_as_user")
    friend = relationship("User", foreign_keys=[friend_id], back_populates="friends_as_friend", overlaps="friends_as_user")

class Listing(Base):
    __tablename__ = "listings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    worker_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    title = Column(String, index=True)
    description = Column(String)
    hours = Column(Float)
    status = Column(String, default="active")
    listing_type = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    prepayment_transaction_id = Column(Integer, ForeignKey("transactions.id"), nullable=True)

    creator = relationship("User", back_populates="created_listings", foreign_keys=[user_id])
    worker = relationship("User", back_populates="working_listings", foreign_keys=[worker_id])
    prepayment = relationship("Transaction", foreign_keys=[prepayment_transaction_id])

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    from_user_id = Column(Integer, ForeignKey("users.id"))
    to_user_id = Column(Integer, ForeignKey("users.id"))
    hours = Column(Float)
    description = Column(String)
    transaction_type = Column(String, default="payment")  # payment, prepayment, refund
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    from_user = relationship("User", foreign_keys=[from_user_id], back_populates="transactions_sent")
    to_user = relationship("User", foreign_keys=[to_user_id], back_populates="transactions_received") 