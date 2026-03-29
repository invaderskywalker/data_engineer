import requests
from typing import Dict, List, Optional
from src.trmeric_api.logging.AppLogger import appLogger
import os


class TrmericVectorStoreClient:
    """
    Thin client for querying Trmeric's internal semantic knowledge base.

    This client communicates with a private vector store service
    that indexes Trmeric-specific documents such as:
        • platform documentation
        • company knowledge
        • goals and strategy
        • product concepts
        • internal narratives

    It is READ-ONLY and semantic in nature.
    """

    def __init__(self, timeout: int = 10):
        self.base_url = os.getenv("VECTORSTORE_ENDPOINT")
        self.timeout = timeout

    def list_collections(self) -> List[str]:
        try:
            resp = requests.get(
                f"{self.base_url}/collections",
                timeout=self.timeout,
            )
            resp.raise_for_status()
            return resp.json().get("collections", [])
        except Exception as e:
            appLogger.error({
                "event": "VectorStoreListCollectionsFailed",
                "error": str(e),
            })
            return []

    def query(
        self,
        *,
        query: str,
        tenant_id: int,
        collection_name: str,
        top_k: int = 5,
    ) -> Dict:
        """
        Executes a semantic query against a Trmeric vector collection.
        """

        payload = {
            "query": query,
            "tenant_id": tenant_id,
            "collection_name": collection_name,
            "top_k": top_k,
        }

        try:
            resp = requests.post(
                f"{self.base_url}/query",
                json=payload,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            return resp.json()

        except Exception as e:
            appLogger.error({
                "event": "VectorStoreQueryFailed",
                "query": query,
                "collection": collection_name,
                "error": str(e),
            })
            return {
                "matches": [],
                "parent_documents": [],
                "error": str(e),
            }
