// Workout detail + FIT preview.
const { useState: useStateW, useEffect: useEffectW } = React;
const FCUW = window.FC_UTILS;

function WorkoutScreen({ recoveryScore, onNavigate, apiStatus, userId }) {
  const D = window.FC_DATA;
  const online = apiStatus === 'online';
  const activityQuery = window.useLiveData(
    (uid) => window.FC_API.fetchGarminActivities(uid, 1, 30),
    { activities: [] },
    [],
    { online, userId },
  );
  const latestActivity = activityQuery.data.activities?.[0];
  const deviceName = latestActivity?.raw_data?.deviceName || latestActivity?.device_name || 'Garmin Connect';
  const rec = D.recommendedByRecovery[recoveryScore] || D.recommendedByRecovery[4];

  const blocks = buildStructure(rec.type);
  const totalSec = blocks.reduce((s, b) => s + b.sec, 0);
  const [running, setRunning] = useStateW(false);
  const [elapsed, setElapsed] = useStateW(0);

  useEffectW(() => {
    if (!running) return;
    const t = setInterval(() => setElapsed(e => Math.min(totalSec, e + 1)), 100); // 10x speed
    return () => clearInterval(t);
  }, [running, totalSec]);

  // Find current block
  let cum = 0;
  let currentIdx = 0;
  for (let i = 0; i < blocks.length; i++) {
    if (elapsed < cum + blocks[i].sec) { currentIdx = i; break; }
    cum += blocks[i].sec;
    currentIdx = i;
  }
  const current = blocks[currentIdx];
  const intoBlock = Math.max(0, elapsed - blocks.slice(0, currentIdx).reduce((s,b) => s + b.sec, 0));
  const blockPct = current ? intoBlock / current.sec : 0;

  return (
    <div data-screen-label="Workout detail" className="col" style={{ gap: 24 }}>
      <div className="screen-head">
        <div>
          <div style={{ display: 'flex', gap: 8, marginBottom: 14 }}>
            <span className="tag accent">{rec.type}</span>
            <span className="tag">{rec.sport}</span>
            <span className="tag" style={{ background: 'transparent', border: '1px solid var(--line)' }}>
              {rec.intensity}
            </span>
          </div>
          <h1>{rec.dutch}.<br/><em>{rec.duration} minuten.</em></h1>
        </div>
        <div className="meta">
          <div className="mono" style={{ fontSize: 11, color: 'var(--ink)' }}>
            <b>workout_{rec.type.toLowerCase()}.FIT</b>
          </div>
          <div style={{ marginTop: 4 }}>Gegenereerd · {FCUW.fmtTime(new Date().toISOString())}</div>
        </div>
      </div>

      {/* Hero: live workout strip */}
      <div className="card dark" style={{ padding: '28px 32px', position: 'relative', overflow: 'hidden' }}>
        <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 3, background: 'var(--accent)' }} />

        <div style={{ display: 'flex', justifyContent: 'space-between',
                      alignItems: 'center', marginBottom: 28 }}>
          <div>
            <div className="mono" style={{ fontSize: 10, color: 'oklch(70% 0.01 100)',
              textTransform: 'uppercase', letterSpacing: '.16em', marginBottom: 8 }}>
              {running ? 'Bezig met training' : 'Klaar om te starten'}
            </div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
              <span className="mono" style={{ fontSize: 56, color: '#fff', fontWeight: 500,
                letterSpacing: '-.03em', fontVariantNumeric: 'tabular-nums' }}>
                {formatTime(elapsed)}
              </span>
              <span className="mono" style={{ fontSize: 16, color: 'oklch(70% 0.01 100)' }}>
                / {formatTime(totalSec)}
              </span>
            </div>
          </div>
          <div style={{ display: 'flex', gap: 10 }}>
            <button onClick={() => setRunning(r => !r)}
              className="btn accent xl"
              style={{ minWidth: 140, justifyContent: 'center' }}>
              {running ? '❚❚ Pauze' : '▶ Start'}
            </button>
            <button onClick={() => { setElapsed(0); setRunning(false); }}
              className="btn ghost" style={{ color: '#fff',
                borderColor: 'oklch(35% 0.005 100)' }}>
              Reset
            </button>
          </div>
        </div>

        {/* Active block */}
        <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: 24, alignItems: 'center' }}>
          <div>
            <div className="mono" style={{ fontSize: 10, color: 'oklch(70% 0.01 100)',
              textTransform: 'uppercase', letterSpacing: '.16em' }}>
              Huidige fase · {currentIdx + 1}/{blocks.length}
            </div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, marginTop: 8 }}>
              <span style={{ fontSize: 36, fontWeight: 600, color: '#fff',
                letterSpacing: '-.02em' }}>{current.label}</span>
              <span className="tag accent">{current.zone}</span>
            </div>
            <div style={{ fontSize: 14, color: 'oklch(78% 0.01 100)', marginTop: 6 }}>
              Doel HR: {current.hr} bpm
            </div>
            {/* Block progress */}
            <div style={{ marginTop: 16, height: 10, background: 'oklch(20% 0.005 100)',
                          borderRadius: 5, overflow: 'hidden', position: 'relative' }}>
              <div style={{
                position: 'absolute', left: 0, top: 0, bottom: 0,
                width: `${blockPct * 100}%`, background: 'var(--accent)',
                transition: 'width .1s linear',
              }}></div>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 6 }}>
              <span className="mono" style={{ fontSize: 11, color: 'oklch(70% 0.01 100)' }}>
                {formatTime(intoBlock)}
              </span>
              <span className="mono" style={{ fontSize: 11, color: 'oklch(70% 0.01 100)' }}>
                {formatTime(current.sec - intoBlock)} resterend
              </span>
            </div>
          </div>

          {/* Big HR target */}
          <div style={{ textAlign: 'center' }}>
            <LivePulse hr={current.hrTarget} running={running} />
            <div className="mono" style={{ fontSize: 10, color: 'oklch(70% 0.01 100)',
              textTransform: 'uppercase', letterSpacing: '.16em', marginTop: 8 }}>
              Hartslag zone
            </div>
          </div>
        </div>

        {/* Block strip */}
        <div style={{ marginTop: 28 }}>
          <div className="mono" style={{ fontSize: 10, color: 'oklch(70% 0.01 100)',
            textTransform: 'uppercase', letterSpacing: '.16em', marginBottom: 10 }}>
            Sessie tijdlijn
          </div>
          <div style={{ display: 'flex', gap: 3, height: 48 }}>
            {blocks.map((b, i) => (
              <div key={i} title={`${b.label} · ${Math.round(b.sec/60)} min`}
                onClick={() => { setElapsed(blocks.slice(0,i).reduce((s,x) => s+x.sec, 0)); }}
                style={{
                  flex: b.sec / totalSec,
                  background: b.color,
                  borderRadius: 3,
                  cursor: 'pointer',
                  position: 'relative',
                  opacity: i === currentIdx ? 1 : .5,
                  transition: 'opacity .2s, transform .15s',
                  ...(i === currentIdx ? { boxShadow: '0 0 0 2px var(--accent)' } : {}),
                }}>
              </div>
            ))}
          </div>
          <div style={{ display: 'flex', gap: 3, marginTop: 6 }}>
            {blocks.map((b, i) => (
              <div key={i} style={{ flex: b.sec / totalSec, textAlign: 'center' }}>
                {b.sec / totalSec > 0.04 && (
                  <span className="mono" style={{ fontSize: 9, color: 'oklch(72% 0.01 100)',
                    textTransform: 'uppercase', letterSpacing: '.1em' }}>
                    {b.shortLabel}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* 3-col details */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 20 }}>
        <SmallStat label="Sessie duur" value={`${rec.duration}`} unit="min" />
        <SmallStat label="Geschatte calorieën" value={`${Math.round(rec.duration * 11)}`} unit="kcal" />
        <SmallStat label="Verwachte TSS" value={`${Math.round(rec.duration * 0.8)}`} unit="" />
      </div>

      {/* Step list + side */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.5fr 1fr', gap: 20 }}>
        <div className="card">
          <h2 style={{ marginBottom: 14 }}>Stappen</h2>
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            {blocks.map((b, i) => (
              <div key={i} style={{
                display: 'grid',
                gridTemplateColumns: '34px 1fr auto auto',
                gap: 14, alignItems: 'center',
                padding: '14px 0',
                borderBottom: i < blocks.length - 1 ? '1px solid var(--line)' : 'none',
                opacity: i === currentIdx || !running ? 1 : .5,
              }}>
                <div className="mono" style={{ fontSize: 11, color: 'var(--ink-4)',
                  fontVariantNumeric: 'tabular-nums' }}>
                  {String(i + 1).padStart(2, '0')}
                </div>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ fontWeight: 500, fontSize: 15 }}>{b.label}</span>
                    <span className="tag" style={{ background: b.color, color: 'white',
                      fontSize: 10, padding: '3px 8px' }}>{b.zone}</span>
                  </div>
                  <div className="mono" style={{ fontSize: 11, color: 'var(--ink-4)',
                    marginTop: 4 }}>HR doel: {b.hr} bpm</div>
                </div>
                <div className="mono" style={{ fontSize: 14, color: 'var(--ink-3)',
                  fontVariantNumeric: 'tabular-nums' }}>{Math.round(b.sec/60)} min</div>
                <div style={{ width: 30, height: 30, borderRadius: 999,
                  background: i === currentIdx && running ? 'var(--accent)' : 'transparent',
                  border: i === currentIdx && running ? 'none' : '1px solid var(--line)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center'
                }}>
                  {i === currentIdx && running ?
                    <span style={{ width: 8, height: 8, background: 'var(--ink)', borderRadius: 999 }}></span> :
                    <span style={{ color: 'var(--ink-4)', fontSize: 12 }}>·</span>}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="col" style={{ gap: 16 }}>
          {/* Send to Garmin */}
          <div className="card tight" style={{ background: 'var(--bg-soft)', borderColor: 'transparent' }}>
            <span className="label">Levering</span>
            <div style={{ marginTop: 14, display: 'flex', alignItems: 'center', gap: 12 }}>
              <div style={{ width: 40, height: 40, borderRadius: 10,
                background: 'var(--ink)', color: 'var(--accent)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontFamily: "'JetBrains Mono', monospace", fontWeight: 700 }}>⌚</div>
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 500, fontSize: 14 }}>{deviceName}</div>
                <div className="mono" style={{ fontSize: 11, color: 'var(--ink-4)', marginTop: 2 }}>
                  {online && userId ? 'Verbonden via Garmin OAuth' : 'Wachten op Garmin login'}
                </div>
              </div>
            </div>
            <button className="btn" style={{ marginTop: 14, width: '100%', justifyContent: 'center' }}>
              Stuur naar Garmin Connect <span className="arrow">↑</span>
            </button>
            <button className="btn ghost" style={{ marginTop: 6, width: '100%', justifyContent: 'center' }}>
              Download FIT-bestand
            </button>
          </div>

          {/* Notes */}
          <div className="card tight">
            <span className="label">Coach notitie</span>
            <p style={{ fontSize: 14, lineHeight: 1.55, marginTop: 10, color: 'var(--ink-2)' }}>
              {rec.desc} Met je <b>recovery {recoveryScore}/6</b> ben je hier prima op gecondityioneerd.
              Hou tijdens de blokken je hartslag in de doelzone — niet bang om iets boven te gaan op de laatste reps.
            </p>
            <div style={{ marginTop: 14, display: 'flex', gap: 6 }}>
              <button className="btn ghost" style={{ padding: '6px 12px', fontSize: 12 }}>
                Vraag aanpassing
              </button>
              <button className="btn ghost" style={{ padding: '6px 12px', fontSize: 12 }}>
                Andere training
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function formatTime(sec) {
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`;
}

function SmallStat({ label, value, unit }) {
  return (
    <div className="card tight">
      <span className="label">{label}</span>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 4, marginTop: 8 }}>
        <span className="mono" style={{ fontSize: 36, fontWeight: 500,
          letterSpacing: '-.02em', fontVariantNumeric: 'tabular-nums' }}>{value}</span>
        {unit && <span className="stat-unit">{unit}</span>}
      </div>
    </div>
  );
}

function LivePulse({ hr, running }) {
  const [v, setV] = useStateW(hr || 120);
  useEffectW(() => {
    if (!running) return;
    const t = setInterval(() => {
      setV(curr => {
        const target = parseInt(hr.split('-')[0]);
        const noise = (Math.random() - 0.5) * 8;
        return Math.round(target + noise);
      });
    }, 700);
    return () => clearInterval(t);
  }, [running, hr]);

  return (
    <div style={{ display: 'inline-flex', flexDirection: 'column',
                  alignItems: 'center', gap: 4 }}>
      <div className="mono" style={{ fontSize: 14, color: 'var(--accent)',
        letterSpacing: '.04em' }}>{hr} bpm</div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 4,
                    color: '#fff' }}>
        <span className="mono" style={{ fontSize: 72, fontWeight: 500,
          letterSpacing: '-.03em', fontVariantNumeric: 'tabular-nums',
          animation: running ? 'beat 1.2s ease-in-out infinite' : 'none' }}>
          {running ? v : '—'}
        </span>
      </div>
      <div className="mono" style={{ fontSize: 11, color: 'oklch(70% 0.01 100)',
        textTransform: 'uppercase', letterSpacing: '.14em' }}>
        bpm {running && <span style={{ color: 'var(--bad)', marginLeft: 6 }}>● LIVE</span>}
      </div>
    </div>
  );
}

if (!document.getElementById('__fc-beat-css')) {
  const s = document.createElement('style');
  s.id = '__fc-beat-css';
  s.textContent = `@keyframes beat { 0%,100% { transform: scale(1); } 14% { transform: scale(1.04); } 28% { transform: scale(1); } 42% { transform: scale(1.02); } }`;
  document.head.appendChild(s);
}

function buildStructure(type) {
  const colors = {
    rest:   'oklch(48% 0.05 220)',
    z1:     'oklch(55% 0.06 220)',
    z2:     'oklch(62% 0.10 145)',
    z3:     'oklch(72% 0.14 100)',
    z4:     'oklch(75% 0.18 60)',
    z5:     'oklch(68% 0.22 25)',
  };
  if (type === 'HERSTEL') return [
    { label: 'Warming-up', shortLabel: 'WU', zone: 'Z1', sec: 5*60, hr: '120-130', hrTarget: '120-130', color: colors.z1 },
    { label: 'Easy walk', shortLabel: 'Easy', zone: 'Z1', sec: 30*60, hr: '110-128', hrTarget: '110-128', color: colors.rest },
    { label: 'Cooling-down', shortLabel: 'CD', zone: 'Z1', sec: 5*60, hr: '110-120', hrTarget: '110-120', color: colors.z1 },
  ];
  if (type === 'DUUR') return [
    { label: 'Warming-up', shortLabel: 'WU', zone: 'Z1', sec: 8*60, hr: '125-135', hrTarget: '125-135', color: colors.z1 },
    { label: 'Duurblok zone 2', shortLabel: 'Z2 Duur', zone: 'Z2', sec: 45*60, hr: '138-152', hrTarget: '138-152', color: colors.z2 },
    { label: 'Cooling-down', shortLabel: 'CD', zone: 'Z1', sec: 7*60, hr: '120-135', hrTarget: '120-135', color: colors.z1 },
  ];
  if (type === 'THRESHOLD') return [
    { label: 'Warming-up', shortLabel: 'WU', zone: 'Z1', sec: 10*60, hr: '125-138', hrTarget: '125-138', color: colors.z1 },
    { label: 'Tempo blok 1', shortLabel: 'Tempo 1', zone: 'Z4', sec: 12*60, hr: '162-170', hrTarget: '162-170', color: colors.z4 },
    { label: 'Actieve rust', shortLabel: 'Rust', zone: 'Z1', sec: 4*60, hr: '130-140', hrTarget: '130-140', color: colors.z1 },
    { label: 'Tempo blok 2', shortLabel: 'Tempo 2', zone: 'Z4', sec: 12*60, hr: '162-170', hrTarget: '162-170', color: colors.z4 },
    { label: 'Cooling-down', shortLabel: 'CD', zone: 'Z1', sec: 8*60, hr: '120-135', hrTarget: '120-135', color: colors.z1 },
  ];
  if (type === 'VO2MAX') return [
    { label: 'Warming-up', shortLabel: 'WU', zone: 'Z1', sec: 10*60, hr: '125-138', hrTarget: '125-138', color: colors.z1 },
    ...Array(6).fill(0).flatMap(() => [
      { label: 'VO2 interval', shortLabel: 'VO2', zone: 'Z5', sec: 3*60, hr: '175-185', hrTarget: '175-185', color: colors.z5 },
      { label: 'Herstel', shortLabel: 'rust', zone: 'Z1', sec: 3*60, hr: '130-140', hrTarget: '130-140', color: colors.z1 },
    ]),
    { label: 'Cooling-down', shortLabel: 'CD', zone: 'Z1', sec: 8*60, hr: '120-135', hrTarget: '120-135', color: colors.z1 },
  ];
  if (type === 'SPRINT') return [
    { label: 'Warming-up', shortLabel: 'WU', zone: 'Z1', sec: 10*60, hr: '125-138', hrTarget: '125-138', color: colors.z1 },
    ...Array(10).fill(0).flatMap(() => [
      { label: 'Sprint', shortLabel: 'SP', zone: 'Z5', sec: 30, hr: '> 180', hrTarget: '180-195', color: colors.z5 },
      { label: 'Walk', shortLabel: 'walk', zone: 'Z1', sec: 90, hr: '110-130', hrTarget: '110-130', color: colors.rest },
    ]),
    { label: 'Cooling-down', shortLabel: 'CD', zone: 'Z1', sec: 7*60, hr: '120-135', hrTarget: '120-135', color: colors.z1 },
  ];
  return [];
}

window.WorkoutScreen = WorkoutScreen;
