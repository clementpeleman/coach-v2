import { useSyncExternalStore } from "react";

const PERIODS = [
  { label: "7d", days: 7 },
  { label: "14d", days: 14 },
  { label: "30d", days: 30 },
] as const;

export { PERIODS };

const STORAGE_KEY = "sportsHubPeriod";
let currentDays = 7;

const listeners = new Set<() => void>();

function notify() {
  listeners.forEach((fn) => fn());
}

function readFromStorage(): number {
  if (typeof window === "undefined") return 7;
  const stored = window.localStorage.getItem(STORAGE_KEY);
  const parsed = stored ? Number(stored) : NaN;
  return [7, 14, 30].includes(parsed) ? parsed : 7;
}

export function setPeriodDays(days: number) {
  currentDays = days;
  if (typeof window !== "undefined") {
    window.localStorage.setItem(STORAGE_KEY, String(days));
  }
  notify();
}

function subscribe(onStoreChange: () => void): () => void {
  listeners.add(onStoreChange);
  return () => {
    listeners.delete(onStoreChange);
  };
}

let snapshotCache: number | null = null;

function getSnapshot(): number {
  if (snapshotCache === null) {
    currentDays = readFromStorage();
    snapshotCache = currentDays;
  }
  if (snapshotCache !== currentDays) {
    snapshotCache = currentDays;
  }
  return currentDays;
}

const SERVER_SNAPSHOT = 7;

export function usePeriodDays(): number {
  return useSyncExternalStore(subscribe, getSnapshot, () => SERVER_SNAPSHOT);
}
