#!/usr/bin/env python3
"""
Utility script to query and delete interviews for a specific user in Firestore.

Usage:
    python scripts/delete_user_interviews.py <user_id> [--dry-run] [--confirm]

Examples:
    # Dry run (just show what would be deleted)
    python scripts/delete_user_interviews.py abc123 --dry-run
    
    # Actually delete (requires confirmation)
    python scripts/delete_user_interviews.py abc123 --confirm
"""
import sys
import asyncio
import argparse
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.db.firestore_client import firestore_client
from shared.auth.firebase_auth import initialize_firebase
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def query_user_interviews(user_id: str) -> list:
    """Query all interviews for a specific user."""
    logger.info(f"🔍 Querying interviews for user: {user_id}")
    
    # Query interviews collection
    interviews = await firestore_client.query_collection(
        collection="interviews",
        filters=[("user_id", "==", user_id)],
        order_by="created_at",
        order_direction="DESCENDING"
    )
    
    # Also query reports collection (reports are linked to interviews)
    reports = await firestore_client.query_collection(
        collection="reports",
        filters=[("user_id", "==", user_id)],
        order_by="created_at",
        order_direction="DESCENDING"
    )
    
    logger.info(f"📊 Found {len(interviews)} interviews and {len(reports)} reports for user {user_id}")
    
    return {
        "interviews": interviews,
        "reports": reports
    }


async def delete_user_interviews(user_id: str, dry_run: bool = True) -> dict:
    """Delete all interviews and reports for a specific user."""
    results = await query_user_interviews(user_id)
    
    interviews = results["interviews"]
    reports = results["reports"]
    
    deleted_interviews = []
    deleted_reports = []
    errors = []
    
    if dry_run:
        logger.info("🔍 DRY RUN MODE - No data will be deleted")
        logger.info(f"Would delete {len(interviews)} interviews:")
        for interview in interviews:
            interview_id = interview.get("id") or interview.get("interview_id")
            logger.info(f"  - Interview ID: {interview_id}")
            deleted_interviews.append(interview_id)
        
        logger.info(f"Would delete {len(reports)} reports:")
        for report in reports:
            report_id = report.get("id") or report.get("report_id")
            interview_id = report.get("interview_id")
            logger.info(f"  - Report ID: {report_id}, Interview ID: {interview_id}")
            deleted_reports.append(report_id)
    else:
        logger.info(f"🗑️  DELETING {len(interviews)} interviews and {len(reports)} reports...")
        
        # Delete interviews
        for interview in interviews:
            interview_id = interview.get("id") or interview.get("interview_id")
            try:
                success = await firestore_client.delete_document("interviews", interview_id)
                if success:
                    logger.info(f"✅ Deleted interview: {interview_id}")
                    deleted_interviews.append(interview_id)
                else:
                    logger.error(f"❌ Failed to delete interview: {interview_id}")
                    errors.append(f"Interview {interview_id}")
            except Exception as e:
                logger.error(f"❌ Error deleting interview {interview_id}: {e}")
                errors.append(f"Interview {interview_id}: {str(e)}")
        
        # Delete reports
        for report in reports:
            report_id = report.get("id") or report.get("report_id")
            try:
                success = await firestore_client.delete_document("reports", report_id)
                if success:
                    logger.info(f"✅ Deleted report: {report_id}")
                    deleted_reports.append(report_id)
                else:
                    logger.error(f"❌ Failed to delete report: {report_id}")
                    errors.append(f"Report {report_id}")
            except Exception as e:
                logger.error(f"❌ Error deleting report {report_id}: {e}")
                errors.append(f"Report {report_id}: {str(e)}")
    
    return {
        "deleted_interviews": deleted_interviews,
        "deleted_reports": deleted_reports,
        "errors": errors,
        "dry_run": dry_run
    }


async def main():
    parser = argparse.ArgumentParser(description="Delete interviews for a specific user")
    parser.add_argument("user_id", help="Firebase user ID (UID)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be deleted without actually deleting")
    parser.add_argument("--confirm", action="store_true", help="Confirm deletion (required for actual deletion)")
    
    args = parser.parse_args()
    
    # Initialize Firebase
    initialize_firebase()
    
    # Query first to show what will be deleted
    results = await query_user_interviews(args.user_id)
    
    if not results["interviews"] and not results["reports"]:
        logger.info(f"✅ No interviews or reports found for user {args.user_id}")
        return
    
    # Determine if this is a dry run
    dry_run = args.dry_run or not args.confirm
    
    if not dry_run:
        # Require explicit confirmation
        print(f"\n⚠️  WARNING: You are about to delete:")
        print(f"   - {len(results['interviews'])} interviews")
        print(f"   - {len(results['reports'])} reports")
        print(f"\nThis action cannot be undone!")
        response = input("Type 'DELETE' to confirm: ")
        if response != "DELETE":
            logger.info("❌ Deletion cancelled")
            return
    
    # Delete interviews
    deletion_results = await delete_user_interviews(args.user_id, dry_run=dry_run)
    
    # Summary
    print("\n" + "="*50)
    print("DELETION SUMMARY")
    print("="*50)
    print(f"User ID: {args.user_id}")
    print(f"Mode: {'DRY RUN' if deletion_results['dry_run'] else 'ACTUAL DELETION'}")
    print(f"Interviews deleted: {len(deletion_results['deleted_interviews'])}")
    print(f"Reports deleted: {len(deletion_results['deleted_reports'])}")
    if deletion_results['errors']:
        print(f"Errors: {len(deletion_results['errors'])}")
        for error in deletion_results['errors']:
            print(f"  - {error}")
    print("="*50)


if __name__ == "__main__":
    asyncio.run(main())

