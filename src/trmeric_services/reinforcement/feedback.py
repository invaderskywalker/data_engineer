import re
from src.trmeric_services.reinforcement import core


class SecureFeedbackProcessor:
    def __init__(self, tenant_id, agent_name,feature_name,section=None,subsection=None,user_id:int=None):
        self.tenant_id = tenant_id
        self.agent_name = agent_name
        self.feature_name = feature_name
        self.section = section
        self.subsection = subsection
        self.user_id = user_id

        self._sanitize_pattern = re.compile(r"(confidential|secret|proprietary)", re.IGNORECASE)
        self.rl = core.ReinforcementLearning()

    def get_processed_feedback(self):
        """ Retrieve and sanitize feedback data  """
        
        raw_data = self._get_raw_feedback()
        if not raw_data:
            return []
        return [self._sanitize_item(item) for item in raw_data]
    
    def _get_raw_feedback(self):
        
        """ Fetch raw feedback specific to tenant and feature """
        return self.rl.get_reinforcement_data(
            tenant_id=self.tenant_id,
            agentName=self.agent_name,
            featureName=self.feature_name,
            section = self.section,
            subsection = self.subsection,
            user_id= self.user_id
        )

    def _sanitize_item(self, item):
        """Remove sensitive information from feedback"""
        sanitized = {
            'sentiment': item.get('sentiment', 0),
            'comment': self._sanitize_text(item.get('comment', '')),
            'metadata': self._filter_metadata(item.get('feedback_metadata', {})),
            'created_at': item.get('created_at')
        }
        return sanitized

    def _sanitize_text(self, text):
        return self._sanitize_pattern.sub("[REDACTED]", text)

    def _filter_metadata(self, metadata):
        
        """Filter metadata to allowed fields"""
        allowed_fields = {'section', 'subsection', 'project_id', 'roadmap_id','user_id'}
        try:
            return {k: v for k, v in metadata.items() if k in allowed_fields}
        except AttributeError:
            return {}

