"""Tests for probability.py.

Run with: pytest test_probability.py -v
"""

from __future__ import annotations

import random

import pytest

from probability import (
    brute_force_stay_probability,
    enumerate_rotations,
    spin_probability,
    stay_probability,
)

CHAMBERS = 6


# --------------------------------------------------------------------------
# 1. Unit tests against hand-computed values
# --------------------------------------------------------------------------

@pytest.mark.parametrize("k", [1, 2, 3, 4, 5])
def test_spin_probability_hand_computed(k):
    assert spin_probability(k, CHAMBERS) == pytest.approx(k / 6)


# Hand-computed (E - m + 1) denominators for each k, m.
@pytest.mark.parametrize(
    "k,m,expected",
    [
        # k=1 -> E=5. m=0 is k/chambers (=1/6, which for k=1 coincides
        # with 1/(E+1) — that coincidence does NOT hold for k>=2, see below).
        (1, 0, 1 / 6),
        (1, 1, 1 / 5),
        (1, 2, 1 / 4),
        (1, 3, 1 / 3),
        (1, 4, 1 / 2),
        (1, 5, 1 / 1),
        # k=2 -> E=4. m=0 is k/chambers = 2/6, NOT 1/(E+1)=1/5.
        (2, 0, 2 / 6),
        (2, 1, 1 / 4),
        (2, 2, 1 / 3),
        (2, 3, 1 / 2),
        (2, 4, 1 / 1),
        # k=3 -> E=3. m=0 is k/chambers = 3/6.
        (3, 0, 3 / 6),
        (3, 1, 1 / 3),
        (3, 2, 1 / 2),
        (3, 3, 1 / 1),
        # k=4 -> E=2. m=0 is k/chambers = 4/6.
        (4, 0, 4 / 6),
        (4, 1, 1 / 2),
        (4, 2, 1 / 1),
        # k=5 -> E=1. m=0 is k/chambers = 5/6.
        (5, 0, 5 / 6),
        (5, 1, 1 / 1),
    ],
)
def test_stay_probability_hand_computed(k, m, expected):
    assert stay_probability(k, m, CHAMBERS) == pytest.approx(expected)


# --------------------------------------------------------------------------
# 2. Enumeration cross-check
# --------------------------------------------------------------------------

@pytest.mark.parametrize("k", [1, 2, 3, 4, 5])
def test_brute_force_matches_closed_form(k):
    empties = CHAMBERS - k
    for m in range(0, empties + 1):
        formula = stay_probability(k, m, CHAMBERS)
        brute = brute_force_stay_probability(k, m, CHAMBERS)
        assert formula == pytest.approx(brute), f"mismatch at k={k}, m={m}"


def test_enumerate_rotations_has_one_per_chamber():
    rotations = enumerate_rotations(CHAMBERS)
    assert len(rotations) == CHAMBERS
    assert {r.start for r in rotations} == set(range(CHAMBERS))


# --------------------------------------------------------------------------
# 3. Monte Carlo stress tests
# --------------------------------------------------------------------------

def _simulate_always_stay(k: int, chambers: int, trials: int, seed: int):
    """Simulate `trials` rounds, always Staying, tracking per-step outcomes.

    Returns a dict {m: (loaded_count, total_count)} — for each streak length
    m (0-indexed draw number since round/spin start), how often that draw
    turned out loaded, out of how many times we reached that draw.
    """
    rng = random.Random(seed)
    empties = chambers - k
    max_m = empties  # can't survive more than `empties` empties
    outcomes = {m: [0, 0] for m in range(max_m + 1)}

    for _ in range(trials):
        start = rng.randrange(chambers)
        m = 0
        while True:
            pointer = m
            loaded = ((pointer - start) % chambers) < k
            outcomes[m][1] += 1
            if loaded:
                outcomes[m][0] += 1
                break
            m += 1
            if m > max_m:
                break

    return outcomes


def _simulate_always_spin(k: int, chambers: int, trials: int, seed: int):
    rng = random.Random(seed)
    loaded_count = 0
    for _ in range(trials):
        start = rng.randrange(chambers)
        loaded = (0 - start) % chambers < k
        if loaded:
            loaded_count += 1
    return loaded_count / trials


@pytest.mark.parametrize("k", [1, 2, 3, 4, 5])
def test_monte_carlo_always_stay(k):
    trials = 100_000
    outcomes = _simulate_always_stay(k, CHAMBERS, trials, seed=42 + k)
    empties = CHAMBERS - k
    for m in range(0, empties + 1):
        loaded_count, total = outcomes[m]
        if total == 0:
            continue  # streak length unreachable with too few trials, skip
        empirical = loaded_count / total
        expected = stay_probability(k, m, CHAMBERS)
        assert abs(empirical - expected) < 0.005, (
            f"k={k}, m={m}: empirical={empirical:.4f} expected={expected:.4f}"
        )


@pytest.mark.parametrize("k", [1, 2, 3, 4, 5])
def test_monte_carlo_always_spin(k):
    trials = 100_000
    empirical = _simulate_always_spin(k, CHAMBERS, trials, seed=99 + k)
    expected = spin_probability(k, CHAMBERS)
    assert abs(empirical - expected) < 0.005


# --------------------------------------------------------------------------
# 4. Edge cases
# --------------------------------------------------------------------------

def test_stay_probability_is_one_at_max_streak():
    for k in range(1, 6):
        empties = CHAMBERS - k
        assert stay_probability(k, empties, CHAMBERS) == pytest.approx(1.0)


def test_spin_and_stay_identical_at_round_start():
    for k in range(1, 6):
        assert spin_probability(k, CHAMBERS) == pytest.approx(
            stay_probability(k, 0, CHAMBERS)
        )


def test_k_five_only_one_empty_chamber():
    # k=5 -> only 1 empty chamber total (E=1). m=0 is the no-info base case
    # (k/chambers = 5/6); once you've survived that one empty (m=1), the
    # single remaining chamber to draw from is certain to be loaded.
    assert stay_probability(5, 0, CHAMBERS) == pytest.approx(5 / 6)
    assert stay_probability(5, 1, CHAMBERS) == pytest.approx(1.0)


@pytest.mark.parametrize("bad_k", [0, 6, -1, 7])
def test_invalid_k_rejected(bad_k):
    with pytest.raises(ValueError):
        spin_probability(bad_k, CHAMBERS)
    with pytest.raises(ValueError):
        stay_probability(bad_k, 0, CHAMBERS)


def test_m_out_of_range_rejected():
    with pytest.raises(ValueError):
        stay_probability(3, -1, CHAMBERS)
    with pytest.raises(ValueError):
        stay_probability(3, 10, CHAMBERS)
