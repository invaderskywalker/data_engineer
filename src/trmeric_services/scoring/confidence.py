"""
Confidence score calculation - measures data quality backing the score.
"""

from .models import ConfidenceBreakdown, ProjectContext


class ConfidenceCalculation:
    """Calculate data quality/completeness scores"""
    
    @staticmethod
    def calculate_confidence(context: ProjectContext) -> ConfidenceBreakdown:
        """
        Calculate overall confidence score (0-100%).
        
        Components:
        1. Status Fields: 100% (always present)
        2. Milestone Data: % of milestones with dates filled
        3. Comments: % of status updates with comments
        4. Risks: Presence of risk tracking
        5. Team Data: % of team with utilization data
        6. Retro Bonus: +5 if completed & has retro
        
        Weights:
        - Status: 25%
        - Milestones: 25%
        - Comments: 15%
        - Risks: 20%
        - Team: 15%
        - Bonus: up to +10%
        """
        
        # 1. Status fields (always 100% - always present)
        status_fields = 100
        
        # 2. Milestone data completeness
        milestones = context.milestones
        if milestones:
            completed = [m for m in milestones if m.get("status_value") == 3]
            if completed:
                with_dates = sum(
                    1 for m in completed
                    if m.get("actual_date") and m.get("target_date")
                )
                milestone_completeness = int((with_dates / len(completed)) * 100)
            else:
                milestone_completeness = 50  # Has milestones but none completed
        else:
            milestone_completeness = 0
        
        # 3. Comments availability
        comments = context.status_comments
        if comments:
            non_null = sum(1 for c in comments if c and len(c.strip()) > 0)
            comment_coverage = (non_null / len(comments)) * 100 if comments else 0
        else:
            comment_coverage = 0
        
        # 4. Risk tracking (0 or 100)
        risk_completeness = 100 if context.risks else 0
        
        # 5. Team data completeness
        team = context.team_members
        if team:
            with_utilization = sum(
                1 for m in team
                if m.get("utilization") is not None
            )
            team_completeness = (with_utilization / len(team)) * 100 if team else 0
        else:
            team_completeness = 0
        
        # 6. Retro bonus (for completed projects)
        retro_bonus = 0
        if context.project_status == "completed" and context.retro_data:
            retro_bonus = 5
        
        value_bonus = 0
        if context.project_status == "completed" and context.value_realization_data:
            value_bonus = 5
        
        total_bonus = min(10, retro_bonus + value_bonus)
        
        # Calculate overall with weights
        overall = (
            (status_fields * 0.25) +
            (milestone_completeness * 0.25) +
            (comment_coverage * 0.15) +
            (risk_completeness * 0.20) +
            (team_completeness * 0.15) +
            total_bonus
        )
        
        overall = int(min(100, max(55, overall)))  # Clamp between 55-100
        
        # Interpretation
        if overall >= 90:
            interpretation = "High confidence - complete data"
        elif overall >= 75:
            interpretation = "Good confidence - most data present"
        elif overall >= 60:
            interpretation = "Moderate confidence - some gaps"
        else:
            interpretation = "Low confidence - significant data gaps"
        
        return ConfidenceBreakdown(
            status_fields=status_fields,
            milestones=int(milestone_completeness),
            comments=int(comment_coverage),
            risks=risk_completeness,
            team_data=int(team_completeness),
            retro_bonus=total_bonus,
            overall=overall,
            interpretation=interpretation
        )
