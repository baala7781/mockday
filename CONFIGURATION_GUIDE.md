# Configuration Guide - Google Cloud, Vercel, Railway

## 📋 Overview

This document details all configurations across Google Cloud (Firebase), Vercel (Frontend), and Railway (Backend).

---

## 🔥 Google Cloud / Firebase Configuration

### Project Details

- **Project ID**: `intervieu-7a3bb` (Firebase project - legacy name, keep as is)
- **Project Name**: MockDay (display name)
- **Domain**: mockday.io
- **Firebase Console**: https://console.firebase.google.com/project/intervieu-7a3bb

### Service Account

- **Service Account Email**: `firebase-adminsdk-fbsvc@intervieu-7a3bb.iam.gserviceaccount.com`
- **Purpose**: Backend authentication and Firestore access

### Required IAM Roles

The service account needs these roles:

1. **Cloud Datastore User** (for Firestore access)
2. **Firebase Admin SDK Administrator Service Agent** (if available)

### How to Grant Permissions

1. Go to: https://console.cloud.google.com/iam-admin/iam?project=intervieu-7a3bb
2. Find: `firebase-adminsdk-fbsvc@intervieu-7a3bb.iam.gserviceaccount.com`
3. Click Edit (pencil icon)
4. Click "ADD ANOTHER ROLE"
5. Add: **Cloud Datastore User**
6. Click "SAVE"

### Service Account JSON

**Location**: Railway environment variable `GOOGLE_APPLICATION_CREDENTIALS_JSON`

**Format**: Single-line JSON (no line breaks)

**How to get**:
1. Go to: https://console.firebase.google.com/project/intervieu-7a3bb/settings/serviceaccounts/adminsdk
2. Click "Generate new private key"
3. Download JSON file
4. Convert to single line: `cat firebase-key.json | jq -c`
5. Paste into Railway variable

### Firestore Database

- **Database ID**: `(default)`
- **Location**: `us-central1` (or your selected region)
- **Mode**: Native mode (Firestore)

### Storage Bucket

- **Bucket Name**: `intervieu-7a3bb.appspot.com`
- **Purpose**: Resume file storage

---

## ⚡ Vercel Configuration (Frontend)

### Project Details

- **Project Name**: `mockday` or `interview-skill-grove`
- **Vercel Dashboard**: https://vercel.com/dashboard
- **Production URL**: `https://mockdayai.vercel.app` (or `https://mockday.io` if custom domain configured)

### Environment Variables

#### Required Variables

| Variable | Value | Description |
|----------|-------|-------------|
| `VITE_API_URL` | `mockday-production.up.railway.app` | Backend API URL (without https://) |
| `VITE_WS_URL` | (optional) | WebSocket URL (auto-constructed from API URL) |

#### How to Set

1. Go to: Vercel Dashboard → Your Project → Settings → Environment Variables
2. Add each variable
3. Select environment: **Production**, **Preview**, **Development**
4. Click "Save"

### Build Settings

- **Framework Preset**: Vite
- **Build Command**: `npm run build` (or `bun run build`)
- **Output Directory**: `dist`
- **Install Command**: `npm install` (or `bun install`)

### Deployment

- **Branch**: `main` (production), `develop` (preview)
- **Auto-deploy**: Enabled
- **Build**: Automatic on push

---

## 🚂 Railway Configuration (Backend)

### Project Details

- **Project Name**: `mockday-production`
- **Railway Dashboard**: https://railway.app/dashboard
- **Production URL**: `https://mockday-production.up.railway.app`

### Service Configuration

- **Root Directory**: `backend`
- **Dockerfile Path**: `Dockerfile`
- **Port**: `8080` (auto-detected from `$PORT`)

### Environment Variables

#### Required Variables

| Variable | Value | Description |
|----------|-------|-------------|
| `GOOGLE_APPLICATION_CREDENTIALS_JSON` | `{...}` | Firebase service account JSON (single line) |
| `ALLOWED_ORIGINS` | `https://mockdayai.vercel.app,http://localhost:5174` | CORS allowed origins (comma-separated) |
| `DEEPGRAM_API_KEYS` | `key1,key2,...` | Deepgram API keys (comma-separated) |
| `GEMINI_API_KEYS` | `key1,key2,...` | Google Gemini API keys (comma-separated) |
| `FIREBASE_STORAGE_BUCKET` | `intervieu-7a3bb.appspot.com` | Firebase storage bucket |
| `REDIS_URL` | (optional) | Redis connection URL (if using Redis) |
| `ENVIRONMENT` | `production` | Environment name |

#### Optional Variables

| Variable | Value | Description |
|----------|-------|-------------|
| `GOOGLE_APPLICATION_CREDENTIALS` | (empty or file path) | **DO NOT SET TO JSON** - only file path |
| `FIREBASE_CREDENTIALS_PATH` | `/app/firebase-key.json` | File path (if using file instead of JSON) |
| `API_GATEWAY_PORT` | `8080` | Port for Railway (usually auto-detected) |

### How to Set Variables

1. Go to: Railway Dashboard → Your Project → Variables
2. Click "New Variable"
3. Enter name and value
4. Click "Add"

### Critical Notes

⚠️ **DO NOT SET `GOOGLE_APPLICATION_CREDENTIALS` TO JSON STRING**
- It should be a **file path** OR **empty**
- Use `GOOGLE_APPLICATION_CREDENTIALS_JSON` for JSON content

### Deployment

- **Branch**: `main` (auto-deploys)
- **Build**: Docker build from `backend/Dockerfile`
- **Health Check**: `/health` endpoint

---

## 🔐 Security Checklist

### Google Cloud / Firebase

- [ ] Service account has minimal required permissions
- [ ] Service account JSON is stored securely (Railway variables)
- [ ] Old service account keys are rotated if exposed
- [ ] Firestore security rules are configured
- [ ] Storage bucket has proper access controls

### Vercel

- [ ] Environment variables are set correctly
- [ ] No API keys in frontend code
- [ ] CORS is configured properly
- [ ] Production builds are optimized

### Railway

- [ ] All secrets are in environment variables
- [ ] `GOOGLE_APPLICATION_CREDENTIALS_JSON` is single-line JSON
- [ ] `GOOGLE_APPLICATION_CREDENTIALS` is NOT set to JSON
- [ ] API keys are rotated regularly
- [ ] Health check endpoint is working

---

## 🔄 Environment Sync

### Development → Staging → Production

1. **Development** (Local)
   - Frontend: `http://localhost:5174`
   - Backend: `http://localhost:8002`
   - Uses `.env.local` files

2. **Staging** (Vercel Preview + Railway)
   - Branch: `develop`
   - Frontend: Vercel preview URL
   - Backend: Railway staging service
   - Uses staging environment variables

3. **Production** (Vercel + Railway)
   - Branch: `main`
   - Frontend: `https://mockdayai.vercel.app`
   - Backend: `https://mockday-production.up.railway.app`
   - Uses production environment variables

---

## 🐛 Troubleshooting

### Firebase Authentication Errors

**Error**: `403 Request had insufficient authentication scopes`

**Fix**:
1. Check service account has "Cloud Datastore User" role
2. Verify `GOOGLE_APPLICATION_CREDENTIALS_JSON` is set correctly
3. Ensure JSON is valid and single-line

### CORS Errors

**Error**: `CORS policy: No 'Access-Control-Allow-Origin' header`

**Fix**:
1. Check `ALLOWED_ORIGINS` in Railway includes frontend URL
2. Format: `https://mockdayai.vercel.app,http://localhost:5174` (comma-separated)
3. Redeploy Railway after changing

### API URL Issues

**Error**: `404 Not Found` or HTML response

**Fix**:
1. Check `VITE_API_URL` in Vercel is correct
2. Should be: `mockday-production.up.railway.app` (no https://)
3. Frontend code adds `/api` automatically

### Build Failures

**Railway Build Fails**:
- Check Dockerfile exists in `backend/` directory
- Verify `requirements.txt` is present
- Check build logs for specific errors

**Vercel Build Fails**:
- Check `package.json` has correct build script
- Verify all dependencies are in `package.json`
- Check build logs for errors

---

## 📝 Quick Reference

### Firebase Service Account JSON Format

```json
{"type":"service_account","project_id":"intervieu-7a3bb","private_key_id":"...","private_key":"-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n","client_email":"firebase-adminsdk-fbsvc@intervieu-7a3bb.iam.gserviceaccount.com",...}
```

**Must be single line!**

### Railway CORS Format

```
https://mockdayai.vercel.app,http://localhost:5174
```

**Comma-separated, no spaces**

### Vercel API URL Format

```
mockday-production.up.railway.app
```

**No https://, no trailing slash**

---

## 🔄 Update Checklist

When updating configurations:

1. [ ] Update this document
2. [ ] Update environment variables in respective platforms
3. [ ] Test in staging first
4. [ ] Deploy to production
5. [ ] Verify health checks pass
6. [ ] Monitor logs for errors

---

## 📞 Support

- **Firebase**: https://console.firebase.google.com/project/intervieu-7a3bb
- **Vercel**: https://vercel.com/dashboard
- **Railway**: https://railway.app/dashboard

---

**Last Updated**: December 2024

