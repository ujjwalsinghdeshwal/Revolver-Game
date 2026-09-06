# Cylinder Gambit

A small Streamlit recreation of the Cylinder Gambit game, with a slider so
you pick your own difficulty (bullets loaded) before each round instead of
climbing a preset ladder.

## Run it

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Run the tests

```bash
pytest -v
```

57 tests: hand-computed values, a brute-force enumeration cross-check,
100,000-round Monte Carlo simulations per bullet count, edge cases, and a
scripted scoring sequence.

## The probability model

A 6-chamber cylinder hides `k` bullets in one consecutive block, starting at
a uniformly random, hidden position. **Spin** re-randomizes that position
and throws away everything you've learned, so `P(loaded) = k / 6` no matter
what happened before. **Stay** advances one chamber and keeps your history:
if you've survived `m` consecutive empty draws since the last spin, then
`P(loaded) = 1 / (E − m + 1)` where `E = 6 − k` is the total number of empty
chambers — derived by enumerating the 6 possible starting positions of the
block, discarding the ones inconsistent with the empties you've already
seen, and taking the fraction of survivors whose next chamber is loaded.
The one wrinkle worth flagging: at `m = 0` (no observations yet) Stay is
just the unconditioned `k / 6`, identical to Spin — plugging `m = 0` into
the `1/(E−m+1)` fraction directly gives the wrong number for any `k` other
than 1, which is exactly the kind of off-by-one trap the enumeration
cross-check in `test_probability.py` is there to catch.

The slider lets you pick `k` from 1 to 5 before every round, so you're
choosing your own risk level each time rather than working through a fixed
sequence of levels.

## What would be easy to extend from here

- **Multi-round campaigns**: `game.py`'s `RoundState` already isolates one
  round's state; a thin wrapper tracking cumulative score across several
  `RoundState` instances would need no changes to the probability or
  scoring logic.
- **A spin-count limit**: `Action.SPIN` is already a distinct branch in
  `RoundState.choose()` — capping it would mean adding one counter and one
  check there, with no changes to `probability.py`.
- **An auto-play "optimal policy" bot**: since `spin_probability` and
  `stay_probability` are pure functions with no UI coupling, a bot that
  always chooses `min(spin_p, stay_p)` could be written in a few lines
  against the existing `RoundState` API and used for a "watch the optimal
  strategy" demo mode.
