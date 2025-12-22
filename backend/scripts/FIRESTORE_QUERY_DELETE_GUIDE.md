# Firestore Query & Delete User Interviews Guide

This guide explains how to query and delete interviews for a specific user in Firestore.

## Important Note

**Interviews are stored in Firestore (database), NOT Firebase Storage (file storage).** 
- Firestore = NoSQL database (documents/collections)
- Firebase Storage = File storage (images, PDFs, etc.)

## Methods to Query & Delete

### Method 1: Python Script (Recommended for Bulk Operations)

Use the provided script for command-line operations:

```bash
cd backend
source venv/bin/activate  # or your virtual environment

# Preview what would be deleted (dry run)
python scripts/delete_user_interviews.py <user_id> --dry-run

# Actually delete (requires typing "DELETE" to confirm)
python scripts/delete_user_interviews.py <user_id> --confirm
```

**Example:**
```bash
# Preview
python scripts/delete_user_interviews.py abc123xyz --dry-run

# Delete
python scripts/delete_user_interviews.py abc123xyz --confirm
# Then type "DELETE" when prompted
```

### Method 2: API Endpoint (For Programmatic Access)

Use the REST API endpoint for programmatic access:

**Endpoint:** `DELETE /api/admin/interviews/user/{user_id}`

**Query Parameters:**
- `confirm` (boolean, default: false) - Set to `true` to actually delete

**Preview (no deletion):**
```bash
curl -X DELETE "http://localhost:8000/api/admin/interviews/user/abc123xyz" \
  -H "Authorization: Bearer <your_token>"
```

**Actually Delete:**
```bash
curl -X DELETE "http://localhost:8000/api/admin/interviews/user/abc123xyz?confirm=true" \
  -H "Authorization: Bearer <your_token>"
```

**Response (Preview):**
```json
{
  "preview": true,
  "interviews_count": 5,
  "reports_count": 5,
  "message": "Set confirm=true to actually delete. This is a preview.",
  "interview_ids": ["id1", "id2", ...],
  "report_ids": ["report1", "report2", ...]
}
```

**Response (After Deletion):**
```json
{
  "success": true,
  "deleted_interviews": 5,
  "deleted_reports": 5,
  "interview_ids": ["id1", "id2", ...],
  "report_ids": ["report1", "report2", ...]
}
```

### Method 3: Direct Firestore Query (Using Python)

You can also query directly using the Firestore client:

```python
from shared.db.firestore_client import firestore_client
from shared.auth.firebase_auth import initialize_firebase
import asyncio

async def query_user_interviews(user_id: str):
    initialize_firebase()
    
    # Query interviews
    interviews = await firestore_client.query_collection(
        collection="interviews",
        filters=[("user_id", "==", user_id)]
    )
    
    # Query reports
    reports = await firestore_client.query_collection(
        collection="reports",
        filters=[("user_id", "==", user_id)]
    )
    
    print(f"Found {len(interviews)} interviews and {len(reports)} reports")
    return interviews, reports

# Run
asyncio.run(query_user_interviews("your_user_id"))
```

## What Gets Deleted

The script/endpoint deletes:
1. **All documents in `interviews` collection** where `user_id == <user_id>`
2. **All documents in `reports` collection** where `user_id == <user_id>`

## Security

- Users can only delete their own interviews (verified by `user_id` matching authenticated user)
- Preview mode by default (requires `confirm=true` for actual deletion)
- Script requires typing "DELETE" to confirm

## Finding User ID

You can find a user's ID from:
- **Firebase Console** → Authentication → Users → Copy UID
- **Your application** → User profile/settings page
- **Firestore Console** → `users` collection → Document ID

## Firestore Collections Structure

```
interviews/
  └── {interview_id}/
      ├── user_id: "abc123"
      ├── interview_id: "xyz789"
      ├── created_at: timestamp
      └── ... (other fields)

reports/
  └── {report_id}/
      ├── user_id: "abc123"
      ├── interview_id: "xyz789"
      ├── created_at: timestamp
      └── ... (other fields)
```

## Troubleshooting

**Error: "Firestore client not initialized"**
- Make sure `GOOGLE_APPLICATION_CREDENTIALS_JSON` is set in your environment
- Or ensure `firebase-service-account.json` exists in the backend directory

**Error: "Insufficient permissions"**
- Check that your service account has "Cloud Datastore User" or "Firestore User" role in Google Cloud Console

**No interviews found**
- Verify the `user_id` is correct
- Check Firestore Console to see if documents exist
- Verify the `user_id` field name matches (could be `userId` or `user_id`)

## Related Files

- `backend/scripts/delete_user_interviews.py` - Python script
- `backend/shared/db/firestore_client.py` - Firestore client with query/delete methods
- `backend/interview_service/main.py` - API endpoint implementation


