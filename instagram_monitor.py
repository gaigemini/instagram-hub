# instagram_monitor.py
import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Set, Optional, Any
from webhook_manager import webhook_manager
from instagram_manager import InstagramManager

logger = logging.getLogger(__name__)

class InstagramMonitor:
    def __init__(self, instagram_manager: InstagramManager):
        self.instagram_manager = instagram_manager
        self.monitoring_tasks: Dict[str, asyncio.Task] = {}
        self.last_message_timestamps: Dict[str, datetime] = {}
        self.last_check_timestamps: Dict[str, datetime] = {}
        self.monitoring = False
    
    def start_monitoring(self):
        """Start monitoring all active sessions"""
        if self.monitoring:
            logger.info("Monitoring already running")
            return
            
        self.monitoring = True
        logger.info("🔍 Starting Instagram monitoring...")
        
        # Start monitoring for all active sessions
        for username in self.instagram_manager.get_all_usernames():
            self.start_user_monitoring(username)
    
    def stop_monitoring(self):
        """Stop all monitoring tasks"""
        self.monitoring = False
        logger.info("🛑 Stopping Instagram monitoring...")
        
        for username, task in self.monitoring_tasks.items():
            task.cancel()
        
        self.monitoring_tasks.clear()
    
    def start_user_monitoring(self, username: str):
        """Start monitoring for a specific user"""
        if username in self.monitoring_tasks:
            logger.info(f"Already monitoring {username}")
            return
            
        task = asyncio.create_task(self._monitor_user(username))
        self.monitoring_tasks[username] = task
        logger.info(f"🔍 Started monitoring for {username}")
    
    def stop_user_monitoring(self, username: str):
        """Stop monitoring for a specific user"""
        if username in self.monitoring_tasks:
            self.monitoring_tasks[username].cancel()
            del self.monitoring_tasks[username]
            logger.info(f"🛑 Stopped monitoring for {username}")
    
    async def _monitor_user(self, username: str):
        """Main monitoring loop for a user"""
        client = self.instagram_manager.get_client(username)
        if not client:
            logger.error(f"No client found for {username}")
            return
        
        # Initialize timestamps
        self.last_check_timestamps[username] = datetime.utcnow()
        
        logger.info(f"🔄 Monitoring loop started for {username}")
        
        while self.monitoring and username in self.instagram_manager.get_all_usernames():
            try:
                # Check for new messages (reduced frequency)
                await self._check_messages(username, client)
                
                # Wait a bit between different checks to avoid rate limiting
                await asyncio.sleep(10)
                
                # Check for new comments (less frequently)
                await self._check_comments(username, client)
                
                # Update last check timestamp
                self.last_check_timestamps[username] = datetime.utcnow()
                
                # Wait much longer before next check to avoid rate limiting
                await asyncio.sleep(120)  # Check every 2 minutes instead of 30 seconds
                
            except Exception as e:
                logger.error(f"❌ Error monitoring {username}: {str(e)}")
                await asyncio.sleep(300)  # Wait 5 minutes if error
        
        # Cleanup when loop exits
        if username in self.monitoring_tasks:
            del self.monitoring_tasks[username]
        logger.info(f"🔄 Monitoring loop ended for {username}")
    
    async def _check_messages(self, username: str, client):
        """Check for new direct messages"""
        try:
            # Get only top 3 threads instead of 20 to reduce API calls
            threads = client.direct_threads(amount=3)
            
            for thread in threads[:2]:  # Check only top 2 threads instead of 5
                try:
                    # Get only 3 messages instead of 5 to reduce API calls
                    messages = client.direct_messages(thread.id, amount=3)
                    
                    for message in messages[:2]:  # Check only 2 most recent messages
                        # Skip our own messages
                        if message.user_id == client.user_id:
                            continue
                        
                        message_time = message.timestamp.replace(tzinfo=None)
                        
                        # Check if this is a new message (increased time window)
                        last_check = self.last_check_timestamps.get(username, datetime.utcnow() - timedelta(minutes=10))
                        
                        if message_time > last_check:
                            # New message detected!
                            message_data = {
                                'id': message.id,
                                'thread_id': thread.id,
                                'text': message.text or '',
                                'timestamp': message_time.isoformat(),
                                'sender': {
                                    'username': message.user.username if message.user else 'unknown',
                                    'full_name': message.user.full_name if message.user else 'unknown'
                                }
                            }
                            
                            await webhook_manager.handle_new_message(username, message_data)
                            logger.info(f"📩 New message detected for {username} from {message_data['sender']['username']}")
                
                except Exception as e:
                    logger.error(f"Error checking messages in thread: {str(e)}")
                    continue
        
        except Exception as e:
            logger.error(f"Error checking messages for {username}: {str(e)}")
    
    async def _check_comments(self, username: str, client):
        """Check for new comments on user's posts"""
        try:
            # Get user's recent media - only check 1 post instead of 3 to reduce API calls
            user_id = client.user_id
            medias = client.user_medias(user_id, amount=1)  # Reduced from 3 to 1
            
            for media in medias:
                try:
                    # Get only 5 comments instead of 10 to reduce API calls
                    comments = client.media_comments(media.id, amount=5)
                    
                    for comment in comments[:3]:  # Check only 3 most recent comments
                        # Skip our own comments
                        if comment.user.pk == client.user_id:
                            continue
                        
                        comment_time = comment.created_at.replace(tzinfo=None)
                        last_check = self.last_check_timestamps.get(username, datetime.utcnow() - timedelta(minutes=10))
                        
                        if comment_time > last_check:
                            # New comment detected!
                            comment_data = {
                                'pk': comment.pk,
                                'media_id': media.id,
                                'text': comment.text,
                                'created_at': comment_time.isoformat(),
                                'user': {
                                    'username': comment.user.username,
                                    'full_name': comment.user.full_name
                                }
                            }
                            
                            await webhook_manager.handle_new_comment(username, comment_data)
                            logger.info(f"💬 New comment detected for {username} from {comment.user.username}")
                
                except Exception as e:
                    logger.error(f"Error checking comments on media: {str(e)}")
                    continue
        
        except Exception as e:
            logger.error(f"Error checking comments for {username}: {str(e)}")
            # If we get the 'data' KeyError, it means Instagram is rate limiting us
            if "'data'" in str(e):
                logger.warning(f"Instagram API rate limit hit for {username} - skipping comment check")
    
    async def _check_mentions(self, username: str, client):
        """Check for new mentions"""
        try:
            # Note: Instagram's API for mentions is limited
            # This is a simplified implementation
            
            # Get recent activity (if available)
            # This would need to be implemented based on available API methods
            pass
            
        except Exception as e:
            logger.error(f"Error checking mentions for {username}: {str(e)}")
    
    def get_monitoring_status(self) -> Dict[str, Any]:
        """Get current monitoring status"""
        return {
            'monitoring': self.monitoring,
            'active_monitors': list(self.monitoring_tasks.keys()),
            'last_checks': {
                username: timestamp.isoformat() 
                for username, timestamp in self.last_check_timestamps.items()
            }
        }