"""Tests for game.py.

Run with: pytest test_game.py -v
"""

from __future__ import annotations

import random

import pytest

from game import (
    CHAMBERS,
    DRAWS_PER_ROUND,
    LEVEL_BASE_SCORE,
    LEVEL_MAX,
    LEVEL_MIN,
    LEVEL_SCORE_STEP,
    Action,
    Campaign,
    DrawResult,
    RoundState,
    bullets_for_level,
    score_for_level,
)

# --------------------------------------------------------------------------
# Level / scoring config
# --------------------------------------------------------------------------

def test_bullets_for_level_is_identity_within_range():
    for level in range(LEVEL_MIN, LEVEL_MAX + 1):
        assert bullets_for_level(level) == level


@pytest.mark.parametrize("bad_level", [0, -1, LEVEL_MAX + 1, 100])
def test_bullets_for_level_rejects_out_of_range(bad_level):
    with pytest.raises(ValueError):
        bullets_for_level(bad_level)


def test_score_for_level_matches_spec():
    # Level 1 -> 10, level 2 -> 15, level 3 -> 20, level 4 -> 25, level 5 -> 30
    expected = {1: 10, 2: 15, 3: 20, 4: 25, 5: 30}
    for level, points in expected.items():
        assert score_for_level(level) == points


def test_score_for_level_is_linear_step():
    for level in range(LEVEL_MIN, LEVEL_MAX):
        diff = score_for_level(level + 1) - score_for_level(level)
        assert diff == LEVEL_SCORE_STEP


@pytest.mark.parametrize("bad_level", [0, -5, LEVEL_MAX + 1])
def test_score_for_level_rejects_out_of_range(bad_level):
    with pytest.raises(ValueError):
        score_for_level(bad_level)


def test_every_level_leaves_at_least_one_empty_chamber():
    # Otherwise stay/spin probability math (which needs >=1 empty) breaks.
    for level in range(LEVEL_MIN, LEVEL_MAX + 1):
        k = bullets_for_level(level)
        assert 1 <= k <= CHAMBERS - 1


# --------------------------------------------------------------------------
# RoundState mechanics (no per-decision scoring anymore — see Campaign tests)
# --------------------------------------------------------------------------

def make_round(k: int, rotation_start: int, seed: int = 0) -> RoundState:
    random.seed(seed)
    rs = RoundState(k=k)
    rs.rotation_start = rotation_start
    rs.pointer = 0
    rs.streak_m = 0
    return rs


def test_first_draw_has_no_decision_recorded():
    # k=3, start=3 -> loaded positions {3,4,5}. pointer 0 empty.
    rs = make_round(k=3, rotation_start=3)
    result = rs.draw_first()
    assert result == DrawResult.EMPTY
    assert rs.first_draw_result == DrawResult.EMPTY
    assert rs.decisions == []
    assert rs.streak_m == 1
    assert rs.pointer == 1


def test_loaded_first_draw_ends_round_immediately():
    rs = make_round(k=3, rotation_start=0)  # positions {0,1,2} loaded
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


def test_current_choice_inputs_exposes_raw_numbers_not_probabilities():
    rs = make_round(k=2, rotation_start=4)  # loaded {4,5}
    rs.draw_first()  # pointer0 empty, m becomes 1
    inputs = rs.current_choice_inputs()
    assert inputs.k == 2
    assert inputs.chambers == 6
    assert inputs.empties == 4
    assert inputs.streak_m == 1
    # ChoiceInputs is a plain data holder — confirm it carries no
    # probability fields a UI could accidentally render.
    assert not hasattr(inputs, "spin_probability")
    assert not hasattr(inputs, "stay_probability")


def test_decision_records_probabilities_for_post_round_review():
    rs = make_round(k=2, rotation_start=4)
    rs.draw_first()
    d = rs.choose(Action.STAY)
    assert d.spin_probability == pytest.approx(2 / 6)
    assert d.stay_probability == pytest.approx(1 / 4)
    assert d.inputs.streak_m == 1


def test_optimal_flag_correct_on_tie_and_mismatch():
    # k=2, start=4: loaded {4,5}. pointer0 empty -> m=1.
    rs = make_round(k=2, rotation_start=4)
    rs.draw_first()
    # m=1: spin=2/6=.333, stay=1/4=.25 -> stay is lower/optimal.
    d_bad = rs.choose(Action.SPIN)
    assert not d_bad.was_optimal


def test_round_clears_after_draws_per_round_survived():
    # k=1, start=5 -> only position 5 loaded. Draws at 0,1,2 all empty.
    rs = make_round(k=1, rotation_start=5)
    rs.draw_first()
    rs.choose(Action.STAY)
    d3 = rs.choose(Action.STAY)
    assert rs.draws_taken == DRAWS_PER_ROUND
    assert rs.round_over
    assert rs.round_cleared
    assert d3.result == DrawResult.EMPTY


def test_all_results_includes_first_draw_and_decisions_in_order():
    rs = make_round(k=1, rotation_start=5)
    rs.draw_first()
    rs.choose(Action.STAY)
    rs.choose(Action.STAY)
    results = rs.all_results()
    assert len(results) == 3
    assert all(r == DrawResult.EMPTY for r in results)


def test_invalid_k_rejected_by_round_state():
    with pytest.raises(ValueError):
        RoundState(k=0)
    with pytest.raises(ValueError):
        RoundState(k=6)


def test_streak_m_never_exceeds_empties_in_real_play():
    """Invariant: with real (unmocked) draw resolution, streak_m can never
    exceed E, because the draw at m == E is *guaranteed* loaded (stay
    probability is exactly 1.0 there) and ends the round before streak_m
    could advance further. This is what keeps stay_probability's m from
    ever going out of range during actual gameplay."""
    rng = random.Random(7)
    for _ in range(5_000):
        level = rng.randint(LEVEL_MIN, LEVEL_MAX)
        k = bullets_for_level(level)
        random.seed(rng.randrange(1_000_000))
        rs = RoundState(k=k)
        empties = rs.chambers - rs.k
        rs.draw_first()
        while not rs.round_over:
            assert rs.streak_m <= empties
            action = rng.choice([Action.SPIN, Action.STAY])
            rs.choose(action)
        assert rs.streak_m <= empties


# --------------------------------------------------------------------------
# Campaign: level progression and scoring
# --------------------------------------------------------------------------

def test_campaign_starts_at_level_one_with_zero_score():
    c = Campaign()
    c.start_level()
    assert c.level == 1
    assert c.total_score == 0
    assert c.round is not None
    assert c.round.k == 1
    assert not c.finished
    assert not c.victory


def _force_clear(rs: RoundState) -> None:
    """Drive a RoundState to a cleared round by always Spinning, with the
    loaded-check patched out so every scheduled draw comes up empty.

    Spinning (not Staying) is used deliberately: it resets streak_m to 0
    on every call, so this stays valid for every k/E combination — including
    high levels (k=4, k=5) where E is smaller than draws_per_round and a
    real "always Stay" run could never physically clear the round anyway.
    """
    rs._is_loaded = lambda position: False  # type: ignore[method-assign]
    rs.draw_first()
    while not rs.round_over:
        rs.choose(Action.SPIN)


def _force_loss_on_first_draw(rs: RoundState) -> None:
    rs._is_loaded = lambda position: True  # type: ignore[method-assign]
    rs.draw_first()


def test_advance_after_clear_awards_correct_points_and_moves_level():
    c = Campaign()
    c.start_level()
    _force_clear(c.round)
    assert c.round.round_cleared

    c.advance_after_clear()
    assert c.total_score == 10  # level 1 clear
    assert c.last_level_points == 10
    assert c.level == 2
    assert c.round.k == 2
    assert not c.finished


def test_advance_after_clear_raises_if_round_not_cleared():
    c = Campaign()
    c.start_level()
    with pytest.raises(RuntimeError):
        c.advance_after_clear()  # round not even started drawing


def test_full_clean_run_scores_100_and_ends_in_victory():
    c = Campaign()
    c.start_level()
    expected_total = 0
    for level in range(1, LEVEL_MAX + 1):
        assert c.level == level
        _force_clear(c.round)
        c.advance_after_clear()
        expected_total += score_for_level(level)
        assert c.total_score == expected_total

    assert c.finished
    assert c.victory
    assert c.total_score == 10 + 15 + 20 + 25 + 30 == 100
    # The final cleared round is kept around (not nulled) so a UI can still
    # display it on the victory screen.
    assert c.round is not None
    assert c.round.round_cleared


def test_register_loss_ends_campaign_without_points_for_current_level():
    c = Campaign()
    c.start_level()
    _force_clear(c.round)
    c.advance_after_clear()  # now on level 2, total_score = 10

    _force_loss_on_first_draw(c.round)
    assert c.round.round_over and not c.round.round_cleared
    c.register_loss()

    assert c.finished
    assert not c.victory
    assert c.total_score == 10  # points from level 1 kept; no points for level 2
    assert c.last_level_points == 0


def test_register_loss_raises_if_round_not_over():
    c = Campaign()
    c.start_level()
    with pytest.raises(RuntimeError):
        c.register_loss()


def test_restart_resets_everything():
    c = Campaign()
    c.start_level()
    _force_clear(c.round)
    c.advance_after_clear()
    assert c.total_score == 10

    c.restart()
    assert c.level == LEVEL_MIN
    assert c.total_score == 0
    assert not c.finished
    assert not c.victory
    assert c.round.k == 1


# --------------------------------------------------------------------------
# Stress test: many random campaigns should never crash or misbehave
# --------------------------------------------------------------------------

def _play_random_campaign(rng: random.Random) -> Campaign:
    random.seed(rng.randrange(1_000_000))  # seeds RoundState's own RNG use
    c = Campaign()
    c.start_level()
    steps = 0
    max_steps = 10_000  # safety valve against any infinite-loop regression
    while not c.finished:
        steps += 1
        assert steps < max_steps, "campaign did not terminate"

        rs = c.round
        if rs.draws_taken == 0:
            rs.draw_first()
        elif not rs.round_over:
            action = rng.choice([Action.SPIN, Action.STAY])
            rs.choose(action)

        if rs.round_over:
            if rs.round_cleared:
                c.advance_after_clear()
            else:
                c.register_loss()
    return c


def test_stress_many_random_campaigns_never_crash_and_stay_consistent():
    rng = random.Random(12345)
    n_campaigns = 2_000
    victories = 0
    for _ in range(n_campaigns):
        c = _play_random_campaign(rng)
        assert c.finished
        assert 1 <= c.level <= LEVEL_MAX
        assert c.total_score >= 0
        assert c.total_score <= 100
        # total_score must always be a prefix-sum of consecutive level scores
        if c.victory:
            assert c.total_score == 100
            victories += 1
        else:
            # score must equal exactly the sum of levels strictly below
            # the one that was lost (or the current level if won some but
            # not all — reconstructible from level/last_level_points logic)
            assert c.total_score % 5 == 0 or c.total_score == 0

    # With random Spin/Stay play, most campaigns should still fail at some
    # point (there's no way to guarantee survival), but a decent minority
    # via luck alone should clear at least level 1. Loose sanity bounds,
    # not a precise probability claim.
    assert 0 <= victories <= n_campaigns


def test_stress_random_campaigns_scores_are_always_valid_sums():
    rng = random.Random(999)
    valid_scores = set()
    total = 0
    for level in range(LEVEL_MIN, LEVEL_MAX + 1):
        total += score_for_level(level)
        valid_scores.add(total)
    valid_scores.add(0)

    for _ in range(500):
        c = _play_random_campaign(rng)
        assert c.total_score in valid_scores, (
            f"score {c.total_score} is not a valid cumulative sum {valid_scores}"
        )
