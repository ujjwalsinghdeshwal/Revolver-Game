"""Tests for game.py.

Run with: pytest test_game.py -v
"""

from __future__ import annotations

import random

import pytest

from game import (
    SCORE_OPTIMAL,
    SCORE_ROUND_CLEAR_BONUS,
    SCORE_SUBOPTIMAL,
    Action,
    DrawResult,
    RoundState,
)


def make_round(k: int, rotation_start: int, seed: int = 0) -> RoundState:
    """Build a RoundState and pin its rotation so results are deterministic."""
    random.seed(seed)
    rs = RoundState(k=k)
    rs.rotation_start = rotation_start
    rs.pointer = 0
    rs.streak_m = 0
    return rs


def test_first_draw_has_no_score():
    # k=3, chambers=6 -> loaded block occupies positions {3,4,5} if start=3.
    # pointer 0 is empty.
    rs = make_round(k=3, rotation_start=3)
    result = rs.draw_first()
    assert result == DrawResult.EMPTY
    assert rs.score == 0
    assert rs.decisions == []
    assert rs.streak_m == 1
    assert rs.pointer == 1


def test_loaded_first_draw_ends_round_immediately():
    # start=0, k=3 -> positions {0,1,2} loaded. pointer 0 is loaded.
    rs = make_round(k=3, rotation_start=0)
    result = rs.draw_first()
    assert result == DrawResult.LOADED
    assert rs.round_over
    assert not rs.round_cleared


def test_choose_before_first_draw_raises():
    rs = make_round(k=2, rotation_start=0)
    with pytest.raises(RuntimeError):
        rs.choose(Action.STAY)


def test_choose_after_round_over_raises():
    rs = make_round(k=3, rotation_start=0)
    rs.draw_first()  # loaded, round over
    with pytest.raises(RuntimeError):
        rs.choose(Action.STAY)


def test_scripted_sequence_predictable_score():
    # k=2, chambers=6 -> E=4, loaded block at start=4 => positions {4,5} loaded.
    # pointer sequence: 0 (empty), 1 (empty), 2 (empty) — 3 draws, round clears.
    rs = make_round(k=2, rotation_start=4)

    first = rs.draw_first()
    assert first == DrawResult.EMPTY  # pointer 0, not loaded
    assert rs.score == 0

    # Decision 2: m=1 now. spin=2/6=0.3333, stay=1/(4-1+1)=1/4=0.25.
    # Stay is lower -> Stay is optimal.
    spin_p, stay_p = rs.current_probabilities()
    assert spin_p == pytest.approx(2 / 6)
    assert stay_p == pytest.approx(1 / 4)
    d2 = rs.choose(Action.STAY)
    assert d2.was_optimal
    assert d2.points == SCORE_OPTIMAL
    assert d2.result == DrawResult.EMPTY  # pointer 1, not loaded

    # Decision 3: m=2 now. spin=2/6=0.3333, stay=1/(4-2+1)=1/3=0.3333 -> tie.
    spin_p, stay_p = rs.current_probabilities()
    assert spin_p == pytest.approx(stay_p)
    d3 = rs.choose(Action.SPIN)  # either choice is optimal on a tie
    assert d3.was_optimal
    assert d3.points == SCORE_OPTIMAL

    # Spinning re-randomizes; we don't know the new rotation, but the round
    # should now be complete (3 draws taken) regardless of the 3rd result,
    # unless the spin happened to land on a loaded chamber.
    assert rs.draws_taken == 3
    if d3.result == DrawResult.EMPTY:
        assert rs.round_over and rs.round_cleared
        expected_score = 2 * SCORE_OPTIMAL + SCORE_ROUND_CLEAR_BONUS
        assert rs.score == expected_score
    else:
        assert rs.round_over and not rs.round_cleared
        expected_score = 2 * SCORE_OPTIMAL
        assert rs.score == expected_score


def test_suboptimal_choice_scores_penalty():
    # k=2, start=4: positions {4,5} loaded. pointer 0 empty (m becomes 1).
    rs = make_round(k=2, rotation_start=4)
    rs.draw_first()
    # m=1: stay=1/4=0.25 is lower than spin=1/3. Choosing SPIN is suboptimal.
    d = rs.choose(Action.SPIN)
    assert not d.was_optimal
    assert d.points == SCORE_SUBOPTIMAL


def test_loaded_draw_stops_round_and_no_clear_bonus():
    # k=3, start=1 -> loaded positions {1,2,3}. pointer0 empty -> m=1, pointer1 loaded.
    rs = make_round(k=3, rotation_start=1)
    first = rs.draw_first()
    assert first == DrawResult.EMPTY
    d = rs.choose(Action.STAY)
    assert d.result == DrawResult.LOADED
    assert rs.round_over
    assert not rs.round_cleared
    # score should not include the clear bonus
    assert rs.score == d.points


def test_invalid_k_rejected_by_round_state():
    with pytest.raises(ValueError):
        RoundState(k=0)
    with pytest.raises(ValueError):
        RoundState(k=6)
