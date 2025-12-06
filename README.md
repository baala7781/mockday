# 🎯 Intervieu - AI-Powered Interview Platform

Intervieu is a comprehensive AI-powered technical interview platform that conducts realistic, adaptive interviews with real-time speech-to-text, text-to-speech, and intelligent question generation.

## 🏗️ Architecture

```
┌─────────────────┐        ┌─────────────────────┐
│    Frontend     │ ◄────► │      Backend        │
│  (React/Vite)   │  WSS   │    (FastAPI)        │
│                 │  HTTP  │                     │
└────────┬────────┘        └──────────┬──────────┘
         │                            │
         │                   ┌────────┴────────┐
         │                   │                 │
    ┌────▼────┐      ┌───────▼───┐    ┌────────▼────┐
    │ Firebase │      │  Redis    │    │ External    │
    │ Auth +   │      │  Cache    │    │ APIs        │
    │ Storage  │      │           │    │ • Deepgram  │
    └──────────┘      └───────────┘    │ • Gemini    │
                                       └─────────────┘
```

## ✨ Features

- **🎤 Real-time Speech Recognition** - Browser-direct Deepgram STT
- **🔊 Natural TTS Responses** - Deepgram voice synthesis
- **🧠 Adaptive Questions** - Gemini-powered question generation
- **📊 Comprehensive Reports** - Detailed interview analysis
- **💻 Coding Challenges** - Built-in code editor with evaluation
- **🔒 Secure Auth** - Firebase Authentication

## 🚀 Quick Start

### Prerequisites

- Python 3.12+
- Node.js 18+
- Redis (local or Upstash)
- Firebase project

### Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment
cp env.example .env
# Edit .env with your API keys

# Start server
uvicorn interview_service.main:app --host 0.0.0.0 --port 8002 --reload
```

### Frontend Setup

```bash
cd Intervieu.com/interview-skill-grove-main

# Install dependencies
npm install

# Copy and configure environment
cp env-example.txt .env.local
# Edit .env.local with your config

# Start development server
npm run dev
```

## 📁 Project Structure

```
intervieu/
├── backend/
│   ├── interview_service/    # Main interview API
│   │   ├── main.py           # FastAPI app
│   │   ├── websocket_handler.py
│   │   ├── question_generator.py
│   │   └── report_generator.py
│   ├── shared/
│   │   ├── auth/             # Firebase auth
│   │   ├── config/           # Settings
│   │   ├── db/               # Firestore/Redis
│   │   └── providers/        # Deepgram, Gemini
│   └── requirements.txt
│
├── Intervieu.com/interview-skill-grove-main/
│   ├── src/
│   │   ├── components/       # React components
│   │   ├── pages/            # Route pages
│   │   ├── hooks/            # Custom hooks
│   │   └── services/         # API services
│   └── package.json
│
└── DEPLOYMENT_STRATEGY.md
```

## 🔑 Environment Variables

### Backend

| Variable | Description | Required |
|----------|-------------|----------|
| `DEEPGRAM_API_KEYS` | Deepgram API keys (comma-separated) | ✅ |
| `GEMINI_API_KEYS` | Google Gemini API keys | ✅ |
| `FIREBASE_CREDENTIALS_PATH` | Firebase service account path | ✅ |
| `REDIS_URL` | Redis connection URL | ✅ |
| `FRONTEND_URL` | Frontend URL for CORS | ✅ |

### Frontend

| Variable | Description | Required |
|----------|-------------|----------|
| `VITE_API_URL` | Backend API URL | ✅ |
| `VITE_FIREBASE_*` | Firebase config | ✅ |
| `VITE_DEEPGRAM_API_KEY` | Deepgram key for browser STT | ✅ |

## 🚢 Deployment

See [DEPLOYMENT_STRATEGY.md](./DEPLOYMENT_STRATEGY.md) for full deployment guide.

**Quick Deploy:**
- **Frontend**: Deploy to Vercel
- **Backend**: Deploy to Railway or Render
- **Redis**: Use Upstash (serverless)

## 📝 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/interviews/start` | POST | Start new interview |
| `/api/interviews/{id}` | GET | Get interview status |
| `/api/interviews/{id}/end` | POST | End interview |
| `/api/interviews/{id}/report` | GET | Get interview report |
| `/ws/interview/{id}` | WS | WebSocket for real-time |

## 🧪 Testing

```bash
# Backend tests
cd backend
pytest tests/

# Frontend tests
cd Intervieu.com/interview-skill-grove-main
npm test
```

## 📄 License

MIT License - see LICENSE file for details.

---

Built with ❤️ by the Intervieu Team

