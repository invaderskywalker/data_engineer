# test_xgboost.py
import sys
sys.path.append('/home/ubuntu/trmeric-ai')

from src.trmeric_ml.models.xgbooster import XGBoostManager

# cd /home/ubuntu/trmeric-ai
# python src/trmeric_ml/models/training.py

features = {
    "comment_length": 15,
    "word_count": 3,
    "has_question": 0,
    "has_suggestion": 0,
    "has_specificity": 0,
    "has_technical": 0,
    "has_vague": 1,
    "sentiment": -1,
    "metadata_count": 0,
    "has_section": 0,
    "has_project": 0
}

xg = XGBoostManager(tenant_id="625")
insight = xg.predict("feedback_quality", features)
print(insight.to_dict())