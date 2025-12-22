"""Firestore database client."""
from google.cloud import firestore
from firebase_admin import firestore as admin_firestore
from typing import Optional, Dict, Any, List
from shared.config.settings import settings
import os


class FirestoreClient:
    """Firestore client wrapper."""
    
    def __init__(self):
        """Initialize Firestore client (lazy initialization)."""
        self.db = None
        self._initialized = False
    
    def _ensure_initialized(self):
        """Ensure Firebase is initialized and Firestore client is ready."""
        if self._initialized and self.db:
            return
        
        try:
            # Ensure Firebase is initialized before creating Firestore client
            from firebase_admin import get_app
            try:
                app = get_app()
            except ValueError:
                # Firebase not initialized, try to initialize it
                from shared.auth.firebase_auth import initialize_firebase
                initialize_firebase()
                app = get_app()
            
            # Now create Firestore client
            self.db = admin_firestore.client()
            self._initialized = True
            import logging
            logger = logging.getLogger(__name__)
            logger.info("✅ Firestore client initialized successfully")
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            error_msg = str(e)
            if "insufficient authentication scopes" in error_msg.lower() or "ACCESS_TOKEN_SCOPE_INSUFFICIENT" in error_msg:
                logger.error("❌ Firestore authentication error: Service account lacks Firestore permissions.")
                logger.error("   Fix: Grant 'Cloud Datastore User' or 'Firestore User' role to service account in Google Cloud Console")
                logger.error(f"   Service account: Check GOOGLE_APPLICATION_CREDENTIALS_JSON -> client_email")
            elif "DefaultCredentialsError" in error_msg or "default credentials were not found" in error_msg.lower():
                logger.error("❌ Firestore client error: Firebase not properly initialized.")
                logger.error("   This usually means GOOGLE_APPLICATION_CREDENTIALS_JSON is not set or invalid.")
                logger.error("   Check Railway environment variables.")
            else:
                logger.error(f"❌ Firestore client initialization failed: {type(e).__name__}: {error_msg[:200]}")
            self.db = None
            self._initialized = False
    
    async def get_document(self, collection: str, document_id: str) -> Optional[Dict[str, Any]]:
        """Get a document from Firestore."""
        self._ensure_initialized()
        if not self.db:
            return None
        try:
            import asyncio
            # Run synchronous Firestore operation in executor to avoid blocking
            def _get_doc():
                return self.db.collection(collection).document(document_id).get()
            
            loop = asyncio.get_event_loop()
            doc = await loop.run_in_executor(None, _get_doc)
            if doc.exists:
                return doc.to_dict()
            return None
        except Exception as e:
            print(f"Error getting document: {e}")
            return None
    
    async def set_document(
        self,
        collection: str,
        document_id: str,
        data: Dict[str, Any],
        merge: bool = False
    ) -> bool:
        """Set a document in Firestore."""
        self._ensure_initialized()
        if not self.db:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"ERROR: Firestore client not initialized. Cannot set document {collection}/{document_id}")
            return False
        try:
            import asyncio
            import logging
            logger = logging.getLogger(__name__)
            
            # Run synchronous Firestore operation in executor to avoid blocking
            def _set_doc():
                ref = self.db.collection(collection).document(document_id)
                if merge:
                    ref.set(data, merge=True)
                    logger.info(f"✅ Merged document {collection}/{document_id}")
                else:
                    ref.set(data)
                    logger.info(f"✅ Set document {collection}/{document_id}")
            
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, _set_doc)
            return True
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"❌ Error setting document {collection}/{document_id}: {type(e).__name__}: {str(e)}", exc_info=True)
            return False
    
    async def update_document(
        self,
        collection: str,
        document_id: str,
        data: Dict[str, Any]
    ) -> bool:
        """Update a document in Firestore."""
        self._ensure_initialized()
        if not self.db:
            return False
        try:
            self.db.collection(collection).document(document_id).update(data)
            return True
        except Exception as e:
            print(f"Error updating document: {e}")
            return False
    
    async def query_collection(
        self,
        collection: str,
        filters: Optional[List[tuple]] = None,
        order_by: Optional[str] = None,
        order_direction: Optional[str] = "ASCENDING",
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Query a collection in Firestore."""
        self._ensure_initialized()
        if not self.db:
            return []
        try:
            import asyncio
            from google.cloud import firestore
            
            def _query():
                query = self.db.collection(collection)
                
                if filters:
                    for field, operator, value in filters:
                        query = query.where(field, operator, value)
                
                if order_by:
                    direction = firestore.Query.DESCENDING if order_direction == "DESCENDING" else firestore.Query.ASCENDING
                    query = query.order_by(order_by, direction=direction)
                
                if limit:
                    query = query.limit(limit)
                
                docs = query.stream()
                return [{"id": doc.id, **doc.to_dict()} for doc in docs]
            
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, _query)
        except Exception as e:
            print(f"Error querying collection: {e}")
            return []
    
    async def delete_document(self, collection: str, document_id: str) -> bool:
        """Delete a document from Firestore."""
        self._ensure_initialized()
        if not self.db:
            return False
        try:
            import asyncio
            import logging
            logger = logging.getLogger(__name__)
            
            def _delete_doc():
                self.db.collection(collection).document(document_id).delete()
                logger.info(f"✅ Deleted document {collection}/{document_id}")
            
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, _delete_doc)
            return True
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"❌ Error deleting document {collection}/{document_id}: {e}")
            return False
    
    async def delete_documents_batch(self, collection: str, document_ids: List[str]) -> dict:
        """Delete multiple documents from Firestore in batch."""
        self._ensure_initialized()
        if not self.db:
            return {"deleted": [], "failed": document_ids}
        
        deleted = []
        failed = []
        
        for doc_id in document_ids:
            success = await self.delete_document(collection, doc_id)
            if success:
                deleted.append(doc_id)
            else:
                failed.append(doc_id)
        
        return {
            "deleted": deleted,
            "failed": failed,
            "total": len(document_ids),
            "success_count": len(deleted),
            "failed_count": len(failed)
        }


# Global Firestore client instance
firestore_client = FirestoreClient()

