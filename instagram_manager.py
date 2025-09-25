# instagram_manager.py
from instagrapi import Client
from instagrapi.exceptions import LoginRequired, BadPassword, ChallengeRequired, ClientError
import asyncio
import json
from datetime import datetime
from typing import Dict, Optional, List, Tuple
from database import InstagramSession, SessionLocal
import logging
import time

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
    
    def _get_db_session(self):
        """Get database session with retry logic"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                return SessionLocal()
            except Exception as e:
                logger.warning(f"Database connection attempt {attempt + 1} failed: {str(e)}")
                if attempt == max_retries - 1:
                    raise
                time.sleep(1)
    
    async def login(self, username: str, password: str) -> Tuple[bool, str, Optional[dict]]:
        """
        Login to Instagram and manage session
        Returns: (success, message, user_info)
        """
        db = None
        try:
            db = self._get_db_session()
            
            # Check if user already has an active session
            existing_session = None
            try:
                existing_session = db.query(InstagramSession).filter(
                    InstagramSession.username == username,
                    InstagramSession.is_active == True
                ).first()
            except Exception as db_error:
                logger.warning(f"Database query failed for {username}, proceeding with fresh login: {str(db_error)}")
            
            if existing_session:
                # Try to use existing session
                try:
                    client = Client()
                    session_data = json.loads(existing_session.session_data)
                    client.set_settings(session_data)
                    
                    # Test the session by getting account info
                    user_info = client.account_info()
                    
                    if user_info:
                        self.add_client(username, client)
                        return True, "Using existing session", user_info.dict()
                except Exception as e:
                    logger.warning(f"Existing session invalid for {username}: {str(e)}")
                    # Existing session is invalid, mark as inactive
                    try:
                        existing_session.is_active = False
                        db.commit()
                    except Exception:
                        pass  # Continue with fresh login even if DB update fails
            
            # Create new session
            client = Client()
            
            # Set some basic settings to avoid issues
            client.delay_range = [1, 3]
            
            try:
                # Attempt login (synchronous call)
                client.login(username, password)
                user_info = client.account_info()
                
                # Save session to database
                session_data = json.dumps(client.get_settings())
                
                # Update or create session record
                try:
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
                except Exception as db_error:
                    logger.warning(f"Failed to save session to database: {str(db_error)}")
                    # Continue anyway - the login was successful
                
                # Add to session manager
                self.add_client(username, client)
                
                logger.info(f"Successfully logged in {username}")
                return True, "Login successful", user_info.dict() if user_info else None
                
            except BadPassword:
                logger.warning(f"Bad password for {username}")
                return False, "Invalid username or password", None
            except ChallengeRequired as e:
                logger.warning(f"Challenge required for {username}: {str(e)}")
                return False, "Challenge required - please try logging in through Instagram app first", None
            except ClientError as e:
                logger.warning(f"Client error for {username}: {str(e)}")
                return False, f"Instagram API error: {str(e)}", None
            except Exception as e:
                logger.error(f"Login failed for {username}: {str(e)}")
                return False, f"Login failed: {str(e)}", None
                
        except Exception as e:
            logger.error(f"Unexpected error during login for {username}: {str(e)}")
            return False, f"Internal server error: {str(e)}", None
        finally:
            if db:
                try:
                    db.close()
                except Exception:
                    pass
    
    async def logout(self, username: str) -> Tuple[bool, str]:
        """
        Logout and deactivate session
        Returns: (success, message)
        """
        db = None
        try:
            # Remove from session manager
            client = self.get_client(username)
            if client:
                try:
                    client.logout()
                except Exception as e:
                    logger.warning(f"Error during logout for {username}: {str(e)}")
                self.remove_client(username)
            
            # Deactivate in database
            try:
                db = self._get_db_session()
                session = db.query(InstagramSession).filter(
                    InstagramSession.username == username
                ).first()
                
                if session:
                    session.is_active = False
                    session.updated_at = datetime.utcnow()
                    db.commit()
            except Exception as db_error:
                logger.warning(f"Failed to update database during logout: {str(db_error)}")
                # Continue anyway - the memory session was cleared
            
            logger.info(f"Successfully logged out {username}")
            return True, f"Logged out {username}"
            
        except Exception as e:
            logger.error(f"Logout failed for {username}: {str(e)}")
            return False, f"Logout failed: {str(e)}"
        finally:
            if db:
                try:
                    db.close()
                except Exception:
                    pass
    
    async def get_user_info(self, username: str) -> Tuple[bool, str, Optional[dict]]:
        """
        Get user information for a logged-in session
        Returns: (success, message, user_info)
        """
        client = self.get_client(username)
        if not client:
            return False, "Session not found or inactive", None
        
        try:
            user_info = client.account_info()
            return True, "User info retrieved", user_info.dict() if user_info else None
        except Exception as e:
            logger.error(f"Failed to get user info for {username}: {str(e)}")
            return False, f"Failed to get user info: {str(e)}", None
    
    async def load_existing_sessions(self):
        """Load existing sessions from database on startup"""
        db = None
        try:
            db = self._get_db_session()
            sessions = db.query(InstagramSession).filter(InstagramSession.is_active == True).all()
            loaded_count = 0
            
            for session in sessions:
                try:
                    client = Client()
                    session_data = json.loads(session.session_data)
                    client.set_settings(session_data)
                    
                    # Try to get user info to verify session is still valid
                    user_info = client.account_info()
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
                    try:
                        session.is_active = False
                        db.commit()
                    except Exception:
                        pass  # Continue with other sessions
            
            logger.info(f"✅ Loaded {loaded_count} active sessions")
            return loaded_count
            
        except Exception as e:
            logger.error(f"Error loading sessions: {str(e)}")
            return 0
        finally:
            if db:
                try:
                    db.close()
                except Exception:
                    pass
    
    def get_session_stats(self) -> dict:
        """Get session statistics"""
        return {
            "active_sessions": len(self.clients),
            "usernames": list(self.clients.keys())
        }