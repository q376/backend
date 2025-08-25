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

# -------------------
# Эндпоинт Telegram login
# -------------------
# -----------------------
# Login / регистрация
# -----------------------
@app.post("/auth/telegram")
def telegram_login(user: UserTelegram, response: Response):
    db = SessionLocal()
    existing_user = db.query(User).filter(User.telegram_id == user.telegram_id).first()

    if not existing_user:
        # Регистрация нового пользователя
        new_user = User(
            telegram_id=user.telegram_id,
            username=user.username,
@@ -97,48 +96,41 @@
        db.close()
        user_db = new_user
    else:
        # Пользователь уже есть
        user_db = existing_user
        db.close()

    # Создаём JWT
    # JWT
    payload = {
        "telegram_id": user_db.telegram_id,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(days=7)  # срок жизни токена
        "exp": datetime.datetime.utcnow() + datetime.timedelta(days=7)
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")

    # Кладём в cookie
    response.set_cookie(
        key="session_token",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=7*24*60*60  # 7 дней
        max_age=7*24*60*60
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
    return {"message": "Login successful", "user": {
        "telegram_id": user_db.telegram_id,
        "username": user_db.username,
        "first_name": user_db.first_name,
        "last_name": user_db.last_name,
        "photo_url": user_db.photo_url,
        "wallet": user_db.wallet
    }}

# -------------------
# Эндпоинт для проверки сессии
# -------------------
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
@@ -163,9 +155,9 @@
        "wallet": user.wallet
    }

# -------------------
# -----------------------
# Logout
# -------------------
# -----------------------
@app.post("/auth/logout")
def logout(response: Response):
    response.delete_cookie("session_token")
    
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
