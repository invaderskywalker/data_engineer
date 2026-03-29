import os
import json
import shap
import base64
import tempfile
import xgboost as xgb
# from pathlib import Path
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from src.trmeric_database.dao import TangoDao
from src.trmeric_api.logging.AppLogger import appLogger


# print("=== ACTUAL XGBOOST VERSION AT RUNTIME ===")
# print("xgboost version:", xgb.__version__)
# print("Has load_raw method?", hasattr(xgb.Booster, "load_raw"))
# print("Has load_model method?", hasattr(xgb.Booster, "load_model"))
# print("=======================================")


@dataclass
class XGBoostInsight:
    score: float
    score_name: str
    percentile: Optional[float] = None
    top_drivers: Optional[List[Dict[str, Any]]] = None
    trained_on: Optional[int] = None
    model_version: Optional[str] = None
    base_value: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "score": round(float(self.score), 2),  
            "score_name": self.score_name,
            "percentile": round(float(self.percentile), 1) if self.percentile is not None else None,
            "top_drivers": [
                {
                    "feature": d["feature"],
                    "value": d["value"],
                    "impact": round(float(d["impact"]), 2),  #Convert np.float32 to float
                    "direction": d["direction"]
                }
                for d in self.top_drivers or []
            ],
            "trained_on": self.trained_on,
            "model_version": self.model_version,
            "base_value": round(float(self.base_value), 2) if self.base_value is not None else None,
            "explanation": f"{self.score_name} is {self.score:.1f}/10"
        }


class XGBoostManager:
    _instances: Dict[str, "XGBoostManager"] = {}

    # _models_dir = Path(".cache/model_cache")
    # _meta_dir = Path(".cache/model_cache/metadata")

    def __new__(cls, tenant_id: str = "global"):
        if tenant_id not in cls._instances:
            cls._instances[tenant_id] = super().__new__(cls)
        return cls._instances[tenant_id]

    def __init__(self, tenant_id: str = "global", debug: bool = False):
        if hasattr(self, "initialized"):
            return
        self.tenant_id = tenant_id
        self.debug = debug
        self._metadata: Dict[str, Dict] = {}
        self._models: Dict[str, xgb.Booster] = {}
        self._explainers: Dict[str, shap.TreeExplainer] = {}
        self._load_all()
        self.initialized = True

    def _load_all(self):
        model_name = "feedback_quality"
        self._load_from_db(model_name=model_name)

    def _load_from_db(self, model_name: str):
        model_key = f"{model_name}_model_{self.tenant_id}"
        meta_key = f"{model_name}_metadata_{self.tenant_id}"

        model_row = TangoDao.fetchLatestTangoStatesTenant(tenant_id=self.tenant_id, key=model_key)
        # print("--debug model_Row-----", len(model_row))
        if not model_row:
            print(f"[XGBoost] No model found for {model_name}")
            return

        payload = json.loads(model_row[0]["value"])
        fmt = payload.get("format", "")
        print(f"[XGBoost] Model format: {fmt}, Model payload: {payload.get('model')[:200]}")

        booster = xgb.Booster()
        raw_bytes = base64.b64decode(payload["model"])
        print(f"Decoded bytes length: {len(raw_bytes)}")

        # Write to temporary file
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            tmp_file.write(raw_bytes)
            temp_filename = tmp_file.name

        try:
            booster.load_model(temp_filename)  
            # print(f"[XGBoost] Booster successfully loaded via temp file | Format: {fmt}")
            # print(f"[XGBoost] Number of features: {booster.num_features()}")
        except Exception as e:
            print(f"[XGBoost] Failed to load model: {str(e)}")
            raise
        finally:
            try:
                os.unlink(temp_filename)
            except Exception:
                print("Error unlinking temp file")
                pass

        meta_row = TangoDao.fetchLatestTangoStatesTenant(tenant_id=self.tenant_id, key=meta_key)
        if meta_row:
            metadata = json.loads(meta_row[0]["value"])
            feature_names = metadata.get("features", [])
            if feature_names:
                booster.feature_names = feature_names  # This helps with validation and SHAP
            self._metadata[model_name] = metadata
        else:
            self._metadata[model_name] = {"trained_on": 0}

        # Store model and explainer
        self._models[model_name] = booster
        self._explainers[model_name] = shap.TreeExplainer(booster)

        # print(f"[XGBoost] Model and metadata fully loaded for {model_name}")

    def predict(self, feature_name: str, features: Dict[str, Any], top_k: int = 3) -> Optional[Dict[str, Any]]:
        if feature_name not in self._models:
            print(f"[XGBoost] No model for '{feature_name}'")
            return None

        try:
            model = self._models[feature_name]
            expected_features = model.feature_names or []

            missing = [f for f in expected_features if f not in features]
            extra = [f for f in features if f not in expected_features]
            if missing or extra:
                raise ValueError(f"Feature mismatch | missing={missing} | extra={extra}")

            # Prepare DMatrix
            ordered_values = [features[f] for f in expected_features]
            dmatrix = xgb.DMatrix([ordered_values], feature_names=expected_features)

            # Prediction
            raw_score = float(model.predict(dmatrix)[0])
            explainer = self._explainers[feature_name]
            shap_vals = explainer.shap_values(dmatrix)[0]
            base = float(explainer.expected_value)

            # Top drivers
            drivers = sorted(zip(expected_features, shap_vals), key=lambda x: abs(x[1]), reverse=True)[:top_k]
            top_drivers = [
                {"feature": f, "value": features[f], "impact": round(v, 2), "direction": "increases" if v > 0 else "decreases"}
                for f, v in drivers
            ]

            # Metadata
            meta = self._metadata.get(feature_name, {})
            hist = meta.get("score_distribution", [])
            percentile = self._percentile(raw_score, hist) if hist else None

            insight = XGBoostInsight(
                score=raw_score,
                score_name=feature_name.replace("_", " ").title(),
                percentile=percentile,
                top_drivers=top_drivers,
                trained_on=meta.get("trained_on"),
                model_version=meta.get("version", "v1"),
                base_value=round(base, 2),
            )

            result = insight.to_dict()
            print(f"[XGBoost] Prediction complete | Score: {raw_score:.2f}")
            return result

        except Exception as e:
            print(f"[XGBoost] Inference error: {str(e)[:200]}")
            return None

    @staticmethod
    def _percentile(score: float, distribution: List[float]) -> float:
        if not distribution:
            return 50.0
        return sum(s < score for s in distribution) / len(distribution) * 100











########### hard time doing loading from db #####3
        # booster = xgb.Booster()
        # raw_bytes = base64.b64decode(payload["model"])
        # print(f"Decoded bytes length: {len(raw_bytes)}")

        # # Unified loading: works for both raw and JSON format in XGBoost 1.7.6
        # buffer = io.BytesIO(raw_bytes)
        # try:
        #     booster.load_model(buffer)
        #     print(f"[XGBoost] Booster successfully loaded from base64 via BytesIO | Format: {fmt}")
        #     print(f"[XGBoost] Number of features: {booster.num_features()}")
        # except Exception as e:
        #     print(f"[XGBoost] Failed to load model: {str(e)}")
        #     raise

        # if fmt.endswith("_raw_base64"):
        #     try:
        #         raw_bytes = base64.b64decode(payload["model"])
        #         print(f"Decoded bytes length: {len(raw_bytes)}")
                
        #         # This works for raw bytes from save_raw() in 1.7.x
        #         buffer = io.BytesIO(raw_bytes)
        #         booster.load_model(buffer)
                
        #         print(f"[XGBoost] Booster loaded via load_model(BytesIO) from raw_base64 | Num features: {booster.num_features()}")
        #     except Exception as e:
        #         print("--debug load error--------", str(e))
        #         raise  # To see full traceback in logs
            # try:
            #     raw_bytes = base64.b64decode(payload["model"])
            #     print(f"Decoded bytes length: {len(raw_bytes)}")
            #     booster.load_raw(raw_bytes)  # <--- ONLY this line
            #     print(f"[XGBoost] Booster loaded via load_raw() | Num features: {booster.num_features()}")
            # except Exception as e:
            #     print("--debug error here--------", str(e)[:20])

            # raw_bytes = base64.b64decode(payload["model"])
            # print(f"Decoded bytes length: {len(raw_bytes)}")
            # booster.load_raw(raw_bytes)   # MUST be load_raw, not load_model
            # print(f"[XGBoost] Booster loaded via load_raw() | Num features: {booster.num_features()}")
            # # b64 = re.sub(r"\s+", "", payload["model"])  # Clean whitespace if any
            # # raw_bytes = base64.b64decode(b64)
            # raw_bytes = base64.b64decode(payload["model"])
            # print(f"Decoded bytes length: {len(raw_bytes)}")

            # # CRITICAL FIX: Use load_raw(), NOT load_model()
            # booster.load_raw(raw_bytes)
            # raw_bytes = base64.b64decode(payload["model"])
            # buffer = io.BytesIO(raw_bytes)
            # booster.load_model(buffer)  # Works everywhere

            # print(f"[XGBoost] Booster loaded via load_raw() | Num features: {booster.num_features()}")
        # else:
        #     raise ValueError(f"Unknown model format: {fmt}")

        # Optional: Set feature names from metadata (important for SHAP and validation)
