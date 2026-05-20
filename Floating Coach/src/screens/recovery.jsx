// Recovery assessment screen.
const { useEffect: useEffectR } = React;
const FCUR = window.FC_UTILS;

function RecoveryScreen({ recoveryScore, recoveryData, recoverySnapshot, onNavigate, embedded }) {
  const D = window.FC_DATA;
  const R = recoveryData || D.recovery;
  const activeDate = recoverySnapshot?.calendar_date
    ? new Date(`${recoverySnapshot.calendar_date}T12:00:00`)
    : new Date();
  const ringPct = recoveryScore / 6;
  const ringClass = recoveryScore <= 2 ? 'bad' : recoveryScore <= 3 ? 'warn' : '';
  const c = 2 * Math.PI * 100;
  const bodyBatteryAtWake = R.bodyBatteryAtWake ?? null;
  const bodyBatteryDisplay = bodyBatteryAtWake ?? R.bodyBatteryCurrent ?? R.bodyBattery ?? null;
  const bodyBatterySub = bodyBatteryAtWake == null && bodyBatteryDisplay != null ? "huidig" : "bij ontwaken";
  const hasRecentTraining = R.recentTrainingLoad != null || Boolean(R.hardestRecentActivity);
  const scoreBreakdown = buildRecoveryScoreBreakdown(recoveryScore, R, recoverySnapshot);

  const sourceLabel = recoverySnapshot?.source === 'live'
    ? 'Van Garmin'
    : (recoverySnapshot?.source === 'stale-live' ? 'Garmin (cache)' : 'Geschat (demo)');

  return (
    <div data-screen-label="Recovery assessment" className="col" style={{ gap: embedded ? 16 : 24 }}>
      {!embedded && (
      <div className="screen-head">
        <div>
          <div className="label" style={{ marginBottom: 10 }}>
            Hersteldiagnose · {activeDate.toLocaleDateString('nl-BE', { day: '2-digit', month: 'long' })}
          </div>
          <h1>Herstel.<br/><em>Hoe vandaag te trainen.</em></h1>
        </div>
        <div className="meta">
          <div>Op basis van slaap, HRV, stress & recente training</div>
          <div className="mono" style={{ marginTop: 4, color: 'var(--ink)' }}>
            <b>0—6 schaal</b> · {sourceLabel}
          </div>
        </div>
      </div>
      )}
      {embedded && (
        <div className="mono" style={{ fontSize: 10, color: 'var(--ink-4)', textTransform: 'uppercase', letterSpacing: '.14em' }}>
          Bron: {sourceLabel}
        </div>
      )}

      {/* Hero ring + advice */}
      <div className="card dark" style={{ padding: '32px 36px', position: 'relative', overflow: 'hidden' }}>
        <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 3,
                      background: 'var(--accent)' }} />
        <div style={{ display: 'grid', gridTemplateColumns: '260px 1fr', gap: 36, alignItems: 'center' }}>
          {/* Ring */}
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
            <div style={{ position: 'relative', width: 240, height: 240 }}>
              <svg width="240" height="240" style={{ transform: 'rotate(-90deg)' }}>
                <circle cx="120" cy="120" r="100" fill="none" stroke="oklch(25% 0.005 100)" strokeWidth="14" />
                <circle cx="120" cy="120" r="100" fill="none"
                  stroke={ringClass === 'bad' ? 'var(--bad)' : ringClass === 'warn' ? 'var(--warn)' : 'var(--accent)'}
                  strokeWidth="14" strokeLinecap="round"
                  strokeDasharray={c} strokeDashoffset={c * (1 - ringPct)}
                  style={{ transition: 'stroke-dashoffset .6s ease' }} />
              </svg>
              <div style={{ position: 'absolute', inset: 0, display: 'flex',
                            flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
                <span style={{ color: '#fff', fontSize: 96, fontWeight: 500,
                  letterSpacing: '-.04em', lineHeight: 1 }}>{recoveryScore}</span>
                <span className="mono" style={{ fontSize: 12, color: 'oklch(72% 0.01 100)',
                  textTransform: 'uppercase', letterSpacing: '.16em' }}>uit 6</span>
              </div>
            </div>
            <div className="mono" style={{ marginTop: 18, fontSize: 12, color: 'var(--accent)',
              textTransform: 'uppercase', letterSpacing: '.18em', fontWeight: 500 }}>
              {FCUR.recoveryLabel(recoveryScore)}
            </div>
          </div>

          {/* Advice */}
          <div>
            <div className="mono" style={{ fontSize: 10, color: 'oklch(70% 0.01 100)',
              textTransform: 'uppercase', letterSpacing: '.16em', marginBottom: 10 }}>
              Aanbeveling
            </div>
            <p style={{ fontSize: 26, lineHeight: 1.35, color: '#fff',
                        letterSpacing: '-.015em', margin: 0, maxWidth: 540 }}>
              {FCUR.recoveryAdvice(recoveryScore)}
            </p>

            {/* Scale row */}
            <div style={{ marginTop: 28 }}>
              <div className="mono" style={{ fontSize: 10, color: 'oklch(70% 0.01 100)',
                textTransform: 'uppercase', letterSpacing: '.16em', marginBottom: 10 }}>
                Herstelschaal
              </div>
              <div style={{ display: 'flex', gap: 5 }}>
                {[0,1,2,3,4,5,6].map(n => {
                  const active = n === recoveryScore;
                  return (
                    <div key={n} style={{
                      flex: 1, padding: '10px 6px', textAlign: 'center',
                      borderRadius: 8,
                      background: active ? 'var(--accent)' : 'oklch(20% 0.005 100)',
                      color: active ? 'var(--accent-ink)' : 'oklch(72% 0.01 100)',
                      transition: 'all .2s',
                    }}>
                      <div className="mono" style={{ fontSize: 18, fontWeight: 600 }}>{n}</div>
                      <div className="mono" style={{ fontSize: 9,
                        textTransform: 'uppercase', letterSpacing: '.1em', marginTop: 2 }}>
                        {['Uitgep.','Verm.','Zwak','Stabiel','Goed','Sterk','Top'][n]}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            <div style={{ display: 'flex', gap: 10, marginTop: 28 }}>
              <button className="btn accent lg" onClick={() => onNavigate('workout')}>
                Bekijk aanbevolen training <span className="arrow">→</span>
              </button>
              <button className="btn ghost" onClick={() => window.dispatchEvent(new CustomEvent('fc-open-coach-orb'))}
                style={{ color: '#fff', borderColor: 'oklch(35% 0.005 100)' }}>
                Vraag de coach
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Inputs into the score */}
      <div className="grid-4">
        <InputCard label="Slaap" value={`${R.sleepScore ?? '–'}`} unit={R.sleepScore == null ? "" : "/100"}
          sub={R.sleepHours ? `${R.sleepHours.toFixed(1)}u totaal` : "Geen slaapdata"}
          impact={scoreBreakdown.impacts.sleep} />
        <InputCard label="HRV overnacht" value={`${R.hrvOvernight ?? '–'}`} unit={R.hrvOvernight == null ? "" : "ms"}
          sub="bij gemiddelde" impact={scoreBreakdown.impacts.hrv} trend="flat" />
        <InputCard label="Stress (avg 24h)" value={`${R.avgStress ?? '–'}`} unit={R.avgStress == null ? "" : "/100"}
          sub="laag-gemiddeld" impact={scoreBreakdown.impacts.stress} trend="down" />
        <InputCard label="Body Battery" value={`${bodyBatteryDisplay ?? '–'}`} unit={bodyBatteryDisplay == null ? "" : "%"}
          sub={bodyBatterySub} impact={scoreBreakdown.impacts.bodyBattery} trend="up" />
        {hasRecentTraining && (
          <InputCard label="Recente training" value={`${R.recentTrainingLoad ?? '–'}`} unit={R.recentTrainingLoad == null ? "" : "load"}
            sub={R.hardestRecentActivity ? `${R.hardestRecentActivity.activity_name || 'Laatste sessie'} · ${R.recentTrainingLabel}` : "Laatste 48 uur"}
            impact={scoreBreakdown.impacts.recentTraining}
            trend={(R.recentTrainingPenalty || 0) >= 0.8 ? "down" : "flat"} />
        )}
      </div>

      <ScoreBreakdownCard breakdown={scoreBreakdown} bodyBatteryAtWake={bodyBatteryAtWake} />

      {R.hardestRecentActivity && (
        <div className="card" style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <div style={{ width: 42, height: 42, borderRadius: 10, background: 'var(--bg-soft)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontFamily: "'JetBrains Mono', monospace", fontWeight: 700 }}>
            {FCUR.sportIcon(R.hardestRecentActivity.activity_type)}
          </div>
          <div style={{ flex: 1 }}>
            <div className="label" style={{ marginBottom: 4 }}>Waarom deze score?</div>
            <div style={{ fontSize: 14, color: 'var(--ink-2)', lineHeight: 1.45 }}>
              Recente belasting weegt mee: <b>{R.hardestRecentActivity.activity_name || FCUR.sportLabel(R.hardestRecentActivity.activity_type)}</b>
              {' '}({R.hardestRecentActivity.duration_minutes} min, gem. HR {R.hardestRecentActivity.average_heart_rate ?? '–'},
              max HR {R.hardestRecentActivity.max_heart_rate ?? '–'}) verlaagt je score tijdelijk met
              {' '}<b>{(R.recentTrainingPenalty || 0).toFixed(1)}</b> punt.
            </div>
          </div>
        </div>
      )}

      {/* Sleep detail + HRV trend */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
        <SleepBreakdown recoveryData={R} />
        <HRVTrend recoveryData={R} />
      </div>
    </div>
  );
}

function buildRecoveryScoreBreakdown(recoveryScore, metrics = {}, snapshot = {}) {
  const model = snapshot?.score_model || {};
  const inputs = model.inputs || snapshot?.scoreInputs || {};
  const hasScoreInputs = Boolean(model.inputs || snapshot?.scoreInputs);
  const staleSignals = model.stale_signals || snapshot?.staleSignals || [];
  const confidence = model.confidence || snapshot?.scoreConfidence || 'medium';
  const version = model.version || 'current_readiness_v3';
  const rows = [];
  const impacts = {
    sleep: null,
    stress: null,
    bodyBattery: null,
    hrv: null,
    recentTraining: null,
  };
  let rawScore = 3.0;

  const addRow = (key, label, value, formula, delta, note) => {
    if (typeof delta === 'number' && Number.isFinite(delta)) {
      rawScore += delta;
      impacts[key] = delta;
    }
    rows.push({ key, label, value, formula, delta, note });
  };

  const sleepScore = numberOrNull(inputs.sleepScore ?? metrics.sleepScore);
  const sleepHours = numberOrNull(inputs.sleepHours ?? metrics.sleepHours);
  if (sleepScore != null) {
    addRow(
      'sleep',
      'Slaapscore',
      `${Math.round(sleepScore)}/100`,
      `(${Math.round(sleepScore)} - 70) / 15`,
      (sleepScore - 70) / 15,
      'Slaapscore krijgt voorrang op alleen slaapduur.',
    );
  } else if (sleepHours != null) {
    addRow(
      'sleep',
      'Slaapduur',
      `${sleepHours.toFixed(1)}u`,
      `(${sleepHours.toFixed(1)} - 7.0) / 1.5`,
      (sleepHours - 7) / 1.5,
      'Geen slaapscore gevonden, daarom telt duur mee.',
    );
  } else {
    addRow('sleep', 'Slaap', 'ontbreekt', 'niet meegeteld', null, 'Geen slaapscore of slaapduur beschikbaar.');
  }

  const avgStress = numberOrNull(inputs.avgStress ?? metrics.avgStress);
  if (avgStress != null) {
    addRow(
      'stress',
      'Stress 24u',
      `${Math.round(avgStress)}/100`,
      `(45 - ${Math.round(avgStress)}) / 20`,
      (45 - avgStress) / 20,
      'Lager dan 45 helpt, hoger dan 45 drukt de score.',
    );
  } else {
    addRow('stress', 'Stress 24u', 'ontbreekt', 'niet meegeteld', null, 'Geen recente stressreeks beschikbaar.');
  }

  const bodyBatteryCurrent = numberOrNull(
    hasScoreInputs ? inputs.bodyBatteryCurrent : (inputs.bodyBatteryCurrent ?? metrics.bodyBatteryCurrent ?? metrics.bodyBattery),
  );
  const measuredBodyBatteryCurrent = numberOrNull(metrics.bodyBatteryCurrent ?? metrics.bodyBattery);
  if (bodyBatteryCurrent != null) {
    addRow(
      'bodyBattery',
      'Body Battery huidig',
      `${Math.round(bodyBatteryCurrent)}%`,
      `(${Math.round(bodyBatteryCurrent)} - 50) / 25`,
      (bodyBatteryCurrent - 50) / 25,
      'Dit is de huidige waarde. Body Battery bij ontwaken is alleen display.',
    );
  } else {
    const staleNote = staleSignals.some((signal) => String(signal).startsWith('bodyBatteryCurrent_'))
      ? 'Huidige Body Battery is stale of ontbreekt en telt daarom niet mee.'
      : 'Geen huidige Body Battery beschikbaar voor de score.';
    addRow(
      'bodyBattery',
      'Body Battery huidig',
      measuredBodyBatteryCurrent != null ? `${Math.round(measuredBodyBatteryCurrent)}% gemeten` : 'ontbreekt',
      'niet meegeteld',
      null,
      staleNote,
    );
  }

  const hrv = numberOrNull(inputs.hrvOvernight ?? metrics.hrvOvernight);
  const hrvBaseline = numberOrNull(inputs.hrvBaselineMs ?? metrics.hrvBaselineMs);
  const hrvDevPct = numberOrNull(inputs.hrvDeviationPct ?? metrics.hrvDeviationPct);
  if (hrv != null) {
    if (hrvBaseline != null) {
      const denom = Math.max(hrvBaseline * 0.15, 8);
      const delta = Math.max(-1, Math.min(1, ((hrv - hrvBaseline) / denom) * 0.4));
      addRow(
        'hrv',
        'HRV overnacht',
        `${Math.round(hrv)} ms (baseline ${Math.round(hrvBaseline)} ms${hrvDevPct != null ? `, ${hrvDevPct > 0 ? '+' : ''}${hrvDevPct}%` : ''})`,
        `clamp(((${hrv} - ${Math.round(hrvBaseline)}) / ${denom.toFixed(1)}) * 0.4)`,
        delta,
        'v4: afwijking t.o.v. je 14-nachten mediaan.',
      );
    } else {
      addRow(
        'hrv',
        'HRV overnacht',
        `${Math.round(hrv)} ms`,
        `(${Math.round(hrv)} - 45) / 35`,
        (hrv - 45) / 35,
        'Te weinig HRV-historie: lichte fallback t.o.v. 45 ms.',
      );
    }
  } else {
    addRow('hrv', 'HRV overnacht', 'ontbreekt', 'niet meegeteld', null, 'Geen HRV-samenvatting beschikbaar.');
  }

  const recentTrainingPenalty = numberOrNull(inputs.recentTrainingPenalty ?? metrics.recentTrainingPenalty) || 0;
  addRow(
    'recentTraining',
    'Recente training',
    recentTrainingPenalty > 0 ? `${recentTrainingPenalty.toFixed(1)} punt` : 'geen penalty',
    recentTrainingPenalty > 0 ? `-${recentTrainingPenalty.toFixed(1)}` : '0',
    -recentTrainingPenalty,
    'Belasting van de laatste 48 uur verlaagt je readiness tijdelijk.',
  );

  const rounded = clampRecoveryScore(Math.round(rawScore));
  const caps = recoveryCaps(bodyBatteryCurrent, recentTrainingPenalty);
  if (bodyBatteryCurrent == null && recentTrainingPenalty >= 0.4) {
    caps.push({
      label: 'Body Battery huidig ontbreekt of is stale bij recente belasting',
      max: 3,
    });
  }
  const capped = caps.reduce((score, cap) => Math.min(score, cap.max), rounded);
  const finalScore = hasScoreInputs && Number.isFinite(recoveryScore) ? recoveryScore : capped;

  return {
    base: 3.0,
    rows,
    impacts,
    rawScore,
    rounded,
    capped,
    finalScore,
    caps,
    confidence,
    staleSignals,
    version,
    hasScoreInputs,
  };
}

function numberOrNull(value) {
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

function clampRecoveryScore(value) {
  return Math.max(0, Math.min(6, value));
}

function recoveryCaps(bodyBatteryCurrent, recentTrainingPenalty) {
  const caps = [];
  if (bodyBatteryCurrent != null) {
    if (bodyBatteryCurrent <= 15) {
      caps.push({ label: 'Body Battery huidig <= 15', max: 2 });
    } else if (bodyBatteryCurrent <= 25) {
      caps.push({ label: 'Body Battery huidig <= 25', max: 3 });
    } else if (bodyBatteryCurrent <= 35 && recentTrainingPenalty >= 0.8) {
      caps.push({ label: 'Body Battery huidig <= 35 met recente belasting', max: 3 });
    }
  }
  if (recentTrainingPenalty >= 1.1) {
    caps.push({ label: 'Zware recente sessie binnen 48 uur', max: 3 });
  }
  if (recentTrainingPenalty >= 1.1 && bodyBatteryCurrent != null && bodyBatteryCurrent <= 25) {
    caps.push({ label: 'Zware recente sessie + lage huidige Body Battery', max: 2 });
  }
  return caps;
}

function formatScoreDelta(delta) {
  if (typeof delta !== 'number' || !Number.isFinite(delta)) return 'niet meegeteld';
  if (Math.abs(delta) < 0.05) return '0.0';
  return `${delta > 0 ? '+' : ''}${delta.toFixed(1)}`;
}

function ScoreBreakdownCard({ breakdown, bodyBatteryAtWake }) {
  const confidenceColor = breakdown.confidence === 'high'
    ? 'var(--good)'
    : breakdown.confidence === 'low'
      ? 'var(--warn)'
      : 'oklch(78% 0.11 80)';
  const finalLabel = breakdown.hasScoreInputs ? 'Eindscore' : 'Berekend';
  const finalSub = breakdown.caps.length > 0
    ? 'na caps'
    : breakdown.finalScore !== breakdown.rounded
      ? 'appscore'
      : 'geen cap';

  return (
    <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
      <div style={{
        padding: '22px 24px 18px',
        display: 'flex',
        justifyContent: 'space-between',
        gap: 18,
        alignItems: 'start',
        borderBottom: '1px solid var(--line)',
      }}>
        <div>
          <div className="label" style={{ marginBottom: 8 }}>Scoreberekening</div>
          <h2>Hoe je herstelscore ontstaat</h2>
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', justifyContent: 'flex-end' }}>
          <span className="mono" style={{
            fontSize: 10,
            letterSpacing: '.12em',
            textTransform: 'uppercase',
            padding: '7px 10px',
            borderRadius: 999,
            background: 'var(--bg-soft)',
            color: 'var(--ink-3)',
            whiteSpace: 'nowrap',
          }}>
            {breakdown.version}
          </span>
          <span className="mono" style={{
            fontSize: 10,
            letterSpacing: '.12em',
            textTransform: 'uppercase',
            padding: '7px 10px',
            borderRadius: 999,
            background: 'var(--bg-soft)',
            color: confidenceColor,
            whiteSpace: 'nowrap',
          }}>
            vertrouwen {breakdown.confidence}
          </span>
        </div>
      </div>

      <div style={{ padding: 24 }}>
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(4, minmax(0, 1fr))',
          gap: 12,
          marginBottom: 20,
        }}>
          <ScoreStep label="Start" value={breakdown.base.toFixed(1)} sub="neutraal punt" />
          <ScoreStep label="Ruw" value={breakdown.rawScore.toFixed(2)} sub="na signalen" />
          <ScoreStep label="Afgerond" value={`${breakdown.rounded}/6`} sub="voor caps" />
          <ScoreStep label={finalLabel} value={`${breakdown.finalScore}/6`} sub={finalSub} accent />
        </div>

        <div style={{ display: 'grid', gap: 8 }}>
          {breakdown.rows.map((row) => (
            <ScoreBreakdownRow key={row.key} row={row} />
          ))}
        </div>

        {breakdown.caps.length > 0 && (
          <div style={{
            marginTop: 18,
            padding: 14,
            borderRadius: 12,
            background: 'oklch(96% 0.04 70)',
            border: '1px solid oklch(88% 0.07 70)',
          }}>
            <div className="label" style={{ color: 'oklch(46% 0.07 70)', marginBottom: 8 }}>Caps toegepast</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              {breakdown.caps.map((cap, index) => (
                <span key={`${cap.label}-${index}`} className="mono" style={{
                  fontSize: 11,
                  color: 'var(--ink)',
                  padding: '7px 9px',
                  borderRadius: 999,
                  background: '#fff',
                  border: '1px solid oklch(86% 0.04 70)',
                }}>
                  {cap.label}: max {cap.max}/6
                </span>
              ))}
            </div>
          </div>
        )}

        {breakdown.staleSignals.length > 0 && (
          <div style={{ marginTop: 14, fontSize: 13, lineHeight: 1.5, color: 'var(--ink-3)' }}>
            <b>Let op:</b> stale of ontbrekende signalen: {breakdown.staleSignals.join(', ')}.
          </div>
        )}

        <div style={{ marginTop: 14, fontSize: 13, lineHeight: 1.5, color: 'var(--ink-3)' }}>
          Body Battery bij ontwaken{bodyBatteryAtWake != null ? ` (${bodyBatteryAtWake}%)` : ''} wordt alleen getoond als context.
          De score gebruikt Body Battery huidig wanneer die recent genoeg is.
        </div>
        {!breakdown.hasScoreInputs && (
          <div style={{ marginTop: 8, fontSize: 13, lineHeight: 1.5, color: 'var(--ink-4)' }}>
            Deze demo/fallback-data bevat geen backend-scoremodel. Bij live Garmin-data gebruikt deze kaart de exacte score-inputs uit de API.
          </div>
        )}
      </div>
    </div>
  );
}

function ScoreStep({ label, value, sub, accent }) {
  return (
    <div style={{
      borderRadius: 12,
      background: accent ? 'var(--accent)' : 'var(--bg-soft)',
      color: accent ? 'var(--accent-ink)' : 'var(--ink)',
      padding: '14px 16px',
      minWidth: 0,
    }}>
      <div className="label" style={{ color: accent ? 'var(--accent-ink)' : 'var(--ink-4)' }}>{label}</div>
      <div className="mono" style={{ marginTop: 8, fontSize: 24, fontWeight: 600 }}>{value}</div>
      <div className="mono" style={{
        marginTop: 4,
        fontSize: 10,
        color: accent ? 'var(--accent-ink)' : 'var(--ink-4)',
        letterSpacing: '.08em',
      }}>{sub}</div>
    </div>
  );
}

function ScoreBreakdownRow({ row }) {
  const isMissing = typeof row.delta !== 'number' || !Number.isFinite(row.delta);
  const positive = !isMissing && row.delta > 0.05;
  const negative = !isMissing && row.delta < -0.05;
  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: '1.15fr .9fr 1.2fr auto',
      gap: 14,
      alignItems: 'center',
      padding: '12px 0',
      borderBottom: '1px solid var(--line)',
    }}>
      <div>
        <div style={{ fontSize: 14, fontWeight: 600 }}>{row.label}</div>
        <div style={{ fontSize: 12, color: 'var(--ink-4)', marginTop: 3, lineHeight: 1.35 }}>{row.note}</div>
      </div>
      <div className="mono" style={{ fontSize: 13, color: 'var(--ink-2)' }}>{row.value}</div>
      <div className="mono" style={{ fontSize: 12, color: 'var(--ink-4)' }}>{row.formula}</div>
      <div className="mono" style={{
        fontSize: 13,
        fontWeight: 700,
        color: positive ? 'var(--good)' : negative ? 'var(--warn)' : 'var(--ink-4)',
        whiteSpace: 'nowrap',
      }}>
        {formatScoreDelta(row.delta)}
      </div>
    </div>
  );
}

function InputCard({ label, value, unit, sub, contribution, trend, impact }) {
  const arrow = trend === 'down' ? '↓' : trend === 'up' ? '↑' : trend === 'flat' ? '→' : null;
  const hasImpact = typeof impact === 'number' && Number.isFinite(impact);
  const inactive = impact == null && contribution == null;
  const barWidth = hasImpact
    ? Math.max(6, Math.min(100, Math.round(Math.abs(impact) * 42)))
    : (contribution ?? 0);
  const barColor = !hasImpact
    ? 'var(--ink-3)'
    : impact < -0.05
      ? 'var(--warn)'
      : impact > 0.05
        ? 'var(--good)'
        : 'var(--ink-3)';
  const impactLabel = hasImpact ? formatScoreDelta(impact) : (inactive ? 'niet meegeteld' : `${contribution}%`);
  return (
    <div className="card">
      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
        <span className="label">{label}</span>
        {arrow && <span className="mono" style={{ fontSize: 12, color: 'var(--ink-3)' }}>{arrow}</span>}
      </div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 4, marginTop: 8 }}>
        <span className="stat-big mono">{value}</span>
        <span className="stat-unit">{unit}</span>
      </div>
      <div className="mono" style={{ fontSize: 11, color: 'var(--ink-4)', marginTop: 6 }}>{sub}</div>
      {/* Score impact bar */}
      <div style={{ marginTop: 14, display: 'flex', alignItems: 'center', gap: 8 }}>
        <div style={{ flex: 1, height: 4, background: 'var(--bg-soft)', borderRadius: 2 }}>
          <div style={{ height: '100%', width: `${barWidth}%`,
                        background: barColor, borderRadius: 2 }}></div>
        </div>
        <span className="mono" style={{ fontSize: 10, color: 'var(--ink-4)',
          letterSpacing: '.08em', whiteSpace: 'nowrap' }}>{impactLabel}</span>
      </div>
    </div>
  );
}

function SleepBreakdown({ recoveryData }) {
  const D = window.FC_DATA;
  const R = recoveryData || D.recovery;
  const total = R.deepSleepMin + R.remMin + R.lightMin + R.awakeMin;
  const stages = [
    { label: 'Diep', min: R.deepSleepMin || 0, color: 'oklch(45% 0.10 250)' },
    { label: 'REM',  min: R.remMin || 0,       color: 'oklch(60% 0.16 280)' },
    { label: 'Licht', min: R.lightMin || 0,    color: 'oklch(75% 0.10 240)' },
    { label: 'Awake', min: R.awakeMin || 0,    color: 'oklch(85% 0.06 60)' },
  ];

  return (
    <div className="card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start' }}>
        <h2>Slaap</h2>
        <div style={{ textAlign: 'right' }}>
          <div className="mono" style={{ fontSize: 24, fontWeight: 500 }}>
            {R.sleepHours ? R.sleepHours.toFixed(1) : '–'}<span style={{ fontSize: 13, color: 'var(--ink-4)' }}> uur</span>
          </div>
          <div className="mono" style={{ fontSize: 11, color: 'var(--ink-4)',
            textTransform: 'uppercase', letterSpacing: '.12em', marginTop: 2 }}>
            score {R.sleepScore ?? '–'}/100
          </div>
        </div>
      </div>

      {/* Stack bar */}
      <div style={{ marginTop: 22, height: 14, borderRadius: 7,
                    overflow: 'hidden', display: 'flex' }}>
        {stages.map((s, i) => (
          <div key={s.label} title={`${s.label} · ${s.min} min`}
            style={{ flex: s.min, background: s.color }}></div>
        ))}
      </div>

      <div style={{ marginTop: 18, display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 12 }}>
        {stages.map(s => (
          <div key={s.label}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <div style={{ width: 8, height: 8, borderRadius: 2, background: s.color }}></div>
              <span className="mono" style={{ fontSize: 10, color: 'var(--ink-4)',
                textTransform: 'uppercase', letterSpacing: '.12em' }}>{s.label}</span>
            </div>
            <div className="mono" style={{ fontSize: 17, fontWeight: 500, marginTop: 4,
              fontVariantNumeric: 'tabular-nums' }}>
              {Math.floor(s.min / 60)}u {s.min % 60}m
            </div>
            <div className="mono" style={{ fontSize: 10, color: 'var(--ink-4)' }}>
              {total ? Math.round((s.min / total) * 100) : 0}%
            </div>
          </div>
        ))}
      </div>

      <div style={{ marginTop: 20, padding: 14, background: 'var(--bg-soft)',
                    borderRadius: 12 }}>
        <p style={{ margin: 0, fontSize: 13, lineHeight: 1.5, color: 'var(--ink-2)' }}>
          <b>Diepe slaap</b> 92 min is sterk — boven je gemiddelde van 78 min.
          REM ligt op koers. <b>Awake</b> 18 min suggereert dat je rond 03:40 even wakker bent geweest.
        </p>
      </div>
    </div>
  );
}

function HRVTrend({ recoveryData }) {
  const D = window.FC_DATA;
  const R = recoveryData || D.recovery;
  const w = 460, h = 140, pad = 16;
  const trend = (R.hrvTrend && R.hrvTrend.length) ? R.hrvTrend : D.recovery.hrvTrend;
  const max = Math.max(...trend) + 4;
  const min = Math.min(...trend) - 4;
  const range = max - min;

  const pts = trend.map((v, i) => {
    const x = pad + (i / Math.max(1, trend.length - 1)) * (w - pad * 2);
    const y = h - pad - ((v - min) / range) * (h - pad * 2);
    return [x, y, v];
  });
  const path = pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${p[0]},${p[1]}`).join(' ');

  return (
    <div className="card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start' }}>
        <h2>HRV trend</h2>
        <div style={{ textAlign: 'right' }}>
          <div className="mono" style={{ fontSize: 24, fontWeight: 500 }}>
            {R.hrvOvernight ?? '–'}<span style={{ fontSize: 13, color: 'var(--ink-4)' }}> ms</span>
          </div>
          <div className="mono" style={{ fontSize: 11, color: 'var(--good)',
            textTransform: 'uppercase', letterSpacing: '.12em', marginTop: 2 }}>
            +4ms vs 7d
          </div>
        </div>
      </div>

      <svg viewBox={`0 0 ${w} ${h}`} style={{ width: '100%', height: 140, marginTop: 14, display: 'block' }}>
        {/* Bands */}
        <rect x={pad} y={pad} width={w - pad*2} height={(h-pad*2)*0.33} fill="var(--bg-soft)" opacity=".5" />
        <line x1={pad} x2={w-pad} y1={h - pad - (((R.hrvOvernight || min) - 4 - min)/range)*(h-pad*2)}
              y2={h - pad - (((R.hrvOvernight || min) - 4 - min)/range)*(h-pad*2)}
              stroke="var(--ink-4)" strokeDasharray="2 4" />
        <path d={path} fill="none" stroke="var(--ink)" strokeWidth="2" />
        {/* Filled area */}
        <path d={`${path} L ${pts[pts.length-1][0]},${h-pad} L ${pts[0][0]},${h-pad} Z`}
              fill="var(--accent)" opacity=".18" />
        {pts.map((p, i) => (
          <circle key={i} cx={p[0]} cy={p[1]} r="3" fill="var(--accent)" stroke="var(--ink)" strokeWidth="1.5" />
        ))}
      </svg>

      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 6 }}>
        {['ma','di','wo','do','vr','za','zo'].map((d, i) => (
          <span key={i} className="mono" style={{ fontSize: 10, color: 'var(--ink-4)',
            textTransform: 'uppercase', letterSpacing: '.1em' }}>{d}</span>
        ))}
      </div>

      <div style={{ marginTop: 16, padding: 14, background: 'var(--bg-soft)', borderRadius: 12 }}>
        <p style={{ margin: 0, fontSize: 13, lineHeight: 1.5, color: 'var(--ink-2)' }}>
          HRV stijgt over de week heen — een teken dat je <b>autonome herstel</b> verbetert.
          Goed moment om de intensiteit op te bouwen.
        </p>
      </div>
    </div>
  );
}

window.RecoveryScreen = RecoveryScreen;
