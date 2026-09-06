"""Round + campaign state machine for Cylinder Gambit.

Holds all mutable state and calls into probability.py for the math. No
Streamlit here — app.py is the only file that should import streamlit.

Game shape (per the current design):
- No difficulty slider. The game is a fixed ladder of levels.
- Level N loads N bullets (1 through LEVEL_MAX) into the CHAMBERS-chamber
  cylinder. Every level fires DRAWS_PER_ROUND shots.
- The very first shot of every round is unconditioned (Spin and Stay are
  mathematically identical at m=0 — see probability.py) so the UI doesn't
  offer a real choice there; it's just "pull the trigger". Every shot after
  that offers a real Spin vs. Stay decision.
- Clearing a level (surviving all its shots) scores points; the amount
  increases by a fixed step each level. Getting a Loaded draw ends the run.
- The player is shown the *inputs* to each option's probability (bullets,
  chambers, empties, streak survived) but never the computed probability
  itself — the point of the game is doing that arithmetic yourself.
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

LEVEL_MIN = 1
LEVEL_MAX = 5  # k = level number; must leave >=1 empty chamber, so <= CHAMBERS-1

LEVEL_BASE_SCORE = 10   # points for clearing level 1
LEVEL_SCORE_STEP = 5    # extra points per level above 1


def bullets_for_level(level: int) -> int:
    """How many bullets are loaded at a given level.

    Currently a direct 1:1 mapping (level 1 -> 1 bullet, level 5 -> 5
    bullets). Kept as its own function so a future change ("level 6 keeps
    5 bullets but drops a draw", etc.) only touches this one spot.
    """
    if not (LEVEL_MIN <= level <= LEVEL_MAX):
        raise ValueError(f"level={level} is outside {LEVEL_MIN}..{LEVEL_MAX}")
    return level


def score_for_level(level: int) -> int:
    """Points awarded for clearing this level.

    Level 1 -> LEVEL_BASE_SCORE, and +LEVEL_SCORE_STEP for every level
    after that (level 2 -> 15, level 3 -> 20, ... with the defaults above).
    """
    if not (LEVEL_MIN <= level <= LEVEL_MAX):
        raise ValueError(f"level={level} is outside {LEVEL_MIN}..{LEVEL_MAX}")
    return LEVEL_BASE_SCORE + LEVEL_SCORE_STEP * (level - 1)


class Action(str, Enum):
    SPIN = "spin"
    STAY = "stay"


class DrawResult(str, Enum):
    EMPTY = "empty"
    LOADED = "loaded"


@dataclass
class ChoiceInputs:
    """The raw numbers the player needs to work out each option's odds.

    Deliberately does NOT include the computed probabilities — the UI
    shows these numbers and lets the player do the division themselves.
    """

    k: int
    chambers: int
    empties: int
    streak_m: int


@dataclass
class Decision:
    """Record of a single Spin/Stay choice and what happened after.

    Probabilities are stored here for the post-round review table (so the
    player can check their reasoning after the fact) but are never shown
    at decision time.
    """

    action: Action
    inputs: ChoiceInputs
    spin_probability: float
    stay_probability: float
    was_optimal: bool
    result: DrawResult


@dataclass
class RoundState:
    """Everything about the level currently in progress."""

    k: int
    chambers: int = CHAMBERS
    draws_per_round: int = DRAWS_PER_ROUND
    rotation_start: int = field(default_factory=lambda: 0)
    pointer: int = 0
    streak_m: int = 0
    draws_taken: int = 0
    decisions: list[Decision] = field(default_factory=list)
    round_over: bool = False
    round_cleared: bool = False
    first_draw_result: DrawResult | None = None

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

    def _resolve_empty_advance(self) -> None:
        self.pointer += 1
        self.streak_m += 1
        if self.draws_taken >= self.draws_per_round:
            self.round_over = True
            self.round_cleared = True

    # -- public API ------------------------------------------------------

    def current_choice_inputs(self) -> ChoiceInputs:
        """Raw numbers for the player to reason about the next draw."""
        return ChoiceInputs(
            k=self.k,
            chambers=self.chambers,
            empties=self.chambers - self.k,
            streak_m=self.streak_m,
        )

    def draw_first(self) -> DrawResult:
        """Resolve the round's opening draw.

        The very first draw of a round has no Spin/Stay choice — the game
        just fires once at the freshly-randomized position, since Spin and
        Stay are provably identical with zero history.
        """
        if self.round_over:
            raise RuntimeError("round is already over")
        if self.draws_taken != 0:
            raise RuntimeError("draw_first can only be called once, at the start")

        loaded = self._is_loaded(self.pointer)
        result = DrawResult.LOADED if loaded else DrawResult.EMPTY
        self.first_draw_result = result
        self.draws_taken += 1

        if loaded:
            self.round_over = True
            self.round_cleared = False
        else:
            self._resolve_empty_advance()

        return result

    def choose(self, action: Action) -> Decision:
        """Resolve one Spin/Stay decision: draw, judge it, log it."""
        if self.round_over:
            raise RuntimeError("round is already over")
        if self.draws_taken == 0:
            raise RuntimeError("call draw_first() before any choose()")

        inputs = self.current_choice_inputs()
        spin_p = spin_probability(self.k, self.chambers)
        stay_p = stay_probability(self.k, self.streak_m, self.chambers)

        if action == Action.SPIN:
            self._randomize_rotation()
        chosen_p = spin_p if action == Action.SPIN else stay_p
        was_optimal = chosen_p == min(spin_p, stay_p)

        loaded = self._is_loaded(self.pointer)
        result = DrawResult.LOADED if loaded else DrawResult.EMPTY

        decision = Decision(
            action=action,
            inputs=inputs,
            spin_probability=spin_p,
            stay_probability=stay_p,
            was_optimal=was_optimal,
            result=result,
        )
        self.decisions.append(decision)
        self.draws_taken += 1

        if loaded:
            self.round_over = True
            self.round_cleared = False
        else:
            self._resolve_empty_advance()

        return decision

    def all_results(self) -> list[DrawResult]:
        """First draw + every decision's draw, in order, for the shot log."""
        results = []
        if self.first_draw_result is not None:
            results.append(self.first_draw_result)
        results.extend(d.result for d in self.decisions)
        return results


@dataclass
class Campaign:
    """Tracks progress across the whole level ladder.

    One Campaign = one attempt at climbing from level 1 to LEVEL_MAX.
    A Loaded draw at any level ends the campaign; clearing LEVEL_MAX wins it.
    """

    level: int = LEVEL_MIN
    total_score: int = 0
    round: RoundState | None = None
    finished: bool = False
    victory: bool = False
    last_level_points: int = 0

    def start_level(self) -> None:
        """(Re)start the round for the current level."""
        k = bullets_for_level(self.level)
        self.round = RoundState(k=k)
        self.finished = False
        self.victory = False

    def advance_after_clear(self) -> None:
        """Call once after self.round.round_cleared is True.

        Awards points for the level just cleared, then either moves to the
        next level (and starts its round) or ends the campaign in victory
        if that was the last level.
        """
        if self.round is None or not self.round.round_cleared:
            raise RuntimeError("advance_after_clear called without a cleared round")

        points = score_for_level(self.level)
        self.total_score += points
        self.last_level_points = points

        if self.level >= LEVEL_MAX:
            self.finished = True
            self.victory = True
            # Deliberately keep self.round as-is (the just-cleared final
            # round) rather than nulling it out, so the UI can still show
            # the cylinder/shot log/review for the winning round.
        else:
            self.level += 1
            self.start_level()

    def register_loss(self) -> None:
        """Call once after self.round.round_over is True and not cleared."""
        if self.round is None or self.round.round_cleared or not self.round.round_over:
            raise RuntimeError("register_loss called without a lost round")
        self.finished = True
        self.victory = False
        self.last_level_points = 0

    def restart(self) -> None:
        """Start a brand new campaign from level 1, score reset to 0."""
        self.level = LEVEL_MIN
        self.total_score = 0
        self.finished = False
        self.victory = False
        self.last_level_points = 0
        self.start_level()
