// Home page — News Oh,Ye!
const { useState: useStateH, useEffect: useEffectH, useMemo: useMemoH } = React;

// Convert articleProgress entry → 0..100 percentage. Handles two shapes:
//   · legacy: <number> from before commit 8f28c21 (still in some readers'
//     localStorage; will fade out as their dayKey rollover replaces it)
//   · new:    { steps: string[], lastTab: string } — 4 steps total, each
//     step = 25%, so steps.length × 25 maps cleanly to the old percent UI
function _articlePct(ap) {
  if (!ap) return 0;
  if (typeof ap === 'number') return ap;
  const steps = (ap && ap.steps) || [];
  return Math.min(100, steps.length * 25);
}

// ────────────────────────────────────────────────────────────────────
// Onboarding — first-launch setup screen (≤ 2 min)
// ────────────────────────────────────────────────────────────────────
// Triggered when tweaks.userName is empty. Asks for name + avatar +
// level + theme. After save, the standard pick-3 flow takes over.
// AVATARS, LEVEL_OPTIONS, THEMES, LANGS come from user-panel.jsx
// (Babel-standalone hoists them to script scope).

// Section helper — defined OUTSIDE OnboardingScreen so that React doesn't
// unmount/remount it on every parent re-render (which would steal focus
// from the name input on every keystroke).
function _OnbSection({ label, sub, children }) {
  return (
    <div style={{marginBottom: 22}}>
      <div style={{
        fontFamily:'Nunito, sans-serif', fontWeight:900, fontSize:13,
        color:'#1b1230', letterSpacing:'.04em', textTransform:'uppercase',
        marginBottom: 4,
      }}>{label}</div>
      {sub && <div style={{fontSize:12.5, color:'#6b5c80', marginBottom: 10}}>{sub}</div>}
      {children}
    </div>
  );
}

function OnboardingScreen({ tweaks, updateTweak, level, setLevel, theme, onDone }) {
  const cfg = window.SITE_CONFIG || {};
  const [name, setName] = useStateH(tweaks?.userName || '');
  const [avatarId, setAvatarId] = useStateH(tweaks?.avatar || 'fox');
  const [pickedLevel, setPickedLevel] = useStateH(level || 'Sprout');
  const [themeId, setThemeId] = useStateH(tweaks?.theme || 'sunny');
  const [lang, setLang] = useStateH(tweaks?.language || 'en');

  const ready = name.trim().length > 0;

  const save = () => {
    if (!ready) return;
    updateTweak('userName', name.trim());
    updateTweak('avatar', avatarId);
    updateTweak('theme', themeId);
    updateTweak('language', lang);
    setLevel(pickedLevel);
    onDone && onDone();
  };

  return (
    <div style={{minHeight:'100vh', background: theme.bg, fontFamily:'Nunito, sans-serif'}}>
      {/* Header */}
      <div style={{padding:'14px 28px', borderBottom:`2px solid ${theme.chip}`}}>
        <div style={{maxWidth:1180, margin:'0 auto'}}>
          <KidsNewsLockup size={100}/>
        </div>
      </div>

      {/* Hero */}
      <div style={{
        background:`linear-gradient(135deg, ${theme.hero1} 0%, ${theme.hero2} 100%)`,
        padding:'32px 28px 28px', borderBottom:`2px solid ${theme.border}`,
      }}>
        <div style={{maxWidth:760, margin:'0 auto', textAlign:'center'}}>
          <div style={{
            fontSize:12, fontWeight:800, letterSpacing:'.12em',
            textTransform:'uppercase', color: theme.heroTextAccent, marginBottom:8,
          }}>
            Welcome — about 2 minutes
          </div>
          <h1 style={{
            fontFamily:'Fraunces, serif', fontWeight:900, fontSize:42, lineHeight:1.05,
            color:'#1b1230', margin:'0 0 6px', letterSpacing:'-0.025em',
          }}>
            Let's set up your <span style={{
              background: theme.accent, padding:'0 12px', borderRadius:12,
              display:'inline-block', transform:'rotate(-1.5deg)',
            }}>21 minutes</span>
          </h1>
          <div style={{
            fontFamily:'Fraunces, serif', fontStyle:'italic', fontWeight:600,
            fontSize:19, color:'#c14e2a', marginTop:8,
          }}>
            {cfg.tagline || 'Little daily, big magic.'}
          </div>
        </div>
      </div>

      {/* Form */}
      <div style={{maxWidth:720, margin:'0 auto', padding:'28px'}}>

        <_OnbSection label="What's your name?" sub="So we can say hi every morning.">
          <input
            type="text" value={name} onChange={e => setName(e.target.value)}
            placeholder="Your first name"
            maxLength={28}
            style={{
              width:'100%', fontSize:17, padding:'14px 16px', border:'2px solid #e8dfd3',
              borderRadius:14, background:'#fff', fontFamily:'Nunito, sans-serif',
              color:'#1b1230', outline:'none',
            }}/>
        </_OnbSection>

        <_OnbSection label="Pick an avatar" sub="Tap one — you can change it later.">
          <div style={{display:'grid', gridTemplateColumns:'repeat(6, 1fr)', gap: 8}}>
            {AVATARS.map(a => (
              <button key={a.id} onClick={()=>setAvatarId(a.id)} style={{
                aspectRatio:'1', background: avatarId === a.id ? a.bg : '#fff',
                border: avatarId === a.id ? `3px solid #1b1230` : `2px solid #f0e8d8`,
                borderRadius: 14, fontSize: 26, cursor:'pointer',
                display:'flex', alignItems:'center', justifyContent:'center',
                boxShadow: avatarId === a.id ? '0 3px 0 rgba(27,18,48,0.18)' : 'none',
                transform: avatarId === a.id ? 'translateY(-2px)' : 'none',
                transition:'all .12s',
              }} title={a.id}>{a.emoji}</button>
            ))}
          </div>
        </_OnbSection>

        <_OnbSection label="Reading level">
          <div style={{display:'grid', gridTemplateColumns:'1fr 1fr', gap:10}}>
            {LEVEL_OPTIONS.map(l => (
              <button key={l.id} onClick={()=>setPickedLevel(l.id)} style={{
                background: pickedLevel === l.id ? '#1b1230' : '#fff',
                color: pickedLevel === l.id ? '#fff' : '#1b1230',
                border: pickedLevel === l.id ? '3px solid #1b1230' : '2px solid #f0e8d8',
                borderRadius: 14, padding: '14px 16px', cursor: 'pointer',
                fontFamily: 'Nunito, sans-serif', textAlign:'left',
                boxShadow: pickedLevel === l.id ? '0 3px 0 rgba(27,18,48,0.18)' : 'none',
                transform: pickedLevel === l.id ? 'translateY(-2px)' : 'none',
                transition: 'all .12s',
              }}>
                <div style={{fontSize: 22, marginBottom: 4}}>{l.emoji} {l.id}</div>
                <div style={{fontSize: 12, fontWeight:600, opacity:0.85}}>{l.sub}</div>
              </button>
            ))}
          </div>
        </_OnbSection>

        <_OnbSection label="Color theme">
          <div style={{display:'grid', gridTemplateColumns:'repeat(4, 1fr)', gap: 8}}>
            {THEMES.map(t => (
              <button key={t.id} onClick={()=>setThemeId(t.id)} style={{
                background:`linear-gradient(135deg, ${t.sw1}, ${t.sw2})`,
                border: themeId === t.id ? '3px solid #1b1230' : '2px solid #f0e8d8',
                borderRadius: 14, padding: '14px 12px', cursor:'pointer',
                fontFamily: 'Nunito, sans-serif',
                boxShadow: themeId === t.id ? '0 3px 0 rgba(27,18,48,0.18)' : 'none',
                transform: themeId === t.id ? 'translateY(-2px)' : 'none',
                transition: 'all .12s',
              }}>
                <div style={{fontSize: 22, marginBottom: 4}}>{t.emoji}</div>
                <div style={{fontSize: 11, fontWeight: 800, color: '#1b1230'}}>{t.label}</div>
              </button>
            ))}
          </div>
        </_OnbSection>

        <_OnbSection label="Language">
          <div style={{display:'grid', gridTemplateColumns:'1fr 1fr', gap:10}}>
            {LANGS.map(l => (
              <button key={l.id} onClick={()=>setLang(l.id)} style={{
                background: lang === l.id ? '#1b1230' : '#fff',
                color: lang === l.id ? '#fff' : '#1b1230',
                border: lang === l.id ? '3px solid #1b1230' : '2px solid #f0e8d8',
                borderRadius: 14, padding: '12px 16px', cursor:'pointer',
                fontFamily:'Nunito, sans-serif', textAlign:'left',
                boxShadow: lang === l.id ? '0 3px 0 rgba(27,18,48,0.18)' : 'none',
                transition: 'all .12s',
              }}>
                <span style={{fontSize:18, marginRight:8}}>{l.flag}</span>
                <span style={{fontWeight:800}}>{l.label}</span>
              </button>
            ))}
          </div>
        </_OnbSection>

        {/* Phase-3 placeholder: parent sync */}
        <div style={{
          margin:'8px 0 24px', padding:'12px 16px', borderRadius:12,
          background:'#fffaf0', border:'1.5px dashed #e8dfd3',
          fontSize:12.5, color:'#6b5c80', textAlign:'center',
        }}>
          🛡️ <b>Parent?</b> Cross-device sync via Google sign-in is coming soon.
          For now your progress lives on this device only.
        </div>

        {/* CTA */}
        <button
          onClick={save} disabled={!ready}
          style={{
            width:'100%', background: ready ? '#1b1230' : '#e8dfd3',
            color: ready ? '#fff' : '#9a8d7a',
            border:'none', borderRadius:16, padding:'16px',
            fontFamily:'Nunito, sans-serif', fontWeight:900, fontSize:17,
            cursor: ready ? 'pointer' : 'not-allowed',
            boxShadow: ready ? '0 5px 0 rgba(27,18,48,0.18)' : 'none',
            transition:'all .12s',
          }}>
          {ready ? '▶ Save & start picking today\'s 3' : 'Type your name to continue'}
        </button>
      </div>
    </div>
  );
}

// ────────────────────────────────────────────────────────────────────
// Pick-3 daily ritual flow — three sequential category screens
// ────────────────────────────────────────────────────────────────────
// First-load-of-the-day surface. Kid sees one category at a time
// (News → Science → Fun) with the editorial 1-big-2-small layout.
// Tap a card to choose, tap a different card to swap. Click "Next →"
// to advance. On the last screen, "▶ Start your 21 minutes" locks all
// three picks for the day.
//
// This frames the experience as a deliberate ritual instead of a
// passive feed — defending against scroll-mode habits.

// Truncate a summary to ≤ N words so the pick screen stays scannable.
// Pipeline-side enforcement is a future tightening.
function _shortHook(s, max = 50) {
  if (!s) return '';
  const words = s.trim().split(/\s+/);
  if (words.length <= max) return s.trim();
  return words.slice(0, max).join(' ') + '…';
}

// One pick card. `variant` controls layout:
//   · 'feature' — large hero card with image left + content right
//   · 'normal'  — compact card stacked image-on-top
function PickCard({ story, picked, variant, onSelect }) {
  const c = CATEGORIES.find(x => x.label === story.category) || CATEGORIES[0];
  const baseStyle = {
    position:'relative', textAlign:'left', cursor:'pointer',
    background: picked ? c.bg : '#fff',
    border: picked ? `3px solid ${c.color}` : `2px solid #f0e8d8`,
    borderRadius:18, padding:0, overflow:'hidden',
    boxShadow: picked ? `0 4px 0 ${c.color}` : '0 2px 0 rgba(27,18,48,0.06)',
    transform: picked ? 'translateY(-2px)' : 'none',
    transition:'transform .15s, box-shadow .15s, background .15s',
    fontFamily:'Nunito, sans-serif',
    width:'100%',
  };
  const checkBadge = picked ? (
    <div style={{
      position:'absolute', top:12, right:12, zIndex:2,
      width:34, height:34, borderRadius:999, background:c.color, color:'#fff',
      display:'flex', alignItems:'center', justifyContent:'center',
      fontFamily:'Fraunces, serif', fontWeight:900, fontSize:18,
      boxShadow:'0 2px 0 rgba(27,18,48,0.2)',
    }}>✓</div>
  ) : null;
  const catChip = (
    <div style={{
      display:'inline-flex', alignItems:'center', gap:5,
      background: picked ? '#fff' : c.bg, color:c.color,
      padding:'3px 10px', borderRadius:999, fontWeight:800,
      fontSize: variant === 'feature' ? 12 : 11,
      marginBottom: variant === 'feature' ? 10 : 8,
    }}>
      <span style={{fontSize: variant === 'feature' ? 14 : 13}}>{c.emoji}</span>
      {story.category} · {story.readMins} min
    </div>
  );

  if (variant === 'feature') {
    return (
      <button onClick={onSelect} style={baseStyle}>
        {checkBadge}
        <div style={{
          display:'grid', gridTemplateColumns:'minmax(240px, 1.1fr) 1.4fr',
          gap:0,
        }}>
          <div style={{
            aspectRatio:'4/3', minHeight:220,
            background: story.image
              ? `url(${story.image}) center/cover, ${c.color}`
              : c.color,
          }}/>
          <div style={{padding:'22px 26px 24px', display:'flex', flexDirection:'column', justifyContent:'center'}}>
            {catChip}
            <div style={{
              fontFamily:'Fraunces, serif', fontWeight:800, fontSize:24,
              lineHeight:1.15, color:'#1b1230', letterSpacing:'-0.015em',
              marginBottom:10,
            }}>{story.title}</div>
            <div style={{
              fontSize:14, color:'#3a2a4a', lineHeight:1.5, fontWeight:500,
            }}>{_shortHook(story.summary, 50)}</div>
          </div>
        </div>
      </button>
    );
  }

  return (
    <button onClick={onSelect} style={baseStyle}>
      {checkBadge}
      <div style={{
        aspectRatio:'16/10',
        background: story.image
          ? `url(${story.image}) center/cover, ${c.color}`
          : c.color,
      }}/>
      <div style={{padding:'14px 16px 16px'}}>
        {catChip}
        <div style={{
          fontFamily:'Fraunces, serif', fontWeight:700, fontSize:16,
          lineHeight:1.22, color:'#1b1230', letterSpacing:'-0.01em',
          marginBottom:6,
        }}>{story.title}</div>
        <div style={{
          fontSize:12.5, color:'#5a4a6e', lineHeight:1.5, fontWeight:600,
        }}>{_shortHook(story.summary, 30)}</div>
      </div>
    </button>
  );
}

function PickFlow({ pool, onLock, theme, tweaks, dateLabel }) {
  const cfg = window.SITE_CONFIG || {};
  const dailyGoal = cfg.dailyGoalMinutes ?? 21;

  // Group the pool into one bucket per category, in CATEGORIES order.
  const groups = useMemoH(() => CATEGORIES.map(c => ({
    cat: c,
    candidates: pool.filter(a => a.category === c.label).slice(0, 3),
  })).filter(g => g.candidates.length > 0), [pool]);

  const [step, setStep] = useStateH(0);
  const [selections, setSelections] = useStateH({});  // { 'News': storyId, ... }

  // If the pool changes (level/lang switch) and previously-current step
  // has no candidates, snap back to step 0.
  useEffectH(() => {
    if (step >= groups.length) setStep(Math.max(0, groups.length - 1));
  }, [groups.length, step]);

  if (groups.length === 0) {
    return (
      <div style={{minHeight:'100vh', background:theme.bg, padding:'80px 20px', textAlign:'center'}}>
        <div style={{fontSize:48, marginBottom:12}}>🌱</div>
        <div style={{fontFamily:'Fraunces, serif', fontWeight:800, fontSize:24, color:'#1b1230', marginBottom:8}}>
          No stories available yet
        </div>
        <div style={{color:'#6b5c80'}}>Tomorrow's batch arrives daily.</div>
      </div>
    );
  }

  const cur = groups[step];
  const selectedId = selections[cur.cat.label];
  const ready = !!selectedId;
  const isLast = step === groups.length - 1;
  const allReady = groups.every(g => selections[g.cat.label]);

  // Tap a card → save the selection AND auto-advance to the next
  // category screen. On the last screen this transitions to the
  // "complete" preview state (showCompleteFor) instead of locking
  // immediately — the kid still gets to see all 3 picks before
  // committing. To change a previous pick, tap a tracker pill.
  const [showComplete, setShowComplete] = useStateH(false);
  const select = (id) => {
    setSelections(prev => {
      const nextSel = { ...prev, [cur.cat.label]: id };
      if (isLast) {
        // Last category — show the complete-status screen.
        // Use a microtask so React renders the "selected" state first,
        // giving a brief visual confirmation before transition.
        setTimeout(() => setShowComplete(true), 280);
      } else {
        setTimeout(() => setStep(step + 1), 280);
      }
      return nextSel;
    });
  };
  const next = () => {
    if (isLast) setShowComplete(true);
    else setStep(step + 1);
  };
  const back = () => {
    if (showComplete) { setShowComplete(false); return; }
    if (step > 0) setStep(step - 1);
  };
  const lockNow = () => {
    const ids = CATEGORIES.map(c => selections[c.label]).filter(Boolean);
    onLock(ids);
  };

  // Big feature = first candidate by current order; small two = the rest.
  // (Ordering already follows source priority + last-used rotation upstream.)
  const [featureCandidate, ...smallCandidates] = cur.candidates;

  // ── Complete-status screen (after the 3rd pick auto-fires) ─────────
  // Shows all three picked stories side-by-side with a confirmation CTA.
  // Kid can change their mind via tracker pills or "Change my picks".
  if (showComplete) {
    const finalIds = CATEGORIES.map(c => selections[c.label]).filter(Boolean);
    const finals = finalIds.map(id => pool.find(p => p.id === id)).filter(Boolean);
    const totalMins = finals.reduce((m, s) => m + (s.readMins || 0), 0);
    return (
      <div style={{minHeight:'100vh', background: theme.bg, fontFamily:'Nunito, sans-serif'}}>
        <div style={{padding:'14px 28px', borderBottom:`2px solid ${theme.chip}`}}>
          <div style={{maxWidth:1180, margin:'0 auto'}}>
            <KidsNewsLockup size={66}/>
          </div>
        </div>

        <div style={{
          background:`linear-gradient(135deg, ${theme.hero1} 0%, ${theme.hero2} 100%)`,
          padding:'30px 28px 24px', borderBottom:`2px solid ${theme.border}`, textAlign:'center',
        }}>
          <div style={{
            fontSize:12, fontWeight:800, letterSpacing:'.12em',
            textTransform:'uppercase', color: theme.heroTextAccent, marginBottom:8,
          }}>
            🎉 All set{tweaks?.userName ? `, ${tweaks.userName}` : ''}
          </div>
          <h1 style={{
            fontFamily:'Fraunces, serif', fontWeight:900, fontSize:40, lineHeight:1.05,
            color:'#1b1230', margin:'0', letterSpacing:'-0.025em',
          }}>
            Today's <span style={{
              background: theme.accent, padding:'0 12px', borderRadius:12,
              display:'inline-block', transform:'rotate(-1.5deg)',
            }}>{totalMins} minutes</span> are ready
          </h1>
          <div style={{
            fontFamily:'Fraunces, serif', fontStyle:'italic', fontWeight:600,
            fontSize:19, color:'#c14e2a', marginTop:8,
          }}>
            {cfg.tagline || 'Little daily, big magic.'}
          </div>
        </div>

        <div style={{maxWidth:1180, margin:'0 auto', padding:'28px'}}>
          <div style={{
            display:'grid', gridTemplateColumns:'repeat(3, 1fr)', gap:18, marginBottom:28,
          }}>
            {finals.map((s, i) => {
              const c = CATEGORIES.find(x => x.label === s.category) || CATEGORIES[0];
              return (
                <div key={s.id} style={{
                  background:'#fff', border:`2px solid ${c.color}`, borderRadius:18,
                  overflow:'hidden', boxShadow:`0 4px 0 ${c.color}33`,
                }}>
                  <div style={{
                    aspectRatio:'16/10',
                    background: s.image ? `url(${s.image}) center/cover, ${c.color}` : c.color,
                  }}/>
                  <div style={{padding:'12px 14px 14px'}}>
                    <div style={{
                      display:'inline-flex', alignItems:'center', gap:5,
                      background: c.bg, color: c.color, padding:'3px 10px', borderRadius:999,
                      fontWeight:800, fontSize:11, marginBottom:8,
                    }}>
                      <span style={{fontSize:13}}>{c.emoji}</span>{i+1} · {s.readMins} min
                    </div>
                    <div style={{
                      fontFamily:'Fraunces, serif', fontWeight:700, fontSize:15,
                      lineHeight:1.22, color:'#1b1230', letterSpacing:'-0.01em',
                    }}>{s.title}</div>
                  </div>
                </div>
              );
            })}
          </div>

          <div style={{display:'flex', justifyContent:'space-between', alignItems:'center', flexWrap:'wrap', gap:12}}>
            <button onClick={() => { setShowComplete(false); setStep(0); }} style={{
              background:'transparent', border:'2px solid #e8dfd3', borderRadius:14,
              padding:'12px 20px', color:'#1b1230',
              fontWeight:800, fontSize:14, fontFamily:'Nunito, sans-serif',
              cursor:'pointer',
            }}>← Change my picks</button>

            <button onClick={lockNow} style={{
              background:'#1b1230', color:'#fff', border:'none', borderRadius:16,
              padding:'16px 28px', fontWeight:900, fontSize:17,
              fontFamily:'Nunito, sans-serif', cursor:'pointer',
              boxShadow:'0 5px 0 rgba(27,18,48,0.18)',
            }}>▶ Start your {dailyGoal} minutes</button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={{minHeight:'100vh', background: theme.bg, fontFamily:'Nunito, sans-serif'}}>
      {/* — Header strip — */}
      <div style={{
        background: theme.bg, borderBottom:`2px solid ${theme.chip}`,
        padding:'14px 28px',
      }}>
        <div style={{maxWidth:1180, margin:'0 auto'}}>
          <KidsNewsLockup size={66}/>
        </div>
      </div>

      {/* — Hero band: date + step heading + tagline + clickable tracker — */}
      <div style={{
        background:`linear-gradient(135deg, ${theme.hero1} 0%, ${theme.hero2} 100%)`,
        padding:'24px 28px 22px', borderBottom:`2px solid ${theme.border}`,
      }}>
        <div style={{maxWidth:1180, margin:'0 auto'}}>
          <div style={{
            fontSize:12, fontWeight:800, letterSpacing:'.12em', textTransform:'uppercase',
            color: theme.heroTextAccent, marginBottom:8,
          }}>
            {dateLabel}{tweaks?.userName ? ` · Hi ${tweaks.userName} 👋` : ''}
          </div>
          <div style={{display:'flex', alignItems:'center', gap:24, flexWrap:'wrap'}}>
            <div style={{flex:1, minWidth:280}}>
              <h1 style={{
                fontFamily:'Fraunces, serif', fontWeight:900, fontSize:36, lineHeight:1.0,
                color:'#1b1230', margin:'0', letterSpacing:'-0.025em',
              }}>
                Pick your <span style={{
                  background: cur.cat.color, color:'#fff', padding:'2px 12px',
                  borderRadius:10, display:'inline-block', transform:'rotate(-1deg)',
                }}>{cur.cat.emoji} {cur.cat.label}</span> story
              </h1>
              <div style={{
                fontFamily:'Fraunces, serif', fontStyle:'italic', fontWeight:600,
                fontSize:18, color:'#c14e2a', marginTop:8, letterSpacing:'-0.01em',
              }}>
                {cfg.tagline || 'Little daily, big magic.'} ({step + 1} of {groups.length})
              </div>
            </div>

            {/* Tracker pills — clickable to jump back */}
            <div style={{display:'flex', gap:8}}>
              {groups.map((g, i) => {
                const sel = selections[g.cat.label];
                const isCurrent = i === step;
                const story = sel ? g.candidates.find(s => s.id === sel) : null;
                return (
                  <button key={g.cat.label} type="button"
                    onClick={() => setStep(i)}
                    style={{
                      cursor:'pointer', border:'none',
                      background:'#fff', borderRadius:14,
                      padding:'10px 14px', minWidth:130,
                      borderTop: isCurrent ? `4px solid ${g.cat.color}` : '4px solid transparent',
                      borderLeft: sel ? `3px solid ${g.cat.color}` : '3px solid transparent',
                      boxShadow: isCurrent ? '0 4px 0 rgba(27,18,48,0.12)' : '0 2px 0 rgba(27,18,48,0.06)',
                      transform: isCurrent ? 'translateY(-1px)' : 'none',
                      transition:'all .15s', textAlign:'left',
                      fontFamily:'Nunito, sans-serif',
                    }}>
                    <div style={{
                      fontSize:10, fontWeight:900, letterSpacing:'.08em',
                      textTransform:'uppercase', color: g.cat.color,
                    }}>
                      {g.cat.emoji} {g.cat.label}
                    </div>
                    <div style={{
                      fontSize:11.5, color: sel ? '#1b1230' : '#9a8d7a',
                      fontWeight: sel ? 700 : 500, marginTop:3,
                      whiteSpace:'nowrap', overflow:'hidden', textOverflow:'ellipsis',
                      maxWidth:160,
                    }}>
                      {story ? story.title : '— pending —'}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      </div>

      {/* — Big feature + 2 small compagnion cards — */}
      <div style={{maxWidth:1180, margin:'0 auto', padding:'24px 28px 28px'}}>
        {featureCandidate && (
          <PickCard
            story={featureCandidate} variant="feature"
            picked={selectedId === featureCandidate.id}
            onSelect={() => select(featureCandidate.id)}
          />
        )}
        {smallCandidates.length > 0 && (
          <div style={{
            display:'grid',
            gridTemplateColumns: smallCandidates.length === 1 ? '1fr' : 'repeat(2, 1fr)',
            gap:18, marginTop:18,
          }}>
            {smallCandidates.map(s => (
              <PickCard key={s.id} story={s} variant="normal"
                picked={selectedId === s.id}
                onSelect={() => select(s.id)}
              />
            ))}
          </div>
        )}

        {/* — Bottom nav: Back + progress hint (Next is implicit — tap card) — */}
        <div style={{
          marginTop:28, display:'flex', justifyContent:'space-between',
          alignItems:'center', flexWrap:'wrap', gap:12,
        }}>
          <button onClick={back} disabled={step === 0} style={{
            background:'transparent', border:'2px solid #e8dfd3',
            borderRadius:14, padding:'12px 20px',
            color: step === 0 ? '#cbbfa9' : '#1b1230',
            fontWeight:800, fontSize:14, fontFamily:'Nunito, sans-serif',
            cursor: step === 0 ? 'not-allowed' : 'pointer',
          }}>← Back</button>

          <div style={{fontSize:12, color:'#6b5c80', fontWeight:700, letterSpacing:'.05em'}}>
            {Object.keys(selections).length}/{groups.length} chosen · {Object.keys(selections).length * (cfg.perArticleMinutes ?? 7)}/{dailyGoal} min
          </div>

          <div style={{
            fontSize:12, color:'#9a8d7a', fontWeight:700, letterSpacing:'.04em',
            fontStyle:'italic',
          }}>
            Tap a story to choose
          </div>
        </div>
      </div>
    </div>
  );
}

// ────────────────────────────────────────────────────────────────────
// Today's-pick sticky banner — sits below the header, follows scroll.
// Shows total daily progress + a context-aware Continue/Start CTA so
// the kid always has a one-tap path back into today's read.
//   · Pre-start  ........... "Start your 21 minutes ▶" (open first card)
//   · Mid-read   ........... "Continue Story 2 ▶"     (re-enter the
//                              article whose steps[] is partial)
//   · Done       ........... "🎉 All done — see you tomorrow"
// ────────────────────────────────────────────────────────────────────
function TodayBanner({ daily3, progress, theme, dailyGoal, minutesToday, onOpen, tweaks }) {
  if (!daily3 || daily3.length === 0) return null;

  // Find first article with partial progress (steps started, not all done).
  const partial = daily3.find(a => {
    const ap = (progress.articleProgress || {})[a.id];
    if (!ap || typeof ap !== 'object') return false;
    const steps = ap.steps || [];
    return steps.length > 0 && steps.length < 4;
  });
  const unread = daily3.find(a => !progress.readToday.includes(a.id));
  const target = partial || unread;
  const allDone = !target;

  const targetIdx = target ? daily3.findIndex(a => a.id === target.id) + 1 : 0;
  const pct = Math.min(100, Math.round((minutesToday / dailyGoal) * 100));
  const targetCat = target ? (CATEGORIES.find(c => c.label === target.category) || CATEGORIES[0]) : null;

  let label, action;
  if (allDone) {
    label = '🎉 All done — see you tomorrow';
    action = null;
  } else if (partial) {
    label = `Continue Story ${targetIdx} ▶`;
    action = () => onOpen(target.id);
  } else {
    label = `▶ Start Story ${targetIdx}`;
    action = () => onOpen(target.id);
  }

  return (
    <div style={{
      position:'sticky', top: 0, zIndex: 25,
      background: 'rgba(255,249,239,0.96)', backdropFilter:'blur(8px)',
      borderBottom:`2px solid ${theme.chip}`,
      padding:'26px 28px 24px',   // ~40% taller than the previous version
    }}>
      <div style={{maxWidth:1180, margin:'0 auto'}}>
        {/* Greeting row: "Hi {name}! 👋 · {date}" — moved up from the hero. */}
        <div style={{
          fontFamily:'Nunito, sans-serif', fontWeight:800,
          color: theme.heroTextAccent, fontSize:13,
          letterSpacing:'.1em', textTransform:'uppercase', marginBottom:8,
        }}>
          Hi {tweaks?.userName || 'friend'}! 👋 &nbsp;·&nbsp; {new Date().toLocaleDateString(undefined, {weekday:'long', month:'short', day:'numeric'})}
        </div>

        {/* Progress row: progress text + CTA button — bigger + breathier */}
        <div style={{
          fontFamily:'Nunito, sans-serif',
          fontSize:16, fontWeight:900, color:'#1b1230', letterSpacing:'.04em',
          textTransform:'uppercase', marginBottom:14,
          display:'flex', alignItems:'center', gap:14, flexWrap:'wrap',
        }}>
          <span style={{fontSize:22}}>⏱️</span>
          <span>Today's read</span>
          <span style={{
            fontFamily:'Fraunces, serif', fontWeight:900, fontSize:32,
            color: theme.heroTextAccent, letterSpacing:'-0.015em',
            textTransform:'none', lineHeight:1,
          }}>{minutesToday} / {dailyGoal} min</span>
          {!allDone && (
            <span style={{
              fontWeight:700, color:'#6b5c80', fontSize:13,
              textTransform:'none', letterSpacing:'.02em',
            }}>· {dailyGoal - minutesToday} min left today</span>
          )}
          {allDone && (
            <span style={{
              fontWeight:900, color:'#0e8d82', fontSize:14,
              textTransform:'none', letterSpacing:'.02em',
            }}>· 🎉 all done — see you tomorrow</span>
          )}
          {/* CTA — Continue or Start, mirrors the hero's old button.
              Pushed to the right; collapses below on narrow widths via flex-wrap. */}
          {!allDone && action && (
            <button onClick={action} style={{
              marginLeft:'auto',
              background:'#1b1230', color:'#fff', border:'none',
              borderRadius:14, padding:'10px 18px',
              fontFamily:'Nunito, sans-serif', fontWeight:900, fontSize:15,
              letterSpacing:'.02em', textTransform:'none', cursor:'pointer',
              boxShadow:'0 4px 0 rgba(0,0,0,0.18)',
            }}>{label}</button>
          )}
        </div>

        {/* Bottom row: progress bar fills the width */}
        <div style={{
          height:10, background:'#f0e8d8', borderRadius:999, overflow:'hidden',
        }}>
          <div style={{
            width: `${pct}%`, height:'100%',
            background:`linear-gradient(90deg, ${theme.accent}, #ff8a3d)`,
            borderRadius:999, transition:'width .3s ease',
          }}/>
        </div>
      </div>
    </div>
  );
}

function HomePage({ onOpen, onOpenArchive, level, setLevel, cat, setCat, progress, theme, heroVariant, tweaks, updateTweak, onOpenUserPanel, archiveDay }) {
  theme = theme || { bg:'#fff9ef', accent:'#ffc83d', hero1:'#ffe2a8', hero2:'#ffc0a8', border:'#ffb98a', heroTextAccent:'#c14e2a', card:'#fff', chip:'#f0e8d8' };

  const isZh = tweaks && tweaks.language === 'zh';
  // In zh mode we show the Chinese summary cards (language === 'zh'); otherwise
  // we show English cards at the selected level (Sprout => easy, Tree => middle).
  const matchesLanguageLevel = (a) => {
    if (isZh) return a.language === 'zh';
    return a.language === 'en' && a.level === level;
  };
  // archiveDay is now a date string "YYYY-MM-DD" (or null for today).
  const isArchive = typeof archiveDay === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(archiveDay);

  // When archiveDay changes, ARTICLES is swapped wholesale by loadArchive()
  // in index.html. Everything below filters the current ARTICLES in-memory.
  const filteredRaw = useMemoH(() => {
    const matches = ARTICLES.filter(matchesLanguageLevel);
    return (cat === 'All' || !cat) ? matches : matches.filter(a => a.category === cat);
  }, [isZh, level, cat, archiveDay]);
  // Cap today to 3 per category (editorial layout). Archive also 3 since
  // each day's bundle only has 3 per category anyway.
  const filtered = useMemoH(() => filteredRaw.slice(0, 3), [filteredRaw]);

  const [calendarOpen, setCalendarOpen] = useStateH(false);
  const [recentOpen, setRecentOpen] = useStateH(false);

  // Per-category displayable pool — only the first 3 stories of each category (what's shown on pages)
  const displayPool = useMemoH(() => {
    const out = [];
    const lang = ARTICLES.filter(matchesLanguageLevel);
    for (const c of CATEGORIES) {
      out.push(...lang.filter(a => a.category === c.label).slice(0, 3));
    }
    return out;
  }, [isZh, level, archiveDay]);
  const poolIds = useMemoH(() => new Set(displayPool.map(a => a.id)), [displayPool]);

  // ── Pick-3 lock state (per-day) ─────────────────────────────────────
  // The brand promise is "Today's 21 minutes" — a finite, chosen ritual.
  // First load each day shows a pick screen ("choose your 3 from 9");
  // once locked, the rest of the home renders with those 3 as the daily
  // stack. Cleared on day rollover (dayKey mismatch). MUST be defined
  // AFTER poolIds because picksLocked validates the saved ids against
  // the current pool.
  const [picksLock, setPicksLock] = useStateH(() => {
    const s = window.safeStorage?.getJSON('ohye_picks_lock_v1');
    return (s && s.dayKey && Array.isArray(s.ids)) ? s : { dayKey: null, ids: [] };
  });
  useEffectH(() => { window.safeStorage?.setJSON('ohye_picks_lock_v1', picksLock); }, [picksLock]);
  const todayKeyLocal = (new Date()).toDateString();
  const picksLocked = !isArchive
    && picksLock.dayKey === todayKeyLocal
    && picksLock.ids.length === 3
    && picksLock.ids.every(id => poolIds.has(id));
  const lockPicks = (ids) => {
    setPicksLock({ dayKey: todayKeyLocal, ids });
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };
  const resetPicks = () => {
    setPicksLock({ dayKey: null, ids: [] });
    // Scroll to top so the kid actually SEES the pick screen instead of
    // being mid-page where the daily-3 stack used to be.
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  // Pick 1 from each category by default, user can swap (only from the 3-per-category pool)
  const [dailyPicks, setDailyPicks] = useStateH(() => {
    const s = window.safeStorage?.getJSON('ohye_daily_picks_v3'); if (s && s.length === 3) return s;
    return null;
  });
  const defaultPicks = useMemoH(() => {
    const out = [];
    for (const c of CATEGORIES) {
      const first = displayPool.find(a => a.category === c.label);
      if (first) out.push(first.id);
    }
    return out.slice(0, 3);
  }, [displayPool]);
  // After pick-3 lock, the locked IDs are the daily 3. Falls back to
  // legacy `dailyPicks`/`defaultPicks` when not locked (e.g. archive view).
  const activePicks = picksLocked
    ? picksLock.ids
    : ((dailyPicks && dailyPicks.every(id => poolIds.has(id))) ? dailyPicks : defaultPicks);
  useEffectH(() => { window.safeStorage?.setJSON('ohye_daily_picks_v3', activePicks); }, [activePicks]);
  const swapPick = (idx, newId) => {
    const next = [...activePicks]; next[idx] = newId; setDailyPicks(next);
  };
  const daily3 = useMemoH(() => activePicks.map(id => displayPool.find(a => a.id === id)).filter(Boolean), [activePicks, displayPool]);
  const [swapOpen, setSwapOpen] = useStateH(null); // index being swapped

  const byCat = useMemoH(() => {
    const m = {};
    CATEGORIES.forEach(c => { m[c.label] = ARTICLES.filter(a => a.category === c.label); });
    return m;
  }, []);

  // ── Onboarding gate (pre-pick-3) ───────────────────────────────────
  // First-launch — empty userName triggers the welcome screen. Saves
  // name + avatar + level + theme + lang into tweaks, then proceeds
  // to pick-3 on next render. Skipped in archive mode (returning user
  // browsing past content).
  const needsOnboarding = !isArchive && (!tweaks?.userName || tweaks.userName.trim() === '');
  if (needsOnboarding) {
    return (
      <OnboardingScreen
        tweaks={tweaks}
        updateTweak={updateTweak || (()=>{})}
        level={level}
        setLevel={setLevel || (()=>{})}
        theme={theme}
      />
    );
  }

  // ── Pick-3 gate ────────────────────────────────────────────────────
  // Today, not archive, picks not yet locked → render pick screen and
  // bypass the rest of home. Archive mode keeps the standard browse.
  // MUST come after every hook call above to satisfy Rules of Hooks.
  if (!isArchive && !picksLocked && displayPool.length >= 3) {
    const dateLabel = new Date().toLocaleDateString('en-US',
      { weekday:'long', month:'short', day:'numeric' });
    // Pool of up to 9 candidates for the kid to choose from.
    const pickPool = displayPool.slice(0, 9);
    return (
      <PickFlow
        pool={pickPool}
        onLock={lockPicks}
        theme={theme}
        tweaks={tweaks}
        dateLabel={dateLabel}
      />
    );
  }

  // All user stats come from REAL state: progress.* (reading data) +
  // tweaks.* (preferences). MOCK_USER is no longer read here — it was
  // causing "I haven't read anything but it says 7-day streak" surprises.
  const minutesToday = progress.minutesToday || 0;
  const streak = tweaks.streakDays ?? 0;
  const goal = tweaks.dailyGoal || (window.SITE_CONFIG?.dailyGoalMinutes ?? 21);
  const goalPct = Math.min(1, minutesToday / goal);
  const readCount = (progress.readToday || []).length;

  return (
    <div style={{background: theme.bg, minHeight:'100vh'}}>
      {/* ——————————— HEADER ——————————— */}
      <Header level={level} setLevel={setLevel} theme={theme} tweaks={tweaks} onOpenUserPanel={onOpenUserPanel} progress={progress} recentOpen={recentOpen} setRecentOpen={setRecentOpen} onOpenArticle={onOpen} />

      {/* ——————————— TODAY'S PROGRESS BANNER (only when picks are locked) ——————————— */}
      {!isArchive && picksLocked && (
        <TodayBanner
          daily3={daily3}
          progress={progress}
          theme={theme}
          dailyGoal={goal}
          minutesToday={minutesToday}
          onOpen={onOpen}
          tweaks={tweaks}
        />
      )}

      {/* ——————————— ARCHIVE BANNER (when viewing an old day) ——————————— */}
      {isArchive && (
        <section style={{maxWidth:1180, margin:'16px auto 0', padding:'0 28px'}}>
          <div style={{
            background:'#1b1230', color:'#fff', borderRadius:18,
            padding:'14px 20px', display:'flex', alignItems:'center', gap:14, flexWrap:'wrap',
          }}>
            <div style={{fontSize:26}}>🗂️</div>
            <div style={{flex:1, minWidth:200}}>
              <div style={{fontFamily:'Fraunces, serif', fontWeight:900, fontSize:20, lineHeight:1.1}}>
                {archiveDayLabel(archiveDay)}
              </div>
              <div style={{fontSize:12, color:'#ffc83d', fontWeight:700, letterSpacing:'.06em', textTransform:'uppercase', marginTop:2}}>
                Reading an old edition
              </div>
            </div>
            <button onClick={()=>onOpenArchive(null)} style={{
              background:'#ffc83d', color:'#1b1230', border:'none', borderRadius:999,
              padding:'10px 18px', fontWeight:900, fontSize:13, cursor:'pointer', fontFamily:'Nunito, sans-serif',
            }}>← Return to today</button>
          </div>
        </section>
      )}

      {/* ——————————— TODAY'S PICK BANNER (hidden in archive) ———————————
          Single column, full-width. Title row on top, 3 cards stacked
          full-width below. Greeting moved to the sticky TodayBanner. */}
      {!isArchive && (
      <section style={{maxWidth:1180, margin:'0 auto', padding:'24px 28px 0'}}>
        <div style={{
          background:`linear-gradient(135deg, ${theme.hero1} 0%, ${theme.hero2} 100%)`,
          borderRadius:28,
          padding:'40px 48px',   // ~40% bigger than the previous 28×32
          position:'relative',
          overflow:'hidden',
          border:`2px solid ${theme.border}`,
        }}>
          {/* doodle */}
          <svg style={{position:'absolute', right:-20, bottom:-30, opacity:.18}} width="240" height="240" viewBox="0 0 100 100"><circle cx="50" cy="50" r="40" stroke="#1b1230" strokeWidth="2" fill="none"/><circle cx="50" cy="50" r="28" stroke="#1b1230" strokeWidth="2" fill="none" strokeDasharray="4 6"/></svg>

          {/* Title row: headline + pick-again / swap-hint toolbar */}
          <div style={{
            display:'flex', alignItems:'center', justifyContent:'space-between',
            flexWrap:'wrap', gap:14, marginBottom:22, position:'relative',
          }}>
            <h1 style={{
              fontFamily:'Fraunces, serif', fontWeight:900, fontSize:48, lineHeight:1.02,
              color:'#1b1230', margin:0, letterSpacing:'-0.02em',
            }}>
              Today's <span style={{background: theme.accent, padding:'0 12px', borderRadius:12, display:'inline-block', transform:'rotate(-2deg)'}}>Top 3 Pick</span>
            </h1>
            <div style={{display:'flex', alignItems:'center', gap:10, flexWrap:'wrap'}}>
              {picksLocked && (
                <button onClick={resetPicks} style={{
                  background:'transparent', border:'1.5px solid #f0e8d8',
                  borderRadius:999, padding:'7px 14px', cursor:'pointer',
                  fontSize:12, fontWeight:800, color:'#1b1230',
                  fontFamily:'Nunito, sans-serif', letterSpacing:'.02em',
                }} title="Re-open the pick screen for today">🔄 Pick again</button>
              )}
              <div style={{fontSize:12, color:'#6b5c80', fontWeight:700}}>Tap ⇆ to swap</div>
            </div>
          </div>

          {/* 3 cards stacked vertically, full-width row layout. Larger image
              and a 4-line summary so each pick reads like a real teaser. */}
          <div style={{display:'flex', flexDirection:'column', gap:14, position:'relative'}}>
            {daily3.map((a, i) => {
              const catColor = CATEGORIES.find(c => c.label === a.category)?.color || '#1b1230';
              const alternates = displayPool.filter(x => x.category === a.category && !activePicks.includes(x.id));
              const canSwap = alternates.length > 0;
              const isSwapping = swapOpen === i;
              return (
                <div key={a.id} style={{position:'relative'}}>
                  {isSwapping ? (
                    <div style={{
                      background:'#1b1230', borderRadius:16, padding:14,
                      boxShadow:'0 4px 0 rgba(27,18,48,0.15)',
                    }}>
                      <div style={{display:'flex', alignItems:'center', justifyContent:'space-between', padding:'2px 6px 10px'}}>
                        <div style={{fontSize:11, fontWeight:800, color:'#ffc83d', textTransform:'uppercase', letterSpacing:'.08em'}}>Pick a different {a.category} story</div>
                        <button onClick={()=>setSwapOpen(null)} style={{
                          background:'transparent', border:'none', color:'#ffc83d', fontWeight:900, cursor:'pointer', fontSize:18, padding:'0 4px',
                        }} title="Close">✕</button>
                      </div>
                      {alternates.map(alt => (
                        <button key={alt.id} onClick={()=>{swapPick(i, alt.id); setSwapOpen(null);}} style={{
                          display:'flex', alignItems:'center', gap:12, width:'100%', textAlign:'left',
                          background:'rgba(255,255,255,0.06)', color:'#fff',
                          border:'none', padding:10, borderRadius:10, cursor:'pointer',
                          marginBottom:8,
                        }} onMouseEnter={e=>e.currentTarget.style.background='rgba(255,255,255,0.14)'} onMouseLeave={e=>e.currentTarget.style.background='rgba(255,255,255,0.06)'}>
                          <div style={{width:56, height:56, borderRadius:10, flexShrink:0, background:`url(${alt.image}) center/cover, ${catColor}`}}/>
                          <div style={{flex:1, minWidth:0}}>
                            <div style={{fontWeight:800, fontSize:14, lineHeight:1.25}}>{alt.title}</div>
                            <div style={{fontSize:11, opacity:0.7, fontWeight:700, marginTop:3}}>{alt.readMins} min · {alt.tag}</div>
                          </div>
                        </button>
                      ))}
                      {alternates.length === 0 && (
                        <div style={{color:'#fff', opacity:0.6, fontSize:12, padding:10, textAlign:'center'}}>No other {a.category} stories today.</div>
                      )}
                    </div>
                  ) : (
                  <div style={{
                    background:'#fff', border:'2px solid #fff', borderRadius:18,
                    padding:'18px 22px', display:'flex', gap:20, alignItems:'flex-start',
                    boxShadow:'0 2px 0 rgba(27,18,48,0.08)',
                  }}>
                    <div style={{
                      width:56, height:56, borderRadius:16, flexShrink:0,
                      background: catColor, color:'#fff', display:'flex', alignItems:'center', justifyContent:'center',
                      fontFamily:'Fraunces, serif', fontWeight:900, fontSize:26,
                    }}>{i+1}</div>
                    <div style={{
                      width:196, height:196, borderRadius:16, flexShrink:0,
                      background:`url(${a.image}) center/cover, ${catColor}`,
                      border:`2px solid ${catColor}`,
                    }}/>
                    <button onClick={()=>onOpen(a.id)} style={{
                      flex:1, minWidth:0, background:'transparent', border:'none', textAlign:'left', cursor:'pointer', padding:0,
                      display:'flex', flexDirection:'column', gap:8,
                    }}>
                      <div style={{
                        fontFamily:'Fraunces, serif', fontWeight:900,
                        fontSize:24, color:'#1b1230', lineHeight:1.2,
                        display:'-webkit-box', WebkitBoxOrient:'vertical', WebkitLineClamp:2, overflow:'hidden',
                      }}>
                        {a.title}
                      </div>
                      <div style={{
                        fontSize:16, color:'#3a2a4a', lineHeight:1.5,
                        display:'-webkit-box', WebkitBoxOrient:'vertical', WebkitLineClamp:4, overflow:'hidden',
                      }}>
                        {_shortHook(a.summary, 60)}
                      </div>
                      {/* Category + read-time line removed — duplicate of the
                          colored slot number on the left and the global "21 min"
                          headline above. Card now leans entirely on title + summary. */}
                    </button>
                    <div style={{display:'flex', flexDirection:'column', alignItems:'flex-end', gap:10, flexShrink:0}}>
                      {(() => {
                        const p = _articlePct((progress.articleProgress||{})[a.id]);
                        const done = progress.readToday.includes(a.id);
                        if (done) return <span style={{fontSize:28, color:'#17b3a6'}}>✓</span>;
                        if (p > 0) return <span style={{fontSize:12, fontWeight:800, color:'#f4a24c', background:'#fff4e0', padding:'4px 10px', borderRadius:999, border:'1.5px solid #f4a24c'}}>{p}%</span>;
                        return null;
                      })()}
                      {canSwap && (
                        <button onClick={()=>setSwapOpen(i)} title={`Pick a different ${a.category} story`} style={{
                          background:'transparent', color:'#6b5c80',
                          border:'2px solid #f0e8d8', borderRadius:10,
                          width:36, height:36, cursor:'pointer', fontSize:16, fontWeight:900,
                          display:'flex', alignItems:'center', justifyContent:'center',
                        }}>⇆</button>
                      )}
                    </div>
                  </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </section>
      )}

      {/* ——————————— CATEGORY TABS ——————————— */}
      <section style={{maxWidth:1180, margin: isArchive ? '24px auto 0' : '32px auto 0', padding:'0 28px', position:'relative'}}>
        <div style={{display:'flex', gap:12, flexWrap:'wrap', alignItems:'center'}}>
          {CATEGORIES.map(c => (
            <CatTab key={c.id} label={c.label} emoji={c.emoji} color={c.color} bg={c.bg} active={cat===c.label} onClick={()=>setCat(c.label)} />
          ))}
          {!isArchive && (
            <button onClick={()=>setCalendarOpen(v=>!v)} style={{
              background: calendarOpen ? '#1b1230' : '#fff', color: calendarOpen ? '#ffc83d' : '#1b1230',
              border: calendarOpen ? '2px solid #1b1230' : '2px dashed #c9b99a',
              borderRadius:999, padding:'8px 16px', fontWeight:800, fontSize:13, cursor:'pointer',
              display:'inline-flex', alignItems:'center', gap:6, fontFamily:'Nunito, sans-serif',
            }}>📅 View old news</button>
          )}
          <div style={{flex:1}}/>
          <span style={{fontSize:13, color:'#7a6b8c', fontWeight:600}}>
            {isZh ? (<>Reading in <b style={{color:'#1b1230'}}>中文</b> · summary only</>) : (<>Showing stories at <b style={{color:'#1b1230'}}>{level}</b> level</>)}
          </span>
        </div>
        {calendarOpen && (
          <DatePopover onPick={(d)=>{setCalendarOpen(false); onOpenArchive(d);}} onClose={()=>setCalendarOpen(false)} />
        )}
      </section>

      {/* ——————————— ARTICLES GRID ——————————— */}
      <section style={{maxWidth:1180, margin:'20px auto 0', padding:'0 28px 60px'}}>
        {filtered.length === 0 ? (
          <div style={{textAlign:'center', padding:'40px 20px', color:'#9a8d7a', background:'#fff', borderRadius:16, border:'2px dashed #f0e8d8'}}>
            <div style={{fontSize:36, marginBottom:8}}>🌱</div>
            <div style={{fontWeight:800, color:'#1b1230', marginBottom:4}}>No stories here</div>
            <div style={{fontSize:13}}>Try a different level from your profile, or a different day.</div>
          </div>
        ) : filtered.length === 3 && !isArchive ? (
          /* Editorial layout: big feature on top (photo left, article right) + 2 companions below */
          <div style={{display:'flex', flexDirection:'column', gap:20}}>
            <ArticleCard article={filtered[0]} onOpen={()=>onOpen(filtered[0].id)} read={progress.readToday.includes(filtered[0].id)} pct={_articlePct((progress.articleProgress||{})[filtered[0].id])} variant="feature" />
            <div style={{display:'grid', gridTemplateColumns:'1fr 1fr', gap:20}}>
              <ArticleCard article={filtered[1]} onOpen={()=>onOpen(filtered[1].id)} read={progress.readToday.includes(filtered[1].id)} pct={_articlePct((progress.articleProgress||{})[filtered[1].id])} variant="normal" />
              <ArticleCard article={filtered[2]} onOpen={()=>onOpen(filtered[2].id)} read={progress.readToday.includes(filtered[2].id)} pct={_articlePct((progress.articleProgress||{})[filtered[2].id])} variant="normal" />
            </div>
          </div>
        ) : (
          <div style={{
            display:'grid',
            gridTemplateColumns:'repeat(auto-fill, minmax(280px, 1fr))',
            gap:20,
          }}>
            {filtered.map((a, i) => (
              <ArticleCard key={a.id} article={a} onOpen={()=>onOpen(a.id)} read={progress.readToday.includes(a.id)} pct={_articlePct((progress.articleProgress||{})[a.id])} variant={i===0 && !isArchive ? 'feature' : 'normal'} />
            ))}
          </div>
        )}
      </section>

      {/* ——————————— FOOTER ——————————— */}
      <footer style={{textAlign:'center', padding:'28px 20px 40px', color:'#9a8d7a', fontSize:13}}>
        {(() => {
          // Use the freshest mined_at across all loaded articles as the "page
          // generated" timestamp. Displayed in the reader's local timezone.
          const ms = (ARTICLES || [])
            .map(a => a.minedAt ? new Date(a.minedAt).getTime() : 0)
            .filter(t => t > 0);
          if (!ms.length) return null;
          const d = new Date(Math.max(...ms));
          const when = d.toLocaleString(undefined, {
            year:'numeric', month:'short', day:'numeric',
            hour:'numeric', minute:'2-digit',
          });
          return (
            <div style={{marginBottom:6, fontSize:12, color:'#b0a490'}}>
              📅 Page generated · {when}
            </div>
          );
        })()}
        Made for curious kids · {window.SITE_CONFIG?.brand || '21 minutes every day'} 🎈
      </footer>
    </div>
  );
}

// ——————————— DATE POPOVER ———————————
// archiveDay is a "YYYY-MM-DD" string.
function archiveDayLabel(d) {
  if (!d) return '';
  const dt = new Date(d + 'T00:00:00');
  return dt.toLocaleDateString(undefined, { weekday:'long', month:'short', day:'numeric' });
}

function DatePopover({ onPick, onClose }) {
  // Fetch the list of archived days from Supabase. The newest entry is
  // today; we exclude it so the picker only offers past editions.
  const [index, setIndex] = useStateH({ dates: [] });
  useStateH && React.useEffect(() => {
    let cancelled = false;
    window.loadArchiveIndex().then(r => { if (!cancelled) setIndex(r); });
    return () => { cancelled = true; };
  }, []);
  const todayStr = new Date().toISOString().slice(0, 10);
  const pastDates = (index.dates || []).filter(d => d !== todayStr).slice(0, 14);

  return (
    <>
      <div onClick={onClose} style={{position:'fixed', inset:0, zIndex:40, background:'transparent'}}/>
      <div style={{
        position:'absolute', top:'100%', marginTop:10, left:28, zIndex:50,
        background:'#fff', borderRadius:18, border:'2px solid #1b1230',
        padding:16, boxShadow:'0 10px 0 rgba(27,18,48,0.12)', width:340,
      }}>
        <div style={{fontFamily:'Fraunces, serif', fontWeight:900, fontSize:18, color:'#1b1230', marginBottom:4}}>📅 Pick a past day</div>
        <div style={{fontSize:12, color:'#6b5c80', fontWeight:600, marginBottom:12}}>
          {pastDates.length === 0
            ? "No past editions yet — check back tomorrow."
            : "Catch up on editions you missed."}
        </div>
        {pastDates.length > 0 && (
          <div style={{display:'grid', gridTemplateColumns:'repeat(7, 1fr)', gap:6}}>
            {pastDates.map(d => {
              const dt = new Date(d + 'T00:00:00');
              return (
                <button key={d} onClick={()=>onPick(d)} style={{
                  padding:'10px 4px', border:'2px solid #f0e8d8',
                  background:'#fff9ef', borderRadius:12, cursor:'pointer',
                  fontFamily:'Nunito, sans-serif',
                }}>
                  <div style={{fontSize:10, fontWeight:800, color:'#9a8d7a', textTransform:'uppercase'}}>{dt.toLocaleDateString(undefined,{weekday:'short'}).slice(0,3)}</div>
                  <div style={{fontFamily:'Fraunces, serif', fontWeight:900, fontSize:20, color:'#1b1230'}}>{dt.getDate()}</div>
                  <div style={{fontSize:9, color:'#9a8d7a', fontWeight:700}}>{dt.toLocaleDateString(undefined,{month:'short'})}</div>
                </button>
              );
            })}
          </div>
        )}
      </div>
    </>
  );
}

// ——————————— HEADER ———————————
function Header({ level, setLevel, theme, tweaks, onOpenUserPanel, progress, recentOpen, setRecentOpen, onOpenArticle }) {
  theme = theme || { bg:'#fff9ef', chip:'#f0e8d8' };
  tweaks = tweaks || {};
  return (
    <header style={{
      background: theme.bg,
      borderBottom: `2px solid ${theme.chip}`,
      position:'sticky', top:0, zIndex:30, backdropFilter:'blur(6px)',
    }}>
      <div style={{maxWidth:1180, margin:'0 auto', padding:'14px 28px', display:'flex', alignItems:'center', gap:16}}>
        {/* New brand lockup — kidsnews mark + wordmark + "a 21mins channel" */}
        <KidsNewsLockup size={66}/>

        <div style={{flex:1}}/>

        {/* Streak pill → opens recent reads popover */}
        <div style={{position:'relative'}}>
          <button onClick={()=>setRecentOpen(v=>!v)} style={{
            display:'flex', alignItems:'center', gap:10, background:'#1b1230', color:'#fff',
            padding:'6px 14px 6px 6px', borderRadius:999, border:'none', cursor:'pointer',
            fontFamily:'Nunito, sans-serif',
          }}>
            <StreakRing minutes={(progress && progress.minutesToday) || 0} goal={tweaks.dailyGoal || (window.SITE_CONFIG?.dailyGoalMinutes ?? 21)} streak={tweaks.streakDays ?? 0} size={40}/>
            <div style={{lineHeight:1.1, textAlign:'left'}}>
              <div style={{fontSize:11, opacity:.7, fontWeight:700}}>STREAK</div>
              <div style={{fontWeight:800, fontSize:14}}>{tweaks.streakDays ?? 0} days 🔥</div>
            </div>
            <span style={{fontSize:11, opacity:0.7, marginLeft:4}}>▾</span>
          </button>
          {recentOpen && (
            <RecentReadsPopover onClose={()=>setRecentOpen(false)} onOpenArticle={(id)=>{setRecentOpen(false); onOpenArticle(id);}} readIds={(progress&&progress.readToday)||[]}/>
          )}
        </div>

        {/* User button — opens the profile panel */}
        {window.UserButton && (
          <window.UserButton tweaks={tweaks} level={level} streak={tweaks.streakDays ?? 0} onClick={onOpenUserPanel}/>
        )}
      </div>
    </header>
  );
}

function _HeaderOldContentRemoved() { return null; }

// ——————————— RECENT READS POPOVER ———————————
function RecentReadsPopover({ onClose, onOpenArticle, readIds }) {
  // Take most recent 15 articles the user has read (from readIds, in order)
  const recent = [];
  const seen = new Set();
  for (let i = readIds.length - 1; i >= 0 && recent.length < 15; i--) {
    const id = readIds[i];
    if (seen.has(id)) continue;
    const a = ARTICLES.find(x => x.id === id);
    if (a) { recent.push(a); seen.add(id); }
  }
  return (
    <>
      <div onClick={onClose} style={{position:'fixed', inset:0, zIndex:40}}/>
      <div style={{
        position:'absolute', top:'calc(100% + 10px)', right:0, zIndex:50, width:340,
        background:'#fff', borderRadius:18, border:'2px solid #1b1230', boxShadow:'0 10px 0 rgba(27,18,48,0.15)',
        padding:14, maxHeight:440, overflow:'auto',
      }}>
        <div style={{display:'flex', justifyContent:'space-between', alignItems:'baseline', marginBottom:10}}>
          <div style={{fontFamily:'Fraunces, serif', fontWeight:900, fontSize:18, color:'#1b1230'}}>🔥 Recently read</div>
          <div style={{fontSize:11, color:'#9a8d7a', fontWeight:700}}>Last {recent.length}</div>
        </div>
        {recent.length === 0 ? (
          <div style={{padding:'24px 8px', textAlign:'center', color:'#9a8d7a', fontSize:13}}>
            You haven't read anything yet today. Start your {goal} min!
          </div>
        ) : recent.map(a => {
          const catColor = CATEGORIES.find(c => c.label === a.category)?.color || '#1b1230';
          return (
            <button key={a.id} onClick={()=>onOpenArticle(a.id)} style={{
              display:'flex', gap:10, alignItems:'center', width:'100%', textAlign:'left',
              background:'transparent', border:'none', padding:'8px 6px', borderRadius:10, cursor:'pointer',
              borderBottom:'1px dashed #f0e8d8',
            }} onMouseEnter={e=>e.currentTarget.style.background='#fff9ef'} onMouseLeave={e=>e.currentTarget.style.background='transparent'}>
              <div style={{width:8, height:32, borderRadius:4, background: catColor, flexShrink:0}}/>
              <div style={{flex:1, minWidth:0}}>
                <div style={{fontWeight:800, fontSize:13, color:'#1b1230', lineHeight:1.2, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap'}}>{a.title}</div>
                <div style={{fontSize:11, color:'#6b5c80', fontWeight:600, marginTop:2}}>{a.category} · {a.level || '中文'} · {a.readMins} min</div>
              </div>
              <span style={{color:'#17b3a6', fontWeight:900}}>✓</span>
            </button>
          );
        })}
      </div>
    </>
  );
}

// ——————————— CATEGORY TAB ———————————
function CatTab({ label, emoji, color, bg, active, onClick }) {
  return (
    <button onClick={onClick} style={{
      background: active ? color : bg,
      color: active ? '#fff' : color,
      border:'none', borderRadius:999, padding:'10px 18px',
      fontWeight:800, fontSize:14, cursor:'pointer',
      display:'inline-flex', alignItems:'center', gap:7,
      fontFamily:'Nunito, sans-serif',
      boxShadow: active ? '0 3px 0 rgba(27,18,48,0.15)' : 'none',
      transition:'all .15s',
    }}>
      <span style={{fontSize:15}}>{emoji}</span>{label}
    </button>
  );
}

// ——————————— PROGRESS BADGE (ring for in-progress, ✓ for complete) ———————————
function ProgressBadge({ pct, size = 28 }) {
  if (!pct || pct <= 0) return null;
  if (pct >= 100) {
    return (
      <div style={{background:'#17b3a6', color:'#fff', padding:'4px 10px', borderRadius:999, fontSize:11, fontWeight:800, display:'inline-flex', alignItems:'center', gap:4, boxShadow:'0 2px 6px rgba(23,179,166,0.35)'}}>
        ✓ Read
      </div>
    );
  }
  const r = size / 2 - 3;
  const c = 2 * Math.PI * r;
  const dash = (pct / 100) * c;
  return (
    <div style={{background:'#fff', padding:'3px 10px 3px 4px', borderRadius:999, fontSize:11, fontWeight:800, display:'inline-flex', alignItems:'center', gap:6, color:'#1b1230', boxShadow:'0 2px 6px rgba(27,18,48,0.12)'}}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="#f0e8d8" strokeWidth="3"/>
        <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="#f4a24c" strokeWidth="3"
          strokeDasharray={`${dash} ${c}`} strokeLinecap="round"
          transform={`rotate(-90 ${size/2} ${size/2})`}/>
      </svg>
      {pct}%
    </div>
  );
}

// ——————————— ARTICLE CARD ———————————
// —— Highlights keyword terms in an article summary ——
// Matches each term as a whole word OR with common English suffixes
// (bet → bets/betting, ban → banned/banning, fine → fined). All occurrences
// are highlighted. Case-insensitive. Styled with a chip + dotted underline.
function HighlightedSummary({ text, keywords }) {
  if (!keywords || keywords.length === 0) return <>{text}</>;
  // Common English verb/noun suffixes so "ban" catches "banned/banning",
  // "fine" catches "fined", "bet" catches "bets/betting", etc.
  const SUFFIX = '(?:s|es|ed|d|ing|ning|ned|ting|ted|er|ers)?';
  // Find every occurrence of every term, case-insensitive, global.
  const hits = [];
  for (const k of keywords) {
    const escaped = k.term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const re = new RegExp(`\\b(${escaped})${SUFFIX}\\b`, 'gi');
    let m;
    while ((m = re.exec(text)) !== null) {
      hits.push({ term: k.term, def: k.def, start: m.index, end: m.index + m[0].length, match: m[0] });
      if (m.index === re.lastIndex) re.lastIndex++; // avoid zero-length loops
    }
  }
  // Sort by start; drop overlaps, preferring earliest/longest
  hits.sort((a, b) => a.start - b.start || (b.end - b.start) - (a.end - a.start));
  const dedup = [];
  let cursor = 0;
  for (const h of hits) {
    if (h.start >= cursor) { dedup.push(h); cursor = h.end; }
  }
  if (dedup.length === 0) return <>{text}</>;
  const parts = [];
  let i = 0;
  dedup.forEach((h, idx) => {
    if (h.start > i) parts.push(<React.Fragment key={'t'+idx}>{text.slice(i, h.start)}</React.Fragment>);
    parts.push(
      <KeywordTip key={'k'+idx} term={h.match} def={h.def}/>
    );
    i = h.end;
  });
  if (i < text.length) parts.push(<React.Fragment key="tail">{text.slice(i)}</React.Fragment>);
  return <>{parts}</>;
}

function KeywordTip({ term, def }) {
  const [hover, setHover] = useStateH(false);
  const [pos, setPos] = React.useState({ top: 0, left: 0 });
  const spanRef = React.useRef(null);
  const show = (e) => {
    e.stopPropagation();
    const r = spanRef.current && spanRef.current.getBoundingClientRect();
    if (r) setPos({ top: r.top - 8, left: r.left + r.width / 2 });
    setHover(true);
  };
  return (
    <span
      ref={spanRef}
      onMouseEnter={show}
      onMouseLeave={(e) => { e.stopPropagation(); setHover(false); }}
      onClick={(e) => e.stopPropagation()}
      style={{
        display:'inline-block',
        fontFamily:'Fraunces, Georgia, serif',
        fontStyle:'italic',
        fontWeight:700,
        color:'#b2541a',
        background: hover ? '#ffedc1' : '#fff4d6',
        padding:'0 6px',
        borderRadius:6,
        textDecoration:'underline dotted #d89b4a',
        textUnderlineOffset:'3px',
        cursor:'help',
        transition:'background .15s',
      }}
    >
      {term}
      {hover && ReactDOM.createPortal(
        <div style={{
          position:'fixed',
          top: pos.top,
          left: pos.left,
          transform:'translate(-50%, -100%)',
          background:'#1b1230',
          color:'#fff',
          padding:'10px 12px',
          borderRadius:12,
          fontFamily:'Nunito, sans-serif',
          fontStyle:'normal',
          fontSize:12,
          fontWeight:600,
          lineHeight:1.45,
          width:'max-content',
          maxWidth:240,
          whiteSpace:'normal',
          textAlign:'left',
          boxShadow:'0 8px 24px rgba(27,18,48,0.25)',
          zIndex:9999,
          pointerEvents:'none',
        }}>
          <div style={{
            fontSize:10, fontWeight:800, color:'#ffc83d',
            textTransform:'uppercase', letterSpacing:'.08em', marginBottom:3,
          }}>What it means</div>
          {def}
          <div style={{
            position:'absolute', top:'100%', left:'50%', transform:'translateX(-50%)',
            width:0, height:0,
            borderLeft:'6px solid transparent', borderRight:'6px solid transparent',
            borderTop:'6px solid #1b1230',
          }}/>
        </div>,
        document.body
      )}
    </span>
  );
}

function ArticleCard({ article, onOpen, read, pct, variant }) {
  const [hover, setHover] = useStateH(false);
  const isFeature = variant === 'feature';
  const isTall = variant === 'tall-feature';
  return (
    <button
      onClick={onOpen}
      onMouseEnter={()=>setHover(true)}
      onMouseLeave={()=>setHover(false)}
      style={{
        background:'#fff',
        border:'2px solid #f0e8d8',
        borderRadius:22,
        padding:0,
        textAlign:'left',
        cursor:'pointer',
        overflow:'hidden',
        position:'relative',
        transform: hover ? 'translateY(-4px) rotate(-0.3deg)' : 'translateY(0)',
        boxShadow: hover ? '0 10px 0 rgba(27,18,48,0.08)' : '0 4px 0 rgba(27,18,48,0.06)',
        transition:'all .2s cubic-bezier(.3,1.4,.6,1)',
        gridColumn: isFeature ? 'span 2' : 'auto',
        display:'flex',
        flexDirection:'column',
        width: isTall ? '100%' : undefined,
        height: isTall ? '100%' : undefined,
      }}
    >
      <div style={{
        position:'relative',
        background:`url(${article.image}) center/cover`,
        aspectRatio: isTall ? 'auto' : (isFeature ? '16/9' : '16/10'),
        width:'100%',
        flex: isTall ? '1 1 auto' : undefined,
        minHeight: isTall ? 280 : 'auto',
      }}>
        {(read || (pct && pct > 0)) && (
          <div style={{position:'absolute', top:10, right:10}}>
            <ProgressBadge pct={read ? 100 : pct}/>
          </div>
        )}
      </div>
      <div style={{padding: isFeature ? '26px 32px 24px' : (isTall ? '24px 26px' : '16px 18px 18px'), flex:'0 0 auto', display:'flex', flexDirection:'column', gap:10}}>
        <h3 style={{
          fontFamily:'Fraunces, serif',
          fontWeight:800,
          fontSize: isFeature ? 28 : (isTall ? 26 : 19),
          lineHeight:1.15,
          letterSpacing:'-0.01em',
          color:'#1b1230',
          margin:0,
        }}>{article.title}</h3>
        <p style={{
          fontSize: isFeature ? 15 : 13.5,
          color:'#4a3d5e',
          lineHeight:1.6,
          margin:0,
        }}><HighlightedSummary text={article.summary} keywords={article.keywords}/></p>
        <div style={{display:'flex', alignItems:'center', gap:8, flexWrap:'wrap', marginTop:'auto', paddingTop:8}}>
          <XpBadge xp={article.xp} small/>
          <span style={{fontSize:12, color:'#9a8d7a', fontWeight:700}}>⏱ {article.readMins} min</span>
        </div>
      </div>
    </button>
  );
}

Object.assign(window, { HomePage });
