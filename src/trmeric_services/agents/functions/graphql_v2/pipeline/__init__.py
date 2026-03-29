"""
Pipeline Module

Orchestrates the complete analysis workflow: fetch → cluster → generate → load
"""

from .analysis_pipeline import AnalysisPipeline

__all__ = ["AnalysisPipeline"]
