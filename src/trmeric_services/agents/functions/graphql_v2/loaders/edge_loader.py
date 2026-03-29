"""
Edge Loader

Handles loading edges into TigerGraph with batching and retry logic.
"""

import time
import traceback
from typing import List, Tuple, Dict, Any
from ..infrastructure import GraphConnector
from ..data_loading import DataSanitizer


class EdgeLoader:
    """
    Loads edges into TigerGraph in batches with retry logic.
    """
    
    def __init__(
        self,
        graph_connector: GraphConnector,
        batch_size: int = 10,
        max_retries: int = 3,
        retry_delay: float = 0.5
    ):
        """
        Initialize edge loader.
        
        Args:
            graph_connector: TigerGraph connector
            batch_size: Number of edges per batch
            max_retries: Maximum retry attempts per batch
            retry_delay: Delay between retries in seconds
        """
        self.graph_connector = graph_connector
        self.batch_size = batch_size
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.sanitizer = DataSanitizer()
    
    def load_edges(
        self,
        edge_type: str,
        from_vertex_type: str,
        to_vertex_type: str,
        data: List[Tuple[str, str]]
    ) -> Dict[str, Any]:
        """
        Load edges into TigerGraph.
        
        Args:
            edge_type: Type of edge (e.g., 'hasPortfolio', 'hasMilestone')
            from_vertex_type: Source vertex type
            to_vertex_type: Target vertex type
            data: List of (source_id, target_id) tuples
            
        Returns:
            Dictionary with loading statistics
        """
        # Prepare and sanitize data
        edge_data = self.sanitizer.prepare_edge_batch(data)
        
        if not edge_data:
            print(f"No valid {edge_type} edges to load")
            return {"loaded": 0, "failed": 0, "total": 0}
        
        print(f"Loading {len(edge_data)} {edge_type} edges in batches of {self.batch_size}")
        
        loaded_count = 0
        failed_count = 0
        
        # Process in batches
        for i in range(0, len(edge_data), self.batch_size):
            batch = edge_data[i:i + self.batch_size]
            batch_num = i // self.batch_size + 1
            
            print(f"Processing {edge_type} batch {batch_num} with {len(batch)} edges")
            
            # Retry logic
            for attempt in range(self.max_retries):
                try:
                    result = self.graph_connector.upsert_edges(
                        source_vertex_type=from_vertex_type,
                        edge_type=edge_type,
                        target_vertex_type=to_vertex_type,
                        edges=batch
                    )
                    print(f"\n✓ Upsert result for {edge_type} batch {batch_num}:")
                    print(f"  Full result type: {type(result)}")
                    print(f"  Full result: {result}")
                    if isinstance(result, dict):
                        for key, val in result.items():
                            print(f"    {key}: {val}")
                    print(f"✓ Loaded {len(batch)} {edge_type} edges (batch {batch_num})")
                    loaded_count += len(batch)
                    break  # Success, exit retry loop
                    
                except Exception as e:
                    print(f"✗ Attempt {attempt + 1} failed for {edge_type} batch {batch_num}: {str(e)}")
                    
                    if attempt == 0:
                        # Only print batch data on first failure
                        print(f"  Sample batch data: {batch[:2]}")
                    
                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_delay * (2 ** attempt))  # Exponential backoff
                    else:
                        print(f"✗ Failed to load {edge_type} batch {batch_num} after {self.max_retries} attempts")
                        print(traceback.format_exc())
                        failed_count += len(batch)
        
        return {
            "loaded": loaded_count,
            "failed": failed_count,
            "total": len(edge_data)
        }
