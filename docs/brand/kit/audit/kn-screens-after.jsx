// AFTER screens — kidsnews-v2 with the locked 21mins brand applied.
// Same layouts as BEFORE so reviewers can scan top-to-bottom diffs.
// Width: 1180.

// ─────────────────────────────────────────────────────────────
// AFTER · Kidsnews wordmark — sun-face + "kidsnews" + "21mins" badge
// This is the lockup that replaces "News Oh,Ye!" everywhere.
// ─────────────────────────────────────────────────────────────
function KidsnewsLockup({ size = 44, compact = false }) {
  return (
    <div style={{display:'flex', alignItems:'center', gap: compact ? 8 : 10}}>
      <MarkKids size={size}/>
      <div style={{lineHeight: 1.0}}>
        <div style={{
          fontFamily:'Fraunces, serif', fontWeight: 700,
          fontSize: compact ? 19 : 24, color: KN.ink, letterSpacing:'-0.02em',
        }}>
          kids<span style={{color: KN.coral}}>news</span>
        </div>
        <div style={{
          display:'flex', alignItems:'center', gap: 6, marginTop: 3,
        }}>
          <Mark21 size={11} ink={KN.muted} accent={KN.muted}/>
          <span style={{
            fontSize: 9.5, fontWeight: 800, color: KN.muted,
            letterSpacing:'.18em', textTransform:'uppercase',
          }}>a 21mins channel</span>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// AFTER · Header
// ─────────────────────────────────────────────────────────────
function HeaderAfter() {
  return (
    <header style={{background: KN.cream, borderBottom: `2px solid ${KN.border}`}}>
      <div style={{maxWidth: 1180, margin:'0 auto', padding:'14px 28px', display:'flex', alignItems:'center', gap:16}}>
        <KidsnewsLockup size={44}/>

        {/* Vertical-switcher pill — primes the brand for future siblings */}
        <button style={{
          background:'#fff', border:`1.5px dashed ${KN.border}`, borderRadius: 999,
          padding:'5px 11px 5px 8px', display:'inline-flex', alignItems:'center', gap:6,
          fontFamily:'Nunito, sans-serif', fontWeight: 700, fontSize: 11, color: KN.muted,
          marginLeft: 4,
        }}>
          <span style={{color: KN.ink, fontWeight: 900}}>kidsnews</span>
          <span style={{color: KN.muted}}>·</span>
          <span style={{opacity:.5}}>ai</span>
          <span style={{color: KN.muted}}>·</span>
          <span style={{opacity:.5}}>finance</span>
          <span style={{color: KN.muted}}>·</span>
          <span style={{opacity:.5}}>tech</span>
          <span style={{fontSize: 9, color: KN.muted, marginLeft: 2}}>▾</span>
        </button>

        <div style={{flex:1}}/>

        {/* Streak — same pattern, refined */}
        <div style={{display:'flex', alignItems:'center', gap:10, background: KN.ink, color:'#fff', padding:'6px 14px 6px 6px', borderRadius:999}}>
          <StreakRingBefore minutes={12} goal={21} streak={7}/>
          <div style={{lineHeight:1.1, textAlign:'left'}}>
            <div style={{fontSize:10, opacity:.7, fontWeight:700, letterSpacing:'.08em'}}>STREAK</div>
            <div style={{fontWeight:800, fontSize:13}}>7 days 🔥</div>
          </div>
          <span style={{fontSize:10, opacity:.7, marginLeft:4}}>▾</span>
        </div>

        {/* User pill — unchanged */}
        <div style={{
          display:'flex', alignItems:'center', gap:10, background:'#fff',
          border:`2px solid ${KN.ink}`, borderRadius:999,
          padding:'4px 14px 4px 4px', boxShadow:'0 3px 0 rgba(27,18,48,0.12)',
        }}>
          <div style={{width:36, height:36, borderRadius:999, background:'#e8e8e8', display:'flex', alignItems:'center', justifyContent:'center', fontSize:20, border:`2px solid ${KN.ink}`}}>🐼</div>
          <div style={{textAlign:'left', lineHeight:1.1}}>
            <div style={{fontWeight:900, fontSize:13, color: KN.ink}}>Mia</div>
            <div style={{fontSize:10, color:'#6b5c80', fontWeight:700}}>🇬🇧 EN · 🌳 Tree</div>
          </div>
          <span style={{fontSize:11, color: KN.muted, marginLeft:2}}>▾</span>
        </div>
      </div>
    </header>
  );
}

// ─────────────────────────────────────────────────────────────
// AFTER · Home hero
// ─────────────────────────────────────────────────────────────
function HomeHeroAfter() {
  const stories = [
    { title: 'Why scientists are racing to map the deep ocean before 2030', cat:'Science', mins: 7, img: 'audit-assets/article-1.webp' },
    { title: 'A small town in Iowa just got a giant data center next door', cat:'News',    mins: 7, img: 'audit-assets/article-2.webp' },
    { title: 'The world record for most yo-yos balanced on one finger',     cat:'Fun',     mins: 7, img: 'audit-assets/article-3.webp' },
  ];
  return (
    <section style={{padding:'24px 28px 0', maxWidth: 1180, margin:'0 auto'}}>
      <div style={{
        background: `linear-gradient(135deg, ${KN.goldHi} 0%, #ffc0a8 100%)`,
        borderRadius: 28, padding: '28px 32px',
        display:'grid', gridTemplateColumns:'1.2fr 1fr', gap: 28,
        alignItems:'center', position:'relative', overflow:'hidden',
        border:`2px solid #ffb98a`,
      }}>
        {/* sun rays as background flourish, picking up the kidsnews mark */}
        <svg style={{position:'absolute', right:-40, top:-40, opacity:.10, transform:'rotate(-12deg)'}} width="280" height="280" viewBox="0 0 200 200">
          {Array.from({length: 12}).map((_, i) => {
            const a = (i*30 - 90) * Math.PI / 180;
            const r1 = 80, r2 = 100;
            return <line key={i}
              x1={100 + Math.cos(a)*r1} y1={100 + Math.sin(a)*r1}
              x2={100 + Math.cos(a)*r2} y2={100 + Math.sin(a)*r2}
              stroke={KN.ink} strokeWidth="6" strokeLinecap="round"/>;
          })}
        </svg>

        <div style={{position:'relative'}}>
          <div style={{fontFamily:'Nunito, sans-serif', fontWeight:800, color:'#c14e2a', fontSize:13, letterSpacing:'.1em', textTransform:'uppercase', marginBottom:8}}>
            Hi Mia! 👋 · Saturday, Apr 25
          </div>
          <h1 style={{fontFamily:'Fraunces, serif', fontWeight:700, fontSize:54, lineHeight:0.98, color: KN.ink, margin:'0 0 6px', letterSpacing:'-0.025em'}}>
            Today's <span style={{background: KN.gold, padding:'0 12px', borderRadius:14, display:'inline-block', transform:'rotate(-2deg)'}}>21 minutes</span>
          </h1>
          <p style={{fontFamily:'Fraunces, serif', fontWeight:600, fontStyle:'italic', fontSize:22, color:'#c14e2a', margin:'0 0 14px', lineHeight:1.2, letterSpacing:'-0.01em'}}>
            Little daily, big magic.
          </p>
          <p style={{fontSize:16, color:'#3a2a4a', margin:'0 0 18px', lineHeight:1.55, maxWidth: 480}}>
            Three smart stories. Read, think, and earn your streak.<br/>
            You've finished <b>1 of 3</b> today — <b>9 minutes</b> to go.
          </p>
          <div style={{display:'flex', gap:10, alignItems:'center'}}>
            <button style={{
              background: KN.ink, color:'#fff', border:'none', borderRadius:16,
              padding:'14px 22px', fontWeight:800, fontSize:16,
              fontFamily:'Nunito, sans-serif', boxShadow:'0 5px 0 rgba(0,0,0,0.18)',
            }}>▶  Start today's read</button>
            <div style={{display:'flex', alignItems:'center', gap:8, padding:'10px 14px', background:'rgba(255,255,255,0.65)', borderRadius:14, fontWeight:700, fontSize:14}}>
              <span style={{fontSize:18}}>⏱️</span><span>12/21 min today</span>
            </div>
          </div>
        </div>

        <div style={{display:'flex', flexDirection:'column', gap:10, position:'relative'}}>
          <div style={{display:'flex', justifyContent:'space-between', alignItems:'baseline'}}>
            <div style={{fontFamily:'Fraunces, serif', fontWeight:700, fontSize:18, color: KN.ink}}>⚡ Today's 3 · 7 min each</div>
            <div style={{fontSize:11, color:'#6b5c80', fontWeight:700}}>Tap ⇆ to swap</div>
          </div>
          {stories.map((s, i) => {
            const cat = KN.cats[s.cat];
            const done = i === 0;
            return (
              <div key={i} style={{
                background:'#fff', border:'2px solid #fff', borderRadius:16, padding:'10px 12px',
                display:'flex', gap:12, alignItems:'center', boxShadow:'0 2px 0 rgba(27,18,48,0.08)',
                opacity: done ? 0.7 : 1,
              }}>
                <div style={{
                  width:36, height:36, borderRadius:12, flexShrink:0,
                  background: cat.color, color:'#fff', display:'flex', alignItems:'center', justifyContent:'center',
                  fontFamily:'Fraunces, serif', fontWeight:900, fontSize:18,
                }}>{i+1}</div>
                <div style={{
                  width:52, height:52, borderRadius:12, flexShrink:0,
                  background:`url(${s.img}) center/cover, ${cat.color}`,
                  border:`2px solid ${cat.color}`,
                }}/>
                <div style={{flex:1, minWidth:0}}>
                  <div style={{fontWeight:800, fontSize:14, color: KN.ink, lineHeight:1.25, marginBottom:4, display:'-webkit-box', WebkitBoxOrient:'vertical', WebkitLineClamp:2, overflow:'hidden'}}>
                    {s.title}
                  </div>
                  <div style={{display:'flex', gap:6, alignItems:'center', fontSize:11, color:'#6b5c80'}}>
                    <span style={{display:'inline-flex', alignItems:'center', gap:4, background: cat.bg, color: cat.color, padding:'2px 8px', borderRadius:999, fontWeight:800, fontSize:10}}>
                      <span>{cat.emoji}</span>{s.cat}
                    </span>
                    <span>· {s.mins} min</span>
                  </div>
                </div>
                {done && <span style={{fontSize:22, color:'#17b3a6'}}>✓</span>}
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}

// ─────────────────────────────────────────────────────────────
// AFTER · Article reader
// ─────────────────────────────────────────────────────────────
function ArticleReaderAfter() {
  const stages = [
    { id:'read', label:'Read & Words', emoji:'📖' },
    { id:'analyze', label:'Background', emoji:'🔍' },
    { id:'quiz', label:'Quiz', emoji:'🎯' },
    { id:'discuss', label:'Think', emoji:'💭' },
  ];
  const cat = KN.cats.Science;
  return (
    <>
      <div style={{background: KN.cream, borderBottom:`2px solid ${KN.border}`}}>
        <div style={{maxWidth:1180, margin:'0 auto', padding:'14px 28px', display:'flex', alignItems:'center', gap:14}}>
          <button style={{
            background:'#fff', border:`2px solid ${KN.border}`, borderRadius:14, padding:'8px 14px',
            fontWeight:800, fontSize:14, color: KN.ink,
          }}>← Back</button>
          <KidsnewsLockup size={32} compact/>
          <div style={{flex:1}}/>
          <div style={{display:'flex', alignItems:'center', gap:6}}>
            {stages.map((s, i) => (
              <React.Fragment key={s.id}>
                <button style={{
                  background: i === 0 ? cat.color : (i === 1 ? '#d4f3ef' : '#fff'),
                  color: i === 0 ? '#fff' : (i === 1 ? '#0e8d82' : '#6b5c80'),
                  border: `2px solid ${i === 0 ? cat.color : (i === 1 ? '#8fd6cd' : KN.border)}`,
                  borderRadius:999, padding:'6px 12px', fontWeight:800, fontSize:13,
                  fontFamily:'Nunito, sans-serif',
                }}>
                  <span style={{marginRight:5}}>{s.emoji}</span>{s.label}
                </button>
                {i < stages.length - 1 && <div style={{width:8, height:2, background: KN.border}}/>}
              </React.Fragment>
            ))}
          </div>
        </div>
      </div>
      <section style={{maxWidth:760, margin:'0 auto', padding:'32px 28px 60px'}}>
        <div style={{display:'inline-flex', alignItems:'center', gap:6, background: cat.bg, color: cat.color, padding:'5px 12px', borderRadius:999, fontWeight:800, fontSize:13, marginBottom:14}}>
          <span style={{fontSize:14}}>{cat.emoji}</span>Science
        </div>
        <h1 style={{fontFamily:'Fraunces, serif', fontWeight:700, fontSize:42, lineHeight:1.08, color: KN.ink, margin:'0 0 16px', letterSpacing:'-0.025em'}}>
          Why scientists are racing to map the deep ocean before 2030
        </h1>
        {/* New: time-budget pill, calmer than the bare "7 min" */}
        <div style={{display:'flex', gap:10, alignItems:'center', marginBottom: 24, flexWrap:'wrap'}}>
          <div style={{display:'inline-flex', alignItems:'center', gap:8, background:'#fff', border:`1.5px solid ${KN.border}`, borderRadius:999, padding:'5px 12px 5px 8px', fontSize:12, fontWeight:700, color: KN.ink}}>
            <span style={{fontSize:14}}>⏱</span>
            <span>7 min · <span style={{color: KN.muted, fontWeight:700}}>1 of your 21</span></span>
          </div>
          <div style={{display:'inline-flex', alignItems:'center', gap:6, fontSize:12, color: KN.muted, fontWeight:700}}>
            <span>🌳 Tree level</span><span>·</span><span>Apr 25, 2026</span>
          </div>
        </div>
        <div style={{aspectRatio:'16/9', background:'url(audit-assets/article-1.webp) center/cover', borderRadius:18, marginBottom:24}}/>
        <p style={{fontSize:17, color:'#3a2a4a', lineHeight:1.65, margin:'0 0 16px'}}>
          Eighty percent of the seafloor has never been seen by human eyes. A team of <span style={{background:'#fff4d6', color:'#b2541a', padding:'0 6px', borderRadius:6, textDecoration:'underline dotted #d89b4a', textUnderlineOffset:3}}>oceanographers</span> from 30 countries is racing to change that — and they think they can finish the map by 2030.
        </p>
        <p style={{fontSize:17, color:'#3a2a4a', lineHeight:1.65, margin:'0 0 16px'}}>
          The mission, called Seabed 2030, uses fleets of <span style={{background:'#fff4d6', color:'#b2541a', padding:'0 6px', borderRadius:6, textDecoration:'underline dotted #d89b4a', textUnderlineOffset:3}}>autonomous</span> robot submarines that can dive five miles deep without a human pilot…
        </p>
      </section>
    </>
  );
}

// ─────────────────────────────────────────────────────────────
// AFTER · User panel hero
// ─────────────────────────────────────────────────────────────
function UserPanelAfter() {
  return (
    <div style={{width: 420, height: 540, background: KN.cream, borderRadius: 16, overflow:'hidden', border:`2px solid ${KN.border}`, position:'relative'}}>
      <button style={{
        position:'absolute', top:16, right:16,
        width:36, height:36, borderRadius:999, border:`2px solid ${KN.ink}`,
        background:'#fff', fontSize:16, fontWeight:900, color: KN.ink,
      }}>×</button>
      <div style={{
        background:'linear-gradient(135deg, #e8e8e8 0%, #ffe8c8 100%)',
        padding:'32px 28px 20px', borderBottom:`2px solid ${KN.border}`,
        position:'relative', overflow:'hidden',
      }}>
        {/* Faint sun-rays watermark, brand DNA */}
        <svg style={{position:'absolute', right:-30, bottom:-30, opacity:.18, pointerEvents:'none'}} width="160" height="160" viewBox="0 0 200 200">
          {Array.from({length: 12}).map((_, i) => {
            const a = (i*30 - 90) * Math.PI / 180;
            const r1 = 70, r2 = 95;
            return <line key={i}
              x1={100 + Math.cos(a)*r1} y1={100 + Math.sin(a)*r1}
              x2={100 + Math.cos(a)*r2} y2={100 + Math.sin(a)*r2}
              stroke={KN.ink} strokeWidth="6" strokeLinecap="round"/>;
          })}
        </svg>
        <div style={{display:'flex', alignItems:'center', gap:16, position:'relative'}}>
          <div style={{
            width:88, height:88, borderRadius:999, background:'#fff',
            display:'flex', alignItems:'center', justifyContent:'center',
            fontSize:56, border:`3px solid ${KN.ink}`, boxShadow:'0 4px 0 rgba(27,18,48,0.2)',
          }}>🐼</div>
          <div style={{flex:1, minWidth:0}}>
            <div style={{fontFamily:'Fraunces, serif', fontWeight:700, fontSize:30, color: KN.ink, letterSpacing:'-0.025em'}}>Mia</div>
            <div style={{display:'flex', gap:6, marginTop:6, flexWrap:'wrap'}}>
              <span style={{background: KN.ink, color: KN.gold, padding:'4px 10px', borderRadius:999, fontSize:11, fontWeight:800}}>🔥 7 day streak</span>
              <span style={{background:'#fff', padding:'4px 10px', borderRadius:999, fontSize:11, fontWeight:800, color: KN.ink}}>147 stories read</span>
            </div>
          </div>
        </div>
      </div>
      <div style={{display:'flex', gap:4, padding:'14px 20px 0', borderBottom:`2px solid ${KN.border}`}}>
        {[{l:'Learn', e:'📚', a:true}, {l:'Look', e:'🎨'}, {l:'Me', e:'😊'}].map((t, i) => (
          <div key={i} style={{
            background: t.a ? KN.ink : 'transparent', color: t.a ? KN.gold : '#6b5c80',
            borderRadius:'12px 12px 0 0', padding:'10px 16px',
            fontWeight:800, fontSize:13, display:'flex', gap:6, alignItems:'center',
          }}>
            <span>{t.e}</span><span>{t.l}</span>
          </div>
        ))}
      </div>
      <div style={{padding:'20px 24px'}}>
        <div style={{fontSize:11, fontWeight:900, color:'#6b5c80', letterSpacing:'.08em', textTransform:'uppercase', marginBottom:6}}>READING LEVEL</div>
        <div style={{display:'grid', gridTemplateColumns:'1fr 1fr', gap:10}}>
          <div style={{background:'#fff', border:`2px solid ${KN.border}`, borderRadius:14, padding:'14px 12px'}}>
            <div style={{fontSize:24}}>🌱</div>
            <div style={{fontWeight:900, fontSize:14, color: KN.ink, marginTop:4}}>Sprout</div>
            <div style={{fontSize:11, color: KN.muted, fontWeight:700}}>Ages 8–10</div>
          </div>
          <div style={{background:'#fff', border:`3px solid ${KN.ink}`, borderRadius:14, padding:'14px 12px', boxShadow:'0 3px 0 rgba(27,18,48,0.15)'}}>
            <div style={{fontSize:24}}>🌳</div>
            <div style={{fontWeight:900, fontSize:14, color: KN.ink, marginTop:4}}>Tree</div>
            <div style={{fontSize:11, color: KN.muted, fontWeight:700}}>Ages 11–13</div>
          </div>
        </div>
        <div style={{fontSize:11, fontWeight:900, color:'#6b5c80', letterSpacing:'.08em', textTransform:'uppercase', marginTop:18, marginBottom:6}}>DAILY GOAL</div>
        <div style={{display:'flex', gap:6}}>
          {[15, 21, 30, 45].map(g => (
            <div key={g} style={{
              flex:1, padding:'10px 0', textAlign:'center',
              background: g === 21 ? KN.ink : '#fff',
              color: g === 21 ? KN.gold : KN.ink,
              borderRadius:12, fontWeight:900, fontSize:14,
              border: g === 21 ? `2px solid ${KN.ink}` : `2px solid ${KN.border}`,
              position:'relative',
            }}>
              {g}m
              {g === 21 && <div style={{position:'absolute', top:-7, right:-4, background: KN.coral, color:'#fff', fontSize:8, fontWeight:900, padding:'2px 5px', borderRadius:999, letterSpacing:'.06em'}}>BRAND</div>}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// AFTER · NEW · Onboarding splash
// (kidsnews-v2 has no first-time experience — adding one.)
// ─────────────────────────────────────────────────────────────
function OnboardingNew() {
  return (
    <div style={{
      width: 920, height: 580, background: KN.cream, borderRadius: 16, overflow:'hidden',
      position:'relative', display:'grid', gridTemplateColumns:'1fr 1fr',
    }}>
      <div style={{
        background:`linear-gradient(135deg, ${KN.goldHi} 0%, #ffc0a8 100%)`,
        display:'flex', alignItems:'center', justifyContent:'center',
        position:'relative', overflow:'hidden',
      }}>
        <MarkKids size={300}/>
        {/* faint sun pattern in corners */}
        <svg style={{position:'absolute', top:20, left:20, opacity:.18}} width="80" height="80" viewBox="0 0 200 200">
          {Array.from({length: 12}).map((_, i) => {
            const a = (i*30 - 90) * Math.PI / 180;
            return <line key={i}
              x1={100 + Math.cos(a)*70} y1={100 + Math.sin(a)*70}
              x2={100 + Math.cos(a)*95} y2={100 + Math.sin(a)*95}
              stroke={KN.ink} strokeWidth="8" strokeLinecap="round"/>;
          })}
        </svg>
      </div>
      <div style={{padding:'56px 44px', display:'flex', flexDirection:'column', justifyContent:'center'}}>
        <div style={{display:'flex', alignItems:'center', gap:6, marginBottom:14}}>
          <Mark21 size={14} ink={KN.muted} accent={KN.muted}/>
          <span style={{fontSize:11, fontWeight:800, color: KN.muted, letterSpacing:'.18em', textTransform:'uppercase'}}>a 21mins channel</span>
        </div>
        <div style={{
          fontFamily:'Fraunces, serif', fontWeight: 700,
          fontSize: 44, color: KN.ink, letterSpacing:'-0.025em', lineHeight: 1.05,
          marginBottom: 8,
        }}>
          kids<span style={{color: KN.coral}}>news</span>
        </div>
        <div style={{
          fontFamily:'Fraunces, serif', fontWeight: 600, fontStyle:'italic',
          fontSize: 26, color: '#c14e2a', marginBottom: 24, letterSpacing:'-0.015em',
        }}>
          Little daily, big magic.
        </div>
        <div style={{fontSize: 16, color:'#3a2a4a', lineHeight:1.5, marginBottom: 28, maxWidth: 360}}>
          Three smart stories every day, made just for you. Read, think, and quiz —
          <b> 21 minutes</b>, then you're done.
        </div>
        <div style={{display:'flex', flexDirection:'column', gap: 10, marginBottom: 24}}>
          {[
            ['📰', 'News', 'What\'s happening this week, in kid-sized words'],
            ['🔬', 'Science', 'Wild discoveries explained simply'],
            ['🎈', 'Fun', 'Records, puzzles, and the weird side of the world'],
          ].map(([e, t, sub]) => (
            <div key={t} style={{display:'flex', alignItems:'center', gap:12}}>
              <div style={{fontSize: 22}}>{e}</div>
              <div>
                <div style={{fontWeight:800, fontSize:14, color: KN.ink}}>{t}</div>
                <div style={{fontSize:12, color: KN.muted, fontWeight:600}}>{sub}</div>
              </div>
            </div>
          ))}
        </div>
        <button style={{
          background: KN.ink, color:'#fff', border:'none', borderRadius:16,
          padding:'14px 22px', fontWeight:800, fontSize:16,
          fontFamily:'Nunito, sans-serif', boxShadow:'0 5px 0 rgba(0,0,0,0.18)',
          alignSelf:'flex-start',
        }}>Pick my animal →</button>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// AFTER · Favicon / browser-tab preview
// ─────────────────────────────────────────────────────────────
function FaviconPreview() {
  return (
    <div style={{
      width: 460, height: 100, background:'#e8dfd0', borderRadius: 8, padding:'8px 8px 0',
      display:'flex', alignItems:'flex-end', gap: 4,
    }}>
      <div style={{
        background: KN.cream, borderRadius:'10px 10px 0 0',
        padding:'8px 12px', display:'flex', alignItems:'center', gap:8,
        border:`1.5px solid #c9bba3`, borderBottom:'none',
        minWidth: 200, maxWidth: 280,
      }}>
        <MarkKids size={16}/>
        <span style={{
          fontFamily:'Nunito, sans-serif', fontSize: 12, fontWeight: 700, color: KN.ink,
          whiteSpace:'nowrap', overflow:'hidden', textOverflow:'ellipsis', flex: 1,
        }}>kidsnews · today's 21 minutes</span>
        <span style={{fontSize: 14, color: KN.muted, cursor:'pointer'}}>×</span>
      </div>
      <div style={{
        background:'rgba(27,18,48,0.08)', borderRadius:'10px 10px 0 0',
        padding:'8px 14px', display:'flex', alignItems:'center', gap:6,
        opacity: .55,
      }}>
        <span style={{fontSize: 12}}>📑</span>
        <span style={{fontSize: 11, fontWeight: 600, color: KN.ink}}>another tab</span>
      </div>
      <div style={{flex:1}}/>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// AFTER · OG / share-card
// ─────────────────────────────────────────────────────────────
function OGCard() {
  return (
    <div style={{
      width: 600, height: 314, background: KN.cream, borderRadius: 16,
      overflow:'hidden', position:'relative', border:`2px solid ${KN.border}`,
      display:'flex', flexDirection:'column', justifyContent:'space-between',
      padding: 36,
    }}>
      {/* sun rays in corner */}
      <svg style={{position:'absolute', right:-60, bottom:-60, opacity:.16}} width="320" height="320" viewBox="0 0 200 200">
        {Array.from({length: 12}).map((_, i) => {
          const a = (i*30 - 90) * Math.PI / 180;
          return <line key={i}
            x1={100 + Math.cos(a)*70} y1={100 + Math.sin(a)*70}
            x2={100 + Math.cos(a)*95} y2={100 + Math.sin(a)*95}
            stroke={KN.ink} strokeWidth="6" strokeLinecap="round"/>;
        })}
        <circle cx={100} cy={100} r={54} fill={KN.gold}/>
      </svg>
      <div style={{display:'flex', alignItems:'center', gap: 12, position:'relative'}}>
        <MarkKids size={56}/>
        <div>
          <div style={{fontFamily:'Fraunces, serif', fontWeight:700, fontSize:30, color: KN.ink, letterSpacing:'-0.02em', lineHeight:1}}>kids<span style={{color: KN.coral}}>news</span></div>
          <div style={{display:'flex', alignItems:'center', gap:6, marginTop:4}}>
            <Mark21 size={11} ink={KN.muted} accent={KN.muted}/>
            <span style={{fontSize:10, fontWeight:800, color: KN.muted, letterSpacing:'.18em', textTransform:'uppercase'}}>a 21mins channel</span>
          </div>
        </div>
      </div>
      <div style={{position:'relative'}}>
        <div style={{fontFamily:'Fraunces, serif', fontWeight: 700, fontStyle:'italic', fontSize: 36, color: KN.ink, letterSpacing:'-0.02em', lineHeight:1.05, marginBottom: 6}}>
          Little daily, big magic.
        </div>
        <div style={{fontSize: 15, color: KN.muted, fontWeight: 700, lineHeight: 1.4, maxWidth: 380}}>
          The daily news habit for curious kids 8–13. Three stories, 21 minutes,<br/>
          read · think · learn.
        </div>
      </div>
    </div>
  );
}

Object.assign(window, {
  KidsnewsLockup, HeaderAfter, HomeHeroAfter, ArticleReaderAfter,
  UserPanelAfter, OnboardingNew, FaviconPreview, OGCard,
});
