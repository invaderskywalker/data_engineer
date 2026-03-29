
from src.database.dao import ProjectsDao, RoadmapDao
from src.utils.fuzzySearch import *

class Anonymizer:
    def __init__(self, tenant_id, user_id):
        self.tenant_id = tenant_id
        self.user_id = user_id
        
        self.PII_TEXT_FOR_LLM = ""
        self.hashed_name_to_real_name = {}
        self.reverse_hashed_name_to_real_name = {}
        self.hashed_team_member_names_mapping = {}
        
        self.eligibleProjects = ProjectsDao.FetchAvailableProject(self.tenant_id, self.user_id)
        self.create_data()

    
    def create_data(self):
        self.fetchAndHashProjectNames()
        self.fetchAndHashRoadmapNames()
        self.fetchAndHashTeamMemberNames()
    
    def anonymize(self, text):
        anonymizedText = self.updateTextWithHashProjectNames(text)
        anonymizedText = fuzzy_match_and_replace_with_actual(
            text=anonymizedText, actual_names=self.hashed_project_names_mapping.values())
        anonymizedText = self.updateTextWithHashProjectNames(anonymizedText)
        return anonymizedText
    
    def deanonymize(self, segment):
        pattern = r'PM_HASH_\d+'
        result = re.sub(pattern, lambda match: self.hashed_name_to_real_name.get(
            match.group(0), match.group(0)), segment)
        result = self.deanonymizeUserDataWithHashProjectNames(result)
        result = self.deanonymizeUserDataWithHashRoadmapNames(result)
        result = self.deanonymizeTextWithTeamMemberNames(result)
        return result
    
    
    def fetchAndHashProjectNames(self):
        projectNames = ProjectsDao.FetchProjectNamesForIds(
            self.eligibleProjects)

        counter = 1
        temp = {}
        for project_data in projectNames:
            project_actual_name = project_data['project_title']
            hashed_name = f"PROJECT_NAME_HASH_{str(counter).zfill(8)}"
            counter = counter + 1
            temp[hashed_name] = project_actual_name
        # print("--fetchAndHashProjectNames---", temp)
        self.hashed_project_names_mapping = temp

    def fetchAndHashTeamMemberNames(self):
        teamMemberNames = ProjectsDao.FetchTeamMemberNames(
            self.eligibleProjects)

        counter = 1
        temp = {}
        for name in teamMemberNames:
            project_actual_name = name['member_name']
            hashed_name = f"TEAM_MEMBER_NAME_HASH_{str(counter).zfill(8)}"
            counter = counter + 1
            temp[hashed_name] = project_actual_name
        # print("--fetchAndHashTeamMemberNames---", temp)
        self.hashed_team_member_names_mapping = temp

    def fetchAndHashRoadmapNames(self):
        roadmapNames = RoadmapDao.FetchRoadmapNames(self.tenant_id)

        counter = 1
        temp = {}
        for roadmap_data in roadmapNames:
            roadmap_actual_name = roadmap_data['title']
            hashed_name = f"ROADMAP_NAME_HASH_{str(counter).zfill(8)}"
            counter = counter + 1
            temp[hashed_name] = roadmap_actual_name
        self.hashed_roadmap_names_mapping = temp

    def updateTextWithHashRoadmapNames(self, text):
        try:
            name_to_hash = {v: k for k,
                            v in self.hashed_roadmap_names_mapping.items()}

            def replace_match(match):
                actual_name = match.group(0)
                hash_key = name_to_hash.get(actual_name, None)
                if hash_key:
                    return hash_key
                return actual_name

            pattern = re.compile('|'.join(re.escape(
                name) for name in self.hashed_roadmap_names_mapping.values()), re.IGNORECASE)
            replaced_text = pattern.sub(replace_match, text)
            return replaced_text
        except Exception as e:
            return text

    def updateTextWithHashProjectNames(self, text):
        try:
            name_to_hash = {v: k for k,
                            v in self.hashed_project_names_mapping.items()}

            def replace_match(match):
                actual_name = match.group(0)
                hash_key = name_to_hash.get(actual_name, None)
                if hash_key:
                    return hash_key
                return actual_name

            pattern = re.compile('|'.join(re.escape(
                name) for name in self.hashed_project_names_mapping.values()), re.IGNORECASE)
            replaced_text = pattern.sub(replace_match, text)
            return replaced_text
        except Exception as e:
            return text

    def updateTextWithHashedTeamMemberNames(self, text):
        try:
            name_to_hash = {v: k for k,
                            v in self.hashed_team_member_names_mapping.items()}

            def replace_match(match):
                actual_name = match.group(0)
                hash_key = name_to_hash.get(actual_name, None)
                if hash_key:
                    return hash_key
                return actual_name

            pattern = re.compile('|'.join(re.escape(
                name) for name in self.hashed_team_member_names_mapping.values()), re.IGNORECASE)
            replaced_text = pattern.sub(replace_match, text)
            return replaced_text
        except Exception as e:
            return text

    def deanonymizeUserDataWithHashProjectNames(self, text):
        hash_to_name = {k: v for k,
                        v in self.hashed_project_names_mapping.items()}

        def replace_match(match):
            hash_key = match.group(0)
            actual_name = hash_to_name.get(hash_key, None)
            if actual_name:
                return actual_name
            return hash_key

        pattern = re.compile('|'.join(re.escape(hash_key)
                             for hash_key in hash_to_name.keys()), re.IGNORECASE)
        replaced_text = pattern.sub(replace_match, text)
        return replaced_text

    def deanonymizeUserDataWithHashRoadmapNames(self, text):
        hash_to_name = {k: v for k,
                        v in self.hashed_roadmap_names_mapping.items()}

        def replace_match(match):
            hash_key = match.group(0)
            actual_name = hash_to_name.get(hash_key, None)
            if actual_name:
                return actual_name
            return hash_key

        pattern = re.compile('|'.join(re.escape(hash_key)
                             for hash_key in hash_to_name.keys()), re.IGNORECASE)
        replaced_text = pattern.sub(replace_match, text)
        return replaced_text

    def deanonymizeTextWithTeamMemberNames(self, text):
        hash_to_name = {k: v for k,
                        v in self.hashed_roadmap_names_mapping.items()}

        def replace_match(match):
            hash_key = match.group(0)
            actual_name = hash_to_name.get(hash_key, None)
            if actual_name:
                return actual_name
            return hash_key

        pattern = re.compile('|'.join(re.escape(hash_key)
                             for hash_key in hash_to_name.keys()), re.IGNORECASE)
        replaced_text = pattern.sub(replace_match, text)
        return replaced_text
