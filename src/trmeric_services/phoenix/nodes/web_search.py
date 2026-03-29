# from src.trmeric_utils.web.WebSearchAgent import WebSearchAgent
from src.trmeric_utils.web.WebsearchAgentOld import WebSearchAgent
from concurrent.futures import ThreadPoolExecutor, as_completed

class WebSearchNode:
    def __init__(self, network_data={}):
        self.web_search_agent = WebSearchAgent()
     
    def runOld(self, sources=[]):
        search_results = [self.web_search_agent.query_search_engine(query, skip_source=True) for query in sources]
        return search_results
       
    def run(self, sources=[]):
        """Runs web searches concurrently for multiple sources."""
        if not sources:
            return []
        
        search_results = []
        # Use ThreadPoolExecutor to parallelize search queries
        with ThreadPoolExecutor(max_workers=min(5, len(sources))) as executor:
            # Submit all queries as futures
            future_to_query = {
                executor.submit(self.web_search_agent.query_search_engine, query, skip_source=True, n=2): query 
                for query in sources
            }
            for future in as_completed(future_to_query):
                query = future_to_query[future]
                try:
                    result = future.result()
                    search_results.append(result)
                except Exception as e:
                    print(f"Error processing web search for query '{query}': {e}")
                    search_results.append([])  # Append empty result on failure
        
        return search_results
      
      
    def runV2(self, sources=[]):
        """Runs web searches concurrently for multiple sources."""
        if not sources:
            return []
        
        search_results = []
        # Use ThreadPoolExecutor to parallelize search queries
        with ThreadPoolExecutor(max_workers=min(5, len(sources))) as executor:
            # Submit all queries as futures
            future_to_query = {
                executor.submit(self.web_search_agent.fetch_first_page_search_results, query, skip_source=False, n=10): query 
                for query in sources
            }
            for future in as_completed(future_to_query):
                query = future_to_query[future]
                try:
                    result = future.result()
                    search_results.append(result)
                except Exception as e:
                    print(f"Error processing web search for query '{query}': {e}")
                    search_results.append([])  # Append empty result on failure
        
        return search_results
        

    def run_and_format(self, sources=[], text = None):
        """Run web searches and format the results."""
        search_results = self.run(sources)
        formatted_output = self.format_search_results(search_results, text)
        # print("--debug webSearch output--", formatted_output)
        formatted_output = f"""
        <web_search_data>
        {formatted_output}
        <web_search_data>
        """
        return formatted_output
    
    def format_search_results(self, search_results, text=None):
        """
        Format web search results into a readable string with markdown formatting.
        
        Args:
            search_results: List of search result items (e.g., [{"raw_data": [...]}, ...])
            text: Optional string to prepend to the output
        
        Returns:
            Formatted string with search results
        """
        formatted_output = "### Web Search Results\n\n"
        
        if text and isinstance(text, str):
            formatted_output += f"{text}\n\n"
        
        if not search_results:
            formatted_output += "No results found.\n"
            return formatted_output.strip()

        for i, result in enumerate(search_results):
            formatted_output += f"#### Result Set {i+1}\n"
            
            if isinstance(result, dict) and 'raw_data' in result:
                for j, item in enumerate(result.get('raw_data', [])):
                    formatted_output += f"- **{j+1}. {item.get('title', 'No title')}**\n"
                    if item.get('source'):
                        formatted_output += f"  - **Source**: {item.get('source', 'No source')}\n"
                    if item.get('snippet'):
                        formatted_output += f"  - **Snippet**: {item.get('snippet', 'No snippet available')}\n"
                    formatted_output += "\n"
                if result.get('full_content'):
                    formatted_output += f"  - **Full Content**:\n"
                    for content_item in result.get('full_content', []):
                        formatted_output += f"    - **Source**: {content_item.get('source', 'No source')}\n"
                        formatted_output += f"      **Content**: {content_item.get('content', 'No content')[:500]}\n\n"
            else:
                formatted_output += "- No valid results in this set.\n\n"
            
            formatted_output += "---\n\n"
        
        return formatted_output.strip()

    @staticmethod
    def format_search_results_v2(sources, search_results):
        """Formats web search results into a Markdown string."""
        output = "# Web Search Results\n\n"
        output += "## Summary\n"
        output += f"- **Number of Queries**: {len(sources)}\n"
        output += f"- **Queries Processed**: {', '.join(sources)}\n\n"
        output += "## Results\n\n"
        
        for query, results in zip(sources, search_results):
            output += f"### Query: {query}\n"
            if not results or not results.get('raw_data'):
                output += "- No results found or an error occurred.\n"
            else:
                for result in results['raw_data']:
                    output += f"- **Title**: {result.get('title', 'N/A')}\n"
                    # output += f"  - **Snippet**: {result.get('snippet', 'N/A')}\n"  # Uncommented snippet
                    if 'source' in result:  # Only include source if present
                        output += f"  - **Source**: [{result['source']}]({result['source']})\n"
                
                # Full content
                if results.get('full_content'):
                    output += "\n#### Full Content\n"
                    for content_item in results['full_content']:
                        output += f"- **Source**: [{content_item['source']}]({content_item['source']})\n"
                        output += f"  - **Content**: {content_item['content']}\n\n\n"
                else:
                    output += "- No full content retrieved.\n"
            output += "\n"
        
        return output
    
    
# Standalone execution
if __name__ == "__main__":
    web_search_node = WebSearchNode()
    sample_sources = ["presience data science solutions"]
    result = web_search_node.run(sources=sample_sources)
    # print(result)
    # print("---")
    formatted_result = web_search_node.format_search_results(sample_sources, result)
    print(formatted_result)