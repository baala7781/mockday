# Naming Convention Issues

## 🔍 Issues Found

### 1. **Project Name Inconsistencies**

| Current Name | Location | Should Be | Priority |
|--------------|----------|-----------|----------|
| `intervieu` | Firebase project, some code | `intervieu` (keep) | Low |
| `Intervieu.com` | Directory name | `frontend` or `web` | High |
| `interview-skill-grove-main` | Subdirectory | `src` or remove | High |
| `vite_react_shadcn_ts` | package.json name | `intervieu-frontend` | Medium |
| `interview-skill-grove` | HTML title | `Intervieu` | Medium |

### 2. **Lovable References (Template Artifacts)**

| Location | Current | Should Be | Priority |
|----------|---------|-----------|----------|
| `index.html` | "Lovable Generated Project" | "Intervieu - AI Interview Platform" | High |
| `index.html` | Lovable meta tags | Intervieu branding | High |
| `package.json` | `lovable-tagger` (devDependency) | Remove or keep (low priority) | Low |
| `index.html` | `@lovable_dev` Twitter | Remove or update | Medium |

### 3. **Virtual Environment Naming**

| Location | Current | Should Be | Priority |
|----------|---------|-----------|----------|
| `backend/intervieu/` | Virtual env directory | `backend/venv/` or `.venv` | Medium |
| `.gitignore` | Should ignore `venv/` | Already ignored | ✅ |

### 4. **Directory Structure Issues**

| Current Path | Issue | Should Be | Priority |
|--------------|-------|-----------|----------|
| `Intervieu.com/interview-skill-grove-main/` | Too nested | `frontend/` | High |
| `backend/intervieu/` | Wrong name | `backend/venv/` (or remove) | Medium |

### 5. **File Naming Issues**

| File | Issue | Priority |
|------|-------|----------|
| `backend/firebase-service-account.json` | Should be in `.gitignore` | ✅ Already ignored |
| `backend/requirements-fastapi.txt` | Duplicate/unused | Low (can remove) |

### 6. **Code References**

| File | Current | Should Be | Priority |
|------|---------|-----------|----------|
| `backend/interview_service/main.py` | "Intervieu API" | Keep | ✅ |
| Various files | Mix of "intervieu" and "interview" | Standardize to "intervieu" | Low |

---

## 📋 Recommended Changes

### High Priority (Do First)

1. **Rename frontend directory**
   ```bash
   mv Intervieu.com/interview-skill-grove-main frontend
   ```

2. **Update index.html**
   - Change title from "interview-skill-grove" to "Intervieu"
   - Remove/replace Lovable meta tags
   - Update description

3. **Update package.json**
   - Change name from "vite_react_shadcn_ts" to "intervieu-frontend"

### Medium Priority

4. **Rename virtual environment**
   ```bash
   # If keeping venv locally
   mv backend/intervieu backend/venv
   # Update .gitignore if needed
   ```

5. **Clean up unused files**
   - Remove `backend/requirements-fastapi.txt` if not used
   - Remove Lovable references from HTML

### Low Priority

6. **Standardize naming in code**
   - Ensure consistent use of "intervieu" vs "interview"
   - Update any remaining references

---

## 🎯 Standard Naming Convention

### Project Name
- **Official**: `Intervieu` (capitalized)
- **Code/URLs**: `intervieu` (lowercase)
- **Display**: "Intervieu - AI Interview Platform"

### Directory Structure
```
interview_skill_grove/
├── frontend/          # (renamed from Intervieu.com/interview-skill-grove-main)
├── backend/
│   ├── venv/          # (renamed from intervieu/)
│   └── ...
└── docs/
```

### Package Names
- Frontend: `intervieu-frontend`
- Backend: `intervieu-backend` (if needed)

---

## ✅ Checklist

- [ ] Rename `Intervieu.com/interview-skill-grove-main` → `frontend`
- [ ] Update `index.html` title and meta tags
- [ ] Update `package.json` name
- [ ] Remove Lovable references
- [ ] Rename `backend/intervieu/` → `backend/venv/` (if keeping)
- [ ] Update all import paths after directory rename
- [ ] Update README.md with new structure
- [ ] Update deployment configs (Vercel, Railway)
- [ ] Test that everything still works after changes

