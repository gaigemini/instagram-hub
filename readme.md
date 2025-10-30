# Instagram Hub - Enhanced with Webhooks & Monitoring

## 🆕 New Features

### 🔔 **Real-time Event Monitoring**
- Automatically detects new direct messages
- Monitors comments on your posts
- Tracks mentions and tags
- Sends webhook notifications for all events

### 🔐 **API Key Authentication**
- All endpoints now protected with API key
- Configurable security via environment variables

### 💬 **Reply System**
- Send replies to direct messages
- Reply to comments on posts
- Comprehensive message management

### 📊 **Webhook Management**
- View all webhook events
- Mark events as processed
- Monitor webhook delivery status

## 📁 Updated Project Structure

```
instagram-hub/
├── main.py                 # FastAPI app with new endpoints
├── database.py             # Enhanced with webhook event storage
├── instagram_manager.py    # Session management
├── instagram_monitor.py    # NEW: Event monitoring system
├── webhook_manager.py      # NEW: Webhook handling
├── models.py              # Updated with new data models
├── requirements.txt       # Updated dependencies
├── docker-compose.yml     # Docker configuration
├── Dockerfile            # Container setup
├── .env.example          # Updated environment template
└── README.md             # This file
```

## 🚀 Setup Instructions

### 1. Install Dependencies
```bash
pip install aiohttp  # New dependency
pip install -r requirements.txt --upgrade
```

### 2. Configure Environment
```bash
# Copy and edit environment file
cp .env.example .env
nano .env
```

**Required Environment Variables:**
```bash
# Database
DATABASE_URL=postgresql://instagram_user:instagram_password@localhost:5432/instagram_hub

# API Security (IMPORTANT!)
API_KEY=your-super-secret-api-key-here

# Webhook URL (where events will be sent)
WEBHOOK_URL=https://your-webhook-endpoint.com/instagram-events
```

### 3. Start Database
```bash
docker-compose up postgres -d
```

### 4. Run Application
```bash
python3 main.py
```

## 📚 New API Endpoints

All endpoints now require API key authentication via `X-API-Key` header.

### 🔔 **Monitoring Endpoints**

#### Get Monitoring Status
```bash
curl -H "X-API-Key: your-api-key" http://localhost:8000/monitoring/status
```

#### Start/Stop Monitoring
```bash
# Start monitoring for all users
curl -X POST -H "X-API-Key: your-api-key" http://localhost:8000/monitoring/start

# Stop monitoring
curl -X POST -H "X-API-Key: your-api-key" http://localhost:8000/monitoring/stop

# Start monitoring for specific user
curl -X POST -H "X-API-Key: your-api-key" http://localhost:8000/monitoring/username/start

# Stop monitoring for specific user
curl -X POST -H "X-API-Key: your-api-key" http://localhost:8000/monitoring/username/stop
```

### 💬 **Reply Endpoints**

#### Send Reply to Direct Message
```bash
curl -X POST http://localhost:8000/reply \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "username": "your_username",
    "thread_id": "thread_id_here",
    "reply_text": "Thanks for your message!",
    "reply_type": "message"
  }'
```

#### Send Reply to Comment
```bash
curl -X POST http://localhost:8000/reply \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "username": "your_username",
    "comment_id": "comment_id_here",
    "reply_text": "Thanks for your comment!",
    "reply_type": "comment"
  }'
```

### 📊 **Webhook Management**

#### Get Webhook Events
```bash
# Get all events
curl -H "X-API-Key: your-api-key" http://localhost:8000/webhook/events

# Get unprocessed events only
curl -H "X-API-Key: your-api-key" http://localhost:8000/webhook/events?processed=false

# Limit results
curl -H "X-API-Key: your-api-key" http://localhost:8000/webhook/events?limit=10
```

#### Mark Event as Processed
```bash
curl -X POST -H "X-API-Key: your-api-key" \
  http://localhost:8000/webhook/events/EVENT_ID/process
```

### 📱 **Enhanced Instagram Endpoints**

#### Get Direct Messages
```bash
# Get message threads
curl -H "X-API-Key: your-api-key" http://localhost:8000/instagram/username/messages

# Get messages from specific thread
curl -H "X-API-Key: your-api-key" http://localhost:8000/instagram/username/messages/THREAD_ID
```

#### Send Direct Message
```bash
curl -X POST http://localhost:8000/instagram/username/send-message \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "recipient_username": "target_user",
    "message": "Hello from Instagram Hub!"
  }'
```

#### Get Recent Comments
```bash
curl -H "X-API-Key: your-api-key" http://localhost:8000/instagram/username/recent-comments
```

## 🔔 Webhook Event Format

When events are detected, webhooks are sent to your configured URL with this format:

```json
{
  "timestamp": "2025-09-25T21:53:31.886Z",
  "event_id": "uuid-here",
  "event_type": "new_message",
  "username": "your_instagram_username",
  "data": {
    "sender": "message_sender_username",
    "message": "Message content here",
    "timestamp": "2025-09-25T21:53:31.886Z",
    "thread_id": "thread_id_here",
    "message_id": "message_id_here"
  }
}
```

### Event Types:
- `new_message` - New direct message received
- `new_comment` - New comment on your post
- `mention` - You were mentioned/tagged
- `new_follower` - New follower (if detectable)

## 🔐 Security Features

### API Key Authentication
All endpoints now require authentication via the `X-API-Key` header:

```bash
curl -H "X-API-Key: your-secret-api-key" http://localhost:8000/endpoint
```

### Environment Security
- Never commit your `.env` file
- Use strong API keys (generate with: `openssl rand -base64 32`)
- Restrict webhook URL access to your servers only

## 🔄 How Monitoring Works

1. **Login Detection**: When you login, monitoring automatically starts
2. **Continuous Polling**: Every 30 seconds, checks for new events
3. **Event Detection**: Compares timestamps to find new activity
4. **Webhook Delivery**: Sends events to your configured webhook URL
5. **Database Storage**: All events stored for tracking and replay

## 🧪 Testing the New Features

### 1. Login with Monitoring
```bash
curl -X POST http://localhost:8000/login \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{"username":"test_user","password":"test_pass"}'
```

### 2. Check Monitoring Status
```bash
curl -H "X-API-Key: your-api-key" http://localhost:8000/monitoring/status
```

### 3. Send Test Message
- Send a DM to your Instagram account
- Check webhook events: `curl -H "X-API-Key: your-api-key" http://localhost:8000/webhook/events`

### 4. Send Reply
```bash
curl -X POST http://localhost:8000/reply \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{"username":"test_user","thread_id":"thread_id","reply_text":"Hello!","reply_type":"message"}'
```

## ⚡ Performance Considerations

- **Rate Limiting**: 30-second intervals prevent Instagram API limits
- **Selective Monitoring**: Only monitors last 5 message threads and 3 recent posts
- **Database Cleanup**: Consider implementing cleanup for old webhook events
- **Webhook Retries**: Failed webhooks are logged but not automatically retried

## 🔧 Troubleshooting

### Common Issues:

1. **"API_KEY environment variable not set"**
   - Add `API_KEY=your-key-here` to `.env` file

2. **"Webhook URL not configured"**
   - Add `WEBHOOK_URL=https://your-endpoint.com` to `.env` file

3. **"Monitoring service not initialized"**
   - Restart the application, monitoring starts after successful login

4. **Events not detected**
   - Check Instagram session is active
   - Verify monitoring is running: `/monitoring/status`
   - Check Instagram rate limits

## 🚀 Next Steps

1. **Implement webhook retries** for failed deliveries
2. **Add media upload support** for replying with images
3. **Create dashboard** for managing webhooks and events
4. **Add filtering options** for specific event types
5. **Implement rate limiting** on API endpoints
6. **Add batch operations** for multiple replies

---

Your Instagram Hub is now a complete social media management system with real-time monitoring and webhook integrations! 🎉