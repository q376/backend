from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os

# -------------------
# Настройка приложения
# -------------------
app = FastAPI()

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

# -------------------
# NEW: Модель пользователя (wallet-based)
# -------------------
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    wallet_address = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    total_earned = Column(Float, default=0.0)
    tournaments_won = Column(Integer, default=0)
    games_played = Column(Integer, default=0)

Base.metadata.create_all(bind=engine)

# -------------------
# Pydantic схемы
# -------------------
class WalletAuth(BaseModel):
    wallet_address: str

class ScoreSubmission(BaseModel):
    wallet: str
    game: str
    score: int
    gameData: dict
    timestamp: int

# -------------------
# CORS
# -------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшене укажите конкретный домен
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------
# NEW: Wallet Authentication
# -------------------
@app.post("/auth/wallet")
def wallet_login(auth: WalletAuth):
    """
    Authenticate or register user by TON wallet address
    """
    db = SessionLocal()
    
    # Validate wallet address format
    if not (auth.wallet_address.startswith("EQ") or auth.wallet_address.startswith("UQ")):
        db.close()
        raise HTTPException(status_code=400, detail="Invalid TON wallet address format")
    
    if len(auth.wallet_address) < 40:
        db.close()
        raise HTTPException(status_code=400, detail="TON wallet address too short")
    
    # Check if user exists
    existing_user = db.query(User).filter(User.wallet_address == auth.wallet_address).first()
    
    if not existing_user:
        # Register new user
        new_user = User(
            wallet_address=auth.wallet_address,
            created_at=datetime.utcnow(),
            total_earned=0.0,
            tournaments_won=0,
            games_played=0
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        response = {
            "message": "User registered",
            "user": {
                "wallet_address": new_user.wallet_address,
                "created_at": new_user.created_at.isoformat(),
                "total_earned": new_user.total_earned,
                "tournaments_won": new_user.tournaments_won,
                "games_played": new_user.games_played
            }
        }
        db.close()
        return response
    else:
        # Return existing user
        response = {
            "message": "Login successful",
            "user": {
                "wallet_address": existing_user.wallet_address,
                "created_at": existing_user.created_at.isoformat(),
                "total_earned": existing_user.total_earned,
                "tournaments_won": existing_user.tournaments_won,
                "games_played": existing_user.games_played
            }
        }
        db.close()
        return response

# -------------------
# Get user by wallet address
# -------------------
@app.get("/user/{wallet_address}")
def get_user(wallet_address: str):
    """
    Get user details by wallet address
    """
    db = SessionLocal()
    user = db.query(User).filter(User.wallet_address == wallet_address).first()
    db.close()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "wallet_address": user.wallet_address,
        "created_at": user.created_at.isoformat(),
        "total_earned": user.total_earned,
        "tournaments_won": user.tournaments_won,
        "games_played": user.games_played
    }

# -------------------
# Submit game score
# -------------------
@app.post("/submit-score")
def submit_score(submission: ScoreSubmission):
    """
    Submit a game score for a wallet address
    """
    db = SessionLocal()
    
    # Find user by wallet
    user = db.query(User).filter(User.wallet_address == submission.wallet).first()
    
    if not user:
        db.close()
        raise HTTPException(status_code=404, detail="User not found. Please connect wallet first.")
    
    # Update games played count
    user.games_played += 1
    db.commit()
    
    # TODO: Here you would:
    # 1. Store the score in a separate scores table
    # 2. Validate the score with anti-cheat logic
    # 3. Update leaderboards
    # 4. Check if user won a tournament and update total_earned
    
    db.close()
    
    return {
        "message": "Score submitted successfully",
        "game": submission.game,
        "score": submission.score,
        "wallet": submission.wallet
    }

# -------------------
# Update user earnings (admin endpoint - add auth later!)
# -------------------
@app.post("/update-earnings")
def update_earnings(wallet_address: str, amount: float, tournament_win: bool = False):
    """
    Update user's earnings after winning a tournament
    NOTE: This should be protected with admin authentication in production!
    """
    db = SessionLocal()
    
    user = db.query(User).filter(User.wallet_address == wallet_address).first()
    
    if not user:
        db.close()
        raise HTTPException(status_code=404, detail="User not found")
    
    user.total_earned += amount
    if tournament_win:
        user.tournaments_won += 1
    
    db.commit()
    db.refresh(user)
    
    response = {
        "message": "Earnings updated",
        "wallet_address": user.wallet_address,
        "total_earned": user.total_earned,
        "tournaments_won": user.tournaments_won
    }
    
    db.close()
    return response

# -------------------
# Get leaderboard
# -------------------
@app.get("/leaderboard")
def get_leaderboard(limit: int = 10):
    """
    Get top earners leaderboard
    """
    db = SessionLocal()
    
    top_users = db.query(User).order_by(User.total_earned.desc()).limit(limit).all()
    
    leaderboard = [
        {
            "wallet_address": user.wallet_address,
            "total_earned": user.total_earned,
            "tournaments_won": user.tournaments_won,
            "games_played": user.games_played
        }
        for user in top_users
    ]
    
    db.close()
    return {"leaderboard": leaderboard}

# -------------------
# Health check
# -------------------
@app.get("/")
def health_check():
    return {"status": "ok", "message": "TonArcade API is running"}

'''
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, BigInteger
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# -------------------
# Настройка приложения
# -------------------
app = FastAPI()

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

# -------------------
# Модель пользователя
# -------------------
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(BigInteger, unique=True, index=True, nullable=False)
    username = Column(String, nullable=True)
    wallet = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    photo_url = Column(String, nullable=True)

Base.metadata.create_all(bind=engine)

# -------------------
# Pydantic схема
# -------------------
class UserTelegram(BaseModel):
    telegram_id: int
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    photo_url: str | None = None
    wallet: str | None = None

# -------------------
# CORS
# -------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # лучше конкретный домен фронта
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------
# Эндпоинт Telegram login
# -------------------
@app.post("/auth/telegram")
def telegram_login(user: UserTelegram):
    db = SessionLocal()
    existing_user = db.query(User).filter(User.telegram_id == user.telegram_id).first()
    
    if not existing_user:
        # регистрация нового пользователя
        new_user = User(
            telegram_id=user.telegram_id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            photo_url=user.photo_url,
            wallet=user.wallet
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        db.close()
        return {"message": "User registered", "user": new_user.__dict__}
    else:
        db.close()
        return {"message": "Login successful", "user": existing_user.__dict__}

# -------------------
# Получение юзера по ID
# -------------------
@app.get("/user/{telegram_id}")
def get_user(telegram_id: int):
    db = SessionLocal()
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    db.close()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "id": user.id,
        "telegram_id": user.telegram_id,
        "username": user.username,
        "wallet": user.wallet,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "photo_url": user.photo_url
    }

class WalletUpdate(BaseModel):
    telegram_id: int
    wallet: str

@app.post("/save_wallet")
def save_wallet(data: WalletUpdate):
    db = SessionLocal()
    user = db.query(User).filter(User.telegram_id == data.telegram_id).first()
    if not user:
        db.close()
        raise HTTPException(status_code=404, detail="User not found")
    user.wallet = data.wallet
    db.commit()
    db.refresh(user)
    db.close()
    return {"message": "Wallet updated", "wallet": user.wallet}
'''
