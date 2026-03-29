
### src/trmeric_services/agents/reports/customers/pf/monthly_savings/prompt.py

from src.trmeric_ml.llm.Types import ChatCompletion
from datetime import datetime
from typing import Dict, List


def monthly_savings_report_with_graph_prompt(snapshot_data: Dict, query: str, conv: List) -> Dict:
    """
    Generate a prompt for presenting monthly savings data with two tables in Markdown format.

    Args:
        snapshot_data (Dict): Aggregated savings data for tables, including programs and table2_data.
        query (str): User query context (e.g., "monthly savings report").
        conv (List): Conversation history for context.

    Returns:
        Dict: ChatCompletion prompt object.
    """
    current_date = datetime.now().date().isoformat()

    system_prompt = """
        You are a financial analyst tasked with presenting a monthly savings report in a clear, professional format. Your goal is to create two beautifully formatted tables in Markdown format to showcase the data. Use a concise, professional tone, and structure the response with clear headings and minimal text to emphasize the tables. If the data contains errors (e.g., missing months, inconsistent totals), note them briefly, explain their impact, and suggest a resolution.

        ### Table Formatting Instructions
        - Present two tables based on the input data, formatted in Markdown with aligned columns, clear headers, and dollar signs ($) for monetary values.
        - Ensure tables are easy to read, with proper Markdown syntax (e.g., | Column | Column |), consistent column alignment, and clean presentation for a professional look.
        - **Table 1**: Show monthly savings by program (e.g., Exit, Migrate) with a grand total for each row and a final total row. Use snapshot_data["programs"]. Include a row for "No date" and all months present in the data (e.g., Jul, Aug, ..., Jan).
        - **Table 2**: Show monthly savings, cumulative savings, and project counts for each month from "No date" to "Jan", with a row for "Cumulative dated" total. Use snapshot_data["table2_data"] directly, which provides precomputed values:
          - Monthly Savings: Sum of savings across programs for each month.
          - Cumulative Savings: For each month, the monthly savings multiplied by the number of months from its start to January 2026. For example:
            - Jul cumulative savings = (Jul savings × 7) (counted in Jul, Aug, Sep, Oct, Nov, Dec 2025, Jan 2026).
            - Aug cumulative savings = (Aug savings × 6) (counted in Aug, Sep, Oct, Nov, Dec 2025, Jan 2026).
            - Sep cumulative savings = (Sep savings × 5).
            - Oct cumulative savings = (Oct savings × 4).
            - Nov cumulative savings = (Nov savings × 3).
            - Dec cumulative savings = (Dec savings × 2).
            - Jan cumulative savings = (Jan savings × 1).
            - No date cumulative savings = No date savings (no multiplier).
          - Cumulative Dated Total (Jul to Dec 2025 only):
            - Monthly Savings column: Sum of monthly savings from Jul to Dec 2025 (excluding "No date" and "Jan").
            - Cumulative Savings column: Sum of cumulative savings from Jul to Dec 2025 (Jul × 7 + Aug × 6 + ... + Dec × 2).
            - Project Count column: Sum of project counts from Jul to Dec 2025.
        - If a month is missing in snapshot_data["programs"], it should be present with $0 savings and 0 projects, as provided by snapshot_data["table2_data"].
        - Format **Table 2** to match the user's preferred structure, ensuring columns for Row Labels, Monthly Savings, Cumulative Savings, and Project Count are clearly aligned in Markdown.

        ### Response Structure
        - **Data Validation**: Validate the data by checking if snapshot_data["total_possible_savings"] matches the sum of savings from snapshot_data["programs"] (including "No date" and all months). Note any discrepancies.
        - **Table 1**: Monthly savings by program with grand totals, in Markdown format, using snapshot_data["programs"].
        - **Table 2**: Monthly savings, cumulative savings, and project counts with "Cumulative dated" total, in Markdown format, using snapshot_data["table2_data"].
        - **Summary**: Highlight key insights (e.g., highest savings month, dominant program).
        - **Notes on Errors**: If errors are detected (e.g., missing months, total mismatch), explain them concisely and suggest next steps (e.g., verify missing data with the provider).
    """

    user_prompt = f"""
        **Monthly Savings Report**  
        **Date**: {current_date}  
        **Input Data**:  
        {snapshot_data}

        Please present the monthly savings data in a professional Markdown format with:
        - **Table 1**: Monthly savings by program (e.g., Exit, Migrate) with grand totals, formatted in Markdown using snapshot_data["programs"].
        - **Table 2**: Monthly savings, cumulative savings, and project counts for each month from "No date" to "Jan", with a row for "Cumulative dated" total, formatted in Markdown using snapshot_data["table2_data"].
        - **Brief Summary**: Highlight key insights (e.g., highest savings month, dominant program).
        - Format both tables in Markdown, ensuring clear alignment, column separation, and professional presentation as shown below.

        ### Example Table 1 (Markdown)
        | Row Labels | Exit      | Migrate   | Grand Total |
        |------------|-----------|-----------|-------------|
        | No date    | $---,---  | $---,---  | $---,---    |
        | Jul        | $---,---  | $---,---  | $---,---    |
        | ...        | ...       | ...       | ...         |
        | Jan        | $---,---  | $---,---  | $---,---    |
        | Total      | $---,---  | $---,---  | $---,---    |

        ### Example Table 2 (Markdown)
        | Row Labels      | Monthly Savings | Cumulative Savings | Project Count |
        |-----------------|-----------------|-------------------|---------------|
        | No date         | $...            | $...              | ...           |
        | Jul             | $...            | $...              | ...           |
        | Aug             | $...            | $...              | ...           |
        | Sep             | $...            | $...              | ...           |
        | Oct             | $...            | $...              | ...           |
        | Nov             | $...            | $...              | ...           |
        | Dec             | $...            | $...              | ...           |
        | Jan             | $...            | $...              | ...           |
        | Cumulative dated| $...            | $...              | ...           |

        If errors are detected in the data, explain them concisely and suggest next steps. Keep the narrative brief, focusing on the tables for impact.
        
        Use snapshot_data["table2_data"] directly for Table 2 without recalculating.
        Output in Rich text format.
    """

    prompt = ChatCompletion(system=system_prompt, prev=[], user=user_prompt)
    print("monthly_savings_report_prompt ", prompt.formatAsString())
    return prompt
  