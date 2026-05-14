import { useSyncExternalStore } from "react";

type SessionSnapshot = {
  resolved: boolean;
  userId: number | null;
};

function readUserIdFromClient(): number | null {
  if (typeof window === "undefined") {
    return null;
  }

  const queryUserId = new URLSearchParams(window.location.search).get("user_id");
  const parsedQueryUserId = queryUserId ? Number(queryUserId) : NaN;
  if (Number.isInteger(parsedQueryUserId) && parsedQueryUserId > 0) {
    return parsedQueryUserId;
  }

  const rawUserId = window.localStorage.getItem("sportsHubUserId");
  const parsed = rawUserId ? Number(rawUserId) : NaN;
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
}

function subscribeToSessionChanges(onStoreChange: () => void): () => void {
  if (typeof window === "undefined") {
    return () => {};
  }

  window.addEventListener("storage", onStoreChange);
  window.addEventListener("popstate", onStoreChange);
  return () => {
    window.removeEventListener("storage", onStoreChange);
    window.removeEventListener("popstate", onStoreChange);
  };
}

export function useSessionUserId(): SessionSnapshot {
  const getSnapshot = (): SessionSnapshot => ({
    resolved: true,
    userId: readUserIdFromClient(),
  });
  const getServerSnapshot = (): SessionSnapshot => ({
    resolved: false,
    userId: null,
  });

  return useSyncExternalStore(
    subscribeToSessionChanges,
    getSnapshot,
    getServerSnapshot,
  );
}
