"""
Quality signal analysis - milestone patterns and complication detection.
"""

from typing import Optional
from datetime import datetime
import statistics
from .models import (
    MilestoneSignal,
    ComplicationSignal,
    QualitySignals,
    SignalPattern,
    ComplicationPattern,
    ProjectContext
)


class SignalAnalysis:
    """Extract quality signals from project context"""
    
    @staticmethod
    def analyze_milestone_health(context: ProjectContext) -> Optional[MilestoneSignal]:
        """
        Analyze milestone completion patterns.
        
        Returns milestone signal with pattern classification:
        - CONSISTENT: avg < 1 day, max < 3 days → +3 confidence
        - MINOR_DRIFT: 1-5 days → +1 confidence
        - SLIPPING: > 5 days → -2 confidence
        - CASCADE_FAILURE: multiple delays compounding → -5 confidence
        """
        # Filter for schedule milestones (type == 2) that have actual dates
        completed = [
            m for m in context.milestones 
            if m.get("type") == 2 and m.get("actual_date")  # Schedule type with actual date = completed
        ]
        
        if not completed:
            return None
        
        # Calculate delays
        delays = []
        for m in completed:
            if m.get("actual_date") and m.get("target_date"):
                try:
                    # Handle both datetime objects and strings
                    actual = m.get("actual_date")
                    target = m.get("target_date")
                    
                    if isinstance(actual, str):
                        from datetime import datetime
                        actual_dt = datetime.fromisoformat(actual.split('T')[0])
                        target_dt = datetime.fromisoformat(target.split('T')[0])
                    else:
                        actual_dt = actual
                        target_dt = target
                    
                    delay = (actual_dt - target_dt).days
                    delays.append(delay)
                except:
                    pass
        
        if not delays:
            return None
        
        # Statistics
        on_time_count = sum(1 for d in delays if d <= 0)
        on_time_ratio = on_time_count / len(delays) if delays else 0
        avg_delay = statistics.mean(delays) if delays else 0
        max_delay = max(delays) if delays else 0
        
        # Detect cascade failures
        cascade_failures = 0
        if len(delays) > 1:
            std_dev = statistics.stdev(delays) if len(delays) > 1 else 0
            threshold = avg_delay + std_dev
            cascade_failures = sum(1 for d in delays if d > threshold)
        
        # Pattern classification
        if cascade_failures > 2:
            pattern = SignalPattern.CASCADE_FAILURE
            confidence_impact = -5
            description = f"Cascade failure: {cascade_failures} milestones cascaded delays"
        elif avg_delay > 5:
            pattern = SignalPattern.SLIPPING
            confidence_impact = -2
            description = f"Slipping: avg {int(avg_delay)} days late"
        elif avg_delay >= 1:
            pattern = SignalPattern.MINOR_DRIFT
            confidence_impact = 1
            description = f"Minor drift: avg {int(avg_delay)} days late"
        else:
            pattern = SignalPattern.CONSISTENT
            confidence_impact = 3
            description = f"Consistent: {int(on_time_ratio*100)}% on-time"
        
        return MilestoneSignal(
            pattern=pattern,
            on_time_ratio=on_time_ratio,
            avg_delay_days=int(avg_delay),
            max_delay_days=int(max_delay),
            completed_count=len(completed),
            confidence_impact=confidence_impact,
            description=description
        )
    
    @staticmethod
    def analyze_status_complications(context: ProjectContext) -> Optional[ComplicationSignal]:
        """
        Analyze status update comments for complications.
        
        Pattern classification:
        - FREQUENT_COMPLICATIONS: >50% have issues → -2 confidence
        - OCCASIONAL_CHALLENGES: 30-50% → 0 confidence
        - WELL_MANAGED_ISSUES: issues but >80% resolved → +2 confidence
        - NO_CLEAR_PATTERN: sparse data → 0 confidence
        """
        if not context.status_comments:
            return None
        
        risk_keywords = ["blocker", "blocked", "risk", "delay", "delayed", "blocker", "stuck"]
        resolved_keywords = ["resolved", "mitigated", "fixed", "completed", "done", "resolved"]
        
        # Scan recent comments
        recent = context.status_comments[-10:] if len(context.status_comments) > 10 else context.status_comments
        
        blocker_count = sum(
            1 for comment in recent
            if any(kw in comment.lower() for kw in risk_keywords)
        )
        
        resolved_count = sum(
            1 for comment in recent
            if any(kw in comment.lower() for kw in resolved_keywords)
        )
        
        if len(recent) == 0:
            return None
        
        complication_ratio = blocker_count / len(recent)
        resolution_rate = resolved_count / blocker_count if blocker_count > 0 else 0
        
        # Pattern classification
        if complication_ratio > 0.5:
            pattern = ComplicationPattern.FREQUENT_COMPLICATIONS
            confidence_impact = -2
            description = f"Frequent complications: {blocker_count}/{len(recent)} updates mention issues"
        elif complication_ratio > 0.3:
            pattern = ComplicationPattern.OCCASIONAL_CHALLENGES
            confidence_impact = 0
            description = f"Occasional challenges: {blocker_count} blockers, {resolved_count} resolved"
        elif resolution_rate > 0.8 and blocker_count > 0:
            pattern = ComplicationPattern.WELL_MANAGED_ISSUES
            confidence_impact = 2
            description = f"Well-managed issues: {blocker_count} blockers resolved ({int(resolution_rate*100)}%)"
        else:
            pattern = ComplicationPattern.NO_CLEAR_PATTERN
            confidence_impact = 0
            description = "No clear pattern in status updates"
        
        return ComplicationSignal(
            pattern=pattern,
            blocker_count=blocker_count,
            resolution_rate=resolution_rate,
            total_complications=blocker_count,
            confidence_impact=confidence_impact,
            description=description
        )
    
    @staticmethod
    def analyze_signals(context: ProjectContext) -> QualitySignals:
        """
        Analyze all quality signals for the project.
        Returns QualitySignals object.
        """
        milestone_signal = SignalAnalysis.analyze_milestone_health(context)
        complication_signal = SignalAnalysis.analyze_status_complications(context)
        
        return QualitySignals(
            milestone_health=milestone_signal,
            status_complications=complication_signal
        )
