// API client - same endpoints as FastAPI (via gateway on production domain).
(function () {
  const LOCAL_DEV_BASE = 'http://localhost:8000';

  function defaultBaseUrl() {
    if (typeof window !== 'undefined' && window.location?.origin) {
      const host = window.location.hostname;
      if (host !== 'localhost' && host !== '127.0.0.1') {
        return window.location.origin;
      }
    }
    return LOCAL_DEV_BASE;
  }

  function getBaseUrl() {
    return defaultBaseUrl();
  }

  function setBaseUrl(_url) {
    /* API base follows current origin in production */
  }

  async function getJson(path) {
    const r = await fetch(`${getBaseUrl()}${path}`, { cache: 'no-store' });
    if (!r.ok) throw new Error(`API ${path} failed (${r.status})`);
    return r.json();
  }

  async function postJson(path, body) {
    const r = await fetch(`${getBaseUrl()}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!r.ok) {
      const t = await r.text();
      let detail = t;
      try {
        const j = JSON.parse(t);
        if (j.detail) detail = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail);
      } catch (_) {}
      throw new Error(`API ${path} failed (${r.status}): ${detail}`);
    }
    return r.json();
  }

  async function deleteJson(path) {
    const r = await fetch(`${getBaseUrl()}${path}`, { method: 'DELETE' });
    if (!r.ok) {
      const t = await r.text();
      throw new Error(`API ${path} failed (${r.status}): ${t}`);
    }
    return r.json();
  }

  // ---- Health / availability probe ----
  async function ping(timeoutMs = 2500) {
    try {
      const ac = new AbortController();
      const t = setTimeout(() => ac.abort(), timeoutMs);
      const r = await fetch(`${getBaseUrl()}/health`, { signal: ac.signal, cache: 'no-store' });
      clearTimeout(t);
      return r.ok;
    } catch (_) {
      return false;
    }
  }

  // ---- Garmin OAuth ----
  function getGarminAuthStartUrl(userId) {
    return `${getBaseUrl()}/garmin/auth/start?user_id=${userId}`;
  }
  function fetchGarminAuthStatus(userId) {
    return getJson(`/garmin/auth/status?user_id=${userId}`);
  }
  function startDirectGarminOAuth({ userId, email, displayName }) {
    return postJson('/web/auth/garmin/start', {
      user_id: userId ?? null,
      email: email || null,
      display_name: displayName || null,
    });
  }
  function disconnectGarmin(userId) {
    return deleteJson(`/garmin/auth/disconnect?user_id=${userId}`);
  }
  function fetchGarminRecovery(userId) {
    return getJson(`/garmin/recovery?user_id=${userId}`);
  }
  function fetchGarminImportStatus(userId, periodDays = 30) {
    return getJson(`/garmin/data/import-status?user_id=${userId}&period_days=${periodDays}`);
  }
  function requestInitialGarminSync(userId) {
    return postJson(`/garmin/data/sync-initial?user_id=${userId}`, {});
  }
  function fetchWeather(lat, lon) {
    return getJson(`/web/weather?lat=${encodeURIComponent(lat)}&lon=${encodeURIComponent(lon)}`);
  }

  // ---- Activities ----
  function fetchGarminActivities(userId, limit = 200, periodDays = 30) {
    return getJson(`/garmin/activities?user_id=${userId}&limit=${limit}&period_days=${periodDays}`);
  }
  function fetchWeeklyAnalysis(userId) {
    return getJson(`/garmin/analysis/weekly?user_id=${userId}`);
  }
  function fetchTrainingProfile(userId, days = 120, currentDays = 7) {
    return getJson(`/garmin/training/profile?user_id=${userId}&days=${days}&current_days=${currentDays}`);
  }
  function fetchTrainingRecommendation(userId, weather) {
    const params = new URLSearchParams({ user_id: String(userId) });
    if (weather?.temperature_c != null) params.set('temperature_c', String(weather.temperature_c));
    if (weather?.wind_speed_kmh != null) params.set('wind_speed_kmh', String(weather.wind_speed_kmh));
    if (weather?.condition) params.set('condition', weather.condition);
    if (weather?.training_note) params.set('training_note', weather.training_note);
    return getJson(`/garmin/training/recommendation?${params.toString()}`);
  }
  function adjustTrainingRecommendation({ userId, recommendation, instruction, trainingProfile }) {
    return postJson('/garmin/training/recommendation/adjust', {
      user_id: userId,
      recommendation: recommendation || {},
      instruction,
      training_profile: trainingProfile || null,
    });
  }
  function createTrainingWorkout({ userId, recommendation, status = 'approved' }) {
    return postJson('/garmin/training/workouts', {
      user_id: userId,
      recommendation,
      status,
    });
  }
  function getTrainingWorkoutFitUrl(workoutId) {
    return `${getBaseUrl()}/garmin/training/workouts/${workoutId}/fit`;
  }
  function uploadTrainingWorkoutToGarmin(workoutId) {
    return postJson(`/garmin/training/workouts/${workoutId}/garmin`, {});
  }

  // ---- Web user ----
  function loginWebUser(email, displayName) {
    return postJson('/web/auth/login', { email, display_name: displayName || null });
  }
  function fetchWebUser(userId) {
    return getJson(`/web/auth/me?user_id=${userId}`);
  }

  // ---- Chat ----
  function sendChatMessage({ userId, message, history, context }) {
    return postJson('/web/chat', {
      user_id: userId,
      message,
      history: (history || []).map((m) => ({ role: m.role, content: m.content })),
      context: context || null,
    });
  }

  window.FC_API = {
    getBaseUrl, setBaseUrl, ping,
    getGarminAuthStartUrl, fetchGarminAuthStatus, startDirectGarminOAuth, disconnectGarmin,
    fetchGarminActivities, fetchWeeklyAnalysis, fetchGarminRecovery, fetchGarminImportStatus,
    requestInitialGarminSync,
    fetchTrainingProfile, fetchTrainingRecommendation, adjustTrainingRecommendation,
    createTrainingWorkout, getTrainingWorkoutFitUrl, uploadTrainingWorkoutToGarmin,
    fetchWeather,
    loginWebUser, fetchWebUser,
    sendChatMessage,
  };
})();
