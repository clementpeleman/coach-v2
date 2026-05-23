// Onboarding - Garmin-first.
const { useState: useStateO } = React;
const FCU = window.FC_UTILS;

function OnboardingScreen({ onComplete, apiStatus }) {
  const [step, setStep] = useStateO(0);
  const [connecting, setConnecting] = useStateO(false);
  const [connectError, setConnectError] = useStateO(null);
  const online = apiStatus === 'online';

  const startOAuth = async () => {
    setConnecting(true);
    setConnectError(null);
    if (!online) {
      setTimeout(() => { setConnecting(false); setStep(1); }, 1200);
      return;
    }
    try {
      const existingId = window.FC_SESSION.readUserId();
      const res = await window.FC_API.startDirectGarminOAuth({ userId: existingId || undefined });
      window.FC_SESSION.writeUserId(res.user_id);
      window.location.href = res.authorization_url;
    } catch (e) {
      setConnectError(FCU.formatApiError(e.message));
      setConnecting(false);
    }
  };

  const steps = [{ label: 'Welkom', n: 1 }, { label: 'Klaar', n: 2 }];

  return (
    <div className="splash" data-screen-label="Onboarding">
      <div style={{ width: '100%', maxWidth: 560 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 56 }}>
          <div style={{ width: 36, height: 36, borderRadius: 999, background: 'var(--ink)', position: 'relative' }}>
            <div style={{ position: 'absolute', inset: 6, borderRadius: 999,
              background: 'var(--accent)', animation: 'breathe 3.2s ease-in-out infinite' }} />
          </div>
          <div>
            <div style={{ fontWeight: 700, fontSize: 18 }}>Floating Coach</div>
            <div className="mono" style={{ fontSize: 10, color: 'var(--ink-4)', textTransform: 'uppercase', letterSpacing: '.18em', marginTop: 1 }}>
              Persoonlijke AI sportcoach
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', gap: 8, marginBottom: 40 }}>
          {steps.map((s, i) => (
            <div key={i} style={{ flex: 1 }}>
              <div style={{ height: 3, borderRadius: 2, background: i <= step ? 'var(--ink)' : 'var(--line-strong)' }} />
            </div>
          ))}
        </div>

        <div className="card" style={{ padding: 36, minHeight: 320 }}>
          {step === 0 && (
            <div>
              <h1 style={{ fontSize: 44, fontWeight: 600, letterSpacing: '-.025em', margin: 0, lineHeight: 1.05 }}>
                Een coach die meedenkt.<br/>
                <em style={{ fontStyle: 'normal', color: 'var(--ink-4)' }}>Niet alleen meet.</em>
              </h1>
              <p style={{ fontSize: 16, lineHeight: 1.55, color: 'var(--ink-2)', marginTop: 22 }}>
                Verbind je Garmin en krijg dagelijks inzicht in belasting, herstel en je volgende training.
              </p>
              <div style={{ marginTop: 30, display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                <button className="btn lg accent" onClick={startOAuth} disabled={connecting}>
                  {connecting ? 'Doorsturen…' : 'Verbind Garmin'} <span className="arrow">→</span>
                </button>
                <button className="btn ghost" onClick={() => setStep(1)} disabled={connecting}>Bekijk demo</button>
              </div>
              {connectError && (
                <div style={{ marginTop: 16, padding: '12px 14px', borderRadius: 10,
                  background: 'oklch(96% 0.04 25)', border: '1px solid oklch(88% 0.08 25)' }}>
                  <p style={{ margin: 0, fontSize: 13, color: 'var(--bad)' }}>{connectError}</p>
                  <button className="btn ghost" style={{ marginTop: 10, padding: '6px 12px', fontSize: 12 }}
                    onClick={() => { setConnectError(null); startOAuth(); }}>Opnieuw proberen</button>
                </div>
              )}
            </div>
          )}
          {step === 1 && (
            <div>
              <h1 style={{ fontSize: 36, fontWeight: 600, margin: 0 }}>Klaar om te starten</h1>
              <p style={{ fontSize: 15, color: 'var(--ink-3)', marginTop: 18 }}>
                Sync na Garmin-koppeling kan enkele minuten duren. In demo zie je fictieve data.
              </p>
              <button className="btn lg accent" style={{ marginTop: 28 }} onClick={() => onComplete()}>
                Naar vandaag <span className="arrow">→</span>
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

window.OnboardingScreen = OnboardingScreen;
