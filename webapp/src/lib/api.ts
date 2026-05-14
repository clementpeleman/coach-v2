const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type GarminAuthStatus = {
  authenticated: boolean;
  garmin_user_id?: string;
  permissions?: string[];
  expires_at?: string;
  message?: string;
};

export type GarminActivity = {
  id: number;
  summary_id: string;
  activity_id?: string;
  activity_type: string;
  activity_name?: string;
  start_time: string;
  duration_seconds?: number;
  distance_meters?: number;
  average_heart_rate?: number;
  max_heart_rate?: number;
  calories?: number;
  manual: boolean;
};

export type ActivitiesResponse = {
  activities: GarminActivity[];
  count: number;
  period_days: number;
  summary: {
    sessions: number;
    distance_meters: number;
    distance_km: number;
    duration_seconds: number;
    duration_hours: number;
    longest_session_minutes: number;
    average_heart_rate: number | null;
    max_heart_rate: number | null;
    running_sessions: number;
    cycling_sessions: number;
    running_average_heart_rate: number | null;
    cycling_average_heart_rate: number | null;
  };
  type_distribution: Record<string, number>;
  weekly_trend: Array<{
    week_start: string;
    sessions: number;
    distance_km: number;
    duration_hours: number;
    average_heart_rate: number | null;
  }>;
};

export type WebUser = {
  user_id: number;
  email?: string;
  display_name?: string;
  garmin_connected?: boolean;
};

export type WeeklyAnalysis = {
  window: {
    current_start: string;
    current_end: string;
    baseline_start: string;
    baseline_end: string;
  };
  current_week: {
    sessions: number;
    distance_meters: number;
    distance_km: number;
    duration_seconds: number;
    duration_hours: number;
    longest_session_minutes: number;
    average_heart_rate: number | null;
    max_heart_rate: number | null;
    running_sessions: number;
    cycling_sessions: number;
    running_average_heart_rate: number | null;
    cycling_average_heart_rate: number | null;
  };
  baseline_weekly: {
    sessions: number;
    distance_km: number;
    duration_hours: number;
    average_heart_rate: number | null;
    running_sessions: number;
    cycling_sessions: number;
  };
  deltas: {
    sessions_percent: number | null;
    distance_percent: number | null;
    duration_percent: number | null;
    avg_heart_rate_delta: number | null;
  };
  load_ratio: number | null;
  insight: string;
  summary: string;
  highlights: Array<{
    type: "success" | "warning" | "info";
    label: string;
    text: string;
  }>;
  days: number;
};

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`API request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export function getGarminAuthStartUrl(userId: number): string {
  return `${API_URL}/garmin/auth/start?user_id=${userId}`;
}

export async function fetchGarminAuthStatus(userId: number): Promise<GarminAuthStatus> {
  return getJson<GarminAuthStatus>(`/garmin/auth/status?user_id=${userId}`);
}

export async function fetchGarminActivities(
  userId: number,
  limit = 200,
  periodDays = 30,
): Promise<ActivitiesResponse> {
  return getJson<ActivitiesResponse>(
    `/garmin/activities?user_id=${userId}&limit=${limit}&period_days=${periodDays}`,
  );
}

export async function requestSmartActivityBackfill(
  userId: number,
  days = 120,
): Promise<{
  status: string;
  message: string;
  activity_backfill?: {
    requested_start: string;
    effective_start: string;
    end: string;
    status: string;
    notes: string[];
  };
}> {
  const response = await fetch(
    `${API_URL}/garmin/data/backfill/smart?user_id=${userId}&days=${days}`,
    { method: "POST" },
  );
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`Smart backfill failed (${response.status}): ${body}`);
  }
  return response.json();
}

export async function fetchWeeklyAnalysis(userId: number, days = 7): Promise<WeeklyAnalysis> {
  return getJson<WeeklyAnalysis>(`/garmin/analysis/weekly?user_id=${userId}&days=${days}`);
}

export async function loginWebUser(email: string, displayName?: string): Promise<{
  user_id: number;
  email: string;
  display_name?: string;
  created: boolean;
}> {
  const response = await fetch(`${API_URL}/web/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      email,
      display_name: displayName || null,
    }),
  });
  if (!response.ok) {
    throw new Error(`Login failed (${response.status})`);
  }
  return response.json();
}

export async function fetchWebUser(userId: number): Promise<WebUser> {
  return getJson<WebUser>(`/web/auth/me?user_id=${userId}`);
}

export async function startDirectGarminOAuth(payload: {
  userId?: number;
  email?: string;
  displayName?: string;
}): Promise<{ user_id: number; authorization_url: string; state: string }> {
  const response = await fetch(`${API_URL}/web/auth/garmin/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      user_id: payload.userId ?? null,
      email: payload.email || null,
      display_name: payload.displayName || null,
    }),
  });

  if (!response.ok) {
    const body = await response.text();
    throw new Error(`Garmin OAuth start failed (${response.status}): ${body}`);
  }

  return response.json();
}

export type AthleteProfile = {
  overview: {
    total_activities: number;
    total_distance_km: number;
    total_duration_hours: number;
    total_calories: number;
    total_elevation_m: number;
  };
  heart_rate_zones: {
    max_hr_observed: number;
    zone1: { name: string; range: string; min: number; max: number };
    zone2: { name: string; range: string; min: number; max: number };
    zone3: { name: string; range: string; min: number; max: number };
    zone4: { name: string; range: string; min: number; max: number };
    zone5: { name: string; range: string; min: number; max: number };
  } | null;
  running: {
    total_sessions: number;
    total_distance_km: number;
    total_duration_hours: number;
    total_calories: number;
    total_elevation_m: number;
    avg_distance_km: number | null;
    avg_duration_min: number | null;
    avg_heart_rate: number | null;
    max_heart_rate_observed: number | null;
    avg_calories_per_session: number | null;
    avg_pace_min_km: number | null;
    best_pace_min_km: number | null;
    avg_cadence_spm: number | null;
    longest_run_km: number | null;
    longest_run_min: number | null;
  } | null;
  cycling: {
    total_sessions: number;
    total_distance_km: number;
    total_duration_hours: number;
    total_calories: number;
    total_elevation_m: number;
    avg_distance_km: number | null;
    avg_duration_min: number | null;
    avg_heart_rate: number | null;
    max_heart_rate_observed: number | null;
    avg_calories_per_session: number | null;
    avg_speed_kmh: number | null;
    max_speed_kmh: number | null;
    avg_elevation_m: number | null;
    longest_ride_km: number | null;
    longest_ride_min: number | null;
  } | null;
  personal_records: {
    running?: Record<string, { value: number; unit: string; date: string | null; activity: string | null }>;
    cycling?: Record<string, { value: number; unit: string; date: string | null; activity: string | null }>;
  };
  training_patterns: {
    favorite_days: Array<{ day: string; count: number }>;
    favorite_hours: Array<{ hour: number; count: number }>;
    avg_days_between_sessions: number | null;
    max_days_between_sessions: number | null;
    sessions_per_week: number;
    first_activity: string | null;
    last_activity: string | null;
    total_active_weeks: number;
  };
  health: {
    days_with_data: number;
    avg_resting_hr: number | null;
    min_resting_hr: number | null;
    max_resting_hr: number | null;
  } | null;
};

export async function fetchAthleteProfile(userId: number): Promise<AthleteProfile> {
  return getJson<AthleteProfile>(`/analysis/profile?user_id=${userId}`);
}

export async function sendChatMessage(payload: {
  userId: number;
  message: string;
  history: Array<{ role: "user" | "assistant"; content: string }>;
}): Promise<{ reply: string }> {
  const response = await fetch(`${API_URL}/web/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      user_id: payload.userId,
      message: payload.message,
      history: payload.history,
    }),
  });

  if (!response.ok) {
    const body = await response.text();
    throw new Error(`Chat failed (${response.status}): ${body}`);
  }

  return response.json();
}
