// Coach chat - full page version (vs. floating orb).
const { useState: useStateC, useEffect: useEffectC, useRef: useRefC } = React;
const FCU = window.FC_UTILS;

function ChatScreen({
  recoveryScore, recoveryData, recoverySnapshot, weather, apiStatus, userId, onNavigate,
  trainingProfile, chatMessages, setChatMessages, chatThinking, setChatThinking, resetChat,
  draftWorkout, setDraftWorkout,
}) {
  const D = window.FC_DATA;
  const R = recoveryData || D.recovery;
  const online = apiStatus === 'online';
  const dataSource = userId ? (recoverySnapshot?.source || 'empty') : 'demo';
  const activitiesQuery = window.useLiveData(
    (uid) => window.FC_API.fetchGarminActivities(uid, 1, 30),
    { activities: D.activities },
    [],
    { online, userId, cacheKey: 'chat_recent_activity', emptyData: { activities: [] } },
  );
  const recentActivity = activitiesQuery.data.activities?.[0] || (!userId ? D.activities[0] : null);
  const messages = chatMessages || D.chatSeed;
  const hasUserMessages = messages.some((message) => message.role === 'user');
  const setMessages = setChatMessages;
  const thinking = chatThinking;
  const setThinking = setChatThinking;
  const [draft, setDraft] = useStateC('');
  const [lastError, setLastError] = useStateC(null);
  const scrollRef = useRefC(null);
  const commitDraftWorkout = (updater) => {
    if (setDraftWorkout) {
      setDraftWorkout(updater);
      return;
    }
    window.FC_SET_DRAFT_WORKOUT?.(updater);
  };

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
    let draftUpdate = null;
    const nextHistory = [...messages, { role: 'user', content: t, time: FCU.fmtTime(new Date().toISOString()) }];
    setMessages(nextHistory);
    setDraft('');
    setThinking(true);
    setLastError(null);
    const lastAnalysisContext = [...(messages || [])]
      .reverse()
      .find((message) => message.analysis_result?.context)?.analysis_result?.context || null;

    // Live path: call /web/chat if API is online + user is logged in.
    if (online && userId) {
      try {
        let contextDraft = draftWorkout;
        if (window.FC_API.adjustTrainingRecommendation && (draftWorkout || window.FC_WORKOUT_PLAN)) {
          try {
            const adjusted = await window.FC_API.adjustTrainingRecommendation({
              userId,
              recommendation: draftWorkout || window.FC_WORKOUT_PLAN?.buildDraft({ recoveryScore, trainingProfile }),
              instruction: t,
              trainingProfile,
            });
            if (adjusted?.changedByInstruction) {
              contextDraft = adjusted;
              draftUpdate = { draft: adjusted, changed: true, summary: adjusted.note };
              commitDraftWorkout(() => adjusted);
            }
          } catch (_) {}
        }
        const res = await window.FC_API.sendChatMessage({
          userId,
          message: t,
          // The backend keeps its own state - we still pass history to seed context.
          history: messages.map((m) => ({ role: m.role, content: m.content })),
          context: {
            weather,
            recovery: {
              score: recoveryScore,
              label: FCU.recoveryLabel(recoveryScore),
              metrics: R,
            },
            training_profile: trainingProfile || null,
            workout_patterns: trainingProfile?.workout_patterns || null,
            draft_workout: draftUpdate?.draft || contextDraft || null,
            last_analysis_context: lastAnalysisContext,
          },
        });
        if (res.draft_workout) {
          commitDraftWorkout(() => res.draft_workout);
        }
        setMessages((m) => [...m, {
          role: 'assistant', content: res.reply,
          time: FCU.fmtTime(new Date().toISOString()), source: 'live',
          analysis_result: res.analysis_result || null,
        }]);
      } catch (e) {
        setLastError(FCU.formatApiError(e.message));
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

    if (window.FC_WORKOUT_PLAN) {
      commitDraftWorkout((current) => {
        const result = window.FC_WORKOUT_PLAN.updateDraftFromText(current || draftWorkout, t, { recoveryScore, trainingProfile });
        draftUpdate = result;
        return result.changed ? result.draft : (current || result.draft);
      });
    }

    // Offline / no user: scripted reply.
    setTimeout(() => {
      const adjustmentNote = draftUpdate?.changed
        ? `<br/><br/><i>${draftUpdate.summary || 'Trainingvoorstel aangepast.'}</i>`
        : '';
      setMessages((m) => [...m, {
        role: 'assistant',
        content: `${mockReplyChat(t, recoveryScore, R)}${adjustmentNote}`,
        time: FCU.fmtTime(new Date().toISOString()),
        source: 'demo',
      }]);
      setThinking(false);
    }, 1300);
  };

  return (
    <div data-screen-label="Coach chat" style={{ display: 'grid',
        gridTemplateColumns: 'minmax(0, 1fr) 360px', gap: 24, minHeight: 'calc(100vh - 90px)' }}>
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
            <BigBubble key={i} m={m} onSend={send} />
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

        {/* Example prompts */}
        {!hasUserMessages && !thinking && (
          <div style={{ padding: '0 28px 16px' }}>
            <div className="mono" style={{ fontSize: 10, color: 'var(--ink-4)',
              textTransform: 'uppercase', letterSpacing: '.14em', marginBottom: 9 }}>
              Voorbeelden
            </div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {D.coachSuggestions.map((s) => (
                <button key={s} onClick={() => send(s)}
                  style={{
                    border: '1px solid var(--line)',
                    background: 'var(--bg-soft)',
                    color: 'var(--ink)',
                    cursor: 'pointer',
                    padding: '10px 14px',
                    borderRadius: 18,
                    fontSize: 13,
                    fontFamily: 'inherit',
                    lineHeight: 1.25,
                  }}>
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Composer */}
        <div style={{ padding: '20px 28px 24px', borderTop: '1px solid var(--line)',
                      display: 'flex', gap: 10, alignItems: 'center' }}>
          <input
            aria-label="Bericht aan coach"
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
      <div className="col" style={{ gap: 16, alignSelf: 'start' }}>
        <TrainingProposalCard
          draftWorkout={draftWorkout}
          setDraftWorkout={setDraftWorkout}
          onNavigate={onNavigate}
          recoveryScore={recoveryScore}
          trainingProfile={trainingProfile}
          dataSource={dataSource}
        />

        <div className="card tight">
          <div className="label" style={{ marginBottom: 12 }}>Coach toolkit</div>
          {['Genereer workout', 'Analyseer trainingsweek', 'Vergelijk 30 dagen', 'Tempo vs hartslag', 'HR-respons in blokken', 'Workoutpatronen'].map((t) => (
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
          <ContextRow k={R.bodyBatteryAtWake == null ? "Body Battery huidig" : "Body Battery ontwaken"}
            v={(R.bodyBatteryAtWake ?? R.bodyBatteryCurrent ?? R.bodyBattery) == null ? 'Geen data' : `${R.bodyBatteryAtWake ?? R.bodyBatteryCurrent ?? R.bodyBattery}%`} />
          <ContextRow k="HRV overnight" v={R.hrvOvernight == null ? 'Geen data' : `${R.hrvOvernight}ms`} />
          <ContextRow k="Resting HR" v={R.restingHr == null ? 'Geen data' : `${R.restingHr} bpm`} />
          <ContextRow k="Stress" v={R.avgStress == null ? 'Geen data' : `${R.avgStress}/100`} />
          <ContextRow k="Recovery" v={`${recoveryScore}/6 · ${FCU.recoveryLabel(recoveryScore)}`} />
        </div>

        <div className="card tight">
          <div className="label" style={{ marginBottom: 10 }}>Recente activiteit</div>
          {recentActivity ? <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
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
          </div> : (
            <div style={{ fontSize: 13, color: 'var(--ink-4)', lineHeight: 1.45 }}>
              Nog geen recente live activiteit beschikbaar.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function TrainingProposalCard({ draftWorkout, setDraftWorkout, onNavigate, recoveryScore, trainingProfile, dataSource }) {
  const plan = draftWorkout || window.FC_WORKOUT_PLAN?.buildDraft({ recoveryScore, trainingProfile });
  if (!plan || !window.FC_WORKOUT_PLAN) return null;
  const totalSec = (plan.blocks || []).reduce((sum, block) => sum + block.sec, 0);
  const totalMin = Math.round(totalSec / 60) || plan.durationMin;
  const sportLabel = window.FC_WORKOUT_PLAN.sportLabel(plan.sportType);
  const typeLabel = window.FC_WORKOUT_PLAN.typeLabel(plan.type);
  const mainBlock = (plan.blocks || []).find((block) => block.zone !== 'Z1') || (plan.blocks || [])[0];
  const mainTarget = mainBlock ? window.FC_WORKOUT_PLAN.targetForBlock(mainBlock, plan.sportType) : null;
  const statusText = plan.status === 'approved' ? 'Goedgekeurd' : 'Concept';

  const commitDraftWorkout = (updater) => {
    if (setDraftWorkout) {
      setDraftWorkout(updater);
      return;
    }
    window.FC_SET_DRAFT_WORKOUT?.(updater);
  };

  const approve = () => {
    commitDraftWorkout((current) => window.FC_WORKOUT_PLAN.approveDraft(current || plan));
  };

  const quickAdjust = (text) => {
    commitDraftWorkout((current) => (
      window.FC_WORKOUT_PLAN.updateDraftFromText(current || plan, text, { recoveryScore, trainingProfile }).draft
    ));
  };

  return (
    <div className="card tight" style={{
      background: 'var(--ink)',
      color: 'var(--text-on-dark)',
      borderColor: 'transparent',
      position: 'sticky',
      top: 18,
      zIndex: 5,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', gap: 12 }}>
        <div>
          <div className="label" style={{ color: 'oklch(70% 0.01 100)', marginBottom: 8 }}>Trainingvoorstel</div>
          <h2 style={{ color: 'var(--text-on-dark)', lineHeight: 1.15 }}>{typeLabel}</h2>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 6 }}>
          <span className={plan.status === 'approved' ? 'tag accent' : 'tag'}
            style={plan.status === 'approved' ? undefined : { background: 'oklch(24% 0.005 100)', color: 'oklch(78% 0.01 100)' }}>
            {statusText}
          </span>
          <span className="mono" style={{ fontSize: 9, color: dataSource === 'stale-live' ? 'oklch(82% 0.12 75)' : 'oklch(66% 0.01 100)',
            textTransform: 'uppercase', letterSpacing: '.12em' }}>
            {dataSource === 'live' ? 'live data' : dataSource === 'stale-live' ? 'stale live' : dataSource === 'demo' ? 'demo' : 'geen live data'}
          </span>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8, marginTop: 16 }}>
        <ProposalMetric label="Sport" value={sportLabel} />
        <ProposalMetric label="Duur" value={`${totalMin}m`} />
        <ProposalMetric label="Intens." value={`${plan.intensityPct || 100}%`} />
      </div>

      <div style={{ marginTop: 16 }}>
        <div style={{ display: 'flex', gap: 3, height: 34 }}>
          {(plan.blocks || []).map((block, index) => (
            <div key={`${block.label}-${index}`}
              title={`${block.label} · ${Math.round(block.sec / 60)} min`}
              style={{
                flex: Math.max(0.02, block.sec / Math.max(1, totalSec)),
                background: block.color || 'var(--accent)',
                borderRadius: 3,
                opacity: block.zone === 'Z1' ? .65 : 1,
              }} />
          ))}
        </div>
        <div className="mono" style={{ marginTop: 8, fontSize: 10, color: 'oklch(74% 0.01 100)', lineHeight: 1.45 }}>
          {mainBlock
            ? `${mainBlock.label} · ${Math.round(mainBlock.sec / 60)} min · ${mainBlock.zone}${mainTarget ? ` · ${mainTarget}` : ''}`
            : 'Nog geen blokken'}
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6, marginTop: 14 }}>
        <button className="btn ghost" onClick={() => quickAdjust('korter')}
          style={{ color: 'var(--text-on-dark)', borderColor: 'oklch(35% 0.005 100)', justifyContent: 'center', padding: '8px 10px' }}>
          Korter
        </button>
        <button className="btn ghost" onClick={() => quickAdjust('rustiger')}
          style={{ color: 'var(--text-on-dark)', borderColor: 'oklch(35% 0.005 100)', justifyContent: 'center', padding: '8px 10px' }}>
          Rustiger
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginTop: 10 }}>
        <button className="btn accent" onClick={approve} style={{ justifyContent: 'center', padding: '11px 12px' }}>
          Goedkeuren
        </button>
        <button className="btn ghost" onClick={() => onNavigate?.('workout')}
          style={{ color: 'var(--text-on-dark)', borderColor: 'oklch(35% 0.005 100)', justifyContent: 'center', padding: '11px 12px' }}>
          Open plan
        </button>
      </div>

      <p style={{ margin: '12px 0 0', color: 'oklch(78% 0.01 100)', fontSize: 12, lineHeight: 1.45 }}>
        {plan.note || 'Vraag iets zoals “maak hem 45 min”, “op de fiets” of “rustiger”.'}
      </p>
    </div>
  );
}

function ProposalMetric({ label, value }) {
  return (
    <div style={{ background: 'oklch(18% 0.005 100)', borderRadius: 10, padding: '10px 8px', minWidth: 0 }}>
      <div className="mono" style={{ fontSize: 9, color: 'oklch(66% 0.01 100)', textTransform: 'uppercase', letterSpacing: '.12em' }}>
        {label}
      </div>
      <div style={{ marginTop: 5, fontSize: 14, fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {value}
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

function BigBubble({ m, onSend }) {
  const isUser = m.role === 'user';
  const analysis = m.analysis_result || m.analysis || null;
  return (
    <div style={{ display: 'flex', flexDirection: 'column',
                  alignItems: isUser ? 'flex-end' : 'flex-start', gap: 6,
                  maxWidth: analysis ? '100%' : '78%', alignSelf: isUser ? 'flex-end' : 'flex-start' }}>
      <div style={{
        background: isUser ? 'var(--ink)' : 'var(--bg-soft)',
        color: isUser ? 'var(--text-on-dark)' : 'var(--ink)',
        padding: '14px 18px',
        borderRadius: isUser ? '18px 18px 4px 18px' : '18px 18px 18px 4px',
        fontSize: 15, lineHeight: 1.55,
        maxWidth: analysis ? 680 : '100%',
      }} dangerouslySetInnerHTML={{ __html: isUser ? escapeHtml(m.content) : formatCoachContent(m.content) }} />
      {!isUser && analysis && <AnalysisCard result={analysis} onSend={onSend} />}
      <div className="mono" style={{ fontSize: 10, color: 'var(--ink-4)',
                                      letterSpacing: '.1em', textTransform: 'uppercase' }}>
        {isUser ? 'Jij' : 'Coach'} · {m.time}
      </div>
    </div>
  );
}

function AnalysisCard({ result, onSend }) {
  const chart = result.chart || null;
  const metrics = Array.isArray(result.metrics) ? result.metrics : [];
  const confidence = result.confidence || {};
  const coverage = result.coverage || {};
  const suggestions = Array.isArray(result.follow_up_suggestions) ? result.follow_up_suggestions.slice(0, 3) : [];
  const source = coverage.effective_data_source || result.context?.data_source || 'summary';
  const sourceLabel = analysisSourceLabel(source);
  return (
    <div className="card tight" style={{
      width: 'min(760px, 100%)',
      borderColor: 'var(--line)',
      background: 'var(--surface)',
      boxShadow: '0 14px 42px color-mix(in oklab, var(--ink) 7%, transparent)',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', gap: 14 }}>
        <div style={{ minWidth: 0 }}>
          <div className="label" style={{ marginBottom: 8 }}>Activiteitenanalyse</div>
          <h2 style={{ fontSize: 22, lineHeight: 1.1, marginBottom: 6 }}>{result.title || 'Analyse'}</h2>
          <p style={{ margin: 0, color: 'var(--ink-3)', lineHeight: 1.45, fontSize: 13 }}>
            {result.summary}
          </p>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 6, flexShrink: 0 }}>
          <span className="tag" style={{
            background: confidence.level === 'high' ? 'oklch(92% 0.16 145)' : confidence.level === 'medium' ? 'oklch(94% 0.10 95)' : 'var(--bg-soft)',
            color: 'var(--ink)',
          }}>
            {confidence.label || confidence.level || 'indicatief'}
          </span>
          <span className="mono" style={{ fontSize: 9, color: 'var(--ink-4)', textTransform: 'uppercase', letterSpacing: '.12em' }}>
            {sourceLabel}
          </span>
        </div>
      </div>

      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 14, alignItems: 'center' }}>
        <span className="mono" style={{ fontSize: 10, color: 'var(--ink-4)', textTransform: 'uppercase', letterSpacing: '.12em', marginRight: 4 }}>
          Databron
        </span>
        {[
          ['auto', 'Auto'],
          ['details', 'ActivityDetails'],
          ['summary', 'Summary'],
        ].map(([key, label]) => (
          <button key={key}
            type="button"
            onClick={() => onSend?.(key === 'details'
              ? 'toon dezelfde analyse met activityDetails'
              : key === 'summary'
                ? 'toon dezelfde analyse met summary'
                : 'toon dezelfde analyse met de beste bron')}
            className="tag"
            style={{
              border: '1px solid var(--line)',
              background: (result.context?.data_source || 'auto') === key ? 'var(--ink)' : 'transparent',
              color: (result.context?.data_source || 'auto') === key ? 'var(--text-on-dark)' : 'var(--ink)',
              cursor: 'pointer',
            }}>
            {label}
          </button>
        ))}
      </div>

      {metrics.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(112px, 1fr))', gap: 8, marginTop: 18 }}>
          {metrics.slice(0, 4).map((metric, index) => (
            <div key={`${metric.label}-${index}`} style={{ background: 'var(--bg-soft)', borderRadius: 8, padding: '11px 12px', minWidth: 0 }}>
              <div className="mono" style={{ fontSize: 9, color: 'var(--ink-4)', textTransform: 'uppercase', letterSpacing: '.12em' }}>
                {metric.label}
              </div>
              <div style={{ marginTop: 5, fontSize: 20, fontWeight: 650, lineHeight: 1 }}>
                {metric.value ?? '-'}{metric.unit ? <span style={{ fontSize: 12, color: 'var(--ink-3)', marginLeft: 4 }}>{metric.unit}</span> : null}
              </div>
              {metric.delta_percent != null && (
                <div className="mono" style={{ marginTop: 6, fontSize: 10, color: Number(metric.delta_percent) >= 0 ? 'var(--good)' : 'var(--bad)' }}>
                  {Number(metric.delta_percent) >= 0 ? '+' : ''}{metric.delta_percent}%
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {chart && (
        <div style={{ marginTop: 18, padding: 14, border: '1px solid var(--line)', borderRadius: 10, background: 'white' }}>
          <div className="mono" style={{ fontSize: 10, color: 'var(--ink-4)', textTransform: 'uppercase', letterSpacing: '.12em', marginBottom: 10 }}>
            {chart.title || 'Grafiek'}
          </div>
          <AnalysisChart chart={chart} />
        </div>
      )}

      {result.table && <AnalysisTable table={result.table} />}

      <div style={{ marginTop: 14, display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
        <div className="mono" style={{ fontSize: 10, color: 'var(--ink-4)', textTransform: 'uppercase', letterSpacing: '.12em' }}>
          {coverage.sessions ?? 0} sessies · {coverage.points ?? coverage.sessions ?? 0} punten · HR dekking {Math.round((coverage.hr_coverage || 0) * 100)}%
        </div>
        {suggestions.length > 0 && (
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {suggestions.map((suggestion) => (
              <button key={suggestion} onClick={() => onSend?.(suggestion)}
                className="tag"
                style={{ border: '1px solid var(--line)', background: 'transparent', cursor: 'pointer' }}>
                {suggestion}
              </button>
            ))}
          </div>
        )}
      </div>
      {Array.isArray(confidence.notes) && confidence.notes.length > 0 && (
        <p style={{ margin: '10px 0 0', color: 'var(--ink-4)', fontSize: 12, lineHeight: 1.4 }}>
          {confidence.notes[0]}
        </p>
      )}
    </div>
  );
}

function AnalysisChart({ chart }) {
  if (chart.type === 'dual_line') return <DualLineChart chart={chart} />;
  if (chart.type === 'scatter') return <ScatterChart chart={chart} />;
  if (chart.type === 'bar') return <BarChart chart={chart} />;
  return <LineChart chart={chart} />;
}

function DualLineChart({ chart }) {
  const series = (chart.series || []).filter((item) => Array.isArray(item.values));
  const primary = normaliseSeries(series[0]);
  const secondary = normaliseSeries(series[1]);
  const xValues = (chart.x || []).map(Number);
  if (!primary.values.length && !secondary.values.length) return <EmptyChart />;
  const w = 680;
  const h = 220;
  const padX = 34;
  const padY = 22;
  const xMin = Number.isFinite(Math.min(...xValues)) ? Math.min(...xValues) : 0;
  const xMax = Number.isFinite(Math.max(...xValues)) ? Math.max(...xValues) : Math.max(primary.values.length, secondary.values.length, 1);
  const xAt = (value, index) => {
    const x = Number.isFinite(value) ? value : index;
    return padX + ((x - xMin) / Math.max(1, xMax - xMin)) * (w - padX * 2);
  };
  const yAt = (value, meta) => {
    if (!Number.isFinite(value)) return h - padY;
    const ratio = (value - meta.min) / Math.max(1, meta.max - meta.min);
    const plotted = meta.invert ? ratio : 1 - ratio;
    return padY + plotted * (h - padY * 2);
  };
  const pathFor = (meta) => meta.values
    .map((value, index) => {
      if (!Number.isFinite(value)) return null;
      return `${index ? 'L' : 'M'}${xAt(xValues[index], index)},${yAt(value, meta)}`;
    })
    .filter(Boolean)
    .join(' ');
  const primaryPath = pathFor(primary);
  const secondaryPath = pathFor(secondary);
  const blocks = Array.isArray(chart.blocks) ? chart.blocks : [];
  return (
    <div>
      <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 8, flexWrap: 'wrap' }}>
        <LegendPill color="var(--accent)" label={`${primary.label || 'Hartslag'} (${primary.unit || ''})`} />
        <LegendPill color="oklch(58% 0.10 220)" label={`${secondary.label || 'Tempo'} (${secondary.unit || ''})`} />
      </div>
      <svg viewBox={`0 0 ${w} ${h}`} style={{ width: '100%', height: 220, display: 'block' }} role="img" aria-label={chart.title || 'dubbele lijn grafiek'}>
        <line x1={padX} y1={h - padY} x2={w - padX} y2={h - padY} stroke="var(--line-strong)" />
        <line x1={padX} y1={padY} x2={padX} y2={h - padY} stroke="var(--line-strong)" />
        {blocks.map((block, index) => {
          const x = xAt(Number(block.start), 0);
          const width = Math.max(2, xAt(Number(block.end), 0) - x);
          const fill = block.kind === 'work' ? 'oklch(87% 0.15 80)' : block.kind === 'recovery' ? 'oklch(90% 0.06 220)' : 'oklch(94% 0.01 100)';
          return (
            <g key={`${block.label}-${index}`}>
              <rect x={x} y={padY} width={width} height={h - padY * 2} fill={fill} opacity="0.34">
                <title>{`${block.label || `Blok ${index + 1}`} · ${block.start}-${block.end} min`}</title>
              </rect>
              {width > 28 && (
                <text x={x + width / 2} y={h - 6} textAnchor="middle"
                  style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 9, fill: 'var(--ink-4)' }}>
                  {block.label?.replace('Blok ', 'B') || `B${index + 1}`}
                </text>
              )}
            </g>
          );
        })}
        {secondaryPath && <path d={secondaryPath} fill="none" stroke="oklch(58% 0.10 220)" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" opacity="0.9" />}
        {primaryPath && <path d={primaryPath} fill="none" stroke="var(--accent)" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" />}
        {primary.values.map((value, index) => {
          if (!Number.isFinite(value)) return null;
          if (index % Math.max(1, Math.ceil(primary.values.length / 18)) !== 0 && index !== primary.values.length - 1) return null;
          const x = xAt(xValues[index], index);
          const y = yAt(value, primary);
          const secondaryValue = secondary.values[index];
          return (
            <g key={`p-${index}`}>
              <circle cx={x} cy={y} r="3.5" fill="var(--ink)" stroke="var(--accent)" strokeWidth="2">
                <title>{`${xValues[index] ?? index} min · ${primary.label}: ${formatChartValue(value, primary.unit)}${Number.isFinite(secondaryValue) ? ` · ${secondary.label}: ${formatChartValue(secondaryValue, secondary.unit)}` : ''}`}</title>
              </circle>
              {(index === 0 || index === primary.values.length - 1) && (
                <text x={x} y={Math.max(12, y - 10)} textAnchor="middle"
                  style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 10, fill: 'var(--ink-3)' }}>
                  {formatChartValue(value, primary.unit)}
                </text>
              )}
            </g>
          );
        })}
      </svg>
      <ChartLegend labels={[`${xMin} min`, `${Math.round((xMin + xMax) / 2)} min`, `${xMax} min`]} />
    </div>
  );
}

function normaliseSeries(series) {
  const values = ((series && series.values) || [])
    .map((value) => value == null ? NaN : Number(value))
    .map((value) => Number.isFinite(value) ? value : NaN);
  const finite = values.filter((value) => Number.isFinite(value));
  const min = finite.length ? Math.min(...finite) : 0;
  const max = finite.length ? Math.max(...finite) : 1;
  return {
    label: series?.label || '',
    unit: series?.unit || '',
    invert: Boolean(series?.invert),
    values,
    min,
    max: max === min ? max + 1 : max,
  };
}

function LegendPill({ color, label }) {
  return (
    <span className="mono" style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 10, color: 'var(--ink-4)', textTransform: 'uppercase', letterSpacing: '.1em' }}>
      <span style={{ width: 20, height: 3, borderRadius: 999, background: color, display: 'inline-block' }}></span>
      {label}
    </span>
  );
}

function LineChart({ chart }) {
  const series = (chart.series || []).filter((item) => Array.isArray(item.values));
  const primary = series[0] || { values: [] };
  const values = primary.values.map(Number).filter((value) => Number.isFinite(value));
  if (!values.length) return <EmptyChart />;
  const min = Math.min(0, ...values);
  const max = Math.max(...values, min + 1);
  const w = 640;
  const h = 180;
  const pad = 18;
  const points = values.map((value, index) => {
    const x = pad + (index / Math.max(1, values.length - 1)) * (w - pad * 2);
    const y = h - pad - ((value - min) / Math.max(1, max - min)) * (h - pad * 2);
    return [x, y];
  });
  const path = points.map((point, index) => `${index ? 'L' : 'M'}${point[0]},${point[1]}`).join(' ');
  const unit = primary.unit || '';
  const labels = chart.x || [];
  return (
    <div>
      <svg viewBox={`0 0 ${w} ${h}`} style={{ width: '100%', height: 180, display: 'block' }} role="img" aria-label={chart.title || 'lijn grafiek'}>
        <line x1={pad} y1={h - pad} x2={w - pad} y2={h - pad} stroke="var(--line-strong)" />
        <path d={path} fill="none" stroke="var(--accent)" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" />
        {points.map((point, index) => (
          <g key={index}>
            <circle cx={point[0]} cy={point[1]} r="4" fill="var(--ink)" stroke="var(--accent)" strokeWidth="2">
              <title>{`${labels[index] || `Punt ${index + 1}`}: ${formatChartValue(values[index], unit)}`}</title>
            </circle>
            {values.length <= 14 && (
              <text x={point[0]} y={Math.max(10, point[1] - 10)} textAnchor="middle"
                style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 10, fill: 'var(--ink-3)' }}>
                {formatChartValue(values[index], unit)}
              </text>
            )}
          </g>
        ))}
      </svg>
      <ChartLegend labels={chart.x || []} />
    </div>
  );
}

function BarChart({ chart }) {
  const series = (chart.series || []).filter((item) => Array.isArray(item.values));
  const primary = series[0] || { values: [] };
  const values = primary.values.map(Number).filter((value) => Number.isFinite(value));
  if (!values.length) return <EmptyChart />;
  const max = Math.max(...values, 1);
  const unit = primary.unit || '';
  const labels = chart.x || [];
  return (
    <div>
      <div style={{ height: 180, display: 'grid', gridTemplateColumns: `repeat(${values.length}, minmax(28px, 1fr))`, gap: 8, alignItems: 'end' }}>
        {values.map((value, index) => (
          <div key={index}
            title={`${labels[index] || `Balk ${index + 1}`}: ${formatChartValue(value, unit)}`}
            style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'end', gap: 6, minWidth: 0 }}>
            <div className="mono" style={{ fontSize: 10, color: 'var(--ink-3)' }}>{formatChartValue(value, unit)}</div>
            <div style={{
              width: '100%',
              height: `${Math.max(7, (value / max) * 138)}px`,
              background: index % 2 ? 'color-mix(in oklab, var(--accent) 64%, var(--ink))' : 'var(--accent)',
              borderRadius: '5px 5px 2px 2px',
            }} />
          </div>
        ))}
      </div>
      <ChartLegend labels={chart.x || []} />
    </div>
  );
}

function ScatterChart({ chart }) {
  const points = (chart.points || [])
    .map((point) => ({ ...point, x: Number(point.x), y: Number(point.y) }))
    .filter((point) => Number.isFinite(point.x) && Number.isFinite(point.y));
  if (!points.length) return <EmptyChart />;
  const w = 640;
  const h = 190;
  const pad = 24;
  const xs = points.map((point) => point.x);
  const ys = points.map((point) => point.y);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  return (
    <svg viewBox={`0 0 ${w} ${h}`} style={{ width: '100%', height: 190, display: 'block' }} role="img" aria-label={chart.title || 'scatter grafiek'}>
      <line x1={pad} y1={h - pad} x2={w - pad} y2={h - pad} stroke="var(--line-strong)" />
      <line x1={pad} y1={pad} x2={pad} y2={h - pad} stroke="var(--line-strong)" />
      {points.map((point, index) => {
        const x = pad + ((point.x - minX) / Math.max(1, maxX - minX)) * (w - pad * 2);
        const y = h - pad - ((point.y - minY) / Math.max(1, maxY - minY)) * (h - pad * 2);
        return (
          <g key={index}>
            <circle cx={x} cy={y} r="5" fill="var(--accent)" stroke="var(--ink)" strokeWidth="1.5">
              <title>{`${point.label || `Punt ${index + 1}`} · ${chart.xLabel || 'x'} ${point.x} · ${chart.yLabel || 'y'} ${point.y}${point.distance_km ? ` · ${point.distance_km} km` : ''}${point.duration_min ? ` · ${point.duration_min} min` : ''}`}</title>
            </circle>
            {points.length <= 12 && (
              <text x={x} y={Math.max(10, y - 10)} textAnchor="middle"
                style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 10, fill: 'var(--ink-3)' }}>
                {point.y}
              </text>
            )}
          </g>
        );
      })}
    </svg>
  );
}

function formatChartValue(value, unit) {
  if (!Number.isFinite(Number(value))) return '-';
  const rounded = Number(value) % 1 === 0 ? String(Number(value)) : Number(value).toFixed(1);
  return unit ? `${rounded}${unit === 'u' || unit === 'km' ? unit : ` ${unit}`}` : rounded;
}

function analysisSourceLabel(source) {
  if (source === 'activityDetails') return 'ActivityDetails';
  if (source === 'activityFiles') return 'ActivityFiles FIT';
  if (source === 'mixed') return 'ActivityDetails + summary';
  if (source === 'details') return 'ActivityDetails';
  if (source === 'auto') return 'Auto';
  return 'Summary';
}

function ChartLegend({ labels }) {
  const shown = (labels || []).filter(Boolean);
  if (!shown.length) return null;
  const picks = shown.length > 6 ? [shown[0], shown[Math.floor(shown.length / 2)], shown[shown.length - 1]] : shown;
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, marginTop: 8 }}>
      {picks.map((label, index) => (
        <span key={`${label}-${index}`} className="mono" style={{ fontSize: 10, color: 'var(--ink-4)', textTransform: 'uppercase', letterSpacing: '.08em', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {label}
        </span>
      ))}
    </div>
  );
}

function EmptyChart() {
  return (
    <div style={{ height: 150, borderRadius: 10, background: 'var(--bg-soft)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--ink-4)', fontSize: 13 }}>
      Te weinig data voor een grafiek.
    </div>
  );
}

function AnalysisTable({ table }) {
  const columns = Array.isArray(table.columns) ? table.columns : [];
  const rows = Array.isArray(table.rows) ? table.rows : [];
  if (!columns.length || !rows.length) return null;
  return (
    <div style={{ marginTop: 16, overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column} className="mono" style={{ textAlign: 'left', color: 'var(--ink-4)', textTransform: 'uppercase', letterSpacing: '.1em', fontSize: 9, padding: '0 10px 8px 0', borderBottom: '1px solid var(--line)' }}>
                {column}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.slice(0, 8).map((row, rowIndex) => (
            <tr key={rowIndex}>
              {(Array.isArray(row) ? row : []).map((cell, cellIndex) => (
                <td key={cellIndex} style={{ padding: '8px 10px 8px 0', borderBottom: '1px solid var(--line)', color: cellIndex === 2 ? 'var(--ink-4)' : 'var(--ink)' }}>
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function formatCoachContent(content) {
  const raw = String(content || '');
  if (!raw.trim()) return '';
  if (/<\/?[a-z][\s\S]*>/i.test(raw)) {
    return sanitiseCoachHtml(raw)
      .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
      .replace(/(^|[\s(])\*([^*\n]+)\*/g, '$1<em>$2</em>');
  }
  return markdownToHtml(raw);
}

function sanitiseCoachHtml(raw) {
  return String(raw || '')
    .replace(/<script[\s\S]*?>[\s\S]*?<\/script>/gi, '')
    .replace(/<style[\s\S]*?>[\s\S]*?<\/style>/gi, '')
    .replace(/\son\w+=(["']).*?\1/gi, '')
    .replace(/\shref=(["'])javascript:.*?\1/gi, '')
    .replace(/\n{2,}/g, '<br/><br/>')
    .replace(/\n/g, '<br/>');
}

function markdownToHtml(raw) {
  const lines = escapeHtml(raw.trim()).split(/\n/);
  const html = [];
  let listType = null;
  const closeList = () => {
    if (listType) {
      html.push(`</${listType}>`);
      listType = null;
    }
  };
  lines.forEach((line) => {
    const trimmed = line.trim();
    if (!trimmed) {
      closeList();
      html.push('<br/>');
      return;
    }
    const bullet = trimmed.match(/^[-*]\s+(.+)$/);
    const numbered = trimmed.match(/^\d+[.)]\s+(.+)$/);
    if (bullet || numbered) {
      const nextType = bullet ? 'ul' : 'ol';
      if (listType !== nextType) {
        closeList();
        html.push(`<${nextType}>`);
        listType = nextType;
      }
      html.push(`<li>${inlineMarkdown(bullet ? bullet[1] : numbered[1])}</li>`);
      return;
    }
    closeList();
    html.push(`<p>${inlineMarkdown(trimmed)}</p>`);
  });
  closeList();
  return html.join('');
}

function inlineMarkdown(text) {
  return String(text || '')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/__([^_]+)__/g, '<strong>$1</strong>')
    .replace(/(^|[\s(])\*([^*\n]+)\*/g, '$1<em>$2</em>')
    .replace(/(^|[\s(])_([^_\n]+)_/g, '$1<em>$2</em>');
}

function escapeHtml(value) {
  return String(value || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function ThinkDot({ d }) {
  return <span style={{
    width: 7, height: 7, borderRadius: 999, background: 'var(--ink-4)',
    display: 'inline-block', animation: `thinking-pulse 1s cubic-bezier(.16,1,.3,1) ${d}s infinite`,
  }}></span>;
}

function mockReplyChat(text, score, recoveryData) {
  const t = text.toLowerCase();
  const R = recoveryData || window.FC_DATA.recovery;
  if (t.includes('slaap')) {
    const batteryLabel = R.bodyBatteryAtWake == null ? 'huidig' : 'bij ontwaken';
    const battery = R.bodyBatteryAtWake ?? R.bodyBatteryCurrent ?? R.bodyBattery ?? '–';
    return `Je slaap staat op <b>${R.sleepHours ? `${R.sleepHours.toFixed(1)} uur` : 'geen data'}</b> met sleep score <b>${R.sleepScore ?? 'geen data'}</b>. Diepe slaap ${R.deepSleepMin ?? '–'} min, REM ${R.remMin ?? '–'} min, awake ${R.awakeMin ?? '–'} min. Body Battery ${batteryLabel} staat op ${battery}${battery === '–' ? '' : '%'}<br/><br/>Dat is de meest recente Garmin-data die ik lokaal heb.`;
  }
  if (t.includes('herstel') || t.includes('recovery') || t.includes('herstel check')) return `<b>Herstelscore ${score}/6 - ${FCU.recoveryLabel(score)}</b><br/><br/>${FCU.recoveryAdvice(score)} HRV staat op <b>${R.hrvOvernight ?? '–'}ms</b>. Resting HR <b>${R.restingHr ?? '–'} bpm</b>.`;
  if (t.includes('duur')) return `Klaargezet. <b>75 min duurloop</b>, zone 2 (HR 138-152). Warming-up 8 min, duurblok 60 min, cooling-down 7 min. <i>FIT-bestand staat in Garmin Connect.</i><br/><br/>Wil je dat ik er ook een drinkmoment inplan?`;
  if (t.includes('interval') || t.includes('tempo') || t.includes('drempel')) return `<b>2× 12 min tempo</b> met 4 min herstel tussendoor.<br/><br/>WU 12 min easy · 12 min @ drempel (162-168) · 4 min easy · 12 min @ drempel · CD 8 min<br/><br/>Wil je dit nu starten?`;
  if (t.includes('analyseer') || t.includes('trainingsweek') || t.includes('week') || t.includes('activiteit')) return `<b>Deze week:</b><br/>· 3 sessies · 31 km · 3u 06min<br/>· Volume <span style="color:var(--bad)">29% onder</span> 4-weken gemiddelde<br/>· Intensiteit op peil (1× drempel woensdag)<br/><br/>Voeg dit weekend een duurloop van 75-90 min toe om je weekvolume in balans te brengen.`;
  if (t.includes('vergelijk')) return `Tussen je <b>Tempo 4×5 min</b> (6/5) en <b>Intervaltraining 6×800m</b> (11/5):<br/>· Avg HR daalde van 158 → 163 bpm (zelfde inspanning, +5 bpm hoger door snellere tempo)<br/>· Pace was 8% sneller deze week<br/>· Beide sessies aan boven-drempel`;
  if (t.includes('wedstrijd') || t.includes('plan')) return `Welke wedstrijd plan je? Geef datum en afstand, dan zet ik een meerwekenplan op met intensiteits- en taperfases. Bv. <i>"10 km op 14 juni"</i>.`;
  if (t.includes('genereer workout')) return `Welke training wil je? Kies type en duur, of laat het aan mij over op basis van je <b>recovery ${score}/6</b>. Voorbeelden: <i>"45 min tempo"</i>, <i>"makkelijke duurloop 60 min"</i>.`;
  return `Begrepen. Op basis van je <b>recovery ${score}/6</b> raad ik vandaag een ${FCU.recoveryAdvice(score).toLowerCase()}<br/><br/>Wil je dat ik een concrete sessie klaarzet?`;
}

window.ChatScreen = ChatScreen;
