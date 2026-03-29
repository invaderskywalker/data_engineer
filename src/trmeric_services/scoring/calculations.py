"""
Individual dimension calculation logic.
Each method takes ProjectContext and returns 0-100 score.
"""

from typing import List, Dict, Any
from datetime import datetime
import statistics


class DimensionCalculations:
    """Pure calculation logic for each dimension"""
    
    @staticmethod
    def calculate_on_time(context) -> tuple[int, str]:
        """
        ON-TIME SCORE (0-100)
        
        Returns: (score, explanation)
        """
        status_value = context.delivery_status
        explanation_parts = []
        
        # Status component
        if status_value == 1:  # on_track
            status_component = 85
            explanation_parts.append("Delivery status is ON TRACK (base: 85)")
        elif status_value == 2:  # at_risk
            status_component = 50
            explanation_parts.append("Delivery status is AT RISK (base: 50)")
        else:  # compromised
            status_component = 20
            explanation_parts.append("Delivery status is COMPROMISED (base: 20)")
        
        # Milestone component (if available)
        completed_milestones = [
            m for m in context.milestones 
            if m.get("type") == 2  # schedule milestones
        ]
        
        if not completed_milestones:
            explanation_parts.append("No schedule milestones available for verification")
            return status_component, "; ".join(explanation_parts)
        
        # Calculate on-time ratio
        on_time_count = 0
        late_count = 0
        for m in completed_milestones:
            target = m.get("target_date")
            actual = m.get("actual_date")
            if actual and target:
                try:
                    if isinstance(actual, str):
                        from datetime import datetime
                        actual = datetime.fromisoformat(actual.split('T')[0])
                        target = datetime.fromisoformat(target.split('T')[0])
                    if actual <= target:
                        on_time_count += 1
                    else:
                        late_count += 1
                except:
                    pass
        
        on_time_ratio = on_time_count / len(completed_milestones) if completed_milestones else 0
        milestone_component = min(100, int(on_time_ratio * 100))
        
        explanation_parts.append(f"{on_time_count}/{len(completed_milestones)} milestones completed on-time ({on_time_ratio:.0%})")
        
        # Aggregate
        score = int((status_component * 0.4) + (milestone_component * 0.6))
        explanation_parts.append(f"Final: 40% status ({status_component}) + 60% milestones ({milestone_component}) = {score}")
        
        return min(100, max(0, score)), "; ".join(explanation_parts)
    
    @staticmethod
    def calculate_on_scope(context) -> tuple[int, str]:
        """
        ON-SCOPE SCORE (0-100)
        
        Returns: (score, explanation)
        """
        status_value = context.scope_status
        
        # Status component - this is all we have
        if status_value == 1:  # on_track
            score = 90
            explanation = "Scope status is ON TRACK (90/100). Note: No baseline/current scope variance data available in schema."
        elif status_value == 2:  # at_risk
            score = 55
            explanation = "Scope status is AT RISK (55/100). Note: No baseline/current scope variance data available in schema."
        else:  # compromised
            score = 25
            explanation = "Scope status is COMPROMISED (25/100). Note: No baseline/current scope variance data available in schema."
        
        return min(100, max(0, score)), explanation
    
    @staticmethod
    def calculate_on_budget(context) -> tuple[int, str]:
        """
        ON-BUDGET SCORE (0-100)
        
        Returns: (score, explanation)
        """
        status_value = context.spend_status
        explanation_parts = []
        
        # Status component
        if status_value == 1:  # on_track
            status_component = 90
            explanation_parts.append("Spend status is ON TRACK (base: 90)")
        elif status_value == 2:  # at_risk
            status_component = 50
            explanation_parts.append("Spend status is AT RISK (base: 50)")
        else:  # compromised
            status_component = 20
            explanation_parts.append("Spend status is COMPROMISED (base: 20)")
        
        # Calculate variance from milestones
        variance_score = 50  # Default if no data
        
        # Aggregate spend from all milestones
        total_planned = sum(
            float(m.get("planned_spend") or 0)
            for m in context.milestones
        )
        total_actual = sum(
            float(m.get("actual_spend") or 0)
            for m in context.milestones
        )
        
        if total_planned and total_planned > 0:
            variance = total_actual / total_planned
            explanation_parts.append(f"Milestone spend: ${total_actual:,.0f} actual vs ${total_planned:,.0f} planned ({variance:.1%} of budget)")
            
            if variance <= 0.95:
                variance_score = 100
                explanation_parts.append("Under budget by 5%+ (variance score: 100)")
            elif variance <= 1.0:
                variance_score = 95
                explanation_parts.append("Within budget (variance score: 95)")
            elif variance <= 1.1:
                variance_score = 80
                explanation_parts.append("10% over budget (variance score: 80, -15 penalty)")
            elif variance <= 1.2:
                variance_score = 60
                explanation_parts.append("20% over budget (variance score: 60, -35 penalty)")
            else:
                variance_score = 40
                explanation_parts.append("More than 20% over budget (variance score: 40, -55 penalty)")
        else:
            explanation_parts.append("No milestone spend data available")
        
        score = int((status_component * 0.5) + (variance_score * 0.5))
        explanation_parts.append(f"Final: 50% status ({status_component}) + 50% variance ({variance_score}) = {score}")
        
        return min(100, max(0, score)), "; ".join(explanation_parts)
    
    @staticmethod
    def calculate_risk_management(context) -> tuple[int, str]:
        """
        RISK MANAGEMENT SCORE (0-100)
        
        Returns: (score, explanation)
        """
        if not context.risks:
            return 100, "No risks identified (score: 100)"
        
        total_risks = len(context.risks)
        explanation_parts = [f"Total risks: {total_risks}"]
        
        # Map risk data from DAO response
        critical_open = 0
        open_risks = 0
        
        for r in context.risks:
            # Impact comes as string from DAO query
            impact = r.get("impact", "").lower()
            is_high_impact = impact in ["high", "3", 3]
            
            # Status: status_value field is numeric (check what values mean)
            # From model: status_value is used but mapping is unclear
            # Assume: 6=Closed, anything else is open
            status_val = r.get("status")  # This is the string status from DAO (e.g. "Active", "Closed")
            is_open = status_val and status_val.lower() not in ["closed", "resolved", "mitigated"]
            
            if is_high_impact and is_open:
                critical_open += 1
            if is_open:
                open_risks += 1
        
        base = 100
        critical_penalty = critical_open * 25
        open_penalty = open_risks * 5
        
        explanation_parts.append(f"{critical_open} critical (high-impact) open risks (-{critical_penalty} points)")
        explanation_parts.append(f"{open_risks} total open risks (-{open_penalty} points)")
        
        score = base - critical_penalty - open_penalty
        explanation_parts.append(f"Final: {base} - {critical_penalty} - {open_penalty} = {score}")
        
        return min(100, max(0, score)), "; ".join(explanation_parts)
    
    @staticmethod
    def calculate_team_health(context) -> tuple[int, str]:
        """
        TEAM HEALTH SCORE (0-100)
        
        Returns: (score, explanation)
        """
        if not context.team_members:
            return 0, "No team data available (score: 0)"
        
        team_size = len(context.team_members)
        explanation_parts = [f"Team size: {team_size} members"]
        
        # Utilization score
        utilizations = [
            m.get("utilization", 0) for m in context.team_members
            if m.get("utilization") is not None
        ]
        
        if utilizations:
            avg_utilization = statistics.mean(utilizations)
            explanation_parts.append(f"Average utilization: {avg_utilization:.1f}%")
            
            if avg_utilization >= 80:
                utilization_score = 100
                explanation_parts.append("High utilization (80%+, score: 100)")
            elif avg_utilization >= 60:
                utilization_score = 85
                explanation_parts.append("Good utilization (60-80%, score: 85)")
            elif avg_utilization >= 40:
                utilization_score = 70
                explanation_parts.append("Moderate utilization (40-60%, score: 70, -30 penalty)")
            elif avg_utilization >= 20:
                utilization_score = 50
                explanation_parts.append("Low utilization (20-40%, score: 50, -50 penalty)")
            else:
                utilization_score = 30
                explanation_parts.append("Very low utilization (<20%, score: 30, -70 penalty)")
        else:
            utilization_score = 50  # Default if no utilization data
            explanation_parts.append("No utilization data available (default: 50)")
        
        # External ratio penalty
        external_count = sum(1 for m in context.team_members if m.get("is_external", False))
        external_ratio = external_count / team_size if team_size > 0 else 0
        external_penalty = int(external_ratio * 15)
        
        if external_count > 0:
            explanation_parts.append(f"{external_count} external members ({external_ratio:.0%}, penalty: -{external_penalty})")
        
        score = utilization_score - external_penalty
        explanation_parts.append(f"Final: {utilization_score} - {external_penalty} = {score}")
        
        return min(100, max(0, score)), "; ".join(explanation_parts)
    
    @staticmethod
    def aggregate_core_score(
        on_time: int,
        on_scope: int,
        on_budget: int,
        risk: int,
        team: int
    ) -> int:
        """
        Weighted average of all 5 dimensions
        Weights: On-Time 25%, On-Scope 25%, On-Budget 25%, Risk 15%, Team 10%
        """
        score = (
            (on_time * 0.25) +
            (on_scope * 0.25) +
            (on_budget * 0.25) +
            (risk * 0.15) +
            (team * 0.10)
        )
        return int(min(100, max(0, score)))
