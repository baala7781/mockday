# Git Best Practices & Deployment Strategy

## 🎯 Overview

This guide covers Git workflow, branching strategies, and deployment best practices to prevent code loss and maintain a clean development workflow.

---

## 📋 Table of Contents

1. [Git Branching Strategy](#git-branching-strategy)
2. [Local Development Workflow](#local-development-workflow)
3. [Backup & Recovery](#backup--recovery)
4. [Deployment Workflow](#deployment-workflow)
5. [Environment Management](#environment-management)

---

## 🌿 Git Branching Strategy

### Branch Structure

```
main (production)
  ├── develop (staging/development)
  │   ├── feature/feature-name
  │   ├── bugfix/bug-name
  │   └── hotfix/hotfix-name
```

### Branch Types

1. **`main`** - Production-ready code only
   - Protected branch (requires PR)
   - Auto-deploys to production
   - Only merge from `develop` or `hotfix/*`

2. **`develop`** - Development/staging branch
   - Integration branch for features
   - Deploys to staging environment
   - Merge feature branches here

3. **`feature/*`** - New features
   - Example: `feature/add-resume-upload`
   - Created from `develop`
   - Merged back to `develop` when complete

4. **`bugfix/*`** - Bug fixes
   - Example: `bugfix/fix-report-generation`
   - Created from `develop`
   - Merged back to `develop`

5. **`hotfix/*`** - Critical production fixes
   - Example: `hotfix/fix-auth-bug`
   - Created from `main`
   - Merged to both `main` and `develop`

---

## 💻 Local Development Workflow

### Initial Setup

```bash
# Clone repository
git clone https://github.com/baala7781/mockday.git
cd mockday

# Create develop branch (if doesn't exist)
git checkout -b develop
git push -u origin develop

# Create feature branch
git checkout develop
git pull origin develop
git checkout -b feature/my-feature
```

### Daily Workflow

```bash
# 1. Start your day - sync with remote
git checkout develop
git pull origin develop

# 2. Create feature branch
git checkout -b feature/my-feature

# 3. Make changes and commit frequently
git add .
git commit -m "feat: add new feature"

# 4. Push to remote (backup)
git push -u origin feature/my-feature

# 5. When feature is complete, merge to develop
git checkout develop
git pull origin develop
git merge feature/my-feature
git push origin develop

# 6. Delete local feature branch
git branch -d feature/my-feature
```

### Commit Message Convention

```
feat: add new feature
fix: fix bug
docs: update documentation
style: formatting changes
refactor: code restructuring
test: add tests
chore: maintenance tasks
```

---

## 💾 Backup & Recovery

### Before Making Changes

**ALWAYS create a backup branch before major changes:**

```bash
# Create backup branch
git checkout -b backup/before-major-changes-$(date +%Y%m%d)

# Push backup to remote
git push -u origin backup/before-major-changes-$(date +%Y%m%d)

# Return to your working branch
git checkout develop
```

### Stashing Changes

```bash
# Save uncommitted changes
git stash save "WIP: working on feature"

# List stashes
git stash list

# Restore stashed changes
git stash pop

# Apply specific stash
git stash apply stash@{0}
```

### Recovery Scenarios

#### Lost Local Changes (Not Committed)

```bash
# Check if changes are in reflog
git reflog

# Recover from reflog
git checkout -b recovery-branch HEAD@{1}
```

#### Accidentally Deleted Branch

```bash
# Find deleted branch in reflog
git reflog | grep deleted-branch-name

# Recover branch
git checkout -b recovered-branch HEAD@{commit-hash}
```

#### Reset to Previous State

```bash
# Soft reset (keeps changes)
git reset --soft HEAD~1

# Hard reset (discards changes) - USE CAREFULLY
git reset --hard HEAD~1
```

---

## 🚀 Deployment Workflow

### Development → Staging

```bash
# 1. Ensure develop is up to date
git checkout develop
git pull origin develop

# 2. Test locally
npm run dev  # Frontend
python -m uvicorn interview_service.main:app --reload  # Backend

# 3. Push to remote (triggers staging deployment)
git push origin develop
```

### Staging → Production

```bash
# 1. Ensure develop is stable
git checkout develop
git pull origin develop

# 2. Merge develop to main
git checkout main
git pull origin main
git merge develop

# 3. Push to main (triggers production deployment)
git push origin main

# 4. Tag the release
git tag -a v1.0.0 -m "Release version 1.0.0"
git push origin v1.0.0
```

### Hotfix Workflow

```bash
# 1. Create hotfix from main
git checkout main
git pull origin main
git checkout -b hotfix/critical-bug

# 2. Fix the bug
# ... make changes ...

# 3. Commit and push
git add .
git commit -m "fix: critical bug fix"
git push -u origin hotfix/critical-bug

# 4. Merge to main
git checkout main
git merge hotfix/critical-bug
git push origin main

# 5. Merge to develop
git checkout develop
git merge hotfix/critical-bug
git push origin develop

# 6. Delete hotfix branch
git branch -d hotfix/critical-bug
git push origin --delete hotfix/critical-bug
```

---

## 🔧 Environment Management

### Local Development

Create `.env.local` (not committed to git):

```bash
# Frontend (.env.local)
VITE_API_URL=http://localhost:8002
VITE_WS_URL=ws://localhost:8002

# Backend (.env.local)
GOOGLE_APPLICATION_CREDENTIALS_JSON={...}
DEEPGRAM_API_KEYS=...
GEMINI_API_KEYS=...
```

### Staging Environment

- Branch: `develop`
- Frontend: Vercel (staging)
- Backend: Railway (staging)

### Production Environment

- Branch: `main`
- Frontend: Vercel (production)
- Backend: Railway (production)

---

## 📝 Best Practices Checklist

### Before Starting Work

- [ ] Pull latest changes from `develop`
- [ ] Create feature branch
- [ ] Create backup branch if major changes

### During Development

- [ ] Commit frequently with clear messages
- [ ] Push to remote regularly (backup)
- [ ] Test locally before pushing

### Before Merging

- [ ] Code is tested locally
- [ ] No console.logs or debug code
- [ ] Environment variables are documented
- [ ] README is updated if needed

### Before Deployment

- [ ] All tests pass
- [ ] Environment variables are set
- [ ] Database migrations are ready
- [ ] Rollback plan is prepared

---

## 🆘 Emergency Procedures

### Production Issue

1. **Create hotfix branch from main**
2. **Fix the issue**
3. **Test thoroughly**
4. **Merge to main (deploys immediately)**
5. **Merge to develop (keeps in sync)**

### Rollback Production

```bash
# Find previous working commit
git log --oneline

# Revert to previous commit
git revert HEAD
git push origin main

# OR reset to specific commit (USE CAREFULLY)
git reset --hard <commit-hash>
git push origin main --force
```

---

## 📚 Additional Resources

- [Git Flow](https://nvie.com/posts/a-successful-git-branching-model/)
- [Conventional Commits](https://www.conventionalcommits.org/)
- [GitHub Flow](https://guides.github.com/introduction/flow/)

---

## ⚠️ Important Notes

1. **NEVER force push to `main` or `develop`**
2. **ALWAYS create backup branches before major changes**
3. **TEST locally before pushing**
4. **Keep `develop` and `main` in sync**
5. **Document all environment variables**

---

## 🔐 Security Reminders

- Never commit `.env` files
- Never commit API keys or secrets
- Use environment variables for all secrets
- Rotate keys if accidentally exposed
- Review `.gitignore` regularly

