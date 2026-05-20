// Dashboard — today overview + hero workout generator.
const { useEffect: useEffectD, useState: useStateD } = React;
const FC = window.FC_UTILS;

function Dashboard({ recoveryScore, recoveryData, recoverySnapshot, weather, onNavigate, apiStatus, userId, draftWorkout }) {
  const D = window.FC_DATA;
  const R = recoveryData || D.recovery;
  const activeDate = recoverySnapshot?.calendar_date
    ? new Date(`${recoverySnapshot.calendar_date}T12:00:00`)
    : new Date();
  const online = apiStatus === 'online';
  const rec = userId && !draftWorkout
    ? {
        type: 'LIVE',
        dutch: 'Voorstel laden',
        sport: 'Garmin live',
        duration: '–',
        desc: 'Ik haal je officiële coachvoorstel op bij de backend.',
      }
    : dashboardRecommendationFromDraft(draftWorkout, recoveryScore);

  // Live data: logged-in users keep stale live data instead of silently seeing demo.
  const activitiesQuery = window.useLiveData(
    (uid) => window.FC_API.fetchGarminActivities(uid, 10, 7),
    { activities: D.activities, weekly_trend: D.weeklyTrend, summary: D.weeklySummary },
    [],
    { online, userId, cacheKey: 'dashboard_activities_7', emptyData: { activities: [], weekly_trend: [], summary: null } },
  );
  const weeklyQuery = window.useLiveData(
    (uid) => window.FC_API.fetchWeeklyAnalysis(uid),
    {
      current_week: { ...D.weeklySummary, distance_meters: D.weeklySummary.distance_km*1000, duration_seconds: D.weeklySummary.duration_hours*3600 },
      baseline_weekly: D.baseline,
      deltas: D.weeklyAnalysis.deltas,
      load_ratio: D.weeklyAnalysis.load_ratio,
      summary: D.weeklyAnalysis.summary,
      insight: D.weeklyAnalysis.insight,
    },
    [],
    { online, userId, cacheKey: 'dashboard_weekly', emptyData: { current_week: null, baseline_weekly: null, deltas: {}, load_ratio: null, summary: null, insight: null } },
  );

  const activities = activitiesQuery.data.activities || (!userId ? D.activities : []);
  const weeklyTrend = activitiesQuery.data.weekly_trend || (!userId ? D.weeklyTrend : []);
  const weekSummary = weeklyQuery.data.current_week || (!userId ? D.weeklySummary : null);
  const analysis = weeklyQuery.data;
  const source = !userId
    ? 'demo'
    : ([activitiesQuery.source, weeklyQuery.source].includes('live') ? 'live'
      : ([activitiesQuery.source, weeklyQuery.source].includes('stale-live') ? 'stale-live' : 'empty'));
  const scoreNum = recoveryScore ?? null;
  const ringPct = scoreNum != null ? (scoreNum / 6) : 0;
  const ringClass = scoreNum == null ? '' : scoreNum <= 2 ? 'bad' : scoreNum <= 3 ? 'warn' : '';
  const recoveryLabel = scoreNum != null ? FC.recoveryLabel(scoreNum).toLowerCase() : 'laden…';
  const weatherLine = weather?.temperature_c != null
    ? `${weather.location_name || 'Huidige locatie'} · ${Math.round(weather.temperature_c)}°C ${weather.condition}`
    : (weather?.source === 'unavailable' ? 'Locatie niet gedeeld' : 'Weer laden…');

  // Animated clock
  const [now, setNow] = useStateD(new Date());
  useEffectD(() => {
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  const showDemoBanner = source === 'demo' || !userId;

  return (
    <div className="col" style={{ gap: 24 }} data-screen-label="Vandaag">
      {showDemoBanner && (
        <div className="card" style={{
          background: 'color-mix(in oklab, var(--accent) 18%, var(--surface))',
          borderColor: 'color-mix(in oklab, var(--accent) 40%, var(--line))',
          padding: '12px 16px', display: 'flex', alignItems: 'center', gap: 12,
        }}>
          <span className="tag accent">Demo</span>
          <div style={{ flex: 1, fontSize: 13, color: 'var(--ink-2)' }}>
            <b>Demo-data</b> — verbind Garmin voor live inzichten.
          </div>
          <button className="btn accent" style={{ padding: '8px 14px', fontSize: 12 }}
            onClick={() => onNavigate('profiel')}>
            Verbind Garmin
          </button>
        </div>
      )}

      {/* Head */}
      <div className="screen-head">
        <div>
          <div className="label" style={{ marginBottom: 10 }}>
            <span style={{ color: 'var(--ink)' }}>{FC.fmtDayName(activeDate.toISOString())}</span>
            {' · '}{activeDate.toLocaleDateString('nl-BE', { day: '2-digit', month: 'long' })}
          </div>
          <h1>Goedemorgen, {D.user.firstName}.<br/>
              <em>Vandaag voel je je </em><span style={{ color: 'var(--ink)' }}>{recoveryLabel}</span><em>.</em>
          </h1>
        </div>
        <div className="meta">
          <div className="mono" style={{ fontSize: 13, color: 'var(--ink)', fontWeight: 500, letterSpacing: '-.01em' }}>
            {now.toLocaleTimeString('nl-BE', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
          </div>
          <div style={{ marginTop: 4 }}>{weatherLine}</div>
        </div>
      </div>

      {/* Live/demo banner — surfaces when API errored */}
      {activitiesQuery.error && (
        <div className="card" style={{ background: 'oklch(96% 0.04 60)', borderColor: 'oklch(85% 0.08 60)',
          padding: '12px 16px', display: 'flex', alignItems: 'center', gap: 12 }}>
          <span className="live-dot" style={{ background: 'oklch(72% 0.16 60)' }}></span>
          <div style={{ flex: 1, fontSize: 13, color: 'oklch(35% 0.10 50)' }}>
            <b>{activitiesQuery.source === 'stale-live' ? 'Laatste live data getoond.' : (userId ? 'Live data tijdelijk niet beschikbaar.' : 'Demo data getoond.')}</b> Backend onbereikbaar:
            <span className="mono" style={{ marginLeft: 6, fontSize: 12 }}>{activitiesQuery.error}</span>
          </div>
          <button className="btn ghost" style={{ padding: '6px 12px', fontSize: 12 }}
                  onClick={activitiesQuery.refetch}>
            Opnieuw <span className="mono">↻</span>
          </button>
        </div>
      )}

      {/* Hero workout card */}
      <HeroWorkout rec={rec} draftWorkout={draftWorkout} score={scoreNum ?? 3} weather={weather} onNavigate={onNavigate} />

      {/* Metric strip */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 20 }}>
        <MetricStat label="Recovery" value={scoreNum ?? '—'} unit={scoreNum != null ? '/6' : ''} ring={scoreNum != null ? ringPct : undefined} ringClass={ringClass} />
        <MetricStat label="Body Battery" value={R.bodyBatteryCurrent ?? R.bodyBattery ?? '–'} unit={(R.bodyBatteryCurrent ?? R.bodyBattery) == null ? '' : "%"} sub={R.hrvOvernight ? `HRV ${R.hrvOvernight}ms` : 'Geen HRV data'} />
        <MetricStat label="Sleep score" value={R.sleepScore ?? '–'} unit="" sub={R.sleepHours ? `${R.sleepHours.toFixed(1)}u slaap` : 'Geen slaapdata'} />
      </div>

      {/* Week + recent */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: 20 }}>
        <WeekChart weeklyTrend={weeklyTrend} weekSummary={weekSummary} analysis={analysis} allowDemo={!userId} />
        <CoachInsight onNavigate={onNavigate} analysis={analysis} allowDemo={!userId} />
      </div>

      <RecentActivities onNavigate={onNavigate} activities={activities} source={source} />
    </div>
  );
}

function HeroWorkout({ rec, draftWorkout, score, weather, onNavigate }) {
  const D = window.FC_DATA;
  const ringPct = (score / 6);
  const ringClass = score <= 2 ? 'bad' : score <= 3 ? 'warn' : '';
  const c = 2 * Math.PI * 64;
  const dash = c * ringPct;

  return (
    <div className="card dark" style={{ padding: 0, overflow: 'hidden', position: 'relative' }}>
      {/* Accent strip */}
      <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 3,
                    background: 'var(--accent)' }} />

      <div style={{ padding: '28px 32px 32px', display: 'grid',
                    gridTemplateColumns: '1.4fr 1fr', gap: 32, alignItems: 'center' }}>
        {/* Left: workout */}
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 18 }}>
            <span className="tag accent">{rec.type}</span>
            <span className="tag" style={{ background: 'transparent',
              border: '1px solid oklch(35% 0.005 100)', color: 'oklch(78% 0.01 100)' }}>
              {rec.sport}
            </span>
            <span className="mono" style={{ fontSize: 10, color: 'oklch(72% 0.01 100)',
              textTransform: 'uppercase', letterSpacing: '.16em' }}>
              Aanbevolen vandaag
            </span>
          </div>
          <h2 style={{ fontSize: 48, fontWeight: 600, letterSpacing: '-.025em',
                       lineHeight: 1, color: '#fff', marginBottom: 12 }}>
            {rec.dutch}
          </h2>
          <p style={{ fontSize: 16, color: 'oklch(78% 0.01 100)', maxWidth: 460,
                      lineHeight: 1.5, margin: '0 0 24px' }}>
            {rec.desc}
            {weather?.training_note && weather.source !== 'unavailable' && (
              <><br/><span style={{ color: 'oklch(86% 0.08 125)' }}>Weer: {weather.training_note}.</span></>
            )}
          </p>

          {/* Workout structure mini-strip */}
          <WorkoutStrip type={rec.type} draftWorkout={draftWorkout} />

          <div style={{ display: 'flex', gap: 12, marginTop: 24, alignItems: 'center' }}>
            <button className="btn accent xl" onClick={() => onNavigate('workout')}>
              Start training <span className="arrow">→</span>
            </button>
            <button className="btn ghost" onClick={() => onNavigate('workout')}
                    style={{ color: '#fff', borderColor: 'oklch(35% 0.005 100)' }}>
              Bekijk plan
            </button>
            <div style={{ marginLeft: 'auto', textAlign: 'right' }}>
              <div className="mono" style={{ fontSize: 10, color: 'oklch(70% 0.01 100)',
                textTransform: 'uppercase', letterSpacing: '.14em' }}>Geschatte duur</div>
              <div className="mono" style={{ fontSize: 24, fontWeight: 500, color: '#fff',
                marginTop: 4, fontVariantNumeric: 'tabular-nums' }}>
                {rec.duration} min
              </div>
            </div>
          </div>
        </div>

        {/* Right: recovery ring */}
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
          <div className="ring-wrap dark" style={{ width: 184, height: 184 }}>
            <svg width="184" height="184">
              <circle cx="92" cy="92" r="80" className="ring-bg"
                      style={{ stroke: 'oklch(25% 0.005 100)', strokeWidth: 12 }} />
              <circle cx="92" cy="92" r="80" className={`ring-fg ${ringClass}`}
                      style={{ strokeWidth: 12, strokeDasharray: 2 * Math.PI * 80,
                                strokeDashoffset: 2 * Math.PI * 80 * (1 - ringPct) }} />
            </svg>
            <div className="ring-center">
              <div className="ring-num" style={{ color: '#fff', fontSize: 56 }}>
                {score}<em>/6</em>
              </div>
              <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10,
                            textTransform: 'uppercase', letterSpacing: '.16em',
                            color: 'var(--accent)', marginTop: 6 }}>
                {FC.recoveryLabel(score)}
              </div>
            </div>
          </div>
          <div style={{ textAlign: 'center', maxWidth: 220 }}>
            <div style={{ color: 'oklch(78% 0.01 100)', fontSize: 13, lineHeight: 1.5 }}>
              {FC.recoveryAdvice(score)}
            </div>
            <button className="btn ghost" onClick={() => onNavigate('profiel')}
                    style={{ marginTop: 10, color: 'var(--accent)', borderColor: 'transparent',
                              padding: '6px 0' }}>
              Herstel in profiel <span className="mono">→</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function WorkoutStrip({ type, draftWorkout }) {
  // Stylised structure block to make the workout tangible.
  // Just visual rhythm — not exact zones.
  const draftBlocks = Array.isArray(draftWorkout?.blocks) && draftWorkout.blocks.length
    ? draftWorkout.blocks.map((block) => [block.short || block.label || 'Blok', Math.max(0.5, (block.sec || 0) / 60), zoneNumber(block.zone)])
    : null;
  const blocks = draftBlocks || {
    HERSTEL:   [['WU', 5, 1], ['Easy', 30, 2], ['CD', 5, 1]],
    DUUR:      [['WU', 8, 1], ['Zone 2', 45, 2], ['CD', 7, 1]],
    THRESHOLD: [['WU', 10, 1], ['Tempo', 12, 4], ['Rust', 4, 1], ['Tempo', 12, 4], ['CD', 8, 1]],
    VO2MAX:    [['WU', 12, 1], ['VO2', 3, 5], ['Rust', 3, 1], ['VO2', 3, 5], ['Rust', 3, 1], ['VO2', 3, 5], ['Rust', 3, 1], ['VO2', 3, 5], ['Rust', 3, 1], ['VO2', 3, 5], ['Rust', 3, 1], ['VO2', 3, 5], ['CD', 8, 1]],
    SPRINT:    [['WU', 10, 1], ...Array(10).fill(0).flatMap((_, i) => [['Sprint', 0.5, 6], ['Walk', 1.5, 1]]), ['CD', 8, 1]],
  }[type] || [['WU', 8, 1], ['Main', 40, 3], ['CD', 7, 1]];
  const total = blocks.reduce((s, b) => s + b[1], 0);

  return (
    <div style={{ background: 'var(--dark-2)', borderRadius: 12, padding: 14 }}>
      <div className="mono" style={{ fontSize: 10, color: 'oklch(70% 0.01 100)',
        textTransform: 'uppercase', letterSpacing: '.14em', marginBottom: 10 }}>
        Sessie structuur
      </div>
      <div style={{ display: 'flex', gap: 2, height: 36, alignItems: 'stretch' }}>
        {blocks.map((b, i) => {
          const intensity = b[2]; // 1-6
          const colors = ['', 'oklch(35% 0.005 100)', 'oklch(50% 0.06 200)',
                         'oklch(60% 0.10 145)', 'oklch(72% 0.16 100)',
                         'oklch(78% 0.19 60)', 'oklch(68% 0.22 25)'];
          return (
            <div key={i}
              title={`${b[0]} · ${b[1]} min`}
              style={{
                flex: b[1] / total,
                background: colors[intensity],
                borderRadius: 3,
                minWidth: 2,
              }} />
          );
        })}
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 8 }}>
        <span className="mono" style={{ fontSize: 10, color: 'oklch(70% 0.01 100)' }}>
          0 min
        </span>
        <span className="mono" style={{ fontSize: 10, color: 'oklch(70% 0.01 100)' }}>
          {Math.round(total)} min
        </span>
      </div>
    </div>
  );
}

function dashboardRecommendationFromDraft(draftWorkout, recoveryScore) {
  const base = window.FC_DATA.recommendedByRecovery[recoveryScore] || window.FC_DATA.recommendedByRecovery[4];
  if (!draftWorkout || !window.FC_WORKOUT_PLAN) return base;
  const fallbackByType = Object.values(window.FC_DATA.recommendedByRecovery)
    .find((item) => item.type === draftWorkout.type) || base;
  const duration = draftWorkout.durationMin
    || Math.round((draftWorkout.blocks || []).reduce((sum, block) => sum + (block.sec || 0), 0) / 60)
    || fallbackByType.duration;
  return {
    ...fallbackByType,
    type: draftWorkout.type || fallbackByType.type,
    dutch: window.FC_WORKOUT_PLAN.typeLabel(draftWorkout.type) || fallbackByType.dutch,
    sport: window.FC_WORKOUT_PLAN.sportLabel(draftWorkout.sportType) || fallbackByType.sport,
    duration,
    desc: descriptionForDraft(draftWorkout, fallbackByType),
  };
}

function descriptionForDraft(draftWorkout, fallback) {
  if (draftWorkout?.note && draftWorkout.source === 'coach') return draftWorkout.note;
  if (draftWorkout?.type === 'THRESHOLD') return 'Drempeltraining op basis van je huidige coachvoorstel.';
  if (draftWorkout?.type === 'DUUR') return 'Comfortabele duurtraining in zone 2.';
  if (draftWorkout?.type === 'HERSTEL') return 'Rustige herstelsessie met lage belasting.';
  if (draftWorkout?.type === 'VO2MAX') return 'Korte intensieve blokken met volledig herstel.';
  if (draftWorkout?.type === 'SPRINT') return 'Korte sprintprikkels met ruime pauzes.';
  return fallback.desc;
}

function zoneNumber(zone) {
  const match = String(zone || '').match(/\d+/);
  return match ? Number(match[0]) : 2;
}

function MetricStat({ label, value, unit, sub, ring, ringClass }) {
  return (
    <div className="card">
      <span className="label">{label}</span>
      <div style={{ display: 'flex', alignItems: 'end', justifyContent: 'space-between', marginTop: 6 }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 2 }}>
            <span className="stat-big mono">{value}</span>
            <span className="stat-unit">{unit}</span>
          </div>
          {sub && <div className="mono" style={{ fontSize: 11, color: 'var(--ink-4)', marginTop: 6 }}>{sub}</div>}
        </div>
        {ring !== undefined && (
          <div style={{ position: 'relative', width: 52, height: 52 }}>
            <svg width="52" height="52" style={{ transform: 'rotate(-90deg)' }}>
              <circle cx="26" cy="26" r="22" fill="none" stroke="oklch(92% 0.005 100)" strokeWidth="5" />
              <circle cx="26" cy="26" r="22" fill="none"
                stroke={ringClass === 'bad' ? 'var(--bad)' : ringClass === 'warn' ? 'var(--warn)' : 'var(--accent)'}
                strokeWidth="5" strokeLinecap="round"
                strokeDasharray={2 * Math.PI * 22}
                strokeDashoffset={2 * Math.PI * 22 * (1 - ring)} />
            </svg>
          </div>
        )}
      </div>
    </div>
  );
}

function WeekChart({ weeklyTrend, weekSummary, analysis, allowDemo }) {
  const trend = (weeklyTrend && weeklyTrend.length) ? weeklyTrend : (allowDemo ? window.FC_DATA.weeklyTrend : []);
  const summary = weekSummary || (allowDemo ? window.FC_DATA.weeklySummary : { duration_hours: 0, duration_seconds: 0 });
  const delta = analysis?.deltas?.duration_percent;
  const max = trend.length ? Math.max(...trend.map(w => w.duration_hours || (w.duration_seconds || 0) / 3600)) : 1;
  return (
    <div className="card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', marginBottom: 18 }}>
        <div>
          <h2>Wekelijkse belasting</h2>
          <div className="mono" style={{ fontSize: 11, color: 'var(--ink-4)', marginTop: 4,
            textTransform: 'uppercase', letterSpacing: '.14em' }}>
            6 weken · uren training
          </div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div className="mono" style={{ fontSize: 28, fontWeight: 500, letterSpacing: '-.02em' }}>
            {(summary.duration_hours ?? (summary.duration_seconds || 0)/3600).toFixed(1)}
            <span style={{ fontSize: 14, color: 'var(--ink-4)', marginLeft: 4 }}>u</span>
          </div>
          {delta != null && (
            <div className="mono" style={{ fontSize: 11,
              color: delta < 0 ? 'var(--bad)' : 'var(--good)',
              textTransform: 'uppercase', letterSpacing: '.1em', marginTop: 2 }}>
              {delta > 0 ? '+' : ''}{Math.round(delta)}% vs basislijn
            </div>
          )}
        </div>
      </div>

      {!trend.length ? (
        <div style={{ height: 140, display: 'flex', alignItems: 'center', justifyContent: 'center',
          border: '1px dashed var(--line)', borderRadius: 10, color: 'var(--ink-4)', fontSize: 13 }}>
          Nog geen live weekdata beschikbaar.
        </div>
      ) : (
      <div style={{ display: 'flex', alignItems: 'end', gap: 14, height: 140,
                    padding: '0 4px', borderBottom: '1px solid var(--line)' }}>
        {trend.map((w, i) => {
          const hours = w.duration_hours ?? (w.duration_seconds || 0) / 3600;
          const h = (hours / (max || 1)) * 130;
          const isLast = i === trend.length - 1;
          return (
            <div key={w.week_start} style={{ flex: 1, display: 'flex',
                  flexDirection: 'column', alignItems: 'center', gap: 6 }}>
              <div className="mono" style={{ fontSize: 10, color: 'var(--ink-4)',
                  fontVariantNumeric: 'tabular-nums' }}>{hours.toFixed(1)}</div>
              <div className={`bar ${isLast ? 'accent' : ''}`}
                   style={{ width: '70%', height: h, position: 'relative' }} />
            </div>
          );
        })}
      </div>
      )}
      {!!trend.length && <div style={{ display: 'flex', gap: 14, marginTop: 8, padding: '0 4px' }}>
        {trend.map((w) => (
          <div key={w.week_start} className="mono" style={{ flex: 1, textAlign: 'center',
                fontSize: 10, color: 'var(--ink-4)', textTransform: 'uppercase',
                letterSpacing: '.1em' }}>
            {new Date(w.week_start).toLocaleDateString('nl-BE', { day: '2-digit', month: 'short' }).replace('.', '')}
          </div>
        ))}
      </div>}
    </div>
  );
}

function CoachInsight({ onNavigate, analysis, allowDemo }) {
  const a = analysis || (allowDemo ? window.FC_DATA.weeklyAnalysis : {});
  return (
    <div className="card" style={{ background: 'var(--bg-soft)', borderColor: 'transparent' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
        <span className="label">Coach insight</span>
        <span style={{ width: 4, height: 4, borderRadius: 999, background: 'var(--ink-4)' }}></span>
        <span className="mono" style={{ fontSize: 10, color: 'var(--ink-4)',
          textTransform: 'uppercase', letterSpacing: '.14em' }}>nu</span>
      </div>
      <p style={{ fontSize: 16, lineHeight: 1.5, margin: 0 }}>
        {a.summary || 'Nog geen live weekanalyse beschikbaar.'}
      </p>
      <div style={{ height: 1, background: 'var(--line)', margin: '18px 0' }}></div>
      <div className="mono" style={{ fontSize: 10, color: 'var(--ink-4)',
        textTransform: 'uppercase', letterSpacing: '.14em', marginBottom: 6 }}>
        Advies
      </div>
      <p style={{ fontSize: 14, lineHeight: 1.5, margin: 0, color: 'var(--ink-2)' }}>
        {a.insight || 'Zodra Garmin-data geladen is, geef ik hier een concreet advies.'}
      </p>
      <button className="btn" onClick={() => window.dispatchEvent(new CustomEvent('fc-open-coach-orb'))}
              style={{ marginTop: 18, width: '100%', justifyContent: 'center' }}>
        Bespreek met coach <span className="arrow">→</span>
      </button>
    </div>
  );
}

function RecentActivities({ onNavigate, activities, source }) {
  const D = window.FC_DATA;
  const list = (activities && activities.length) ? activities : D.activities;
  return (
    <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between',
                    alignItems: 'center', padding: '20px 24px 8px' }}>
        <h2>Recente activiteiten</h2>
        <button className="btn ghost" onClick={() => onNavigate('activities')}
                style={{ padding: '6px 0' }}>
          Alles bekijken <span className="mono">→</span>
        </button>
      </div>
      <table className="fc" style={{ marginTop: 6 }}>
        <thead>
          <tr>
            <th style={{ paddingLeft: 24 }}>Sport</th>
            <th>Naam</th>
            <th>Datum</th>
            <th style={{ textAlign: 'right' }}>Afstand</th>
            <th style={{ textAlign: 'right' }}>Duur</th>
            <th style={{ textAlign: 'right' }}>Avg HR</th>
            <th style={{ paddingRight: 24, textAlign: 'right' }}>Tempo</th>
          </tr>
        </thead>
        <tbody>
          {list.slice(0, 5).map((a) => (
            <tr key={a.id} className="hover" onClick={() => onNavigate('workout')}>
              <td style={{ paddingLeft: 24 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <div style={{ width: 28, height: 28, borderRadius: 8,
                                background: 'var(--bg-soft)', display: 'flex',
                                alignItems: 'center', justifyContent: 'center',
                                fontFamily: "'JetBrains Mono', monospace",
                                fontWeight: 700, fontSize: 13 }}>
                    {FC.sportIcon(a.activity_type)}
                  </div>
                  <span style={{ fontWeight: 500 }}>{FC.sportLabel(a.activity_type)}</span>
                </div>
              </td>
              <td>{a.activity_name}</td>
              <td className="mono" style={{ color: 'var(--ink-3)' }}>
                {FC.fmtDate(a.start_time)} · {FC.fmtTime(a.start_time)}
              </td>
              <td className="mono" style={{ textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                {(a.distance_meters / 1000).toFixed(1)} km
              </td>
              <td className="mono" style={{ textAlign: 'right' }}>{FC.fmtDuration(a.duration_seconds)}</td>
              <td className="mono" style={{ textAlign: 'right' }}>{a.average_heart_rate}</td>
              <td className="mono" style={{ textAlign: 'right', paddingRight: 24, color: 'var(--ink-3)' }}>
                {a.activity_type === 'RUNNING' ? FC.fmtPace(a.distance_meters, a.duration_seconds) : '–'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

window.Dashboard = Dashboard;
