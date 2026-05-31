"""
Offline evaluation for the intervention recommender.
Run: py scripts/evaluate_recommender.py
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from recommender import train_and_save  # noqa: E402

REPORT_PATH = ROOT / "reports" / "recommender_evaluation.md"


def main() -> None:
    summary = train_and_save()
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# Recommender evaluation",
        "",
        "## Setup",
        "- **Baseline**: category-aware rules on mood intensity",
        "- **Model**: logistic regression on `(intensity, category, hour)` from `checkins` table",
        f"- **Minimum samples to train**: {summary.get('n_samples', 0)} in DB",
        "",
        "## Results",
        f"- Check-ins in database: **{summary.get('n_samples', 0)}**",
        f"- Model trained: **{summary.get('trained', False)}**",
    ]

    if summary.get("trained"):
        eval_type = summary.get("eval_type", "unknown")
        lines.append(f"- Evaluation type: **{eval_type}**")
        lines.append(f"- Accuracy: **{summary.get('accuracy', 0):.2%}**")
        lines.append("")
        lines.append("### Classification report")
        lines.append("```")
        lines.append(summary.get("classification_report", "").strip())
        lines.append("```")
    else:
        lines.append(f"- Note: {summary.get('message', '')}")

    lines.extend(
        [
            "",
            "## How to use in the bot",
            "- After `/checkin`, recommendations use the ML model when enough data exists.",
            "- Otherwise the transparent rule baseline is used (labeled implicitly as rules).",
            "",
            "## Interview talking points",
            "- Chose a **simple, explainable** model suitable for small personal datasets.",
            "- Baseline rules ensure the product works from day one.",
            "- Offline evaluation script supports reproducible metrics as data grows.",
        ]
    )

    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {REPORT_PATH}")
    print(summary.get("message", "Done."))


if __name__ == "__main__":
    main()
