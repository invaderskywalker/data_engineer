


default_template_content_idea = {
    "output_structure": {
        "executive_summary": {
            "description": "Provides a brief overview (4–5 sentences) of the idea, its purpose, and expected outcomes.",
            "format": "paragraph",
            "index": 1
        },
        "strategic_alignment": {
            "description": "Describes how the idea supports enterprise OKRs or business priorities.",
            "format": "list",
            "index": 2
        },
        "estimated_investment": {
            "description": "Details the estimated costs for the idea, including labor, non-labor, and total costs.",
            "format": "table",
            "index": 3,
            "subsections": {
                "labor_cost": {
                    "description": "Estimated labor costs for the idea.",
                    "format": "table",
                    "columns": ["Category", "Amount", "Justification"]
                },
                "non_labor_cost": {
                    "description": "Estimated non-labor costs for the idea.",
                    "format": "table",
                    "columns": ["Category", "Amount", "Justification"]
                },
                "total_cost": {
                    "description": "Summarizes the total estimated costs by combining labor and non-labor costs.",
                    "format": "table",
                    "columns": ["Category", "Amount", "Justification"]
                }
            }
        },
        "expected_benefits": {
            "description": "Lists the summarized benefits of the idea, such as efficiency gains, financial savings, or improved customer experience.",
            "format": "list",
            "index": 4
        },
        "financials": {
            "description": "Provides key financial metrics, including ROI, NPV (optional), and payback period.",
            "format": "table",
            "index": 5,
            "subsections": {
                "roi": {
                    "description": "Details the return on investment for the idea.",
                    "format": "table",
                    "columns": ["Metric", "Value", "Justification"]
                },
                "npv": {
                    "description": "Details the net present value for the idea (optional).",
                    "format": "table",
                    "columns": ["Metric", "Value", "Justification"]
                },
                "payback_period": {
                    "description": "Details the payback period for the idea.",
                    "format": "table",
                    "columns": ["Metric", "Value", "Justification"]
                }
            },
            "calculation": {
                "description": "",
                "format": "table",
                "columns": [
                    "formula",
                    "calculation",
                    "result",
                    "justification"
                ],
                "section<name>": [{
                    "data": {}    
                }],
            }
        },
        "risks_and_dependencies": {
            "description": "Identifies concise risks or dependencies relevant to early evaluation of the idea.",
            "format": "list",
            "index": 6
        },
        "recommendation": {
            "description": "Provides a concise (1–2 sentence) recommendation for the next steps, such as proceeding to pilot, needing validation, or deferring.",
            "format": "paragraph",
            "index": 7
        },
        "thought_process": {
            "description": f"""Provide a detailed breakdown of the reasoning behind the business case generated for the idea.
                - Explain the basis for ROI, NPV, and payback period calculations.
                - Detail how labor and non-labor cost estimates were derived.
                - Mention any data sources, assumptions, or estimation logic used.

                The output must be in **Markdown string bullet points** (4-8 points, total 80–150 words), clearly elaborating the rationale behind all calculations and inputs.""",
            "format": "markdown",
            "index": 8
        }
    } 
}




default_template_content = {
    "output_structure": {
        "executive_summary": {
            "description": "Summarizes the key aspects of the project/roadmap or initiative, including the problem or opportunity it addresses, the proposed solution, and the expected benefits (both financial and non-financial). Includes a brief recommendation for approval.",
            "format": "paragraph",
            "index": 1
        },
        "strategic_alignment": {
            "description": "Describes how the initiative aligns with the organization's strategic goals, business priorities, and competitive context.",
            "format": "list",
            "index": 2
        },
        "business_objectives_and_benefits": {
            "description": "Lists the business objectives and expected benefits (tangible/intangible) with success metrics (KPIs/Key results).",
            "format": "list",
            "index": 3,
            "subsections": {
                "objectives": {
                    "description": "Specific objectives of the project.",
                    "format": "list"
                },
                "kpis": {
                    "description": "Key performance indicators to measure success.",
                    "format": "list"
                },
                "benefits": {
                    "description": "Expected benefits, both tangible and intangible.",
                    "format": "list"
                }
            }
        },
        "problem_or_opportunity_analysis": {
            "description": "Provides a detailed analysis of the problem or opportunity the project addresses, including supporting data, research, or trends.",
            "format": "paragraph",
            "index": 4
        },
        "project_scope": {
            "description": "Defines the project scope, listing inclusions, exclusions, assumptions, constraints, and dependencies.",
            "format": "paragraph",
            "index": 5
        },
        "proposed_solution_overview": {
            "description": "Describes the proposed solution, including key features, technologies, and reasons for selection.",
            "format": "paragraph",
            "index": 6
        },
        "cost_and_budget_estimates": {
            "description": "Provides detailed cost estimates for the project, including development, implementation, and ongoing expenses.",
            "format": "table",
            "index": 7,
            "subsections": {
                "estimated_labor_cost": {
                    "description": "Details labor costs with categories, amounts, and justifications.",
                    "format": "table",
                    "columns": ["Category", "Amount", "Justification"]
                },
                "estimated_non_labor_cost": {
                    "description": "Details non-labor costs with categories, amounts, and justifications.",
                    "format": "table",
                    "columns": ["Category", "Amount", "Justification"]
                },
                "overall_cost_breakdown": {
                    "description": "Summarizes total costs by combining labor and non-labor costs.",
                    "format": "table",
                    "columns": ["Category", "Amount", "Justification"]
                }
            }
        },
        "financial_analysis_and_ROI": {
            "description": "Computes financial benefits including ROI, NPV, and payback period, with detailed calculations.",
            "format": "table",
            "index": 8,
            "subsections": {
                "revenue_uplift_cashflow": {
                    "description": "Details revenue uplift cash inflows by year.",
                    "format": "table",
                    "columns": ["Year", "Revenue Category", "Total Revenue", "Justification"]
                },
                "operational_efficiency_gains": {
                    "description": "Details operational efficiency savings by year.",
                    "format": "table",
                    "columns": ["Year", "Savings Category", "Amount", "Justification"]
                },
                "cash_flow_analysis": {
                    "description": "Summarizes cash flow analysis including total revenue, costs, and net cash flow.",
                    "format": "table",
                    "columns": ["Year", "Total Revenue", "Total Costs", "Operational Efficiency Savings", "Net Cash Flow"]
                }
            },
            "calculation": {
                "description": "",
                "format": "table",
                "columns": [
                    "formula",
                    "calculation",
                    "result",
                    "justification"
                ],
                "section<name>": [{
                    "data": {}    
                }],
            }
        },
        "risk_analysis": {
            "description": "Identifies key risks, their probability, impact, and mitigation strategies.",
            "format": "table",
            "index": 9,
            "subsections": {
                "risks": {
                    "description": "Details each risk with probability, impact, and mitigation strategy.",
                    "format": "table"
                }
            }
        },
        "stakeholder_analysis": {
            "description": "Lists key stakeholders, their roles, responsibilities, and communication plan.",
            "format": "table",
            "index": 10,
            "subsections": {
                "stakeholders": {
                    "description": "Details each stakeholder's role and communication plan.",
                    "format": "table"
                }
            }
        },
        "project_timeline_and_milestones": {
            "description": "Provides a high-level timeline, major milestones, dependencies, and critical path tasks.",
            "format": "table",
            "index": 11,
            "subsections": {
                "milestones": {
                    "description": "Details each milestone with date, dependencies, and critical path status.",
                    "format": "table"
                }
            }
        },
        "conclusion_and_recommendation": {
            "description": "Summarizes the project benefits and provides a final recommendation for approval.",
            "format": "paragraph",
            "index": 12
        },
        "approval_section": {
            "description": "Includes space for necessary sign-offs by project sponsors and business unit leaders.",
            "format": "paragraph",
            "index": 13
        }
    }
}