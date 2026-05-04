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

// Read state from articleProgress alone (the persistent, 10-day-bounded
// dictionary). readToday only knows TODAY's completes — using it as the
// "read" source meant past-day reads (visible in archive view + Continue
// rail) couldn't show their completion checkmark, only today's could.
// articleProgress.steps.length===4 is the right signal: persists for 10
// days, survives midnight rollover, works for any day's articles.
function _isDoneArticle(progress, articleId) {
  const ap = ((progress && progress.articleProgress) || {})[articleId];
  if (!ap) return false;
  if (typeof ap === 'number') return ap >= 100;
  return ((ap.steps || []).length) >= 4;
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

// ────────────────────────────────────────────────────────────────────
// SignInNudge — slim banner above the daily ritual that tells anon
// users their streak is at risk. Renders only when:
//   (a) the kid has done onboarding (otherwise OnboardingScreen has
//       its own loud sign-in CTA — don't double up)
//   (b) they're NOT already Gmail-linked
//   (c) they haven't dismissed it (`ohye_signin_nudge_dismissed`)
// Tap → opens the user panel where IdentityExpander handles the
// actual OAuth flow.
// ────────────────────────────────────────────────────────────────────
function SignInNudge({ tweaks, onOpenUserPanel }) {
  const [identity, setIdentity] = useStateH(undefined);  // undefined = loading; null = anon
  const [dismissed, setDismissed] = useStateH(() => {
    try { return window.safeStorage?.get('ohye_signin_nudge_dismissed') === '1'; }
    catch { return false; }
  });
  useEffectH(() => {
    if (!window.kidsync || !window.kidsync.getIdentity) {
      setIdentity(null);
      return;
    }
    let cancelled = false;
    window.kidsync.getIdentity().then(id => { if (!cancelled) setIdentity(id || null); }).catch(() => {});
    return () => { cancelled = true; };
  }, []);
  // Hide while loading + after dismiss + when already Gmail-linked +
  // when onboarding hasn't happened yet.
  if (identity === undefined) return null;
  if (dismissed) return null;
  // Hide for any signed-in identity (Gmail OR magic-link email).
  // Both anchor recovery; nudging signed-in kids is just nagging.
  if (identity && (identity.type === 'google' || identity.type === 'email')) return null;
  if (!tweaks || !(tweaks.userName || '').trim()) return null;

  const dismiss = () => {
    setDismissed(true);
    try { window.safeStorage?.set('ohye_signin_nudge_dismissed', '1'); } catch {}
  };

  return (
    <section style={{maxWidth:1180, margin:'14px auto 0', padding:'0 28px'}}>
      <div style={{
        display:'flex', alignItems:'center', gap:14, flexWrap:'wrap',
        background:'linear-gradient(135deg, #fff9ef 0%, #ffe9bb 100%)',
        border:'2px solid #1b1230', borderRadius:14,
        padding:'10px 14px',
        boxShadow:'0 3px 0 rgba(27,18,48,0.10)',
      }}>
        <div style={{fontSize:22}}>✨</div>
        <div style={{flex:1, minWidth:200}}>
          <div style={{fontFamily:'Fraunces, serif', fontWeight:800, fontSize:14.5, color:'#1b1230', lineHeight:1.2}}>
            Save your streak — sign in once
          </div>
          <div style={{fontSize:12, color:'#3a2a4a', marginTop:2, lineHeight:1.4}}>
            Right now your reading lives <strong>only on this browser</strong>. Sign in with Google so it follows you anywhere.
          </div>
        </div>
        <button onClick={onOpenUserPanel} style={{
          background:'#1b1230', color:'#ffc83d', border:'none', borderRadius:10,
          padding:'8px 14px', fontWeight:900, fontSize:12,
          fontFamily:'Nunito, sans-serif', cursor:'pointer',
          letterSpacing:'.04em', whiteSpace:'nowrap',
        }}>🇬 Sign in →</button>
        <button onClick={dismiss} title="Hide this for now" style={{
          background:'transparent', color:'#9a8d7a', border:'none',
          padding:'4px 6px', fontSize:18, fontWeight:700, cursor:'pointer',
          lineHeight:1, fontFamily:'Nunito, sans-serif',
        }}>×</button>
      </div>
    </section>
  );
}

// Shown briefly while a magic-link RPC is in-flight — see docs/bugs/
// 2026-05-03-magic-link-onboarding-flash.md. Replaces what would
// otherwise be a flash of OnboardingScreen with a "send magic link"
// form, which made users think their link didn't work.
function SigningInScreen({ theme }) {
  return (
    <div style={{
      minHeight:'100vh', background: theme.bg,
      fontFamily:'Nunito, sans-serif',
      display:'flex', flexDirection:'column',
      alignItems:'center', justifyContent:'center',
      gap: 18, padding: 24, textAlign:'center',
    }}>
      <div style={{
        width: 48, height: 48, borderRadius: '50%',
        border: `4px solid ${theme.chip}`,
        borderTopColor: '#1b1230',
        animation: 'spin 0.9s linear infinite',
      }}/>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      <div style={{
        fontFamily: 'Fraunces, serif', fontWeight: 800,
        fontSize: 20, color: '#1b1230',
      }}>Signing you in…</div>
      <div style={{ color: '#6b5c80', fontSize: 14 }}>
        Linking your email to this device.
      </div>
    </div>
  );
}

function OnboardingScreen({ tweaks, updateTweak, level, setLevel, theme, onDone, magicLinkError }) {
  const cfg = window.SITE_CONFIG || {};
  const [name, setName] = useStateH(tweaks?.userName || '');
  const [avatarId, setAvatarId] = useStateH(tweaks?.avatar || 'fox');
  const [pickedLevel, setPickedLevel] = useStateH(level || 'Sprout');
  const [themeId, setThemeId] = useStateH(tweaks?.theme || 'sunny');
  const [lang, setLang] = useStateH(tweaks?.language || 'en');
  const [signingIn, setSigningIn] = useStateH(false);
  const [signInErr, setSignInErr] = useStateH(null);
  const [magicEmailOpen, setMagicEmailOpen] = useStateH(false);
  const [magicEmail, setMagicEmail] = useStateH('');
  const [magicSentTo, setMagicSentTo] = useStateH(null);

  const ready = name.trim().length > 0;

  const persistProfile = () => {
    updateTweak('userName', name.trim());
    updateTweak('avatar', avatarId);
    updateTweak('theme', themeId);
    updateTweak('language', lang);
    setLevel(pickedLevel);
  };

  const save = () => {
    if (!ready) return;
    persistProfile();
    onDone && onDone();
  };

  // Save profile fields FIRST so they survive the Google redirect, then
  // kick off OAuth. The redirect comes back to the same URL; index.html's
  // bootstrap useEffect picks up the auth callback and runs
  // linkCurrentSession to bind the email server-side. After bind the
  // tweaks are already there (because we wrote them above) and the
  // onboarding gate's `userName` check passes — kid drops directly into
  // pickup, no second walkthrough.
  const saveAndSignIn = async () => {
    if (!ready) return;
    persistProfile();
    setSigningIn(true); setSignInErr(null);
    try {
      if (!window.kidsync || !window.kidsync.signInWithGoogle) {
        throw new Error('Sign-in not available on this device — continue without it.');
      }
      const r = await window.kidsync.signInWithGoogle();
      if (!r || !r.redirected) throw new Error(r?.error || 'Sign-in failed');
      // Page redirects to Google; nothing else to do here.
    } catch (e) {
      setSignInErr(e.message || String(e));
      setSigningIn(false);
    }
  };

  // Magic-link path. We persist the profile so when the kid clicks the
  // link from their email and lands back on this URL, index.html's
  // boot consumes the magic token + binds email→client_id, and the
  // onboarding gate is already past (userName is set).
  //
  // Cross-device note: profile auto-upload via the [tweaks] useEffect
  // is async/fire-and-forget. If the kid clicks the email link on a
  // different device BEFORE Device A's auto-upload reaches cloud, the
  // fetchProfile on Device B finds an empty row → OnboardingScreen
  // re-fires. To close the race, we explicitly upload the form values
  // (NOT React state — closures here are stale right after persistProfile)
  // and await before sending the magic email. See
  // docs/bugs/2026-05-03-magic-link-onboarding-flash.md.
  const saveAndSendMagic = async () => {
    if (!ready) return;
    const cleaned = (magicEmail || '').trim().toLowerCase();
    if (!cleaned || cleaned.indexOf('@') < 1) {
      setSignInErr('Please type a valid email.');
      return;
    }
    persistProfile();
    setSigningIn(true); setSignInErr(null);
    try {
      if (!window.kidsync || !window.kidsync.requestMagicLink) {
        throw new Error('Email sign-in not available on this device.');
      }
      // Force-upload profile to cloud BEFORE sending the email, using the
      // form values directly (the React tweaks state from `tweaks` is
      // stale — persistProfile's setState hasn't flushed yet at this
      // microtask). Best-effort: if the upload fails we still send the
      // email so the kid isn't blocked, but we log the failure.
      if (window.kidsync.upsertKidProfile) {
        try {
          await window.kidsync.upsertKidProfile({
            userName: name.trim(),
            avatar: avatarId,
            theme: themeId,
            language: lang,
            level: pickedLevel,
            dailyGoal: tweaks?.dailyGoal || 21,
          });
        } catch (e) {
          console.warn('[saveAndSendMagic] profile pre-upload failed; cross-device click may need re-onboarding:', e);
        }
      }
      await window.kidsync.requestMagicLink(cleaned);
      setMagicSentTo(cleaned);
    } catch (e) {
      setSignInErr(e.message || String(e));
    } finally {
      setSigningIn(false);
    }
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

        {/* ── Strong sign-in recommendation ─────────────────────────────
            Without this, the streak + history live ONLY in this browser's
            cache. Cleared cache = lost progress. Sign in once and the
            kid's identity is anchored to a Gmail forever — moves across
            devices, survives any cache wipe, unlocks parent dashboard. */}
        <div style={{
          margin:'8px 0 18px', padding:'18px 18px 14px', borderRadius:16,
          background:'#fff9ef', border:`2px solid ${theme.border || '#1b1230'}`,
          boxShadow:'0 4px 0 rgba(27,18,48,0.10)',
        }}>
          <div style={{
            fontFamily:'Fraunces, serif', fontWeight:900, fontSize:19,
            color:'#1b1230', letterSpacing:'-0.015em', marginBottom:6,
          }}>
            ✨ Save your streak — sign in once
          </div>
          <div style={{fontSize:13, color:'#3a2a4a', lineHeight:1.5, marginBottom:12}}>
            Right now your reading lives <strong>only on this device</strong>. Sign in
            with Google (or have a parent help) and it follows you to every browser,
            every device. We never share your email — it's only used to remember you.
          </div>
          <button
            onClick={saveAndSignIn} disabled={!ready || signingIn}
            style={{
              width:'100%', background: (ready && !signingIn) ? '#1b1230' : '#e8dfd3',
              color: (ready && !signingIn) ? '#ffc83d' : '#9a8d7a',
              border:'none', borderRadius:14, padding:'14px',
              fontFamily:'Nunito, sans-serif', fontWeight:900, fontSize:15,
              cursor: (ready && !signingIn) ? 'pointer' : 'not-allowed',
              boxShadow: (ready && !signingIn) ? '0 4px 0 rgba(27,18,48,0.18)' : 'none',
              display:'flex', alignItems:'center', justifyContent:'center', gap:10,
            }}>
            <span style={{fontSize:18}}>🇬</span>
            {signingIn ? 'Redirecting…' : 'Sign in with Google · recommended'}
          </button>

          {/* Banner shown when the user clicked a magic link but the
              consume RPC rejected it (expired, already used, malformed).
              Without this hint, the user just sees the same "send magic
              link" UI and assumes the link silently failed. */}
          {magicLinkError && !magicSentTo && (
            <div style={{
              marginTop: 10, padding: '10px 12px', borderRadius: 12,
              background: '#fff0e8', border: '1.5px solid #f4c4ad',
              color: '#c14e2a', fontSize: 13, fontWeight: 700,
            }}>
              ⚠ That magic link couldn't be used: {magicLinkError}
              <div style={{ fontWeight: 500, marginTop: 4, color: '#7a3a18' }}>
                Send a fresh one below — links expire after 10 minutes.
              </div>
            </div>
          )}

          {/* Magic-link alternative for kids/parents without Google. Tap
              "or use email" to expand a small inline form. After "Send
              link" the kid sees a confirmation + can close the tab and
              continue from the email's link on any device. */}
          {!magicEmailOpen && !magicSentTo && (
            <button onClick={() => setMagicEmailOpen(true)} style={{
              width:'100%', marginTop:8,
              background:'transparent', color:'#3a2a4a',
              border:'1.5px solid #e8dfd3', borderRadius:14, padding:'10px',
              fontFamily:'Nunito, sans-serif', fontWeight:700, fontSize:13,
              cursor:'pointer',
            }}>📧 or use email instead (no Google account)</button>
          )}
          {magicEmailOpen && !magicSentTo && (
            <div style={{marginTop:8}}>
              <input
                type="email" inputMode="email" autoComplete="email"
                placeholder="you@example.com"
                value={magicEmail}
                onChange={e => setMagicEmail(e.target.value)}
                style={{
                  width:'100%', boxSizing:'border-box',
                  fontFamily:'Nunito, sans-serif', fontWeight:700, fontSize:14,
                  padding:'10px 12px', borderRadius:12, border:'2px solid #1b1230',
                  background:'#fff', color:'#1b1230', outline:'none',
                }}
              />
              <button onClick={saveAndSendMagic} disabled={!ready || signingIn || !magicEmail.includes('@')} style={{
                width:'100%', marginTop:8,
                background: (ready && magicEmail.includes('@') && !signingIn) ? '#1b1230' : '#e8dfd3',
                color: (ready && magicEmail.includes('@') && !signingIn) ? '#ffc83d' : '#9a8d7a',
                border:'none', borderRadius:12, padding:'10px',
                fontFamily:'Nunito, sans-serif', fontWeight:900, fontSize:14,
                cursor: (ready && magicEmail.includes('@') && !signingIn) ? 'pointer' : 'not-allowed',
              }}>
                {signingIn ? 'Sending…' : '📧 Send me a magic link'}
              </button>
            </div>
          )}
          {magicSentTo && (
            <div style={{marginTop:10, padding:'10px 12px', borderRadius:12, background:'#e0f6f3', border:'1.5px solid #17b3a6'}}>
              <div style={{display:'flex', alignItems:'center', gap:6, color:'#0e8d82', fontWeight:800, fontSize:13}}>
                <span>✓</span> Sent to {magicSentTo}
              </div>
              <div style={{fontSize:12, color:'#3a2a4a', marginTop:4, lineHeight:1.4}}>
                Open your email and tap the link. (Check spam if it doesn't appear in a minute.) Expires in 30 minutes.
              </div>
            </div>
          )}
          {signInErr && (
            <div style={{marginTop:8, fontSize:12, color:'#b22525'}}>{signInErr}</div>
          )}
        </div>

        {/* "Skip — local only" — small text link, intentionally less
            visually heavy than the primary sign-in CTA. We don't lock
            the kid out; we just nudge hard. */}
        <button
          onClick={save} disabled={!ready}
          style={{
            width:'100%', background:'transparent',
            color: ready ? '#6b5c80' : '#c9bfae',
            border:'1.5px dashed #c9b99a', borderRadius:14, padding:'12px',
            fontFamily:'Nunito, sans-serif', fontWeight:700, fontSize:13,
            cursor: ready ? 'pointer' : 'not-allowed',
          }}>
          {ready ? 'Skip for now — save on this device only' : 'Type your name to continue'}
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
      {story.category}
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

function HomePage({ onOpen, onOpenArchive, onOpenSearch, onResume, level, setLevel, cat, setCat, progress, setProgress, theme, heroVariant, tweaks, updateTweak, onOpenUserPanel, archiveDay, magicConsuming, magicLinkError }) {
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

  // Publish feedback context — same pattern as ArticlePage. Tells the
  // 💬 modal which view + filters the user is on so the GH issue is
  // page-scoped.
  useEffectH(() => {
    window.__feedbackContext = {
      view: 'home',
      level,
      category: cat || 'All',
      language: (tweaks && tweaks.language) || 'en',
      archive_date: typeof archiveDay === 'string' ? archiveDay : null,
    };
    return () => { window.__feedbackContext = null; };
  }, [level, cat, archiveDay, tweaks && tweaks.language]);

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
  // pickFlowOpen drives the opt-in PickFlow ritual (kid clicks "Choose
  // your own 3" → flips this to true → gate below renders the flow).
  // No longer auto-firing on every visit — defaultPicks is the new default.
  const [pickFlowOpen, setPickFlowOpen] = useStateH(false);
  const todayKeyLocal = (new Date()).toDateString();
  // Lock the kid's pick for the local calendar day. The slot-positional
  // IDs (`2026-04-26-news-2`) plus the dayKey + "all ids still in pool"
  // checks are sufficient to invalidate when the day rolls over OR when
  // the kid switched level/language. Earlier we also kept a bundleStamp
  // (freshest mined_at) and invalidated on mined_at drift — but every
  // republish nudged mined_at and silently forced re-picks across same-
  // day reloads, so the kid kept landing on the pickup screen. Removed.
  const picksLocked = !isArchive
    && picksLock.dayKey === todayKeyLocal
    && picksLock.ids.length === 3
    && picksLock.ids.every(id => poolIds.has(id));
  const lockPicks = (ids) => {
    setPicksLock({ dayKey: todayKeyLocal, ids });
    if (window.kidsync && typeof window.kidsync.upsertPicks === 'function') {
      window.kidsync.upsertPicks(todayKeyLocal, ids);
    }
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };
  const resetPicks = () => {
    setPicksLock({ dayKey: null, ids: [] });
    if (window.kidsync && typeof window.kidsync.upsertPicks === 'function') {
      // Mirror the reset to cloud so a fresh device doesn't see stale picks.
      window.kidsync.upsertPicks(null, []);
    }
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
    // Swap is a view-only change: progress.articleProgress is keyed by
    // article id, so the outgoing article's % naturally hides (it's no
    // longer in daily3) and reappears unchanged if the kid swaps back.
    // No setProgress mutation here — minutesToday + readToday continue
    // to reflect what the kid actually did, regardless of which slots
    // are currently shown.
    if (picksLocked) {
      setPicksLock(L => {
        const newIds = L.ids.map((id, i) => i === idx ? newId : id);
        if (window.kidsync && typeof window.kidsync.upsertPicks === 'function') {
          window.kidsync.upsertPicks(L.dayKey || todayKeyLocal, newIds);
        }
        return { ...L, ids: newIds };
      });
    } else {
      const next = [...activePicks]; next[idx] = newId; setDailyPicks(next);
    }
  };
  const daily3 = useMemoH(() => activePicks.map(id => displayPool.find(a => a.id === id)).filter(Boolean), [activePicks, displayPool]);
  const [swapOpen, setSwapOpen] = useStateH(null); // index being swapped

  const byCat = useMemoH(() => {
    const m = {};
    CATEGORIES.forEach(c => { m[c.label] = ARTICLES.filter(a => a.category === c.label); });
    return m;
  }, []);

  // ── Magic-link consumption gate ────────────────────────────────────
  // When the URL carried ?magic=<token>, App's bootstrap useEffect is
  // calling consumeMagicLink in the background. Without this gate, the
  // OnboardingScreen below would briefly render a "send magic link" form
  // while the RPC is in-flight — users see that, think the link didn't
  // work, and re-submit. See docs/bugs/2026-05-03-magic-link-onboarding-flash.md.
  if (magicConsuming) {
    return <SigningInScreen theme={theme} />;
  }

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
        magicLinkError={magicLinkError}
      />
    );
  }

  // ── Pick-3 gate ────────────────────────────────────────────────────
  // OPT-IN ONLY. Previously this gate fired on every refresh whenever
  // picks weren't locked, forcing the kid through a 3-of-9 selection
  // ritual every visit — confusing for daily users. New behavior:
  // home renders straight away with the curator's defaultPicks (one
  // from each category). The kid can swap individual picks via the
  // existing per-card swap button, or trigger the full 3-of-9 flow by
  // clicking "Choose your own 3" (which calls resetPicks() + sets
  // pickFlowOpen so this gate fires on the next render).
  if (pickFlowOpen && !isArchive && displayPool.length >= 3 && !isZh) {
    const dateLabel = new Date().toLocaleDateString('en-US',
      { weekday:'long', month:'short', day:'numeric' });
    const pickPool = displayPool.slice(0, 9);
    return (
      <PickFlow
        pool={pickPool}
        onLock={(ids) => { lockPicks(ids); setPickFlowOpen(false); }}
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
      <Header level={level} setLevel={setLevel} theme={theme} tweaks={tweaks} onOpenUserPanel={onOpenUserPanel} progress={progress} recentOpen={recentOpen} setRecentOpen={setRecentOpen} onOpenArticle={onOpen} onOpenArchive={onOpenArchive} onOpenSearch={onOpenSearch} />

      {/* ——————————— ANONYMOUS-USER SIGN-IN NUDGE ———————————
          Slim dismissible banner above the daily ritual. Only renders
          when (a) we're showing today (not archive), (b) the kid has
          already done first-launch onboarding (so this isn't piled on
          top of the OnboardingScreen sign-in prompt), (c) the kid
          hasn't dismissed it, and (d) they're not already Gmail-linked.
          One tap opens the user panel where IdentityExpander is
          already default-expanded with the same Google CTA. */}
      {!isArchive && (
        <SignInNudge tweaks={tweaks} onOpenUserPanel={onOpenUserPanel}/>
      )}

      {/* ——————————— TODAY'S PROGRESS BANNER (only when picks are locked) ——————————— */}
      {/* Chinese mode is summary-only — pick-3 ritual is skipped, so
          there's nothing for the sticky progress banner to track. */}
      {!isArchive && picksLocked && !isZh && (
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

      {/* ——————————— TODAY'S PICK BANNER (hidden in archive + zh) ———————————
          Single column, full-width. Title row on top, 3 cards stacked
          full-width below. Greeting moved to the sticky TodayBanner.
          Chinese mode is summary-only audit (no pick-3 ritual, no
          "open the article reader" interaction), so the whole banner
          is hidden — kid/parent in zh mode just browses category cards
          below. The pickup-route gate + sticky-TodayBanner check `!isZh`
          for the same reason; this third surface was missed. */}
      {!isArchive && !isZh && (
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
              {/* "Choose your own 3" is always available, locked or not.
                  When clicked, clears any current lock and opens PickFlow. */}
              <button onClick={() => { resetPicks(); setPickFlowOpen(true); }} style={{
                background:'transparent', border:'1.5px solid #f0e8d8',
                borderRadius:999, padding:'7px 14px', cursor:'pointer',
                fontSize:12, fontWeight:800, color:'#1b1230',
                fontFamily:'Nunito, sans-serif', letterSpacing:'.02em',
              }} title="Open the 3-of-9 picker">🎯 Choose your own 3</button>
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
                        // 6-line clamp — card_summary is server-side-bounded
                        // to ≤50 words, which fits in 5-6 lines at this
                        // size. 4 lines was cutting trailing punctuation.
                        display:'-webkit-box', WebkitBoxOrient:'vertical', WebkitLineClamp:6, overflow:'hidden',
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
                      {/* Swap rules per user direction:
                          · Science / Fun: hide swap once done — the slot
                            is "spent" and re-swapping would feel like
                            taking back credit.
                          · News: swap always allowed — there's usually
                            still appetite for a second news read of
                            the day. */}
                      {canSwap && (a.category === 'News' || !progress.readToday.includes(a.id)) && (
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
            <ArticleCard article={filtered[0]} onOpen={isZh ? null : ()=>onOpen(filtered[0].id)} read={_isDoneArticle(progress, filtered[0].id)} pct={_articlePct((progress.articleProgress||{})[filtered[0].id])} variant="feature" />
            <div style={{display:'grid', gridTemplateColumns:'1fr 1fr', gap:20}}>
              <ArticleCard article={filtered[1]} onOpen={isZh ? null : ()=>onOpen(filtered[1].id)} read={_isDoneArticle(progress, filtered[1].id)} pct={_articlePct((progress.articleProgress||{})[filtered[1].id])} variant="normal" />
              <ArticleCard article={filtered[2]} onOpen={isZh ? null : ()=>onOpen(filtered[2].id)} read={_isDoneArticle(progress, filtered[2].id)} pct={_articlePct((progress.articleProgress||{})[filtered[2].id])} variant="normal" />
            </div>
          </div>
        ) : (
          <div style={{
            display:'grid',
            gridTemplateColumns:'repeat(auto-fill, minmax(280px, 1fr))',
            gap:20,
          }}>
            {filtered.map((a, i) => (
              <ArticleCard key={a.id} article={a} onOpen={isZh ? null : ()=>onOpen(a.id)} read={_isDoneArticle(progress, a.id)} pct={_articlePct((progress.articleProgress||{})[a.id])} variant={i===0 && !isArchive ? 'feature' : 'normal'} />
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
function Header({ level, setLevel, theme, tweaks, onOpenUserPanel, progress, recentOpen, setRecentOpen, onOpenArticle, onOpenArchive, onOpenSearch }) {
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

        {/* Search button — opens dedicated search page. */}
        <button onClick={() => { if (typeof onOpenSearch === 'function') onOpenSearch(); }} style={{
          background:'#1b1230', color:'#fff', border:'none',
          width:42, height:42, borderRadius:21, cursor:'pointer',
          display:'flex', alignItems:'center', justifyContent:'center',
          fontSize:18,
        }} title="Search archives">🔍</button>

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
            <RecentReadsPopover
              onClose={()=>setRecentOpen(false)}
              onOpenArticle={(id)=>{setRecentOpen(false); onOpenArticle(id);}}
              onResumeItem={(item)=>{
                setRecentOpen(false);
                if (typeof onResume === 'function') onResume(item);
                else if (typeof onOpenArticle === 'function') onOpenArticle(item.id);
              }}
              // Source: lifetime readHistory (survives midnight rollovers).
              // Falls back to readToday for users whose saved state predates
              // the readHistory field.
              readIds={
                (progress && Array.isArray(progress.readHistory) && progress.readHistory.length)
                  ? progress.readHistory.map(e => (typeof e === 'string' ? e : e?.id)).filter(Boolean)
                  : ((progress && progress.readToday) || [])
              }
              // In-progress = articleProgress entries with steps.length > 0
              // and < 4. Sort newest first; the snapshot fields rendered by
              // the popover come from articleProgress directly so we don't
              // need ARTICLES to be on the right day.
              inProgress={
                Object.entries((progress && progress.articleProgress) || {})
                  .filter(([id, v]) => v && Array.isArray(v.steps) && v.steps.length > 0 && v.steps.length < 4)
                  .map(([id, v]) => ({
                    id,
                    title: v.title || id,
                    category: v.category || 'News',
                    level: v.level || 'Tree',
                    imageURL: v.imageURL || '',
                    readMins: v.readMins || 7,
                    archiveDate: v.archiveDate || (id.match(/^(\d{4}-\d{2}-\d{2})/)?.[1] || null),
                    percent: Math.round((v.steps.length / 4) * 100),
                    lastTouchedAt: v.lastTouchedAt || '',
                  }))
                  .sort((a, b) => (b.lastTouchedAt || '').localeCompare(a.lastTouchedAt || ''))
                  .slice(0, 10)
              }
              // Snapshot fallback for past-day reads — popover finds the
              // article metadata here when ARTICLES (currently-loaded
              // bundle) doesn't contain the id.
              articleProgress={(progress && progress.articleProgress) || {}}
            />
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

// ——————————— SEARCH PAGE ———————————
// Full-page (Google-style) full-text search across all archived
// articles. Hits the archive-search edge function which queries
// redesign_search_index (tsvector + GIN). Results are date-DESC +
// ts_rank-DESC. Routed via App's route.page === 'search'.
//
// Image URLs in the search index are stored as relative paths
// like "/article_images/article_xxx.webp". For TODAY those resolve
// at the site root; for past dates the file lives under Supabase
// storage at <ARCHIVE_BASE>/<published_date>/article_images/...
// We always go through storage here because rows only land in the
// search index AFTER pack_and_upload runs (so the file is on
// storage by the time it's searchable, regardless of date).
function searchResultImageUrl(r) {
  const raw = r && r.image_url;
  if (!raw) return '';
  if (raw.startsWith('http')) return raw;
  const rel = raw.replace(/^\//, '');
  const base = (typeof window !== 'undefined' && window.ARCHIVE_BASE) || '';
  // Without a base+date, we can't be sure the file is at the site
  // root (a row indexed for a past date won't exist there). Return
  // empty and let the placeholder render rather than ship a broken
  // image request.
  if (!base || !r.published_date) return '';
  return `${base}/${r.published_date}/${rel}`;
}

function SearchPage({ onBack, onOpenResult, level, language }) {
  const [q, setQ] = useStateH("");
  const [results, setResults] = useStateH([]);
  const [loading, setLoading] = useStateH(false);
  const [hasSearched, setHasSearched] = useStateH(false);

  useEffectH(() => {
    window.__feedbackContext = {
      view: 'search',
      query: q,
      level,
      language: language || 'en',
      result_count: results.length,
    };
    return () => { window.__feedbackContext = null; };
  }, [q, level, language, results.length]);

  // Map the user's current preference into the search-index level
  // value. Search ONLY returns rows for the user's chosen mode —
  // no cross-language or cross-level surprises.
  const indexLevel = (language === 'zh') ? 'zh'
                    : (level === 'Sprout') ? 'easy'
                    : 'middle';

  // Debounced search — 300ms idle, no submit button needed.
  useEffectH(() => {
    const term = q.trim();
    if (!term) { setResults([]); setHasSearched(false); return; }
    let cancelled = false;
    const t = setTimeout(async () => {
      setLoading(true);
      const r = await window.archiveSearch(term, { limit: 20, level: indexLevel });
      if (cancelled) return;
      setLoading(false);
      setHasSearched(true);
      setResults((r && Array.isArray(r.results)) ? r.results : []);
    }, 300);
    return () => { cancelled = true; clearTimeout(t); };
  }, [q, indexLevel]);

  return (
    <div style={{minHeight:'100vh', background:'#f7f5f0', fontFamily:'Nunito, sans-serif'}}>
      {/* Slim header strip with back + search box */}
      <div style={{
        background:'#fff', borderBottom:'1px solid #eee',
        position:'sticky', top:0, zIndex:30,
      }}>
        <div style={{
          maxWidth:780, margin:'0 auto', padding:'12px 20px',
          display:'flex', alignItems:'center', gap:12,
        }}>
          <button onClick={onBack} style={{
            background:'transparent', border:'none', cursor:'pointer',
            fontSize:22, color:'#1b1230', padding:'4px 6px', lineHeight:1,
          }} title="Back">←</button>
          <div style={{
            fontFamily:'Fraunces, serif', fontWeight:900, fontSize:20,
            color:'#1b1230', marginRight:6,
          }}>Search</div>
          <input
            autoFocus
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search all past articles…"
            aria-label="Search past articles"
            style={{
              flex:1, padding:'10px 14px', border:'1.5px solid #ddd',
              borderRadius:24, fontSize:15, outline:'none',
              fontFamily:'Nunito, sans-serif', background:'#fafafa',
            }}
          />
        </div>
        <div style={{
          maxWidth:780, margin:'0 auto', padding:'0 20px 10px',
          fontSize:11, color:'#888', letterSpacing:'.04em',
          textTransform:'uppercase',
        }}>
          Searching <strong>
            {indexLevel === 'zh' ? '中文' : indexLevel === 'easy' ? 'Sprout' : 'Tree'}
          </strong> articles · change level in your profile to switch
        </div>
      </div>

      {/* Results list */}
      <div style={{maxWidth:780, margin:'0 auto', padding:'18px 20px 60px'}}>
        {!q.trim() && !loading && (
          <div style={{padding:'30px 4px', fontSize:14, color:'#888', textAlign:'center'}}>
            Type a word or phrase to search every past article.<br/>
            Tip: double quotes for exact phrase — <code>"climate change"</code>.
          </div>
        )}

        {loading && <div style={{padding:'18px 4px', fontSize:14, color:'#777'}}>Searching…</div>}

        {!loading && hasSearched && results.length === 0 && (
          <div style={{padding:'24px 4px', fontSize:14, color:'#777', textAlign:'center'}}>
            No matches for <strong>"{q}"</strong>. Try fewer words, or a synonym.
          </div>
        )}

        {!loading && hasSearched && results.length > 0 && (
          <div style={{fontSize:12, color:'#888', marginBottom:12, paddingLeft:4}}>
            About {results.length} result{results.length === 1 ? '' : 's'}
          </div>
        )}

        {results.map(r => {
          const imgSrc = searchResultImageUrl(r);
          return (
            <button
              key={`${r.story_id}-${r.level}`}
              onClick={() => onOpenResult(r)}
              style={{
                display:'flex', gap:14, padding:'14px', width:'100%',
                background:'#fff', border:'1px solid #eee', borderRadius:12,
                marginBottom:10, cursor:'pointer', textAlign:'left',
                alignItems:'flex-start', boxShadow:'0 1px 2px rgba(0,0,0,0.04)',
              }}
            >
              {imgSrc ? (
                <img
                  src={imgSrc}
                  alt=""
                  loading="lazy"
                  onError={(e) => { e.currentTarget.style.display = 'none'; }}
                  style={{
                    width:96, height:72, objectFit:'cover', borderRadius:8,
                    background:'#e8e4dc', flexShrink:0,
                  }}
                />
              ) : (
                <div style={{
                  width:96, height:72, borderRadius:8, background:'#e8e4dc',
                  flexShrink:0, display:'flex', alignItems:'center',
                  justifyContent:'center', color:'#aaa', fontSize:12,
                }}>—</div>
              )}
              <div style={{flex:1, minWidth:0}}>
                <div style={{fontSize:11, color:'#888', marginBottom:4,
                              textTransform:'uppercase', letterSpacing:'.04em'}}>
                  {r.published_date} · {r.category} · {r.level === 'zh' ? '中文' : (r.level === 'easy' ? 'Sprout' : 'Tree')}
                  {r.source_name ? <span> · {r.source_name}</span> : null}
                </div>
                <div style={{fontFamily:'Fraunces, serif', fontWeight:800,
                              fontSize:17, lineHeight:1.25, marginBottom:6,
                              color:'#1b1230'}}>
                  {r.title}
                </div>
                <div
                  style={{fontSize:13, color:'#555', lineHeight:1.45,
                          overflow:'hidden', display:'-webkit-box',
                          WebkitLineClamp:3, WebkitBoxOrient:'vertical'}}
                  dangerouslySetInnerHTML={{ __html: r.snippet || '' }}
                />
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
window.SearchPage = SearchPage;


// ——————————— FEEDBACK BUTTON + MODAL ———————————
// Floating bottom-right 💬 button that opens a modal where the user
// can submit a bug / suggestion / content note. Posts to the
// submit-feedback edge function via window.submitFeedback().
// Always rendered above route content (zIndex high). Hidden during
// onboarding via the wrapper in App.
function FeedbackButton() {
  const [open, setOpen] = useStateH(false);
  return (
    <>
      <button
        onClick={() => setOpen(true)}
        title="Send feedback"
        aria-label="Send feedback"
        style={{
          position:'fixed', right:18, bottom:18, zIndex:90,
          width:54, height:54, borderRadius:27,
          background:'#1b1230', color:'#fff', border:'none',
          fontSize:22, cursor:'pointer',
          boxShadow:'0 4px 16px rgba(0,0,0,0.25)',
        }}
      >💬</button>
      {open && <FeedbackModal onClose={() => setOpen(false)}/>}
    </>
  );
}
window.FeedbackButton = FeedbackButton;

function FeedbackModal({ onClose }) {
  const [category, setCategory] = useStateH('bug');
  const [message, setMessage] = useStateH('');
  const [sending, setSending] = useStateH(false);
  const [result, setResult] = useStateH(null);   // null | 'ok' | error string

  const send = async () => {
    if (sending) return;
    if (message.trim().length < 5) {
      setResult('请至少写 5 个字让我们能看明白~');
      return;
    }
    setSending(true);
    setResult(null);
    const r = await window.submitFeedback({ category, message: message.trim() });
    setSending(false);
    if (r && r.ok) {
      setResult('ok');
      setTimeout(onClose, 1200);
    } else {
      setResult((r && r.error) || 'Something went wrong — please try again.');
    }
  };

  const cats = [
    { v:'bug',        label:'🐞 Bug — 哪里坏了' },
    { v:'suggestion', label:'💡 Suggestion — 想加什么' },
    { v:'content',    label:'📰 Content — 文章/选题反馈' },
    { v:'other',      label:'💬 Other — 其它' },
  ];

  return (
    <>
      <div onClick={onClose} style={{
        position:'fixed', inset:0, zIndex:120, background:'rgba(0,0,0,0.32)',
      }}/>
      <div role="dialog" aria-label="Send feedback" style={{
        position:'fixed', zIndex:121,
        left:'50%', top:'50%', transform:'translate(-50%,-50%)',
        width:'min(460px, 92vw)', background:'#fff', borderRadius:16,
        padding:20, boxShadow:'0 20px 60px rgba(0,0,0,0.30)',
        fontFamily:'Nunito, sans-serif',
      }}>
        <div style={{display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:12}}>
          <div style={{fontFamily:'Fraunces, serif', fontWeight:900, fontSize:20, color:'#1b1230'}}>
            💬 Send us feedback
          </div>
          <button onClick={onClose} style={{
            background:'transparent', border:'none', fontSize:22, cursor:'pointer', color:'#888',
          }} aria-label="Close">×</button>
        </div>

        <div style={{fontSize:13, color:'#555', marginBottom:14, lineHeight:1.45}}>
          Your message goes straight to the team. Anonymous — no sign-in needed.
        </div>

        <div style={{marginBottom:12}}>
          <div style={{fontSize:11, fontWeight:800, color:'#6b5c80', letterSpacing:'.06em', textTransform:'uppercase', marginBottom:6}}>Type</div>
          <div style={{display:'flex', flexWrap:'wrap', gap:6}}>
            {cats.map(c => (
              <button
                key={c.v}
                onClick={() => setCategory(c.v)}
                style={{
                  padding:'8px 12px', border: category===c.v ? '2px solid #1b1230' : '1.5px solid #ddd',
                  borderRadius:18, background: category===c.v ? '#fff9ef' : '#fff',
                  fontSize:12, fontWeight:700, cursor:'pointer', color:'#1b1230',
                }}
              >{c.label}</button>
            ))}
          </div>
        </div>

        <div style={{marginBottom:12}}>
          <div style={{fontSize:11, fontWeight:800, color:'#6b5c80', letterSpacing:'.06em', textTransform:'uppercase', marginBottom:6}}>Message</div>
          <textarea
            autoFocus
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            maxLength={4000}
            placeholder={category === 'bug'
              ? "What happened? What did you expect? Steps to reproduce help a lot."
              : "Tell us what's on your mind…"}
            style={{
              width:'100%', minHeight:120, padding:'10px 12px',
              border:'1.5px solid #ddd', borderRadius:10, fontSize:14,
              outline:'none', resize:'vertical', fontFamily:'inherit',
              boxSizing:'border-box', color:'#1b1230', background:'#fafafa',
            }}
          />
          <div style={{fontSize:11, color:'#aaa', marginTop:4}}>
            {message.length} / 4000
          </div>
        </div>

        {result && result !== 'ok' && (
          <div style={{padding:'8px 10px', background:'#fff1f1', color:'#a02b2b',
                        border:'1px solid #f5c6c6', borderRadius:8, fontSize:12,
                        marginBottom:10}}>
            {result}
          </div>
        )}
        {result === 'ok' && (
          <div style={{padding:'8px 10px', background:'#ecfaf0', color:'#197a3b',
                        border:'1px solid #b6e3c5', borderRadius:8, fontSize:13,
                        marginBottom:10}}>
            ✓ Sent! Thank you 🙏
          </div>
        )}

        <div style={{display:'flex', justifyContent:'flex-end', gap:8}}>
          <button onClick={onClose} style={{
            background:'transparent', border:'1px solid #ddd', borderRadius:8,
            padding:'9px 16px', cursor:'pointer', fontSize:13, color:'#444',
          }}>Cancel</button>
          <button
            onClick={send}
            disabled={sending}
            style={{
              background: sending ? '#888' : '#1b1230', color:'#fff',
              border:'none', borderRadius:8, padding:'9px 18px',
              cursor: sending ? 'wait' : 'pointer', fontSize:13, fontWeight:800,
            }}
          >{sending ? 'Sending…' : 'Send'}</button>
        </div>
      </div>
    </>
  );
}
window.FeedbackModal = FeedbackModal;


function RecentReadsPopover({ onClose, onOpenArticle, onResumeItem, readIds, inProgress, articleProgress }) {
  // Take most recent 15 articles the user has read (from readIds, in order).
  // Source order:
  //   1. Try ARTICLES.find — works for articles in the currently-loaded
  //      bundle (today's, or whatever archive day is active).
  //   2. Fall back to the articleProgress snapshot — articles read on a
  //      different day still render their title/category/image because
  //      we stash those fields on the first step bump (see article.jsx).
  // Without the fallback, past-day completed reads silently disappeared
  // from the popover whenever the user wasn't viewing that day's bundle.
  const recent = [];
  const seen = new Set();
  const apMap = articleProgress || {};
  for (let i = readIds.length - 1; i >= 0 && recent.length < 15; i--) {
    const id = readIds[i];
    if (seen.has(id)) continue;
    const a = ARTICLES.find(x => x.id === id);
    if (a) {
      recent.push({ ...a, _resumable: false });
      seen.add(id);
      continue;
    }
    const snap = apMap[id];
    if (snap && typeof snap === 'object' && snap.title) {
      const m = id.match(/^(\d{4}-\d{2}-\d{2})/);
      recent.push({
        id,
        title: snap.title,
        category: snap.category || 'News',
        level: snap.level || '',
        readMins: snap.readMins || 7,
        archiveDate: snap.archiveDate || (m ? m[1] : null),
        _resumable: true,
      });
      seen.add(id);
    }
  }
  const continueItems = Array.isArray(inProgress) ? inProgress : [];
  return (
    <>
      <div onClick={onClose} style={{position:'fixed', inset:0, zIndex:40}}/>
      <div style={{
        position:'absolute', top:'calc(100% + 10px)', right:0, zIndex:50, width:340,
        background:'#fff', borderRadius:18, border:'2px solid #1b1230', boxShadow:'0 10px 0 rgba(27,18,48,0.15)',
        padding:14, maxHeight:440, overflow:'auto',
      }}>
        {/* ——— Continue reading (in-progress, last 10 days) ——— */}
        {continueItems.length > 0 && (
          <div style={{marginBottom:14}}>
            <div style={{display:'flex', justifyContent:'space-between', alignItems:'baseline', marginBottom:8}}>
              <div style={{fontFamily:'Fraunces, serif', fontWeight:900, fontSize:18, color:'#1b1230'}}>📖 Continue reading</div>
              <div style={{fontSize:11, color:'#9a8d7a', fontWeight:700}}>{continueItems.length}</div>
            </div>
            {continueItems.map(it => {
              const catColor = CATEGORIES.find(c => c.label === it.category)?.color || '#1b1230';
              return (
                <button key={it.id} onClick={()=>onResumeItem && onResumeItem(it)} style={{
                  display:'flex', gap:10, alignItems:'center', width:'100%', textAlign:'left',
                  background:'transparent', border:'none', padding:'8px 6px', borderRadius:10, cursor:'pointer',
                  borderBottom:'1px dashed #f0e8d8',
                }} onMouseEnter={e=>e.currentTarget.style.background='#fff9ef'} onMouseLeave={e=>e.currentTarget.style.background='transparent'}>
                  <div style={{width:8, height:32, borderRadius:4, background: catColor, flexShrink:0}}/>
                  <div style={{flex:1, minWidth:0}}>
                    <div style={{fontWeight:800, fontSize:13, color:'#1b1230', lineHeight:1.2, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap'}}>{it.title}</div>
                    <div style={{fontSize:11, color:'#6b5c80', fontWeight:600, marginTop:2}}>
                      {it.archiveDate || ''} · {it.percent}% done
                    </div>
                  </div>
                  <div style={{fontSize:11, color:catColor, fontWeight:800, flexShrink:0}}>Resume →</div>
                </button>
              );
            })}
          </div>
        )}
        <div style={{display:'flex', justifyContent:'space-between', alignItems:'baseline', marginBottom:10}}>
          <div style={{fontFamily:'Fraunces, serif', fontWeight:900, fontSize:18, color:'#1b1230'}}>🔥 Recently read</div>
          <div style={{fontSize:11, color:'#9a8d7a', fontWeight:700}}>Last {recent.length}</div>
        </div>
        {recent.length === 0 ? (
          <div style={{padding:'24px 8px', textAlign:'center', color:'#9a8d7a', fontSize:13}}>
            You haven't read anything yet today. Start your 21 min!
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
  // No `onOpen` callback → render-only mode (used in zh mode where the
  // detail page doesn't exist). Disable hover lift + click cursor so it
  // looks like a poster, not a tappable card.
  const clickable = typeof onOpen === 'function';
  return (
    <button
      onClick={clickable ? onOpen : undefined}
      disabled={!clickable}
      onMouseEnter={()=>clickable && setHover(true)}
      onMouseLeave={()=>setHover(false)}
      style={{
        background:'#fff',
        border:'2px solid #f0e8d8',
        borderRadius:22,
        padding:0,
        textAlign:'left',
        cursor: clickable ? 'pointer' : 'default',
        overflow:'hidden',
        position:'relative',
        transform: clickable && hover ? 'translateY(-4px) rotate(-0.3deg)' : 'translateY(0)',
        boxShadow: clickable && hover ? '0 10px 0 rgba(27,18,48,0.08)' : '0 4px 0 rgba(27,18,48,0.06)',
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
