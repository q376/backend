"""from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Dict, Any

class WalletAuth(BaseModel):
    wallet_raw: str
    wallet_user_friendly: str

class ScoreSubmission(BaseModel):
    wallet_address: str = Field(..., alias="wallet_address")
    game: str
    score: float
    gameData: Optional[Dict[str, Any]] = None
    timestamp: int

    class Config:
        populate_by_name = True  # Allows both 'wallet' and 'wallet_address'

class GameResultCreate(BaseModel):
    wallet_raw: str
    wallet_user_friendly: str
    game_name: str
    score: float

class GameResultResponse(GameResultCreate):
    id: int
    played_at: datetime

    class Config:
        from_attributes = True  # Updated for Pydantic v2 (was orm_mode)
"""

from pydantic import BaseModel
from datetime import datetime

class WalletAuth(BaseModel):
    wallet_raw: str
    wallet_user_friendly: str

class ScoreSubmission(BaseModel):
    wallet: str
    game: str
    score: int
    gameData: dict
    timestamp: int

class GameResultCreate(BaseModel):
    wallet_raw: str
    wallet_user_friendly: str
    game_name: str
    score: float

class GameResultResponse(GameResultCreate):
    id: int
    played_at: datetime

    class Config:
        orm_mode = True
