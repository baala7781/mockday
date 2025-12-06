# 🚀 Intervieu Deployment Strategy

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                           PRODUCTION                                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌──────────────────┐         ┌──────────────────────────────────┐ │
│  │   FRONTEND       │         │           BACKEND                  │ │
│  │   (Vercel)       │ ──────▶ │         (Railway/Render)          │ │
│  │                  │         │                                    │ │
│  │  • React/Vite    │  HTTPS  │  • FastAPI + Uvicorn              │ │
│  │  • Static files  │   API   │  • WebSocket support               │ │
│  │  • CDN edge      │ + WSS   │  • Auto-scaling                    │ │
│  │                  │         │                                    │ │
│  └──────────────────┘         └─────────────┬────────────────────┘ │
│                                              │                       │
│                    ┌─────────────────────────┼───────────────────┐ │
│                    │                         │                    │ │
│            ┌───────▼────┐  ┌────────────┐  ┌▼─────────────────┐ │ │
│            │  Firebase   │  │   Redis     │  │   External APIs   │ │ │
│            │  Firestore  │  │   (Upstash) │  │   - Deepgram      │ │ │
│            │  Auth       │  │   Cache     │  │   - Gemini        │ │ │
│            │  Storage    │  │             │  │   - OpenAI        │ │ │
│            └─────────────┘  └────────────┘  └───────────────────┘ │ │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
```

## 📦 Recommended Stack

| Component | Service | Reason |
|-----------|---------|--------|
| **Frontend** | **Vercel** | Best for React, free tier, global CDN, auto-deploys |
| **Backend** | **Railway** or **Render** | WebSocket support, auto-scaling, easy setup |
| **Database** | **Firebase Firestore** | Already using, real-time, generous free tier |
| **Cache** | **Upstash Redis** | Serverless Redis, pay-per-use, global |
| **Auth** | **Firebase Auth** | Already using, handles OAuth |

## 🔐 Secrets to Configure

### Backend Environment Variables
```env
# Firebase
FIREBASE_CREDENTIALS_PATH=/app/firebase-service-account.json
GOOGLE_APPLICATION_CREDENTIALS=/app/firebase-service-account.json
FIREBASE_STORAGE_BUCKET=intervieu-7a3bb.appspot.com

# Redis (Upstash)
REDIS_URL=redis://default:xxx@xxx.upstash.io:6379

# API Keys (comma-separated for load balancing)
DEEPGRAM_API_KEYS=key1,key2
GEMINI_API_KEYS=key1,key2
OPENAI_API_KEYS=key1

# CORS
FRONTEND_URL=https://intervieu.vercel.app
ALLOWED_ORIGINS=https://intervieu.vercel.app,https://www.intervieu.com

# Environment
ENVIRONMENT=production
```

### Frontend Environment Variables
```env
VITE_API_URL=https://api.intervieu.com
VITE_WS_URL=wss://api.intervieu.com
VITE_FIREBASE_API_KEY=xxx
VITE_FIREBASE_AUTH_DOMAIN=xxx
VITE_FIREBASE_PROJECT_ID=xxx
VITE_FIREBASE_STORAGE_BUCKET=xxx
VITE_FIREBASE_MESSAGING_SENDER_ID=xxx
VITE_FIREBASE_APP_ID=xxx
```

## 📁 Files to Clean Up

### DELETE these files/folders:
```
backend/
  ├── __pycache__/           # Python cache
  ├── intervieu/             # Local venv (don't deploy)
  ├── *.md (except README)   # Dev docs
  ├── tests/                 # Test files (or keep for CI)
  ├── scripts/               # Dev scripts
  ├── check_server.sh        # Dev scripts
  └── test_*.py              # Test files

frontend/
  ├── node_modules/          # Dependencies (auto-installed)
  ├── dist/                  # Build output (auto-generated)
  └── bun.lockb              # Unused if using npm
```

### CREATE these files:

1. **backend/Dockerfile**
2. **backend/.env.example**
3. **backend/railway.json** or **render.yaml**
4. **frontend/.env.example**
5. **frontend/vercel.json**

## 🛠️ Step-by-Step Deployment

### Phase 1: Clean & Prepare (5 min)
1. Create `.env.example` files
2. Update `.gitignore`
3. Create Dockerfile
4. Create deployment configs

### Phase 2: Backend Deployment (10 min)
1. Create Railway/Render account
2. Connect GitHub repo
3. Set environment variables
4. Deploy

### Phase 3: Redis Setup (5 min)
1. Create Upstash account
2. Create Redis database
3. Copy connection URL

### Phase 4: Frontend Deployment (5 min)
1. Create Vercel account
2. Connect GitHub repo
3. Set environment variables
4. Deploy

### Phase 5: Domain & SSL (10 min)
1. Configure custom domain
2. Update CORS settings
3. Test end-to-end

## 💰 Cost Estimate (Monthly)

| Service | Free Tier | Paid (Est.) |
|---------|-----------|-------------|
| Vercel | 100GB bandwidth | $0-20 |
| Railway | 500 hours | $5-20 |
| Upstash Redis | 10K commands/day | $0-10 |
| Firebase | Generous | $0-50 |
| **Total** | **$0-20** | **$20-100** |

## 🔄 CI/CD Pipeline (Optional)

```yaml
# .github/workflows/deploy.yml
name: Deploy
on:
  push:
    branches: [main]
jobs:
  deploy-backend:
    # Auto-deploy via Railway/Render GitHub integration
  deploy-frontend:
    # Auto-deploy via Vercel GitHub integration
```

---

**Ready to proceed? I'll now clean up the files and create deployment configs!**

