// Onboarding / Garmin connect.
const { useState: useStateO } = React;

function OnboardingScreen({ onComplete, apiStatus }) {
  const [step, setStep] = useStateO(0);
  const [email, setEmail] = useStateO('');
  const [name, setName] = useStateO('');
  const [connecting, setConnecting] = useStateO(false);
  const [connectError, setConnectError] = useStateO(null);
  const online = apiStatus === 'online';

  const startOAuth = async () => {
    setConnecting(true);
    setConnectError(null);
    if (!online) {
      // Demo mode — fake the redirect.
      setTimeout(() => { setConnecting(false); setStep(3); }, 1600);
      return;
    }
    try {
      const existingId = window.FC_SESSION.readUserId();
      const res = await window.FC_API.startDirectGarminOAuth({
        userId: existingId || undefined,
        email,
        displayName: name || undefined,
      });
      window.FC_SESSION.writeUserId(res.user_id);
      // Hand off to Garmin's OAuth screen — they'll redirect back to the configured callback.
      window.location.href = res.authorization_url;
    } catch (e) {
      setConnectError(e.message || 'OAuth start mislukt.');
      setConnecting(false);
    }
  };

  const steps = [
    { label: 'Welkom', n: 1 },
    { label: 'Account', n: 2 },
    { label: 'Garmin', n: 3 },
    { label: 'Klaar', n: 4 },
  ];

  return (
    <div className="splash" data-screen-label="Onboarding">
      <div style={{ width: '100%', maxWidth: 560 }}>
        {/* Brand */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 56 }}>
          <div style={{ width: 36, height: 36, borderRadius: 999, background: 'var(--ink)',
                        position: 'relative' }}>
            <div style={{ position: 'absolute', inset: 6, borderRadius: 999,
              background: 'var(--accent)', animation: 'breathe 3.2s ease-in-out infinite' }}></div>
          </div>
          <div>
            <div style={{ fontWeight: 700, fontSize: 18 }}>Floating Coach</div>
            <div className="mono" style={{ fontSize: 10, color: 'var(--ink-4)',
              textTransform: 'uppercase', letterSpacing: '.18em', marginTop: 1 }}>
              Persoonlijke AI sportcoach
            </div>
          </div>
        </div>

        {/* Step indicator */}
        <div style={{ display: 'flex', gap: 8, marginBottom: 40 }}>
          {steps.map((s, i) => (
            <div key={i} style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 8 }}>
              <div style={{ height: 3, borderRadius: 2,
                background: i <= step ? 'var(--ink)' : 'var(--line-strong)',
                transition: 'background .3s' }}></div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span className="mono" style={{ fontSize: 11, fontWeight: 500,
                  color: i <= step ? 'var(--ink)' : 'var(--ink-4)' }}>
                  0{s.n}
                </span>
                <span className="mono" style={{ fontSize: 10, color: 'var(--ink-4)',
                  textTransform: 'uppercase', letterSpacing: '.14em' }}>{s.label}</span>
              </div>
            </div>
          ))}
        </div>

        {/* Step content */}
        <div className="card" style={{ padding: 36, minHeight: 380 }}>
          {step === 0 && (
            <div>
              <h1 style={{ fontSize: 44, fontWeight: 600, letterSpacing: '-.025em',
                            margin: 0, lineHeight: 1.05 }}>
                Een coach die meedenkt.<br/>
                <em style={{ fontStyle: 'normal', color: 'var(--ink-4)' }}>Niet alleen meet.</em>
              </h1>
              <p style={{ fontSize: 16, lineHeight: 1.55, color: 'var(--ink-2)',
                          marginTop: 22, maxWidth: 460 }}>
                Verbind je Garmin en chat met je AI-coach. Op basis van je slaap,
                stress en HRV stelt hij dagelijks de juiste training voor —
                en levert die rechtstreeks aan je horloge.
              </p>
              <ul style={{ marginTop: 24, padding: 0, listStyle: 'none',
                          display: 'flex', flexDirection: 'column', gap: 10 }}>
                {[
                  ['🇳🇱', 'Volledig Nederlandstalig'],
                  ['⌚', 'Garmin OAuth2 - geen wachtwoord, tokens versleuteld'],
                  ['🧠', 'Workouts aangepast aan je herstel (0-6)'],
                  ['📥', 'Rustige eerste import: activiteiten + core health'],
                ].map(([ico, t]) => (
                  <li key={t} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <span className="mono" style={{
                      width: 26, height: 26, borderRadius: 7, background: 'var(--bg-soft)',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      fontSize: 13,
                    }}>{ico}</span>
                    <span style={{ fontSize: 14, color: 'var(--ink-2)' }}>{t}</span>
                  </li>
                ))}
              </ul>
              <div style={{ marginTop: 30, display: 'flex', gap: 10 }}>
                <button className="btn lg accent" onClick={() => setStep(1)}>
                  Aan de slag <span className="arrow">→</span>
                </button>
                <button className="btn ghost" onClick={() => onComplete()}>
                  Bekijk de demo
                </button>
              </div>
            </div>
          )}

          {step === 1 && (
            <div>
              <h1 style={{ fontSize: 36, fontWeight: 600, letterSpacing: '-.02em',
                            margin: 0, lineHeight: 1.1 }}>
                Hoe heet je?
              </h1>
              <p style={{ fontSize: 15, lineHeight: 1.55, color: 'var(--ink-3)',
                          marginTop: 14 }}>
                We koppelen je email aan een interne user-ID. Geen wachtwoord nodig.
              </p>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 20, marginTop: 28, maxWidth: 380 }}>
                <div className="field">
                  <label>Email</label>
                  <input value={email} onChange={(e) => setEmail(e.target.value)}
                          type="email" placeholder="jij@voorbeeld.com" autoFocus />
                </div>
                <div className="field">
                  <label>Naam (optioneel)</label>
                  <input value={name} onChange={(e) => setName(e.target.value)}
                          type="text" placeholder="Jouw naam" />
                </div>
              </div>
              <div style={{ marginTop: 28, display: 'flex', gap: 10 }}>
                <button className="btn ghost" onClick={() => setStep(0)}>← Terug</button>
                <button className="btn lg" onClick={() => setStep(2)}
                        disabled={!email.includes('@')}
                        style={{ opacity: email.includes('@') ? 1 : 0.4 }}>
                  Volgende <span className="arrow">→</span>
                </button>
              </div>
            </div>
          )}

          {step === 2 && (
            <div>
              <h1 style={{ fontSize: 36, fontWeight: 600, letterSpacing: '-.02em',
                            margin: 0, lineHeight: 1.1 }}>
                Verbind Garmin
              </h1>
              <p style={{ fontSize: 15, lineHeight: 1.55, color: 'var(--ink-3)',
                          marginTop: 14, maxWidth: 460 }}>
                Verbind via Garmin's officiële OAuth2 flow. Geen wachtwoord, geen
                opslag van je inloggegevens. Tokens worden Fernet-versleuteld.
              </p>

              <div style={{ marginTop: 28, padding: 22, background: 'var(--bg-soft)',
                            borderRadius: 16, display: 'flex', gap: 16, alignItems: 'center' }}>
                <div style={{ width: 56, height: 56, borderRadius: 12,
                  background: 'var(--ink)', color: 'var(--accent)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 26, fontFamily: "'JetBrains Mono', monospace" }}>⌚</div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 600, fontSize: 15 }}>Garmin Connect</div>
                  <div className="mono" style={{ fontSize: 11, color: 'var(--ink-4)',
                    textTransform: 'uppercase', letterSpacing: '.12em', marginTop: 4 }}>
                    Health API · Activity API · Workout upload
                  </div>
                </div>
                {connecting && (
                  <div className="mono" style={{ fontSize: 11, color: 'var(--ink-4)' }}>
                    <span className="live-dot" style={{ marginRight: 6 }}></span>
                    Verbinden…
                  </div>
                )}
              </div>

              <ul style={{ marginTop: 22, padding: 0, listStyle: 'none', display: 'flex',
                          flexDirection: 'column', gap: 10 }}>
                {[
                  'Slaap, HRV en stress voor herstelscore',
                  'Activiteiten - hardlopen, fietsen, zwemmen',
                  'Trainingen direct uploaden naar je horloge',
                  'Historische data wordt via Garmin webhooks aangeleverd',
                ].map(t => (
                  <li key={t} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <span style={{ color: 'var(--accent)', fontFamily: "'JetBrains Mono', monospace" }}>✓</span>
                    <span style={{ fontSize: 13, color: 'var(--ink-2)' }}>{t}</span>
                  </li>
                ))}
              </ul>

              <div style={{ marginTop: 28, display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
                <button className="btn ghost" onClick={() => setStep(1)}>← Terug</button>
                <button className="btn lg accent" onClick={startOAuth} disabled={connecting}>
                  {connecting ? 'Doorsturen naar Garmin…' : (online ? 'Verbind via OAuth2' : 'Demo verbinding')} <span className="arrow">→</span>
                </button>
                {!online && (
                  <span className="mono" style={{ fontSize: 10, color: 'var(--ink-4)',
                    textTransform: 'uppercase', letterSpacing: '.14em' }}>
                    Backend offline · demo
                  </span>
                )}
              </div>
              {connectError && (
                <p className="mono" style={{ marginTop: 10, fontSize: 12, color: 'var(--bad)' }}>
                  ⚠ {connectError}
                </p>
              )}
            </div>
          )}

          {step === 3 && (
            <div>
              <div style={{
                width: 72, height: 72, borderRadius: 999, background: 'var(--accent)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 32, marginBottom: 24,
              }}>✓</div>
              <h1 style={{ fontSize: 36, fontWeight: 600, letterSpacing: '-.02em',
                            margin: 0, lineHeight: 1.1 }}>
                Klaar.<br/>
                <em style={{ fontStyle: 'normal', color: 'var(--ink-4)' }}>
                  Je coach is online.
                </em>
              </h1>
              <p style={{ fontSize: 15, lineHeight: 1.55, color: 'var(--ink-3)',
                          marginTop: 18, maxWidth: 460 }}>
                We vragen nu gecontroleerd je <b>laatste 30 dagen activiteiten</b>
                en <b>7 dagen core health</b> op. Garmin levert die data via
                webhooks; meestal zie je de eerste records binnen enkele minuten.
              </p>

              <div style={{ marginTop: 24, padding: 16, background: 'var(--bg-soft)',
                            borderRadius: 12, display: 'flex', alignItems: 'center', gap: 14 }}>
                <span className="live-dot"></span>
                <div style={{ flex: 1 }}>
                  <div className="mono" style={{ fontSize: 11, color: 'var(--ink-2)',
                    textTransform: 'uppercase', letterSpacing: '.14em' }}>
                    Eerste import aangevraagd
                  </div>
                  <div style={{ height: 6, background: 'rgba(13,14,11,.12)', borderRadius: 3, marginTop: 6,
                                overflow: 'hidden' }}>
                    <div style={{ height: '100%', width: '38%', background: 'var(--accent)',
                                  borderRadius: 3, animation: 'fill 2s ease-out forwards' }}></div>
                  </div>
                </div>
                <span className="mono" style={{ fontSize: 11, color: 'var(--ink-3)' }}>38%</span>
              </div>

              <div style={{ marginTop: 28, display: 'flex', gap: 10 }}>
                <button className="btn lg accent" onClick={() => onComplete()}>
                  Naar dashboard <span className="arrow">→</span>
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Skip */}
        {step < 3 && (
          <div style={{ marginTop: 18, textAlign: 'center' }}>
            <button onClick={() => onComplete()}
              style={{ background: 'transparent', border: 'none', cursor: 'pointer',
                color: 'var(--ink-4)', fontSize: 12, fontFamily: 'inherit' }}>
              Sla over · bekijk de demo
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

if (!document.getElementById('__fc-onb-css')) {
  const s = document.createElement('style');
  s.id = '__fc-onb-css';
  s.textContent = `@keyframes fill { from { width: 0; } to { width: 38%; } }`;
  document.head.appendChild(s);
}

window.OnboardingScreen = OnboardingScreen;
