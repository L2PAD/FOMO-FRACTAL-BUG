"""
ML Overlay V1: Training Pipeline
LogisticRegression with StandardScaler + class_weight='balanced'.
Target: predict forecast errors, NOT market direction.
"""
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from ml_overlay.dataset_builder import NUMERIC_FEATURES, CATEGORICAL_FEATURES

MODEL_DIR = Path("/app/backend/artifacts/ml_overlay_v1")
MODEL_DIR.mkdir(parents=True, exist_ok=True)


def build_pipeline():
    numeric_pipe = Pipeline(steps=[
        ("imputer", SimpleImputer(strategy="constant", fill_value=0.0)),
        ("scaler", StandardScaler()),
    ])
    categorical_pipe = Pipeline(steps=[
        ("imputer", SimpleImputer(strategy="constant", fill_value="unknown")),
        ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
    ])
    preprocessor = ColumnTransformer(transformers=[
        ("num", numeric_pipe, NUMERIC_FEATURES),
        ("cat", categorical_pipe, CATEGORICAL_FEATURES),
    ])
    model = LogisticRegression(
        max_iter=2000,
        class_weight="balanced",
        random_state=42,
    )
    return Pipeline(steps=[
        ("preprocessor", preprocessor),
        ("model", model),
    ])


def train_model(df: pd.DataFrame):
    """Train the ML overlay model. Returns (pipe, metrics)."""
    all_features = NUMERIC_FEATURES + CATEGORICAL_FEATURES

    for col in all_features + ["target_error"]:
        if col not in df.columns:
            df[col] = None

    X = df[all_features].copy()
    y = df["target_error"].astype(int)

    if len(y.unique()) < 2:
        raise ValueError(f"Need both classes. Got only: {y.unique().tolist()}")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=42, stratify=y,
    )

    pipe = build_pipeline()
    pipe.fit(X_train, y_train)

    proba = pipe.predict_proba(X_test)[:, 1]
    pred = (proba >= 0.5).astype(int)

    auc = roc_auc_score(y_test, proba) if len(y_test.unique()) > 1 else 0.0
    report = classification_report(y_test, pred, output_dict=True, zero_division=0)

    # Feature importances (logistic regression coefficients)
    model = pipe.named_steps["model"]
    preprocessor = pipe.named_steps["preprocessor"]
    feature_names = preprocessor.get_feature_names_out()
    coefs = model.coef_[0]
    importances = sorted(
        zip(feature_names.tolist(), coefs.tolist()),
        key=lambda x: abs(x[1]), reverse=True
    )[:20]

    metrics = {
        "roc_auc": float(auc),
        "classification_report": report,
        "train_size": int(len(X_train)),
        "test_size": int(len(X_test)),
        "positive_rate": float(y.mean()),
        "total_samples": int(len(df)),
        "top_features": importances,
    }

    # Save
    joblib.dump(pipe, MODEL_DIR / "model.joblib")
    (MODEL_DIR / "metrics.json").write_text(json.dumps(metrics, indent=2, default=str))

    return pipe, metrics
