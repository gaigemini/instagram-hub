# Instagram Hub - Modular Project Structure

## 📁 Project Structure

```
instagram-hub/
├── main.py                 # FastAPI application and routes
├── database.py             # Database models and configuration
├── instagram_manager.py    # Instagram session management
├── models.py              # Pydantic models for API
├── requirements.txt       # Python dependencies
├── docker-compose.yml     # Docker configuration
├── Dockerfile            # Container setup
├── .env.example          # Environment variables template
└── README.md             # This file
```

## 🏗️ Architecture Overview

### 1. **database.py** - Database Layer
- SQLAlchemy models and configuration
- Database connection management
- Session storage schema

### 2. **instagram_manager.py** - Business Logic
- Instagram client management
- Session persistence and restoration
- Login/logout functionality
- Session validation and cleanup

### 3. **models.py** - Data Models
- Pydantic models for API requests/responses
- Type validation and serialization

### 4. **main.py** - API Layer
- FastAPI application and routes
- Request/response handling
- Error management
- Additional Instagram API endpoints

## 🚀 Setup Instructions

### 1. Create Project Directory
```bash
mkdir instagram-hub
cd instagram-hub
```

### 2. Create All Files
Create the following files with their respective content:
- `database.py` (Database Models and Configuration)
- `instagram_manager.py` (Instagram Session Manager) 
- `models.py` (Pydantic Models)
- `main.py` (Main FastAPI Application)
- `requirements.txt` (Requirements File)
- `docker-compose.yml` (Docker Compose Configuration)
- `Dockerfile` (Dockerfile)

### 3. Environment Setup
```bash
# Copy environment template
cp .env.example .env

# Edit with your database credentials
nano .env
```

### 4. Run with Docker
```bash
docker-compose up -d
```

### 5. Run Locally (Alternative)
```bash
# Install dependencies
pip install -r requirements.txt

# Set up database
export DATABASE_URL="postgresql://username:password@localhost:5432/instagram_hub"

# Run application
uvicorn main:app --reload
```

## 📚 Module Documentation

### InstagramManager Class

The `InstagramManager` handles all Instagram-related operations:

```python
# Usage example
manager = InstagramManager()

# Login
success, message, user_info = await manager.login("username", "password")

# Get client
client = manager.get_client("username")

# Logout
success, message = await manager.logout("username")
```

### Database Models

The `InstagramSession` model stores:
- `username`: Primary key
- `session_data`: Encrypted session information
- `created_at`: Session creation time
- `updated_at`: Last modification time
- `is_active`: Session status

### API Endpoints

- `POST /login` - Login to Instagram
- `POST /logout/{username}` - Logout from Instagram
- `GET /sessions` - List all active sessions
- `GET /user/{username}` - Get user information
- `GET /media/{username}` - Get user's recent media
- `GET /followers/{username}` - Get followers count
- `GET /` - Health check

## 🧪 Testing the API

### Login Test
```bash
curl -X POST http://localhost:8000/login \
  -H "Content-Type: application/json" \
  -d '{"username":"your_username","password":"your_password"}'
```

### Check Sessions
```bash
curl http://localhost:8000/sessions
```

### Get User Media
```bash
curl http://localhost:8000/media/your_username?count=5
```

## 🔧 Benefits of This Structure

### ✅ **Separation of Concerns**
- Database logic isolated in `database.py`
- Instagram operations in `instagram_manager.py`
- API routes in `main.py`
- Data models in `models.py`

### ✅ **Maintainability**
- Easy to modify individual components
- Clear code organization
- Better testing capabilities

### ✅ **Scalability**
- Can easily add new Instagram features
- Database operations are centralized
- Session management is isolated

### ✅ **Reusability**
- `InstagramManager` can be used in other applications
- Database models can be extended
- Clean API interfaces

## 🚀 Next Steps

You can extend this structure by adding:

1. **Services Layer**: Add `services/` directory for complex business logic
2. **Utils**: Add `utils/` for helper functions
3. **Config**: Add `config.py` for application settings
4. **Tests**: Add `tests/` directory for unit tests
5. **Middleware**: Add custom middleware for authentication
6. **Background Tasks**: Add Celery for background processing

## 🔍 File Dependencies

```
main.py
├── database.py (DB models, connection)
├── instagram_manager.py (Instagram operations)
└── models.py (Pydantic models)

instagram_manager.py
└── database.py (Session storage)
```

This modular structure makes the codebase much more maintainable and allows for easy extension of functionality!