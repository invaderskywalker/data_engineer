"""
LLM-based retrospective analysis for project maturity scoring.
Analyzes retrospective summaries to extract structured insights for scoring.
"""

from typing import Optional, Dict, Any
from src.trmeric_ml.llm.models.OpenAIClient import ChatGPTClient
from src.trmeric_ml.llm.Types import ChatCompletion, ModelOptions
from src.trmeric_utils.json_parser import extract_json_after_llm
from src.trmeric_api.logging.AppLogger import appLogger


class RetrospectiveAnalyzer:
    """LLM-based analyzer for project retrospectives"""
    
    def __init__(self):
        self.llm = ChatGPTClient()
    
    @staticmethod
    def build_retrospective_analysis_prompt(retro_data: Dict[str, Any]) -> str:
        """
        Build the system prompt for retrospective analysis.
        Instructs LLM to score various dimensions of the retrospective.
        """
        return """
You are an expert project retrospective analyst. Analyze the provided project retrospective and score it across multiple dimensions.

SCORING GUIDELINES:

1. LEARNING QUALITY (0-100): How much substantial learning is captured?
   - 90-100: Detailed, specific lessons with clear examples and insights
   - 70-89: Good lessons identified with some detail
   - 50-69: Basic lessons captured, lacking depth
   - 30-49: Minimal learning documented
   - 0-29: No meaningful learning captured

2. SENTIMENT & OUTCOME (0-100): Overall positivity and success indicators?
   - 90-100: Strong positive outcomes, high team satisfaction, clear wins
   - 70-89: Mostly positive, some challenges overcome
   - 50-69: Mixed results, balanced challenges and wins
   - 30-49: Mostly negative, significant challenges
   - 0-29: Negative outcomes, low satisfaction

3. ACTIONABILITY (0-100): How specific and actionable are recommendations?
   - 90-100: Clear, specific actions for next project with measurable outcomes
   - 70-89: Good action items with implementation details
   - 50-69: Some actions identified but lacking specifics
   - 30-49: Vague improvement areas without clear actions
   - 0-29: No actionable improvements

4. TEAM INVOLVEMENT (0-100): Evidence of team participation and buy-in?
   - 90-100: Multiple perspectives, diverse team input, clear consensus
   - 70-89: Good team participation across roles
   - 50-69: Some team input but limited perspectives
   - 30-49: Minimal team involvement, mainly single perspective
   - 0-29: No evidence of team participation

5. RISK AWARENESS (0-100): How well are risks, blockers, and lessons captured?
   - 90-100: Comprehensive risk analysis with mitigation strategies
   - 70-89: Good risk identification with solutions
   - 50-69: Risks mentioned but lacking analysis
   - 30-49: Minimal risk discussion
   - 0-29: No risk awareness

6. SUSTAINABILITY (0-100): Will lessons be retained and applied?
   - 90-100: Documented in team processes, assigned owners, tracked follow-up
   - 70-89: Clear documentation with follow-up plan
   - 50-69: Documented but sustainability uncertain
   - 30-49: Minimal documentation or follow-up plan
   - 0-29: No mechanism for retention

Return a JSON object with these exact fields:
{
    "learning_quality": <0-100>,
    "sentiment_and_outcome": <0-100>,
    "actionability": <0-100>,
    "team_involvement": <0-100>,
    "risk_awareness": <0-100>,
    "sustainability": <0-100>,
    "key_insights": ["insight1", "insight2", "insight3"],
    "critical_issues": ["issue1", "issue2"],
    "recommended_actions": ["action1", "action2"],
    "overall_assessment": "2-3 sentence summary of the retrospective quality"
}
"""
    
    @staticmethod
    def build_user_message(retro_data: Dict[str, Any]) -> str:
        """Build the user message containing the retrospective data to analyze."""
        parts = []
        
        if retro_data.get("retrospective_summary"):
            parts.append(f"RETROSPECTIVE SUMMARY:\n{retro_data.get('retrospective_summary')}")
        
        if retro_data.get("things_to_keep_doing"):
            parts.append(f"THINGS TO KEEP DOING:\n{retro_data.get('things_to_keep_doing')}")
        
        if retro_data.get("areas_for_improvement"):
            parts.append(f"AREAS FOR IMPROVEMENT:\n{retro_data.get('areas_for_improvement')}")
        
        if retro_data.get("detailed_analysis"):
            detailed = retro_data.get("detailed_analysis", {})
            parts.append(f"DETAILED ANALYSIS:\n{str(detailed)}")
        
        return "\n\n".join(parts) if parts else "No retrospective data provided."
    
    def analyze_retrospective(self, retro_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Use LLM to analyze retrospective data and extract structured scores.
        
        Args:
            retro_data: Retrospective data dictionary with keys:
                - retrospective_summary: str
                - things_to_keep_doing: str
                - areas_for_improvement: str
                - detailed_analysis: dict
                - team_score: int (optional)
        
        Returns:
            Dictionary with LLM-analyzed scores:
                - learning_quality: 0-100
                - sentiment_and_outcome: 0-100
                - actionability: 0-100
                - team_involvement: 0-100
                - risk_awareness: 0-100
                - sustainability: 0-100
                - key_insights: list[str]
                - critical_issues: list[str]
                - recommended_actions: list[str]
                - overall_assessment: str
        """
        try:
            # Build the prompt
            system_prompt = self.build_retrospective_analysis_prompt(retro_data)
            user_message = self.build_user_message(retro_data)
            
            # Create chat completion
            chat = ChatCompletion(
                system=system_prompt,
                prev=[],
                user=user_message
            )
            
            # Call LLM
            response = self.llm.run(
                chat,
                ModelOptions(model="gpt-4o", max_tokens=2000, temperature=0.2),
                'scoring::retrospective_analysis'
            )
            
            # Parse response
            result = extract_json_after_llm(response)
            
            # Validate required fields
            if not result:
                return self._default_analysis()
            
            # Ensure all fields are present with defaults
            validated = {
                "learning_quality": int(result.get("learning_quality", 50)),
                "sentiment_and_outcome": int(result.get("sentiment_and_outcome", 50)),
                "actionability": int(result.get("actionability", 50)),
                "team_involvement": int(result.get("team_involvement", 50)),
                "risk_awareness": int(result.get("risk_awareness", 50)),
                "sustainability": int(result.get("sustainability", 50)),
                "key_insights": result.get("key_insights", []),
                "critical_issues": result.get("critical_issues", []),
                "recommended_actions": result.get("recommended_actions", []),
                "overall_assessment": result.get("overall_assessment", "")
            }
            
            # Clamp all scores to 0-100
            for key in ["learning_quality", "sentiment_and_outcome", "actionability", 
                       "team_involvement", "risk_awareness", "sustainability"]:
                validated[key] = max(0, min(100, validated[key]))
            
            appLogger.info({
                "event": "retrospective_analysis_success",
                "learning_quality": validated["learning_quality"],
                "sentiment_and_outcome": validated["sentiment_and_outcome"],
                "actionability": validated["actionability"]
            })
            
            return validated
            
        except Exception as e:
            appLogger.error({
                "event": "retrospective_analysis_failed",
                "error": str(e),
                "traceback": str(e)
            })
            return self._default_analysis()
    
    @staticmethod
    def _default_analysis() -> Dict[str, Any]:
        """Return default analysis when LLM analysis fails."""
        return {
            "learning_quality": 0,
            "sentiment_and_outcome": 0,
            "actionability": 0,
            "team_involvement": 0,
            "risk_awareness": 0,
            "sustainability": 0,
            "key_insights": [],
            "critical_issues": [],
            "recommended_actions": [],
            "overall_assessment": "LLM analysis unavailable"
        }
    
    @staticmethod
    def calculate_composite_retro_score(analysis: Dict[str, Any], team_score: Optional[int] = None) -> int:
        """
        Calculate composite retrospective score from analyzed dimensions.
        
        Weights:
        - Learning Quality: 25%
        - Sentiment & Outcome: 25%
        - Actionability: 20%
        - Team Involvement: 15%
        - Risk Awareness: 10%
        - Sustainability: 5%
        
        Plus optional team score component (5%)
        
        Args:
            analysis: Output from analyze_retrospective()
            team_score: Optional team satisfaction score (0-100)
        
        Returns:
            Composite retrospective score (0-100)
        """
        learning = analysis.get("learning_quality", 0)
        sentiment = analysis.get("sentiment_and_outcome", 0)
        actionability = analysis.get("actionability", 0)
        team_involvement = analysis.get("team_involvement", 0)
        risk_awareness = analysis.get("risk_awareness", 0)
        sustainability = analysis.get("sustainability", 0)
        
        # Base calculation
        score = (
            (learning * 0.25) +
            (sentiment * 0.25) +
            (actionability * 0.20) +
            (team_involvement * 0.15) +
            (risk_awareness * 0.10) +
            (sustainability * 0.05)
        )
        
        # Add team score bonus if provided (up to 5% boost)
        if team_score and team_score > 0:
            team_bonus = (team_score / 100.0) * 5  # Max 5 points
            score += team_bonus
        
        return int(min(100, max(0, score)))
