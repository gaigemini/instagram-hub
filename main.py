# main.py
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from contextlib import asynccontextmanager
import uvicorn
import logging
import asyncio

# Import our modules
from database import get_db, create_tables, InstagramSession, SessionLocal, check_database_health
from instagram_manager import InstagramManager
from models import (
    LoginRequest, LoginResponse, LogoutResponse, UserInfoResponse,
    SessionInfo, SessionsResponse, HealthResponse
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Instagram Manager
instagram_manager = InstagramManager()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("🚀 Starting Instagram Hub...")
    
    # Check database health
    if not check_database_health():
        logger.error("❌ Database health check failed!")
    else:
        logger.info("✅ Database health check passed")
    
    try:
        create_tables()
        loaded_sessions = await instagram_manager.load_existing_sessions()
        logger.info(f"✅ Loaded {loaded_sessions} active sessions")
    except Exception as e:
        logger.error(f"❌ Startup error: {str(e)}")
    
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
    try:
        success, message, user_info = await instagram_manager.login(
            request.username, 
            request.password
        )
        
        return LoginResponse(success=success, message=message, user_info=user_info)
    
    except Exception as e:
        logger.error(f"Login endpoint error: {str(e)}")
        return LoginResponse(
            success=False, 
            message=f"Login failed: {str(e)}", 
            user_info=None
        )

@app.post("/logout/{username}", response_model=LogoutResponse)
async def logout(username: str):
    """Logout and deactivate session"""
    try:
        success, message = await instagram_manager.logout(username)
        
        if not success:
            raise HTTPException(status_code=500, detail=message)
        
        return LogoutResponse(success=success, message=message)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Logout endpoint error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Logout failed: {str(e)}")

@app.get("/sessions", response_model=SessionsResponse)
async def get_sessions():
    """Get all active sessions"""
    try:
        # Get sessions from memory (more reliable than DB during connection issues)
        active_usernames = instagram_manager.get_all_usernames()
        
        # Try to get additional info from database
        session_list = []
        try:
            db = SessionLocal()
            sessions = db.query(InstagramSession).filter(
                InstagramSession.username.in_(active_usernames),
                InstagramSession.is_active == True
            ).all()
            db.close()
            
            session_list = [
                SessionInfo(
                    username=session.username,
                    is_active=session.is_active,
                    created_at=session.created_at,
                    updated_at=session.updated_at
                )
                for session in sessions
            ]
        except Exception as db_error:
            logger.warning(f"Database error in get_sessions: {str(db_error)}")
            # Fallback to memory-only data
            from datetime import datetime
            session_list = [
                SessionInfo(
                    username=username,
                    is_active=True,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                for username in active_usernames
            ]
        
        return SessionsResponse(sessions=session_list)
    
    except Exception as e:
        logger.error(f"Get sessions error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get sessions: {str(e)}")

@app.get("/user/{username}", response_model=UserInfoResponse)
async def get_user_info(username: str):
    """Get user information for a logged-in session"""
    try:
        success, message, user_info = await instagram_manager.get_user_info(username)
        
        if not success:
            raise HTTPException(status_code=404, detail=message)
        
        return UserInfoResponse(success=success, message=message, user_info=user_info)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get user info error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get user info: {str(e)}")

@app.get("/", response_model=HealthResponse)
async def root():
    """Health check endpoint"""
    try:
        stats = instagram_manager.get_session_stats()
        db_healthy = check_database_health()
        
        message = "Instagram Hub is running"
        if not db_healthy:
            message += " (Database connection issues detected)"
        
        return HealthResponse(
            message=message,
            active_sessions=stats["active_sessions"],
            usernames=stats["usernames"]
        )
    except Exception as e:
        logger.error(f"Health check error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")

# Additional Instagram API endpoints
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
        logger.error(f"Get media error for {username}: {str(e)}")
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
        logger.error(f"Get followers error for {username}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get followers: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )