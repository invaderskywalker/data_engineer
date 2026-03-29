"""
LLM-based scoring explanation generator.
Generates natural language explanations of why a project received its score.
"""

from typing import Optional, Dict, Any
from src.trmeric_ml.llm.models.OpenAIClient import ChatGPTClient
from src.trmeric_ml.llm.Types import ChatCompletion, ModelOptions
from src.trmeric_utils.json_parser import extract_json_after_llm
from src.trmeric_api.logging.AppLogger import appLogger


class ScoringExplanationGenerator:
    """Generates human-readable explanations of project scores using LLM"""
    
    def __init__(self):
        self.llm = ChatGPTClient()
    
    @staticmethod
    def build_explanation_prompt() -> str:
        """Build the system prompt for score explanation."""
        return """
You are an expert project scoring analyst with complete visibility into all project data and scoring calculations.
Your task is to provide a DEFINITIVE, AUTHORITATIVE explanation based on the actual data you can see.

SCORING METHODOLOGY (you have full visibility):
- On-Time Delivery: Based on delivery status + milestone completion rates (on-time/at-risk/delayed counts)
- On-Scope: Based on scope tracking status + baseline vs current scope metrics
- On-Budget: Based on spend status + milestone budget performance
- Risk Management: Based on identified risks by severity (Critical/High/Medium/Low)
- Team Health: Based on team capacity, role coverage, member status
- Data Confidence: Calculated from completeness of milestones, risks, team, comments (0-100%)

CRITICAL INSTRUCTIONS:
1. SPEAK WITH AUTHORITY - You have all the data. State facts directly, not possibilities.
   ❌ "suggests potential issues" → ✅ "indicates issues because..."
   ❌ "likely due to" → ✅ "caused by [specific data point]"
   ❌ "raises questions" → ✅ "reveals that..."
   
2. CITE EXACT NUMBERS - Use the actual metrics provided
   ✅ "On-Time score of 34/100 is calculated from 0 of 4 milestones completed on-time"
   ✅ "Team Health score of 0/100 results from zero team members defined"
   ✅ "Risk Management score of 100/100 reflects that no risks are identified"

3. EXPLAIN SCORE CALCULATIONS - Connect the data directly to scores
   - "The On-Budget score of 70/100 results from..." [cite actual budget data]
   - "Data Confidence of 55% reflects that 3 of 5 data categories are missing"

4. IDENTIFY CONTRADICTIONS PRECISELY
   ✅ "Delivery status shows 'On-Track', yet On-Time score is 34/100 because milestone data reveals 0 of 4 milestones are on schedule"

5. STATE WHAT'S MISSING AND ITS IMPACT
   ✅ "No milestones defined, which prevents assessment of schedule progress and contributes to the 55% confidence score"

OUTPUT FORMAT - JSON with:
{
    "explanation": "2-3 paragraphs stating facts about what the data shows and how scores were calculated. Use definitive language.",
    "key_strengths": ["strength with exact metric from data"],
    "key_concerns": ["concern with specific data point that causes it"],
    "data_quality_note": "list what data exists vs missing and state the exact confidence impact"
}

TONE: Authoritative, fact-based, definitive. You're reporting what you directly observe in the data, not speculating.
"""
    
    def generate_explanation(
        self,
        project_title: str,
        project_description: Optional[str],
        core_score: int,
        dimensions: Dict[str, int],
        confidence: int,
        project_status: str,
        scope_status: str,
        delivery_status: str,
        spend_status: str,
        status_comments: list,
        milestones_data: list,
        risks_data: list,
        team_data: list,
        signals: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate explanation for a project's score with full data context.
        
        Args:
            project_title: Name of project
            project_description: Project description/summary
            core_score: Overall score (0-100)
            dimensions: Dict with keys: on_time, on_scope, on_budget, risk_management, team_health
            confidence: Data confidence % (0-100)
            project_status: active/completed/archived
            scope_status: On-Track/At-Risk/Off-Track
            delivery_status: On-Track/At-Risk/Off-Track
            spend_status: On-Track/At-Risk/Off-Track
            status_comments: List of status update comments
            milestones_data: List of milestone dicts with status, deadline, etc
            risks_data: List of risk dicts with severity, description, etc
            team_data: List of team member dicts with role, capacity, etc
            signals: Optional quality signals dict
        
        Returns:
            Dict with explanation, strengths, concerns, and data quality notes
        """
        try:
            # Format milestone details for context
            milestone_details = self._format_milestone_details(milestones_data)
            risk_details = self._format_risk_details(risks_data)
            team_details = self._format_team_details(team_data)
            comment_summary = self._format_comment_summary(status_comments)
            
            # Calculate data completeness breakdown
            data_categories_present = sum([
                1 if milestones_data else 0,
                1 if risks_data else 0,
                1 if team_data else 0,
                1 if status_comments else 0,
                1  # status fields always present
            ])
            data_categories_total = 5
            
            # Build comprehensive user message with all data
            user_message = f"""
PROJECT: {project_title}
Description: {project_description if project_description else 'No description provided'}
Status: {project_status.upper()}

TRACKING STATUS (influences scoring):
- Scope: {scope_status}
- Delivery: {delivery_status}  
- Spend: {spend_status}

FINAL SCORES (these are the calculated results you must explain):
- Overall Score: {core_score}/100
- On-Time Delivery: {dimensions.get('on_time', 0)}/100 ← Calculated from delivery status + milestone completion
- On-Scope: {dimensions.get('on_scope', 0)}/100 ← Calculated from scope tracking status
- On-Budget: {dimensions.get('on_budget', 0)}/100 ← Calculated from spend status + milestone budget data
- Risk Management: {dimensions.get('risk_management', 0)}/100 ← Calculated from identified risks by severity
- Team Health: {dimensions.get('team_health', 0)}/100 ← Calculated from team composition and capacity
- Data Confidence: {confidence}% ← Calculated from {data_categories_present} of {data_categories_total} data categories present

RAW PROJECT DATA (this is what drove the calculations):

MILESTONES ({len(milestones_data)} defined):
{milestone_details}

RISKS ({len(risks_data)} identified):
{risk_details}

TEAM ({len(team_data)} members defined):
{team_details}

STATUS UPDATE HISTORY:
{comment_summary}

{f"QUALITY SIGNALS: {signals}" if signals else "QUALITY SIGNALS: None available"}

YOUR TASK:
State definitively why this project scored {core_score}/100. Connect each dimension score to the specific data that produced it.
- On-Time {dimensions.get('on_time', 0)}/100 is this score because... [cite milestone data + delivery status]
- On-Scope {dimensions.get('on_scope', 0)}/100 is this score because... [cite scope status]
- On-Budget {dimensions.get('on_budget', 0)}/100 is this score because... [cite spend status + budget data]
- Risk {dimensions.get('risk_management', 0)}/100 is this score because... [cite risk inventory]
- Team {dimensions.get('team_health', 0)}/100 is this score because... [cite team composition]

State what data is missing and how it reduces confidence to {confidence}%.
Use definitive language - you have all the information that exists.
"""
            
            # Create chat completion
            chat = ChatCompletion(
                system=self.build_explanation_prompt(),
                prev=[],
                user=user_message
            )
            
            # Call LLM
            response = self.llm.run(
                chat,
                ModelOptions(model="gpt-4o", max_tokens=1500, temperature=0.3),
                'scoring::explanation_generation'
            )
            
            # Parse response
            result = extract_json_after_llm(response)
            
            if not result:
                return self._default_explanation()
            
            # Validate structure
            validated = {
                "explanation": result.get("explanation", ""),
                "key_strengths": result.get("key_strengths", []),
                "key_concerns": result.get("key_concerns", []),
                "data_quality_note": result.get("data_quality_note", "")
            }
            
            # Ensure explanation is present
            if not validated["explanation"]:
                return self._default_explanation()
            
            appLogger.info({
                "event": "scoring_explanation_generated",
                "project": project_title,
                "score": core_score,
                "strengths": len(validated["key_strengths"]),
                "concerns": len(validated["key_concerns"])
            })
            
            return validated
            
        except Exception as e:
            appLogger.error({
                "event": "scoring_explanation_failed",
                "error": str(e),
                "project_title": project_title
            })
            return self._default_explanation()
    
    @staticmethod
    def _format_milestone_details(milestones: list) -> str:
        """Format milestone details for explanation context."""
        if not milestones:
            return "- No milestones defined"
        
        lines = []
        on_time = 0
        at_risk = 0
        delayed = 0
        
        for m in milestones:
            status = m.get("status", "unknown")
            name = m.get("name", "Unnamed")
            deadline = m.get("deadline", "TBD")
            
            if status.lower() == "completed":
                on_time_flag = m.get("on_time", False)
                if on_time_flag:
                    on_time += 1
                    lines.append(f"- {name}: Completed on-time")
                else:
                    delayed += 1
                    lines.append(f"- {name}: Completed late")
            elif status.lower() == "at risk":
                at_risk += 1
                lines.append(f"- {name}: At-Risk (due {deadline})")
            else:
                lines.append(f"- {name}: {status.capitalize()} (due {deadline})")
        
        summary = f"\nTotal: {len(milestones)} | On-Time: {on_time} | At-Risk: {at_risk} | Delayed: {delayed}"
        return "\n".join(lines) + summary if lines else "- No milestone details available" + summary
    
    @staticmethod
    def _format_risk_details(risks: list) -> str:
        """Format risk details for explanation context."""
        if not risks:
            return "- No identified risks"
        
        by_severity = {"high": [], "medium": [], "low": []}
        
        for risk in risks:
            severity = risk.get("severity", "medium").lower()
            name = risk.get("name", "Unnamed Risk")
            description = risk.get("description", "")
            
            if severity not in by_severity:
                severity = "medium"
            
            desc_text = f" - {description[:60]}" if description else ""
            by_severity[severity].append(f"{name}{desc_text}")
        
        lines = []
        for severity in ["high", "medium", "low"]:
            if by_severity[severity]:
                lines.append(f"\n{severity.upper()} ({len(by_severity[severity])}):")
                for risk in by_severity[severity]:
                    lines.append(f"  - {risk}")
        
        total_risks = sum(len(v) for v in by_severity.values())
        summary = f"\nTotal: {total_risks} risks"
        return "".join(lines) + summary if lines else "- No risks categorized" + summary
    
    @staticmethod
    def _format_team_details(team: list) -> str:
        """Format team details for explanation context."""
        if not team:
            return "- No team members defined"
        
        lines = []
        roles = {}
        
        for member in team:
            role = member.get("role", "Unknown")
            name = member.get("name", "Unnamed")
            status = member.get("status", "active")
            capacity = member.get("capacity", "unknown")
            
            if role not in roles:
                roles[role] = []
            roles[role].append((name, status, capacity))
            
            lines.append(f"- {name} ({role}): {status} | Capacity: {capacity}")
        
        summary = f"\nTotal: {len(team)} members"
        role_summary = " | ".join([f"{role}: {len(members)}" for role, members in roles.items()])
        
        return "".join([f"\n{line}" for line in lines]) + summary + f"\n{role_summary}" if lines else "- No team data" + summary
    
    @staticmethod
    def _format_comment_summary(comments: list) -> str:
        """Format status comments for explanation context."""
        if not comments:
            return "- No status comments recorded"
        
        lines = []
        for comment in comments[-5:]:  # Last 5 comments
            text = comment.get("text", "")[:80] if isinstance(comment, dict) else str(comment)[:80]
            date = comment.get("created_at", "") if isinstance(comment, dict) else ""
            date_str = f" ({date})" if date else ""
            lines.append(f"- {text}...{date_str}")
        
        total = len(comments)
        return "\n".join(lines) + f"\n(Latest 5 of {total} total comments)" if lines else "- No comments available"
    
    
    @staticmethod
    def _default_explanation() -> Dict[str, Any]:
        """Return default explanation when LLM fails."""
        return {
            "explanation": "Unable to generate explanation at this time. Please review the dimension scores above.",
            "key_strengths": [],
            "key_concerns": [],
            "data_quality_note": "LLM explanation unavailable."
        }
