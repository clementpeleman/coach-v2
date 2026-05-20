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
  })[type] || type,
  sportIcon: (type) => ({
    RUNNING: '↗',
    CYCLING: '◯',
    INDOOR_CYCLING: '◌',
    LAP_SWIMMING: '~',
    CARDIO_TRAINING: '∙',
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
  formatApiError: (message) => {
    if (!message) return 'Er ging iets mis. Probeer opnieuw.';
    const m = String(message);
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
