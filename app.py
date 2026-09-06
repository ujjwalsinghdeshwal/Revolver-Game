"""Streamlit UI for Cylinder Gambit.

All game logic lives in game.py / probability.py — this file only wires
state to widgets and draws the cylinder. Nothing in here should need to
change if the probability math or scoring rules change.
"""

from __future__ import annotations

import math

import streamlit as st

from game import (
    CHAMBERS,
    DRAWS_PER_ROUND,
    K_MAX,
    K_MIN,
    SCORE_ROUND_CLEAR_BONUS,
    Action,
    DrawResult,
    RoundState,
)

st.set_page_config(page_title="Cylinder Gambit", page_icon="🎯", layout="centered")

RESULT_LABEL = {DrawResult.EMPTY: "Empty", DrawResult.LOADED: "Loaded"}
RESULT_COLOR = {DrawResult.EMPTY: "#2e7d32", DrawResult.LOADED: "#c62828"}

# --------------------------------------------------------------------------
# Session state
# --------------------------------------------------------------------------

if "round" not in st.session_state:
    st.session_state.round = None  # RoundState | None
if "first_draw_result" not in st.session_state:
    st.session_state.first_draw_result = None


def start_round(k: int) -> None:
    rs = RoundState(k=k)
    st.session_state.round = rs
    st.session_state.first_draw_result = rs.draw_first()
    st.session_state.last_verdict = None


def reset_to_setup() -> None:
    st.session_state.round = None
    st.session_state.first_draw_result = None
    st.session_state.last_verdict = None


# --------------------------------------------------------------------------
# Cylinder visual
# --------------------------------------------------------------------------

def render_cylinder_svg(rs: RoundState) -> str:
    """A ring of `chambers` circles; used chambers are colored by outcome."""
    size = 220
    center = size / 2
    radius = 80
    chambers = rs.chambers
    n_results = len(rs.decisions) + (1 if st.session_state.first_draw_result else 0)

    results: list[DrawResult] = []
    if st.session_state.first_draw_result:
        results.append(st.session_state.first_draw_result)
    results.extend(d.result for d in rs.decisions)

    parts = [f'<svg viewBox="0 0 {size} {size}" xmlns="http://www.w3.org/2000/svg">']
    for i in range(chambers):
        angle = -math.pi / 2 + (2 * math.pi * i / chambers)
        cx = center + radius * math.cos(angle)
        cy = center + radius * math.sin(angle)

        if i < n_results:
            fill = RESULT_COLOR[results[i]]
        elif not rs.round_over and i == n_results:
            fill = "#f9a825"  # next chamber up
        else:
            fill = "#9e9e9e"  # unused

        parts.append(
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="18" fill="{fill}" '
            f'stroke="#333" stroke-width="2" />'
        )
        parts.append(
            f'<text x="{cx:.1f}" y="{cy + 5:.1f}" text-anchor="middle" '
            f'font-size="13" fill="white" font-family="sans-serif">{i + 1}</text>'
        )

    parts.append(
        f'<circle cx="{center}" cy="{center}" r="6" fill="#333" />'
    )
    parts.append("</svg>")
    return "".join(parts)


# --------------------------------------------------------------------------
# Screens
# --------------------------------------------------------------------------

def setup_screen() -> None:
    st.title("🎯 Cylinder Gambit")
    st.write(
        f"A {CHAMBERS}-chamber cylinder hides a consecutive block of bullets "
        f"at a random, unknown position. Fire {DRAWS_PER_ROUND} times per round. "
        "Before each shot after the first, choose to **Spin** (re-randomize, "
        "forget what you've learned) or **Stay** (advance one chamber, keep "
        "your history) — whichever has the lower odds of Loaded."
    )
    k = st.slider(
        "Bullets loaded (out of 6 chambers)",
        min_value=K_MIN,
        max_value=K_MAX,
        value=2,
    )
    st.caption(f"That's {k} loaded / {CHAMBERS - k} empty chambers.")
    if st.button("Start Round", type="primary"):
        start_round(k)
        st.rerun()


def shot_log(rs: RoundState) -> None:
    st.subheader("Shot log")
    entries = []
    if st.session_state.first_draw_result:
        entries.append(("1", "—", RESULT_LABEL[st.session_state.first_draw_result]))
    for i, d in enumerate(rs.decisions, start=2):
        entries.append((str(i), d.action.value.capitalize(), RESULT_LABEL[d.result]))
    remaining = rs.draws_per_round - len(entries)
    for j in range(remaining):
        entries.append((str(len(entries) + 1), "—", "pending"))

    cols = st.columns(len(entries))
    for col, (num, action, result) in zip(cols, entries):
        with col:
            st.markdown(f"**Draw {num}**")
            st.write(action)
            st.write(result)


def round_screen() -> None:
    rs: RoundState = st.session_state.round

    st.title("🎯 Cylinder Gambit")
    st.markdown(render_cylinder_svg(rs), unsafe_allow_html=True)

    shot_log(rs)
    st.markdown(f"**Score:** {rs.score}")

    verdict = st.session_state.get("last_verdict")
    if verdict:
        st.info(verdict)

    if rs.round_over:
        show_round_summary(rs)
        return

    spin_p, stay_p = rs.current_probabilities()
    st.subheader("Your move")
    col1, col2 = st.columns(2)
    with col1:
        if st.button(f"Spin — {spin_p:.1%}", use_container_width=True):
            handle_choice(rs, Action.SPIN)
    with col2:
        if st.button(f"Stay — {stay_p:.1%}", use_container_width=True):
            handle_choice(rs, Action.STAY)


def handle_choice(rs: RoundState, action: Action) -> None:
    decision = rs.choose(action)
    verdict = "✅ That was the statistically correct call." if decision.was_optimal else "❌ That was the riskier call."
    st.session_state["last_verdict"] = verdict
    st.rerun()


def show_round_summary(rs: RoundState) -> None:
    if rs.round_cleared:
        st.success(f"Round cleared! +{SCORE_ROUND_CLEAR_BONUS} bonus.")
    else:
        st.error("Loaded. Round over.")

    st.subheader("Decisions")
    if rs.decisions:
        rows = []
        for i, d in enumerate(rs.decisions, start=2):
            rows.append(
                {
                    "Draw": i,
                    "Choice": d.action.value.capitalize(),
                    "Spin %": f"{d.spin_probability:.1%}",
                    "Stay %": f"{d.stay_probability:.1%}",
                    "Optimal?": "Yes" if d.was_optimal else "No",
                    "Result": RESULT_LABEL[d.result],
                    "Points": d.points,
                }
            )
        st.table(rows)
    else:
        st.caption("No decisions were made — the round ended on the opening draw.")

    st.markdown(f"### Final score: {rs.score}")

    if st.button("Configure a new round", type="primary"):
        reset_to_setup()
        st.rerun()


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------

if st.session_state.round is None:
    setup_screen()
else:
    round_screen()
