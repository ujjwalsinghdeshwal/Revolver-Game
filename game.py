"""Round state machine for Cylinder Gambit.

Holds all mutable round state (pointer streak, shot log, score) and calls
into probability.py for the math. No Streamlit here — app.py is the only
file that should import streamlit.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum

from probability import spin_probability, stay_probability

# --------------------------------------------------------------------------
# Config — one place to change the rules of the game.
# --------------------------------------------------------------------------
CHAMBERS = 6
DRAWS_PER_ROUND = 3
K_MIN = 1
K_MAX = 5
SCORE_OPTIMAL = 10
SCORE_SUBOPTIMAL = -5
SCORE_ROUND_CLEAR_BONUS = 15


class Action(str, Enum):
    SPIN = "spin"
    STAY = "stay"


class DrawResult(str, Enum):
    EMPTY = "empty"
    LOADED = "loaded"


@dataclass
class Decision:
    """Record of a single Spin/Stay choice and what happened after."""

    action: Action
    spin_probability: float
    stay_probability: float
    chosen_probability: float
    was_optimal: bool
    result: DrawResult
    points: int


@dataclass
class RoundState:
    """Everything about the round currently in progress."""

    k: int
    chambers: int = CHAMBERS
    draws_per_round: int = DRAWS_PER_ROUND
    rotation_start: int = field(default_factory=lambda: 0)
    pointer: int = 0
    streak_m: int = 0
    draws_taken: int = 0
    decisions: list[Decision] = field(default_factory=list)
    score: int = 0
    round_over: bool = False
    round_cleared: bool = False

    def __post_init__(self) -> None:
        # Reuses spin_probability purely for its k/chambers validation.
        spin_probability(self.k, self.chambers)
        self._randomize_rotation()

    # -- internal helpers ---------------------------------------------

    def _randomize_rotation(self) -> None:
        self.rotation_start = random.randrange(self.chambers)
        self.pointer = 0
        self.streak_m = 0

    def _is_loaded(self, position: int) -> bool:
        offset = (position - self.rotation_start) % self.chambers
        return offset < self.k

    # -- public API ------------------------------------------------------

    def current_probabilities(self) -> tuple[float, float]:
        """Return (spin_probability, stay_probability) for the next draw."""
        spin_p = spin_probability(self.k, self.chambers)
        stay_p = stay_probability(self.k, self.streak_m, self.chambers)
        return spin_p, stay_p

    def draw_first(self) -> DrawResult:
        """Resolve the round's opening draw.

        The very first draw of a round has no Spin/Stay choice — the game
        just fires once at the freshly-randomized position. Not scored,
        since there was no decision to grade.
        """
        if self.round_over:
            raise RuntimeError("round is already over")
        if self.draws_taken != 0:
            raise RuntimeError("draw_first can only be called once, at the start")

        loaded = self._is_loaded(self.pointer)
        result = DrawResult.LOADED if loaded else DrawResult.EMPTY
        self.draws_taken += 1

        if loaded:
            self.round_over = True
            self.round_cleared = False
        else:
            self.pointer += 1
            self.streak_m += 1
            if self.draws_taken >= self.draws_per_round:
                self.round_over = True
                self.round_cleared = True
                self.score += SCORE_ROUND_CLEAR_BONUS

        return result

    def choose(self, action: Action) -> Decision:
        """Resolve one Spin/Stay decision: draw, score it, log it."""
        if self.round_over:
            raise RuntimeError("round is already over")
        if self.draws_taken == 0:
            raise RuntimeError("call draw_first() before any choose()")

        spin_p, stay_p = self.current_probabilities()

        if action == Action.SPIN:
            self._randomize_rotation()
            chosen_p = spin_p
        else:
            chosen_p = stay_p

        lower = min(spin_p, stay_p)
        was_optimal = chosen_p == lower

        loaded = self._is_loaded(self.pointer)
        result = DrawResult.LOADED if loaded else DrawResult.EMPTY
        points = SCORE_OPTIMAL if was_optimal else SCORE_SUBOPTIMAL
        self.score += points

        decision = Decision(
            action=action,
            spin_probability=spin_p,
            stay_probability=stay_p,
            chosen_probability=chosen_p,
            was_optimal=was_optimal,
            result=result,
            points=points,
        )
        self.decisions.append(decision)
        self.draws_taken += 1

        if loaded:
            self.round_over = True
            self.round_cleared = False
        else:
            # advance pointer/streak for the next Stay-probability calc
            self.pointer += 1
            self.streak_m += 1
            if self.draws_taken >= self.draws_per_round:
                self.round_over = True
                self.round_cleared = True
                self.score += SCORE_ROUND_CLEAR_BONUS

        return decision
