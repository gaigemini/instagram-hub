# models.py
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List

class LoginRequest(BaseModel):
    username: str
    password: str

class SessionInfo(BaseModel):
    username: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

class LoginResponse(BaseModel):
    success: bool
    message: str
    user_info: Optional[dict] = None

class LogoutResponse(BaseModel):
    success: bool
    message: str

class UserInfoResponse(BaseModel):
    success: bool
    message: str
    user_info: Optional[dict] = None

class SessionsResponse(BaseModel):
    sessions: List[SessionInfo]

class HealthResponse(BaseModel):
    message: str
    active_sessions: int
    usernames: List[str]