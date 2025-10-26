from schemas import WalletAuth, GameResultCreate, GameResultResponse, ScoreSubmission
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import func
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
    wallet_raw = Column(String, unique=True, index=True, nullable=False)
    wallet_user_friendly = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    total_earned = Column(Float, default=0.0)
    tournaments_won = Column(Integer, default=0)
    games_played = Column(Integer, default=0)

class GameResult(Base):
    __tablename__ = "game_results"
    id = Column(Integer, primary_key=True, index=True)
    wallet_raw = Column(String(64), ForeignKey("users.wallet_raw", ondelete="CASCADE"))
    wallet_user_friendly = Column(String, nullable=False)
    game_name = Column(String(64), nullable=False)
    score = Column(Float, nullable=False)
    played_at = Column(DateTime(timezone=True), server_default=func.now())

Base.metadata.create_all(bind=engine)

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
# NEW: Wallet Authentication (FIXED VALIDATION)
# -------------------
@app.post("/auth/wallet")
def wallet_login(auth: WalletAuth):
    db = SessionLocal()
    
    # Берём raw и user-friendly
    wallet_raw = auth.wallet_raw.strip()
    wallet_user_friendly = auth.wallet_user_friendly.strip()
    
    # Проверка
    if not wallet_raw or not wallet_user_friendly:
        db.close()
        raise HTTPException(status_code=400, detail="Wallet addresses cannot be empty")
    
    # Проверка существующего пользователя по raw адресу
    existing_user = db.query(User).filter(User.wallet_raw == wallet_raw).first()
    
    if not existing_user:
        # Регистрация нового
        new_user = User(
            wallet_raw=wallet_raw,
            wallet_user_friendly=wallet_user_friendly,
            created_at=datetime.utcnow(),
            total_earned=0.0,
            tournaments_won=0,
            games_played=0
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        db.close()
        return {"message": "User registered", "user": new_user.__dict__}
    
    db.close()
    return {"message": "Login successful", "user": existing_user.__dict__}


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
    user = db.query(User).filter(User.wallet_raw == submission.wallet).first()
    
    if not user:
        db.close()
        raise HTTPException(status_code=404, detail="User not found. Please connect wallet first.")
    
    # Update games played count
    user.games_played += 1
    db.commit()
    
    print(f"🎮 Score submitted - Wallet: {submission.wallet}, Game: {submission.game}, Score: {submission.score}")
    
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
    
    print(f"💰 Earnings updated - Wallet: {wallet_address}, Amount: {amount} TON")
    
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
"""
@app.get("/leaderboard")
def get_leaderboard(limit: int = 10):
"""
#Get top earners leaderboard
"""
    db = SessionLocal()
    
    top_users = db.query(User).order_by(User.total_earned.desc()).limit(limit).all()
    
    leaderboard = [
        {
            "wallet_address": user.wallet_address,
            "wallet_short": f"{user.wallet_address[:6]}...{user.wallet_address[-4:]}",
            "total_earned": user.total_earned,
            "tournaments_won": user.tournaments_won,
            "games_played": user.games_played
        }
        for user in top_users
    ]
    
    db.close()
    return {"leaderboard": leaderboard}
"""

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/game/result", response_model=GameResultResponse)
def save_game_result(result: GameResultCreate, db: Session = Depends(get_db)):
    # Проверяем, что пользователь существует
    user = db.query(models.User).filter(models.User.wallet_raw == result.wallet_raw).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    new_result = models.GameResult(**result.dict())
    db.add(new_result)

    # Можно инкрементировать количество сыгранных игр
    user.games_played += 1

    db.commit()
    db.refresh(new_result)

    return new_result

# -------------------
# Health check
# -------------------
@app.get("/")
def health_check():
    return {
        "status": "ok", 
        "message": "TonArcade API is running",
        "endpoints": {
            "auth": "/auth/wallet",
            "user": "/user/{wallet_address}",
            "submit_score": "/submit-score",
            "leaderboard": "/leaderboard"
        }
    }






