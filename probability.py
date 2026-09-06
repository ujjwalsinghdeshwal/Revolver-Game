"""Pure probability functions for Cylinder Gambit.

No Streamlit, no I/O, no game state — just numbers in, numbers out, so this
module can be unit tested and reused if the UI or scoring model ever changes.

Model
-----
A cylinder has ``chambers`` slots arranged in a circle. ``k`` bullets are
loaded into a single *consecutive* run of ``k`` chambers, starting at a
uniformly random rotation ``r`` in ``0 .. chambers - 1``. The player always
draws from a fixed pointer position and either:

* **Spins**: the rotation is re-randomized (uniform again), history is
  forgotten, and the very next draw is like a fresh start (m = 0).
* **Stays**: the pointer simply advances one chamber and whatever streak of
  empty draws has been observed so far (``m``) carries forward.

Spin probability
-----------------
After a spin, the position about to be drawn is uniformly one of the
``chambers`` slots, and exactly ``k`` of them are loaded, so:

    P(next draw loaded | spin) = k / chambers

This holds regardless of any prior history, because a spin erases it.

Stay probability — derivation
------------------------------
Fix the pointer's starting slot as position 0, and number the chambers
0, 1, 2, ... going around the cylinder. The rotation ``r`` (the starting
position of the k-length loaded block) is uniform over ``chambers`` values.
Suppose the player has already survived ``m`` consecutive empty draws since
the last spin/round-start — i.e. positions 0, 1, ..., m-1 were all empty.

Enumerate the ``chambers`` possible rotations ``r``. For a given r, position
``p`` is loaded iff ``p`` lies in the arc ``[r, r+k-1] (mod chambers)``.
Filter to rotations consistent with "positions 0..m-1 all empty", then ask:
of those survivors, what fraction have position m loaded?

**The m = 0 case is special and must not be plugged into the same fraction.**
With zero empties observed there is nothing to condition on yet, so Stay is
just "draw from the current position with no information" — identical to a
fresh Spin:

    P(next draw loaded | stay, m = 0) = k / chambers  (same as Spin)

For m >= 1, filtering the rotations on "positions 0..m-1 all empty" rules
out every rotation whose block would have touched any of those m positions.
What remains are exactly the rotations where the block starts somewhere in
positions m, m+1, ..., chambers-1 such that the *entire* block still fits
without wrapping back over the already-cleared positions 0..m-1. Working
through the arc-counting (see ``enumerate_rotations`` for the brute-force
version that checks this by direct simulation rather than argument), the
number of consistent rotations reduces to ``E - m + 1`` where
``E = chambers - k`` is the total number of empty chambers, and among those
survivors exactly one places the block's leading edge right at position m
(i.e., position m is loaded). That gives, for m >= 1:

    P(next draw loaded | stay, m empties survived) = 1 / (E - m + 1)

Naively applying this same fraction at m = 0 (giving 1/(E+1)) is a classic
trap: it only happens to equal k/chambers when k = 1, and is wrong for
every k >= 2 (verify with ``brute_force_stay_probability`` — it disagrees
with 1/(E+1) at m=0 for k >= 2, but agrees with it for every m >= 1). The
mistake comes from treating "zero observations" as if it were a real
conditioning event instead of the no-information base case it actually is.
In this game m is never actually 0 at decision time anyway — the opening
draw of a round is unconditional and un-scored (see game.py), so every
real Spin/Stay choice happens with m >= 1 — but the function still handles
m = 0 correctly for testing and for completeness.

This is emphatically **not** ``bullets_remaining / chambers_remaining``
(the "shrinking deck" model) — that model assumes bullets get reshuffled
into the remaining chambers after each draw, which is wrong here because
the k bullets are locked into one consecutive block for the whole round.
The formula above only depends on how many *consecutive* empties you've
already survived, not on how many chambers are physically left.
"""

from __future__ import annotations

from dataclasses import dataclass


def spin_probability(k: int, chambers: int = 6) -> float:
    """P(next draw is loaded) immediately after a Spin.

    Always k / chambers — a spin re-randomizes uniformly and forgets
    everything that happened before it.
    """
    _validate_k(k, chambers)
    return k / chambers


def stay_probability(k: int, m: int, chambers: int = 6) -> float:
    """P(next draw is loaded) after Staying, having survived m empties.

    E = chambers - k empty chambers total.
    m = consecutive empty draws already survived since the last spin
        (or since round start).

    m == 0: no observations yet -> same as spin, k / chambers.
    m >= 1: P = 1 / (E - m + 1)   (see module docstring for the derivation
            and why m = 0 is NOT just this same formula with m plugged in)
    """
    _validate_k(k, chambers)
    empties = chambers - k
    if m < 0 or m > empties:
        raise ValueError(
            f"m={m} is out of range for k={k}, chambers={chambers} "
            f"(valid range is 0..{empties})"
        )
    if m == 0:
        return k / chambers
    return 1 / (empties - m + 1)


def _validate_k(k: int, chambers: int) -> None:
    if not (1 <= k <= chambers - 1):
        raise ValueError(
            f"k={k} is invalid: must have at least 1 bullet and at least "
            f"1 empty chamber (1 <= k <= {chambers - 1})"
        )


@dataclass(frozen=True)
class Rotation:
    """One possible hidden state of the cylinder: bullets start at `start`."""

    start: int

    def is_loaded(self, position: int, k: int, chambers: int) -> bool:
        offset = (position - self.start) % chambers
        return offset < k


def enumerate_rotations(chambers: int = 6) -> list[Rotation]:
    """All equally-likely hidden rotations of the loaded block."""
    return [Rotation(start=r) for r in range(chambers)]


def brute_force_stay_probability(k: int, m: int, chambers: int = 6) -> float:
    """Brute-force cross-check for stay_probability.

    Enumerates every rotation, keeps only the ones consistent with
    "positions 0..m-1 were all empty", and returns the fraction of
    survivors for which position m is loaded. Used only in tests, to
    confirm the closed-form formula above is not a case of getting the
    algebra wrong.
    """
    _validate_k(k, chambers)
    empties = chambers - k
    if m < 0 or m > empties:
        raise ValueError(f"m={m} out of range 0..{empties}")

    rotations = enumerate_rotations(chambers)
    survivors = [
        rot
        for rot in rotations
        if all(not rot.is_loaded(p, k, chambers) for p in range(m))
    ]
    if not survivors:
        raise RuntimeError("no surviving rotations — should not happen")

    loaded_next = sum(1 for rot in survivors if rot.is_loaded(m, k, chambers))
    return loaded_next / len(survivors)
