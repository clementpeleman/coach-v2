// Profiel — Garmin, account, herstel.
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
  const garminConnected = profile?.garmin_connected ?? false;

  useEffectP(() => {
    if (profile?.email) setEmail(profile.email);
    if (profile?.display_name) setName(profile.display_name);
  }, [profile]);

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
        <button className="btn ghost" onClick={onLogout} style={{ alignSelf: 'flex-start' }}>
          Uitloggen
        </button>
      )}
    </div>
  );
}

window.ProfileScreen = ProfileScreen;
