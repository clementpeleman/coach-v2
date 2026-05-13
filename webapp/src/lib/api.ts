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
