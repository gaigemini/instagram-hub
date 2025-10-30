# webhook_manager.py
import aiohttp
import asyncio
import json
import uuid
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from database import WebhookEvent, SessionLocal, WEBHOOK_URL

logger = logging.getLogger(__name__)

class WebhookManager:
    def __init__(self):
        self.webhook_url = WEBHOOK_URL
        
    async def send_webhook(self, event_data: Dict[str, Any]) -> bool:
        """Send webhook notification"""
        if not self.webhook_url:
            logger.warning("No webhook URL configured")
            return False
            
        try:
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                headers = {
                    'Content-Type': 'application/json',
                    'User-Agent': 'Instagram-Hub-Webhook/1.0'
                }
                
                payload = {
                    'timestamp': datetime.utcnow().isoformat(),
                    'event_id': event_data.get('event_id', str(uuid.uuid4())),
                    'event_type': event_data.get('event_type'),
                    'username': event_data.get('username'),
                    'data': event_data.get('data', {})
                }
                
                async with session.post(
                    self.webhook_url, 
                    json=payload, 
                    headers=headers
                ) as response:
                    if response.status == 200:
                        logger.info(f"✅ Webhook sent successfully for {event_data.get('event_type')}")
                        return True
                    else:
                        logger.warning(f"❌ Webhook failed with status {response.status}")
                        return False
                        
        except asyncio.TimeoutError:
            logger.error("❌ Webhook timeout")
            return False
        except Exception as e:
            logger.error(f"❌ Webhook error: {str(e)}")
            return False
    
    async def log_event(self, username: str, event_type: str, event_data: Dict[str, Any]) -> str:
        """Log event to database and send webhook"""
        event_id = str(uuid.uuid4())
        
        try:
            db = SessionLocal()
            
            # Create webhook event record
            webhook_event = WebhookEvent(
                id=event_id,
                username=username,
                event_type=event_type,
                event_data=json.dumps(event_data),
                processed=False,
                webhook_sent=False
            )
            
            db.add(webhook_event)
            db.commit()
            
            # Prepare webhook payload
            webhook_payload = {
                'event_id': event_id,
                'username': username,
                'event_type': event_type,
                'data': event_data
            }
            
            # Send webhook
            webhook_success = await self.send_webhook(webhook_payload)
            
            # Update webhook status
            webhook_event.webhook_sent = webhook_success
            webhook_event.webhook_response = "Success" if webhook_success else "Failed"
            db.commit()
            
            logger.info(f"📝 Logged {event_type} event for {username}")
            return event_id
            
        except Exception as e:
            logger.error(f"❌ Failed to log event: {str(e)}")
            return event_id
        finally:
            db.close()
    
    async def handle_new_message(self, username: str, message_data: Dict[str, Any]):
        """Handle new direct message"""
        await self.log_event(username, "new_message", {
            'sender': message_data.get('sender', {}).get('username'),
            'message': message_data.get('text', ''),
            'timestamp': message_data.get('timestamp'),
            'thread_id': message_data.get('thread_id'),
            'message_id': message_data.get('id')
        })
    
    async def handle_new_comment(self, username: str, comment_data: Dict[str, Any]):
        """Handle new comment on post"""
        await self.log_event(username, "new_comment", {
            'commenter': comment_data.get('user', {}).get('username'),
            'comment': comment_data.get('text', ''),
            'timestamp': comment_data.get('created_at'),
            'post_id': comment_data.get('media_id'),
            'comment_id': comment_data.get('pk')
        })
    
    async def handle_mention(self, username: str, mention_data: Dict[str, Any]):
        """Handle user mention"""
        await self.log_event(username, "mention", {
            'mentioned_by': mention_data.get('user', {}).get('username'),
            'content': mention_data.get('text', ''),
            'timestamp': mention_data.get('created_at'),
            'mention_type': mention_data.get('type'),  # story, post, comment
            'content_id': mention_data.get('pk')
        })
    
    async def handle_follower(self, username: str, follower_data: Dict[str, Any]):
        """Handle new follower"""
        await self.log_event(username, "new_follower", {
            'follower': follower_data.get('username'),
            'timestamp': datetime.utcnow().isoformat(),
            'follower_count': follower_data.get('follower_count'),
            'profile_pic': follower_data.get('profile_pic_url')
        })

# Global webhook manager instance
webhook_manager = WebhookManager()