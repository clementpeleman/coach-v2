// Shared utilities.
window.FC_UTILS = {
  fmtTime: (iso) => {
    const d = new Date(iso);
    return d.toLocaleTimeString('nl-BE', { hour: '2-digit', minute: '2-digit' });
  },
  fmtDate: (iso) => {
    const d = new Date(iso);
    return d.toLocaleDateString('nl-BE', { day: '2-digit', month: 'short' }).replace('.', '');
  },
  fmtDayName: (iso) => {
    const d = new Date(iso);
    return d.toLocaleDateString('nl-BE', { weekday: 'short' });
  },
  fmtDuration: (sec) => {
    if (!sec) return '–';
    const h = Math.floor(sec / 3600);
    const m = Math.floor((sec % 3600) / 60);
    if (h > 0) return `${h}u ${String(m).padStart(2,'0')}`;
    return `${m} min`;
  },
  fmtPace: (distM, durSec) => {
    if (!distM || !durSec) return '–';
    const km = distM / 1000;
    const minPerKm = durSec / 60 / km;
    const m = Math.floor(minPerKm);
    const s = Math.round((minPerKm - m) * 60);
    return `${m}:${String(s).padStart(2,'0')}/km`;
  },
  sportLabel: (type) => ({
    RUNNING: 'Hardlopen',
    CYCLING: 'Fietsen',
    INDOOR_CYCLING: 'Indoor fietsen',
    LAP_SWIMMING: 'Zwemmen',
    CARDIO_TRAINING: 'Wandelen',
    STRENGTH_TRAINING: 'Kracht',
    HIIT: 'HIIT',
  })[type] || type,
  sportIcon: (type) => ({
    RUNNING: '↗',
    CYCLING: '◯',
    INDOOR_CYCLING: '◌',
    LAP_SWIMMING: '~',
    CARDIO_TRAINING: '∙',
    STRENGTH_TRAINING: '▣',
    HIIT: '⚡',
  })[type] || '•',
  recoveryLabel: (s) => {
    if (s <= 1) return 'Uitgeput';
    if (s === 2) return 'Vermoeid';
    if (s === 3) return 'Stabiel';
    if (s === 4) return 'Goed';
    if (s === 5) return 'Sterk';
    return 'Topvorm';
  },
  recoveryAdvice: (s) => {
    if (s <= 1) return 'Rust vandaag. Korte wandeling max.';
    if (s === 2) return 'Lichte sessie. Geen intensiteit.';
    if (s === 3) return 'Aerobe duurtraining is prima.';
    if (s === 4) return 'Klaar voor tempo of drempel.';
    if (s === 5) return 'Intervallen mogen vandaag.';
    return 'Sprints of wedstrijdsessie kan.';
  },
  /** Garmin stress bands: rest <26, laag 26–50, matig 51–75, hoog 76–100 */
  stressLabel: (avgStress) => {
    if (avgStress == null || !Number.isFinite(Number(avgStress))) return 'geen data';
    const v = Number(avgStress);
    if (v < 26) return 'rust';
    if (v <= 50) return 'laag';
    if (v <= 75) return 'matig';
    return 'hoog';
  },
  trendFromImpact: (impact) => {
    if (typeof impact !== 'number' || !Number.isFinite(impact)) return 'flat';
    if (impact < -0.05) return 'down';
    if (impact > 0.05) return 'up';
    return 'flat';
  },
  hrvDeltaLabel: (hrv, baseline, deviationPct) => {
    if (hrv == null || baseline == null) return null;
    const delta = Math.round(hrv - baseline);
    const pct = deviationPct != null ? ` (${deviationPct > 0 ? '+' : ''}${deviationPct}%)` : '';
    const sign = delta > 0 ? '+' : '';
    return `${sign}${delta}ms vs baseline${pct}`;
  },
  hrvTrendInsight: (trend) => {
    if (!trend || trend.length < 3) return null;
    const first = trend.slice(0, Math.ceil(trend.length / 2));
    const second = trend.slice(Math.floor(trend.length / 2));
    const avg = (arr) => arr.reduce((s, v) => s + v, 0) / arr.length;
    const diff = avg(second) - avg(first);
    if (diff >= 3) {
      return 'HRV stijgt - autonoom herstel verbetert. Goed moment om op te bouwen.';
    }
    if (diff <= -3) {
      return 'HRV daalt - let op slaap en belasting. Houd intensiteit conservatief.';
    }
    return 'HRV stabiel - houd je huidige trainingsritme aan.';
  },
  sleepStageInsight: ({ deepSleepMin, remMin, awakeMin, sleepHours }) => {
    if (sleepHours == null && deepSleepMin == null) return null;
    const parts = [];
    if (deepSleepMin != null) {
      parts.push(`<b>Diepe slaap</b> ${deepSleepMin} min${deepSleepMin >= 60 ? ' - solide' : deepSleepMin >= 45 ? '' : ' - aan de lage kant'}.`);
    }
    if (remMin != null) {
      parts.push(`REM ${remMin} min.`);
    }
    if (awakeMin != null && awakeMin >= 15) {
      parts.push(`<b>Awake</b> ${awakeMin} min - lichte onderbrekingen in de nacht.`);
    } else if (awakeMin != null) {
      parts.push(`Awake ${awakeMin} min - rustige nacht.`);
    }
    return parts.join(' ');
  },
  formatApiError: (message) => {
    if (!message) return 'Er ging iets mis. Probeer opnieuw.';
    const m = String(message);
    if (m.includes('partner_registration_not_found') || m.includes('no user partner found')) {
      return 'Garmin is nog bezig met koppelen. Wacht even en vernieuw, of probeer opnieuw te verbinden.';
    }
    if (m.includes('GARMIN_REDIRECT_URI') || m.includes('GARMIN_CONSUMER')) {
      return 'Garmin is nog niet geconfigureerd op de server.';
    }
    if (m.includes('OPENAI_API_KEY')) return 'De coach-chat is tijdelijk niet beschikbaar.';
    if (m.includes('Internal Server Error') || m.includes('not configured')) {
      return 'Serverfout. Probeer het later opnieuw.';
    }
    if (m.includes('405') || m.includes('Not Allowed')) {
      return 'Verbinding met de server mislukt. Vernieuw de pagina.';
    }
    return m.replace(/^API\s+\S+\s+failed\s*\(\d+\):\s*/i, '').trim() || m;
  },
};
