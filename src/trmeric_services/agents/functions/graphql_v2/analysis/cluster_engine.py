"""
Cluster Engine

Ported from original analysis.py: clustering helpers using sklearn KMeans.
Refactored to support multiple entity types (projects, roadmaps, etc.) with shared clustering logic.
Now with semantic embedding support for solution/objective text fields.

Two-Stage Clustering:
1. Mathematical pre-clustering: Use ML to reduce large datasets to manageable groups (5+ entities per cluster)
2. LLM-based refinement: Use LLM for final semantic clustering within pre-clustered groups
"""
from typing import List, Dict, Tuple, Optional, Any
from abc import ABC, abstractmethod
import math
import traceback
import numpy as np
import json
from sklearn.cluster import KMeans
from sklearn.preprocessing import MultiLabelBinarizer, MinMaxScaler
from sklearn.metrics import silhouette_score
import logging

from src.trmeric_api.logging.AppLogger import appLogger

# Import semantic features
from .semantic_features import SemanticFeatureExtractor


def format_entity_for_llm(entity: Dict, entity_type: str = "roadmap") -> str:
    """Format entity data for LLM clustering prompt with comprehensive details."""
    if entity_type.lower() == "roadmap":
        roadmap_id = entity.get("roadmap_id", "Unknown")
        name = entity.get("name", "Untitled") or "Untitled"
        description = entity.get("description") or "No description"
        objectives = entity.get("roadmap_objectives") or "No objectives specified"
        solution = entity.get("solution") or "No solution specified"
        
        # Extract categories, types, scopes
        categories = [c.get("name", "Unknown") for c in entity.get("categories", [])]
        roadmap_types = [t.get("name", "Unknown") for t in entity.get("roadmap_types", [])]
        scopes = [s.get("scope_name", "Unknown") for s in entity.get("scopes", [])]
        
        # Extract portfolios
        portfolios = [p.get("name", "Unknown") for p in entity.get("portfolios", [])]
        
        # Extract constraints with types
        constraints_list = entity.get("constraints", [])
        constraints = [f"{c.get('constraint_name', 'Unknown')} ({c.get('constraint_type', 'Unknown')})" 
                      for c in constraints_list]
        
        # Extract KPIs
        kpis = [k.get("kpi_name", "Unknown") for k in entity.get("key_results", [])]
        
        # Extract priorities and statuses
        priority_list = entity.get("priorities", [])
        priority = priority_list[0].get("priority_level", "Unknown") if priority_list else "Unknown"
        
        status_list = entity.get("statuses", [])
        status = status_list[0].get("status", "Unknown") if status_list else "Unknown"
        
        # Extract team info
        team = entity.get("team", [])
        team_summary = f"{len(team)} team members" if team else "No team"
        labour_types = list(set([t.get("labour_type", "Unknown") for t in team]))
        
        # Budget and strategy
        budget = entity.get("budget") or "Not specified"
        strategy = entity.get("org_strategy_align") or "No strategy alignment"
        
        return f"""Roadmap {roadmap_id}: {name}
Description: {description[:250]}
Objectives: {objectives[:250]}
Solution: {solution[:400]}
Strategy Alignment: {strategy[:150]}

Portfolios: {', '.join(portfolios) if portfolios else 'None'}
Categories: {', '.join(categories) if categories else 'None'}
Types: {', '.join(roadmap_types) if roadmap_types else 'None'}
Scopes: {', '.join(scopes[:5]) if scopes else 'None'}

Priority: {priority}
Status: {status}
Budget: {budget}

Key Results/KPIs: {', '.join(kpis[:5]) if kpis else 'None'}
Constraints: {', '.join(constraints[:5]) if constraints else 'None'}
Team: {team_summary} ({', '.join(labour_types) if labour_types else 'Unknown'})"""
    
    elif entity_type.lower() == "project":
        project_id = entity.get("project_id", "Unknown")
        name = entity.get("name") or "Untitled"
        description = entity.get("description") or "No description"
        objectives = entity.get("project_objectives") or "No objectives"
        
        # Extract categories and technologies
        categories = [c.get("name", "Unknown") for c in entity.get("categories", [])]
        technologies = [t.get("name", "Unknown") for t in entity.get("technologies", [])]
        
        # Extract project type and SDLC
        project_type_list = entity.get("project_type", [])
        project_type = project_type_list[0].get("name", "Unknown") if project_type_list else "Unknown"
        
        sdlc_list = entity.get("sdlc_method", [])
        sdlc = sdlc_list[0].get("name", "Unknown") if sdlc_list else "Unknown"
        
        # Extract KPIs and milestones
        kpis = [k.get("kpi_name", "Unknown") for k in entity.get("key_results", [])]
        milestones = [m.get("milestone_name", "Unknown") for m in entity.get("milestones", [])]
        
        # Team and budget
        team = entity.get("team", [])
        team_size = len(team)
        budget = entity.get("budget") or entity.get("total_external_spend", "Not specified")
        
        # Strategy and risks
        strategy = entity.get("org_strategy_align", "No strategy alignment")
        risks = entity.get("risks", [])
        risk_count = len(risks)
        
        return f"""Project {project_id}: {name}
Description: {description[:250]}
Objectives: {objectives[:250]}
Strategy Alignment: {strategy[:150] if strategy else 'None'}

Project Type: {project_type}
SDLC Method: {sdlc}
Categories: {', '.join(categories) if categories else 'None'}
Technologies: {', '.join(technologies[:8]) if technologies else 'None'}

Budget: {budget}
Team Size: {team_size}
Risks: {risk_count} identified

Key Results/KPIs: {', '.join(kpis[:5]) if kpis else 'None'}
Milestones: {', '.join(milestones[:5]) if milestones else 'None'}"""
    
    return str(entity)


def _llm_merge_singletons(
    entities: List[Dict],
    clusters: List[List[int]],
    llm_client,
    entity_type: str = "roadmap",
) -> List[List[int]]:
    """Use LLM to merge singleton clusters into the most appropriate larger cluster.
    
    Called as a post-validation step when the initial LLM clustering produces
    clusters with only 1 entity despite being told not to.
    
    Args:
        entities: Original entity list
        clusters: Current cluster assignments (list of index lists)
        llm_client: LLM client
        entity_type: "roadmap" or "project"
        
    Returns:
        Updated clusters with no singletons
    """
    from src.trmeric_ml.llm.Types import ChatCompletion, ModelOptions
    from src.trmeric_utils.json_parser import extract_json_after_llm
    
    singletons = [c for c in clusters if len(c) == 1]
    valid_clusters = [c for c in clusters if len(c) > 1]
    
    if not singletons:
        return clusters
    
    if not valid_clusters:
        # All clusters are singletons — merge everything into one
        appLogger.info({
            "event": "CLUSTERING_ALL_SINGLETONS",
            "stage": "CLUSTER",
            "entity_type": entity_type,
            "singleton_count": len(singletons),
        })
        return [[idx for c in clusters for idx in c]]
    
    singleton_indices = [c[0] for c in singletons]
    
    # Build a concise description of each valid cluster
    cluster_descriptions = []
    for ci, cluster_indices in enumerate(valid_clusters):
        names = []
        for idx in cluster_indices:
            e = entities[idx]
            name = e.get("name") or e.get("roadmap_id") or e.get("project_id") or f"Entity {idx}"
            names.append(f"[{idx}] {name}")
        cluster_descriptions.append(f"Cluster {ci}: {', '.join(names)}")
    
    # Build descriptions of singletons
    singleton_descriptions = []
    for idx in singleton_indices:
        singleton_descriptions.append(f"[{idx}] {format_entity_for_llm(entities[idx], entity_type)}")
    
    prompt = f"""You previously clustered {entity_type}s but some ended up alone in their own cluster.
Single-entity clusters cannot form meaningful patterns. You must assign each singleton to one of the existing multi-entity clusters.

EXISTING CLUSTERS:
{chr(10).join(cluster_descriptions)}

SINGLETONS TO ASSIGN (each must go into exactly one cluster above):
{chr(10).join(singleton_descriptions)}

For each singleton, pick the cluster (by number) it is most similar to based on strategic intent, domain, technologies, and business goals.

Return a JSON object mapping each singleton index to its target cluster number:
{{"<entity_index>": <cluster_number>, ...}}

Example: {{"3": 0, "7": 1}} means entity 3 joins Cluster 0 and entity 7 joins Cluster 1.

JSON only, no explanation:"""
    
    try:
        chat_completion = ChatCompletion(
            system=prompt,
            prev=[],
            user="Assign each singleton to a cluster."
        )
        response = llm_client.run(
            chat_completion,
            ModelOptions(model="gpt-4o", max_tokens=500, temperature=0.1),
            'analysis::llm_merge_singletons'
        )
        
        if response is None:
            raise ValueError("LLM returned None")
        
        assignments = extract_json_after_llm(response)
        appLogger.info({
            "event": "CLUSTERING_SINGLETON_ASSIGNMENTS",
            "stage": "CLUSTER",
            "entity_type": entity_type,
            "assignments": assignments,
        })
        
        if isinstance(assignments, dict):
            for entity_idx_str, cluster_num in assignments.items():
                entity_idx = int(entity_idx_str)
                cluster_num = int(cluster_num)
                if 0 <= cluster_num < len(valid_clusters) and entity_idx in singleton_indices:
                    valid_clusters[cluster_num].append(entity_idx)
                    singleton_indices.remove(entity_idx)
        
        # Any singletons LLM couldn't assign — put into the largest cluster
        if singleton_indices:
            largest_cluster = max(range(len(valid_clusters)), key=lambda i: len(valid_clusters[i]))
            for idx in singleton_indices:
                valid_clusters[largest_cluster].append(idx)
            appLogger.warning({
                "event": "CLUSTERING_SINGLETON_FALLBACK",
                "stage": "CLUSTER",
                "entity_type": entity_type,
                "remaining_singletons": singleton_indices,
                "fallback_cluster": largest_cluster,
            })
        
        appLogger.info({
            "event": "CLUSTERING_SINGLETONS_MERGED",
            "stage": "CLUSTER",
            "entity_type": entity_type,
            "cluster_sizes": [len(c) for c in valid_clusters],
        })
        return valid_clusters
        
    except Exception as e:
        appLogger.error({
            "event": "CLUSTERING_SINGLETON_MERGE_FAILED",
            "stage": "CLUSTER",
            "entity_type": entity_type,
            "error": str(e),
            "traceback": traceback.format_exc(),
        })
        # Deterministic fallback: put each singleton into the largest cluster
        largest_cluster = max(range(len(valid_clusters)), key=lambda i: len(valid_clusters[i]))
        for idx in singleton_indices:
            valid_clusters[largest_cluster].append(idx)
        return valid_clusters


def _entity_unique_key(entity: Dict[str, Any]) -> str:
    if entity.get("roadmap_id") is not None:
        return f"roadmap:{entity.get('roadmap_id')}"
    if entity.get("project_id") is not None:
        return f"project:{entity.get('project_id')}"
    return f"memory:{id(entity)}"


def _clusters_to_index_clusters(entities: List[Dict], clusters: List[List[Dict]]) -> List[List[int]]:
    index_by_key = {
        _entity_unique_key(entity): idx
        for idx, entity in enumerate(entities)
    }
    index_clusters: List[List[int]] = []
    for cluster in clusters:
        index_cluster = []
        for entity in cluster:
            idx = index_by_key.get(_entity_unique_key(entity))
            if idx is not None:
                index_cluster.append(idx)
        if index_cluster:
            index_clusters.append(index_cluster)
    return index_clusters


def _index_clusters_to_entities(entities: List[Dict], index_clusters: List[List[int]]) -> List[List[Dict]]:
    return [[entities[idx] for idx in cluster] for cluster in index_clusters]


def llm_cluster_entities(
    entities: List[Dict],
    llm_client,
    entity_type: str = "roadmap",
    min_cluster_size: int = 2,
    max_cluster_size: int = 5,
) -> List[List[int]]:
    """Use LLM to cluster entities based on semantic similarity.
    
    Args:
        entities: List of entity dictionaries
        llm_client: LLM client for making API calls
        entity_type: "roadmap" or "project"
        min_cluster_size: Minimum entities per cluster
        max_cluster_size: Maximum entities per cluster after LLM clustering
    
    Returns:
        List of clusters, where each cluster is a list of entity indices.
        Guarantees every cluster has >= min_cluster_size entities (unless total < min_cluster_size).
    """
    if not entities or len(entities) < 2:
        return [[i for i in range(len(entities))]]
    
    # Format entities for LLM
    formatted_entities = []
    for idx, entity in enumerate(entities):
        formatted_entities.append(f"[{idx}] {format_entity_for_llm(entity, entity_type)}")
    
    entities_text = "\n\n".join(formatted_entities)
    
    prompt = f"""You are an expert at clustering {entity_type}s based on their semantic similarity and strategic alignment.

Below are {len(entities)} {entity_type}s. Your task is to group them into clusters where each cluster contains {entity_type}s that are:
- Strategically similar (same business goals, approaches)
- Technically similar (same technologies, solutions, or methods)
- Contextually similar (same categories, scopes, or domains)

HARD CONSTRAINTS (you MUST follow these):
1. Every cluster MUST have at least {min_cluster_size} {entity_type}s. NO single-entity clusters allowed.
2. If a {entity_type} does not fit perfectly with others, still place it in the MOST similar cluster rather than leaving it alone.
3. It is ALWAYS better to have a slightly imperfect cluster of 2-3 than a "perfect" cluster of 1.
4. Maximum {max_cluster_size} {entity_type}s per cluster for manageable pattern generation.
5. Prefer 2-3 clusters total when possible.

Group by strategic intent and solution approach, not just keywords.

{entity_type.upper()}S TO CLUSTER:
{entities_text}

Provide your clustering decision as a JSON array of arrays, where each inner array contains the indices of {entity_type}s in that cluster.
Remember: EVERY cluster must have at least {min_cluster_size} items. Do NOT create any cluster with only 1 item.

Example format:
[[0, 1, 3], [2, 4]]

Your clustering decision (JSON only, no explanation):"""
    
    try:
        from src.trmeric_ml.llm.Types import ChatCompletion, ModelOptions
        from src.trmeric_utils.json_parser import extract_json_after_llm
        
        chat_completion = ChatCompletion(
            system=prompt,
            prev=[],
            user="Provide clustering decision as JSON array."
        )
        response = llm_client.run(
            chat_completion,
            ModelOptions(model="gpt-4o", max_tokens=500, temperature=0.2),
            'analysis::llm_cluster'
        )
        
        if response is None:
            appLogger.warning({
                "event": "CLUSTERING_LLM_EMPTY_RESPONSE",
                "stage": "CLUSTER",
                "entity_type": entity_type,
                "entity_count": len(entities),
            })
            return [[i for i in range(len(entities))]]
        
        # Use extract_json_after_llm to parse the response
        clusters = extract_json_after_llm(response)
        
        # Validate clusters
        if not isinstance(clusters, list) or not all(isinstance(c, list) for c in clusters):
            raise ValueError("Invalid cluster format")
        
        # Ensure all indices are covered
        all_indices = set(range(len(entities)))
        clustered_indices = set(idx for cluster in clusters for idx in cluster)
        
        if clustered_indices != all_indices:
            appLogger.warning({
                "event": "CLUSTERING_LLM_MISSING_INDICES",
                "stage": "CLUSTER",
                "entity_type": entity_type,
                "missing_indices": sorted(all_indices - clustered_indices),
            })
            return [[i for i in range(len(entities))]]
        
        # Deduplicate: if LLM placed the same index in multiple clusters, keep first occurrence only
        all_used = [idx for cluster in clusters for idx in cluster]
        if len(all_used) != len(set(all_used)):
            dup_count = len(all_used) - len(set(all_used))
            appLogger.info({
                "event": "CLUSTERING_DEDUP_OVERLAP",
                "stage": "CLUSTER",
                "duplicate_count": dup_count,
                "cluster_sizes_before": [len(c) for c in clusters]
            })
            seen = set()
            deduped = []
            for cluster in clusters:
                clean = [idx for idx in cluster if idx not in seen]
                seen.update(clean)
                if clean:
                    deduped.append(clean)
            clusters = deduped
        
        # Post-validation: merge any singleton clusters using LLM
        has_singletons = any(len(c) < min_cluster_size for c in clusters)
        if has_singletons and len(clusters) > 1:
            singleton_count = sum(1 for c in clusters if len(c) < min_cluster_size)
            appLogger.info({
                "event": "CLUSTERING_SINGLETON_MERGE",
                "stage": "CLUSTER",
                "singleton_count": singleton_count,
                "total_clusters": len(clusters),
                "cluster_sizes": [len(c) for c in clusters]
            })
            clusters = _llm_merge_singletons(entities, clusters, llm_client, entity_type)
        
        # Post-validation: enforce max_cluster_size by splitting over-cap clusters
        max_size = max_cluster_size
        enforced = []
        for c in clusters:
            if len(c) > max_size:
                # Deterministic split into chunks of ceil(len/2) to stay under cap
                mid = (len(c) + 1) // 2
                enforced.append(c[:mid])
                enforced.append(c[mid:])
                appLogger.info({"event": "CLUSTERING_MAX_SIZE_SPLIT", "stage": "CLUSTER", "original_size": len(c), "split_into": [mid, len(c) - mid]})
            else:
                enforced.append(c)
        clusters = enforced

        appLogger.info({
            "event": "CLUSTERING_LLM_SUCCESS",
            "stage": "CLUSTER",
            "entity_type": entity_type,
            "cluster_sizes": [len(c) for c in clusters],
        })
        return clusters
        
    except Exception as e:
        appLogger.error({
            "event": "CLUSTERING_LLM_FAILED",
            "stage": "CLUSTER",
            "entity_type": entity_type,
            "entity_count": len(entities),
            "error": str(e),
            "traceback": traceback.format_exc(),
        })
        # Fallback: return all entities in one cluster
        return [[i for i in range(len(entities))]]


class BaseClusterEngine(ABC):
    """Base class for clustering entities with hybrid ML + LLM approach."""
    
    def __init__(
        self,
        llm_client=None,
        use_llm_refinement: bool = True,
        min_cluster_size: int = 2,
        max_cluster_size: int = 5,
        ml_precluster_threshold: Optional[int] = 10,
    ):
        """
        Initialize cluster engine.
        
        Args:
            llm_client: LLM client for semantic clustering refinement
            use_llm_refinement: Whether to use LLM for final clustering (default: True)
            min_cluster_size: Minimum meaningful final cluster size after refinement (default: 2)
            max_cluster_size: Maximum entities per cluster — clusters larger than this will be sub-divided by LLM (default: 5)
            ml_precluster_threshold: Minimum entity count required before using ML pre-sharding.
                If omitted, defaults to 2 * max_cluster_size.
        """
        self.llm_client = llm_client
        self.use_llm_refinement = use_llm_refinement
        self.min_cluster_size = min_cluster_size
        self.max_cluster_size = max_cluster_size
        self.ml_precluster_threshold = ml_precluster_threshold or (2 * max_cluster_size)

    def _get_precluster_candidates(self, entity_count: int) -> List[int]:
        """Pick candidate shard counts that keep ML pre-clusters around max_cluster_size."""
        target_n = max(2, math.ceil(entity_count / self.max_cluster_size))
        upper_bound = max(2, entity_count - 1)
        candidates = {
            max(2, min(upper_bound, target_n - 1)),
            max(2, min(upper_bound, target_n)),
            max(2, min(upper_bound, target_n + 1)),
        }
        return sorted(candidates)

    def _repair_small_clusters(
        self,
        entities: List[Dict],
        clusters: List[List[Dict]],
        entity_type: str,
        min_cluster_size: int = 2,
    ) -> List[List[Dict]]:
        if len(clusters) <= 1 or not any(len(cluster) < min_cluster_size for cluster in clusters):
            return clusters

        index_clusters = _clusters_to_index_clusters(entities, clusters)
        repaired_index_clusters = _llm_merge_singletons(entities, index_clusters, self.llm_client, entity_type)
        repaired_clusters = _index_clusters_to_entities(entities, repaired_index_clusters)

        appLogger.info({
            "event": "CLUSTERING_SMALL_CLUSTER_REPAIR",
            "stage": "CLUSTER",
            "entity_type": entity_type,
            "before": [len(cluster) for cluster in clusters],
            "after": [len(cluster) for cluster in repaired_clusters],
        })
        return repaired_clusters

    def _llm_refine_clusters(
        self,
        entities: List[Dict],
        shards: List[List[Dict]],
        entity_type: str,
        shard_silhouettes: Dict[int, float],
    ) -> Tuple[List[List[Dict]], Dict[int, float]]:
        if not self.use_llm_refinement or not self.llm_client:
            return shards, shard_silhouettes

        final_clusters: List[List[Dict]] = []
        refined_silhouettes: Dict[int, float] = {}
        refined_cluster_idx = 0

        for shard_idx, shard in enumerate(shards):
            if len(shard) < 2:
                final_clusters.append(shard)
                refined_silhouettes[refined_cluster_idx] = shard_silhouettes.get(shard_idx, 0.0)
                refined_cluster_idx += 1
                continue

            shard_cluster_indices = llm_cluster_entities(
                shard,
                self.llm_client,
                entity_type,
                min_cluster_size=max(2, self.min_cluster_size),
                max_cluster_size=self.max_cluster_size,
            )

            for sub_cluster_indices in shard_cluster_indices:
                sub_cluster = [shard[idx] for idx in sub_cluster_indices]
                if len(sub_cluster) > self.max_cluster_size:
                    mid = (len(sub_cluster) + 1) // 2
                    split_clusters = [sub_cluster[:mid], sub_cluster[mid:]]
                    for split_cluster in split_clusters:
                        final_clusters.append(split_cluster)
                        refined_silhouettes[refined_cluster_idx] = shard_silhouettes.get(shard_idx, 0.0)
                        refined_cluster_idx += 1
                else:
                    final_clusters.append(sub_cluster)
                    refined_silhouettes[refined_cluster_idx] = shard_silhouettes.get(shard_idx, 0.0)
                    refined_cluster_idx += 1

        repaired_clusters = self._repair_small_clusters(entities, final_clusters, entity_type)
        repaired_silhouettes = {
            idx: refined_silhouettes.get(idx, 0.0)
            for idx in range(len(repaired_clusters))
        }
        return repaired_clusters, repaired_silhouettes

    @abstractmethod
    def prepare_features(self, entities: List[Dict]) -> np.ndarray:
        """
        Prepare features for clustering. Must be implemented by subclasses.
        
        Args:
            entities: List of entity dictionaries (projects, roadmaps, etc.)
            
        Returns:
            Feature matrix as numpy array
        """
        pass

    def cluster(self, entities: List[Dict], n_clusters_range: range = range(2, 5), entity_type: str = "roadmap") -> Tuple[List[List[Dict]], float, int, Dict[int, float]]:
        """Cluster entities using hybrid ML + LLM approach.
        
        Two-stage process:
        1. If entities <= ml_precluster_threshold: Skip ML and let the LLM do final semantic clustering.
        2. If entities > ml_precluster_threshold: Use ML only to create coarse shards near max_cluster_size, then let the LLM do final semantic clustering on each shard.
        
        Args:
            entities: List of entity dictionaries
            n_clusters_range: Range of cluster counts to try for ML pre-clustering
            entity_type: "roadmap" or "project" for LLM formatting
            
        Returns:
            Tuple of (clusters, best_silhouette_score, best_n_clusters, per_cluster_silhouettes)
        """
        if not entities:
            return [entities], -1.0, 1, {}
        
        # Stage 1: Skip ML unless the portfolio is large enough to need pre-sharding.
        if len(entities) <= self.ml_precluster_threshold:
            appLogger.info({
                "event": "CLUSTERING_SKIP_ML",
                "stage": "CLUSTER",
                "entity_count": len(entities),
                "ml_precluster_threshold": self.ml_precluster_threshold,
                "reason": "Portfolio small enough for direct LLM clustering",
            })
            
            if self.use_llm_refinement and self.llm_client:
                try:
                    cluster_indices = llm_cluster_entities(
                        entities,
                        self.llm_client,
                        entity_type,
                        min_cluster_size=max(2, self.min_cluster_size),
                        max_cluster_size=self.max_cluster_size,
                    )
                    final_clusters = [[entities[idx] for idx in cluster] for cluster in cluster_indices]
                    final_clusters = self._repair_small_clusters(entities, final_clusters, entity_type)
                    
                    appLogger.info({"event": "CLUSTERING_LLM_DIRECT", "stage": "CLUSTER", "entity_count": len(entities), "n_clusters": len(final_clusters), "cluster_sizes": [len(c) for c in final_clusters]})
                    
                    return final_clusters, 1.0, len(final_clusters), {i: 1.0 for i in range(len(final_clusters))}
                except Exception as e:
                    appLogger.error({
                        "event": "CLUSTERING_LLM_DIRECT_FAILED",
                        "stage": "CLUSTER",
                        "entity_type": entity_type,
                        "entity_count": len(entities),
                        "error": str(e),
                        "traceback": traceback.format_exc(),
                    })
            
            # Fallback: return as single cluster
            return [entities], 1.0, 1, {0: 1.0}
        
        # Stage 2: ML pre-clustering for large portfolios only.

        try:
            features = self.prepare_features(entities)
            
            # LOG: Only log on error or success, not verbose feature details
            if features.size == 0:
                appLogger.info({"event": "CLUSTER_EMPTY_FEATURES", "stage": "CLUSTER", "entity_count": len(entities)})
                return [entities], -1.0, 1, {}
                    
        except Exception as e:
            appLogger.error({
                "event": "CLUSTER_FEATURE_PREP_FAILED",
                "stage": "CLUSTER",
                "entity_type": entity_type,
                "entity_count": len(entities),
                "error": str(e),
                "traceback": traceback.format_exc(),
            })
            return [entities], -1.0, 1, {}

        best_score = -1.0
        best_clusters = [entities]
        best_n = 1
        best_labels = None
        best_features = features

        candidate_cluster_counts = self._get_precluster_candidates(len(entities))
        appLogger.info({
            "event": "CLUSTERING_PRECLUSTER_START",
            "stage": "CLUSTER",
            "entity_type": entity_type,
            "entity_count": len(entities),
            "candidate_cluster_counts": candidate_cluster_counts,
            "max_cluster_size": self.max_cluster_size,
        })

        for n in candidate_cluster_counts:
            if n > len(entities):
                break
            try:
                kmeans = KMeans(n_clusters=n, random_state=42)
                labels = kmeans.fit_predict(features)
                score = silhouette_score(features, labels) if len(set(labels)) > 1 else -1.0
                if score > best_score:
                    best_score = score
                    best_labels = labels
                    best_clusters = [[] for _ in range(n)]
                    for entity, lbl in zip(entities, labels):
                        best_clusters[lbl].append(entity)
                    best_n = n
            except Exception as e:
                appLogger.warning({
                    "event": "CLUSTERING_PRECLUSTER_CANDIDATE_FAILED",
                    "stage": "CLUSTER",
                    "entity_type": entity_type,
                    "candidate_n": n,
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                })
                continue

        appLogger.info({
            "event": "CLUSTERING_PRECLUSTER_CHOSEN",
            "stage": "CLUSTER",
            "entity_type": entity_type,
            "best_n": best_n,
            "best_score": round(best_score, 3) if best_score != -1.0 else best_score,
            "precluster_sizes": [len(cluster) for cluster in best_clusters],
        })

        # Calculate per-cluster silhouette scores
        per_cluster_silhouettes = {}
        if best_n > 1 and len(entities) > 1 and best_labels is not None:
            try:
                from sklearn.metrics import silhouette_samples
                cluster_silhouettes = silhouette_samples(best_features, best_labels)
                for cluster_id in range(best_n):
                    cluster_mask = best_labels == cluster_id
                    per_cluster_silhouettes[cluster_id] = float(np.mean(cluster_silhouettes[cluster_mask])) if cluster_mask.sum() > 0 else 0.0
            except Exception as e:
                appLogger.warning({
                    "event": "CLUSTERING_SILHOUETTE_FAILED",
                    "stage": "CLUSTER",
                    "entity_type": entity_type,
                    "error": str(e),
                })
                per_cluster_silhouettes = {}
        
        # Stage 3: LLM performs final semantic clustering on each ML shard.
        if self.use_llm_refinement and self.llm_client:
            try:
                appLogger.info({
                    "event": "CLUSTERING_LLM_REFINE_START",
                    "stage": "CLUSTER",
                    "entity_type": entity_type,
                    "ml_clusters": best_n,
                    "ml_silhouette": round(best_score, 3) if best_score != -1.0 else best_score,
                    "precluster_sizes": [len(cluster) for cluster in best_clusters],
                })

                final_clusters, refined_silhouettes = self._llm_refine_clusters(
                    entities,
                    best_clusters,
                    entity_type,
                    per_cluster_silhouettes,
                )

                appLogger.info({
                    "event": "CLUSTERING_LLM_REFINE_COMPLETE",
                    "stage": "CLUSTER",
                    "entity_type": entity_type,
                    "ml_clusters": best_n,
                    "final_clusters": len(final_clusters),
                    "cluster_sizes": [len(c) for c in final_clusters],
                })

                return final_clusters, best_score, len(final_clusters), refined_silhouettes

            except Exception as e:
                appLogger.error({
                    "event": "CLUSTERING_LLM_REFINE_FAILED",
                    "stage": "CLUSTER",
                    "entity_type": entity_type,
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                })
                # Fall back to ML shards if refinement fails.
                repaired_clusters = self._repair_small_clusters(entities, best_clusters, entity_type)
                repaired_silhouettes = {i: per_cluster_silhouettes.get(i, 0.0) for i in range(len(repaired_clusters))}
                return repaired_clusters, best_score, len(repaired_clusters), repaired_silhouettes

        repaired_clusters = self._repair_small_clusters(entities, best_clusters, entity_type)
        repaired_silhouettes = {i: per_cluster_silhouettes.get(i, 0.0) for i in range(len(repaired_clusters))}
        return repaired_clusters, best_score, len(repaired_clusters), repaired_silhouettes


class ProjectClusterEngine(BaseClusterEngine):
    """Clustering engine for projects with project-specific features."""

    def prepare_features(self, projects: List[Dict]) -> np.ndarray:
        if not projects:
            return np.array([])

        techs = [p.get("technologies", []) or [] for p in projects]
        kpis = [p.get("key_results", []) or [] for p in projects]
        milestones = [p.get("milestones", []) or [] for p in projects]
        categories = [p.get("categories", []) or [] for p in projects]
        sdlc_methods = [(p.get("sdlc_method", [{}])[0] if p.get("sdlc_method") else {}).get("name", "Unknown") or "Unknown" for p in projects]
        project_types = [(p.get("project_type", [{}])[0] if p.get("project_type") else {}).get("name", "Unknown") or "Unknown" for p in projects]
        team_roles = [[t.get("role", "Unknown") or "Unknown" for t in p.get("team", [])] for p in projects]

        mlb = MultiLabelBinarizer()
        # Filter out None values from technology names
        tech_features = mlb.fit_transform([[t.get("name") or "Unknown" for t in p if t] for p in techs])
        kpi_features = mlb.fit_transform([[k.get("kpi_name") or "Unknown" for k in p if k] for p in kpis])
        milestone_features = mlb.fit_transform([[m.get("milestone_name") or "Unknown" for m in p if m] for p in milestones])
        category_features = mlb.fit_transform([[c.get("name") or "Unknown" for c in p if c] for p in categories])
        role_features = mlb.fit_transform(team_roles)
        sdlc_features = mlb.fit_transform([[m or "Unknown"] for m in sdlc_methods])
        type_features = mlb.fit_transform([[t or "Unknown"] for t in project_types])

        # numerical features
        durations, success_rates, budgets, risk_scores, milestone_times, team_sizes = [], [], [], [], [], []
        for p in projects:
            start_date = p.get("start_date")
            end_date = p.get("end_date")
            try:
                if start_date and end_date:
                    duration = int((np.datetime64(str(end_date)) - np.datetime64(str(start_date))))
                else:
                    duration = 0
            except Exception:
                duration = 0
            durations.append(duration)

            success_rates_list = p.get("key_results", []) or []
            success = np.nanmean([k.get("success_rate", 0) or 0 for k in success_rates_list]) if success_rates_list else 0
            success_rates.append(success if not np.isnan(success) else 0)

            budget = (p.get("budget") or p.get("total_external_spend")) or 0
            try:
                budgets.append(float(budget))
            except:
                budgets.append(0)

            risks = p.get("risks", []) or []
            if risks:
                risk_values = []
                for r in risks:
                    impact = r.get("impact")
                    if isinstance(impact, (int, float)):
                        risk_values.append(impact)
                    elif impact:
                        try:
                            risk_values.append(float(impact))
                        except:
                            risk_values.append(1)
                    else:
                        risk_values.append(1)
                risk_score = np.nanmean(risk_values)
            else:
                risk_score = 0
            risk_scores.append(risk_score if not np.isnan(risk_score) else 0)

            milestones_list = p.get("milestones", []) or []
            milestone_time = np.nanmean([m.get("duration_days", 0) or 0 for m in milestones_list]) if milestones_list else 0
            milestone_times.append(milestone_time if not np.isnan(milestone_time) else 0)

            team_size = len(p.get("team", []) or [])
            team_sizes.append(team_size)

        numerical_features = np.array([durations, success_rates, budgets, risk_scores, milestone_times, team_sizes]).T
        scaler = MinMaxScaler()
        numerical_features = scaler.fit_transform(numerical_features)

        # concatenate all features
        features = np.hstack([
            tech_features if tech_features.size else np.zeros((len(projects), 0)),
            kpi_features if kpi_features.size else np.zeros((len(projects), 0)),
            milestone_features if milestone_features.size else np.zeros((len(projects), 0)),
            category_features if category_features.size else np.zeros((len(projects), 0)),
            role_features if role_features.size else np.zeros((len(projects), 0)),
            sdlc_features if sdlc_features.size else np.zeros((len(projects), 0)),
            type_features if type_features.size else np.zeros((len(projects), 0)),
            numerical_features,
        ])

        return features

    def cluster_projects(self, projects: List[Dict], n_clusters_range: range = range(2, 5)) -> Tuple[List[List[Dict]], float, int, Dict[int, float]]:
        """
        Cluster projects and choose the best cluster count by silhouette score.
        
        This is a convenience method that calls the base cluster() method.
        
        Returns:
            Tuple of (clusters, best_silhouette_score, best_n_clusters, per_cluster_silhouettes)
        """
        return self.cluster(projects, n_clusters_range, entity_type="project")


class RoadmapClusterEngine(BaseClusterEngine):
    """Clustering engine for roadmaps with roadmap-specific features."""

    def prepare_features(self, roadmaps: List[Dict]) -> np.ndarray:
        """
        Prepare features for roadmap clustering.
        
        Features precisely tuned to roadmap data structure from fetch_all_roadmap_data():
        - Portfolios (multi-label): portfolio names
        - Constraints (multi-label): constraint names + constraint types
        - Key results/KPIs (multi-label): kpi names
        - Scopes (multi-label): scope names
        - Categories (multi-label): category names
        - Roadmap types (multi-label): roadmap type names
        - Team labour types (multi-label): Labour/Non Labour
        - Effort types (multi-label): person_days/person_months
        - Priorities (categorical): High/Medium/Low
        - Statuses (categorical): Intake/Approved/Execution/etc
        - Numerical: duration, KPI count, team size, constraint count, budget, total effort estimate
        - Semantic: solution text embeddings
        """
        if not roadmaps:
            return np.array([])

        # Multi-label features from related entities
        portfolios = [r.get("portfolios", []) or [] for r in roadmaps]
        constraints = [r.get("constraints", []) or [] for r in roadmaps]
        key_results = [r.get("key_results", []) or [] for r in roadmaps]
        scopes = [r.get("scopes", []) or [] for r in roadmaps]
        categories = [r.get("categories", []) or [] for r in roadmaps]
        roadmap_types = [r.get("roadmap_types", []) or [] for r in roadmaps]
        
        # Team features: labour_type and effort_type from team data
        team_labour_types = [[(t.get("labour_type", "Unknown") or "Unknown").lower().strip() for t in r.get("team", [])] for r in roadmaps]
        team_effort_types = [[(t.get("effort_type", "Unknown") or "Unknown").lower().strip() for t in r.get("team", [])] for r in roadmaps]
        
        # Categorical features - safely handle list structure
        priorities = []
        for r in roadmaps:
            priority_list = r.get("priorities", [])
            if priority_list and len(priority_list) > 0:
                priorities.append((priority_list[0].get("priority_level", "Unknown") or "Unknown").lower().strip())
            else:
                priorities.append("unknown")
        
        statuses = []
        for r in roadmaps:
            status_list = r.get("statuses", [])
            if status_list and len(status_list) > 0:
                statuses.append((status_list[0].get("status", "Unknown") or "Unknown").lower().strip())
            else:
                statuses.append("unknown")

        # Encode multi-label features with normalization
        mlb = MultiLabelBinarizer()
        portfolio_features = mlb.fit_transform([[(p.get("name") or "Unknown").lower().strip() for p in r if p] for r in portfolios])
        
        # Constraint features: use both constraint_name and constraint_type for richer clustering
        constraint_names = [[(c.get("constraint_name") or "Unknown").lower().strip() for c in r if c] for r in constraints]
        constraint_types = [[(c.get("constraint_type") or "Unknown").lower().strip() for c in r if c] for r in constraints]
        constraint_name_features = mlb.fit_transform(constraint_names)
        constraint_type_features = mlb.fit_transform(constraint_types)
        
        kpi_features = mlb.fit_transform([[(k.get("kpi_name") or "Unknown").lower().strip() for k in r if k] for r in key_results])
        scope_features = mlb.fit_transform([[(s.get("scope_name") or "Unknown").lower().strip() for s in r if s] for r in scopes])
        category_features = mlb.fit_transform([[(c.get("name") or "Unknown").lower().strip() for c in r if c] for r in categories])
        type_features = mlb.fit_transform([[(t.get("name") or "Unknown").lower().strip() for t in r if t] for r in roadmap_types])
        labour_type_features = mlb.fit_transform(team_labour_types)
        effort_type_features = mlb.fit_transform(team_effort_types)
        priority_features = mlb.fit_transform([[p] for p in priorities])
        status_features = mlb.fit_transform([[s] for s in statuses])

        # Numerical features: duration, counts, budget, effort estimates
        durations, kpi_counts, team_sizes, constraint_counts, budgets, total_efforts = [], [], [], [], [], []
        for r in roadmaps:
            # Duration calculation
            start_date = r.get("start_date")
            end_date = r.get("end_date")
            try:
                duration = (np.datetime64(end_date) - np.datetime64(start_date)).astype(int) if start_date and end_date else 0
            except Exception:
                duration = 0
            durations.append(duration)

            # Counts
            kpi_counts.append(len(r.get("key_results", [])))
            team_sizes.append(len(r.get("team", [])))
            constraint_counts.append(len(r.get("constraints", [])))
            
            # Budget from base roadmap field
            budget = r.get("budget", 0)
            try:
                budgets.append(float(budget) if budget is not None else 0)
            except:
                budgets.append(0)
            
            # Total effort estimate from team labour_estimate_value
            team_data = r.get("team", [])
            total_effort = 0
            for t in team_data:
                estimate_val = t.get("labour_estimate_value", 0)
                try:
                    total_effort += float(estimate_val) if estimate_val is not None else 0
                except:
                    pass
            total_efforts.append(total_effort)

        numerical_features = np.array([durations, kpi_counts, team_sizes, constraint_counts, budgets, total_efforts]).T
        scaler = MinMaxScaler()
        numerical_features = scaler.fit_transform(numerical_features) if numerical_features.size > 0 else numerical_features

        # Extract semantic embeddings from solution field
        # Note: roadmaps have 'solution' as base field containing solution text
        solution_features = None
        try:
            extractor = SemanticFeatureExtractor()
            solution_embeddings = extractor.extract_solution_embeddings(roadmaps, solution_key="solution")
            if solution_embeddings is not None:
                # Normalize embeddings and scale to 0-1
                solution_features = (solution_embeddings - solution_embeddings.min(axis=0)) / (solution_embeddings.max(axis=0) - solution_embeddings.min(axis=0) + 1e-8)
                appLogger.info({"event": "CLUSTERING_SEMANTIC_SOLUTIONS", "stage": "CLUSTER", "roadmap_count": len(roadmaps), "embedding_dims": solution_features.shape[1], "embedding_status": "integrated"})
        except Exception as e:
            appLogger.warning({
                "event": "CLUSTERING_SEMANTIC_SOLUTIONS_FAILED",
                "stage": "CLUSTER",
                "roadmap_count": len(roadmaps),
                "error": str(e),
            })

        # Concatenate all features in logical order
        feature_list = [
            portfolio_features if portfolio_features.size else np.zeros((len(roadmaps), 0)),
            constraint_name_features if constraint_name_features.size else np.zeros((len(roadmaps), 0)),
            constraint_type_features if constraint_type_features.size else np.zeros((len(roadmaps), 0)),
            kpi_features if kpi_features.size else np.zeros((len(roadmaps), 0)),
            scope_features if scope_features.size else np.zeros((len(roadmaps), 0)),
            category_features if category_features.size else np.zeros((len(roadmaps), 0)),
            type_features if type_features.size else np.zeros((len(roadmaps), 0)),
            labour_type_features if labour_type_features.size else np.zeros((len(roadmaps), 0)),
            effort_type_features if effort_type_features.size else np.zeros((len(roadmaps), 0)),
            priority_features if priority_features.size else np.zeros((len(roadmaps), 0)),
            status_features if status_features.size else np.zeros((len(roadmaps), 0)),
            numerical_features,
        ]
        
        # Add solution embeddings if available
        if solution_features is not None:
            feature_list.append(solution_features)
        
        features = np.hstack(feature_list)

        return features

    def cluster_roadmaps(self, roadmaps: List[Dict], n_clusters_range: range = range(2, 5)) -> Tuple[List[List[Dict]], float, int, Dict[int, float]]:
        """
        Cluster roadmaps and choose the best cluster count by silhouette score.
        
        This is a convenience method that calls the base cluster() method.
        
        Returns:
            Tuple of (clusters, best_silhouette_score, best_n_clusters, per_cluster_silhouettes)
        """
        return self.cluster(roadmaps, n_clusters_range, entity_type="roadmap")
