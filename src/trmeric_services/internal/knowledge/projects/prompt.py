"""
    Prompt Lbrary for knowledge creation of projects 
"""
from src.trmeric_ml.llm.Types import ChatCompletion


def generate_summary_view_of_projects(portfolio_title, projects_data) -> ChatCompletion:
    """
    Generates a summary view for a list of projects within a given portfolio.
    """
    
    prompt = f"""
    You are a project management assistant tasked with summarizing a portfolio of projects.
    To create a knowledge layer of this portfolio.
    The portfolio titled "{portfolio_title}" includes the following projects:

    {projects_data}

    Please provide:
    1. A detailed summary of the portfolio, covering the following for each project:
       - Title, duration, location, type, SDLC method, and budget.
       - Main objectives and key deliverables.
       - Technologies, tools, and methodologies used.
       - Key milestones and their status (completed, on track, delayed).
       - Team composition and their contributions.
    2. An analysis of synergies and common themes across the projects, including:
       - Shared technologies, methodologies, or objectives.
       - Interdependencies or collaborative opportunities between projects.
    3. Challenges identified within the portfolio and their potential resolutions.
    4. Strategic recommendations to improve portfolio outcomes, including:
       - Suggestions for resource allocation, process improvements, or technology adoption.
       - Any gaps in data or planning that need to be addressed.
    5. Insights into how this portfolio contributes to the broader organizational goals or strategic vision.
    6. Any additional observations, patterns, or trends that could guide future portfolio planning.
    
    """

    return ChatCompletion(
        system="You are an experienced project management assistant with deep knowledge of portfolio management and project management.",
        prev=[],
        user=prompt
    )


def generate_company_knowledge_layer(portfolios_data) -> ChatCompletion:
    """
    Combines data from multiple portfolios to create an enhanced knowledge layer for the company.
    """
    
    prompt = f"""
    You are a strategic knowledge management assistant tasked with creating a consolidated knowledge layer for a company. 
    The following is the aggregated data from multiple portfolios:

    {portfolios_data}

    Using this data, provide a detailed and structured knowledge layer that includes:

    1. **Portfolio Overview**:
        - Summarize the key objectives, project types, milestones, and results achieved across all portfolios.
        - Highlight the unique strengths and focus areas of each portfolio.

    2. **Cross-Portfolio Insights**:
        - Identify recurring themes, shared challenges, and common success factors across the portfolios.
        - Analyze interdependencies, synergies, and collaborative opportunities between portfolios.

    3. **Company-Level Analysis**:
        - Create an overarching summary of how these portfolios align with the company’s strategic vision, mission, and goals.
        - Evaluate the impact of these portfolios on the company’s growth, innovation, and market presence.

    4. **Key Metrics and Performance Indicators**:
        - Aggregate and summarize quantitative metrics such as budgets, timelines, technologies used, and team contributions.
        - Highlight any notable trends, such as overachieving or underperforming areas.

    5. **Knowledge Gaps and Opportunities**:
        - Identify missing data or under-explored areas that could improve future portfolio performance.
        - Suggest new initiatives or improvements to strengthen alignment with company goals.

    6. **Strategic Recommendations**:
        - Provide actionable recommendations for optimizing resource allocation, process efficiency, and project execution.
        - Highlight potential investments in technology, training, or partnerships that could enhance portfolio success.

    7. **Visual Summary Suggestions**:
        - Outline ideas for visualizing this knowledge layer, such as charts, graphs, or dashboards, to make the insights more accessible.

    Ensure the response is structured, insightful, and actionable, serving as a foundational knowledge layer for decision-makers at the company.
    """

    return ChatCompletion(
        system="You are a seasoned knowledge management assistant with expertise in creating strategic insights, actionable recommendations, and clear summaries from complex datasets.",
        prev=[],
        user=prompt
    )
