######
from src.trmeric_services.internal.knowledge.base import KnowledgeBase
from src.trmeric_database.dao.portfolios import PortfolioDao
from src.trmeric_database.dao.roadmap import RoadmapDao
from src.trmeric_services.internal.knowledge.roadmaps.prompt import *


class RoadmapKnowledge(KnowledgeBase):
    def __init__(self):
        super().__init__()
        self.table_name = 'roadmap_knowledge'

    def processRoadmapsInPortfolio(self, item):
        """
        item: {'id': 107, 'title': 'Supply Chain', 'roadmap_ids': [192]}
        """
        roadmap_ids = item.get("roadmap_ids", [])
        roadmaps_data = []
        for roadmap_id in roadmap_ids:
            data = RoadmapDao.fetchRoadmapDataForBusinessPlan(
                roadmap_id=roadmap_id)
            roadmaps_data.append(data)
        print("---processRoadmapsInPortfolio--", roadmaps_data)
        prompt = geetnerateRoadmapPortfolioSnapshot(
            portfolio_title=item.get("title"), roadmaps_data=roadmaps_data)
        response = self.llm_service.run(prompt, self.modelOptions)
        print("----", response)

    def extract_roadmap_knowledge(self, tenant_id):
        """Fetches roadmap data, processes it with LLM, and saves it as knowledge."""
        print("extract_roadmap_knowledge_start", tenant_id)
        portfoliosRoadmapMapping = PortfolioDao.fetchPortfoliosOfRoadmaps(
            tenant_id=tenant_id
        )

        for item in portfoliosRoadmapMapping:
            self.processRoadmapsInPortfolio(item)

        # fetch all portfolios
        # process each portfolio -- fetch all roadmap data
        # then create summary for each

        # query = """
        #     SELECT name, description, type, priority, objective, org_strategic_alignment,
        #         scope, key_results, timeline, constraints, portfolios_mapping,
        #         capabilities, resource_effort_estimate, budget
        #     FROM roadmaps;
        # """
        # roadmap_data = self.fetch_data(query)

        # # Step 2: Process data using the LLM
        # processed_knowledge = self.process_with_llm(roadmap_data)

        # # Step 3: Save processed knowledge into the database
        # for knowledge_item in processed_knowledge:
        #     self.save_to_db(self.table_name, knowledge_item)

        # print("Roadmap knowledge successfully processed and saved.")
