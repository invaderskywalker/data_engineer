"""
Maturity score calculation - for completed projects (Tier 3).
Assesses retrospective insights and value realization using LLM analysis.
"""

from typing import Optional
from .models import MaturityScore, ProjectContext
from .retrospective_analyzer import RetrospectiveAnalyzer


class MaturityCalculation:
    """Calculate project maturity score (Tier 3, completed projects only)"""
    
    def __init__(self):
        self.retrospective_analyzer = RetrospectiveAnalyzer()
    
    def calculate_maturity_score(self, context: ProjectContext) -> Optional[MaturityScore]:
        """
        Calculate maturity score for completed projects.
        Only applicable if project_status is "completed" or "archived".
        
        Returns None if project is still active.
        
        Components:
        - Retrospective score: 60% weight (LLM-analyzed)
          * Uses RetrospectiveAnalyzer to assess:
            - Learning quality (25%)
            - Sentiment & outcomes (25%)
            - Actionability (20%)
            - Team involvement (15%)
            - Risk awareness (10%)
            - Sustainability (5%)
          * Plus optional team score bonus (up to 5%)
        
        - Value realization score: 40% weight
          * >= 100%: 100 points (exceeded targets)
          * >= 90%: 90 points (strong)
          * >= 75%: 75 points (acceptable)
          * >= 60%: 60 points (partial)
          * < 60%: 40 points (underperformed)
        """
        
        if context.project_status not in ["completed", "archived"]:
            return None
        
        # --- RETROSPECTIVE SCORE (with LLM analysis) ---
        retro_score = 0
        
        if context.retro_data:
            # Use LLM to analyze retrospective text for structured insights
            analysis = self.retrospective_analyzer.analyze_retrospective(context.retro_data)
            
            # Calculate composite score using LLM-derived dimensions
            team_score = context.retro_data.get("team_score")
            retro_score = self.retrospective_analyzer.calculate_composite_retro_score(
                analysis, 
                team_score=team_score
            )
        
        retro_score = min(100, max(0, retro_score))
        
        # --- VALUE REALIZATION SCORE ---
        value_score = 0
        
        if context.value_realization_data:
            kpis = context.value_realization_data.get("kpis", [])
            
            if kpis:
                realization_rates = []
                
                for kpi in kpis:
                    target = kpi.get("target_value")
                    actual = kpi.get("actual_value")
                    
                    if target and actual and target > 0:
                        rate = (actual / target) * 100
                        realization_rates.append(rate)
                
                if realization_rates:
                    avg_realization = sum(realization_rates) / len(realization_rates)
                    
                    if avg_realization >= 100:
                        value_score = 100
                    elif avg_realization >= 90:
                        value_score = 90
                    elif avg_realization >= 75:
                        value_score = 75
                    elif avg_realization >= 60:
                        value_score = 60
                    else:
                        value_score = 40
        
        # --- AGGREGATE MATURITY SCORE ---
        overall_maturity = int((retro_score * 0.60) + (value_score * 0.40))
        
        # Label
        if overall_maturity >= 85:
            label = "Excellent Learning Project"
        elif overall_maturity >= 70:
            label = "Good Retrospective"
        elif overall_maturity >= 50:
            label = "Partial Data Available"
        else:
            label = "Limited Learning Data"
        
        return MaturityScore(
            retrospective_score=retro_score,
            value_realization_score=value_score,
            overall_maturity=overall_maturity,
            label=label
        )
