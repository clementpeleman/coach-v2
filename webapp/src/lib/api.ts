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
  limit = 20,
): Promise<{ activities: GarminActivity[]; count: number }> {
  return getJson<{ activities: GarminActivity[]; count: number }>(
    `/garmin/activities?user_id=${userId}&limit=${limit}`,
  );
}

export async function fetchWeeklyAnalysis(userId: number): Promise<WeeklyAnalysis> {
  return getJson<WeeklyAnalysis>(`/garmin/analysis/weekly?user_id=${userId}`);
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
