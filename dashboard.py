"""
Wellness analytics dashboard (Streamlit).
Reads from the same SQLite DB as the WhatsApp bot.
"""

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from sentiment_nlp import CRISIS_NOTE

DB_PATH = Path(__file__).resolve().parent / "wellness.db"


@st.cache_data(ttl=30)
def load_table(query: str, params: tuple = ()) -> pd.DataFrame:
    import sqlite3

    if not DB_PATH.exists():
        return pd.DataFrame()
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql_query(query, conn, params=params)


def main() -> None:
    st.set_page_config(
        page_title="Mental Wellness Dashboard",
        page_icon="🌱",
        layout="wide",
    )
    st.title("Mental Wellness Dashboard")
    st.caption("Analytics from your WhatsApp wellness bot (local demo).")

    if not DB_PATH.exists():
        st.warning("No database found yet. Use the bot on WhatsApp to create `wellness.db`.")
        return

    mood = load_table(
        """
        SELECT user_phone, intensity, timestamp, notes, mood
        FROM mood_logs
        ORDER BY timestamp DESC
        """
    )
    checkins = load_table(
        """
        SELECT user_phone, intensity, category, note, created_at
        FROM checkins
        ORDER BY created_at DESC
        """
    )
    users = load_table("SELECT phone_number, joined_date FROM users")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Users", len(users) if not users.empty else 0)
    col2.metric("Mood logs", len(mood) if not mood.empty else 0)
    col3.metric("Guided check-ins", len(checkins) if not checkins.empty else 0)
    if not mood.empty:
        col4.metric("Avg mood (all)", f"{mood['intensity'].mean():.1f}/10")
    else:
        col4.metric("Avg mood (all)", "—")

    vent_logs = load_table(
        """
        SELECT user_phone, sentiment_bucket, word_count, is_crisis, source, created_at
        FROM vent_logs
        ORDER BY created_at DESC
        """
    )

    tab_mood, tab_checkin, tab_vent, tab_ml, tab_safety = st.tabs(
        ["Mood trends", "Check-ins", "Vent NLP", "ML recommender", "Scope & safety"]
    )

    with tab_mood:
        if mood.empty:
            st.info("No mood data yet. Try `/mood 7` or `/checkin` on WhatsApp.")
        else:
            mood["timestamp"] = pd.to_datetime(mood["timestamp"], errors="coerce")
            mood = mood.dropna(subset=["timestamp"])
            mood_display = mood.copy()
            mood_display["notes"] = mood_display["notes"].fillna("").replace("", "—")
            crisis_mood = mood_display[mood_display["mood"] == "crisis"]
            mood_for_chart = mood_display[
                (mood_display["mood"] != "crisis") & mood_display["intensity"].notna()
            ]
            mood_sorted = mood_for_chart.sort_values("timestamp")

            if not crisis_mood.empty:
                st.warning(
                    f"**{len(crisis_mood)}** crisis flag(s) logged (notes show `{CRISIS_NOTE}` only — no message text stored)."
                )

            st.subheader("Mood over time")
            st.caption("Crisis flags are excluded from the average line chart.")
            if mood_sorted.empty:
                st.info("No numeric mood scores yet for the chart.")
            else:
                chart_df = mood_sorted.groupby(mood_sorted["timestamp"].dt.date)[
                    "intensity"
                ].mean().reset_index()
                chart_df.columns = ["date", "avg_intensity"]
                st.line_chart(chart_df, x="date", y="avg_intensity")

            st.subheader("Recent mood logs")
            st.dataframe(
                mood_display.head(20)[["timestamp", "intensity", "mood", "notes"]],
                use_container_width=True,
                hide_index=True,
            )

    with tab_checkin:
        if checkins.empty:
            st.info("No check-ins yet. Try `/checkin` on WhatsApp.")
        else:
            checkins["created_at"] = pd.to_datetime(checkins["created_at"], errors="coerce")
            checkins_display = checkins.copy()
            crisis_checkins = checkins_display[checkins_display["note"] == CRISIS_NOTE]
            checkins_chart = checkins_display[checkins_display["note"] != CRISIS_NOTE]

            if not crisis_checkins.empty:
                st.warning(
                    f"**{len(crisis_checkins)}** check-in(s) ended with crisis detection (`{CRISIS_NOTE}` in note — no message text stored)."
                )

            st.subheader("Check-ins by category")
            st.caption("Crisis-flagged check-ins excluded from category chart.")
            if checkins_chart.empty:
                st.info("No non-crisis check-ins for category chart.")
            else:
                st.bar_chart(checkins_chart["category"].value_counts())

            st.subheader("Recent check-ins")
            st.dataframe(
                checkins_display.head(20)[["created_at", "intensity", "category", "note"]],
                use_container_width=True,
                hide_index=True,
            )

    with tab_vent:
        st.subheader("Vent sessions (VADER NLP)")
        st.caption(
            "Free-text mood uses **VADER** sentiment on `/vent` only. "
            "We store bucket + word count — not full message text."
        )
        if vent_logs.empty:
            st.info("No vent logs yet. Try `/vent` on WhatsApp and share a message.")
        else:
            vent_logs["created_at"] = pd.to_datetime(vent_logs["created_at"], errors="coerce")
            crisis_count = int(vent_logs["is_crisis"].sum()) if "is_crisis" in vent_logs else 0
            c1, c2, c3 = st.columns(3)
            c1.metric("Vent events", len(vent_logs))
            c2.metric("Crisis flags", crisis_count)
            non_crisis = vent_logs[vent_logs["is_crisis"] == 0] if "is_crisis" in vent_logs else vent_logs
            if not non_crisis.empty:
                c3.metric("Most common tone", non_crisis["sentiment_bucket"].mode().iloc[0])
            else:
                c3.metric("Most common tone", "—")

            if not non_crisis.empty:
                st.bar_chart(non_crisis["sentiment_bucket"].value_counts())
            crisis_only = vent_logs[vent_logs["is_crisis"] == 1] if "is_crisis" in vent_logs else pd.DataFrame()
            if not crisis_only.empty and "source" in crisis_only.columns:
                st.subheader("Crisis flags by source")
                st.caption("Crisis events are stored here (not in mood/check-in tables).")
                st.bar_chart(crisis_only["source"].value_counts())

            st.dataframe(
                vent_logs.head(30)[
                    ["created_at", "sentiment_bucket", "word_count", "is_crisis", "source"]
                ],
                use_container_width=True,
                hide_index=True,
            )

    with tab_ml:
        from recommender import META_PATH, MIN_SAMPLES_TO_TRAIN, train_and_save

        st.subheader("Intervention recommender")
        st.write(
            f"Uses **rules** by default; trains a small logistic regression when you have "
            f"**{MIN_SAMPLES_TO_TRAIN}+** check-ins."
        )
        if st.button("Train / refresh model"):
            with st.spinner("Training..."):
                summary = train_and_save()
            st.json(summary)
        elif META_PATH.exists():
            st.json(json.loads(META_PATH.read_text(encoding="utf-8")))
        else:
            st.info("No model yet. Complete more `/checkin` flows, then train here.")

    with tab_safety:
        st.markdown(
            """
            ### What this bot is
            - A **wellness support** tool for mood tracking, breathing exercises, meditation prompts, and reflections.
            - **Not** a substitute for professional mental health care, diagnosis, or emergency services.

            ### Privacy (demo)
            - Data is stored locally in `wellness.db` on the machine running the bot.
            - Phone numbers are stored to associate logs with users; do not deploy with real user data without consent and security review.

            ### NLP scope
            - **/vent**: lexicon sentiment + crisis phrase detection (`sentiment_nlp.py`)
            - **/checkin** & **/mood**: structured numbers only; ML recommender uses intensity + category + hour
            - **Crisis logging**: `vent_logs` + placeholder rows in mood/check-in tabs (`[crisis]` only — no message text)

            ### Planned upgrades
            - **React** web dashboard (full-stack) reading from a proper API
            - WhatsApp interactive buttons and optional GenAI (constrained, safety-first)
            """
        )


if __name__ == "__main__":
    main()
