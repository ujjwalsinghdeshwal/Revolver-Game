"""Streamlit UI for Cylinder Gambit.

All game logic lives in game.py / probability.py — this file only wires
state to widgets and draws the cylinder. Nothing in here should need to
change if the probability math, level ladder, or scoring rules change.
"""

from __future__ import annotations

import math

import streamlit as st

from game import (
    CHAMBERS,
    DRAWS_PER_ROUND,
    LEVEL_MAX,
    Action,
    Campaign,
    DrawResult,
)

st.set_page_config(page_title="Cylinder Gambit", page_icon="🎯", layout="centered")

# --------------------------------------------------------------------------
# Theme — dark card matching the reference screenshot
# --------------------------------------------------------------------------
st.markdown(
    """
    <style>
    .stApp {
        background-color: #14141f;
    }
    .block-container {
        max-width: 700px;
        padding-top: 2rem;
    }
    .cg-card {
        background-color: #1a1a29;
        border: 1px solid #2c2c3d;
        border-radius: 14px;
        padding: 28px 32px;
        margin-bottom: 18px;
    }
    .cg-header-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        font-family: 'Courier New', monospace;
        letter-spacing: 1px;
        margin-bottom: 18px;
    }
    .cg-level-label {
        color: #9a9aab;
        font-size: 0.95rem;
        text-transform: uppercase;
    }
    .cg-score-label {
        color: #9a9aab;
        font-size: 0.95rem;
    }
    .cg-score-value {
        color: #f2f2f5;
        font-weight: 700;
        font-size: 1.1rem;
    }
    .cg-shot-pill {
        display: inline-block;
        border: 1px solid #3a3a4d;
        border-radius: 8px;
        padding: 6px 14px;
        margin: 0 5px;
        font-family: 'Courier New', monospace;
        font-size: 0.85rem;
        color: #b8b8c8;
    }
    .cg-shot-pill.empty { border-color: #4a7a63; color: #7fbf9e; }
    .cg-shot-pill.loaded { border-color: #8c3b3b; color: #d98a8a; }
    .cg-message {
        text-align: center;
        color: #b8b8c8;
        font-size: 1.02rem;
        margin: 18px 0;
        line-height: 1.5;
    }
    .cg-inputs-box {
        background-color: #20202f;
        border: 1px solid #33334a;
        border-radius: 10px;
        padding: 14px 16px;
        margin-bottom: 10px;
        font-family: 'Courier New', monospace;
        font-size: 0.88rem;
        color: #cfcfe0;
    }
    .cg-inputs-title {
        font-weight: 700;
        color: #e8d9a8;
        margin-bottom: 6px;
        font-size: 0.95rem;
    }
    div.stButton > button {
        background-color: #a9812f;
        color: #14141f;
        font-weight: 700;
        border: none;
        border-radius: 8px;
        padding: 10px 0;
        width: 100%;
    }
    div.stButton > button:hover {
        background-color: #c2984a;
        color: #14141f;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

RESULT_LABEL = {DrawResult.EMPTY: "Empty", DrawResult.LOADED: "Loaded"}

# --------------------------------------------------------------------------
# Session state
# --------------------------------------------------------------------------

if "campaign" not in st.session_state:
    st.session_state.campaign = None  # Campaign | None


def start_new_campaign() -> None:
    c = Campaign()
    c.start_level()
    c.round.draw_first()
    st.session_state.campaign = c


# --------------------------------------------------------------------------
# Cylinder visual
# --------------------------------------------------------------------------

def render_cylinder_svg(rs) -> str:
    """A ring of `chambers` circles. Cream fill; the chamber about to be
    fired gets a gold ring; already-fired chambers are tinted by outcome."""
    size = 240
    center = size / 2
    radius = 82
    chambers = rs.chambers
    results = rs.all_results()
    n_results = len(results)

    RESULT_FILL = {
        DrawResult.EMPTY: "#4a7a63",
        DrawResult.LOADED: "#8c3b3b",
    }
    CREAM = "#e8e4d8"
    GOLD = "#d4a72c"

    parts = [f'<svg viewBox="0 0 {size} {size}" xmlns="http://www.w3.org/2000/svg">']
    for i in range(chambers):
        angle = -math.pi / 2 + (2 * math.pi * i / chambers)
        cx = center + radius * math.cos(angle)
        cy = center + radius * math.sin(angle)

        if i < n_results:
            fill = RESULT_FILL[results[i]]
            stroke = "#12120f"
            stroke_w = 2
        elif not rs.round_over and i == n_results:
            fill = CREAM
            stroke = GOLD
            stroke_w = 4
        else:
            fill = CREAM
            stroke = "#3a3a2f"
            stroke_w = 2

        parts.append(
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="20" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="{stroke_w}" />'
        )

    parts.append(f'<circle cx="{center}" cy="{center}" r="7" fill="#3a3a4d" />')
    parts.append("</svg>")
    return "".join(parts)


# --------------------------------------------------------------------------
# Small pieces
# --------------------------------------------------------------------------

def render_shot_pills(rs) -> str:
    results = rs.all_results()
    pills = []
    for i in range(rs.draws_per_round):
        if i < len(results):
            cls = "empty" if results[i] == DrawResult.EMPTY else "loaded"
            label = RESULT_LABEL[results[i]]
        else:
            cls = ""
            label = "pending"
        pills.append(f'<span class="cg-shot-pill {cls}">Shot {i + 1}: {label}</span>')
    return "".join(pills)


def opening_message(k: int) -> str:
    return (
        "A fresh cylinder, freshly spun. No history yet — spin or stay are "
        "identical right now."
    )


def decision_message(rs) -> str:
    n = len(rs.decisions) + 2  # which shot number we're about to take
    return f"Shot {n} of {rs.draws_per_round}. Choose your move."


# --------------------------------------------------------------------------
# Screens
# --------------------------------------------------------------------------

def start_screen() -> None:
    st.markdown('<div class="cg-card">', unsafe_allow_html=True)
    st.markdown(
        "<h2 style='color:#e8e4d8; text-align:center; font-family:monospace;'>"
        "🎯 CYLINDER GAMBIT</h2>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<p class='cg-message'>A {CHAMBERS}-chamber cylinder hides a "
        f"consecutive block of bullets at a random, unknown position. Climb "
        f"from Level 1 (1 bullet) to Level {LEVEL_MAX} ({LEVEL_MAX} bullets), "
        f"firing {DRAWS_PER_ROUND} shots per level. Clear a level to score "
        f"points and move up — get Loaded and the run ends.</p>",
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)
    if st.button("Start Game", type="primary"):
        start_new_campaign()
        st.rerun()


def round_screen(c: Campaign) -> None:
    rs = c.round
    k = rs.k

    st.markdown('<div class="cg-card">', unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="cg-header-row">
            <span class="cg-level-label">LEVEL {c.level} — {k} BULLET{'S' if k != 1 else ''} LOADED (of {CHAMBERS})</span>
            <span class="cg-score-label">Score <span class="cg-score-value">{c.total_score}</span></span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f'<div style="text-align:center;">{render_cylinder_svg(rs)}</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div style="text-align:center; margin-top:10px;">{render_shot_pills(rs)}</div>',
        unsafe_allow_html=True,
    )

    if rs.round_over:
        render_round_outcome(c)
        st.markdown("</div>", unsafe_allow_html=True)
        return

    if rs.draws_taken == 1 and not rs.decisions:
        # First decision point, right after the automatic opening draw.
        st.markdown(f'<p class="cg-message">{opening_message(k)}</p>', unsafe_allow_html=True)
    else:
        st.markdown(f'<p class="cg-message">{decision_message(rs)}</p>', unsafe_allow_html=True)

    render_choice_inputs(rs)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Spin", key="spin_btn", use_container_width=True):
            c.round.choose(Action.SPIN)
            st.rerun()
    with col2:
        if st.button("Stay", key="stay_btn", use_container_width=True):
            c.round.choose(Action.STAY)
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)


def render_choice_inputs(rs) -> None:
    """Show the raw numbers behind each option — never the computed odds."""
    inputs = rs.current_choice_inputs()
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(
            f"""
            <div class="cg-inputs-box">
                <div class="cg-inputs-title">Spin</div>
                Bullets loaded (k): {inputs.k}<br/>
                Total chambers: {inputs.chambers}
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            f"""
            <div class="cg-inputs-box">
                <div class="cg-inputs-title">Stay</div>
                Empty chambers total (E): {inputs.empties}<br/>
                Empties survived so far (m): {inputs.streak_m}
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_round_outcome(c: Campaign) -> None:
    from game import score_for_level

    rs = c.round

    if rs.round_cleared:
        if c.finished:
            # Final level was already cleared and advance_after_clear() has
            # run — this is the victory screen.
            st.markdown(
                f'<p class="cg-message">🏆 You cleared Level {LEVEL_MAX} — '
                f"campaign complete! Final score: {c.total_score}.</p>",
                unsafe_allow_html=True,
            )
            if st.button("Play Again", type="primary"):
                c.restart()
                c.round.draw_first()
                st.rerun()
        else:
            upcoming_points = score_for_level(c.level)
            st.markdown(
                f'<p class="cg-message">✅ Level cleared! +{upcoming_points} points.</p>',
                unsafe_allow_html=True,
            )
            is_last_level = c.level >= LEVEL_MAX
            label = "Finish Campaign" if is_last_level else f"Continue to Level {c.level + 1}"
            if st.button(label, type="primary"):
                c.advance_after_clear()
                if not c.finished:
                    c.round.draw_first()
                st.rerun()
    else:
        if not c.finished:
            c.register_loss()
        st.markdown(
            f'<p class="cg-message">💀 Loaded. Run over at Level {c.level}. '
            f"Final score: {c.total_score}.</p>",
            unsafe_allow_html=True,
        )
        if st.button("Restart from Level 1", type="primary"):
            c.restart()
            c.round.draw_first()
            st.rerun()

    render_decision_review(rs)


def render_decision_review(rs) -> None:
    if not rs.decisions:
        return
    st.subheader("Review")
    rows = []
    for i, d in enumerate(rs.decisions, start=2):
        rows.append(
            {
                "Shot": i,
                "Choice": d.action.value.capitalize(),
                "k": d.inputs.k,
                "Chambers": d.inputs.chambers,
                "Empties (E)": d.inputs.empties,
                "Streak (m)": d.inputs.streak_m,
                "Spin %": f"{d.spin_probability:.1%}",
                "Stay %": f"{d.stay_probability:.1%}",
                "Optimal?": "Yes" if d.was_optimal else "No",
                "Result": RESULT_LABEL[d.result],
            }
        )
    st.table(rows)


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------

campaign: Campaign | None = st.session_state.campaign

if campaign is None:
    start_screen()
else:
    round_screen(campaign)
