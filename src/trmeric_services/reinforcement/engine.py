import re
import json
import spacy
import numpy as np
from datetime import datetime
from collections import Counter, defaultdict
from src.trmeric_ml.models.xgbooster import XGBoostManager
from src.trmeric_services.reinforcement import core, engine, feedback
from src.trmeric_api.logging.AppLogger import appLogger

class DifferentialRewardEngine:
    def __init__(self, tenant_id,agent_name,feature_name,section=None,subsection=None,user_id:int=None):
        # print("--debug in DifferentialRewardEngine--", tenant_id, feature_name)
        self.tenant_id = tenant_id
        self.agent_name = agent_name
        self.feature_name = feature_name
        self.section = section
        self.subsection = subsection
        self.user_id = user_id
        
        self.feedback_processor = feedback.SecureFeedbackProcessor(tenant_id,agent_name, feature_name,section=section,subsection=subsection, user_id=user_id)
        
        # Weighted reward calculation
        self.base_reward_weights = {
            'sentiment': 0.6,
            'frequency': 0.25,
            'specificity': 0.10,
            'recent_trend': 0.05  # Weight for recent feedback trends
        }
        
        self.nlp = spacy.load("en_core_web_sm")  # Load small English model
        self.pattern_rules = {
            'too_many_suggestions': {
                'keywords': ['too many', 'many roles', 'excessive', 'overwhelming', 'reduce', 'way too'],
                'phrases': [r'too\s+many\s+\w+', r'way\s+too\s+\w+', r'excessive\s+\w+', r'overwhelming'],
                'negative_indicators': ['not_helpful', 'neutral'],
                'rule': "REDUCE NUMBER OF SUGGESTIONS - FOCUS ON TOP RECOMMENDATIONS",
                'priority': 'high'
            },
            'insufficient_suggestions': {
                'keywords': ['only one', 'not enough', 'missing', 'more', 'additional', 'need more'],
                'phrases': [r'only\s+one\s+\w+', r'not\s+enough\s+\w+', r'need\s+more\s+\w+', r'missing\s+\w+'],
                'negative_indicators': ['not_helpful', 'neutral'],
                'rule': "INCREASE SUGGESTION DIVERSITY - PROVIDE MORE OPTIONS",
                'priority': 'high'
            },
            'quality_issues': {
                'keywords': ['quality', 'better', 'improve', 'bad', 'poor', 'wrong', 'incorrect'],
                'phrases': [r'quality\s+\w+\s+\w+', r'could\s+be\s+better', r'not\s+good', r'improve\s+\w+'],
                'negative_indicators': ['not_helpful'],
                'rule': "IMPROVE SUGGESTION QUALITY AND ACCURACY",
                'priority': 'critical'
            },
            'relevance_issues': {
                'keywords': ['irrelevant', 'not relevant', 'wrong', 'doesnt match', 'not what', 'different'],
                'phrases': [r'not\s+relevant', r'doesn.?t\s+match', r'not\s+what\s+\w+', r'completely\s+wrong'],
                'negative_indicators': ['not_helpful'],
                'rule': "ENHANCE CONTEXTUAL RELEVANCE OF SUGGESTIONS",
                'priority': 'critical'
            },
            'timing_issues': {
                'keywords': ['timeline', 'time', 'deadline', 'schedule', 'duration', 'estimation'],
                'phrases': [r'timeline\s+\w+', r'time\s+estimation', r'deadline\s+\w+'],
                'negative_indicators': ['not_helpful', 'neutral'],
                'rule': "IMPROVE TIME ESTIMATION AND PROJECT TIMELINE ACCURACY",
                'priority': 'medium'
            },
            'positive_reinforcement': {
                'keywords': ['good', 'great', 'excellent', 'perfect', 'liked', 'love', 'nice', 'thanks'],
                'phrases': [r'very\s+\w+', r'really\s+good', r'great\s+\w+', r'perfect\s+\w+'],
                'positive_indicators': ['helpful'],
                'rule': "MAINTAIN CURRENT APPROACH - USERS FIND IT VALUABLE",
                'priority': 'maintain'
            }
        }

    def calculate_reward(self):
        """Calculate reward - your data already has numeric sentiment"""
        feedback_data = self.feedback_processor.get_processed_feedback()
        print("--debug feedback_data--", len(feedback_data) if feedback_data else 0, self.tenant_id, self.feature_name)
        if not feedback_data:
            return 0.0
        
        # Your sentiment values are already numeric (1, 0, -1)
        sentiments = [item.get('sentiment', 0) for item in feedback_data]
        
        # Calculate components
        avg_sentiment = sum(sentiments) / len(sentiments)
        frequency_reward = self._calc_frequency(feedback_data)
        specificity_reward = self._calc_specificity(feedback_data)
        trend_reward = self._calc_recent_trend(feedback_data)
        
        # Weighted combination
        base_reward = (
            self.base_reward_weights['sentiment'] * avg_sentiment +
            self.base_reward_weights['frequency'] * frequency_reward +
            self.base_reward_weights['specificity'] * specificity_reward +
            self.base_reward_weights['recent_trend'] * trend_reward
        )
        
        # Apply differential privacy
        final_reward = self._add_noise(base_reward, epsilon=0.4)
        
        print(f"--debug reward_calculation-- avg_sentiment: {avg_sentiment:.3f}, "
              f"frequency: {frequency_reward:.3f}, specificity: {specificity_reward:.3f}, "
              f"trend: {trend_reward:.3f}, final: {final_reward:.3f}")
        
        return np.clip(final_reward, -1.0, 1.0)

    def _map_ui_sentiment(self, sentiment_value):
        """Map UI feedback to numeric sentiment"""
        if isinstance(sentiment_value, str):
            return self.ui_sentiment_mapping.get(sentiment_value.lower(), 0)
        return self.ui_sentiment_mapping.get(sentiment_value, sentiment_value)

    def _calc_frequency(self, data, freq_days=7):
        """Calculate recent feedback frequency - shorter window for UI feedback"""
        try:
            current_time = datetime.now()
            recent_count = 0
            
            for item in data:
                created_at = item.get('created_at')
                if isinstance(created_at, str):
                    try:
                        # Handle different datetime formats
                        if 'T' in created_at:
                            created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                        else:
                            created_at = datetime.fromisoformat(created_at)
                    except ValueError:
                        continue
                
                if created_at:
                    days_diff = (current_time - created_at.replace(tzinfo=None)).days
                    if days_diff <= freq_days:
                        recent_count += 1
            
            # Normalize: optimal is 5-10 feedback items per week
            return min(recent_count / 8.0, 1.0)
        except Exception as e:
            print(f"--debug frequency calc error-- {e}")
            return 0.0

    def _calc_specificity(self, data):
        """Calculate comment specificity - reward detailed feedback"""
        if not data:
            return 0.0
        
        total_specificity = 0
        comment_count = 0
        
        for item in data:
            comment = item.get('comment', '').strip()
            if comment and len(comment) > 2:  # Non-trivial comments
                # Reward longer, more detailed comments
                specificity = min(len(comment) / 100.0, 1.0)
                # Bonus for specific keywords
                if any(word in comment.lower() for word in ['because', 'should', 'could', 'would', 'specific']):
                    specificity *= 1.2
                total_specificity += specificity
                comment_count += 1
        
        return total_specificity / max(comment_count, 1)

    def _calc_recent_trend(self, data, trend_days=3):
        """Calculate recent trend - are things getting better or worse?"""
        if len(data) < 2:
            return 0.0
        
        try:
            # Sort by date
            sorted_data = sorted(data, key=lambda x: x.get('created_at', ''))
            recent_data = [item for item in sorted_data 
                          if self._is_recent(item.get('created_at'), trend_days)]
            
            if len(recent_data) < 2:
                return 0.0
            
            # Get sentiment values directly (already numeric)
            recent_sentiments = [item.get('sentiment', 0) for item in recent_data]
            
            # Simple linear trend
            n = len(recent_sentiments)
            if n < 2:
                return 0.0
            
            # Compare first half to second half
            mid = n // 2
            first_half_avg = sum(recent_sentiments[:mid]) / mid if mid > 0 else 0
            second_half_avg = sum(recent_sentiments[mid:]) / (n - mid)
            
            trend = second_half_avg - first_half_avg
            return np.clip(trend, -1.0, 1.0)
            
        except Exception as e:
            print(f"--debug trend calc error-- {e}")
            return 0.0

    def _is_recent(self, created_at, days):
        """Check if feedback is within recent days"""
        try:
            if isinstance(created_at, str):
                created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            days_diff = (datetime.now() - created_at.replace(tzinfo=None)).days
            return days_diff <= days
        except:
            return False

    def _add_noise(self, value, epsilon=0.4):
        """Add Laplace noise for differential privacy"""
        scale = 1 / epsilon
        noise = np.random.laplace(0, scale * 0.08)  # Reduced noise for UI feedback
        return value + noise

    def analyze_feedback_patterns(self):
        """Analyze patterns with your actual feedback format + XGBoost enrichment"""
        feedback_data = self.feedback_processor.get_processed_feedback()
        print("--debug analyzing patterns from feedback--", len(feedback_data) if feedback_data else 0)
        
        if not feedback_data:
            return [], {}

        rules = []
        metadata = {'feedback_ids': [], 'pattern_scores': {}, 'feedback_stats': {}}
        
        # Calculate feedback stats
        sentiments = [item.get('sentiment', 0) for item in feedback_data]
        feedback_stats = {
            'positive': sum(1 for s in sentiments if s == 1),
            'neutral': sum(1 for s in sentiments if s == 0), 
            'negative': sum(1 for s in sentiments if s == -1),
            'total': len(feedback_data),
            'avg_sentiment': sum(sentiments) / len(sentiments)
        }
        feedback_stats.update({
            'positive_ratio': feedback_stats['positive'] / feedback_stats['total'],
            'negative_ratio': feedback_stats['negative'] / feedback_stats['total'],
            'neutral_ratio': feedback_stats['neutral'] / feedback_stats['total']
        })
        
        comments_with_text = sum(1 for item in feedback_data if len(item.get('comment', '').strip()) > 2)
        
        # Pattern scoring
        pattern_scores = defaultdict(float)
        
        for item in feedback_data:
            comment = item.get('comment', '').strip().lower()
            sentiment = item.get('sentiment', 0)
            
            if len(comment) > 2:  # Only analyze meaningful comments
                for pattern_name, config in self.pattern_rules.items():
                    score = 0.0
                    
                    # Weight based on sentiment - negative feedback gets higher priority
                    if 'negative_indicators' in config:
                        if sentiment <= 0:  # Neutral or negative feedback
                            weight = 2.0 if sentiment == -1 else 1.5
                        else:
                            weight = 0.5
                    elif 'positive_indicators' in config:
                        if sentiment == 1:  # Positive feedback
                            weight = 1.5
                        else:
                            weight = 0.5
                    else:
                        weight = 1.0
                    
                    # Keyword matching
                    for keyword in config['keywords']:
                        if keyword in comment:
                            score += weight
                            # print(f"--debug pattern match-- {pattern_name}: '{keyword}' found in comment, weight: {weight}")
                    
                    # Phrase matching
                    for phrase_pattern in config.get('phrases', []):
                        if re.search(phrase_pattern, comment):
                            score += weight * 1.5
                            print(f"--debug phrase match-- {pattern_name}: pattern '{phrase_pattern}' matched")
                    
                    if score > 0:
                        pattern_scores[pattern_name] += score
                        if item.get('id'):
                            metadata['feedback_ids'].append(item['id'])

        # Store feedback stats
        metadata['feedback_stats'] = feedback_stats
        metadata['comments_with_text'] = comments_with_text
        
        # Generate rules based on patterns and thresholds
        total_feedback = len(feedback_data)
        
        for pattern_name, score in pattern_scores.items():
            # Dynamic threshold based on feedback volume
            threshold = 0.15 if total_feedback > 10 else 0.25
            confidence = score / total_feedback
            
            # print(f"--debug pattern analysis-- {pattern_name}: score={score}, confidence={confidence:.3f}, threshold={threshold}")
            
            if confidence >= threshold:
                rule_config = self.pattern_rules[pattern_name]
                rules.append(rule_config['rule'])
                metadata['pattern_scores'][pattern_name] = {
                    'confidence': confidence,
                    'priority': rule_config.get('priority', 'medium'),
                    'raw_score': score
                }
        
        # High-level sentiment-based rules
        if feedback_stats['negative_ratio'] > 0.3:  # More than 30% negative
            rules.append("CRITICAL: HIGH NEGATIVE FEEDBACK - REVIEW AND IMPROVE CORE FUNCTIONALITY")
            metadata['pattern_scores']['high_negative_feedback'] = {
                'confidence': feedback_stats['negative_ratio'],
                'priority': 'critical'
            }
        elif feedback_stats['positive_ratio'] > 0.7:  # More than 70% positive
            rules.append("EXCELLENT PERFORMANCE - MAINTAIN CURRENT QUALITY STANDARDS")
            metadata['pattern_scores']['high_satisfaction'] = {
                'confidence': feedback_stats['positive_ratio'],
                'priority': 'maintain'
            }
        elif feedback_stats['neutral_ratio'] > 0.6:  # More than 60% neutral
            rules.append("MODERATE PERFORMANCE - FOCUS ON MAKING RESPONSES MORE ENGAGING")
            metadata['pattern_scores']['high_neutral_feedback'] = {
                'confidence': feedback_stats['neutral_ratio'],
                'priority': 'medium'
            }

        # ========================================
        # XGBoost + SHAP: Enrich Latest Feedback
        # ========================================
        try:
            # Enrich the latest feedback row (for real-time insight)
            latest_feedback = feedback_data[0]
            enriched_feedback = self._enrich_feedback_with_xgboost(latest_feedback, str(self.tenant_id))
            # print("--debug xgboost-----enriched_feedback--", enriched_feedback.get("xgboost_insight"))
            # Add insight to metadata
            insight = enriched_feedback.get("xgboost_insight")
            if insight:
                metadata["xgboost_quality"] = insight
                score = insight["score"]
                print(f"--debug [XGBoost] Feedback Quality: {score:.2f}/10")
                
                # Trigger SHAP-driven rules (based on top drivers)
                top_driver = insight.get("top_drivers", [{}])[0] if insight.get("top_drivers") else {}
                if top_driver.get("impact", 0) < -1.5:
                    feature = top_driver["feature"]
                    impact = top_driver["impact"]
                    if "vague" in feature or "vague" in comment:
                        rules.append("CRITICAL: FEEDBACK VAGUE - PROMPT FOR SPECIFICS")
                    elif "sentiment" in feature and impact < -1.8:
                        rules.append("HIGH: ADDRESS USER FRUSTRATION - OFFER CLARIFICATION")
                    elif "comment_length" in feature and top_driver.get("value", 0) < 20:
                        rules.append("MEDIUM: COMMENT SHORT - ENCOURAGE MORE DETAIL")
                    print(f"--debug [SHAP Rule] {feature} ({impact:+.1f})")
                
                # Quality-based adjustments (e.g., for temperature in policy)
                if score < 3.0:
                    metadata["suggested_temperature"] = 0.2  # Low temp for focus
                elif score < 5.0:
                    metadata["suggested_temperature"] = 0.4  # Medium focus
                else:
                    metadata["suggested_temperature"] = None  # Default
            
        except Exception as e:
            print(f"--debug [XGBoost Error] {str(e)}")
            # Fail gracefully - pattern rules continue
        
        print("--debug final rules generated--", len(rules))
        # print("--debug feedback_stats--", feedback_stats)
        
        return rules, metadata


    def _sentiment_to_string(self, sentiment):
        """Convert sentiment back to UI string for analysis"""
        if sentiment == 1:
            return 'helpful'
        elif sentiment == -1:
            return 'not_helpful'
        else:
            return 'neutral'

    
    def _enrich_feedback_with_xgboost(self, feedback_row: dict, tenant_id: str) -> dict:
        """
        Enrich a single feedback row with XGBoost insight.
        Input: One row from tango_reinforcement (dict)
        Output: Same row + xgboost_insight (dict or None)
        """
        try:
            comment = str(feedback_row.get("comment", "")).lower().strip()
            meta = feedback_row.get("feedback_metadata") or {}
            meta = meta if isinstance(meta, dict) else {}

            # Build feature dict (MUST match training exactly)
            features = {
                "comment_length": len(comment),
                "word_count": len(comment.split()),
                "has_question": int("?" in comment),
                "has_suggestion": int(any(w in comment for w in ["add", "remove", "change", "suggest", "try", "include"])),
                "has_specificity": int(any(w in comment for w in ["because", "due to", "reason", "since", "example"])),
                "has_technical": int(any(w in comment for w in ["api", "ui", "bug", "error", "database", "code"])),
                "has_vague": int(any(w in comment for w in ["vague", "wild", "confusing", "not clear", "weird"])),
                "sentiment": feedback_row.get("sentiment", 0),  # default to 0 if missing
                "metadata_count": len(meta),
                "has_section": int("section" in meta),
                "has_project": int("project_id" in meta or "project" in meta),
            }

            xg_manager = XGBoostManager(tenant_id=tenant_id)  # This returns the existing instance
            insight = xg_manager.predict("feedback_quality", features, top_k=3)

            feedback_row["xgboost_insight"] = insight  # Already a dict or None
            print("\n\n--debug xgboost_insight----------", feedback_row['xgboost_insight'])

            if insight:
                appLogger.info({
                    "event": "xgboost_enriched","tenant_id": tenant_id,
                    "percentile": insight.get("percentile"),"score": insight["score"],
                    "top_driver": insight["top_drivers"][0]["feature"] if insight["top_drivers"] else None
                })
            else:
                appLogger.error({"event": "xgboost_failed","tenant_id": tenant_id,"reason": "No model or prediction failed"})

            return feedback_row

        except Exception as e:
            appLogger.error({"event": "xgboost_enrich_error","tenant_id": tenant_id,"error": str(e),"feedback_id": feedback_row})
            feedback_row["xgboost_insight"] = None
            return feedback_row



    # def _enrich_feedback_with_xgboost(self, feedback_row, tenant_id):
    #     """
    #     Enrich a single feedback row with XGBoost insight.
    #     Input: One row from tango_reinforcement (dict)
    #     Output: Same row + xgboost_insight (dict)
    #     """
    #     # 1. Extract raw values
    #     comment = str(feedback_row.get("comment", "")).lower().strip()
    #     meta = feedback_row.get("feedback_metadata") or {}
    #     meta = meta if isinstance(meta, dict) else {}

    #     # 2. Build feature dict (MUST match training)
    #     features = {
    #         "comment_length": len(comment),
    #         "word_count": len(comment.split()),
    #         "has_question": int("?" in comment),
    #         "has_suggestion": int(any(w in comment for w in ["add", "remove", "change", "suggest", "try", "include"])),
    #         "has_specificity": int(any(w in comment for w in ["because", "due to", "reason", "since", "example"])),
    #         "has_technical": int(any(w in comment for w in ["api", "ui", "bug", "error", "database", "code"])),
    #         "has_vague": int(any(w in comment for w in ["vague", "wild", "confusing", "not clear", "weird"])),
    #         "sentiment": feedback_row["sentiment"],
    #         "metadata_count": len(meta),
    #         "has_section": int("section" in meta),
    #         "has_project": int("project_id" in meta or "project" in meta),
    #     }

    #     # 3. Run XGBoost
    #     xg = XGBoostManager(tenant_id=tenant_id)
    #     insight = xg.predict(f"feedback_quality", features)
    #     # insight = xg.predict("feedback_quality", features)
    #     print("DEBUG insight type:", type(insight))
    #     appLogger.info({"insight type": type(insight)})
        


        # 4. Attach JSON result
        # feedback_row["xgboost_insight"] = clean_for_json(insight.to_dict()) if insight else None
        feedback_row["xgboost_insight"] = insight if insight else None

        # print("\n\n---debug clean----xgboost insight---", len(feedback_row["xgboost_insight"]))

        return feedback_row