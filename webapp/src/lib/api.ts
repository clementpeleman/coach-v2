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
    average_heart_rate: number | null;
    running_sessions: number;
    cycling_sessions: number;
  };
  baseline_weekly: {
    sessions: number;
    distance_km: number;
    duration_hours: number;
    average_heart_rate: number | null;
  };
  load_ratio: number | null;
  insight: string;
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
