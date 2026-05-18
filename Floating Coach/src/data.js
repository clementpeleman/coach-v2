// Mock data for Floating Coach prototype.
// Shapes mirror the actual API contracts in webapp/src/lib/api.ts.

window.FC_DATA = (() => {
  const today = new Date('2026-05-14T18:24:00');

  // Recovery score 0-6, sleep & stress
  const recovery = {
    score: 4,                 // tweakable
    sleepScore: 78,
    sleepHours: 7.2,
    deepSleepMin: 92,
    remMin: 86,
    lightMin: 254,
    awakeMin: 18,
    avgStress: 31,           // 0-100
    bodyBattery: 78,         // waking Body Battery
    bodyBatteryAtWake: 78,
    bodyBatteryCurrent: 20,
    hrvOvernight: 58,        // ms
    restingHr: 48,
    hrvTrend: [52, 49, 55, 60, 56, 61, 58],
    stressTrend: [42, 38, 35, 40, 33, 30, 31],
  };

  // Today's recommended workout (changes based on recovery)
  const recommendedByRecovery = {
    0: { type: 'HERSTEL', dutch: 'Herstel', sport: 'Wandelen', duration: 40, intensity: 'Zeer laag', desc: 'Korte herstelwandeling. Hartslag onder 120.', color: 'rest' },
    1: { type: 'HERSTEL', dutch: 'Herstel', sport: 'Wandelen', duration: 45, intensity: 'Zeer laag', desc: 'Actief herstel. Body Battery aanvullen.', color: 'rest' },
    2: { type: 'HERSTEL', dutch: 'Licht herstel', sport: 'Fietsen', duration: 50, intensity: 'Laag', desc: 'Lichte aerobe sessie, zone 1.', color: 'rest' },
    3: { type: 'DUUR', dutch: 'Duurloop', sport: 'Hardlopen', duration: 60, intensity: 'Gematigd', desc: 'Comfortabele duurloop in zone 2.', color: 'endurance' },
    4: { type: 'THRESHOLD', dutch: 'Tempo', sport: 'Hardlopen', duration: 55, intensity: 'Gemiddeld-hoog', desc: '2× 15 min op drempel. Stabiele inspanning.', color: 'tempo' },
    5: { type: 'VO2MAX', dutch: 'Intervallen', sport: 'Hardlopen', duration: 50, intensity: 'Hoog', desc: '6× 3 min VO2max. Volledig herstel tussendoor.', color: 'vo2' },
    6: { type: 'SPRINT', dutch: 'Sprints', sport: 'Hardlopen', duration: 35, intensity: 'Maximaal', desc: '10× 30s all-out. Max kracht en explosiviteit.', color: 'sprint' },
  };

  // Recent activities — uses GarminActivity shape
  const activities = [
    { id: 8412, activity_type: 'RUNNING',    activity_name: 'Ochtendloop Schelde',          start_time: '2026-05-13T07:14:00', duration_seconds: 3120, distance_meters: 9420,  average_heart_rate: 148, max_heart_rate: 172, calories: 612, manual: false },
    { id: 8408, activity_type: 'CYCLING',    activity_name: 'Pendel naar werk',              start_time: '2026-05-12T08:02:00', duration_seconds: 1680, distance_meters: 13400, average_heart_rate: 121, max_heart_rate: 154, calories: 244, manual: false },
    { id: 8401, activity_type: 'RUNNING',    activity_name: 'Intervaltraining 6×800m',       start_time: '2026-05-11T18:35:00', duration_seconds: 2940, distance_meters: 8100,  average_heart_rate: 163, max_heart_rate: 189, calories: 591, manual: false },
    { id: 8397, activity_type: 'LAP_SWIMMING',activity_name: 'Baantjes',                      start_time: '2026-05-10T19:10:00', duration_seconds: 1860, distance_meters: 1800,  average_heart_rate: 134, max_heart_rate: 162, calories: 318, manual: false },
    { id: 8390, activity_type: 'RUNNING',    activity_name: 'Duurloop park',                 start_time: '2026-05-09T09:42:00', duration_seconds: 4380, distance_meters: 13200, average_heart_rate: 142, max_heart_rate: 168, calories: 854, manual: false },
    { id: 8385, activity_type: 'CYCLING',    activity_name: 'Rondje Schoten',                start_time: '2026-05-08T17:18:00', duration_seconds: 4920, distance_meters: 42800, average_heart_rate: 138, max_heart_rate: 164, calories: 712, manual: false },
    { id: 8378, activity_type: 'CARDIO_TRAINING', activity_name: 'Avondwandeling',           start_time: '2026-05-07T20:45:00', duration_seconds: 2400, distance_meters: 3100,  average_heart_rate: 102, max_heart_rate: 118, calories: 198, manual: false },
    { id: 8370, activity_type: 'RUNNING',    activity_name: 'Tempo 4×5 min',                 start_time: '2026-05-06T07:30:00', duration_seconds: 2640, distance_meters: 7400,  average_heart_rate: 158, max_heart_rate: 182, calories: 522, manual: false },
    { id: 8365, activity_type: 'RUNNING',    activity_name: 'Easy run',                      start_time: '2026-05-04T08:15:00', duration_seconds: 2520, distance_meters: 7200,  average_heart_rate: 138, max_heart_rate: 158, calories: 488, manual: false },
    { id: 8358, activity_type: 'CYCLING',    activity_name: 'Lange duurrit Kalmthout',       start_time: '2026-05-03T09:00:00', duration_seconds: 9420, distance_meters: 78400, average_heart_rate: 142, max_heart_rate: 171, calories: 1418, manual: false },
  ];

  // Weekly trend — last 6 weeks
  const weeklyTrend = [
    { week_start: '2026-04-06', sessions: 3, distance_km: 28.4, duration_hours: 3.1, average_heart_rate: 142 },
    { week_start: '2026-04-13', sessions: 4, distance_km: 41.2, duration_hours: 4.6, average_heart_rate: 145 },
    { week_start: '2026-04-20', sessions: 5, distance_km: 52.8, duration_hours: 5.8, average_heart_rate: 146 },
    { week_start: '2026-04-27', sessions: 4, distance_km: 48.1, duration_hours: 5.2, average_heart_rate: 144 },
    { week_start: '2026-05-04', sessions: 5, distance_km: 61.4, duration_hours: 6.4, average_heart_rate: 148 },
    { week_start: '2026-05-11', sessions: 3, distance_km: 31.0, duration_hours: 3.1, average_heart_rate: 144 },
  ];

  const weeklySummary = {
    sessions: 3,
    distance_km: 31.0,
    duration_hours: 3.1,
    average_heart_rate: 144,
    longest_session_minutes: 73,
    running_sessions: 2,
    cycling_sessions: 1,
    max_heart_rate: 189,
  };

  const baseline = {
    sessions: 4.2,
    distance_km: 43.8,
    duration_hours: 4.7,
    average_heart_rate: 145,
  };

  const weeklyAnalysis = {
    summary: 'Volume is licht onder je 4-weken gemiddelde. Intensiteit blijft op peil dankzij de intervalsessie van woensdag.',
    insight: 'Voeg dit weekend een rustige duurloop van 75-90 min toe om je weekvolume in balans te brengen.',
    load_ratio: 0.74,
    deltas: { sessions_percent: -28, distance_percent: -29, duration_percent: -34, avg_heart_rate_delta: -1 },
  };

  // Chat seed messages
  const chatSeed = [
    { role: 'assistant', content: 'Hey, je herstelscore is <b>4/6</b>. Goede dag voor een tempotraining — wil je dat ik een sessie van 55 min klaarmaak?', time: '08:12', source: 'seed' },
  ];

  // Floating coach quick suggestions
  const coachSuggestions = [
    'Hoe was mijn slaap vannacht?',
    'Maak een duurloop van 75 min',
    'Wat is mijn herstelstatus?',
    'Toon mijn activiteiten van deze week',
  ];

  return {
    today,
    user: { name: 'Clement', firstName: 'Clement', avatarInitials: 'CP', garminConnected: true },
    recovery,
    recommendedByRecovery,
    activities,
    weeklyTrend,
    weeklySummary,
    baseline,
    weeklyAnalysis,
    chatSeed,
    coachSuggestions,
  };
})();
