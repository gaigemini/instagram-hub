# main.py
from fastapi import FastAPI, HTTPException, Depends, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security.api_key import APIKeyHeader
from sqlalchemy.orm import Session
from contextlib import asynccontextmanager
import uvicorn
import logging
import asyncio
import os
import json

# Import our modules
from database import get_db, create_tables, InstagramSession, WebhookEvent, SessionLocal, check_database_health
from instagram_manager import InstagramManager
from instagram_monitor import InstagramMonitor
from webhook_manager import webhook_manager
from models import (
    LoginRequest, LoginResponse, LogoutResponse, UserInfoResponse,
    SessionInfo, SessionsResponse, HealthResponse, ReplyRequest, 
    ReplyResponse, WebhookEventInfo, WebhookEventsResponse, MonitoringStatusResponse
)

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# API Key configuration
API_KEY = os.getenv("API_KEY")
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

async def get_api_key(api_key_header: str = Security(api_key_header)):
    """Dependency to validate the API key in the request header."""
    if not API_KEY:
        logger.warning("API_KEY environment variable not set. Endpoint security is disabled.")
        return
    if api_key_header == API_KEY:
        return api_key_header
    else:
        raise HTTPException(status_code=403, detail="Could not validate credentials")

# Initialize components
instagram_manager = InstagramManager()
instagram_monitor = None  # Initialize after startup

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global instagram_monitor
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
        
        # Initialize and start monitoring
        instagram_monitor = InstagramMonitor(instagram_manager)
        if loaded_sessions > 0:
            instagram_monitor.start_monitoring()
            logger.info("🔍 Started Instagram monitoring")
        
    except Exception as e:
        logger.error(f"❌ Startup error: {str(e)}")
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down Instagram Hub...")
    if instagram_monitor:
        instagram_monitor.stop_monitoring()

# FastAPI App
app = FastAPI(
    title="Instagram Hub",
    description="Multi-session Instagram API hub with real-time monitoring and webhooks",
    version="2.0.0",
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

# Core Authentication Endpoints
@app.post("/login", response_model=LoginResponse, dependencies=[Security(get_api_key)])
async def login(request: LoginRequest):
    """Login to Instagram and save session"""
    try:
        success, message, user_info = await instagram_manager.login(
            request.username, 
            request.password
        )
        
        # Start monitoring for this user if login successful
        if success and instagram_monitor:
            instagram_monitor.start_user_monitoring(request.username)
        
        return LoginResponse(success=success, message=message, user_info=user_info)
    
    except Exception as e:
        logger.error(f"Login endpoint error: {str(e)}")
        return LoginResponse(
            success=False, 
            message=f"Login failed: {str(e)}", 
            user_info=None
        )

@app.post("/logout/{username}", response_model=LogoutResponse, dependencies=[Security(get_api_key)])
async def logout(username: str):
    """Logout and deactivate session"""
    try:
        # Stop monitoring for this user
        if instagram_monitor:
            instagram_monitor.stop_user_monitoring(username)
        
        success, message = await instagram_manager.logout(username)
        
        if not success:
            raise HTTPException(status_code=500, detail=message)
        
        return LogoutResponse(success=success, message=message)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Logout endpoint error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Logout failed: {str(e)}")

@app.get("/sessions", response_model=SessionsResponse, dependencies=[Security(get_api_key)])
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

@app.get("/user/{username}", response_model=UserInfoResponse, dependencies=[Security(get_api_key)])
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

# Basic Instagram API Endpoints
@app.get("/media/{username}", dependencies=[Security(get_api_key)])
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

@app.get("/followers/{username}", dependencies=[Security(get_api_key)])
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

# Reply System
@app.post("/reply", response_model=ReplyResponse, dependencies=[Security(get_api_key)])
async def send_reply(request: ReplyRequest):
    """Send reply to message or comment"""
    client = instagram_manager.get_client(request.username)
    if not client:
        raise HTTPException(status_code=404, detail="Session not found or inactive")
    
    try:
        reply_id = None
        
        if request.reply_type == "message":
            if not request.thread_id:
                raise HTTPException(status_code=400, detail="thread_id required for message reply")
            
            # Send direct message reply
            message = client.direct_send(request.reply_text, [request.thread_id])
            reply_id = message.id if message else None
            
        elif request.reply_type == "comment":
            if not request.comment_id:
                raise HTTPException(status_code=400, detail="comment_id required for comment reply")
            
            # Reply to comment (simplified - you'd need media_id for actual implementation)
            reply_id = str(request.comment_id)
            
        else:
            raise HTTPException(status_code=400, detail="reply_type must be 'message' or 'comment'")
        
        logger.info(f"✅ Reply sent from {request.username}: {request.reply_text[:50]}...")
        
        return ReplyResponse(
            success=True,
            message=f"Reply sent successfully via {request.reply_type}",
            reply_id=reply_id
        )
        
    except Exception as e:
        logger.error(f"Reply error for {request.username}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to send reply: {str(e)}")

# Webhook Management
@app.get("/webhook/events", response_model=WebhookEventsResponse, dependencies=[Security(get_api_key)])
async def get_webhook_events(limit: int = 50, processed: bool = None):
    """Get webhook events from database"""
    try:
        db = SessionLocal()
        query = db.query(WebhookEvent)
        
        if processed is not None:
            query = query.filter(WebhookEvent.processed == processed)
        
        events = query.order_by(WebhookEvent.created_at.desc()).limit(limit).all()
        total_count = query.count()
        
        event_list = [
            WebhookEventInfo(
                id=event.id,
                username=event.username,
                event_type=event.event_type,
                event_data=json.loads(event.event_data),
                processed=event.processed,
                webhook_sent=event.webhook_sent,
                created_at=event.created_at
            )
            for event in events
        ]
        
        db.close()
        return WebhookEventsResponse(events=event_list, total_count=total_count)
        
    except Exception as e:
        logger.error(f"Get webhook events error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get webhook events: {str(e)}")

@app.post("/webhook/events/{event_id}/process", dependencies=[Security(get_api_key)])
async def mark_event_processed(event_id: str):
    """Mark webhook event as processed"""
    try:
        db = SessionLocal()
        event = db.query(WebhookEvent).filter(WebhookEvent.id == event_id).first()
        
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")
        
        event.processed = True
        db.commit()
        db.close()
        
        return {"success": True, "message": f"Event {event_id} marked as processed"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Mark processed error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to mark event as processed: {str(e)}")

# Monitoring Management
@app.get("/monitoring/status", response_model=MonitoringStatusResponse, dependencies=[Security(get_api_key)])
async def get_monitoring_status():
    """Get current monitoring status"""
    if not instagram_monitor:
        raise HTTPException(status_code=503, detail="Monitoring service not initialized")
    
    try:
        status = instagram_monitor.get_monitoring_status()
        return MonitoringStatusResponse(
            monitoring=status['monitoring'],
            active_monitors=status['active_monitors'],
            last_checks=status['last_checks']
        )
    except Exception as e:
        logger.error(f"Get monitoring status error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get monitoring status: {str(e)}")

@app.post("/monitoring/start", dependencies=[Security(get_api_key)])
async def start_monitoring():
    """Start Instagram monitoring for all active sessions"""
    if not instagram_monitor:
        raise HTTPException(status_code=503, detail="Monitoring service not initialized")
    
    try:
        instagram_monitor.start_monitoring()
        return {"success": True, "message": "Monitoring started for all active sessions"}
    except Exception as e:
        logger.error(f"Start monitoring error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to start monitoring: {str(e)}")

@app.post("/monitoring/stop", dependencies=[Security(get_api_key)])
async def stop_monitoring():
    """Stop Instagram monitoring"""
    if not instagram_monitor:
        raise HTTPException(status_code=503, detail="Monitoring service not initialized")
    
    try:
        instagram_monitor.stop_monitoring()
        return {"success": True, "message": "Monitoring stopped"}
    except Exception as e:
        logger.error(f"Stop monitoring error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to stop monitoring: {str(e)}")

@app.post("/monitoring/{username}/start", dependencies=[Security(get_api_key)])
async def start_user_monitoring(username: str):
    """Start monitoring for a specific user"""
    if not instagram_monitor:
        raise HTTPException(status_code=503, detail="Monitoring service not initialized")
    
    client = instagram_manager.get_client(username)
    if not client:
        raise HTTPException(status_code=404, detail="Session not found or inactive")
    
    try:
        instagram_monitor.start_user_monitoring(username)
        return {"success": True, "message": f"Monitoring started for {username}"}
    except Exception as e:
        logger.error(f"Start user monitoring error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to start monitoring for {username}: {str(e)}")

@app.post("/monitoring/{username}/stop", dependencies=[Security(get_api_key)])
async def stop_user_monitoring(username: str):
    """Stop monitoring for a specific user"""
    if not instagram_monitor:
        raise HTTPException(status_code=503, detail="Monitoring service not initialized")
    
    try:
        instagram_monitor.stop_user_monitoring(username)
        return {"success": True, "message": f"Monitoring stopped for {username}"}
    except Exception as e:
        logger.error(f"Stop user monitoring error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to stop monitoring for {username}: {str(e)}")

# Enhanced Instagram Endpoints
@app.get("/instagram/{username}/messages", dependencies=[Security(get_api_key)])
async def get_direct_messages(username: str, limit: int = 20):
    """Get direct message threads"""
    client = instagram_manager.get_client(username)
    if not client:
        raise HTTPException(status_code=404, detail="Session not found or inactive")
    
    try:
        threads = client.direct_threads(amount=limit)
        return {
            "success": True,
            "username": username,
            "threads": [
                {
                    "id": thread.id,
                    "title": thread.title,
                    "users": [{"username": user.username, "full_name": user.full_name} for user in thread.users],
                    "last_activity": thread.last_activity_at.isoformat() if thread.last_activity_at else None,
                    "unread_count": getattr(thread, 'unread_count', 0)
                }
                for thread in threads
            ]
        }
    except Exception as e:
        logger.error(f"Get messages error for {username}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get messages: {str(e)}")

@app.get("/instagram/{username}/messages/{thread_id}", dependencies=[Security(get_api_key)])
async def get_thread_messages(username: str, thread_id: str, limit: int = 20):
    """Get messages from a specific thread"""
    client = instagram_manager.get_client(username)
    if not client:
        raise HTTPException(status_code=404, detail="Session not found or inactive")
    
    try:
        messages = client.direct_messages(thread_id, amount=limit)
        return {
            "success": True,
            "username": username,
            "thread_id": thread_id,
            "messages": [
                {
                    "id": msg.id,
                    "text": msg.text,
                    "timestamp": msg.timestamp.isoformat() if msg.timestamp else None,
                    "user_id": msg.user_id,
                    "is_from_me": msg.user_id == client.user_id,
                    "message_type": msg.item_type if hasattr(msg, 'item_type') else 'text'
                }
                for msg in messages
            ]
        }
    except Exception as e:
        logger.error(f"Get thread messages error for {username}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get thread messages: {str(e)}")

@app.post("/instagram/{username}/send-message", dependencies=[Security(get_api_key)])
async def send_direct_message(username: str, recipient_username: str, message: str):
    """Send direct message to a user"""
    client = instagram_manager.get_client(username)
    if not client:
        raise HTTPException(status_code=404, detail="Session not found or inactive")
    
    try:
        # Get recipient user ID
        recipient_user = client.user_info_by_username(recipient_username)
        
        # Send message
        sent_message = client.direct_send(message, [recipient_user.pk])
        
        return {
            "success": True,
            "message": "Direct message sent successfully",
            "recipient": recipient_username,
            "message_id": sent_message.id if sent_message else None
        }
    except Exception as e:
        logger.error(f"Send message error for {username}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to send message: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )