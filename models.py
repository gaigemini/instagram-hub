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

class ReplyRequest(BaseModel):
    username: str
    thread_id: Optional[str] = None
    message_id: Optional[str] = None
    comment_id: Optional[str] = None
    reply_text: str
    reply_type: str  # "message" or "comment"

class ReplyResponse(BaseModel):
    success: bool
    message: str
    reply_id: Optional[str] = None

class WebhookEventInfo(BaseModel):
    id: str
    username: str
    event_type: str
    event_data: dict
    processed: bool
    webhook_sent: bool
    created_at: datetime

class WebhookEventsResponse(BaseModel):
    events: List[WebhookEventInfo]
    total_count: int

class MonitoringStatusResponse(BaseModel):
    monitoring: bool
    active_monitors: List[str]
    last_checks: dict