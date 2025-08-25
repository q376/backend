from fastapi import FastAPI, HTTPException, Request, Response, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, BigInteger
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import os
import jwt
import datetime
import hashlib
import hmac
import time
from typing import Optional

# -------------------
# App Configuration
# -------------------
app = FastAPI()

DATABASE_URL = os.getenv("DATABASE_URL")
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-this-in-production")
BOT_TOKEN = os.getenv("BOT_TOKEN", "your-telegram-bot-token")  # Add this to your .env

# SQLAlchemy setup
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

security = HTTPBearer(auto_error=False)

# -------------------
# Database Model
# -------------------
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(BigInteger, unique=True, index=True, nullable=False)
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    photo_url = Column(String, nullable=True)
    wallet = Column(String, nullable=True)

Base.metadata.create_all(bind=engine)

# -------------------
# Pydantic Models
# -------------------
class TelegramAuthData(BaseModel):
    id: int
    first_name: str
    username: Optional[str] = None
    last_name: Optional[str] = None
    photo_url: Optional[str] = None
    auth_date: int
    hash: str

class Token(BaseModel):
    access_token: str
    token_type: str

class UserResponse(BaseModel):
    telegram_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    photo_url: Optional[str] = None
    wallet: Optional[str] = None

# -------------------
# CORS Configuration
# -------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change to your domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
# JWT Helper Functions
# -------------------
def create_access_token(telegram_id: int, expires_delta: Optional[datetime.timedelta] = None):
    if expires_delta:
        expire = datetime.datetime.utcnow() + expires_delta
    else:
        expire = datetime.datetime.utcnow() + datetime.timedelta(days=7)
    
    payload = {
        "sub": str(telegram_id),
        "exp": expire,
        "iat": datetime.datetime.utcnow()
    }
    
    token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
    return token

def verify_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        telegram_id = int(payload.get("sub"))
        return telegram_id
    except jwt.ExpiredSignatureError:
        return None
    except (jwt.JWTError, ValueError):
        return None

def verify_telegram_auth(auth_data: dict, bot_token: str) -> bool:
    """Verify Telegram widget authentication data"""
    check_hash = auth_data.pop('hash', None)
    if not check_hash:
        return False
    
    # Create data check string
    data_check_arr = []
    for key, value in sorted(auth_data.items()):
        data_check_arr.append(f"{key}={value}")
    data_check_string = '\n'.join(data_check_arr)
    
    # Create secret key from bot token
    secret_key = hashlib.sha256(bot_token.encode()).digest()
    
    # Calculate hash
    calculated_hash = hmac.new(
        secret_key, 
        data_check_string.encode(), 
        hashlib.sha256
    ).hexdigest()
    
    # Verify hash matches
    if calculated_hash != check_hash:
        return False
    
    # Check auth_date (should be within 1 day)
    auth_date = auth_data.get('auth_date', 0)
    current_time = int(time.time())
    if current_time - auth_date > 86400:  # 24 hours
        return False
    
    return True

# -------------------
# Authentication Dependency
# -------------------
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    if not credentials:
        raise HTTPException(
            status_code=401, 
            detail="Authentication required"
        )
    
    telegram_id = verify_token(credentials.credentials)
    if not telegram_id:
        raise HTTPException(
            status_code=401, 
            detail="Invalid or expired token"
        )
    
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return user

# -------------------
# API Endpoints
# -------------------
@app.post("/auth/telegram", response_model=dict)
def telegram_login(auth_data: TelegramAuthData, db: Session = Depends(get_db)):
    """Login with Telegram widget data"""
    
    # Convert to dict for verification (without hash for verification)
    auth_dict = auth_data.dict()
    
    # Verify Telegram authentication
    if not verify_telegram_auth(auth_dict.copy(), BOT_TOKEN):
        raise HTTPException(
            status_code=401,
            detail="Invalid Telegram authentication data"
        )
    
    # Check if user exists
    user = db.query(User).filter(User.telegram_id == auth_data.id).first()
    
    if not user:
        # Create new user
        user = User(
            telegram_id=auth_data.id,
            username=auth_data.username,
            first_name=auth_data.first_name,
            last_name=auth_data.last_name,
            photo_url=auth_data.photo_url
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        # Update existing user info
        user.username = auth_data.username
        user.first_name = auth_data.first_name
        user.last_name = auth_data.last_name
        user.photo_url = auth_data.photo_url
        db.commit()
    
    # Create JWT token
    access_token = create_access_token(user.telegram_id)
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "telegram_id": user.telegram_id,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "photo_url": user.photo_url,
            "wallet": user.wallet
        }
    }

@app.get("/auth/me", response_model=UserResponse)
def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current authenticated user information"""
    return UserResponse(
        telegram_id=current_user.telegram_id,
        username=current_user.username,
        first_name=current_user.first_name,
        last_name=current_user.last_name,
        photo_url=current_user.photo_url,
        wallet=current_user.wallet
    )

@app.post("/auth/refresh", response_model=Token)
def refresh_token(current_user: User = Depends(get_current_user)):
    """Refresh the access token"""
    access_token = create_access_token(current_user.telegram_id)
    return {"access_token": access_token, "token_type": "bearer"}

@app.put("/user/wallet")
def update_wallet(
    wallet_data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update user's wallet address"""
    wallet = wallet_data.get("wallet", "").strip()
    
    if not wallet:
        raise HTTPException(status_code=400, detail="Wallet address is required")
    
    # Basic TON wallet validation
    if not (wallet.startswith("EQ") or wallet.startswith("UQ")):
        raise HTTPException(
            status_code=400, 
            detail="Invalid TON wallet format! Address should start with EQ or UQ"
        )
    
    if len(wallet) < 40:
        raise HTTPException(
            status_code=400, 
            detail="TON wallet address is too short!"
        )
    
    current_user.wallet = wallet
    db.commit()
    
    return {"message": "Wallet updated successfully", "wallet": wallet}

@app.get("/user/{telegram_id}")
def get_user_by_id(telegram_id: int, db: Session = Depends(get_db)):
    """Get user by Telegram ID - for backward compatibility"""
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

@app.post("/submit-score")
def submit_score(
    score_data: dict,
    current_user: User = Depends(get_current_user)
):
    """Submit game score - protected endpoint"""
    # Here you can add your score validation and storage logic
    game = score_data.get("game")
    score = score_data.get("score")
    
    if not game or score is None:
        raise HTTPException(status_code=400, detail="Game and score are required")
    
    # Add your score processing logic here
    return {
        "message": "Score submitted successfully",
        "game": game,
        "score": score,
        "user_id": current_user.telegram_id
    }

# -------------------
# Health Check
# -------------------
@app.get("/")
def root():
    return {"message": "CryptoVerse API is running!"}

@app.get("/health")
def health():
    return {"status": "healthy"}
'''
from fastapi import FastAPI, HTTPException
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

# -----------------------
# Login / регистрация
# -----------------------
@app.post("/auth/telegram")
def telegram_login(user: UserTelegram, response: Response):
    db = SessionLocal()
    existing_user = db.query(User).filter(User.telegram_id == user.telegram_id).first()
    
    if not existing_user:
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
        user_db = existing_user
        db.close()
    
    # JWT
    payload = {
        "telegram_id": user_db.telegram_id,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(days=7)
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
    
    response.set_cookie(
        key="session_token",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=7*24*60*60
    )
    
    return {"message": "Login successful", "user": {
        "telegram_id": user_db.telegram_id,
        "username": user_db.username,
        "first_name": user_db.first_name,
        "last_name": user_db.last_name,
        "photo_url": user_db.photo_url,
        "wallet": user_db.wallet
    }}

# -----------------------
# Проверка сессии
# -----------------------
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

# -----------------------
# Logout
# -----------------------
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
)
'''
