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
