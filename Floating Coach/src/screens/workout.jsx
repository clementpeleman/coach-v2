// Workout detail + FIT preview.
const { useState: useStateW } = React;
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
  const [targetMode, setTargetMode] = useStateW('pace');
  const [intensityPct, setIntensityPct] = useStateW(100);
  const adjustedBlocks = blocks.map((block) => ({
    ...block,
    adjustedHr: adjustHrRange(block.hr, intensityPct),
    adjustedPace: adjustPaceRange(block.pace, intensityPct),
  }));
  const workBlocks = adjustedBlocks.filter((b) => !['Z1'].includes(b.zone));
  const mainTarget = workBlocks[0] || adjustedBlocks[1] || adjustedBlocks[0];
  const targetLabel = targetMode === 'pace' ? 'Tempo/snelheid' : 'Hartslag';
  const targetValue = targetMode === 'pace' ? mainTarget?.adjustedPace : `${mainTarget?.adjustedHr} bpm`;

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

      {/* Hero: workout plan */}
      <div className="card dark" style={{ padding: '28px 32px', position: 'relative', overflow: 'hidden' }}>
        <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 3, background: 'var(--accent)' }} />

        <div style={{ display: 'flex', justifyContent: 'space-between',
                      alignItems: 'center', marginBottom: 28 }}>
          <div>
            <div className="mono" style={{ fontSize: 10, color: 'oklch(70% 0.01 100)',
              textTransform: 'uppercase', letterSpacing: '.16em', marginBottom: 8 }}>
              Trainingsplan
            </div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
              <span className="mono" style={{ fontSize: 56, color: '#fff', fontWeight: 500,
                letterSpacing: '-.03em', fontVariantNumeric: 'tabular-nums' }}>
                {formatTime(totalSec)}
              </span>
              <span className="mono" style={{ fontSize: 16, color: 'oklch(70% 0.01 100)' }}>
                totaal
              </span>
            </div>
          </div>
          <div style={{ width: 360 }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6, marginBottom: 14 }}>
              {[
                ['pace', 'Tempo'],
                ['hr', 'Hartslag'],
              ].map(([mode, label]) => (
                <button key={mode} onClick={() => setTargetMode(mode)}
                  className={targetMode === mode ? 'btn accent' : 'btn ghost'}
                  style={{ justifyContent: 'center', color: targetMode === mode ? undefined : '#fff',
                    borderColor: targetMode === mode ? undefined : 'oklch(35% 0.005 100)' }}>
                  {label}
                </button>
              ))}
            </div>
            <div className="mono" style={{ color: 'oklch(70% 0.01 100)', fontSize: 10,
              textTransform: 'uppercase', letterSpacing: '.14em', marginBottom: 8 }}>
              Intensiteit {intensityPct}%
            </div>
            <input type="range" min="90" max="110" step="1" value={intensityPct}
              onChange={(e) => setIntensityPct(Number(e.target.value))}
              onInput={(e) => setIntensityPct(Number(e.target.value))}
              style={{ width: '100%', accentColor: 'var(--accent)' }} />
            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4 }}>
              {['90%', '100%', '110%'].map((v) => (
                <span key={v} className="mono" style={{ fontSize: 10, color: 'oklch(70% 0.01 100)' }}>{v}</span>
              ))}
            </div>
          </div>
        </div>

        {/* Main target */}
        <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: 24, alignItems: 'center' }}>
          <div>
            <div className="mono" style={{ fontSize: 10, color: 'oklch(70% 0.01 100)',
              textTransform: 'uppercase', letterSpacing: '.16em' }}>
              Belangrijkste doel
            </div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, marginTop: 8 }}>
              <span style={{ fontSize: 36, fontWeight: 600, color: '#fff',
                letterSpacing: '-.02em' }}>{mainTarget?.label}</span>
              <span className="tag accent">{mainTarget?.zone}</span>
            </div>
            <div style={{ fontSize: 14, color: 'oklch(78% 0.01 100)', marginTop: 6 }}>
              Gebruik <b>{targetMode === 'pace' ? 'tempo/snelheid' : 'hartslag'}</b> als primaire sturing. Hartslag blijft nuttig als veiligheidscheck.
            </div>
          </div>

          {/* Big target */}
          <div style={{ textAlign: 'center' }}>
            <div className="mono" style={{ fontSize: 10, color: 'oklch(70% 0.01 100)',
              textTransform: 'uppercase', letterSpacing: '.16em' }}>{targetLabel}</div>
            <div className="mono" style={{ fontSize: 42, color: '#fff', fontWeight: 500,
              letterSpacing: '-.03em', marginTop: 8 }}>{targetValue || '–'}</div>
            <div className="mono" style={{ fontSize: 10, color: 'oklch(70% 0.01 100)',
              textTransform: 'uppercase', letterSpacing: '.16em', marginTop: 8 }}>
              Aangepast naar {intensityPct}%
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
                style={{
                  flex: b.sec / totalSec,
                  background: b.color,
                  borderRadius: 3,
                  position: 'relative',
                  opacity: .82,
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
            {adjustedBlocks.map((b, i) => (
              <div key={i} style={{
                display: 'grid',
                gridTemplateColumns: '34px 1fr auto auto',
                gap: 14, alignItems: 'center',
                padding: '14px 0',
                borderBottom: i < blocks.length - 1 ? '1px solid var(--line)' : 'none',
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
                    marginTop: 4 }}>
                    {targetMode === 'pace'
                      ? `Tempo: ${b.adjustedPace || 'vrij'} · HR check: ${b.adjustedHr} bpm`
                      : `HR doel: ${b.adjustedHr} bpm · Tempo indicatie: ${b.adjustedPace || 'vrij'}`}
                  </div>
                </div>
                <div className="mono" style={{ fontSize: 14, color: 'var(--ink-3)',
                  fontVariantNumeric: 'tabular-nums' }}>{Math.round(b.sec/60)} min</div>
                <div style={{ width: 30, height: 30, borderRadius: 999,
                  border: '1px solid var(--line)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center'
                }}>
                  <span style={{ color: 'var(--ink-4)', fontSize: 12 }}>·</span>
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
              Deze versie stuurt primair op <b>{targetMode === 'pace' ? 'tempo/snelheid' : 'hartslag'}</b> en staat op <b>{intensityPct}%</b>.
              Pas de slider aan als je vandaag iets conservatiever of scherper wil trainen.
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

function adjustHrRange(range, pct) {
  if (!range) return '–';
  const nums = String(range).match(/\d+/g);
  if (!nums || nums.length === 0) return range;
  const adjusted = nums.map((n) => Math.round(Number(n) * pct / 100));
  if (String(range).trim().startsWith('>')) return `> ${adjusted[0]}`;
  return adjusted.length >= 2 ? `${adjusted[0]}-${adjusted[1]}` : `${adjusted[0]}`;
}

function paceToSeconds(value) {
  const [m, s] = value.split(':').map(Number);
  return (m || 0) * 60 + (s || 0);
}

function secondsToPace(seconds) {
  const rounded = Math.max(1, Math.round(seconds));
  const m = Math.floor(rounded / 60);
  const s = rounded % 60;
  return `${m}:${String(s).padStart(2, '0')}/km`;
}

function adjustPaceRange(range, pct) {
  if (!range) return null;
  const parts = String(range).replace('/km', '').split('-').map((p) => p.trim()).filter(Boolean);
  if (!parts.length) return range;
  const factor = 100 / pct;
  const adjusted = parts.map((p) => secondsToPace(paceToSeconds(p) * factor));
  return adjusted.length >= 2 ? adjusted.join('-') : adjusted[0];
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
    { label: 'Warming-up', shortLabel: 'WU', zone: 'Z1', sec: 5*60, hr: '120-130', pace: '7:00-8:00/km', color: colors.z1 },
    { label: 'Easy walk', shortLabel: 'Easy', zone: 'Z1', sec: 30*60, hr: '110-128', pace: '8:00-10:00/km', color: colors.rest },
    { label: 'Cooling-down', shortLabel: 'CD', zone: 'Z1', sec: 5*60, hr: '110-120', pace: '7:30-9:00/km', color: colors.z1 },
  ];
  if (type === 'DUUR') return [
    { label: 'Warming-up', shortLabel: 'WU', zone: 'Z1', sec: 8*60, hr: '125-135', pace: '6:40-7:20/km', color: colors.z1 },
    { label: 'Duurblok zone 2', shortLabel: 'Z2 Duur', zone: 'Z2', sec: 45*60, hr: '138-152', pace: '5:55-6:35/km', color: colors.z2 },
    { label: 'Cooling-down', shortLabel: 'CD', zone: 'Z1', sec: 7*60, hr: '120-135', pace: '6:45-7:40/km', color: colors.z1 },
  ];
  if (type === 'THRESHOLD') return [
    { label: 'Warming-up', shortLabel: 'WU', zone: 'Z1', sec: 10*60, hr: '125-138', pace: '6:30-7:15/km', color: colors.z1 },
    { label: 'Tempo blok 1', shortLabel: 'Tempo 1', zone: 'Z4', sec: 12*60, hr: '162-170', pace: '4:55-5:15/km', color: colors.z4 },
    { label: 'Actieve rust', shortLabel: 'Rust', zone: 'Z1', sec: 4*60, hr: '130-140', pace: '6:50-7:40/km', color: colors.z1 },
    { label: 'Tempo blok 2', shortLabel: 'Tempo 2', zone: 'Z4', sec: 12*60, hr: '162-170', pace: '4:55-5:15/km', color: colors.z4 },
    { label: 'Cooling-down', shortLabel: 'CD', zone: 'Z1', sec: 8*60, hr: '120-135', pace: '6:45-7:40/km', color: colors.z1 },
  ];
  if (type === 'VO2MAX') return [
    { label: 'Warming-up', shortLabel: 'WU', zone: 'Z1', sec: 10*60, hr: '125-138', pace: '6:30-7:15/km', color: colors.z1 },
    ...Array(6).fill(0).flatMap(() => [
      { label: 'VO2 interval', shortLabel: 'VO2', zone: 'Z5', sec: 3*60, hr: '175-185', pace: '4:25-4:45/km', color: colors.z5 },
      { label: 'Herstel', shortLabel: 'rust', zone: 'Z1', sec: 3*60, hr: '130-140', pace: '7:00-8:00/km', color: colors.z1 },
    ]),
    { label: 'Cooling-down', shortLabel: 'CD', zone: 'Z1', sec: 8*60, hr: '120-135', pace: '6:45-7:40/km', color: colors.z1 },
  ];
  if (type === 'SPRINT') return [
    { label: 'Warming-up', shortLabel: 'WU', zone: 'Z1', sec: 10*60, hr: '125-138', pace: '6:30-7:15/km', color: colors.z1 },
    ...Array(10).fill(0).flatMap(() => [
      { label: 'Sprint', shortLabel: 'SP', zone: 'Z5', sec: 30, hr: '> 180', pace: '3:45-4:10/km', color: colors.z5 },
      { label: 'Walk', shortLabel: 'walk', zone: 'Z1', sec: 90, hr: '110-130', pace: '8:00-10:00/km', color: colors.rest },
    ]),
    { label: 'Cooling-down', shortLabel: 'CD', zone: 'Z1', sec: 7*60, hr: '120-135', pace: '6:45-7:40/km', color: colors.z1 },
  ];
  return [];
}

window.WorkoutScreen = WorkoutScreen;
