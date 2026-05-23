# Floating Coach — Algorithms

## Versions

| Module | Version | Config |
|--------|---------|--------|
| Readiness | `readiness_v4` (default) or `current_readiness_v3` | `READINESS_VERSION` env |
| Load ratio | `load_metrics_v1` | unified 7d / 28d windows |

## Readiness score (0–6)

**Entry:** `app/core/readiness.py` → `compute_readiness_score()`

Base score `3.0` plus:

- Sleep score: `(sleep_score - 70) / 15`
- Sleep hours (fallback): `(sleep_hours - 7) / 1.5`
- Stress: `(45 - avg_stress) / 20`
- Body Battery: `(body_battery - 50) / 25`
- HRV v4: deviation from 14-night median baseline
- Minus recent training penalty

Caps apply for low Body Battery and recent hard sessions.

### Stress bands (Garmin UI)

| Range | Label |
|-------|-------|
| 0–25 | rust |
| 26–50 | laag |
| 51–75 | matig |
| 76–100 | hoog |

Higher stress values are worse for recovery (score uses `(45 - avg_stress) / 20`).

## Recent training fatigue

**Entry:** `compute_recent_fatigue()` — window **72 hours**.

- Uses `% of effective_max_hr` from `app/core/hr_profile.py`, not absolute 160 bpm.
- **Strength / HIIT:** duration-based load floor when average HR is low (`STRENGTH_TRAINING`, `HIIT`, etc.).
- **Hard-session floor:** `1.1` until 36h, then linear decay to `0` at 72h (replaces binary cliff).
- Load decay divisor aligned with 72h window.

Penalty thresholds on weighted load: 25 → 0.4, 45 → 0.8, 70 → 1.2, 100 → 1.6.

## HRV trend

**Entry:** `app/core/recovery_snapshot.py`

`metrics.hrvTrend` = chronological list of nightly `lastNightAvg` values from `_hrv_history()` (up to 14 nights), **not** intraday `hrvValues`.

## Workout type

**Entry:** `workout_type_from_readiness()` in `readiness.py`, used by `training_recommendation_engine.py`.

| Score | Default type |
|-------|----------------|
| ≤2 | HERSTEL |
| 3 | DUUR |
| 4 | THRESHOLD |
| 5 | VO2MAX |
| 6 | SPRINT (only if sprint history + low penalty) |

Body Battery ≤25 or recent hard penalty ≥1.1 → HERSTEL override.

## Training generator rules

**Entry:** `build_recommendation()` in `training_recommendation_engine.py`

Signals wired from training profile:

| Signal | Rule |
|--------|------|
| `sport_baselines[sport].load_ratio` | >1.25 → type −1 step, −12% duration; <0.75 + recovery ≥4 → +10% duration |
| `weekly_pattern.hard_sessions_per_week` + recent hard (<72h) | Cap intensity (step down THRESHOLD/VO2/SPRINT) |
| `weekly_pattern.common_sequence` | Suggest next type when recent sessions match sequence prefix |
| `recent_training.sessions` / strength yesterday | HERSTEL + cross-training sport after strength/HIIT |
| `dominant_sport` | Preferred sport when pattern has no `preferred_sport` |

Reasoning lines include load ratio, yesterday's session, and recovery penalty when relevant.

Demo UI (`workout-plan.js`) mirrors `workout_type_from_readiness`; logged-in users use backend draft only.

## Load ratio

**Entry:** `app/core/load_metrics.py`

`load_ratio = acute_hours(7d) / chronic_weekly_hours(28d ÷ 4)`

Thresholds: &lt; 0.75 low, 0.75–1.25 balanced, &gt; 1.25 high.

## Weather adjustments

**Entry:** `_apply_weather_adjustments()` in `training_recommendation_engine.py`

- Heat ≥ 28°C: −10% duration, cap intensity 95%
- Cold ≤ 3°C: +8 min
- Thunder: cap intensity on non-recovery sessions

## API

- `GET /garmin/recovery` → `build_live_recovery_snapshot()`
- `GET /garmin/training/recommendation` → `build_recommendation()`
- Agent tool `assess_recovery_status` uses the same snapshot builder.
