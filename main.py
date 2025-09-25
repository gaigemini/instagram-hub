# main.py
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from contextlib import asynccontextmanager
import uvicorn
import logging

# Import our modules
from database import get_db, create_tables, InstagramSession, SessionLocal
from instagram_manager import InstagramManager
from models import (
    LoginRequest, LoginResponse, LogoutResponse, UserInfoResponse,
    SessionInfo, SessionsResponse, HealthResponse
)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Instagram Manager
instagram_manager = InstagramManager()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("🚀 Starting Instagram Hub...")
    create_tables()
    loaded_sessions = await instagram_manager.load_existing_sessions()
    logger.info(f"✅ Loaded {loaded_sessions} active sessions")
    yield
    # Shutdown
    logger.info("🛑 Shutting down Instagram Hub...")

# FastAPI App
app = FastAPI(
    title="Instagram Hub",
    description="Multi-session Instagram API hub using aiograpi",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """Login to Instagram and save session"""
    success, message, user_info = await instagram_manager.login(
        request.username, 
        request.password
    )
    
    if not success:
        # Don't raise HTTPException for login failures, return structured response
        return LoginResponse(success=False, message=message, user_info=user_info)
    
    return LoginResponse(success=success, message=message, user_info=user_info)

@app.post("/logout/{username}", response_model=LogoutResponse)
async def logout(username: str):
    """Logout and deactivate session"""
    success, message = await instagram_manager.logout(username)
    
    if not success:
        raise HTTPException(status_code=500, detail=message)
    
    return LogoutResponse(success=success, message=message)

@app.get("/sessions", response_model=SessionsResponse)
async def get_sessions(db: Session = Depends(get_db)):
    """Get all active sessions"""
    try:
        sessions = db.query(InstagramSession).filter(
            InstagramSession.is_active == True
        ).all()
        
        session_list = [
            SessionInfo(
                username=session.username,
                is_active=session.is_active,
                created_at=session.created_at,
                updated_at=session.updated_at
            )
            for session in sessions
        ]
        
        return SessionsResponse(sessions=session_list)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get sessions: {str(e)}")

@app.get("/user/{username}", response_model=UserInfoResponse)
async def get_user_info(username: str):
    """Get user information for a logged-in session"""
    success, message, user_info = await instagram_manager.get_user_info(username)
    
    if not success:
        raise HTTPException(status_code=404, detail=message)
    
    return UserInfoResponse(success=success, message=message, user_info=user_info)

@app.get("/", response_model=HealthResponse)
async def root():
    """Health check endpoint"""
    stats = instagram_manager.get_session_stats()
    return HealthResponse(
        message="Instagram Hub is running",
        active_sessions=stats["active_sessions"],
        usernames=stats["usernames"]
    )

# Additional Instagram API endpoints can be added here
@app.get("/media/{username}")
async def get_user_media(username: str, count: int = 10):
    """Get user's recent media"""
    client = instagram_manager.get_client(username)
    if not client:
        raise HTTPException(status_code=404, detail="Session not found or inactive")
    
    try:
        user_id = client.user_id_from_username(username)
        medias = client.user_medias(user_id, count)
        return {
            "success": True,
            "count": len(medias),
            "medias": [media.dict() for media in medias]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get media: {str(e)}")

@app.get("/followers/{username}")
async def get_followers_count(username: str):
    """Get followers count for a user"""
    client = instagram_manager.get_client(username)
    if not client:
        raise HTTPException(status_code=404, detail="Session not found or inactive")
    
    try:
        user_info = client.account_info()
        return {
            "success": True,
            "username": user_info.username,
            "followers_count": user_info.follower_count,
            "following_count": user_info.following_count,
            "media_count": user_info.media_count
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get followers: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )