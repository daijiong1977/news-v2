// BEFORE screens — faithful recreations of the current kidsnews-v2 UI.
// Sourced from site/index.html, home.jsx, article.jsx, components.jsx.
// Width: 1180 (matches the live max-width). Height fills to content.

// — The current placeholder logo (OhYeLogo from components.jsx)
function OhYeLogoBefore({ size = 40 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" style={{display:'block'}}>
      <defs>
        <linearGradient id="logoSkyBefore" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0" stopColor="#ffc83d"/><stop offset="1" stopColor="#ffa23d"/>
        </linearGradient>
      </defs>
      <g stroke="#ff6b5b" strokeWidth="1.8" strokeLinecap="round" fill="none" opacity="0.85">
        <path d="M54 14 q3 -1 4 -4"/><path d="M57 19 q5 -1 7 -6"/>
      </g>
      <g fill="#ffb82e">
        <circle cx="6" cy="12" r="1.4"/><circle cx="10" cy="8" r="1.1"/>
      </g>
      <g transform="rotate(-6 32 36)">
        <rect x="11" y="17" width="42" height="38" rx="4" fill="#fff3d6" stroke="#1b1230" strokeWidth="2"/>
        <rect x="8" y="20" width="42" height="38" rx="4" fill="#fff" stroke="#1b1230" strokeWidth="2"/>
        <rect x="12" y="24" width="34" height="7" rx="2" fill="url(#logoSkyBefore)"/>
        <text x="29" y="29.8" textAnchor="middle" fontSize="6" fontWeight="900" fill="#1b1230" fontFamily="Fraunces, serif" letterSpacing="1">NEWS</text>
        <rect x="12" y="34.5" width="26" height="2.2" rx="1" fill="#d9cdb7"/>
        <rect x="12" y="39.2" width="20" height="2.2" rx="1" fill="#d9cdb7"/>
        <circle cx="19" cy="49" r="2" fill="#1b1230"/><circle cx="27" cy="49" r="2" fill="#1b1230"/>
        <path d="M17 52.5 q6 4 12 0" stroke="#1b1230" strokeWidth="2" strokeLinecap="round" fill="none"/>
        <circle cx="15" cy="52" r="1.3" fill="#ff9eb5" opacity=".85"/>
        <circle cx="31" cy="52" r="1.3" fill="#ff9eb5" opacity=".85"/>
      </g>
      <g transform="rotate(8 48 16)">
        <path d="M38 6 h18 a4 4 0 0 1 4 4 v10 a4 4 0 0 1 -4 4 h-10 l-4 4 -1 -4 h-3 a4 4 0 0 1 -4 -4 v-10 a4 4 0 0 1 4 -4 z"
          fill="#ff6b5b" stroke="#1b1230" strokeWidth="2" strokeLinejoin="round"/>
        <text x="47" y="20" textAnchor="middle" fontSize="12" fontWeight="900" fill="#fff" fontFamily="Fraunces, serif">Ye!</text>
      </g>
    </svg>
  );
}

function StreakRingBefore({ minutes = 8, goal = 15, streak = 7, size = 40 }) {
  const r = size/2 - 4, c = 2*Math.PI*r, pct = Math.min(1, minutes/goal);
  return (
    <div style={{position:'relative', width:size, height:size}}>
      <svg width={size} height={size} style={{transform:'rotate(-90deg)'}}>
        <circle cx={size/2} cy={size/2} r={r} stroke="rgba(255,255,255,0.2)" strokeWidth="4" fill="none"/>
        <circle cx={size/2} cy={size/2} r={r} stroke="#ff8a3d" strokeWidth="4" fill="none"
          strokeDasharray={c} strokeDashoffset={c*(1-pct)} strokeLinecap="round"/>
      </svg>
      <div style={{position:'absolute', inset:0, display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center', lineHeight:1}}>
        <div style={{fontSize:14}}>🔥</div>
        <div style={{fontFamily:'Fraunces, serif', fontWeight:800, fontSize:10, color:'#ffc83d', marginTop:1}}>{streak}</div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// BEFORE · Header (from home.jsx → Header)
// ─────────────────────────────────────────────────────────────
function HeaderBefore() {
  return (
    <header style={{
      background: KN.cream, borderBottom: `2px solid ${KN.border}`,
    }}>
      <div style={{maxWidth: 1180, margin:'0 auto', padding:'14px 28px', display:'flex', alignItems:'center', gap:16}}>
        <div style={{display:'flex', alignItems:'center', gap:10}}>
          <OhYeLogoBefore size={44}/>
          <div style={{lineHeight:1}}>
            <div style={{fontFamily:'Fraunces, serif', fontWeight:900, fontSize:22, color: KN.ink, letterSpacing:'-0.01em'}}>
              News Oh<span style={{color: KN.coral}}>,</span>Ye<span style={{color: KN.coral}}>!</span>
            </div>
            <div style={{fontSize:11, color: KN.muted, fontWeight:700, marginTop:2, letterSpacing:'.08em'}}>READ · THINK · LEARN</div>
          </div>
        </div>
        <div style={{flex:1}}/>
        <div style={{display:'flex', alignItems:'center', gap:10, background: KN.ink, color:'#fff', padding:'6px 14px 6px 6px', borderRadius:999}}>
          <StreakRingBefore/>
          <div style={{lineHeight:1.1, textAlign:'left'}}>
            <div style={{fontSize:10, opacity:.7, fontWeight:700}}>STREAK</div>
            <div style={{fontWeight:800, fontSize:13}}>7 days 🔥</div>
          </div>
          <span style={{fontSize:10, opacity:.7, marginLeft:4}}>▾</span>
        </div>
        <div style={{
          display:'flex', alignItems:'center', gap:10,
          background:'#fff', border:`2px solid ${KN.ink}`, borderRadius:999,
          padding:'4px 14px 4px 4px', boxShadow:'0 3px 0 rgba(27,18,48,0.12)',
        }}>
          <div style={{width:36, height:36, borderRadius:999, background:'#e8e8e8', display:'flex', alignItems:'center', justifyContent:'center', fontSize:20, border:`2px solid ${KN.ink}`}}>🐼</div>
          <div style={{textAlign:'left', lineHeight:1.1}}>
            <div style={{fontWeight:900, fontSize:13, color: KN.ink}}>Me</div>
            <div style={{fontSize:10, color:'#6b5c80', fontWeight:700}}>🇬🇧 EN · 🌳 Tree · 🔥 7</div>
          </div>
          <span style={{fontSize:11, color: KN.muted, marginLeft:2}}>▾</span>
        </div>
      </div>
    </header>
  );
}

// ─────────────────────────────────────────────────────────────
// BEFORE · Home hero (Today's 15 minutes, Daily 3 stack)
// ─────────────────────────────────────────────────────────────
function HomeHeroBefore() {
  const stories = [
    { title: 'Why scientists are racing to map the deep ocean before 2030', cat:'Science', mins: 5, img: 'audit-assets/article-1.webp' },
    { title: 'A small town in Iowa just got a giant data center next door', cat:'News',    mins: 5, img: 'audit-assets/article-2.webp' },
    { title: 'The world record for most yo-yos balanced on one finger',     cat:'Fun',     mins: 5, img: 'audit-assets/article-3.webp' },
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
        <div>
          <div style={{fontFamily:'Nunito, sans-serif', fontWeight:800, color:'#c14e2a', fontSize:13, letterSpacing:'.1em', textTransform:'uppercase', marginBottom:6}}>
            Hi friend! 👋 · Saturday, Apr 25
          </div>
          <h1 style={{fontFamily:'Fraunces, serif', fontWeight:900, fontSize:52, lineHeight:1.02, color: KN.ink, margin:'0 0 12px', letterSpacing:'-0.02em'}}>
            Today's <span style={{background: KN.gold, padding:'0 10px', borderRadius:12, display:'inline-block', transform:'rotate(-2deg)'}}>15 minutes</span>
          </h1>
          <p style={{fontSize:17, color:'#3a2a4a', margin:'0 0 18px', lineHeight:1.5, maxWidth: 480}}>
            Read 3 smart stories, learn new words, and win your streak. You've read <b>1 of 3</b> today.
          </p>
          <div style={{display:'flex', gap:10, alignItems:'center'}}>
            <button style={{
              background: KN.ink, color:'#fff', border:'none', borderRadius:16,
              padding:'14px 22px', fontWeight:800, fontSize:16,
              fontFamily:'Nunito, sans-serif', boxShadow:'0 5px 0 rgba(0,0,0,0.18)',
            }}>▶  Start today's read</button>
            <div style={{display:'flex', alignItems:'center', gap:8, padding:'10px 14px', background:'rgba(255,255,255,0.65)', borderRadius:14, fontWeight:700, fontSize:14}}>
              <span style={{fontSize:18}}>⏱️</span><span>8/15 min today</span>
            </div>
          </div>
        </div>
        <div style={{display:'flex', flexDirection:'column', gap:10}}>
          <div style={{display:'flex', justifyContent:'space-between', alignItems:'baseline'}}>
            <div style={{fontFamily:'Fraunces, serif', fontWeight:800, fontSize:18, color: KN.ink}}>⚡ Today's 3 · 5 min</div>
            <div style={{fontSize:11, color:'#6b5c80', fontWeight:700}}>Tap ⇆ to swap</div>
          </div>
          {stories.map((s, i) => {
            const cat = KN.cats[s.cat];
            return (
              <div key={i} style={{
                background:'#fff', border:'2px solid #fff', borderRadius:16, padding:'10px 12px',
                display:'flex', gap:12, alignItems:'center', boxShadow:'0 2px 0 rgba(27,18,48,0.08)',
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
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}

// ─────────────────────────────────────────────────────────────
// BEFORE · Category tabs + article grid
// ─────────────────────────────────────────────────────────────
function HomeGridBefore() {
  const articles = [
    { title:'Why scientists are racing to map the deep ocean before 2030', summary:'A new global mission will use robot subs to chart the seafloor, where 80% is still a mystery to humans.', cat:'Science', mins: 5, img:'audit-assets/article-1.webp' },
    { title:"A small town in Iowa got a giant data center next door — what's the deal?", summary:'The plant will power millions of AI chats. Locals are split on jobs vs. water and noise.', cat:'News', mins: 5, img:'audit-assets/article-2.webp' },
    { title:'The world record for most yo-yos balanced on one finger is wild', summary:'A 14-year-old in Tokyo just stacked 21 in a row. We asked her physics teacher how it works.', cat:'Fun', mins: 5, img:'audit-assets/article-3.webp' },
  ];
  return (
    <>
      <section style={{maxWidth:1180, margin:'32px auto 0', padding:'0 28px'}}>
        <div style={{display:'flex', gap:12, flexWrap:'wrap', alignItems:'center'}}>
          {['News','Science','Fun'].map((c, i) => {
            const cat = KN.cats[c];
            const active = i === 0;
            return (
              <button key={c} style={{
                background: active ? cat.color : cat.bg,
                color: active ? '#fff' : cat.color,
                border:'none', borderRadius:999, padding:'10px 18px',
                fontWeight:800, fontSize:14,
                display:'inline-flex', alignItems:'center', gap:7, fontFamily:'Nunito, sans-serif',
                boxShadow: active ? '0 3px 0 rgba(27,18,48,0.15)' : 'none',
              }}>
                <span style={{fontSize:15}}>{cat.emoji}</span>{c}
              </button>
            );
          })}
          <button style={{
            background:'#fff', color: KN.ink, border:`2px dashed #c9b99a`,
            borderRadius:999, padding:'8px 16px', fontWeight:800, fontSize:13,
            display:'inline-flex', alignItems:'center', gap:6, fontFamily:'Nunito, sans-serif',
          }}>📅 View old news</button>
          <div style={{flex:1}}/>
          <span style={{fontSize:13, color:'#7a6b8c', fontWeight:600}}>
            Showing stories at <b style={{color: KN.ink}}>Tree</b> level
          </span>
        </div>
      </section>
      <section style={{maxWidth:1180, margin:'20px auto 0', padding:'0 28px 60px'}}>
        <div style={{display:'flex', flexDirection:'column', gap:20}}>
          {/* feature card */}
          <div style={{
            background:'#fff', border:`2px solid ${KN.border}`, borderRadius:22,
            overflow:'hidden', boxShadow:'0 4px 0 rgba(27,18,48,0.06)',
          }}>
            <div style={{aspectRatio:'16/9', background:`url(${articles[0].img}) center/cover`}}/>
            <div style={{padding:'26px 32px 24px', display:'flex', flexDirection:'column', gap:10}}>
              <h3 style={{fontFamily:'Fraunces, serif', fontWeight:800, fontSize:28, lineHeight:1.15, letterSpacing:'-0.01em', color: KN.ink, margin:0}}>{articles[0].title}</h3>
              <p style={{fontSize:15, color:'#4a3d5e', lineHeight:1.6, margin:0}}>{articles[0].summary}</p>
              <div style={{display:'flex', alignItems:'center', gap:8, paddingTop:8}}>
                <span style={{display:'inline-flex', alignItems:'center', gap:4, background:'#fff4c2', color:'#8a6d00', padding:'3px 10px', borderRadius:999, fontWeight:800, fontSize:12}}>
                  <span>⭐</span>+10 XP
                </span>
                <span style={{fontSize:12, color: KN.muted, fontWeight:700}}>⏱ {articles[0].mins} min</span>
              </div>
            </div>
          </div>
          <div style={{display:'grid', gridTemplateColumns:'1fr 1fr', gap:20}}>
            {articles.slice(1).map((a, i) => (
              <div key={i} style={{
                background:'#fff', border:`2px solid ${KN.border}`, borderRadius:22,
                overflow:'hidden', boxShadow:'0 4px 0 rgba(27,18,48,0.06)',
              }}>
                <div style={{aspectRatio:'16/10', background:`url(${a.img}) center/cover`}}/>
                <div style={{padding:'16px 18px 18px', display:'flex', flexDirection:'column', gap:10}}>
                  <h3 style={{fontFamily:'Fraunces, serif', fontWeight:800, fontSize:19, lineHeight:1.15, letterSpacing:'-0.01em', color: KN.ink, margin:0}}>{a.title}</h3>
                  <p style={{fontSize:13.5, color:'#4a3d5e', lineHeight:1.6, margin:0}}>{a.summary}</p>
                  <div style={{display:'flex', alignItems:'center', gap:8, paddingTop:8}}>
                    <span style={{display:'inline-flex', alignItems:'center', gap:4, background:'#fff4c2', color:'#8a6d00', padding:'2px 8px', borderRadius:999, fontWeight:800, fontSize:11}}>
                      <span>⭐</span>+10 XP
                    </span>
                    <span style={{fontSize:12, color: KN.muted, fontWeight:700}}>⏱ {a.mins} min</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>
    </>
  );
}

// ─────────────────────────────────────────────────────────────
// BEFORE · Article reader top + stepper
// ─────────────────────────────────────────────────────────────
function ArticleReaderBefore() {
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
          <div style={{display:'flex', alignItems:'center', gap:10}}>
            <OhYeLogoBefore size={32}/>
            <div style={{fontFamily:'Fraunces, serif', fontWeight:900, fontSize:18, color: KN.ink}}>News Oh,Ye!</div>
          </div>
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
        <h1 style={{fontFamily:'Fraunces, serif', fontWeight:900, fontSize:42, lineHeight:1.1, color: KN.ink, margin:'0 0 16px', letterSpacing:'-0.02em'}}>
          Why scientists are racing to map the deep ocean before 2030
        </h1>
        <div style={{display:'flex', gap:14, alignItems:'center', color: KN.muted, fontSize:13, fontWeight:700, marginBottom:24}}>
          <span>⏱ 7 min · Tree level</span>
          <span>·</span>
          <span>Apr 25, 2026</span>
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
// BEFORE · User panel header (drawer hero)
// ─────────────────────────────────────────────────────────────
function UserPanelBefore() {
  return (
    <div style={{width: 420, height: 540, background: KN.cream, borderRadius: 16, overflow:'hidden', border:`2px solid ${KN.border}`}}>
      <button style={{
        position:'absolute', top:16, right:16,
        width:36, height:36, borderRadius:999, border:`2px solid ${KN.ink}`,
        background:'#fff', fontSize:16, fontWeight:900, color: KN.ink,
      }}>×</button>
      <div style={{
        background:'linear-gradient(135deg, #e8e8e8 0%, #ffe8c8 100%)',
        padding:'32px 28px 20px', borderBottom:`2px solid ${KN.border}`,
      }}>
        <div style={{display:'flex', alignItems:'center', gap:16}}>
          <div style={{
            width:88, height:88, borderRadius:999, background:'#fff',
            display:'flex', alignItems:'center', justifyContent:'center',
            fontSize:56, border:`3px solid ${KN.ink}`, boxShadow:'0 4px 0 rgba(27,18,48,0.2)',
          }}>🐼</div>
          <div style={{flex:1, minWidth:0}}>
            <div style={{fontFamily:'Fraunces, serif', fontWeight:900, fontSize:30, color: KN.ink, letterSpacing:'-0.02em'}}>Your name</div>
            <div style={{display:'flex', gap:6, marginTop:4, flexWrap:'wrap'}}>
              <span style={{background:'#fff', padding:'4px 10px', borderRadius:999, fontSize:11, fontWeight:800}}>🔥 7 day streak</span>
              <span style={{background:'#fff', padding:'4px 10px', borderRadius:999, fontSize:11, fontWeight:800}}>⭐ 240 XP</span>
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
          {[5, 10, 15, 20, 30].map(g => (
            <div key={g} style={{
              flex:1, padding:'10px 0', textAlign:'center',
              background: g === 15 ? KN.ink : '#fff',
              color: g === 15 ? KN.gold : KN.ink,
              borderRadius:12, fontWeight:900, fontSize:14,
              border: g === 15 ? `2px solid ${KN.ink}` : `2px solid ${KN.border}`,
            }}>{g}m</div>
          ))}
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { HeaderBefore, HomeHeroBefore, HomeGridBefore, ArticleReaderBefore, UserPanelBefore, OhYeLogoBefore, StreakRingBefore });
