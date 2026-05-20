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

## Recent training fatigue

**Entry:** `compute_recent_fatigue()` — uses `% of effective_max_hr` from `app/core/hr_profile.py`, not absolute 160 bpm.

## Workout type

**Entry:** `workout_type_from_readiness()` in `readiness.py`, used by `training_recommendation_engine.py`.

SPRINT at score 6 only if penalty &lt; 0.4 and user has sprint sessions in `workout_patterns.by_type`.

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
- Agent tool `assess_recovery_status` uses the same snapshot builder.
