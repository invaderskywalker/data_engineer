from src.trmeric_ml.llm.Types import ChatCompletion
from src.trmeric_ml.llm.utils.parsing_response import ModelOutputFormat


def geetnerateRoadmapPortfolioSnapshot(
    portfolio_title, roadmaps_data
) -> ChatCompletion:
    prompt = f"""
        You are the Head of the organization responsible for creating snapshot of all the roadmap attributes for a portfolio:
        Current portfolio: portfolio_title = {portfolio_title}, 
        
        All roadmaps data in this portfolio:
        {roadmaps_data}
        --------

        For each attribute from all the roadmaps data:
            You are supposed to create a super summarized view for each attribute.
        
        
        Output in Json Format each attribute:
        ```json
            
        ```
    """

    return ChatCompletion(
        system="",
        prev=[],
        user=prompt
    )
