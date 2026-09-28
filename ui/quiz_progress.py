"""'Quiz progress' section shown at the bottom of the Stats page (Step 2 / I-02).

Uses the same CSS classes (``stat-card``, ``chart-section-title``) and plotly
styling as the rest of the Stats page so it looks native.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from utils.quiz_attempts import get_attempts, get_quiz_summary, get_score_trend_dataframe


def render_quiz_progress(email: str) -> None:
    import plotly.express as px

    st.markdown("<div style='height:1.8rem;'></div>", unsafe_allow_html=True)
    st.markdown('<div class="chart-section-title">Quiz progress</div>', unsafe_allow_html=True)

    summary = get_quiz_summary(email)
    if summary["attempts"] == 0:
        st.info(
            "No quiz attempts yet — type `quiz` in Chat, answer the questions "
            "and press **Submit Quiz**. Your scores will show up here."
        )
        return

    # ---- Stat cards ----
    cards = [
        ("📝", str(summary["attempts"]), "Quizzes taken"),
        ("📊", f"{summary['average_percent']:g}%", "Average score"),
        ("🏆", f"{summary['best_percent']:g}%", "Best score"),
        ("🎯", f"{summary['latest_percent']:g}%", "Latest score"),
    ]
    for col, (icon, value, label) in zip(st.columns(4), cards):
        with col:
            st.markdown(
                '<div class="stat-card">'
                f'<div class="stat-card-icon">{icon}</div>'
                f'<div class="stat-card-value">{value}</div>'
                f'<div class="stat-card-label">{label}</div>'
                "</div>",
                unsafe_allow_html=True,
            )

    st.markdown("<div style='height:1.2rem;'></div>", unsafe_allow_html=True)

    # ---- Score trend ----
    trend_df = get_score_trend_dataframe(email)
    if len(trend_df) >= 2:
        fig = px.line(
            trend_df,
            x="attempt",
            y="percent",
            markers=True,
            hover_data={"video": True, "when": True, "score": True, "out_of": True, "attempt": False},
            color_discrete_sequence=["#2563eb"],
        )
        fig.update_layout(
            margin=dict(t=10, b=10, l=10, r=10),
            height=260,
            xaxis_title="Quiz attempt",
            yaxis_title="Score (%)",
            yaxis=dict(range=[0, 100]),
            xaxis=dict(dtick=1),
            font=dict(family="Inter, sans-serif", color="#374151"),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.caption("Take at least two quizzes to see your score trend.")

    # ---- Recent attempts ----
    recent = get_attempts(email, limit=10)
    table = pd.DataFrame(
        [
            {
                "When": a["timestamp"],
                "Video": a["video_title"] or "Untitled video",
                "Score": f"{a['score']} / {a['num_questions']}",
                "%": a["percent"],
            }
            for a in recent
        ]
    )
    st.markdown("**Recent attempts**")
    st.dataframe(table, hide_index=True)
