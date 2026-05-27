// Floating Coach orb - persistent, click to expand into chat panel.
const { useState, useEffect, useRef } = React;
const { fmtTime, recoveryLabel, recoveryAdvice } = window.FC_UTILS;

function CoachOrb({
  recoveryScore, recoveryData, weather, apiStatus, userId,
  trainingProfile, draftWorkout, setDraftWorkout, messages, setMessages, thinking, setThinking,
  currentScreen, onNavigateChat,
}) {
  const { formatApiError } = window.FC_UTILS;
  const online = apiStatus === 'online';
  const R = recoveryData || window.FC_DATA.recovery;
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState('');
  const [chatError, setChatError] = useState(null);
  const scrollRef = useRef(null);

  useEffect(() => {
    const openPanel = () => setOpen(true);
    window.addEventListener('fc-open-coach-orb', openPanel);
    return () => window.removeEventListener('fc-open-coach-orb', openPanel);
  }, []);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, open, thinking]);

  const send = async (text) => {
    if (!text.trim()) return;
    const userMsg = { role: 'user', content: text, time: fmtTime(new Date().toISOString()) };
    const history = [...messages, userMsg];
    setMessages(history);
    setDraft('');
    setThinking(true);
    setChatError(null);
    const lastAnalysisContext = [...(messages || [])]
      .reverse()
      .find((message) => message.analysis_result?.context)?.analysis_result?.context || null;

    if (online && userId) {
      try {
        let contextDraft = draftWorkout;
        if (window.FC_API.adjustTrainingRecommendation && (draftWorkout || window.FC_WORKOUT_PLAN)) {
          try {
            const adjusted = await window.FC_API.adjustTrainingRecommendation({
              userId,
              recommendation: draftWorkout || window.FC_WORKOUT_PLAN?.buildDraft({ recoveryScore, trainingProfile }),
              instruction: text,
              trainingProfile,
            });
            if (adjusted?.changedByInstruction) {
              contextDraft = adjusted;
              setDraftWorkout?.(() => adjusted);
            }
          } catch (_) {}
        }
        const res = await window.FC_API.sendChatMessage({
          userId, message: text,
          history: messages.map((m) => ({ role: m.role, content: m.content })),
          context: {
            weather,
            recovery: {
              score: recoveryScore,
              label: recoveryLabel(recoveryScore),
              metrics: R,
            },
            training_profile: trainingProfile || null,
            workout_patterns: trainingProfile?.workout_patterns || null,
            draft_workout: contextDraft || null,
            last_analysis_context: lastAnalysisContext,
          },
        });
        if (res.draft_workout) setDraftWorkout?.(() => res.draft_workout);
        setMessages((m) => [...m, {
          role: 'assistant',
          content: res.reply,
          time: fmtTime(new Date().toISOString()),
          source: 'live',
          analysis_result: res.analysis_result || null,
        }]);
      } catch (e) {
        setChatError(formatApiError(e.message));
        setMessages((m) => [...m, { role: 'assistant',
          content: `<i>Demo (backend offline):</i><br/>${mockReply(text, recoveryScore, R)}`,
          time: fmtTime(new Date().toISOString()) }]);
      } finally {
        setThinking(false);
      }
      return;
    }
    setTimeout(() => {
      const reply = mockReply(text, recoveryScore, R);
      setMessages((m) => [...m, { role: 'assistant', content: reply, time: fmtTime(new Date().toISOString()) }]);
      setThinking(false);
    }, 1400);
  };

  return (
    <div className="orb-wrap" data-screen-label="Floating Coach orb">
      {open && (
        <div className="coach-panel" role="dialog" aria-label="Coach chat" onClick={(e) => e.stopPropagation()}>
          {/* Header */}
          <div style={{ padding: '18px 20px 14px', borderBottom: '1px solid var(--line)',
                        display: 'flex', alignItems: 'center', gap: 12 }}>
            <div className="orb-face-mini">
              <div style={{
                width: 36, height: 36, borderRadius: 999,
                background: 'linear-gradient(150deg, var(--accent), color-mix(in oklab, var(--accent) 60%, var(--ink)))',
                position: 'relative', flexShrink: 0
              }}>
                <div style={{ position:'absolute', top:13, left:10, width:5, height:5, borderRadius:999, background:'var(--ink)' }}></div>
                <div style={{ position:'absolute', top:13, right:10, width:5, height:5, borderRadius:999, background:'var(--ink)' }}></div>
                <div style={{ position:'absolute', left:11, right:11, bottom:10, height:3,
                              borderRadius:'0 0 6px 6px', background:'var(--ink)' }}></div>
              </div>
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 14, fontWeight: 600, letterSpacing: '-.01em' }}>
                Coach <span style={{ color: 'var(--ink-4)', fontWeight: 500 }}>· online</span>
              </div>
              <div className="mono" style={{ fontSize: 10, color: 'var(--ink-4)',
                                              textTransform: 'uppercase', letterSpacing: '.14em',
                                              marginTop: 2 }}>
                Recovery {recoveryScore}/6
              </div>
            </div>
            <button onClick={() => setOpen(false)} aria-label="Close" style={{
              border: 'none', background: 'transparent', cursor: 'pointer',
              padding: 6, color: 'var(--ink-3)', fontSize: 18, lineHeight: 1
            }}>✕</button>
          </div>

          {/* Messages */}
          <div ref={scrollRef} className="scroll" style={{
            flex: 1, padding: '18px 20px', display: 'flex', flexDirection: 'column', gap: 14,
            minHeight: 320, maxHeight: 380,
          }}>
            {messages.map((m, i) => (
              <ChatBubble key={i} m={m} onNavigateChat={onNavigateChat} onClose={() => setOpen(false)} />
            ))}
            {chatError && (
              <p style={{ margin: 0, fontSize: 12, color: 'var(--bad)' }}>{chatError}</p>
            )}
            {thinking && (
              <div style={{ display: 'flex', gap: 6, paddingLeft: 4 }}>
                <Dot delay={0} /><Dot delay={.2} /><Dot delay={.4} />
              </div>
            )}
          </div>

          {/* Quick suggestions */}
          {messages.length < 5 && !thinking && (
            <div style={{ padding: '0 20px 14px', display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {window.FC_DATA.coachSuggestions.slice(0, 3).map((s) => (
                <button key={s} onClick={() => send(s)} className="tag"
                        style={{ border: '1px solid var(--line)', background: 'transparent', cursor: 'pointer' }}>
                  {s}
                </button>
              ))}
            </div>
          )}

          {/* Composer */}
          <div style={{ padding: '14px 16px 16px', borderTop: '1px solid var(--line)',
                        display: 'flex', gap: 8, alignItems: 'center' }}>
            <input
              aria-label="Vraag iets aan je coach"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') send(draft); }}
              placeholder="Vraag iets aan je coach…"
              style={{ flex: 1, border: '1px solid var(--line-strong)', borderRadius: 999,
                        padding: '12px 16px', fontSize: 14, outline: 'none',
                        fontFamily: 'inherit' }}
            />
            <button onClick={() => send(draft)} className="btn accent" aria-label="Verstuur vraag" style={{ padding: '12px 14px' }}>
              <span className="mono">→</span>
            </button>
          </div>
        </div>
      )}

      <button type="button" className="orb"
        aria-label={open ? 'Sluit coach' : 'Open coach'}
        aria-expanded={open}
        onClick={() => {
          if (currentScreen === 'chat') return;
          setOpen((v) => !v);
        }}>
        <div className="face">
          <div className="mouth"></div>
          <div className="halo"></div>
        </div>
        <div className="meta">
          <div className="name">Klaar voor training</div>
          <div className="sub">
            Recovery {recoveryScore}/6
          </div>
        </div>
      </button>
    </div>
  );
}

function ChatBubble({ m, onNavigateChat, onClose }) {
  const isUser = m.role === 'user';
  const analysis = m.analysis_result || m.analysis || null;
  return (
    <div style={{ display: 'flex', flexDirection: 'column',
                  alignItems: isUser ? 'flex-end' : 'flex-start', gap: 4 }}>
      <div style={{
        maxWidth: '85%',
        background: isUser ? 'var(--ink)' : 'var(--bg-soft)',
        color: isUser ? 'var(--text-on-dark)' : 'var(--ink)',
        padding: '10px 14px',
        borderRadius: isUser ? '16px 16px 4px 16px' : '16px 16px 16px 4px',
        fontSize: 14, lineHeight: 1.5,
      }} dangerouslySetInnerHTML={{ __html: m.content }} />
      {!isUser && analysis && (
        <button type="button"
          onClick={() => {
            onClose?.();
            onNavigateChat?.();
          }}
          style={{
            border: '1px solid var(--line)',
            background: 'var(--surface)',
            borderRadius: 12,
            padding: '10px 12px',
            maxWidth: '85%',
            textAlign: 'left',
            cursor: 'pointer',
            color: 'var(--ink)',
            boxShadow: '0 10px 24px color-mix(in oklab, var(--ink) 7%, transparent)',
          }}>
          <span className="mono" style={{ display: 'block', fontSize: 9, color: 'var(--ink-4)', textTransform: 'uppercase', letterSpacing: '.12em', marginBottom: 4 }}>
            Analysekaart
          </span>
          <span style={{ display: 'block', fontSize: 13, fontWeight: 600 }}>{analysis.title || 'Bekijk grafiek'}</span>
          <span style={{ display: 'block', fontSize: 12, color: 'var(--ink-3)', marginTop: 2 }}>
            Open Coach-tab voor grafiek en tabel.
          </span>
        </button>
      )}
      <div className="mono" style={{ fontSize: 10, color: 'var(--ink-4)',
                                      letterSpacing: '.1em', textTransform: 'uppercase' }}>
        {m.time}
      </div>
    </div>
  );
}

function Dot({ delay }) {
  return <span style={{
    width: 6, height: 6, borderRadius: 999, background: 'var(--ink-4)',
    display: 'inline-block', animation: `thinking-pulse 1s cubic-bezier(.16,1,.3,1) ${delay}s infinite`,
  }}></span>;
}

function mockReply(text, score, recoveryData) {
  const t = text.toLowerCase();
  const R = recoveryData || window.FC_DATA.recovery;
  if (t.includes('slaap')) {
    const sleep = R.sleepHours ? `${R.sleepHours.toFixed(1)} uur` : 'nog niet beschikbaar';
    const batteryText = R.bodyBatteryAtWake != null
      ? `<i>Body Battery bij ontwaken</i>: ${R.bodyBatteryAtWake}%.`
      : `<i>Body Battery huidig</i>: ${R.bodyBatteryCurrent ?? R.bodyBattery ?? '–'}%.`;
    return `Je slaap staat op <b>${sleep}</b> met sleep score <b>${R.sleepScore ?? 'geen data'}</b>. Diepe slaap: ${R.deepSleepMin ?? '–'} min. ${batteryText}`;
  }
  if (t.includes('herstel') || t.includes('recovery')) return `Herstelscore is <b>${score}/6</b>: ${recoveryLabel(score)}. ${recoveryAdvice(score)}`;
  if (t.includes('duur') || t.includes('duurloop')) return `Klaargezet. <b>75 min duurloop</b>, zone 2, doel HR 138-152. <i>FIT-bestand staat in Garmin Connect.</i>`;
  if (t.includes('interval') || t.includes('tempo')) return `Geen probleem. <b>5× 4 min</b> op tempo, 90s herstel. Warming-up 12 min, cooling-down 8 min. Klaar om te starten?`;
  if (t.includes('activiteit') || t.includes('week')) return `Deze week: <b>3 sessies</b>, 31 km, 3u 06min. Volume ligt 29% onder je 4-weken gemiddelde. Tijd om dit weekend in te halen.`;
  return `Begrepen. Op basis van je <b>recovery ${score}/6</b> raad ik vandaag een ${recoveryAdvice(score).toLowerCase()}.`;
}

window.CoachOrb = CoachOrb;
