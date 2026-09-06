# Cylinder Gambit

A Streamlit recreation of the Cylinder Gambit game: a fixed 5-level ladder
where each level loads one more bullet than the last, and the player has to
work out the odds of Spin vs. Stay themselves — the app shows the raw
numbers, not the computed percentages.

## Run it

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Run the tests

```bash
pytest -v
```

80 tests: hand-computed probability values, a brute-force enumeration
cross-check, 100,000-round Monte Carlo simulations per bullet count, the
level/score configuration, full Campaign progression (clearing every level,
losing mid-run, restarting), and two large randomized stress tests
(thousands of simulated campaigns) confirming the game never crashes and
scores are always valid.

## How the game works now

- **No difficulty slider.** The game is a fixed ladder: Level 1 loads 1
  bullet into the 6-chamber cylinder, Level 2 loads 2, up through Level 5
  (5 bullets, only 1 empty chamber). Every level fires 3 shots.
- **The opening shot of each level has no choice.** With zero history, Spin
  and Stay are mathematically identical, so the game just fires once at
  the freshly-randomized position — that's the "Pull the trigger" step.
- **Every shot after that is a real Spin vs. Stay decision.** Spin
  re-randomizes the cylinder and forgets everything you've learned. Stay
  advances one chamber and keeps your streak of survived empties.
- **The app shows the inputs, not the odds.** For Spin you're shown the
  bullet count and total chambers (`k / chambers`). For Stay you're shown
  the total empty chambers and how many you've already survived in a row
  (`1 / (E − m + 1)`, for m ≥ 1). You do the division yourself. After the
  level ends, the review table does show both computed percentages and
  whether each choice was optimal, so you can check your reasoning.
- **Scoring is per level, not per decision.** Clearing Level 1 scores 10
  points, Level 2 scores 15, Level 3 scores 20, Level 4 scores 25, Level 5
  scores 30 — a flat +5 per level, awarded only when you survive all 3
  shots. A Loaded draw at any point ends the run with whatever you'd
  already banked from earlier levels.
- **High levels require spinning.** At Level 4 (2 empty chambers) and
  especially Level 5 (1 empty chamber), staying too long makes the next
  draw *guaranteed* loaded — the math forces you to spin at least once
  (twice, at Level 5) to have any chance of clearing the level at all.
  This is a real, provable property of the model (see the
  `test_streak_m_never_exceeds_empties_in_real_play` stress test), not a
  quirk of hard-coded difficulty.

## The probability model

Full derivation lives in `probability.py`'s docstring, but the short
version: Spin is always `k / 6` — no history to condition on. Stay is
`1 / (E − m + 1)` once you've survived `m ≥ 1` consecutive empties (`E` is
the total number of empty chambers), derived by enumerating the 6 possible
starting positions of the bullet block and counting which are still
consistent with what you've seen. The one trap: at `m = 0`, Stay is just
`k / 6` (same as Spin) — plugging `m = 0` straight into the `1/(E−m+1)`
fraction gives the wrong answer for every `k` except 1, which is exactly
what the brute-force enumeration test in `test_probability.py` is there to
catch.

## What would be easy to extend from here

- **A difficulty toggle** (fixed ladder vs. free choice of `k`): the old
  slider-driven `bullets_for_level`-equivalent already existed in an
  earlier version of this game; re-adding it would only mean changing how
  `Campaign.start_level()` picks `k`, with no changes to `probability.py`
  or `RoundState`.
- **More than 5 levels**: `LEVEL_MAX` and `bullets_for_level` are the only
  two things that would need to change if a future version wants levels
  beyond 5 bullets — though with only 6 chambers, level 5 is already the
  hardest possible level (1 empty chamber).
- **An auto-play "optimal policy" bot**: `spin_probability` and
  `stay_probability` are still pure functions with no UI coupling, so a
  bot that always picks `min(spin_p, stay_p)` could be written in a few
  lines against the existing `RoundState`/`Campaign` API.
