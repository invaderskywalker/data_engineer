# train_feedback_quality.py
# import io
import os
import json
import base64
import tempfile
import traceback
import pandas as pd
import xgboost as xgb
from pathlib import Path
from datetime import datetime
import sys
sys.path.append('/home/ubuntu/trmeric-ai') 
from src.trmeric_api.logging.AppLogger import appLogger
from src.trmeric_database.dao import ReinforcementDao, TangoDao

# ========================================
# CONFIG
# ========================================
MODEL_NAME = "feedback_quality"
MODEL_DIR = Path(".cache/model_cache")
META_DIR = Path(".cache/model_cache/metadata")
MODEL_DIR.mkdir(parents=True, exist_ok=True)
META_DIR.mkdir(parents=True, exist_ok=True)

## Problem: xgboost training happens in cron machine which creates the file in .cache folder 
## the code for reinforcement runs in main machine which doesn't have access to these files
## so xgboost insights remains None, need to store it in diff place so that both machines has access to it
## for now doing in postgres in tango_states with unique key for the file name


def start_training(tenant_id):
    try:
        print(f"[{datetime.now()}] Starting training for {MODEL_NAME}...")

        # ========================================
        # 1. FETCH ALL FEEDBACK
        # ========================================
        data = ReinforcementDao.fetchTangoReinforcementData(
            projection_attrs=["id", "comment", "sentiment", "feedback_metadata"],
            tenant_id = tenant_id
        )
        raw = {"data": data}
        if not raw or "data" not in raw or not data:
            raise ValueError("No data returned from get_reinforcement_data")

        df = pd.DataFrame(raw["data"])
        print(f"Loaded {len(df)} feedback rows")

        # ========================================
        # 2. FEATURE ENGINEERING
        # ========================================
        def extract_features(row):
            comment = str(row.get("comment", "")).lower().strip()
            meta = row.get("feedback_metadata") or {}
            meta = meta if isinstance(meta, dict) else {}

            return pd.Series({
                "comment_length": len(comment),
                "word_count": len(comment.split()),
                "has_question": int("?" in comment),
                "has_suggestion": int(any(w in comment for w in ["add", "remove", "change", "suggest", "try", "include"])),
                "has_specificity": int(any(w in comment for w in ["because", "due to", "reason", "since", "example"])),
                "has_technical": int(any(w in comment for w in ["api", "ui", "bug", "error", "database", "code"])),
                "has_vague": int(any(w in comment for w in ["vague", "wild", "confusing", "not clear", "weird"])),
                "sentiment": row["sentiment"],
                "metadata_count": len(meta),
                "has_section": int("section" in meta),
                "has_project": int("project_id" in meta or "project" in meta),
            })

        features = df.apply(extract_features, axis=1)
        print(f"Features engineered: {features.columns.tolist()}")

        # ========================================
        # 3. TARGET: feedback_quality_score (0–10)
        # ========================================
        def compute_quality(row):
            base = 5.0
            sent = row["sentiment"]
            comment = str(row.get("comment", "")).lower()

            # Sentiment
            if sent == 1:   base += 2.5
            if sent == -1:  base -= 3.0

            # Length
            if len(comment) > 50:     base += 1.5
            elif len(comment) < 15:   base -= 1.5

            # Clarity
            if any(w in comment for w in ["because", "example", "suggest"]):
                base += 2.0
            if any(w in comment for w in ["vague", "wild", "confusing"]):
                base -= 2.5

            # Actionable
            if any(w in comment for w in ["add", "remove", "change"]):
                base += 1.0

            return round(max(0.0, min(10.0, base)), 1)

        df["feedback_quality_score"] = df.apply(compute_quality, axis=1)
        print(f"Target distribution: min={df['feedback_quality_score'].min()}, max={df['feedback_quality_score'].max()}, mean={df['feedback_quality_score'].mean():.2f}")

        # ========================================
        # 4. TRAIN XGBOOST
        # ========================================
        X = features
        y = df["feedback_quality_score"]

        # CRITICAL: Force base_score to Python float
        mean_score = float(y.mean())

        model = xgb.XGBRegressor(
            objective="reg:squarederror",
            n_estimators=100,
            max_depth=5,
            learning_rate=0.1,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            base_score = mean_score
        )
        model.fit(X, y)

        print("Model trained")

        # ========================================
        # 5. SAVE MODEL + METADATA (FIXED)
        # ========================================
        # model_path = MODEL_DIR / f{MODEL_NAME}_{tenant_id}.json"
        # # Save model with feature names
        # model.save_model(str(model_path))
        # ## henceforth saving in tango state
        # booster = model.get_booster()
        # # Raw binary model bytes
        # raw_model = booster.save_raw()  # bytes
        # encoded_model = base64.b64encode(raw_model).decode("utf-8")
        # # print("\n\n-----debug raw_model------------", encoded_model)

        booster = model.get_booster()
        # Create a temporary file
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            temp_filename = tmp_file.name

        # Save model to the temp file (XGBoost 1.7.6 supports this)
        booster.save_model(temp_filename)

        # Read the file bytes into memory
        with open(temp_filename, "rb") as f:
            model_bytes = f.read()

        # Clean up the temp file
        os.unlink(temp_filename)

        # Encode to base64
        encoded_model = base64.b64encode(model_bytes).decode("utf-8")

        # Save to bytes buffer (JSON format)
        # buffer = io.BytesIO()
        # booster.save_model(buffer)
        # buffer.seek(0)
        # model_bytes = buffer.getvalue()
        # encoded_model = base64.b64encode(model_bytes).decode("utf-8")

        payload = {
            "format": "xgboost_feedback_quality_json_base64",
            "model": encoded_model
        }
        TangoDao.upsertTangoState(
            tenant_id = tenant_id,
            user_id = None,
            key = f"{MODEL_NAME}_model_{tenant_id}",
            value = json.dumps(payload),
            session_id = None
        )
        print(f"Model saved with feature names: ")

        # Save metadata (no scientific notation)
        meta = {
            "version": "v1.0",
            "trained_on": len(df),
            "last_updated": datetime.now().isoformat(),
            "features": X.columns.tolist(),  # Critical: save feature order
            "target": "feedback_quality_score (0–10, heuristic)",
            "score_distribution": y.tolist(),  # For percentile
            "score_stats": {
                "mean": float(y.mean()),
                "std": float(y.std()),
                "min": float(y.min()),
                "max": float(y.max())
            },
            "sample_comments": df["comment"].head(3).tolist()
        }

        meta_path = META_DIR / f"{MODEL_NAME}_{tenant_id}.json"
        with open(meta_path, "w") as f:
            json.dump(meta, f, indent=2, default=float)  # Ensures no 'E' notation

        ##saving metadata
        TangoDao.upsertTangoState(
            tenant_id = tenant_id,
            user_id = None,
            key = f"{MODEL_NAME}_metadata_{tenant_id}",
            value = json.dumps(meta,indent=2, default=float),
            session_id = None
        )

        print(f"Metadata saved: {meta_path} for tenant {tenant_id}")
        print(f"Ready for XGBoostManager to load!")


    except Exception as e:
        appLogger.error({"event": "xgboost_training","error": str(e),"traceback": traceback.format_exc()})
        print(f"Error during training: {e}")




if __name__ == "__main__":
    pass
    # start_training(tenant_id=776)