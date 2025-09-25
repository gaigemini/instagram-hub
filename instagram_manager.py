# instagram_manager.py
from aiograpi import Client
from aiograpi.exceptions import LoginRequired, BadPassword, ChallengeRequired
import asyncio
import json
from datetime import datetime
from typing import Dict, Optional, List, Tuple
from database import InstagramSession, SessionLocal
import logging

logger = logging.getLogger(__name__)

class InstagramManager:
    def __init__(self):
        self.clients: Dict[str, Client] = {}
    
    def add_client(self, username: str, client: Client):
        """Add a client to the session manager"""
        self.clients[username] = client
        logger.info(f"Added client for {username}")
    
    def get_client(self, username: str) -> Optional[Client]:
        """Get a client by username"""
        return self.clients.get(username)
    
    def remove_client(self, username: str):
        """Remove a client from session manager"""
        if username in self.clients:
            del self.clients[username]
            logger.info(f"Removed client for {username}")
    
    def get_all_usernames(self) -> List[str]:
        """Get all active usernames"""
        return list(self.clients.keys())
    
    async def login(self, username: str, password: str) -> Tuple[bool, str, Optional[dict]]:
        """
        Login to Instagram and manage session
        Returns: (success, message, user_info)
        """
        db = SessionLocal()
        try:
            # Check if user already has an active session
            existing_session = db.query(InstagramSession).filter(
                InstagramSession.username == username,
                InstagramSession.is_active == True
            ).first()
            
            if existing_session:
                # Try to use existing session
                try:
                    client = Client()
                    session_data = json.loads(existing_session.session_data)
                    client.set_settings(session_data)
                    user_info = await asyncio.to_thread(client.account_info)
                    
                    if user_info:
                        self.add_client(username, client)
                        return True, "Using existing session", user_info.dict()
                except Exception as e:
                    logger.warning(f"Existing session invalid for {username}: {str(e)}")
                    # Existing session is invalid, mark as inactive
                    existing_session.is_active = False
                    db.commit()
            
            # Create new session
            client = Client()
            
            try:
                # Attempt login
                await asyncio.to_thread(client.login, username, password)
                user_info = await asyncio.to_thread(client.account_info)
                
                # Save session to database
                session_data = json.dumps(client.get_settings())
                
                # Update or create session record
                if existing_session:
                    existing_session.session_data = session_data
                    existing_session.is_active = True
                    existing_session.updated_at = datetime.utcnow()
                else:
                    new_session = InstagramSession(
                        username=username,
                        session_data=session_data
                    )
                    db.add(new_session)
                
                db.commit()
                
                # Add to session manager
                self.add_client(username, client)
                
                logger.info(f"Successfully logged in {username}")
                return True, "Login successful", user_info.dict() if user_info else None
                
            except BadPassword:
                logger.warning(f"Bad password for {username}")
                return False, "Invalid username or password", None
            except ChallengeRequired:
                logger.warning(f"Challenge required for {username}")
                return False, "Challenge required - please try logging in through Instagram app first", None
            except Exception as e:
                logger.error(f"Login failed for {username}: {str(e)}")
                return False, f"Login failed: {str(e)}", None
                
        except Exception as e:
            logger.error(f"Database error during login for {username}: {str(e)}")
            return False, f"Internal server error: {str(e)}", None
        finally:
            db.close()
    
    async def logout(self, username: str) -> Tuple[bool, str]:
        """
        Logout and deactivate session
        Returns: (success, message)
        """
        db = SessionLocal()
        try:
            # Remove from session manager
            client = self.get_client(username)
            if client:
                try:
                    await asyncio.to_thread(client.logout)
                except Exception as e:
                    logger.warning(f"Error during logout for {username}: {str(e)}")
                self.remove_client(username)
            
            # Deactivate in database
            session = db.query(InstagramSession).filter(
                InstagramSession.username == username
            ).first()
            
            if session:
                session.is_active = False
                session.updated_at = datetime.utcnow()
                db.commit()
            
            logger.info(f"Successfully logged out {username}")
            return True, f"Logged out {username}"
            
        except Exception as e:
            logger.error(f"Logout failed for {username}: {str(e)}")
            return False, f"Logout failed: {str(e)}"
        finally:
            db.close()
    
    async def get_user_info(self, username: str) -> Tuple[bool, str, Optional[dict]]:
        """
        Get user information for a logged-in session
        Returns: (success, message, user_info)
        """
        client = self.get_client(username)
        if not client:
            return False, "Session not found or inactive", None
        
        try:
            user_info = await asyncio.to_thread(client.account_info)
            return True, "User info retrieved", user_info.dict() if user_info else None
        except Exception as e:
            logger.error(f"Failed to get user info for {username}: {str(e)}")
            return False, f"Failed to get user info: {str(e)}", None
    
    async def load_existing_sessions(self):
        """Load existing sessions from database on startup"""
        db = SessionLocal()
        try:
            sessions = db.query(InstagramSession).filter(InstagramSession.is_active == True).all()
            loaded_count = 0
            
            for session in sessions:
                try:
                    client = Client()
                    session_data = json.loads(session.session_data)
                    client.set_settings(session_data)
                    
                    # Try to get user info to verify session is still valid
                    user_info = await asyncio.to_thread(client.account_info)
                    if user_info:
                        self.add_client(session.username, client)
                        loaded_count += 1
                        logger.info(f"✅ Restored session for {session.username}")
                    else:
                        # Mark session as inactive if it's no longer valid
                        session.is_active = False
                        db.commit()
                        logger.warning(f"❌ Session for {session.username} is no longer valid")
                except Exception as e:
                    logger.error(f"❌ Failed to restore session for {session.username}: {str(e)}")
                    # Mark session as inactive
                    session.is_active = False
                    db.commit()
            
            logger.info(f"✅ Loaded {loaded_count} active sessions")
            return loaded_count
            
        except Exception as e:
            logger.error(f"Error loading sessions: {str(e)}")
            return 0
        finally:
            db.close()
    
    def get_session_stats(self) -> dict:
        """Get session statistics"""
        return {
            "active_sessions": len(self.clients),
            "usernames": list(self.clients.keys())
        }