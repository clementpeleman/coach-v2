// Coach chat — full page version (vs. floating orb).
const { useState: useStateC, useEffect: useEffectC, useRef: useRefC } = React;
const FCU = window.FC_UTILS;

function ChatScreen({
  recoveryScore, recoveryData, weather, apiStatus, userId,
  trainingProfile, chatMessages, setChatMessages, chatThinking, setChatThinking, resetChat,
}) {
  const D = window.FC_DATA;
  const R = recoveryData || D.recovery;
  const online = apiStatus === 'online';
  const activitiesQuery = window.useLiveData(
    (uid) => window.FC_API.fetchGarminActivities(uid, 1, 30),
    { activities: D.activities },
    [],
    { online, userId },
  );
  const recentActivity = activitiesQuery.data.activities?.[0] || D.activities[0];
  const messages = chatMessages || D.chatSeed;
  const setMessages = setChatMessages;
  const thinking = chatThinking;
  const setThinking = setChatThinking;
  const [draft, setDraft] = useStateC('');
  const [lastError, setLastError] = useStateC(null);
  const scrollRef = useRefC(null);

  useEffectC(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages, thinking]);

  useEffectC(() => {
    let pending = null;
    try {
      const raw = window.sessionStorage.getItem('fc_pending_chat_messages');
      if (raw) {
        pending = JSON.parse(raw);
        window.sessionStorage.removeItem('fc_pending_chat_messages');
      }
    } catch (_) {}
    if (!Array.isArray(pending) || !pending.length) return;
    setMessages((current) => {
      const existingIds = new Set((current || []).map((message) => message.id).filter(Boolean));
      const unique = pending.filter((message) => !message.id || !existingIds.has(message.id));
      return [...(current || D.chatSeed), ...unique];
    });
  }, []);

  const send = async (text) => {
    const t = (text || draft).trim();
    if (!t) return;
    const nextHistory = [...messages, { role: 'user', content: t, time: FCU.fmtTime(new Date().toISOString()) }];
    setMessages(nextHistory);
    setDraft('');
    setThinking(true);
    setLastError(null);

    // Live path: call /web/chat if API is online + user is logged in.
    if (online && userId) {
      try {
        const res = await window.FC_API.sendChatMessage({
          userId,
          message: t,
          // The backend keeps its own state — we still pass history to seed context.
          history: messages.map((m) => ({ role: m.role, content: m.content })),
          context: {
            weather,
            recovery: {
              score: recoveryScore,
              label: FCU.recoveryLabel(recoveryScore),
              metrics: R,
            },
            workout_patterns: trainingProfile?.workout_patterns || null,
          },
        });
        setMessages((m) => [...m, {
          role: 'assistant', content: res.reply,
          time: FCU.fmtTime(new Date().toISOString()), source: 'live',
        }]);
      } catch (e) {
        setLastError(e.message);
        // Fall back to mock reply so the conversation stays usable
        setMessages((m) => [...m, {
          role: 'assistant',
          content: `<i>Demo antwoord (backend onbereikbaar):</i><br/><br/>${mockReplyChat(t, recoveryScore, R)}`,
          time: FCU.fmtTime(new Date().toISOString()), source: 'demo',
        }]);
      } finally {
        setThinking(false);
      }
      return;
    }

    // Offline / no user: scripted reply.
    setTimeout(() => {
      setMessages((m) => [...m, {
        role: 'assistant',
        content: mockReplyChat(t, recoveryScore, R),
        time: FCU.fmtTime(new Date().toISOString()),
        source: 'demo',
      }]);
      setThinking(false);
    }, 1300);
  };

  return (
    <div data-screen-label="Coach chat" style={{ display: 'grid',
        gridTemplateColumns: '1fr 320px', gap: 24, minHeight: 'calc(100vh - 90px)' }}>
      {/* Chat column */}
      <div className="card" style={{ display: 'flex', flexDirection: 'column',
          padding: 0, overflow: 'hidden' }}>
        <div style={{ padding: '22px 28px', borderBottom: '1px solid var(--line)',
                      display: 'flex', alignItems: 'center', gap: 14 }}>
          <div style={{
            width: 42, height: 42, borderRadius: 999,
            background: 'linear-gradient(150deg, var(--accent), color-mix(in oklab, var(--accent) 60%, var(--ink)))',
            position: 'relative'
          }}>
            <div style={{ position:'absolute', top:15, left:12, width:6, height:6, borderRadius:999, background:'var(--ink)' }}></div>
            <div style={{ position:'absolute', top:15, right:12, width:6, height:6, borderRadius:999, background:'var(--ink)' }}></div>
            <div style={{ position:'absolute', left:13, right:13, bottom:11, height:3, borderRadius:'0 0 6px 6px', background:'var(--ink)' }}></div>
          </div>
          <div style={{ flex: 1 }}>
            <h2>Coach</h2>
            <div className="mono" style={{ fontSize: 11, color: 'var(--ink-4)',
              textTransform: 'uppercase', letterSpacing: '.14em', marginTop: 4 }}>
              <span className="live-dot"
                style={{ marginRight: 6, verticalAlign: 'middle',
                  background: online ? 'var(--good)' : 'var(--ink-4)' }}></span>
              {online && userId ? 'LangGraph agent · live' : online ? 'Wachten op login' : 'Demo modus · backend offline'}
              {' · '}Recovery {recoveryScore}/6
            </div>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={resetChat} className="btn ghost" style={{ padding: '8px 12px', fontSize: 12 }}>
              <span className="mono">↻</span> Nieuw gesprek
            </button>
          </div>
        </div>

        <div ref={scrollRef} className="scroll" style={{
          flex: 1, padding: '32px 28px', display: 'flex', flexDirection: 'column', gap: 18,
        }}>
          {messages.map((m, i) => (
            <BigBubble key={i} m={m} />
          ))}
          {lastError && (
            <div className="mono" style={{ fontSize: 11, color: 'var(--bad)',
              padding: '6px 10px', borderRadius: 8,
              background: 'oklch(96% 0.04 30)', alignSelf: 'flex-start',
              maxWidth: '78%' }}>
              ⚠ {lastError}
            </div>
          )}
          {thinking && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--ink-4)' }}>
              <ThinkDot d={0} /><ThinkDot d={.2} /><ThinkDot d={.4} />
              <span className="mono" style={{ fontSize: 10, textTransform: 'uppercase',
                letterSpacing: '.14em' }}>Coach denkt na…</span>
            </div>
          )}
        </div>

        {/* Quick prompts */}
        {messages.length < 3 && (
          <div style={{ padding: '0 28px 14px', display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {D.coachSuggestions.map((s) => (
              <button key={s} onClick={() => send(s)} className="tag"
                style={{ border: '1px solid var(--line)', background: 'transparent',
                  cursor: 'pointer', padding: '8px 14px', fontSize: 12 }}>
                {s}
              </button>
            ))}
          </div>
        )}

        {/* Composer */}
        <div style={{ padding: '20px 28px 24px', borderTop: '1px solid var(--line)',
                      display: 'flex', gap: 10, alignItems: 'center' }}>
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') send(); }}
            placeholder="Typ je vraag of vraag een training aan…"
            style={{ flex: 1, border: '1px solid var(--line-strong)', borderRadius: 999,
                      padding: '14px 18px', fontSize: 15, outline: 'none',
                      fontFamily: 'inherit', background: 'var(--bg)' }}
          />
          <button onClick={() => send()} className="btn accent" style={{ padding: '14px 20px' }}>
            Verstuur <span className="arrow">↑</span>
          </button>
        </div>
      </div>

      {/* Side context column */}
      <div className="col" style={{ gap: 16 }}>
        <div className="card tight">
          <div className="label" style={{ marginBottom: 12 }}>Coach toolkit</div>
          {['Genereer workout', 'Analyseer trainingsweek', 'Herstel check', 'Vergelijk activiteiten', 'Plan een wedstrijd'].map((t) => (
            <div key={t} style={{
              padding: '10px 12px', borderRadius: 8, fontSize: 13,
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              cursor: 'pointer', marginBottom: 2,
            }}
              onMouseEnter={(e) => e.currentTarget.style.background = 'var(--bg-soft)'}
              onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
              onClick={() => send(t.toLowerCase())}>
              <span>{t}</span>
              <span className="mono" style={{ color: 'var(--ink-4)' }}>→</span>
            </div>
          ))}
        </div>

        <div className="card tight" style={{ background: 'var(--bg-soft)', borderColor: 'transparent' }}>
          <div className="label" style={{ marginBottom: 12 }}>Context vandaag</div>
          <ContextRow k="Slaap" v={R.sleepHours ? `${R.sleepHours.toFixed(1)}u (score ${R.sleepScore ?? '–'})` : 'Geen slaapdata'} />
          <ContextRow k="Body Battery ontwaken" v={(R.bodyBatteryAtWake ?? R.bodyBattery) == null ? 'Geen data' : `${R.bodyBatteryAtWake ?? R.bodyBattery}%`} />
          <ContextRow k="HRV overnight" v={R.hrvOvernight == null ? 'Geen data' : `${R.hrvOvernight}ms`} />
          <ContextRow k="Resting HR" v={R.restingHr == null ? 'Geen data' : `${R.restingHr} bpm`} />
          <ContextRow k="Stress" v={R.avgStress == null ? 'Geen data' : `${R.avgStress}/100`} />
          <ContextRow k="Recovery" v={`${recoveryScore}/6 · ${FCU.recoveryLabel(recoveryScore)}`} />
        </div>

        <div className="card tight">
          <div className="label" style={{ marginBottom: 10 }}>Recente activiteit</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{
              width: 36, height: 36, borderRadius: 8, background: 'var(--bg-soft)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontFamily: "'JetBrains Mono', monospace", fontWeight: 700,
            }}>↗</div>
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 500, fontSize: 14 }}>{recentActivity.activity_name}</div>
              <div className="mono" style={{ fontSize: 11, color: 'var(--ink-4)', marginTop: 2 }}>
                {(recentActivity.distance_meters / 1000).toFixed(1)} km · {FCU.fmtDuration(recentActivity.duration_seconds)} · {recentActivity.average_heart_rate ?? '–'} bpm
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function ContextRow({ k, v }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between',
                  alignItems: 'baseline', padding: '6px 0',
                  borderBottom: '1px solid color-mix(in oklab, var(--ink) 8%, transparent)' }}>
      <span style={{ fontSize: 12, color: 'var(--ink-3)' }}>{k}</span>
      <span className="mono" style={{ fontSize: 12, fontWeight: 500,
        fontVariantNumeric: 'tabular-nums' }}>{v}</span>
    </div>
  );
}

function BigBubble({ m }) {
  const isUser = m.role === 'user';
  return (
    <div style={{ display: 'flex', flexDirection: 'column',
                  alignItems: isUser ? 'flex-end' : 'flex-start', gap: 6,
                  maxWidth: '78%', alignSelf: isUser ? 'flex-end' : 'flex-start' }}>
      <div style={{
        background: isUser ? 'var(--ink)' : 'var(--bg-soft)',
        color: isUser ? '#fff' : 'var(--ink)',
        padding: '14px 18px',
        borderRadius: isUser ? '18px 18px 4px 18px' : '18px 18px 18px 4px',
        fontSize: 15, lineHeight: 1.55,
      }} dangerouslySetInnerHTML={{ __html: m.content }} />
      <div className="mono" style={{ fontSize: 10, color: 'var(--ink-4)',
                                      letterSpacing: '.1em', textTransform: 'uppercase' }}>
        {isUser ? 'Jij' : 'Coach'} · {m.time}
      </div>
    </div>
  );
}

function ThinkDot({ d }) {
  return <span style={{
    width: 7, height: 7, borderRadius: 999, background: 'var(--ink-4)',
    display: 'inline-block', animation: `bounce 1s ease-in-out ${d}s infinite`,
  }}></span>;
}

function mockReplyChat(text, score, recoveryData) {
  const t = text.toLowerCase();
  const R = recoveryData || window.FC_DATA.recovery;
  if (t.includes('slaap')) return `Je slaap staat op <b>${R.sleepHours ? `${R.sleepHours.toFixed(1)} uur` : 'geen data'}</b> met sleep score <b>${R.sleepScore ?? 'geen data'}</b>. Diepe slaap ${R.deepSleepMin ?? '–'} min, REM ${R.remMin ?? '–'} min, awake ${R.awakeMin ?? '–'} min. Body Battery bij ontwaken staat op ${R.bodyBatteryAtWake ?? R.bodyBattery ?? '–'}%.<br/><br/>Dat is de meest recente Garmin-data die ik lokaal heb.`;
  if (t.includes('herstel') || t.includes('recovery') || t.includes('herstel check')) return `<b>Herstelscore ${score}/6 — ${FCU.recoveryLabel(score)}</b><br/><br/>${FCU.recoveryAdvice(score)} HRV staat op <b>${R.hrvOvernight ?? '–'}ms</b>. Resting HR <b>${R.restingHr ?? '–'} bpm</b>.`;
  if (t.includes('duur')) return `Klaargezet. <b>75 min duurloop</b>, zone 2 (HR 138-152). Warming-up 8 min, duurblok 60 min, cooling-down 7 min. <i>FIT-bestand staat in Garmin Connect.</i><br/><br/>Wil je dat ik er ook een drinkmoment inplan?`;
  if (t.includes('interval') || t.includes('tempo') || t.includes('drempel')) return `<b>2× 12 min tempo</b> met 4 min herstel tussendoor.<br/><br/>WU 12 min easy · 12 min @ drempel (162-168) · 4 min easy · 12 min @ drempel · CD 8 min<br/><br/>Wil je dit nu starten?`;
  if (t.includes('analyseer') || t.includes('trainingsweek') || t.includes('week') || t.includes('activiteit')) return `<b>Deze week:</b><br/>· 3 sessies · 31 km · 3u 06min<br/>· Volume <span style="color:#c0392b">29% onder</span> 4-weken gemiddelde<br/>· Intensiteit op peil (1× drempel woensdag)<br/><br/>Voeg dit weekend een duurloop van 75-90 min toe om je weekvolume in balans te brengen.`;
  if (t.includes('vergelijk')) return `Tussen je <b>Tempo 4×5 min</b> (6/5) en <b>Intervaltraining 6×800m</b> (11/5):<br/>· Avg HR daalde van 158 → 163 bpm (zelfde inspanning, +5 bpm hoger door snellere tempo)<br/>· Pace was 8% sneller deze week<br/>· Beide sessies aan boven-drempel`;
  if (t.includes('wedstrijd') || t.includes('plan')) return `Welke wedstrijd plan je? Geef datum en afstand, dan zet ik een meerwekenplan op met intensiteits- en taperfases. Bv. <i>"10 km op 14 juni"</i>.`;
  if (t.includes('genereer workout')) return `Welke training wil je? Kies type en duur, of laat het aan mij over op basis van je <b>recovery ${score}/6</b>. Voorbeelden: <i>"45 min tempo"</i>, <i>"makkelijke duurloop 60 min"</i>.`;
  return `Begrepen. Op basis van je <b>recovery ${score}/6</b> raad ik vandaag een ${FCU.recoveryAdvice(score).toLowerCase()}<br/><br/>Wil je dat ik een concrete sessie klaarzet?`;
}

window.ChatScreen = ChatScreen;
