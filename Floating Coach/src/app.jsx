// App shell — sidebar nav, screen router, floating orb.
const { useState: useStateApp, useEffect: useEffectApp } = React;

const ACCENT_HEX   = '#caff3b';
const ACCENT_INK   = '#0d0e0b';
const DEFAULT_RECOVERY = 4;

function App() {
  const session = window.useSession();
  const apiStatus = window.useApiStatus();
  const [recoverySnapshot, setRecoverySnapshot] = useStateApp(() => (
    session.userId ? readAppLiveCache(`recovery_${session.userId}`)?.data || null : null
  ));
  const [weather, setWeather] = useStateApp(null);
  const [trainingProfile, setTrainingProfile] = useStateApp(() => (
    session.userId ? readAppLiveCache(`training_profile_${session.userId}`)?.data || null : null
  ));
  const chatStorageKey = `fc_chat_messages_v1_${session.userId || 'demo'}`;
  const recoveryMetrics = recoverySnapshot?.metrics || (session.userId ? {} : window.FC_DATA.recovery);
  const recoveryScoreRaw = recoverySnapshot?.score;
  const recoveryScore = session.userId
    ? (recoveryScoreRaw ?? null)
    : DEFAULT_RECOVERY;
  const recoveryScoreForPlan = recoveryScore ?? 3;
  const [chatMessages, setChatMessages] = useStateApp(() => readStoredChat(chatStorageKey));
  const [chatThinking, setChatThinking] = useStateApp(false);
  const [draftWorkout, setDraftWorkout] = useStateApp(() => (
    session.userId
      ? readAppLiveCache(`training_recommendation_${session.userId}`)?.data || null
      : window.FC_WORKOUT_PLAN?.buildDraft({ recoveryScore: DEFAULT_RECOVERY, trainingProfile: null })
  ));
  const resetChat = () => {
    setChatMessages(window.FC_DATA.chatSeed);
    setChatThinking(false);
  };

  // Initial screen: OAuth paths like /dashboard?user_id=… or stored session → dashboard
  const [screen, setScreen] = useStateApp(() => {
    const path = (window.location.pathname || '/').replace(/\/$/, '') || '/';
    if (session.userId && (path === '/dashboard' || path === '/')) return 'dashboard';
    return session.userId ? 'dashboard' : 'onboarding';
  });

  // Live user profile from /web/auth/me (name, garmin_connected).
  const [profile, setProfile] = useStateApp(null);
  useEffectApp(() => {
    setProfile(null);
    if (apiStatus.status !== 'online' || !session.userId) return;
    let cancelled = false;
    window.FC_API.fetchWebUser(session.userId).then((p) => {
      if (!cancelled) setProfile(p);
    }).catch(() => {});
    return () => { cancelled = true; };
  }, [apiStatus.status, session.userId]);

  // Shared training profile: personal targets, sport baselines, and learned workout patterns.
  useEffectApp(() => {
    if (!session.userId) {
      setTrainingProfile(null);
      return;
    }
    const cacheKey = `training_profile_${session.userId}`;
    const cached = readAppLiveCache(cacheKey);
    if (cached?.data) setTrainingProfile({ ...cached.data, _source: 'stale-live', _updatedAt: cached.updatedAt });
    if (apiStatus.status !== 'online') return;
    let cancelled = false;
    window.FC_API.fetchTrainingProfile(session.userId, 120, 7).then((profileData) => {
      const updatedAt = new Date().toISOString();
      writeAppLiveCache(cacheKey, profileData, updatedAt);
      if (!cancelled) setTrainingProfile({ ...profileData, _source: 'live', _updatedAt: updatedAt });
    }).catch((e) => {
      const fallback = readAppLiveCache(cacheKey);
      if (!cancelled && fallback?.data) {
        setTrainingProfile({ ...fallback.data, _source: 'stale-live', _updatedAt: fallback.updatedAt, _error: e.message });
      }
    });
    return () => { cancelled = true; };
  }, [apiStatus.status, session.userId]);

  // Shared chat memory for both the floating coach and full Coach tab.
  useEffectApp(() => {
    setChatMessages(readStoredChat(chatStorageKey));
    setChatThinking(false);
  }, [chatStorageKey]);

  useEffectApp(() => {
    try {
      window.localStorage.setItem(chatStorageKey, JSON.stringify(chatMessages.slice(-80)));
    } catch (_) {}
  }, [chatStorageKey, chatMessages]);

  useEffectApp(() => {
    if (!session.userId) {
      if (!window.FC_WORKOUT_PLAN) return;
      setDraftWorkout((current) => (
        current && current.source === 'auto'
          ? current
          : window.FC_WORKOUT_PLAN.buildDraft({ recoveryScore: recoveryScoreForPlan, trainingProfile: null })
      ));
      return;
    }

    const cacheKey = `training_recommendation_${session.userId}`;
    const canReplace = (current) => !current || (
      ['auto', 'backend', 'stale-live'].includes(current.source)
      && current.status !== 'approved'
    );
    const cached = readAppLiveCache(cacheKey);
    if (cached?.data) {
      setDraftWorkout((current) => canReplace(current)
        ? { ...cached.data, source: cached.data.source || 'backend', dataSource: 'stale-live' }
        : current);
    }
    if (apiStatus.status !== 'online') return;

    let cancelled = false;
    window.FC_API.fetchTrainingRecommendation(session.userId, weather).then((recommendation) => {
      const updatedAt = new Date().toISOString();
      const liveRecommendation = {
        ...recommendation,
        source: recommendation.source || 'backend',
        dataSource: 'live',
        updatedAt: recommendation.updatedAt || updatedAt,
      };
      writeAppLiveCache(cacheKey, liveRecommendation, updatedAt);
      if (!cancelled) {
        setDraftWorkout((current) => canReplace(current) ? liveRecommendation : current);
      }
    }).catch((e) => {
      const fallback = readAppLiveCache(cacheKey);
      if (!cancelled && fallback?.data) {
        setDraftWorkout((current) => canReplace(current)
          ? { ...fallback.data, source: fallback.data.source || 'backend', dataSource: 'stale-live', error: e.message }
          : current);
      }
    });
    return () => { cancelled = true; };
  }, [apiStatus.status, session.userId, recoveryScoreForPlan, trainingProfile?._updatedAt, weather?.observed_at]);

  useEffectApp(() => {
    window.FC_SET_DRAFT_WORKOUT = (updater) => setDraftWorkout(updater);
    return () => {
      if (window.FC_SET_DRAFT_WORKOUT) delete window.FC_SET_DRAFT_WORKOUT;
    };
  }, []);

  useEffectApp(() => {
    const openCoachWithMessages = (messagesOrEvent) => {
      const incoming = Array.isArray(messagesOrEvent)
        ? messagesOrEvent
        : messagesOrEvent?.detail;
      if (Array.isArray(incoming) && incoming.length) {
        setChatThinking(false);
        setChatMessages((current) => appendUniqueChatMessages(current || window.FC_DATA.chatSeed, incoming));
      }
      window.dispatchEvent(new CustomEvent('fc-open-coach-orb'));
    };
    window.FC_OPEN_COACH_MESSAGES = openCoachWithMessages;
    window.addEventListener('fc-open-chat-messages', openCoachWithMessages);
    return () => {
      window.removeEventListener('fc-open-chat-messages', openCoachWithMessages);
      if (window.FC_OPEN_COACH_MESSAGES === openCoachWithMessages) delete window.FC_OPEN_COACH_MESSAGES;
    };
  }, []);

  // Live Garmin health snapshot for recovery, sleep, stress, HRV and body battery.
  useEffectApp(() => {
    if (!session.userId) {
      setRecoverySnapshot(null);
      return;
    }
    const cacheKey = `recovery_${session.userId}`;
    const cached = readAppLiveCache(cacheKey);
    if (cached?.data) {
      setRecoverySnapshot({ ...cached.data, source: 'stale-live', stale: true, updated_at: cached.updatedAt });
    }
    if (apiStatus.status !== 'online') return;
    let cancelled = false;
    window.FC_API.fetchGarminRecovery(session.userId).then((snapshot) => {
      const updatedAt = new Date().toISOString();
      const liveSnapshot = { ...snapshot, source: snapshot?.source || 'live', stale: false, updated_at: updatedAt };
      if (snapshot?.source === 'live') writeAppLiveCache(cacheKey, liveSnapshot, updatedAt);
      if (!cancelled) setRecoverySnapshot(liveSnapshot);
    }).catch((e) => {
      const fallback = readAppLiveCache(cacheKey);
      if (!cancelled && fallback?.data) {
        setRecoverySnapshot({
          ...fallback.data,
          source: 'stale-live',
          stale: true,
          error: e.message,
          updated_at: fallback.updatedAt,
        });
      }
    });
    return () => { cancelled = true; };
  }, [apiStatus.status, session.userId]);

  // Browser location + live weather. If permission is denied, keep the UI honest.
  useEffectApp(() => {
    setWeather(null);
    if (apiStatus.status !== 'online' || !session.userId || !navigator.geolocation) return;
    let cancelled = false;
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        window.FC_API.fetchWeather(pos.coords.latitude, pos.coords.longitude).then((w) => {
          if (!cancelled) setWeather(w);
        }).catch(() => {});
      },
      () => {
        if (!cancelled) setWeather({ source: 'unavailable', condition: 'locatie onbekend' });
      },
      { enableHighAccuracy: false, timeout: 8000, maximumAge: 30 * 60 * 1000 },
    );
    return () => { cancelled = true; };
  }, [apiStatus.status, session.userId]);

  // Apply accent token once.
  useEffectApp(() => {
    document.documentElement.style.setProperty('--accent', ACCENT_HEX);
    document.documentElement.style.setProperty('--accent-ink', ACCENT_INK);
  }, []);

  // Garmin OAuth callback: ?user_id= & optional /dashboard path → normalize URL to /
  useEffectApp(() => {
    const params = new URLSearchParams(window.location.search);
    const hadUser = params.has('user_id');
    const hadGarmin = params.has('garmin_connected');
    if (hadUser) params.delete('user_id');
    if (hadGarmin) params.delete('garmin_connected');
    const onDashboardPath = window.location.pathname.replace(/\/$/, '') === '/dashboard';
    if (hadUser || hadGarmin || onDashboardPath) {
      if (session.userId) setScreen('dashboard');
      const q = params.toString();
      window.history.replaceState({}, '', '/' + (q ? `?${q}` : ''));
    }
  }, [session.userId]);

  const SCREENS = {
    dashboard:  { label: 'Vandaag',      ico: '◆', Comp: window.Dashboard },
    workout:    { label: 'Training',     ico: '▶', Comp: window.WorkoutScreen },
    activities: { label: 'Activiteiten', ico: '≡', Comp: window.ActivitiesScreen },
    profiel:    { label: 'Profiel',      ico: '◎', Comp: window.ProfileScreen },
  };

  if (screen === 'onboarding') {
    return (
      <window.OnboardingScreen
        onComplete={() => setScreen('dashboard')}
        apiStatus={apiStatus.status} />
    );
  }

  const userName = profile?.display_name || profile?.email || window.FC_DATA.user.name;
  const userInitials = (profile?.display_name || profile?.email || 'CP')
    .replace(/[^a-zA-Z]/g, '').slice(0, 2).toUpperCase() || 'CP';
  const garminConnected = profile?.garmin_connected ?? false;
  const isLive = apiStatus.status === 'online';
  const appDataSource = session.userId
    ? (recoverySnapshot?.source || trainingProfile?._source || 'empty')
    : 'demo';

  const clearLocalCoachData = () => {
    try {
      const keys = [];
      for (let i = 0; i < window.localStorage.length; i++) {
        const k = window.localStorage.key(i);
        if (!k) continue;
        if (k.startsWith('fc_live_') || k.startsWith('fc_chat_messages')) keys.push(k);
      }
      keys.forEach((k) => window.localStorage.removeItem(k));
      window.sessionStorage.removeItem('fc_pending_chat_messages');
    } catch (_) {}
  };

  const logout = async () => {
    const uid = session.userId;
    if (uid && isLive) {
      try {
        await window.FC_API.disconnectGarmin(uid);
      } catch (e) {
        console.warn('Garmin disconnect:', e);
      }
    }
    clearLocalCoachData(uid);
    window.FC_SESSION.writeUserId(null);
    window.history.replaceState({}, '', '/');
    setProfile(null);
    setRecoverySnapshot(null);
    setTrainingProfile(null);
    setDraftWorkout(null);
    setScreen('onboarding');
  };

  const activeKey = SCREENS[screen] ? screen : 'dashboard';
  const Active = SCREENS[activeKey]?.Comp;
  const screenProps = {
    recoveryScore,
    recoveryData: recoveryMetrics,
    recoverySnapshot,
    weather,
    onNavigate: setScreen,
    apiStatus: apiStatus.status,
    userId: session.userId,
    profile,
    trainingProfile,
    chatMessages,
    setChatMessages,
    chatThinking,
    setChatThinking,
    resetChat,
    draftWorkout,
    setDraftWorkout,
    onLogout: logout,
  };

  return (
    <>
      <div className="app">
        {/* Sidebar */}
        <aside className="rail">
          <div className="brand rail-brand">
            <div className="dot"></div>
            <div>
              <b>Floating Coach</b>
              <small>v2 · nl</small>
            </div>
          </div>

          {Object.entries(SCREENS).map(([k, s]) => (
            <div key={k}
              className={`rail-item tab-nav ${screen === k ? 'active' : ''}`}
              onClick={() => setScreen(k)}>
              <span className="ico">{s.ico}</span>
              <span>{s.label}</span>
            </div>
          ))}

          <div className="spacer"></div>

          <div className="rail-status" style={{ padding: '10px 12px', marginBottom: 10,
                        background: 'var(--surface)', border: '1px solid var(--line)',
                        borderRadius: 10 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
              <span className="label">Garmin</span>
              <window.ConnectionPill status={apiStatus.status} source={appDataSource}
                onClick={() => setScreen('profiel')} />
            </div>
            <div style={{ fontSize: 13, fontWeight: 600, marginTop: 8,
              color: garminConnected ? 'var(--good)' : 'var(--warn)' }}>
              {garminConnected ? 'Verbonden' : 'Niet verbonden'}
            </div>
          </div>

          <div className="footer rail-footer">
            <div className="avatar">{userInitials}</div>
            <div style={{ flex: 1 }}>
              <div className="who">{userName}</div>
              <div className="stat">
                {appDataSource === 'stale-live'
                  ? 'Garmin · stale'
                  : (isLive
                    ? (garminConnected ? 'Garmin · live' : (session.userId ? 'API · live' : 'Demo · login nodig'))
                    : 'Demo modus')}
              </div>
            </div>
          </div>
        </aside>

        {/* Main */}
        <main className="main">
          {Active && <Active {...screenProps} />}
        </main>
      </div>

      {/* Floating coach — enige coach-ingang */}
      <window.CoachOrb recoveryScore={recoveryScore}
                          recoveryData={recoveryMetrics}
                          weather={weather}
                          currentScreen={screen}
                          apiStatus={apiStatus.status}
                          userId={session.userId}
                          trainingProfile={trainingProfile}
                          draftWorkout={draftWorkout}
                          setDraftWorkout={setDraftWorkout}
                          messages={chatMessages}
                          setMessages={setChatMessages}
                          thinking={chatThinking}
                          setThinking={setChatThinking} />
    </>
  );
}

function readStoredChat(key) {
  try {
    const parsed = JSON.parse(window.localStorage.getItem(key) || 'null');
    if (Array.isArray(parsed) && parsed.length) {
      if (isLegacyDemoChat(parsed)) return window.FC_DATA.chatSeed;
      return parsed
        .filter((m) => m && typeof m.role === 'string' && typeof m.content === 'string')
        .map((m) => ({
          role: m.role === 'user' ? 'user' : 'assistant',
          content: m.content,
          time: m.time || '',
          source: m.source,
        }));
    }
  } catch (_) {}
  return window.FC_DATA.chatSeed;
}

function isLegacyDemoChat(messages) {
  const legacyUserText = 'Doe maar, maar liever 45 min, ik moet om 19u thuis zijn.';
  const legacyAssistantText = 'Top. <b>2× 12 min</b> op drempel met 4 min herstel tussendoor, plus warming-up en cooling-down. <i>Klaargezet in Garmin Connect.</i>';
  return messages.length === 3
    && messages[0]?.role === 'assistant'
    && messages[1]?.role === 'user'
    && messages[1]?.content === legacyUserText
    && messages[2]?.role === 'assistant'
    && messages[2]?.content === legacyAssistantText;
}

function readAppLiveCache(key) {
  try {
    const parsed = JSON.parse(window.localStorage.getItem(`fc_live_${key}`) || 'null');
    if (parsed?.data) return parsed;
  } catch (_) {}
  return null;
}

function writeAppLiveCache(key, data, updatedAt) {
  try {
    window.localStorage.setItem(`fc_live_${key}`, JSON.stringify({ data, updatedAt }));
  } catch (_) {}
}

function appendUniqueChatMessages(messages, additions) {
  const existingIds = new Set((messages || []).map((message) => message.id).filter(Boolean));
  const unique = additions.filter((message) => !message.id || !existingIds.has(message.id));
  return [...(messages || []), ...unique];
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
