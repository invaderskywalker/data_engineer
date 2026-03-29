

from src.utils.helper.decorators import log_function_io_and_time
from src.utils.types.getter import *
from src.utils.web.CompanyScraper import CompanyInfoScraper
from src.services.phoenix.nodes import WebSearchNode
from src.api.logging.AppLogger import appLogger, debugLogger
import concurrent.futures
import traceback
from src.utils.helper.event_bus import event_bus




class WebDataGetter:
    def __init__(self, tenant_id: int, user_id: int, session_id: str):
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.session_id = session_id
        self.event_bus = event_bus
        self.fn_maps = {
           "web_search": self.web_search, 
        }
        
    @log_function_io_and_time
    def web_search(self, params: Optional[Dict] = DEFAULT_WEB_AGENT_PARAMS) -> Dict:
        """
        Here we can do deep web search using: web_queries_string: we can write multiple queries that we would ideally search in web
        use website_urls when u know what website to use
        """
        try:
            params = params.copy()
            web_queries = (params.get("web_queries_string") or []) 
            # + (params.get("website_web_queries_also_add_which_company_in_string") or [])
            website_urls = params.get("website_urls", [])
            result = {}

            debugLogger.info(f"running web_search with {web_queries} and {website_urls}")

            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                futures = {}

                # Submit web queries task
                if web_queries:
                    futures["web_queries_result"] = executor.submit(
                        self.fetch_first_search_list, web_queries=web_queries
                    )

                # Submit scraping tasks
                if website_urls:
                    futures["website_urls_result"] = {
                        site: executor.submit(self._scrape_site, site)
                        for site in website_urls if site != ""
                    }

                # Collect results
                for key, fut in futures.items():
                    if key == "web_queries_result":
                        try:
                            res = fut.result()  # wait for web queries (list of URL arrays)
                            query_results = {q: r for q, r in zip(web_queries, res)}                            
                            all_scraped_urls = []
                            result["web_queries_result"] = query_results
                            
                            # Collect all top URLs across queries for deduplication and concurrent scraping
                            all_top_urls_set = set()
                            query_top_urls_map = {}  # Maps query to its list of top_urls (for later mapping)
                            import re
                            reject_url_patterns = re.compile(r"(pdf|scribd|wordpress|youtube|buffer)", re.IGNORECASE)

                            for q, urls in query_results.items():
                                filtered_urls = [url for url in urls if not reject_url_patterns.search(url)]
                                top_urls = filtered_urls[:3]
                                query_top_urls_map[q] = top_urls
                                all_top_urls_set.update(top_urls)
                            
                            print("all_top_urls_set ", all_top_urls_set)
                            # Submit all unique scrape tasks concurrently
                            scrape_futures = {
                                url: executor.submit(self._scrape_single_page, url)
                                for url in all_top_urls_set
                            }
                            
                            # Wait for all scrapes to complete concurrently
                            scraped_contents = {}
                            for url, scrape_fut in scrape_futures.items():
                                # print("debug  ", url, scrape_fut)
                                try:
                                    scraped_contents[url] = scrape_fut.result()
                                except Exception as scrape_error:
                                    appLogger.error(f"Error scraping {url}: {str(scrape_error)}")
                                    scraped_contents[url] = {}
                            
                            # Build per-query scraped dicts using the shared scraped_contents
                            for q, top_urls in query_top_urls_map.items():
                                query_scraped = {
                                    url: scraped_contents.get(url, {})
                                    for url in top_urls
                                    if url in scraped_contents  # Already ensured by set, but safe
                                }
                                all_scraped_urls.append(query_scraped)
                            
                            query_results["scraped_contents"] = all_scraped_urls
                            result["web_queries_result"] = query_results
                        except Exception as e:
                            appLogger.error(f"Error in web queries: {str(e)}")
                            result["web_queries_result"] = {}
              
                    elif key == "website_urls_result":
                        result["website_urls_result"] = {}
                        for site, site_future in fut.items():
                            try:
                                result["website_urls_result"][site] = site_future.result()
                            except Exception as scrape_error:
                                appLogger.error(f"Error scraping {site}: {str(scrape_error)}")
                                result["website_urls_result"][site] = {}
            
            # with open(f'data_scrape.json', 'w') as json_file:
            #     json.dump(result, json_file, indent=2)
                
            return result

        except Exception as e:
            appLogger.error({
                "function": "web_search",
                "error": str(e),
                "traceback": traceback.format_exc(),
                "tenant_id": self.tenant_id
            })
            return {}


    @log_function_io_and_time
    def _scrape_site(self, site: str) -> Dict:
        """Helper method to scrape a single site (extracted for thread pooling)."""
        self.event_bus.dispatch(
            'STEP_UPDATE',
            {'message': f"Scraping: {site}"},
            session_id=self.session_id
        )
        scraper_c = CompanyInfoScraper(site, max_workers=3)
        res = scraper_c.scrape()
        return res
    
    @log_function_io_and_time
    def _scrape_single_page(self, site: str) -> Dict:
        """Helper method to scrape a single site (extracted for thread pooling)."""
        self.event_bus.dispatch(
            'STEP_UPDATE',
            {'message': f"Scraping: {site}"},
            session_id=self.session_id
        )
        try:
            scraper_c = CompanyInfoScraper(site, max_workers=3)
            out = scraper_c.scrape_single_page()
            if len(out) > 0:
                if ("error" in out[0]):
                    return ""
                if ("content" in out[0]):
                    out[0]["content"] = " ".join(out[0]["content"].split(" ")[:400])
            
            safe_url = site.replace("https://", "").replace("http://", "").replace("/", "_")
            # with open(f'_scrape_single_page_{safe_url}.json', 'w') as json_file:
            #     json.dump(out, json_file, indent=2)
            return out
        except Exception as e:
            print("error here ", e, traceback.format_exc())
            return ""

    @log_function_io_and_time
    def fetch_first_search_list(self, web_queries):
        for q in web_queries:
            self.event_bus.dispatch(
                'STEP_UPDATE',
                {'message': f"WebSearch for Query: {q}"},
                session_id=self.session_id
            )
        return WebSearchNode().runV2(sources=web_queries)
        
        