"""
Semantic Features Module

Provides lightweight semantic similarity for text fields like solutions, 
objectives, and descriptions using TF-IDF (no heavy dependencies).
"""

from typing import List, Dict, Optional
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


class SemanticFeatureExtractor:
    """Extracts semantic features from text fields using lightweight TF-IDF."""
    
    def __init__(self):
        """Initialize the semantic feature extractor with TF-IDF."""
        self.vectorizer = TfidfVectorizer(
            max_features=100,  # Keep it light
            stop_words='english',
            lowercase=True,
            strip_accents='unicode'
        )
        print(f"✓ TF-IDF semantic feature extractor initialized")
    
    def encode_text(self, texts: List[str]) -> Optional[np.ndarray]:
        """
        Encode a list of texts to TF-IDF vectors.
        
        Args:
            texts: List of text strings to encode
            
        Returns:
            numpy array of shape (len(texts), n_features) or None if inputs are empty
        """
        if not texts or len(texts) < 2:
            return None
        
        try:
            # Filter out None/empty strings
            clean_texts = [t if isinstance(t, str) and t.strip() else "unknown" for t in texts]
            # Need at least 2 documents for TF-IDF to work
            if len(set(clean_texts)) < 2:
                return None
            vectors = self.vectorizer.fit_transform(clean_texts).toarray()
            return vectors
        except Exception as e:
            print(f"Error encoding texts: {e}")
            return None
    
    def extract_solution_embeddings(self, entities: List[Dict], solution_key: str = "solution") -> Optional[np.ndarray]:
        """
        Extract semantic features from solution field of entities.
        
        Args:
            entities: List of entity dictionaries (roadmaps with solution field)
            solution_key: Key name for solution field in entity dicts
            
        Returns:
            numpy array of TF-IDF vectors normalized to 0-1
        """
        solutions = [e.get(solution_key, "") for e in entities]
        vectors = self.encode_text(solutions)
        
        if vectors is None:
            return None
        
        # Normalize to 0-1 range (TF-IDF is already normalized for cosine similarity)
        return vectors
    
    def similarity_score(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """Compute cosine similarity between two embeddings."""
        if embedding1 is None or embedding2 is None:
            return 0.0
        try:
            return float(cosine_similarity([embedding1], [embedding2])[0][0])
        except Exception:
            return 0.0


def get_solution_embedding_features(roadmaps: List[Dict]) -> Optional[np.ndarray]:
    """
    Convenience function to extract solution features from roadmaps.
    
    Args:
        roadmaps: List of roadmap dictionaries with "solution" field
        
    Returns:
        numpy array of TF-IDF vectors or None if extraction fails
    """
    try:
        extractor = SemanticFeatureExtractor()
        return extractor.extract_solution_embeddings(roadmaps, solution_key="solution")
    except Exception as e:
        print(f"Error getting solution features: {e}")
        return None


def get_objective_embedding_features(projects: List[Dict]) -> Optional[np.ndarray]:
    """
    Convenience function to extract objective features from projects.
    
    Args:
        projects: List of project dictionaries with "objectives" field
        
    Returns:
        numpy array of TF-IDF vectors or None if extraction fails
    """
    try:
        extractor = SemanticFeatureExtractor()
        return extractor.extract_solution_embeddings(projects, solution_key="objectives")
    except Exception as e:
        print(f"Error getting objective features: {e}")
        return None

