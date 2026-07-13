"""
Explainable intervention recommender for wellness check-ins.

- Baseline: transparent rules on mood intensity + life category
- ML: logistic regression on check-in history (when enough data)

Free-text NLP is only used in /vent (sentiment_nlp.py), not here.
"""

from __future__ import annotations

import json
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Dict, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from db_paths import DATABASE_PATH, connect, db_available

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = DATABASE_PATH
MODEL_PATH = BASE_DIR / "models" / "recommender.joblib"
META_PATH = BASE_DIR / "models" / "recommender_meta.json"
MIN_SAMPLES_TO_TRAIN = 12

INTERVENTIONS = (
    "breathe_calm",
    "breathe_relaxation",
    "vent",
    "meditate_quick",
    "meditate_medium",
    "affirmation",
)

MESSAGES: Dict[str, Tuple[str, str]] = {
    "breathe_calm": (
        "A steady breathing exercise may help you feel more grounded.",
        "/breathe calm",
    ),
    "breathe_relaxation": (
        "A relaxation breathing pattern can ease tension in your body.",
        "/breathe relaxation",
    ),
    "vent": (
        "Talking it out can help process what you are feeling.",
        "/vent",
    ),
    "meditate_quick": (
        "A short meditation could help you reset and refocus.",
        "/meditate quick",
    ),
    "meditate_medium": (
        "A slightly longer meditation may help you unwind.",
        "/meditate medium",
    ),
    "affirmation": (
        "A positive affirmation can reinforce what is going well.",
        "/affirmation",
    ),
}

CATEGORY_INDEX = {
    "work": 0,
    "health": 1,
    "relationships": 2,
    "studies": 3,
    "other": 4,
}


def rule_based_intervention(intensity: int, category: str = "other") -> str:
    """Category-aware rules — labels used to train the ML model."""
    cat = (category or "other").lower()

    if intensity <= 3:
        if cat == "relationships":
            return "vent"
        if cat == "health":
            return "breathe_calm"
        return "breathe_relaxation"

    if intensity <= 5:
        if cat in ("work", "studies"):
            return "breathe_relaxation"
        if cat == "relationships":
            return "vent"
        return "vent"

    if intensity <= 7:
        if cat in ("work", "studies"):
            return "meditate_quick"
        return "meditate_medium"

    return "affirmation"


def _load_checkins_df() -> pd.DataFrame:
    if not db_available():
        return pd.DataFrame()
    with connect() as conn:
        return pd.read_sql_query(
            "SELECT intensity, category, created_at FROM checkins ORDER BY created_at",
            conn,
        )


def _build_training_frame(df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
    df = df.copy()
    df["category"] = df["category"].fillna("other").str.lower()
    df["cat_idx"] = df["category"].map(CATEGORY_INDEX).fillna(4).astype(int)
    df["label"] = df.apply(
        lambda row: rule_based_intervention(int(row["intensity"]), row["category"]),
        axis=1,
    )
    df["hour"] = (
        pd.to_datetime(df["created_at"], errors="coerce").dt.hour.fillna(12).astype(int)
    )

    x = np.column_stack([df["intensity"].values, df["cat_idx"].values, df["hour"].values])
    y = df["label"].values
    return x, y


def train_and_save() -> Dict:
    """Train model on check-ins; returns summary dict for reports."""
    df = _load_checkins_df()
    summary = {"n_samples": len(df), "trained": False, "accuracy": None}

    if len(df) < MIN_SAMPLES_TO_TRAIN:
        summary["message"] = f"Need at least {MIN_SAMPLES_TO_TRAIN} check-ins to train (have {len(df)})."
        return summary

    x, y = _build_training_frame(df)
    n = len(y)
    n_classes = len(set(y))
    min_class_count = min(Counter(y).values())
    test_count = max(2, int(round(n * 0.25)))

    pipeline = Pipeline(
        [
            ("scaler", StandardScaler()),
            ("clf", LogisticRegression(max_iter=500)),
        ]
    )

    use_holdout = n >= 20 and test_count >= n_classes and min_class_count >= 2
    stratify = y if use_holdout and test_count >= n_classes else None

    if use_holdout:
        x_train, x_test, y_train, y_test = train_test_split(
            x, y, test_size=0.25, random_state=42, stratify=stratify
        )
        pipeline.fit(x_train, y_train)
        preds = pipeline.predict(x_test)
        acc = float(accuracy_score(y_test, preds))
        report = classification_report(y_test, preds, zero_division=0)
        eval_type = "holdout"
        message = "Model saved (holdout evaluation)."
    else:
        pipeline.fit(x, y)
        preds = pipeline.predict(x)
        acc = float(accuracy_score(y, preds))
        report = classification_report(y, preds, zero_division=0)
        eval_type = "in_sample"
        message = (
            "Model saved (in-sample metrics). "
            "Add more check-ins for reliable holdout evaluation."
        )

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, MODEL_PATH)
    meta = {
        "n_samples": len(df),
        "accuracy": acc,
        "eval_type": eval_type,
        "features": ["intensity", "category_index", "hour_of_day"],
        "classes": list(INTERVENTIONS),
    }
    META_PATH.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    summary.update(
        {
            "trained": True,
            "accuracy": acc,
            "eval_type": eval_type,
            "classification_report": report,
            "message": message,
        }
    )
    return summary


def _load_model() -> Optional[Pipeline]:
    if not MODEL_PATH.exists():
        return None
    return joblib.load(MODEL_PATH)


def recommend_intervention(
    intensity: int,
    category: str = "other",
    hour_of_day: Optional[int] = None,
) -> Tuple[str, str, str]:
    """
    Returns (message, command, source) where source is 'ml' or 'rules'.
    """
    cat = (category or "other").lower()
    cat_idx = CATEGORY_INDEX.get(cat, 4)
    hour = hour_of_day if hour_of_day is not None else 12

    model = _load_model()
    meta = {}
    if META_PATH.exists():
        meta = json.loads(META_PATH.read_text(encoding="utf-8"))

    if model is not None and meta.get("n_samples", 0) >= MIN_SAMPLES_TO_TRAIN:
        features = meta.get("features", ["intensity", "category_index"])
        if len(features) >= 3:
            pred = model.predict(np.array([[intensity, cat_idx, hour]]))[0]
        else:
            pred = model.predict(np.array([[intensity, cat_idx]]))[0]
        key = str(pred)
        source = "ml"
    else:
        key = rule_based_intervention(intensity, cat)
        source = "rules"

    if key not in MESSAGES:
        key = rule_based_intervention(intensity, cat)
        source = "rules"

    msg, cmd = MESSAGES[key]
    return msg, cmd, source
