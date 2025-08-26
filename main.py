from fastapi import FastAPI, HTTPException, Request, Response, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, BigInteger
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import os
import jwt
import datetime
import hashlib
import hmac

# -------------------
# App Setup
# -------------------
app = FastAPI()

DATABASE_URL = os.getenv("DATABASE_URL")
SECRET_KEY = os.getenv("SECRET_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")  # Add this to your environment

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

# -------------------
# Database Model
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
# Pydantic Schemas
# -------------------
class TelegramUser(BaseModel):
    id: int
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    photo_url: str | None = None
    auth_date: int
    hash: str

# -------------------
# Database Dependency
# -------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# -------------------
# Security Functions
# -------------------
def verify_telegram_hash(data: dict) -> bool:
    """Verify Telegram Login Widget data is authentic"""
    if not TELEGRAM_BOT_TOKEN:
        print("WARNING: TELEGRAM_BOT_TOKEN not set!")
        return True  # Skip verification in development
    
    received_hash = data.pop('hash', None)
    if not received_hash:
        return False
    
    # Create data check string
    data_check_string = '\n'.join([f"{k}={v}" for k, v in sorted(data.items())])
    
    # Create secret key
    secret_key = hashlib.sha256(TELEGRAM_BOT_TOKEN.encode()).digest()
    
    # Calculate hash
    calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    
    return calculated_hash == received_hash

def get_current_user_id(request: Request) -> int | None:
    """Get current user ID from JWT token"""
    token = request.cookies.get("session_token")
    if not token:
        return None
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload["telegram_id"]
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None

# -------------------
# CORS Setup
# -------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------
# Auth Endpoints
# -------------------
@app.post("/auth/telegram")
def telegram_login(user: TelegramUser, response: Response, db: Session = Depends(get_db)):
    """Telegram Login - Now with hash verification"""
    
    # Verify Telegram data is authentic (CRITICAL FOR P2E!)
    user_dict = user.dict()
    if not verify_telegram_hash(user_dict.copy()):
        raise HTTPException(status_code=401, detail="Invalid Telegram authentication")
    
    telegram_id = user.id
    
    # Find or create user
    existing_user = db.query(User).filter(User.telegram_id == telegram_id).first()
    
    if not existing_user:
        # Register new user
        new_user = User(
            telegram_id=telegram_id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            photo_url=user.photo_url
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        user_db = new_user
    else:
        # Update existing user data
        existing_user.username = user.username
        existing_user.first_name = user.first_name
        existing_user.last_name = user.last_name
        existing_user.photo_url = user.photo_url
        db.commit()
        user_db = existing_user
    
    # Create JWT token
    payload = {
        "telegram_id": user_db.telegram_id,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(days=7)
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
    
    # Set secure cookie
    response.set_cookie(
        key="session_token",
        value=token,
        httponly=True,          # JavaScript can't access (anti-XSS)
        secure=True,           # HTTPS only (set to False for local dev)
        samesite="strict",     # CSRF protection
        max_age=7*24*60*60     # 7 days
    )
    
    return {
        "success": True,
        "message": "Login successful",
        "user": {
            "telegram_id": user_db.telegram_id,
            "username": user_db.username,
            "first_name": user_db.first_name,
            "last_name": user_db.last_name,
            "photo_url": user_db.photo_url,
            "wallet": user_db.wallet
        }
    }

@app.get("/auth/check")
def check_session(request: Request, db: Session = Depends(get_db)):
    """Check if user is logged in - THIS PREVENTS LOGOUT ON REFRESH"""
    
    user_id = get_current_user_id(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # Get user from database
    user = db.query(User).filter(User.telegram_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "authenticated": True,
        "telegram_id": user.telegram_id,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "photo_url": user.photo_url,
        "wallet": user.wallet
    }

@app.post("/auth/logout")
def logout(response: Response):
    """Logout user"""
    response.delete_cookie("session_token")
    return {"success": True, "message": "Logged out"}

# -------------------
# Protected Routes (examples)
# -------------------
@app.get("/user/{telegram_id}")
def get_user(telegram_id: int, db: Session = Depends(get_db)):
    """Get user by telegram ID"""
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "telegram_id": user.telegram_id,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "photo_url": user.photo_url,
        "wallet": user.wallet
    }

@app.post("/user/update-wallet")
def update_wallet(wallet: str, request: Request, db: Session = Depends(get_db)):
    """Update user's wallet address"""
    
    user_id = get_current_user_id(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    user = db.query(User).filter(User.telegram_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.wallet = wallet
    db.commit()
    
    return {"success": True, "message": "Wallet updated"}

# -------------------
# Game Score Endpoint (example)
# -------------------
@app.post("/submit-score")
def submit_score(score_data: dict, request: Request, db: Session = Depends(get_db)):
    """Submit game score - protected endpoint"""
    
    user_id = get_current_user_id(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # Validate and save score
    # Add your game score logic here
    
    return {"success": True, "message": "Score submitted"}

# -------------------
# Health Check
# -------------------
@app.get("/")
def root():
    return {"message": "CryptoVerse API is running!", "status": "healthy"}

'''from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, BigInteger
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
# for session keys
from fastapi import Request, Response
import jwt, datetime

# FastAPI app
app = FastAPI()

# Render database URL
DATABASE_URL = os.getenv("DATABASE_URL")
SECRET_KEY = os.getenv("SECRET_KEY")

from fastapi import FastAPI, HTTPException, Request, Response, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, BigInteger
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
import jwt, datetime

# -------------------
# Настройка приложения
# -------------------
app = FastAPI()

DATABASE_URL = os.getenv("DATABASE_URL")
SECRET_KEY = os.getenv("SECRET_KEY")

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
    allow_origins=["*"],  # фронт: можно конкретный URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------
# Эндпоинт Telegram login
# -------------------
@app.post("/auth/telegram")
def telegram_login(user: UserTelegram, response: Response):
    db = SessionLocal()
    existing_user = db.query(User).filter(User.telegram_id == user.telegram_id).first()
    
    if not existing_user:
        # Регистрация нового пользователя
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
        user_db = new_user
    else:
        # Пользователь уже есть
        user_db = existing_user
        db.close()
    
    # Создаём JWT
    payload = {
        "telegram_id": user_db.telegram_id,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(days=7)  # срок жизни токена
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
    
    # Кладём в cookie
    response.set_cookie(
        key="session_token",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=7*24*60*60  # 7 дней
    )
    
    return {
        "message": "Login successful",
        "user": {
            "telegram_id": user_db.telegram_id,
            "username": user_db.username,
            "first_name": user_db.first_name,
            "last_name": user_db.last_name,
            "photo_url": user_db.photo_url,
            "wallet": user_db.wallet
        }
    }
    print("Token:", token)

# -------------------
# Эндпоинт для проверки сессии
# -------------------
@app.get("/auth/check")
def auth_check(request: Request):
    token = request.cookies.get("session_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        telegram_id = payload["telegram_id"]
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    db = SessionLocal()
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    db.close()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "telegram_id": user.telegram_id,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "photo_url": user.photo_url,
        "wallet": user.wallet
    }

# -------------------
# Logout
# -------------------
@app.post("/auth/logout")
def logout(response: Response):
    response.delete_cookie("session_token")
    return {"message": "Logged out"}


# SQLAlchemy setup
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

# Table - Users
class User(Base):
    __tablename__ = "users" # name of the table
    id = Column(Integer, primary_key=True, index=True) # SQL identification (unique)
    telegram_id = Column(BigInteger, unique=True, index=True, nullable=False) # TELEGRAM ID (unique)
    username = Column(String, nullable=True) # TELEGRAM username (unique (?)) 
    wallet = Column(String, nullable=True) # TON wallet
    first_name = Column(String, nullable=True) # TELEGRAM first name
    last_name = Column(String, nullable=True) # TELEGRAM last name - surname
    photo_url = Column(String, nullable=True) # TELEGRAM user photo/avatar/pfp 

# Creating the tables
Base.metadata.create_all(bind=engine)

# Pydantic schema
class UserCreate(BaseModel):
    telegram_id: int
    username: str | None = None
    wallet: str | None = None
    # new
    first_name: str | None
    last_name: str | None
    photo_url: str | None

@app.post("/register")
def register(user: UserCreate):
    db = SessionLocal()
    existing = db.query(User).filter(User.telegram_id == user.telegram_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="User already exists")

    new_user = User(
        telegram_id=user.telegram_id,
        username=user.username,
        wallet=user.wallet,
        first_name=user.first_name,
        last_name=user.last_name,
        photo_url=user.photo_url  # changed avatar_url -> photo_url
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    db.close()

    return {
        "message": "User registered",
        "user": {
            "id": new_user.id,
            "telegram_id": new_user.telegram_id,
            "username": new_user.username,
            "wallet": new_user.wallet,
            "first_name": new_user.first_name,
            "last_name": new_user.last_name,
            "photo_url": new_user.photo_url  # changed avatar_url -> photo_url
        }
    }

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
        "photo_url": user.photo_url  # changed avatar_url -> photo_url
    }

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # или конкретный URL фронта
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)'''
