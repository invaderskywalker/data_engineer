import pandas as pd
import xgboost as xgb
from pathlib import Path
import json
import numpy as np

TENANT_ID = 776
FEATURES_FILE = f"full_features_for_xgboost_{TENANT_ID}.csv"
MODELS_DIR = Path(".cache/model_cache")
MODELS_DIR.mkdir(parents=True, exist_ok=True)
METADATA_DIR = MODELS_DIR / "metadata"
METADATA_DIR.mkdir(exist_ok=True)

df = pd.read_csv(FEATURES_FILE)

print(f"Loaded {len(df)} users")
print("Columns:", list(df.columns))

# Fix column names if needed (from your data)
if 'query_count_x' in df.columns:
    df['query_count'] = df['query_count_x']
if 'query_count_y' in df.columns:
    df.drop('query_count_y', axis=1, inplace=True, errors='ignore')

# Normalize safely
df['norm_query_count'] = np.log1p(df['query_count'])
df['norm_tokens_per_query'] = df['avg_tokens_per_query'] / (df['avg_tokens_per_query'].max() + 1e-6)
df['norm_queries_per_user'] = df['query_count'] / (df['query_count'].max() + 1e-6)
df['norm_session_depth'] = df['queries_per_session'] / (df['queries_per_session'].max() + 1e-6)

# Compute target scores
df['prioritization_intensity'] = (
    0.4 * df.get('pct_demand_prioritization', 0) +
    0.3 * df['norm_queries_per_user'] +
    0.2 * df['norm_tokens_per_query'] +
    0.1 * df.get('pct_project_and_roadmap_creation_and_update', 0)
) * 10

df['strategic_oversight'] = (
    0.3 * df.get('pct_portfolio_and_team_listing', 0) +
    0.3 * df.get('pct_project_and_roadmap_status_tracking', 0) +
    0.2 * df['norm_tokens_per_query'] +
    0.2 * (1 - df['norm_queries_per_user'])  # inverse volume = more oversight
) * 10

df['resource_optimization'] = (
    0.5 * df.get('pct_resource_management_and_allocation', 0) +
    0.3 * df['norm_session_depth'] +
    0.2 * df['norm_tokens_per_query']
) * 10

df['ideation_velocity'] = (
    0.5 * df.get('pct_idea_generation_and_refinement', 0) +
    0.3 * df['norm_query_count'] +
    0.2 * df.get('pct_existing_solution_discovery', 0)
) * 10

# Clip
for col in ['prioritization_intensity', 'strategic_oversight', 'resource_optimization', 'ideation_velocity']:
    df[col] = df[col].clip(0, 10).round(2)

print("\nTarget scores by role:")
print(df.groupby('primary_role')[['prioritization_intensity', 'strategic_oversight', 'resource_optimization', 'ideation_velocity']].mean().round(2))

# Features for training
feature_cols = [
    'avg_tokens_per_query', 'query_count', 'queries_per_session', 'avg_query_length_chars',
    'pct_idea_generation_and_refinement', 'pct_demand_prioritization',
    'pct_existing_solution_discovery', 'pct_project_and_roadmap_status_tracking',
    'pct_resource_management_and_allocation', 'pct_portfolio_and_team_listing',
    'pct_project_and_roadmap_creation_and_update', 'pct_risk_and_constraint_analysis',
    'pct_demand_and_project_lifecycle_analysis', 'pct_reporting_and_insights_generation',
    'pct_template_and_document_management', 'pct_bug_and_enhancement_tracking'
]

targets = ['prioritization_intensity', 'strategic_oversight', 'resource_optimization', 'ideation_velocity']

for target in targets:
    print(f"\nTraining {target}...")
    X = df[feature_cols]
    y = df[target]

    model = xgb.XGBRegressor(n_estimators=300, learning_rate=0.05, max_depth=5, random_state=42)
    model.fit(X, y)

    path = MODELS_DIR / f"{target}.json"
    model.save_model(path)

    meta = {
        "trained_on": len(df),
        "features": feature_cols,
        "score_distribution": y.tolist(),
        "mean": float(y.mean()),
        "version": "v1"
    }
    meta_path = METADATA_DIR / f"{target}.json"
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2, default=float)  # Ensures no 'E' notation
    # (METADATA_DIR / f"{target}.json").write_text(json.dumps(meta, indent=2))

    print(f"Saved {path}")

print("\nALL MODELS TRAINED AND READY")
print("Your XGBoostManager will load them automatically.")