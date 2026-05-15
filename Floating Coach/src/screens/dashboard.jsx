// Dashboard — today overview + hero workout generator + live HR.
const { useEffect: useEffectD, useState: useStateD } = React;
const FC = window.FC_UTILS;

function Dashboard({ recoveryScore, onNavigate, apiStatus, userId }) {
  const D = window.FC_DATA;
  const online = apiStatus === 'online';
  const rec = D.recommendedByRecovery[recoveryScore] || D.recommendedByRecovery[4];

  // Live data — falls back to mock when offline / no user / API error.
  const activitiesQuery = window.useLiveData(
    (uid) => window.FC_API.fetchGarminActivities(uid, 10, 7),
    { activities: D.activities, weekly_trend: D.weeklyTrend, summary: D.weeklySummary },
    [],
    { online, userId },
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
    { online, userId },
  );

  const activities = activitiesQuery.data.activities || D.activities;
  const weeklyTrend = activitiesQuery.data.weekly_trend || D.weeklyTrend;
  const weekSummary = weeklyQuery.data.current_week || D.weeklySummary;
  const analysis = weeklyQuery.data;
  const source = (activitiesQuery.source === 'live' && weeklyQuery.source === 'live') ? 'live' : 'demo';
  const ringPct = (recoveryScore / 6);
  const ringClass = recoveryScore <= 2 ? 'bad' : recoveryScore <= 3 ? 'warn' : '';

  // Live HR ticker
  const [hr, setHr] = useStateD(72);
  const [hrHist, setHrHist] = useStateD(D.hrStream);
  useEffectD(() => {
    const t = setInterval(() => {
      setHrHist((arr) => {
        const last = arr[arr.length - 1];
        const next = Math.max(58, Math.min(96, last + (Math.random() - 0.5) * 6));
        const v = Math.round(next);
        setHr(v);
        return [...arr.slice(1), v];
      });
    }, 700);
    return () => clearInterval(t);
  }, []);

  // Animated clock
  const [now, setNow] = useStateD(new Date());
  useEffectD(() => {
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="col" style={{ gap: 24 }} data-screen-label="Dashboard">
      {/* Head */}
      <div className="screen-head">
        <div>
          <div className="label" style={{ marginBottom: 10 }}>
            <span style={{ color: 'var(--ink)' }}>{FC.fmtDayName(D.today.toISOString())}</span>
            {' · '}{D.today.toLocaleDateString('nl-BE', { day: '2-digit', month: 'long' })}
          </div>
          <h1>Goedemorgen, {D.user.firstName}.<br/>
              <em>Vandaag voel je je </em><span style={{ color: 'var(--ink)' }}>{FC.recoveryLabel(recoveryScore).toLowerCase()}</span><em>.</em>
          </h1>
        </div>
        <div className="meta">
          <div className="mono" style={{ fontSize: 13, color: 'var(--ink)', fontWeight: 500, letterSpacing: '-.01em' }}>
            {now.toLocaleTimeString('nl-BE', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
          </div>
          <div style={{ marginTop: 4 }}>Antwerpen · 14°C bewolkt</div>
        </div>
      </div>

      {/* Live/demo banner — surfaces when API errored */}
      {activitiesQuery.error && (
        <div className="card" style={{ background: 'oklch(96% 0.04 60)', borderColor: 'oklch(85% 0.08 60)',
          padding: '12px 16px', display: 'flex', alignItems: 'center', gap: 12 }}>
          <span className="live-dot" style={{ background: 'oklch(72% 0.16 60)' }}></span>
          <div style={{ flex: 1, fontSize: 13, color: 'oklch(35% 0.10 50)' }}>
            <b>Demo data getoond.</b> Backend onbereikbaar:
            <span className="mono" style={{ marginLeft: 6, fontSize: 12 }}>{activitiesQuery.error}</span>
          </div>
          <button className="btn ghost" style={{ padding: '6px 12px', fontSize: 12 }}
                  onClick={activitiesQuery.refetch}>
            Opnieuw <span className="mono">↻</span>
          </button>
        </div>
      )}

      {/* Hero workout card */}
      <HeroWorkout rec={rec} score={recoveryScore} onNavigate={onNavigate} />

      {/* Metric strip */}
      <div className="grid-4">
        <MetricLive label="Hartslag nu" value={Math.round(hr)} unit="bpm" hist={hrHist} live />
        <MetricStat label="Recovery" value={recoveryScore} unit="/6" ring={ringPct} ringClass={ringClass} />
        <MetricStat label="Body Battery" value={D.recovery.bodyBattery} unit="%" sub={`HRV ${D.recovery.hrvOvernight}ms`} />
        <MetricStat label="Sleep score" value={D.recovery.sleepScore} unit="" sub={`${D.recovery.sleepHours.toFixed(1)}u slaap`} />
      </div>

      {/* Week + recent */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: 20 }}>
        <WeekChart weeklyTrend={weeklyTrend} weekSummary={weekSummary} analysis={analysis} />
        <CoachInsight onNavigate={onNavigate} analysis={analysis} />
      </div>

      <RecentActivities onNavigate={onNavigate} activities={activities} source={source} />
    </div>
  );
}

function HeroWorkout({ rec, score, onNavigate }) {
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
          </p>

          {/* Workout structure mini-strip */}
          <WorkoutStrip type={rec.type} />

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
            <button className="btn ghost" onClick={() => onNavigate('recovery')}
                    style={{ marginTop: 10, color: 'var(--accent)', borderColor: 'transparent',
                              padding: '6px 0' }}>
              Volledig herstelrapport <span className="mono">→</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function WorkoutStrip({ type }) {
  // Stylised structure block to make the workout tangible.
  // Just visual rhythm — not exact zones.
  const blocks = {
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

function MetricLive({ label, value, unit, hist, live }) {
  // Sparkline from hist
  const w = 240, h = 36;
  const min = Math.min(...hist), max = Math.max(...hist);
  const range = max - min || 1;
  const path = hist.map((v, i) => {
    const x = (i / (hist.length - 1)) * w;
    const y = h - ((v - min) / range) * h;
    return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');

  return (
    <div className="card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start' }}>
        <span className="label">{label}</span>
        {live && (
          <span className="mono" style={{ fontSize: 10, color: 'var(--bad)',
            textTransform: 'uppercase', letterSpacing: '.14em', display: 'flex',
            alignItems: 'center', gap: 6 }}>
            <span className="live-dot"></span> LIVE
          </span>
        )}
      </div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 4, marginTop: 6 }}>
        <span className="stat-big mono">{value}</span>
        <span className="stat-unit">{unit}</span>
      </div>
      <svg viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none"
           style={{ width: '100%', height: 36, marginTop: 8, display: 'block' }}>
        <path d={path} fill="none" stroke="var(--accent)" strokeWidth="1.8" strokeLinecap="round" />
      </svg>
    </div>
  );
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

function WeekChart({ weeklyTrend, weekSummary, analysis }) {
  const trend = (weeklyTrend && weeklyTrend.length) ? weeklyTrend : window.FC_DATA.weeklyTrend;
  const summary = weekSummary || window.FC_DATA.weeklySummary;
  const delta = analysis?.deltas?.duration_percent;
  const max = Math.max(...trend.map(w => w.duration_hours || (w.duration_seconds || 0) / 3600));
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
      <div style={{ display: 'flex', gap: 14, marginTop: 8, padding: '0 4px' }}>
        {trend.map((w) => (
          <div key={w.week_start} className="mono" style={{ flex: 1, textAlign: 'center',
                fontSize: 10, color: 'var(--ink-4)', textTransform: 'uppercase',
                letterSpacing: '.1em' }}>
            {new Date(w.week_start).toLocaleDateString('nl-BE', { day: '2-digit', month: 'short' }).replace('.', '')}
          </div>
        ))}
      </div>
    </div>
  );
}

function CoachInsight({ onNavigate, analysis }) {
  const a = analysis || window.FC_DATA.weeklyAnalysis;
  return (
    <div className="card" style={{ background: 'var(--bg-soft)', borderColor: 'transparent' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
        <span className="label">Coach insight</span>
        <span style={{ width: 4, height: 4, borderRadius: 999, background: 'var(--ink-4)' }}></span>
        <span className="mono" style={{ fontSize: 10, color: 'var(--ink-4)',
          textTransform: 'uppercase', letterSpacing: '.14em' }}>nu</span>
      </div>
      <p style={{ fontSize: 16, lineHeight: 1.5, margin: 0 }}>
        {a.summary || window.FC_DATA.weeklyAnalysis.summary}
      </p>
      <div style={{ height: 1, background: 'var(--line)', margin: '18px 0' }}></div>
      <div className="mono" style={{ fontSize: 10, color: 'var(--ink-4)',
        textTransform: 'uppercase', letterSpacing: '.14em', marginBottom: 6 }}>
        Advies
      </div>
      <p style={{ fontSize: 14, lineHeight: 1.5, margin: 0, color: 'var(--ink-2)' }}>
        {a.insight || window.FC_DATA.weeklyAnalysis.insight}
      </p>
      <button className="btn" onClick={() => onNavigate('chat')}
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
