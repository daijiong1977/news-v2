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

function HomePage({ onOpen, onOpenArchive, level, setLevel, cat, setCat, progress, theme, heroVariant, tweaks, onOpenUserPanel, archiveDay }) {
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
  const activePicks = (dailyPicks && dailyPicks.every(id => poolIds.has(id))) ? dailyPicks : defaultPicks;
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

      {/* ——————————— TODAY'S 15 HERO (hidden in archive) ——————————— */}
      {!isArchive && (
      <section style={{maxWidth:1180, margin:'0 auto', padding:'24px 28px 0'}}>
        <div style={{
          background:`linear-gradient(135deg, ${theme.hero1} 0%, ${theme.hero2} 100%)`,
          borderRadius:28,
          padding:'28px 32px',
          display:'grid',
          gridTemplateColumns: heroVariant === 'streak' ? '1fr 1fr' : '1.2fr 1fr',
          gap:28,
          alignItems:'center',
          position:'relative',
          overflow:'hidden',
          border:`2px solid ${theme.border}`,
        }}>
          {/* doodles */}
          <svg style={{position:'absolute', right:-20, bottom:-30, opacity:.18}} width="240" height="240" viewBox="0 0 100 100"><circle cx="50" cy="50" r="40" stroke="#1b1230" strokeWidth="2" fill="none"/><circle cx="50" cy="50" r="28" stroke="#1b1230" strokeWidth="2" fill="none" strokeDasharray="4 6"/></svg>

          <div style={{position:'relative'}}>
            <div style={{fontFamily:'Nunito, sans-serif', fontWeight:800, color: theme.heroTextAccent, fontSize:13, letterSpacing:'.1em', textTransform:'uppercase', marginBottom:6}}>
              Hi {tweaks.userName || 'friend'}! 👋 &nbsp;·&nbsp; {new Date().toLocaleDateString(undefined, {weekday:'long', month:'short', day:'numeric'})}
            </div>
            {heroVariant === 'streak' ? (
              <>
                <div style={{display:'inline-flex', alignItems:'center', gap:8, background:'#1b1230', color:'#ffc83d', padding:'6px 14px', borderRadius:999, fontFamily:'Nunito, sans-serif', fontWeight:900, fontSize:12, letterSpacing:'.1em', textTransform:'uppercase', marginBottom:12}}>
                  🔥 Streak mode
                </div>
                <h1 style={{fontFamily:'Fraunces, serif', fontWeight:900, fontSize:64, lineHeight:0.95, color:'#1b1230', margin:'0 0 10px', letterSpacing:'-0.03em'}}>
                  {streak} days<br/><span style={{color: theme.heroTextAccent, fontStyle:'italic'}}>on fire.</span>
                </h1>
                <p style={{fontSize:17, color:'#3a2a4a', margin:'0 0 14px', lineHeight:1.5, maxWidth:480}}>
                  {streak > 0
                    ? <>Read today to hit <b>day {streak+1}</b>. You've practiced <b>{minutesToday} of {goal} min</b>.</>
                    : <>Read your first story today to start a streak. Today's goal: <b>{goal} min</b>.</>
                  }
                </p>
                {/* mini calendar of last 7 days */}
                <div style={{display:'flex', gap:6, marginBottom:16}}>
                  {Array.from({length:7}).map((_,i)=>{
                    const done = i < 6;
                    return (
                      <div key={i} style={{width:36, height:44, borderRadius:10, background: done ? '#1b1230' : 'rgba(255,255,255,0.65)', color: done ? '#ffc83d' : '#9a8d7a', display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center', fontFamily:'Nunito, sans-serif', fontWeight:900, fontSize:11, border: i===6 ? `2px dashed ${theme.heroTextAccent}` : 'none'}}>
                        <div style={{fontSize:9, opacity:0.7}}>{['M','T','W','T','F','S','S'][i]}</div>
                        <div style={{fontSize:14}}>{done ? '✓' : '·'}</div>
                      </div>
                    );
                  })}
                </div>
              </>
            ) : (
              <>
                <h1 style={{fontFamily:'Fraunces, serif', fontWeight:900, fontSize:52, lineHeight:1.02, color:'#1b1230', margin:'0 0 12px', letterSpacing:'-0.02em'}}>
                  Today's <span style={{background: theme.accent, padding:'0 10px', borderRadius:12, display:'inline-block', transform:'rotate(-2deg)'}}>{goal} minutes</span>
                </h1>
                <p style={{fontSize:17, color:'#3a2a4a', margin:'0 0 18px', lineHeight:1.5, maxWidth:480}}>
                  Read 3 smart stories, learn new words, and win your streak. You've read <b>{readCount} of 3</b> today.
                </p>
              </>
            )}
            <div style={{display:'flex', gap:10, alignItems:'center', flexWrap:'wrap'}}>
              <BigButton bg="#1b1230" color="#fff" onClick={() => onOpen(daily3.find(a => !progress.readToday.includes(a.id))?.id || daily3[0].id)}>
                ▶ &nbsp;Start today's read
              </BigButton>
              <div style={{display:'flex', alignItems:'center', gap:8, padding:'10px 14px', background:'rgba(255,255,255,0.65)', borderRadius:14, fontWeight:700, fontSize:14}}>
                <span style={{fontSize:18}}>⏱️</span>
                <span>{minutesToday}/{goal} min today</span>
              </div>
            </div>
          </div>

          {/* Daily 3 stack — swappable picks */}
          <div style={{display:'flex', flexDirection:'column', gap:10, position:'relative'}}>
            <div style={{display:'flex', justifyContent:'space-between', alignItems:'baseline'}}>
              <div style={{fontFamily:'Fraunces, serif', fontWeight:800, fontSize:18, color:'#1b1230'}}>⚡ Today's {window.SITE_CONFIG?.storiesPerDay ?? 3} · {window.SITE_CONFIG?.perArticleMinutes ?? 7} min</div>
              <div style={{fontSize:11, color:'#6b5c80', fontWeight:700}}>Tap ⇆ to swap</div>
            </div>
            {daily3.map((a, i) => {
              const catColor = CATEGORIES.find(c => c.label === a.category)?.color || '#1b1230';
              const alternates = displayPool.filter(x => x.category === a.category && !activePicks.includes(x.id));
              const canSwap = alternates.length > 0;
              const isSwapping = swapOpen === i;
              return (
                <div key={a.id} style={{position:'relative'}}>
                  {isSwapping ? (
                    <div style={{
                      background:'#1b1230', borderRadius:16, padding:10,
                      boxShadow:'0 4px 0 rgba(27,18,48,0.15)',
                    }}>
                      <div style={{display:'flex', alignItems:'center', justifyContent:'space-between', padding:'2px 6px 8px'}}>
                        <div style={{fontSize:10, fontWeight:800, color:'#ffc83d', textTransform:'uppercase', letterSpacing:'.08em'}}>Pick a different {a.category} story</div>
                        <button onClick={()=>setSwapOpen(null)} style={{
                          background:'transparent', border:'none', color:'#ffc83d', fontWeight:900, cursor:'pointer', fontSize:16, padding:'0 4px',
                        }} title="Close">✕</button>
                      </div>
                      {alternates.map(alt => (
                        <button key={alt.id} onClick={()=>{swapPick(i, alt.id); setSwapOpen(null);}} style={{
                          display:'flex', alignItems:'center', gap:10, width:'100%', textAlign:'left',
                          background:'rgba(255,255,255,0.06)', color:'#fff',
                          border:'none', padding:8, borderRadius:10, cursor:'pointer',
                          marginBottom:6,
                        }} onMouseEnter={e=>e.currentTarget.style.background='rgba(255,255,255,0.14)'} onMouseLeave={e=>e.currentTarget.style.background='rgba(255,255,255,0.06)'}>
                          <div style={{width:44, height:44, borderRadius:10, flexShrink:0, background:`url(${alt.image}) center/cover, ${catColor}`}}/>
                          <div style={{flex:1, minWidth:0}}>
                            <div style={{fontWeight:800, fontSize:13, lineHeight:1.25}}>{alt.title}</div>
                            <div style={{fontSize:10, opacity:0.7, fontWeight:700, marginTop:3}}>{alt.readMins} min · {alt.tag}</div>
                          </div>
                        </button>
                      ))}
                      {alternates.length === 0 && (
                        <div style={{color:'#fff', opacity:0.6, fontSize:12, padding:10, textAlign:'center'}}>No other {a.category} stories today.</div>
                      )}
                    </div>
                  ) : (
                  <div style={{
                    background:'#fff', border:'2px solid #fff', borderRadius:16,
                    padding:'10px 12px', display:'flex', gap:12, alignItems:'center',
                    boxShadow:'0 2px 0 rgba(27,18,48,0.08)',
                  }}>
                    <div style={{
                      width:36, height:36, borderRadius:12, flexShrink:0,
                      background: catColor, color:'#fff', display:'flex', alignItems:'center', justifyContent:'center',
                      fontFamily:'Fraunces, serif', fontWeight:900, fontSize:18,
                    }}>{i+1}</div>
                    <div style={{
                      width:52, height:52, borderRadius:12, flexShrink:0,
                      background:`url(${a.image}) center/cover, ${catColor}`,
                      border:`2px solid ${catColor}`,
                    }}/>
                    <button onClick={()=>onOpen(a.id)} style={{
                      flex:1, minWidth:0, background:'transparent', border:'none', textAlign:'left', cursor:'pointer', padding:0,
                    }}>
                      <div style={{fontWeight:800, fontSize:14, color:'#1b1230', lineHeight:1.25, marginBottom:4, display:'-webkit-box', WebkitBoxOrient:'vertical', WebkitLineClamp:2, overflow:'hidden'}}>
                        {a.title}
                      </div>
                      <div style={{display:'flex', gap:6, alignItems:'center', fontSize:11, color:'#6b5c80'}}>
                        <CatChip cat={a.category} small/>
                        <span>· {a.readMins} min</span>
                      </div>
                    </button>
                    {(() => {
                      const p = _articlePct((progress.articleProgress||{})[a.id]);
                      const done = progress.readToday.includes(a.id);
                      if (done) return <span style={{fontSize:22, color:'#17b3a6'}}>✓</span>;
                      if (p > 0) return <span style={{fontSize:11, fontWeight:800, color:'#f4a24c', background:'#fff4e0', padding:'3px 8px', borderRadius:999, border:'1.5px solid #f4a24c'}}>{p}%</span>;
                      return null;
                    })()}
                    {canSwap && (
                      <button onClick={()=>setSwapOpen(i)} title={`Pick a different ${a.category} story`} style={{
                        background:'transparent', color:'#6b5c80',
                        border:'2px solid #f0e8d8', borderRadius:10,
                        width:32, height:32, cursor:'pointer', fontSize:14, fontWeight:900,
                        display:'flex', alignItems:'center', justifyContent:'center',
                      }}>⇆</button>
                    )}
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
        <div style={{display:'flex', alignItems:'center', gap:10}}>
          <OhYeLogo size={44}/>
          <div style={{lineHeight:1}}>
            <div style={{fontFamily:'Fraunces, serif', fontWeight:900, fontSize:22, color:'#1b1230', letterSpacing:'-0.01em'}}>
              News Oh<span style={{color:'#ff6b5b'}}>,</span>Ye<span style={{color:'#ff6b5b'}}>!</span>
            </div>
            <div style={{fontSize:11, color:'#9a8d7a', fontWeight:700, marginTop:2, letterSpacing:'.08em'}}>READ · THINK · LEARN</div>
          </div>
        </div>

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
