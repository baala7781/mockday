# Interview Service Backend

FastAPI-based interview service with WebSocket support for real-time communication, speech-to-text, text-to-speech, and adaptive interview flow.

## Quick Start

### Prerequisites

- Python 3.12+
- Redis (for caching and session management)
- Firebase credentials (`firebase-service-account.json`)
- API Keys: Deepgram, Gemini (OpenAI optional)

### Start the Server

```bash
cd backend
./start_server.sh
```

Or manually:
```bash
cd backend
source venv/bin/activate  # or source intervieu/bin/activate for legacy
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
uvicorn interview_service.main:app --host 0.0.0.0 --port 8002 --reload
```

### Verify Server is Running

```bash
# Health check
curl http://localhost:8002/health

# API docs
open http://localhost:8002/docs
```

## Server Endpoints

- **API Base:** http://localhost:8002
- **API Docs:** http://localhost:8002/docs
- **Health Check:** http://localhost:8002/health
- **WebSocket:** ws://localhost:8002/ws/interview/{interview_id}

## Available Scripts

- `./start_server.sh` - Start server (recommended)
- `./start_interview_service.sh` - Start server (alternative)
- `./run_interview_service.sh` - Start server (alternative)
- `./stop_server.sh` - Stop server
- `./check_server.sh` - Check if server is running

## Project Structure

```
backend/
├── interview_service/    # Interview service (FastAPI)
│   ├── main.py          # FastAPI app with WebSocket
│   ├── models.py        # Pydantic models
│   ├── interview_state.py  # Interview state management
│   ├── phased_flow.py   # Phased interview flow
│   ├── question_generator.py  # LLM question generation
│   ├── answer_evaluator.py   # Answer evaluation
│   └── websocket_handler.py  # WebSocket message handling
├── shared/              # Shared utilities
│   ├── auth/           # Firebase authentication
│   ├── db/             # Database clients (Firestore, Redis)
│   ├── providers/      # Provider clients (Deepgram, Gemini)
│   └── config/         # Configuration
└── docs/               # Documentation
```

## Environment Variables

Create a `.env` file in the `backend/` directory:

```env
# Firebase
FIREBASE_CREDENTIALS_PATH=./firebase-service-account.json
GOOGLE_APPLICATION_CREDENTIALS=

# Database
REDIS_URL=redis://localhost:6379/0

# Provider API Keys (comma-separated for multiple accounts)
DEEPGRAM_API_KEYS=key1,key2,key3
GEMINI_API_KEYS=key1,key2,key3
OPENAI_API_KEYS=key1,key2,key3

# CORS
FRONTEND_URL=http://localhost:5174
```

## Dependencies

```bash
cd backend
source venv/bin/activate  # or source intervieu/bin/activate for legacy
pip install -r requirements.txt
```

## API Endpoints

### Profile Endpoints

- `GET /api/profile` - Get user profile
- `PUT /api/profile` - Update user profile

### Resume Endpoints

- `GET /api/resumes` - List user resumes
- `POST /api/resumes` - Add resume metadata

### Interview Endpoints

- `POST /api/interviews/start` - Start a new interview
- `GET /api/interviews/{interview_id}` - Get interview status
- `GET /api/interviews` - Get all interview reports
- `POST /api/interviews/{interview_id}/answer` - Submit an answer
- `WS /ws/interview/{interview_id}` - WebSocket connection for real-time communication

## WebSocket Protocol

### Client → Server Messages

- `audio_chunk` - Send audio chunk for transcription
- `answer` - Submit answer to current question
- `ping` - Heartbeat
- `get_current_question` - Request current question (for reconnection)

### Server → Client Messages

- `connected` - Connection established
- `question` - New question received
- `transcript` - Audio transcription result
- `evaluation` - Answer evaluation
- `audio` - Text-to-speech audio (base64)
- `resume` - Interview state resumed
- `completed` - Interview completed
- `error` - Error message
- `pong` - Heartbeat response

## Architecture

### Interview Flow

1. **Start Interview** - User starts interview with role and resume
2. **Resume Analysis** - Extract skills and projects from resume
3. **Skill Weighting** - Calculate skill relevance based on role
4. **Phased Questions** - Generate questions in phases:
   - Introduction
   - Projects
   - Standout Skills
   - Role Skills
5. **Answer Evaluation** - Evaluate answers and adjust difficulty
6. **Adaptive Flow** - Adjust questions based on performance
7. **Completion** - Generate final report

### WebSocket Connection

- WebSocket connections are managed per interview
- Only one connection per interview is allowed (new connections close old ones)
- Connection automatically resumes interview state
- Questions are tracked by `question_id` to prevent duplicates on reconnect
- Connection stays open until client disconnects or interview completes

### State Management

- Interview state is stored in Redis (fast access)
- Interview state is also saved to Firestore (persistence)
- State includes: current question, answers, progress, phase, difficulty

## Migration Notes

### Flask to FastAPI Migration

All Flask endpoints have been migrated to FastAPI:
- `/api/profile` - ✅ Migrated
- `/api/resumes` - ✅ Migrated
- `/api/interviews` - ✅ Migrated

**Note:** Flask-related files have been deprecated and removed. All authentication now uses `shared/auth/firebase_auth.py` with FastAPI dependencies.

## Common Issues

### ❌ Error: `ModuleNotFoundError: No module named 'shared'`

**Solution:** Make sure you're running from the `backend` directory, not `backend/interview_service`

```bash
cd backend
./start_server.sh
```

### ❌ Error: Port 8002 already in use

**Solution:** 
```bash
lsof -ti:8002 | xargs kill -9
# Or use the stop script
./stop_server.sh
```

### ❌ Error: Redis connection failed

**Solution:** Make sure Redis is running:
```bash
# macOS (using Homebrew)
brew services start redis

# Or run directly
redis-server
```

### ❌ Error: Firebase credentials not found

**Solution:** Make sure `firebase-service-account.json` exists in the `backend/` directory.

### ❌ WebSocket Connection Issues

**Symptoms:**
- WebSocket closes immediately with code 1000
- Connection established but then disconnects
- Duplicate questions on reconnect

**Solutions:**
1. Check if server is running on port 8002
2. Check if interview exists in Redis/Firestore
3. Check browser console for WebSocket errors
4. Verify WebSocket URL: `ws://localhost:8002/ws/interview/{interview_id}`
5. Check server logs for errors
6. Ensure only one connection per interview (close other tabs/windows)

**Debugging:**
- Check server logs for WebSocket connection/disconnection messages
- Verify interview state is loaded correctly
- Check if TTS audio generation is causing delays
- Ensure WebSocket handler is not throwing errors

### ❌ Interview Not Starting

**Solutions:**
1. Check if Redis is running
2. Check if Firebase credentials are valid
3. Check if API keys (Gemini, Deepgram) are set
4. Check server logs for errors
5. Verify resume data is parsed correctly

### ❌ Questions Not Generating

**Solutions:**
1. Check if Gemini API key is valid
2. Check if resume data is parsed correctly
3. Check server logs for LLM errors
4. Verify skill weighting is working
5. Check if role mapping is correct

## Development

### Running Tests

```bash
cd backend
source venv/bin/activate  # or source intervieu/bin/activate for legacy
python -m pytest tests/
```

### Code Style

```bash
# Format code
black backend/

# Lint code
flake8 backend/
```

## Troubleshooting

### WebSocket Connection Issues

1. **Connection closes immediately:**
   - Check server logs for errors
   - Verify interview state exists
   - Check if TTS audio generation is failing
   - Ensure WebSocket handler is not throwing exceptions

2. **Duplicate questions on reconnect:**
   - This is fixed by tracking `question_id` per interview
   - Check if `sent_question_ids` is being cleared incorrectly
   - Verify question_id is unique for each question

3. **Connection not staying open:**
   - Check if client is sending ping messages
   - Verify server is handling ping/pong correctly
   - Check for errors in WebSocket message handler

### Interview Flow Issues

1. **Resume parsing fails:**
   - Check if resume text is provided
   - Verify Gemini API key is valid
   - Check server logs for LLM errors
   - Ensure resume format is supported

2. **Skill weighting issues:**
   - Check if role mapping is correct
   - Verify resume skills are extracted correctly
   - Check if role skills are defined in question pool

3. **Question generation fails:**
   - Check if Gemini API key is valid
   - Verify resume data is available
   - Check server logs for LLM errors
   - Ensure question pool has questions for the role

## License

MIT
