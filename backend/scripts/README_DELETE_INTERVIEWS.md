# Delete User Interviews Script

This script allows you to query and delete all interviews and reports for a specific user in Firestore.

## Usage

### Dry Run (Preview what will be deleted)
```bash
cd backend
source venv/bin/activate
python scripts/delete_user_interviews.py <user_id> --dry-run
```

### Actual Deletion
```bash
cd backend
source venv/bin/activate
python scripts/delete_user_interviews.py <user_id> --confirm
```

When you use `--confirm`, you'll be prompted to type "DELETE" to confirm the action.

## Examples

```bash
# Preview what would be deleted for user abc123
python scripts/delete_user_interviews.py abc123 --dry-run

# Actually delete (requires typing "DELETE" to confirm)
python scripts/delete_user_interviews.py abc123 --confirm
```

## What it does

1. **Queries Firestore** for:
   - All documents in `interviews` collection where `user_id == <user_id>`
   - All documents in `reports` collection where `user_id == <user_id>`

2. **Deletes** all found interviews and reports

3. **Provides summary** of what was deleted

## Safety Features

- **Dry run mode** by default - shows what would be deleted without actually deleting
- **Confirmation required** - must type "DELETE" to confirm actual deletion
- **Error handling** - continues even if some deletions fail, reports errors at the end

## Finding User ID

You can find a user's ID from:
- Firebase Console → Authentication → Users
- Or from your application's user management interface


