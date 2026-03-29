"""
Vertex Loader

Handles loading vertices into TigerGraph with batching and retry logic.
"""

import time
import traceback
from typing import List, Tuple, Dict, Any
from ..infrastructure import GraphConnector
from ..data_loading import DataSanitizer


class VertexLoader:
    """
    Loads vertices into TigerGraph in batches with retry logic.
    """
    
    def __init__(
        self,
        graph_connector: GraphConnector,
        batch_size: int = 10,
        max_retries: int = 3,
        retry_delay: float = 0.5
    ):
        """
        Initialize vertex loader.
        
        Args:
            graph_connector: TigerGraph connector
            batch_size: Number of vertices per batch
            max_retries: Maximum retry attempts per batch
            retry_delay: Delay between retries in seconds
        """
        self.graph_connector = graph_connector
        self.batch_size = batch_size
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.sanitizer = DataSanitizer()
    
    def load_vertices(
        self,
        vertex_type: str,
        data: List[Tuple[str, Dict[str, Any]]]
    ) -> Dict[str, Any]:
        """
        Load vertices into TigerGraph.
        
        Args:
            vertex_type: Type of vertex (e.g., 'Project', 'Portfolio')
            data: List of (vertex_id, attributes_dict) tuples
            
        Returns:
            Dictionary with loading statistics
        """
        # Prepare and sanitize data
        vertex_data = self.sanitizer.prepare_vertex_batch(data, vertex_type)
        
        if not vertex_data:
            print(f"No valid {vertex_type} vertices to load")
            return {"loaded": 0, "failed": 0, "total": 0}
        
        print(f"Loading {len(vertex_data)} {vertex_type} vertices in batches of {self.batch_size}")
        
        loaded_count = 0
        failed_count = 0
        
        # Process in batches
        for i in range(0, len(vertex_data), self.batch_size):
            batch = vertex_data[i:i + self.batch_size]
            batch_num = i // self.batch_size + 1
            
            print(f"Processing {vertex_type} batch {batch_num} with {len(batch)} vertices")
            
            # Retry logic
            for attempt in range(self.max_retries):
                try:
                    result = self.graph_connector.upsert_vertices(
                        vertex_type=vertex_type,
                        vertices=batch
                    )
                    print(f"\n✓ Upsert result for {vertex_type} batch {batch_num}:")
                    print(f"  Full result type: {type(result)}")
                    print(f"  Full result: {result}")
                    if isinstance(result, dict):
                        for key, val in result.items():
                            print(f"    {key}: {val}")
                    print(f"✓ Loaded {len(batch)} {vertex_type} vertices (batch {batch_num})")
                    loaded_count += len(batch)
                    break  # Success, exit retry loop
                    
                except Exception as e:
                    print(f"✗ Attempt {attempt + 1} failed for {vertex_type} batch {batch_num}: {str(e)}")
                    
                    if attempt == 0:
                        # Only print batch data on first failure
                        print(f"  Sample batch data: {batch[:2]}")
                    
                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_delay * (2 ** attempt))  # Exponential backoff
                    else:
                        print(f"✗ Failed to load {vertex_type} batch {batch_num} after {self.max_retries} attempts")
                        print(traceback.format_exc())
                        failed_count += len(batch)
        
        return {
            "loaded": loaded_count,
            "failed": failed_count,
            "total": len(vertex_data)
        }
