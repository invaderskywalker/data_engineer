from src.trmeric_ml.llm.Types import ChatCompletion
from src.trmeric_ml.llm.utils.parsing_response import ModelOutputFormat

def roleAndJobDescription(data_category, data) :
    return f"""
        You are a Portfolio Manager of a very good organization.
        Your current job is to create insights from this data provided.
        
        This data is for {data_category}.
        
        Data: {data}
    """
    
def outputFormat():
    return """
    Oputut Foramt JSON:
    
    ```json
    {
        insights: [], // short insights and upto 3 insights
    }
    ```
    """

class PortfolioApiPrompts:
    """_summary_

    Returns:
        _type_: _description_
    """
    @staticmethod
    def planned_vs_actual_insight_prompt(data) -> ChatCompletion:
        prompt = f"""
            {roleAndJobDescription(data_category="planned_vs_actual_month_wise", data=data)}
            
            {outputFormat()}
        """

        return ChatCompletion(
            system="",
            prev=[],
            user=prompt
        )
        
    @staticmethod
    def planned_and_actual_by_portfolio(data) -> ChatCompletion:
        prompt = f"""
            {roleAndJobDescription(data_category="planned_vs_actual_by_portfolio", data=data)}
            
            {outputFormat()}
        """

        return ChatCompletion(
            system="",
            prev=[],
            user=prompt
        )

    @staticmethod
    def planned_and_actual_by_category_prompt(data) -> ChatCompletion:
        prompt = f"""
            {roleAndJobDescription(data_category="planned_and_actual_by_category", data=data)}
            
            {outputFormat()}
        """

        return ChatCompletion(
            system="",
            prev=[],
            user=prompt
        )
        
    @staticmethod
    def overall_success_rate(data) -> ChatCompletion:
        prompt = f"""
            {roleAndJobDescription(data_category="overall_performance_compared_from_last_week", data=data)}
            {outputFormat()}
        """
        
        return ChatCompletion(
            system="",
            prev=[],
            user=prompt
        )
        
    @staticmethod
    def overall_performance_compared_from_last_week_by_type(data) -> ChatCompletion:
        prompt = f"""
            {roleAndJobDescription(data_category="overall_performance_compared_from_last_week_by_type", data=data)}
            {outputFormat()}
        """
        
        return ChatCompletion(
            system="",
            prev=[],
            user=prompt
        )
        
    @staticmethod
    def impact_analysis(data) -> ChatCompletion:
        prompt = f"""
            {roleAndJobDescription(data_category="impact_analysis", data=data)}
            {outputFormat()}
        """
        
        return ChatCompletion(
            system="",
            prev=[],
            user=prompt
        )
        
    
    

