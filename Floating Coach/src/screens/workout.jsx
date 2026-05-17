// Workout detail + FIT preview.
const { useState: useStateW, useEffect: useEffectW } = React;
const FCUW = window.FC_UTILS;

const SPORT_OPTIONS = [
  { key: 'WALKING', label: 'Wandelen', shortLabel: 'Wandel', garminType: 'WALKING', metric: 'pace', targetLabel: 'Tempo', targetText: 'wandeltempo' },
  { key: 'RUNNING', label: 'Hardlopen', shortLabel: 'Run', garminType: 'RUNNING', metric: 'pace', targetLabel: 'Tempo', targetText: 'looptempo' },
  { key: 'CYCLING', label: 'Fietsen', shortLabel: 'Fiets', garminType: 'CYCLING', metric: 'speed', targetLabel: 'Snelheid', targetText: 'snelheid' },
  { key: 'INDOOR_CYCLING', label: 'Indoor fietsen', shortLabel: 'Zwift', garminType: 'INDOOR_CYCLING', metric: 'speed', targetLabel: 'Snelheid', targetText: 'Zwift-snelheid' },
  { key: 'SWIMMING', label: 'Zwemmen', shortLabel: 'Zwem', garminType: 'LAP_SWIMMING', metric: 'pace', targetLabel: 'Tempo', targetText: 'zwemtempo' },
];

function WorkoutScreen({ recoveryScore, onNavigate, apiStatus, userId, trainingProfile }) {
  const D = window.FC_DATA;
  const online = apiStatus === 'online';
  const activityQuery = window.useLiveData(
    (uid) => window.FC_API.fetchGarminActivities(uid, 1, 30),
    { activities: [] },
    [],
    { online, userId },
  );
  const trainingProfileQuery = window.useLiveData(
    (uid) => window.FC_API.fetchTrainingProfile(uid, 120, 7),
    { personal_targets: {}, sport_baselines: {}, workout_patterns: {}, method: { phase: 1 } },
    [],
    { online, userId },
  );
  const profileData = trainingProfile || trainingProfileQuery.data;
  const latestActivity = activityQuery.data.activities?.[0];
  const deviceName = latestActivity?.raw_data?.deviceName || latestActivity?.device_name || 'Garmin Connect';
  const rec = D.recommendedByRecovery[recoveryScore] || D.recommendedByRecovery[4];
  const patternForType = profileData.workout_patterns?.by_type?.[rec.type];
  const patternSport = patternForType?.preferred_sport;
  const patternSportKey = patternSport && SPORT_OPTIONS.some((sport) => sport.key === patternSport)
    ? patternSport
    : null;
  const plannedDuration = patternForType?.typical_duration_min || rec.duration;

  const [sportType, setSportType] = useStateW(sportFromRecommendation(rec.sport));
  const [sportTouched, setSportTouched] = useStateW(false);
  const [targetMode, setTargetMode] = useStateW('pace');
  const [intensityPct, setIntensityPct] = useStateW(100);
  useEffectW(() => {
    if (!sportTouched && patternSportKey) setSportType(patternSportKey);
  }, [patternSportKey, sportTouched]);

  const selectedSport = SPORT_OPTIONS.find((sport) => sport.key === sportType) || SPORT_OPTIONS[1];
  const personalSportProfile = profileData.personal_targets?.[sportType];
  const personalConfidence = personalSportProfile?.confidence || 'none';
  const detailSegments = personalSportProfile?.detail_segments || 0;
  const primaryTargetLabel = selectedSport.targetLabel;
  const primaryTargetText = selectedSport.targetText;
  const baseBlocks = buildStructure(rec.type, sportType, personalSportProfile, patternForType);
  const blocks = patternForType?.typical_duration_min
    ? fitBlocksToDuration(baseBlocks, plannedDuration)
    : baseBlocks;
  const totalSec = blocks.reduce((s, b) => s + b.sec, 0);
  const adjustedBlocks = blocks.map((block) => ({
    ...block,
    adjustedHr: adjustHrRange(block.hr, intensityPct),
    adjustedPace: adjustPaceRange(block.pace, intensityPct),
    adjustedSpeed: adjustSpeedRange(block.speed, intensityPct),
  }));
  const workBlocks = adjustedBlocks.filter((b) => !['Z1'].includes(b.zone));
  const mainTarget = workBlocks[0] || adjustedBlocks[1] || adjustedBlocks[0];
  const primaryTargetValue = selectedSport.metric === 'speed' ? mainTarget?.adjustedSpeed : mainTarget?.adjustedPace;
  const targetLabel = targetMode === 'pace' ? primaryTargetLabel : 'Hartslag';
  const targetValue = targetMode === 'pace' ? primaryTargetValue : `${mainTarget?.adjustedHr} bpm`;
  const getPrimaryTarget = (block) => (
    selectedSport.metric === 'speed' ? block.adjustedSpeed : block.adjustedPace
  ) || 'vrij';

  return (
    <div data-screen-label="Workout detail" className="col" style={{ gap: 24 }}>
      <div className="screen-head">
        <div>
          <div style={{ display: 'flex', gap: 8, marginBottom: 14 }}>
            <span className="tag accent">{rec.type}</span>
            <span className="tag">{selectedSport.label}</span>
            <span className="tag" style={{ background: 'transparent', border: '1px solid var(--line)' }}>
              {rec.intensity}
            </span>
          </div>
          <h1>{rec.dutch}.<br/><em>{Math.round(totalSec / 60)} minuten.</em></h1>
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
          <div style={{ width: 400 }}>
            <div className="mono" style={{ color: 'oklch(70% 0.01 100)', fontSize: 10,
              textTransform: 'uppercase', letterSpacing: '.14em', marginBottom: 8 }}>
              Sport
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, minmax(0, 1fr))', gap: 5, marginBottom: 14 }}>
              {SPORT_OPTIONS.map((sport) => (
                <button key={sport.key} onClick={() => { setSportTouched(true); setSportType(sport.key); }}
                  className={sportType === sport.key ? 'btn accent' : 'btn ghost'}
                  style={{ justifyContent: 'center', color: sportType === sport.key ? undefined : '#fff',
                    borderColor: sportType === sport.key ? undefined : 'oklch(35% 0.005 100)',
                    padding: '8px 6px', fontSize: 11, minWidth: 0 }}>
                  {sport.shortLabel}
                </button>
              ))}
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6, marginBottom: 14 }}>
              {[
                ['pace', primaryTargetLabel],
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
              Gebruik <b>{targetMode === 'pace' ? primaryTargetText : 'hartslag'}</b> als primaire sturing. Hartslag blijft nuttig als veiligheidscheck.
            </div>
            <div className="mono" style={{ fontSize: 10, color: 'oklch(70% 0.01 100)',
              textTransform: 'uppercase', letterSpacing: '.12em', marginTop: 8 }}>
              {personalSportProfile
                ? `Persoonlijk profiel · ${personalSportProfile.sessions} sessies · ${detailSegments} detailsegmenten · vertrouwen ${personalConfidence}`
                : 'Fallback targets · nog te weinig sportdata'}
              {patternForType && ` · patroon ${patternForType.typical_structure || 'continu'}`}
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
        <SmallStat label="Sessie duur" value={`${Math.round(totalSec / 60)}`} unit="min" />
        <SmallStat label="Geschatte calorieën" value={`${Math.round((totalSec / 60) * 11)}`} unit="kcal" />
        <SmallStat label="Verwachte TSS" value={`${Math.round((totalSec / 60) * 0.8)}`} unit="" />
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
                      ? `${primaryTargetLabel}: ${getPrimaryTarget(b)} · HR check: ${b.adjustedHr} bpm`
                      : `HR doel: ${b.adjustedHr} bpm · ${primaryTargetLabel} indicatie: ${getPrimaryTarget(b)}`}
                    {b.personalized && (
                      <span style={{ color: 'var(--ink-3)' }}>
                        {' '}· geleerd uit {b.source === 'activityDetails' ? 'details/laps' : 'sessies'}
                      </span>
                    )}
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
                <div className="mono" style={{ fontSize: 11, color: 'var(--ink-4)', marginTop: 2 }}>
                  Garmin sporttype: {selectedSport.garminType}
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
              {rec.desc} Met je <b>recovery {recoveryScore}/6</b> ben je hier prima op geconditioneerd.
              Deze versie is ingesteld voor <b>{selectedSport.label.toLowerCase()}</b>, stuurt primair op <b>{targetMode === 'pace' ? primaryTargetText : 'hartslag'}</b> en staat op <b>{intensityPct}%</b>.
              {personalSportProfile
                ? ` Targets zijn geleerd uit je laatste ${personalSportProfile.sessions} ${selectedSport.label.toLowerCase()}-sessies${detailSegments ? ` en ${detailSegments} detailsegmenten` : ''}.`
                : ' Ik gebruik voorlopig ruime standaardtargets tot er meer sessies binnen zijn.'}
              {patternForType
                ? ` Structuur gebaseerd op je typische ${rec.type.toLowerCase()}-sessies: ${patternForType.typical_structure || 'continu'}, meestal ${sportLabelFromKey(patternForType.preferred_sport)}.`
                : ' Voor de workoutstructuur gebruik ik de standaardopbouw omdat er nog weinig patroondata is.'}
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
  return `${m}:${String(s).padStart(2, '0')}`;
}

function adjustPaceRange(range, pct) {
  if (!range) return null;
  const suffix = String(range).includes('/100m') ? '/100m' : '/km';
  const parts = String(range).replace(suffix, '').split('-').map((p) => p.trim()).filter(Boolean);
  if (!parts.length) return range;
  const factor = 100 / pct;
  const adjusted = parts.map((p) => secondsToPace(paceToSeconds(p) * factor));
  return `${adjusted.length >= 2 ? adjusted.join('-') : adjusted[0]}${suffix}`;
}

function adjustSpeedRange(range, pct) {
  if (!range) return null;
  const nums = String(range).match(/\d+(\.\d+)?/g);
  if (!nums || nums.length === 0) return range;
  const adjusted = nums.map((n) => Math.round(Number(n) * pct / 100));
  if (String(range).trim().startsWith('>')) return `> ${adjusted[0]} km/u`;
  return `${adjusted.length >= 2 ? adjusted.join('-') : adjusted[0]} km/u`;
}

function sportFromRecommendation(sport) {
  const normalized = String(sport || '').toLowerCase();
  if (normalized.includes('fiets') || normalized.includes('cycling')) return 'CYCLING';
  if (normalized.includes('zwem') || normalized.includes('swim')) return 'SWIMMING';
  if (normalized.includes('wandel') || normalized.includes('walk')) return 'WALKING';
  return 'RUNNING';
}

function sportLabelFromKey(key) {
  return (SPORT_OPTIONS.find((sport) => sport.key === key)?.label || key || 'deze sport').toLowerCase();
}

function parsePatternStructure(structure) {
  const text = String(structure || '').toLowerCase();
  const match = text.match(/(\d+)\s*x\s*(\d+(?:\.\d+)?)(min|s)/);
  if (!match) return null;
  const count = Number(match[1]);
  const value = Number(match[2]);
  const unit = match[3];
  if (!count || !value) return null;
  return { count, workSec: unit === 's' ? value : value * 60 };
}

function fitBlocksToDuration(blocks, durationMin) {
  const targetSec = Math.max(5, Math.round(durationMin || 0)) * 60;
  const currentSec = blocks.reduce((sum, block) => sum + block.sec, 0);
  const diff = targetSec - currentSec;
  if (!blocks.length || Math.abs(diff) < 60) return blocks;
  const index = blocks.reduce((best, block, i) => {
    const currentBest = blocks[best];
    if (block.zone !== 'Z1' && block.sec > currentBest.sec) return i;
    if (currentBest.zone === 'Z1' && block.sec > currentBest.sec) return i;
    return best;
  }, 0);
  return blocks.map((block, i) => (
    i === index ? { ...block, sec: Math.max(60, block.sec + diff) } : block
  ));
}

function buildPatternIntervals(type, sportType, personalProfile, pattern, colors) {
  const parsed = parsePatternStructure(pattern?.typical_structure);
  if (!parsed || !['THRESHOLD', 'VO2MAX', 'SPRINT'].includes(type)) return null;
  const settings = {
    THRESHOLD: { label: 'Tempo blok', short: 'Tempo', zone: 'Z4', metric: 'z4', restSec: 4*60, warmSec: 10*60, coolSec: 8*60, color: colors.z4 },
    VO2MAX: { label: 'VO2 interval', short: 'VO2', zone: 'Z5', metric: 'z5', restSec: 3*60, warmSec: 10*60, coolSec: 8*60, color: colors.z5 },
    SPRINT: { label: 'Sprint', short: 'SP', zone: 'Z5', metric: 'z5', restSec: 90, warmSec: 10*60, coolSec: 7*60, color: colors.z5 },
  }[type];
  const blocks = [
    withSportTarget({ label: 'Warming-up', shortLabel: 'WU', zone: 'Z1', sec: settings.warmSec, hr: '125-138', color: colors.z1 }, sportType, 'z1', personalProfile),
  ];
  for (let i = 0; i < parsed.count; i += 1) {
    blocks.push(withSportTarget({
      label: `${settings.label} ${i + 1}`,
      shortLabel: settings.short,
      zone: settings.zone,
      sec: parsed.workSec,
      hr: type === 'THRESHOLD' ? '162-170' : '> 175',
      color: settings.color,
    }, sportType, settings.metric, personalProfile));
    if (i < parsed.count - 1) {
      blocks.push(withSportTarget({
        label: 'Herstel',
        shortLabel: 'rust',
        zone: 'Z1',
        sec: settings.restSec,
        hr: type === 'SPRINT' ? '110-130' : '130-140',
        color: colors.z1,
      }, sportType, type === 'SPRINT' ? 'rest' : 'z1', personalProfile));
    }
  }
  blocks.push(withSportTarget({ label: 'Cooling-down', shortLabel: 'CD', zone: 'Z1', sec: settings.coolSec, hr: '120-135', color: colors.z1 }, sportType, 'z1', personalProfile));
  return blocks;
}

function metricForSport(sportType, zone) {
  const table = {
    WALKING: {
      rest: { pace: '9:30-11:00/km' },
      z1: { pace: '9:00-10:15/km' },
      z2: { pace: '8:15-9:15/km' },
      z4: { pace: '7:10-8:00/km' },
      z5: { pace: '6:30-7:15/km' },
    },
    RUNNING: {
      rest: { pace: '8:00-10:00/km' },
      z1: { pace: '6:45-7:40/km' },
      z2: { pace: '5:55-6:35/km' },
      z4: { pace: '4:55-5:15/km' },
      z5: { pace: '4:25-4:45/km' },
    },
    CYCLING: {
      rest: { speed: '16-20 km/u' },
      z1: { speed: '19-23 km/u' },
      z2: { speed: '24-28 km/u' },
      z4: { speed: '31-35 km/u' },
      z5: { speed: '37-43 km/u' },
    },
    INDOOR_CYCLING: {
      rest: { speed: '18-22 km/u' },
      z1: { speed: '22-26 km/u' },
      z2: { speed: '27-32 km/u' },
      z4: { speed: '34-40 km/u' },
      z5: { speed: '42-50 km/u' },
    },
    SWIMMING: {
      rest: { pace: '2:45-3:15/100m' },
      z1: { pace: '2:25-2:55/100m' },
      z2: { pace: '2:05-2:25/100m' },
      z4: { pace: '1:45-2:00/100m' },
      z5: { pace: '1:30-1:45/100m' },
    },
  };
  return table[sportType]?.[zone] || table.RUNNING[zone] || {};
}

function effortForMetricZone(metricZone) {
  if (metricZone === 'z2') return 'endurance';
  if (metricZone === 'z4') return 'threshold';
  if (metricZone === 'z5') return 'vo2';
  return 'easy';
}

function withSportTarget(block, sportType, metricZone, personalProfile) {
  const zone = metricZone || block.metricZone || 'z1';
  const defaults = metricForSport(sportType, zone);
  const effort = effortForMetricZone(zone);
  const personalZone = personalProfile?.zones?.[effort];
  const personalMetric = personalZone?.metric;
  const personalTarget = personalProfile?.metric_type === 'speed'
    ? { speed: personalMetric || defaults.speed }
    : { pace: personalMetric || defaults.pace };
  return {
    ...block,
    ...defaults,
    ...personalTarget,
    hr: personalZone?.hr || block.hr,
    personalized: Boolean(personalMetric || personalZone?.hr),
    source: personalZone?.source || 'fallback',
  };
}

function buildStructure(type, sportType = 'RUNNING', personalProfile = null, pattern = null) {
  const colors = {
    rest:   'oklch(48% 0.05 220)',
    z1:     'oklch(55% 0.06 220)',
    z2:     'oklch(62% 0.10 145)',
    z3:     'oklch(72% 0.14 100)',
    z4:     'oklch(75% 0.18 60)',
    z5:     'oklch(68% 0.22 25)',
  };
  const patternBlocks = buildPatternIntervals(type, sportType, personalProfile, pattern, colors);
  if (patternBlocks) return patternBlocks;

  if (type === 'HERSTEL') return [
    withSportTarget({ label: 'Warming-up', shortLabel: 'WU', zone: 'Z1', sec: 5*60, hr: '120-130', color: colors.z1 }, sportType, 'z1', personalProfile),
    withSportTarget({ label: sportType === 'WALKING' ? 'Rustige wandeling' : 'Easy blok', shortLabel: 'Easy', zone: 'Z1', sec: 30*60, hr: '110-128', color: colors.rest }, sportType, 'rest', personalProfile),
    withSportTarget({ label: 'Cooling-down', shortLabel: 'CD', zone: 'Z1', sec: 5*60, hr: '110-120', color: colors.z1 }, sportType, 'z1', personalProfile),
  ];
  if (type === 'DUUR') return [
    withSportTarget({ label: 'Warming-up', shortLabel: 'WU', zone: 'Z1', sec: 8*60, hr: '125-135', color: colors.z1 }, sportType, 'z1', personalProfile),
    withSportTarget({ label: 'Duurblok zone 2', shortLabel: 'Z2 Duur', zone: 'Z2', sec: 45*60, hr: '138-152', color: colors.z2 }, sportType, 'z2', personalProfile),
    withSportTarget({ label: 'Cooling-down', shortLabel: 'CD', zone: 'Z1', sec: 7*60, hr: '120-135', color: colors.z1 }, sportType, 'z1', personalProfile),
  ];
  if (type === 'THRESHOLD') return [
    withSportTarget({ label: 'Warming-up', shortLabel: 'WU', zone: 'Z1', sec: 10*60, hr: '125-138', color: colors.z1 }, sportType, 'z1', personalProfile),
    withSportTarget({ label: 'Tempo blok 1', shortLabel: 'Tempo 1', zone: 'Z4', sec: 12*60, hr: '162-170', color: colors.z4 }, sportType, 'z4', personalProfile),
    withSportTarget({ label: 'Actieve rust', shortLabel: 'Rust', zone: 'Z1', sec: 4*60, hr: '130-140', color: colors.z1 }, sportType, 'z1', personalProfile),
    withSportTarget({ label: 'Tempo blok 2', shortLabel: 'Tempo 2', zone: 'Z4', sec: 12*60, hr: '162-170', color: colors.z4 }, sportType, 'z4', personalProfile),
    withSportTarget({ label: 'Cooling-down', shortLabel: 'CD', zone: 'Z1', sec: 8*60, hr: '120-135', color: colors.z1 }, sportType, 'z1', personalProfile),
  ];
  if (type === 'VO2MAX') return [
    withSportTarget({ label: 'Warming-up', shortLabel: 'WU', zone: 'Z1', sec: 10*60, hr: '125-138', color: colors.z1 }, sportType, 'z1', personalProfile),
    ...Array(6).fill(0).flatMap(() => [
      withSportTarget({ label: 'VO2 interval', shortLabel: 'VO2', zone: 'Z5', sec: 3*60, hr: '175-185', color: colors.z5 }, sportType, 'z5', personalProfile),
      withSportTarget({ label: 'Herstel', shortLabel: 'rust', zone: 'Z1', sec: 3*60, hr: '130-140', color: colors.z1 }, sportType, 'z1', personalProfile),
    ]),
    withSportTarget({ label: 'Cooling-down', shortLabel: 'CD', zone: 'Z1', sec: 8*60, hr: '120-135', color: colors.z1 }, sportType, 'z1', personalProfile),
  ];
  if (type === 'SPRINT') return [
    withSportTarget({ label: 'Warming-up', shortLabel: 'WU', zone: 'Z1', sec: 10*60, hr: '125-138', color: colors.z1 }, sportType, 'z1', personalProfile),
    ...Array(10).fill(0).flatMap(() => [
      withSportTarget({ label: 'Sprint', shortLabel: 'SP', zone: 'Z5', sec: 30, hr: '> 180', color: colors.z5 }, sportType, 'z5', personalProfile),
      withSportTarget({ label: sportType === 'WALKING' ? 'Rustig wandelen' : 'Herstel', shortLabel: 'rust', zone: 'Z1', sec: 90, hr: '110-130', color: colors.rest }, sportType, 'rest', personalProfile),
    ]),
    withSportTarget({ label: 'Cooling-down', shortLabel: 'CD', zone: 'Z1', sec: 7*60, hr: '120-135', color: colors.z1 }, sportType, 'z1', personalProfile),
  ];
  return [];
}

window.WorkoutScreen = WorkoutScreen;
