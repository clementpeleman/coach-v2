// Shared workout draft builder for chat + workout surfaces.
(function () {
  const SPORT_OPTIONS = [
    { key: 'WALKING', label: 'Wandelen', shortLabel: 'Wandel', garminType: 'WALKING', metric: 'pace', targetLabel: 'Tempo' },
    { key: 'RUNNING', label: 'Hardlopen', shortLabel: 'Run', garminType: 'RUNNING', metric: 'pace', targetLabel: 'Tempo' },
    { key: 'CYCLING', label: 'Fietsen', shortLabel: 'Fiets', garminType: 'CYCLING', metric: 'speed', targetLabel: 'Snelheid' },
    { key: 'INDOOR_CYCLING', label: 'Indoor fietsen', shortLabel: 'Zwift', garminType: 'INDOOR_CYCLING', metric: 'speed', targetLabel: 'Snelheid' },
    { key: 'SWIMMING', label: 'Zwemmen', shortLabel: 'Zwem', garminType: 'LAP_SWIMMING', metric: 'pace', targetLabel: 'Tempo' },
  ];

  const SPORT_DURATION_MINUTES = {
    WALKING: { HERSTEL: 45, DUUR: 70, THRESHOLD: 50, VO2MAX: 42, SPRINT: 35 },
    RUNNING: { HERSTEL: 40, DUUR: 60, THRESHOLD: 46, VO2MAX: 54, SPRINT: 37 },
    CYCLING: { HERSTEL: 55, DUUR: 95, THRESHOLD: 72, VO2MAX: 62, SPRINT: 48 },
    INDOOR_CYCLING: { HERSTEL: 45, DUUR: 75, THRESHOLD: 60, VO2MAX: 52, SPRINT: 40 },
    SWIMMING: { HERSTEL: 28, DUUR: 42, THRESHOLD: 38, VO2MAX: 34, SPRINT: 30 },
  };

  const TYPE_LABELS = {
    HERSTEL: 'Herstel',
    DUUR: 'Duur',
    THRESHOLD: 'Drempel',
    VO2MAX: 'VO2 max',
    SPRINT: 'Sprints',
  };

  function buildDraft({ recoveryScore = 4, trainingProfile = null, previous = null } = {}) {
    const rec = window.FC_DATA.recommendedByRecovery[recoveryScore] || window.FC_DATA.recommendedByRecovery[4];
    const type = previous?.type || rec.type;
    const pattern = trainingProfile?.workout_patterns?.by_type?.[type];
    const sportType = previous?.sportType || pattern?.preferred_sport || sportFromRecommendation(rec.sport);
    const durationMin = previous?.durationMin || plannedDurationForSport(type, sportType, rec.duration, pattern);
    const blocks = fitBlocksToDuration(buildStructure(type, sportType), durationMin);
    return {
      id: previous?.id || `draft-${Date.now()}`,
      status: previous?.status || 'draft',
      source: previous?.source || 'auto',
      type,
      sportType,
      durationMin,
      intensityPct: previous?.intensityPct || 100,
      blocks,
      note: previous?.note || 'Gebaseerd op je herstel en sportprofiel.',
      updatedAt: new Date().toISOString(),
    };
  }

  function updateDraftFromText(draft, text, context = {}) {
    const current = draft || buildDraft(context);
    const lower = String(text || '').toLowerCase();
    const next = { ...current, source: 'coach', status: 'draft' };
    let rebuild = false;
    let changed = false;
    const notes = [];

    const sport = inferSport(lower);
    if (sport && sport !== next.sportType) {
      next.sportType = sport;
      next.durationMin = SPORT_DURATION_MINUTES[sport]?.[next.type] || next.durationMin;
      rebuild = true;
      changed = true;
      notes.push(`sport naar ${sportLabel(sport)}`);
    }

    const type = inferType(lower);
    if (type && type !== next.type) {
      next.type = type;
      next.durationMin = SPORT_DURATION_MINUTES[next.sportType]?.[type] || next.durationMin;
      rebuild = true;
      changed = true;
      notes.push(`type naar ${TYPE_LABELS[type].toLowerCase()}`);
    }

    const explicitDuration = inferDuration(lower);
    if (explicitDuration && explicitDuration !== next.durationMin) {
      next.durationMin = explicitDuration;
      rebuild = true;
      changed = true;
      notes.push(`${explicitDuration} minuten`);
    } else if (/\b(korter|compact|sneller klaar|minder lang)\b/.test(lower)) {
      next.durationMin = Math.max(20, next.durationMin - 10);
      rebuild = true;
      changed = true;
      notes.push('korter gemaakt');
    } else if (/\b(langer|meer volume|uitbreiden|extra lang)\b/.test(lower)) {
      next.durationMin = Math.min(150, next.durationMin + 10);
      rebuild = true;
      changed = true;
      notes.push('langer gemaakt');
    }

    const interval = lower.match(/\b(\d{1,2})\s*x\s*(\d{1,2})\s*(min|m|')\b/);
    if (interval && ['THRESHOLD', 'VO2MAX'].includes(next.type)) {
      next.blocks = buildCustomIntervals(next.type, next.sportType, Number(interval[1]), Number(interval[2]) * 60);
      next.durationMin = Math.round(next.blocks.reduce((sum, block) => sum + block.sec, 0) / 60);
      rebuild = false;
      changed = true;
      notes.push(`${interval[1]}x${interval[2]}min structuur`);
    }

    if (/\b(rustiger|makkelijker|conservatiever|lager|easy)\b/.test(lower)) {
      next.intensityPct = Math.max(90, (next.intensityPct || 100) - 5);
      changed = true;
      notes.push('intensiteit omlaag');
    }
    if (/\b(harder|zwaarder|scherper|intensiever|steviger)\b/.test(lower)) {
      next.intensityPct = Math.min(110, (next.intensityPct || 100) + 5);
      changed = true;
      notes.push('intensiteit omhoog');
    }

    if (rebuild) {
      next.blocks = fitBlocksToDuration(buildStructure(next.type, next.sportType), next.durationMin);
    }
    if (!changed) return { draft: current, changed: false, summary: null };
    next.updatedAt = new Date().toISOString();
    next.note = notes.length ? `Aangepast door coach: ${notes.join(', ')}.` : current.note;
    return { draft: next, changed: true, summary: next.note };
  }

  function approveDraft(draft) {
    if (!draft) return draft;
    return { ...draft, status: 'approved', approvedAt: new Date().toISOString(), updatedAt: new Date().toISOString() };
  }

  function inferSport(text) {
    if (/\b(zwift|indoor fiets|indoor cycling|rollen)\b/.test(text)) return 'INDOOR_CYCLING';
    if (/\b(fiets|fietsen|cycling|bike|biken|rit)\b/.test(text)) return 'CYCLING';
    if (/\b(zwem|zwemmen|swim|baantjes)\b/.test(text)) return 'SWIMMING';
    if (/\b(wandel|wandelen|walk|stappen)\b/.test(text)) return 'WALKING';
    if (/\b(loop|lopen|run|running|hardlopen)\b/.test(text)) return 'RUNNING';
    return null;
  }

  function inferType(text) {
    if (/\b(herstel|recovery|herstelloop|losfietsen)\b/.test(text)) return 'HERSTEL';
    if (/\b(duur|zone 2|z2|aeroob|endurance)\b/.test(text)) return 'DUUR';
    if (/\b(drempel|threshold|tempo)\b/.test(text)) return 'THRESHOLD';
    if (/\b(vo2|vo2max|interval|intervallen|4x4|3x3|6x3)\b/.test(text)) return 'VO2MAX';
    if (/\b(sprint|sprints|all-out|all out|30s)\b/.test(text)) return 'SPRINT';
    return null;
  }

  function inferDuration(text) {
    const hourMatch = text.match(/\b(\d+(?:[,.]\d+)?)\s*(u|uur|hour|hours)\b/);
    if (hourMatch) return Math.round(Number(hourMatch[1].replace(',', '.')) * 60);
    const minMatch = text.match(/\b(\d{2,3})\s*(min|m|minuten)\b/);
    if (minMatch) return Number(minMatch[1]);
    return null;
  }

  function sportFromRecommendation(sport) {
    const normalized = String(sport || '').toLowerCase();
    if (normalized.includes('fiets') || normalized.includes('cycling')) return 'CYCLING';
    if (normalized.includes('zwem') || normalized.includes('swim')) return 'SWIMMING';
    if (normalized.includes('wandel') || normalized.includes('walk')) return 'WALKING';
    return 'RUNNING';
  }

  function plannedDurationForSport(type, sportType, fallback, pattern) {
    const patternMatchesSport = pattern?.typical_duration_min && (!pattern.preferred_sport || pattern.preferred_sport === sportType);
    if (patternMatchesSport) return Math.round(pattern.typical_duration_min);
    return SPORT_DURATION_MINUTES[sportType]?.[type] || fallback || 45;
  }

  function buildStructure(type, sportType) {
    const colors = {
      rest: 'oklch(48% 0.05 220)',
      z1: 'oklch(55% 0.06 220)',
      z2: 'oklch(62% 0.10 145)',
      z4: 'oklch(75% 0.18 60)',
      z5: 'oklch(68% 0.22 25)',
    };
    const target = (block, zone) => ({ ...block, ...metricForSport(sportType, zone) });
    if (type === 'HERSTEL') return [
      target({ label: 'Warming-up', shortLabel: 'WU', zone: 'Z1', sec: 5*60, hr: '120-130', color: colors.z1 }, 'z1'),
      target({ label: sportType === 'WALKING' ? 'Rustige wandeling' : 'Easy blok', shortLabel: 'Easy', zone: 'Z1', sec: 30*60, hr: '110-128', color: colors.rest }, 'rest'),
      target({ label: 'Cooling-down', shortLabel: 'CD', zone: 'Z1', sec: 5*60, hr: '110-120', color: colors.z1 }, 'z1'),
    ];
    if (type === 'DUUR') return [
      target({ label: 'Warming-up', shortLabel: 'WU', zone: 'Z1', sec: 8*60, hr: '125-135', color: colors.z1 }, 'z1'),
      target({ label: 'Duurblok zone 2', shortLabel: 'Z2', zone: 'Z2', sec: 45*60, hr: '138-152', color: colors.z2 }, 'z2'),
      target({ label: 'Cooling-down', shortLabel: 'CD', zone: 'Z1', sec: 7*60, hr: '120-135', color: colors.z1 }, 'z1'),
    ];
    if (type === 'THRESHOLD') return buildCustomIntervals(type, sportType, 2, 12*60);
    if (type === 'VO2MAX') return buildCustomIntervals(type, sportType, 6, 3*60);
    if (type === 'SPRINT') return [
      target({ label: 'Warming-up', shortLabel: 'WU', zone: 'Z1', sec: 10*60, hr: '125-138', color: colors.z1 }, 'z1'),
      ...Array(10).fill(0).flatMap((_, index) => [
        target({ label: `Sprint ${index + 1}`, shortLabel: 'SP', zone: 'Z5', sec: 30, hr: '> 180', color: colors.z5 }, 'z5'),
        target({ label: 'Herstel', shortLabel: 'rust', zone: 'Z1', sec: 90, hr: '110-130', color: colors.rest }, 'rest'),
      ]),
      target({ label: 'Cooling-down', shortLabel: 'CD', zone: 'Z1', sec: 7*60, hr: '120-135', color: colors.z1 }, 'z1'),
    ];
    return [];
  }

  function buildCustomIntervals(type, sportType, count, workSec) {
    const colors = {
      z1: 'oklch(55% 0.06 220)',
      z4: 'oklch(75% 0.18 60)',
      z5: 'oklch(68% 0.22 25)',
    };
    const isThreshold = type === 'THRESHOLD';
    const workZone = isThreshold ? 'z4' : 'z5';
    const workLabel = isThreshold ? 'Tempo blok' : 'VO2 interval';
    const restSec = isThreshold ? 4*60 : Math.max(90, Math.min(3*60, workSec));
    const target = (block, zone) => ({ ...block, ...metricForSport(sportType, zone) });
    const blocks = [
      target({ label: 'Warming-up', shortLabel: 'WU', zone: 'Z1', sec: 10*60, hr: '125-138', color: colors.z1 }, 'z1'),
    ];
    for (let index = 0; index < count; index += 1) {
      blocks.push(target({
        label: `${workLabel} ${index + 1}`,
        shortLabel: isThreshold ? 'Tempo' : 'VO2',
        zone: isThreshold ? 'Z4' : 'Z5',
        sec: workSec,
        hr: isThreshold ? '162-170' : '175-185',
        color: isThreshold ? colors.z4 : colors.z5,
      }, workZone));
      if (index < count - 1) {
        blocks.push(target({ label: 'Herstel', shortLabel: 'rust', zone: 'Z1', sec: restSec, hr: '130-140', color: colors.z1 }, 'z1'));
      }
    }
    blocks.push(target({ label: 'Cooling-down', shortLabel: 'CD', zone: 'Z1', sec: 8*60, hr: '120-135', color: colors.z1 }, 'z1'));
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

  function fitBlocksToDuration(blocks, durationMin) {
    const targetSec = Math.max(5, Math.round(durationMin || 0)) * 60;
    const currentSec = blocks.reduce((sum, block) => sum + block.sec, 0);
    const diff = targetSec - currentSec;
    if (!blocks.length || Math.abs(diff) < 60) return blocks;
    const work = blocks.map((block, index) => ({ block, index })).filter(({ block }) => block.zone !== 'Z1');
    const targets = work.length ? work : blocks.map((block, index) => ({ block, index }));
    const targetIndexes = new Set(targets.map(({ index }) => index));
    const targetTotal = targets.reduce((sum, { block }) => sum + block.sec, 0) || currentSec;
    return blocks.map((block, index) => {
      if (!targetIndexes.has(index)) return block;
      const share = block.sec / targetTotal;
      return { ...block, sec: Math.max(block.zone === 'Z5' ? 20 : 60, Math.round(block.sec + diff * share)) };
    });
  }

  function sportLabel(sportType) {
    return SPORT_OPTIONS.find((sport) => sport.key === sportType)?.label || sportType;
  }

  function typeLabel(type) {
    return TYPE_LABELS[type] || type;
  }

  function targetForBlock(block, sportType) {
    const metric = SPORT_OPTIONS.find((sport) => sport.key === sportType)?.metric;
    return metric === 'speed' ? block.speed : block.pace;
  }

  window.FC_WORKOUT_PLAN = {
    SPORT_OPTIONS,
    TYPE_LABELS,
    buildDraft,
    updateDraftFromText,
    approveDraft,
    sportLabel,
    typeLabel,
    targetForBlock,
  };
})();
