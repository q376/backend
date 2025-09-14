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
