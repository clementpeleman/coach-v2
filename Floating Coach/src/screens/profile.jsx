// Profiel - Garmin, account, herstel, data-import.
const { useState: useStateP, useEffect: useEffectP } = React;
const FCU = window.FC_UTILS;

function ProfileScreen({ recoveryScore, recoveryData, recoverySnapshot, apiStatus, userId, profile, onNavigate, onLogout }) {
  const online = apiStatus === 'online';
  const [email, setEmail] = useStateP('');
  const [name, setName] = useStateP('');
  const [saving, setSaving] = useStateP(false);
  const [saveMsg, setSaveMsg] = useStateP(null);
  const [connecting, setConnecting] = useStateP(false);
  const [connectError, setConnectError] = useStateP(null);
  const [importStatus, setImportStatus] = useStateP(null);
  const [syncing, setSyncing] = useStateP(false);
  const [syncMsg, setSyncMsg] = useStateP(null);
  const [importLog, setImportLog] = useStateP([]);
  const garminConnected = profile?.garmin_connected ?? false;

  const loadImportStatus = () => {
    if (!userId || !online) return;
    window.FC_API.fetchGarminImportStatus(userId, 30)
      .then((s) => setImportStatus(s))
      .catch(() => setImportStatus(null));
  };

  useEffectP(() => {
    if (profile?.email) setEmail(profile.email);
    if (profile?.display_name) setName(profile.display_name);
  }, [profile]);

  useEffectP(() => {
    loadImportStatus();
  }, [userId, online, garminConnected]);

  const saveProfile = async () => {
    if (!email.includes('@') || !userId || !online) return;
    setSaving(true);
    setSaveMsg(null);
    try {
      await window.FC_API.loginWebUser(email, name || undefined);
      setSaveMsg('Profiel opgeslagen.');
    } catch (e) {
      setSaveMsg(FCU.formatApiError(e.message));
    } finally {
      setSaving(false);
    }
  };

  const reconnectGarmin = async () => {
    setConnecting(true);
    setConnectError(null);
    try {
      const res = await window.FC_API.startDirectGarminOAuth({
        userId: userId || undefined,
        email: email || undefined,
        displayName: name || undefined,
      });
      window.FC_SESSION.writeUserId(res.user_id);
      window.location.href = res.authorization_url;
    } catch (e) {
      setConnectError(FCU.formatApiError(e.message));
      setConnecting(false);
    }
  };

  const startDataImport = async () => {
    if (!userId || !online) return;
    setSyncing(true);
    setSyncMsg(null);
    setImportLog([]);
    try {
      const res = await window.FC_API.requestInitialGarminSync(userId);
      const sessions = res?.import_status?.activity_sessions;
      const health = res?.import_status?.health_records;
      const extra = sessions != null
        ? ` (${sessions} activiteiten, ${health ?? '?'} gezondheid - 30 dagen)`
        : '';
      setSyncMsg((res.message || 'Import gestart. Even geduld…') + extra);
      setImportLog(Array.isArray(res.import_log) ? res.import_log : []);
      try { window.localStorage.setItem(`fc_initial_sync_${userId}`, 'done'); } catch (_) {}
      setTimeout(loadImportStatus, 3000);
      setTimeout(loadImportStatus, 15000);
    } catch (e) {
      setSyncMsg(FCU.formatApiError(e.message));
      setImportLog([]);
    } finally {
      setSyncing(false);
    }
  };

  const logLevelColor = (level) => {
    if (level === 'error') return 'var(--bad)';
    if (level === 'warn') return 'var(--warn)';
    if (level === 'ok') return 'var(--good)';
    return 'var(--ink-3)';
  };

  const summary = importStatus?.summary || {};
  const activityCount = summary.activity_records ?? 0;
  const healthCount = summary.health_records ?? 0;
  const hasData = activityCount > 0 || healthCount > 0;

  return (
    <div className="col" style={{ gap: 24 }} data-screen-label="Profiel">
      <div className="screen-head">
        <div>
          <div className="label" style={{ marginBottom: 10 }}>Account</div>
          <h1>Profiel.<br/><em>Garmin & voorkeuren.</em></h1>
        </div>
      </div>

      <div className="card" style={{ padding: '24px 28px' }}>
        <h2 style={{ margin: '0 0 16px', fontSize: 16 }}>Garmin</h2>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
          <span style={{ fontSize: 14, color: 'var(--ink-2)' }}>Status</span>
          <span style={{ fontWeight: 600, color: garminConnected ? 'var(--good)' : 'var(--warn)' }}>
            {garminConnected ? 'Verbonden' : 'Niet verbonden'}
          </span>
        </div>
        <button className="btn accent" onClick={reconnectGarmin} disabled={connecting}>
          {connecting ? 'Bezig…' : (garminConnected ? 'Opnieuw verbinden' : 'Verbind Garmin')}
        </button>
        {connectError && <p style={{ marginTop: 12, fontSize: 13, color: 'var(--bad)' }}>{connectError}</p>}
      </div>

      {garminConnected && userId && online && (
        <div className="card" style={{ padding: '24px 28px' }}>
          <h2 style={{ margin: '0 0 12px', fontSize: 16 }}>Data-import</h2>
          <p style={{ margin: '0 0 16px', fontSize: 13, color: 'var(--ink-3)', lineHeight: 1.5 }}>
            {hasData
              ? `${activityCount} activiteiten en ${healthCount} gezondheidsrecords in de laatste 30 dagen.`
              : 'Nog geen data in de database. Start een import - Garmin stuurt records via webhooks (enkele minuten).'}
            {hasData && activityCount <= 2 && (
              <span style={{ display: 'block', marginTop: 8, color: 'var(--warn)' }}>
                Weinig historiek zichtbaar? Klik opnieuw importeren en laat Garmin verbonden -
                historiek komt via webhooks (2–15 min), niet via directe API-pull.
              </span>
            )}
          </p>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            <button className="btn accent" onClick={startDataImport} disabled={syncing}>
              {syncing ? 'Import starten…' : (hasData ? 'Opnieuw importeren' : 'Start data-import')}
            </button>
            <button className="btn ghost" onClick={loadImportStatus} disabled={syncing}>
              Status vernieuwen
            </button>
          </div>
          {syncMsg && (
            <p style={{ marginTop: 12, fontSize: 13, color: 'var(--ink-2)' }}>{syncMsg}</p>
          )}
          {importLog.length > 0 && (
            <div style={{
              marginTop: 16,
              padding: '14px 16px',
              background: 'var(--surface-2, oklch(96% 0.005 100))',
              borderRadius: 8,
              maxHeight: 320,
              overflowY: 'auto',
            }}>
              <div className="mono" style={{
                fontSize: 10,
                textTransform: 'uppercase',
                letterSpacing: '.12em',
                color: 'var(--ink-4)',
                marginBottom: 10,
              }}>
                Import-log
              </div>
              <ul style={{ margin: 0, padding: 0, listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 8 }}>
                {importLog.map((entry, idx) => (
                  <li key={`${entry.at || idx}-${entry.step}-${idx}`} style={{ fontSize: 12, lineHeight: 1.45 }}>
                    <span className="mono" style={{ color: 'var(--ink-4)', marginRight: 8 }}>
                      {entry.at ? entry.at.replace('T', ' ').replace('Z', '').slice(11, 19) : '--:--:--'}
                    </span>
                    <span className="mono" style={{
                      color: logLevelColor(entry.level),
                      marginRight: 8,
                      fontWeight: 600,
                      textTransform: 'uppercase',
                      fontSize: 10,
                    }}>
                      {entry.step || 'log'}
                    </span>
                    <span style={{ color: 'var(--ink-2)' }}>{entry.message}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {!hasData && (
            <p style={{ marginTop: 12, fontSize: 12, color: 'var(--ink-4)', lineHeight: 1.45 }}>
              Geen data na 15 min? Controleer in Garmin Developer dat webhooks naar{' '}
              <span className="mono">/garmin/webhook/activity</span> en{' '}
              <span className="mono">/garmin/webhook/health</span> wijzen (zelfde domein als de app).
            </p>
          )}
        </div>
      )}

      {userId && online && (
        <div className="card" style={{ padding: '24px 28px' }}>
          <h2 style={{ margin: '0 0 16px', fontSize: 16 }}>Contact (optioneel)</h2>
          <div className="field" style={{ marginBottom: 16 }}>
            <label>Email</label>
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="jij@voorbeeld.com" />
          </div>
          <div className="field" style={{ marginBottom: 16 }}>
            <label>Naam</label>
            <input type="text" value={name} onChange={(e) => setName(e.target.value)} placeholder="Jouw naam" />
          </div>
          <button className="btn" onClick={saveProfile} disabled={saving || !email.includes('@')}>
            {saving ? 'Opslaan…' : 'Opslaan'}
          </button>
          {saveMsg && <p style={{ marginTop: 10, fontSize: 13, color: 'var(--ink-3)' }}>{saveMsg}</p>}
        </div>
      )}

      <div>
        <div className="label" style={{ marginBottom: 12 }}>Herstel</div>
        {window.RecoveryScreen && (
          <window.RecoveryScreen
            recoveryScore={recoveryScore}
            recoveryData={recoveryData}
            recoverySnapshot={recoverySnapshot}
            onNavigate={onNavigate}
            embedded
          />
        )}
      </div>

      {onLogout && (
        <button className="btn ghost" onClick={() => onLogout()} style={{ alignSelf: 'flex-start' }}>
          Uitloggen
        </button>
      )}
    </div>
  );
}

window.ProfileScreen = ProfileScreen;
