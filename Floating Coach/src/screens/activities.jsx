// Activities — list + trends, mirrors webapp/src/app/activities/page.tsx data shapes.
const { useState: useStateA, useMemo: useMemoA } = React;
const FCUA = window.FC_UTILS;

function ActivitiesScreen({ onNavigate, apiStatus, userId }) {
  const D = window.FC_DATA;
  const online = apiStatus === 'online';
  const [period, setPeriod] = useStateA(30);
  const [sportFilter, setSportFilter] = useStateA('ALL');

  const q = window.useLiveData(
    (uid) => window.FC_API.fetchGarminActivities(uid, 500, period),
    {
      activities: D.activities,
      weekly_trend: D.weeklyTrend,
      summary: {
        sessions: D.weeklySummary.sessions,
        distance_km: D.weeklySummary.distance_km,
        duration_hours: D.weeklySummary.duration_hours,
        average_heart_rate: D.weeklySummary.average_heart_rate,
        longest_session_minutes: D.weeklySummary.longest_session_minutes,
        running_sessions: D.weeklySummary.running_sessions,
        cycling_sessions: D.weeklySummary.cycling_sessions,
        max_heart_rate: D.weeklySummary.max_heart_rate,
      },
      period_days: period,
    },
    [period],
    { online, userId, cacheKey: `activities_${period}`, emptyData: { activities: [], weekly_trend: [], summary: null, period_days: period } },
  );
  const profileQuery = window.useLiveData(
    (uid) => window.FC_API.fetchTrainingProfile(uid, 120, 7),
    { personal_targets: {}, sport_baselines: {} },
    [],
    { online, userId, cacheKey: 'training_profile', emptyData: { personal_targets: {}, sport_baselines: {} } },
  );
  const allActivities = q.data.activities || (!userId ? D.activities : []);
  const weeklyTrend  = q.data.weekly_trend || (!userId ? D.weeklyTrend : []);
  const apiSummary   = q.data.summary;
  const displaySummary = sportFilter === 'ALL' ? apiSummary : null;
  const selectedBaseline = profileQuery.data.sport_baselines?.[canonicalSportFilter(sportFilter)] || null;

  const filtered = useMemoA(() => {
    return allActivities.filter(a => sportFilter === 'ALL' || canonicalActivityType(a) === sportFilter);
  }, [sportFilter, allActivities]);

  const totals = useMemoA(() => {
    const acc = { sessions: 0, distance: 0, duration: 0, hr: 0, hrn: 0, runs: 0, rides: 0, longest: 0, maxHr: 0 };
    filtered.forEach(a => {
      acc.sessions++;
      acc.distance += a.distance_meters || 0;
      acc.duration += a.duration_seconds || 0;
      acc.longest = Math.max(acc.longest, (a.duration_seconds || 0) / 60);
      acc.maxHr = Math.max(acc.maxHr, a.max_heart_rate || 0);
      if (a.average_heart_rate) { acc.hr += a.average_heart_rate; acc.hrn++; }
      if (a.activity_type === 'RUNNING') acc.runs++;
      if (a.activity_type === 'CYCLING') acc.rides++;
    });
    return {
      sessions: acc.sessions,
      distance_km: acc.distance / 1000,
      duration_hours: acc.duration / 3600,
      avg_hr: acc.hrn ? Math.round(acc.hr / acc.hrn) : null,
      longest_min: Math.round(acc.longest),
      max_hr: acc.maxHr || null,
      runs: acc.runs,
      rides: acc.rides,
    };
  }, [filtered]);

  return (
    <div data-screen-label="Activities" className="col" style={{ gap: 24 }}>
      <div className="screen-head">
        <div>
          <div className="label" style={{ marginBottom: 10 }}>Sessies & trends</div>
          <h1>Activiteiten.<br/><em>Laatste {period} dagen.</em></h1>
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          {[7, 30].map(d => (
            <button key={d} onClick={() => setPeriod(d)}
              className={period === d ? 'btn' : 'btn ghost'}
              style={{ padding: '10px 16px', fontSize: 12 }}>
              {d}d
            </button>
          ))}
        </div>
      </div>

      {/* Error banner */}
      {q.error && (
        <div className="card" style={{ background: 'oklch(96% 0.04 60)', borderColor: 'oklch(85% 0.08 60)',
          padding: '12px 16px', display: 'flex', alignItems: 'center', gap: 12 }}>
          <span className="live-dot" style={{ background: 'oklch(72% 0.16 60)' }}></span>
          <div style={{ flex: 1, fontSize: 13, color: 'oklch(35% 0.10 50)' }}>
            <b>Demo data getoond.</b>
            <span className="mono" style={{ marginLeft: 6, fontSize: 12 }}>{q.error}</span>
          </div>
          <button className="btn ghost" style={{ padding: '6px 12px', fontSize: 12 }} onClick={q.refetch}>
            Opnieuw <span className="mono">↻</span>
          </button>
        </div>
      )}

      {/* Summary */}
      <div className="grid-4">
        <BigStat label="Sessies" value={(displaySummary?.sessions ?? totals.sessions)} unit="" hint="Aantal opgeslagen trainingen in deze periode." />
        <BigStat label="Afstand" value={(displaySummary?.distance_km ?? totals.distance_km).toFixed(1)} unit="km" hint="Totale afstand over de zichtbare sessies." />
        <BigStat label="Trainingstijd" value={(displaySummary?.duration_hours ?? totals.duration_hours).toFixed(1)} unit="u" hint="Totale actieve duur, niet inclusief rustdagen." />
        <BigStat label="Gem. hartslag" value={(displaySummary?.average_heart_rate ?? totals.avg_hr) ?? '–'} unit="bpm" hint="Gemiddelde van de sessie-gemiddelden." />
      </div>

      {/* Trend insight + breakdown */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: 20 }}>
        <TrendCard weeklyTrend={weeklyTrend} activities={allActivities} period={period}
          sportFilter={sportFilter} sportBaseline={selectedBaseline} />
        <SportBreakdown allActivities={allActivities} sportFilter={sportFilter} setSportFilter={setSportFilter} />
      </div>

      {/* Wekelijkse tabel */}
      <div className="card">
        <h2 style={{ marginBottom: 18 }}>Wekelijkse trend</h2>
        <table className="fc">
          <thead>
            <tr>
              <th>Week start</th>
              <th style={{ textAlign: 'right' }}>Sessies</th>
              <th style={{ textAlign: 'right' }}>Afstand</th>
              <th style={{ textAlign: 'right' }}>Duur</th>
              <th style={{ textAlign: 'right' }}>Gem. HR</th>
              <th style={{ width: 140 }}>Volume</th>
            </tr>
          </thead>
          <tbody>
            {weeklyTrend.map((w, i) => {
              const hours = w.duration_hours ?? (w.duration_seconds || 0)/3600;
              const max = Math.max(...weeklyTrend.map(x => x.duration_hours ?? (x.duration_seconds || 0)/3600));
              const pct = hours / (max || 1);
              const isLast = i === weeklyTrend.length - 1;
              return (
                <tr key={w.week_start}>
                  <td className="mono">{new Date(w.week_start).toLocaleDateString('nl-BE', { day: '2-digit', month: 'short' }).replace('.', '')}</td>
                  <td className="mono" style={{ textAlign: 'right' }}>{w.sessions}</td>
                  <td className="mono" style={{ textAlign: 'right' }}>{(w.distance_km ?? 0).toFixed(1)} km</td>
                  <td className="mono" style={{ textAlign: 'right' }}>{hours.toFixed(1)} u</td>
                  <td className="mono" style={{ textAlign: 'right' }}>{w.average_heart_rate ?? '–'}</td>
                  <td>
                    <div style={{ height: 6, background: 'var(--bg-soft)', borderRadius: 4 }}>
                      <div style={{
                        height: '100%', width: `${pct * 100}%`,
                        background: isLast ? 'var(--accent)' : 'var(--ink)',
                        borderRadius: 4
                      }}></div>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Activity detail table */}
      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <div style={{ padding: '20px 24px 8px', display: 'flex',
                      justifyContent: 'space-between', alignItems: 'center' }}>
          <h2>Activiteit details</h2>
          <span className="mono" style={{ fontSize: 11, color: 'var(--ink-4)',
            textTransform: 'uppercase', letterSpacing: '.14em' }}>
            {filtered.length} van {allActivities.length} sessies
          </span>
        </div>
        <table className="fc">
          <thead>
            <tr>
              <th style={{ paddingLeft: 24 }}>Sport</th>
              <th>Naam</th>
              <th>Datum</th>
              <th style={{ textAlign: 'right' }}>Afstand</th>
              <th style={{ textAlign: 'right' }}>Duur</th>
              <th style={{ textAlign: 'right' }}>Avg / Max HR</th>
              <th style={{ textAlign: 'right' }}>Cal</th>
              <th style={{ paddingRight: 24, textAlign: 'right' }}>Tempo</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 && (
              <tr>
                <td colSpan="8" style={{ padding: '28px 24px', color: 'var(--ink-3)' }}>
                  Geen sessies voor deze filter en periode.
                </td>
              </tr>
            )}
            {filtered.map((a) => (
              <tr key={a.id} className="hover" onClick={() => onNavigate('workout')}>
                <td style={{ paddingLeft: 24 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <div style={{ width: 28, height: 28, borderRadius: 8,
                                  background: 'var(--bg-soft)', display: 'flex',
                                  alignItems: 'center', justifyContent: 'center',
                                  fontFamily: "'JetBrains Mono', monospace",
                                  fontWeight: 700, fontSize: 13 }}>
                      {FCUA.sportIcon(a.activity_type)}
                    </div>
                    <span style={{ fontWeight: 500, fontSize: 13 }}>{FCUA.sportLabel(a.activity_type)}</span>
                  </div>
                </td>
                <td style={{ fontSize: 14 }}>{a.activity_name}</td>
                <td className="mono" style={{ color: 'var(--ink-3)', fontSize: 12 }}>
                  {FCUA.fmtDate(a.start_time)} · {FCUA.fmtTime(a.start_time)}
                </td>
                <td className="mono" style={{ textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                  {(a.distance_meters / 1000).toFixed(1)} km
                </td>
                <td className="mono" style={{ textAlign: 'right' }}>{FCUA.fmtDuration(a.duration_seconds)}</td>
                <td className="mono" style={{ textAlign: 'right' }}>
                  <span>{a.average_heart_rate}</span>
                  <span style={{ color: 'var(--ink-4)' }}> / {a.max_heart_rate}</span>
                </td>
                <td className="mono" style={{ textAlign: 'right' }}>{a.calories}</td>
                <td className="mono" style={{ textAlign: 'right', paddingRight: 24, color: 'var(--ink-3)' }}>
                  {a.activity_type === 'RUNNING' ? FCUA.fmtPace(a.distance_meters, a.duration_seconds) : '–'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function BigStat({ label, value, unit, hint }) {
  return (
    <div className="card">
      <span className="label">{label}</span>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 4, marginTop: 8 }}>
        <span className="stat-big mono">{value}</span>
        {unit && <span className="stat-unit">{unit}</span>}
      </div>
      {hint && (
        <div style={{ marginTop: 8, fontSize: 12, lineHeight: 1.4, color: 'var(--ink-4)' }}>
          {hint}
        </div>
      )}
    </div>
  );
}

function canonicalSportFilter(filter) {
  if (filter === 'INDOOR_CYCLING') return 'INDOOR_CYCLING';
  if (filter === 'LAP_SWIMMING') return 'SWIMMING';
  if (filter === 'CARDIO_TRAINING') return 'WALKING';
  return filter;
}

function canonicalActivityType(activity) {
  const type = String(activity.activity_type || '').toUpperCase();
  const name = String(activity.activity_name || '').toLowerCase();
  const rawType = String(activity.raw_data?.activityType || '').toUpperCase();
  const combined = `${type} ${rawType} ${name}`;
  if (combined.includes('SWIM')) return 'LAP_SWIMMING';
  if ((combined.includes('INDOOR') || combined.includes('ZWIFT') || combined.includes('VIRTUAL')) &&
      (combined.includes('CYCLE') || combined.includes('BIKE') || combined.includes('CYCLING'))) return 'INDOOR_CYCLING';
  if (combined.includes('CYCLE') || combined.includes('BIKE') || combined.includes('CYCLING')) return 'CYCLING';
  if (combined.includes('WALK') || combined.includes('WANDEL') || type === 'CARDIO_TRAINING') return 'CARDIO_TRAINING';
  if (combined.includes('RUN')) return 'RUNNING';
  return type || 'UNKNOWN';
}

function sportScopeLabel(filter) {
  const canonical = canonicalSportFilter(filter);
  return ({
    ALL: 'alle sporten samen',
    RUNNING: 'hardlopen',
    WALKING: 'wandelen',
    CYCLING: 'fietsen',
    INDOOR_CYCLING: 'indoor fietsen',
    SWIMMING: 'zwemmen',
  })[canonical] || String(filter || '').toLowerCase();
}

function TrendCard({ weeklyTrend, activities, period, sportFilter, sportBaseline }) {
  // Compute deltas client-side from the trend if available
  const trend = (weeklyTrend && weeklyTrend.length) ? weeklyTrend : window.FC_DATA.weeklyTrend;
  const split = Math.ceil(trend.length / 2);
  const a = trend.slice(0, split), b = trend.slice(split);
  const avg = (vs) => vs.length ? vs.reduce((s,v)=>s+v,0)/vs.length : 0;
  const dur = (vs, key) => vs.map((w) => w[key] ?? (key==='duration_hours' ? (w.duration_seconds||0)/3600 : 0));
  const baselineDeltas = sportBaseline?.deltas;
  const dDur = baselineDeltas?.duration_percent ?? (a.length && b.length ? ((avg(dur(b,'duration_hours')) - avg(dur(a,'duration_hours'))) / (avg(dur(a,'duration_hours')) || 1)) * 100 : -34);
  const dDis = baselineDeltas?.distance_percent ?? (a.length && b.length ? ((avg(dur(b,'distance_km')) - avg(dur(a,'distance_km'))) / (avg(dur(a,'distance_km')) || 1)) * 100 : -29);
  const aHr = avg(a.map(w => w.average_heart_rate || 0).filter(Boolean));
  const bHr = avg(b.map(w => w.average_heart_rate || 0).filter(Boolean));
  const dHr = baselineDeltas?.avg_heart_rate_delta ?? (aHr && bHr ? bHr - aHr : -1);
  const fmt = (n) => `${n >= 0 ? '+' : ''}${n.toFixed(0)}%`;

  const list = (activities && activities.length) ? activities : [];
  const now = new Date();
  const daysAgo = (dateString) => {
    const t = new Date(dateString).getTime();
    return Number.isFinite(t) ? (now.getTime() - t) / 86400000 : Infinity;
  };
  const hoursFor = (items) => items.reduce((sum, item) => sum + ((item.duration_seconds || 0) / 3600), 0);
  const acuteHours = hoursFor(list.filter((item) => daysAgo(item.start_time) <= 7));
  const chronicBase = list.filter((item) => daysAgo(item.start_time) > 7 && daysAgo(item.start_time) <= 30);
  const chronicWeeklyHours = chronicBase.length ? hoursFor(chronicBase) / (23 / 7) : null;
  const loadRatio = sportBaseline?.load_ratio ?? (chronicWeeklyHours ? acuteHours / chronicWeeklyHours : null);
  const loadPct = Math.max(0, Math.min(100, ((loadRatio || 0) / 1.6) * 100));
  const loadLabel = !loadRatio
    ? 'nog niet genoeg data'
    : loadRatio < 0.75
      ? 'lage belasting'
      : loadRatio <= 1.25
        ? 'stabiele opbouw'
        : 'hoge sprong';
  const headline = period === 7
    ? `Recente belasting voor ${sportScopeLabel(sportFilter)}`
    : loadRatio && loadRatio > 1.25
      ? 'Belasting stijgt snel'
      : loadRatio && loadRatio < 0.75
        ? 'Belasting ligt lager dan je basis'
        : 'Belasting blijft in balans';
  const scopeText = sportFilter === 'ALL'
    ? 'alle sporten samen'
    : `alleen je ${sportScopeLabel(sportFilter)}sessies`;
  const baselineText = sportBaseline
    ? `Deze vergelijking gebruikt ${scopeText}: laatste 7 dagen tegenover je gemiddelde week uit de vorige 4 weken.`
    : 'Verhouding tussen je trainingstijd van de laatste 7 dagen en je normale weekvolume uit de weken ervoor.';

  return (
    <div className="card dark" style={{ position: 'relative', overflow: 'hidden' }}>
      <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 2,
                    background: 'var(--accent)' }} />
      <div style={{ display: 'flex', justifyContent: 'space-between',
                    alignItems: 'start', marginBottom: 24 }}>
        <div>
          <span className="label">Trendinzicht</span>
          <h2 style={{ marginTop: 10, color: '#fff' }}>{headline}</h2>
        </div>
        <span className="tag" style={{ background: 'oklch(35% 0.005 100)',
          color: 'oklch(85% 0.005 100)' }}>{period}d</span>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 20 }}>
        <DeltaStat label="Trainingstijd/week" delta={fmt(dDur)} sub={sportBaseline ? 'vs 4-weeks sportbasis' : 'tweede helft vs eerste helft'} trend={dDur < 0 ? 'down' : 'up'} />
        <DeltaStat label="Afstand/week" delta={fmt(dDis)} sub={sportBaseline ? 'vs 4-weeks sportbasis' : 'tweede helft vs eerste helft'} trend={dDis < 0 ? 'down' : 'up'} />
        <DeltaStat label="Hartslag" delta={`${dHr >= 0 ? '+' : ''}${dHr.toFixed(0)} bpm`} sub="gem. sessie-HR verschil" trend={Math.abs(dHr) < 2 ? 'flat' : (dHr < 0 ? 'down' : 'up')} />
      </div>

      <div style={{ height: 1, background: 'oklch(25% 0.005 100)', margin: '24px 0' }}></div>

      <div className="mono" style={{ fontSize: 10, color: 'oklch(70% 0.01 100)',
        textTransform: 'uppercase', letterSpacing: '.14em', marginBottom: 10 }}>
        Belasting vs 4-weeks gemiddelde
      </div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
        <div className="mono" style={{ fontSize: 36, fontWeight: 500,
          color: '#fff', letterSpacing: '-.02em' }}>
          {loadRatio ? loadRatio.toFixed(2) : '–'}
        </div>
        <div style={{ color: 'oklch(78% 0.16 60)', fontSize: 13 }}>
          {loadLabel}
        </div>
      </div>
      <p style={{ color: 'oklch(76% 0.01 100)', fontSize: 12, lineHeight: 1.45, margin: '8px 0 0' }}>
        {baselineText}
      </p>
      {/* Load gauge */}
      <div style={{ marginTop: 12, height: 8, borderRadius: 4, background: 'oklch(25% 0.005 100)',
                    position: 'relative', overflow: 'hidden' }}>
        <div style={{
          position: 'absolute', left: '40%', width: '20%', top: 0, bottom: 0,
          background: 'oklch(78% 0.19 125)', opacity: .4,
        }}></div>
        <div style={{
          position: 'absolute', left: '60%', width: '20%', top: 0, bottom: 0,
          background: 'oklch(75% 0.16 60)', opacity: .4,
        }}></div>
        <div style={{
          position: 'absolute', left: '80%', right: 0, top: 0, bottom: 0,
          background: 'oklch(67% 0.20 25)', opacity: .4,
        }}></div>
        <div style={{
          position: 'absolute', left: `${loadPct}%`, top: -3, bottom: -3, width: 3,
          background: 'var(--accent)', borderRadius: 2,
        }}></div>
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 8 }}>
        {['0.5', '0.8', '1.3', '1.5+'].map((v) => (
          <span key={v} className="mono" style={{ fontSize: 9,
            color: 'oklch(70% 0.01 100)' }}>{v}</span>
        ))}
      </div>
    </div>
  );
}

function DeltaStat({ label, delta, sub, trend }) {
  const arrow = trend === 'down' ? '↓' : trend === 'up' ? '↑' : '→';
  const color = trend === 'down' ? 'var(--bad)' : trend === 'up' ? 'var(--good)' : 'oklch(78% 0.16 60)';
  return (
    <div>
      <div className="mono" style={{ fontSize: 10, color: 'oklch(70% 0.01 100)',
        textTransform: 'uppercase', letterSpacing: '.14em' }}>
        {label}
      </div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, marginTop: 6 }}>
        <span className="mono" style={{ fontSize: 24, fontWeight: 500, color: '#fff',
          letterSpacing: '-.02em' }}>{delta}</span>
        <span className="mono" style={{ color, fontSize: 14 }}>{arrow}</span>
      </div>
      <div style={{ fontSize: 11, color: 'oklch(72% 0.01 100)', marginTop: 2 }}>{sub}</div>
    </div>
  );
}

function SportBreakdown({ allActivities, sportFilter, setSportFilter }) {
  const list = (allActivities && allActivities.length) ? allActivities : window.FC_DATA.activities;
  const counts = list.reduce((acc, a) => {
    const key = canonicalActivityType(a);
    acc[key] = (acc[key] || 0) + 1;
    return acc;
  }, {});
  const total = list.length;
  const items = [
    { key: 'ALL', label: 'Alle', n: total },
    { key: 'RUNNING', label: 'Hardlopen', n: counts.RUNNING || 0 },
    { key: 'CYCLING', label: 'Fietsen', n: counts.CYCLING || 0 },
    { key: 'INDOOR_CYCLING', label: 'Zwift', n: counts.INDOOR_CYCLING || 0 },
    { key: 'LAP_SWIMMING', label: 'Zwemmen', n: counts.LAP_SWIMMING || 0 },
    { key: 'CARDIO_TRAINING', label: 'Wandelen', n: counts.CARDIO_TRAINING || 0 },
  ];
  return (
    <div className="card">
      <span className="label">Sport verdeling</span>
      <div style={{ marginTop: 14, display: 'flex', flexDirection: 'column', gap: 8 }}>
        {items.map(it => {
          const pct = total ? (it.key === 'ALL' ? 1 : (it.n / total)) : 0;
          const active = sportFilter === it.key;
          return (
            <button key={it.key} onClick={() => setSportFilter(it.key)}
              style={{
                border: 'none', background: active ? 'var(--bg-soft)' : 'transparent',
                padding: '10px 12px', borderRadius: 8, cursor: 'pointer',
                display: 'flex', alignItems: 'center', gap: 12, width: '100%',
                textAlign: 'left',
              }}>
              <span style={{ fontSize: 14, fontWeight: 500, flex: '0 0 90px' }}>{it.label}</span>
              <div style={{ flex: 1, height: 6, background: 'var(--bg-soft)', borderRadius: 4,
                            display: active ? 'none' : 'block' }}>
                <div style={{
                  height: '100%', width: `${pct * 100}%`,
                  background: 'var(--ink)', borderRadius: 4
                }}></div>
              </div>
              {active && (
                <div style={{ flex: 1, height: 6, background: 'rgba(13,14,11,.08)', borderRadius: 4 }}>
                  <div style={{ height: '100%', width: `${pct * 100}%`,
                    background: 'var(--accent)', borderRadius: 4 }}></div>
                </div>
              )}
              <span className="mono" style={{ fontSize: 12, color: 'var(--ink-3)',
                fontVariantNumeric: 'tabular-nums', minWidth: 20, textAlign: 'right' }}>
                {it.n}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

window.ActivitiesScreen = ActivitiesScreen;
