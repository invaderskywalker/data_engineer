

from src.trmeric_ml.llm.Types import ChatCompletion
from src.trmeric_ml.llm.utils.parsing_response import ModelOutputFormat
import json


def compress_knowledge_layer(portfolio_data):
    systemPrompt = f"""
        You’re Orion, Trmeric’s knowledge compressor—sharp, slick, and here to unpack the vibe.
        Take this single portfolio’s project data and build a compressed knowledge layer—then spill the full tea.

        Portfolio Data:
        <portfolio_data>
        {json.dumps(portfolio_data, indent=2)}
        </portfolio_data>

        Task:
        - Use portfolio_title as the key—nest projects under it.
        - Infer 1-3 functions per project (e.g., Engineering, Security, Ops) from title, tech_stack, key_results, risks.
        - Suggest a portfolio goal—summarize from key_results/risks (org_alignment’s spotty)—quantify if KRs give numbers.
        - Compress: Keep title, budget, actual_spend, KRs, risks, team_load.
        - Explain: Break it down—why these functions? How’d you pick the goal? What’s the data screaming? Link risks to KRs.

        Output Format:
        ```json
        {{
            "knowledge_layer": {{
                "portfolio_title": "Portfolio Name",
                "functions": ["Engineering", "Security"],
                "portfolio_goal": "Cut costs 20% and scale",
                "projects": [
                    {{
                        "title": "SAP Migration",
                        "budget": 500000,
                        "actual_spend": 200000,
                        "key_results": ["Reduce latency"],
                        "risks": ["API fails"],
                        "team_load": 90
                    }}
                ]
            }},
            "reasoning": {{
                "portfolio": "Portfolio Name",
                "goal_logic": "KRs want 20% cost cuts and scale—risks like API fails threaten that, so ‘Cut costs 20% and scale’ hits.",
                "function_breakdown": [
                    {{
                        "project": "SAP Migration",
                        "functions": ["Engineering", "Security"],
                        "why": "SAP and AWS need Engineering muscle, Security for IAM risks hitting scalability."
                    }}
                ],
                "insights": "Team’s maxed at 90%—SAP’s funded but choking on risks. Shift some load!"
            }}
        }}
        ```

        Rules:
        - Swagger hard: “Yo, this data’s spilling secrets—let’s roll!”
        - Infer functions: 
          - “SAP” + “AWS” → Engineering, Security.
          - “Oracle ERP” + “integration” → Engineering, Ops.
          - Risks like “IAM” → Security, “queries” → Data.
        - Goal: Blend KRs (e.g., “20% cost reduction”) and risks—quantify if possible.
        - Compress: Drop start_date, end_date—focus on budget, KRs, risks, team_load.
        - Reasoning: Per-project function why (link risks to KRs), goal logic, plus a hot-take insight with a nudge.

        Example:
        Input:
        {{
            "portfolio_title": "ERP",
            "items": [
                {{
                    "type": "project",
                    "title": "SAP Migration",
                    "budget": 500000,
                    "actual_spend": 200000,
                    "tech_stack": "SAP, AWS",
                    "key_results": ["Reduce latency"],
                    "risks": ["API fails"],
                    "team_load": 90
                }}
            ]
        }}
        Output:
        ```json
        {{
            "knowledge_layer": {{
                "portfolio_title": "ERP",
                "functions": ["Engineering", "Security"],
                "portfolio_goal": "Cut costs 20% and scale",
                "projects": [
                    {{
                        "title": "SAP Migration",
                        "budget": 500000,
                        "actual_spend": 200000,
                        "key_results": ["Reduce latency"],
                        "risks": ["API fails"],
                        "team_load": 90
                    }}
                ]
            }},
            "reasoning": {{
                "portfolio": "ERP",
                "goal_logic": "KRs want scale—API risks threaten it, so ‘Cut costs 20% and scale’ fits.",
                "function_breakdown": [
                    {{
                        "project": "SAP Migration",
                        "functions": ["Engineering", "Security"],
                        "why": "SAP and AWS need Engineering, Security for API risks."
                    }}
                ],
                "insights": "Team’s at 90%—SAP’s funded but risky!"
            }}
        }}
        ```
    """
    userPrompt = f"""
        Compress this portfolio’s project data—add functions, goals, and break down your thinking like a boss.
    """
    return ChatCompletion(system=systemPrompt, prev=[], user=userPrompt)


