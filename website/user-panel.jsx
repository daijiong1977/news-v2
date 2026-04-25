// User Profile Button + Panel
const { useState: useStateU } = React;

const AVATARS = [
  { id:'fox', emoji:'🦊', bg:'#ffb27a' },
  { id:'panda', emoji:'🐼', bg:'#e8e8e8' },
  { id:'octopus', emoji:'🐙', bg:'#ffa5c5' },
  { id:'unicorn', emoji:'🦄', bg:'#e0cbff' },
  { id:'frog', emoji:'🐸', bg:'#bde8a0' },
  { id:'lion', emoji:'🦁', bg:'#ffd98a' },
  { id:'penguin', emoji:'🐧', bg:'#bed7ff' },
  { id:'tiger', emoji:'🐯', bg:'#ffc48a' },
  { id:'cat', emoji:'🐱', bg:'#f5e0b8' },
  { id:'rocket', emoji:'🚀', bg:'#c8bfff' },
  { id:'turtle', emoji:'🐢', bg:'#a8e6c4' },
  { id:'bear', emoji:'🐻', bg:'#e8c8a0' },
];

const LANGS = [
  { id:'en', flag:'🇬🇧', label:'English' },
  { id:'zh', flag:'🇨🇳', label:'中文' },
];

const LEVEL_OPTIONS = [
  { id:'Sprout', emoji:'🌱', sub:'Ages 8–10 · easier reads' },
  { id:'Tree', emoji:'🌳', sub:'Ages 11–13 · deeper dives' },
];

const THEMES = [
  { id:'sunny',  emoji:'☀️', label:'Sunny',  sw1:'#ffe2a8', sw2:'#ffc0a8' },
  { id:'sky',    emoji:'🌊', label:'Sky',    sw1:'#cfe6ff', sw2:'#bfd9ff' },
  { id:'candy',  emoji:'🍬', label:'Candy',  sw1:'#ffd0e2', sw2:'#e0cbff' },
  { id:'forest', emoji:'🌳', label:'Forest', sw1:'#d9ecc0', sw2:'#f2e1a6' },
];

const GOALS = [5, 10, 15, 20, 30];

// Find avatar object by id
function getAvatar(id) {
  return AVATARS.find(a => a.id === id) || AVATARS[0];
}

// —————————— USER BUTTON (in header) ——————————
function UserButton({ tweaks, onClick, streak, level }) {
  const av = getAvatar(tweaks.avatar);
  // Prefer the prop `level` (app's authoritative state used for content
  // filtering) over `tweaks.level` (a mirror that can drift on legacy
  // installs). Falls back to tweaks for the iframe-edit-mode preview.
  const activeLevel = level || tweaks.level;
  const lvl = LEVEL_OPTIONS.find(l => l.id === activeLevel) || LEVEL_OPTIONS[1];
  return (
    <button onClick={onClick} style={{
      display:'flex', alignItems:'center', gap:10,
      background:'#fff', border:'2px solid #1b1230',
      borderRadius:999, padding:'4px 14px 4px 4px',
      cursor:'pointer',
      boxShadow:'0 3px 0 rgba(27,18,48,0.12)',
      fontFamily:'Nunito, sans-serif',
      transition:'transform .15s',
    }}
    onMouseEnter={e=>e.currentTarget.style.transform='translateY(-2px)'}
    onMouseLeave={e=>e.currentTarget.style.transform='translateY(0)'}
    >
      <div style={{
        width:38, height:38, borderRadius:999, background:av.bg,
        display:'flex', alignItems:'center', justifyContent:'center',
        fontSize:22, border:'2px solid #1b1230',
      }}>{av.emoji}</div>
      <div style={{textAlign:'left', lineHeight:1.1}}>
        <div style={{fontWeight:900, fontSize:14, color:'#1b1230'}}>{tweaks.userName || 'Me'}</div>
        <div style={{fontSize:11, color:'#6b5c80', fontWeight:700, display:'flex', gap:6, alignItems:'center'}}>
          {tweaks.language === 'zh' ? (
            // Chinese mode: show flag + 中文; level is irrelevant
            // (Chinese variants are summary-only at Sprout level only).
            <span>🇨🇳 中文</span>
          ) : (
            // English mode: show language flag + reading level so users
            // see at a glance both axes of their choice.
            <>
              <span>🇬🇧 EN</span>
              <span style={{color:'#d0c4b4'}}>·</span>
              <span>{lvl.emoji} {lvl.id}</span>
            </>
          )}
          <span style={{color:'#d0c4b4'}}>·</span>
          <span>🔥 {streak}</span>
        </div>
      </div>
      <span style={{fontSize:12, color:'#9a8d7a', marginLeft:2}}>▾</span>
    </button>
  );
}

// —————————— USER PANEL (slide-in drawer) ——————————
function UserPanel({ tweaks, updateTweak, level, setLevel, onClose, progress }) {
  const av = getAvatar(tweaks.avatar);
  const [tab, setTab] = useStateU('learn'); // learn | look | me

  const setLevelBoth = (lv) => { setLevel(lv); updateTweak('level', lv); };

  // Real progression numbers (not MOCK_USER):
  // - storiesRead = articles read today (only metric we track now)
  // - badges = milestone count: 1 badge per 3 stories read today
  const storiesRead = ((progress && progress.readToday) || []).length;
  const badges = Math.floor(storiesRead / 3);

  return (
    <>
      {/* backdrop */}
      <div onClick={onClose} style={{
        position:'fixed', inset:0, background:'rgba(27,18,48,0.35)', zIndex:90,
        animation:'fadeIn .2s ease-out',
      }}/>
      {/* drawer */}
      <div style={{
        position:'fixed', top:0, right:0, bottom:0, width:420,
        background:'#fff9ef', zIndex:100,
        boxShadow:'-10px 0 40px rgba(27,18,48,0.2)',
        overflowY:'auto',
        fontFamily:'Nunito, sans-serif',
        animation:'slideIn .25s ease-out',
      }}>
        <style>{`
          @keyframes fadeIn { from{opacity:0} to{opacity:1} }
          @keyframes slideIn { from{transform:translateX(100%)} to{transform:translateX(0)} }
        `}</style>

        {/* close */}
        <button onClick={onClose} style={{
          position:'absolute', top:16, right:16, zIndex:2,
          width:36, height:36, borderRadius:999, border:'2px solid #1b1230',
          background:'#fff', cursor:'pointer', fontSize:16, fontWeight:900, color:'#1b1230',
        }}>×</button>

        {/* hero */}
        <div style={{
          background:`linear-gradient(135deg, ${av.bg} 0%, #ffe8c8 100%)`,
          padding:'32px 28px 20px',
          borderBottom:'2px solid #f0e8d8',
        }}>
          <div style={{display:'flex', alignItems:'center', gap:16}}>
            <div style={{
              width:88, height:88, borderRadius:999, background:'#fff',
              display:'flex', alignItems:'center', justifyContent:'center',
              fontSize:56, border:'3px solid #1b1230',
              boxShadow:'0 4px 0 rgba(27,18,48,0.2)',
            }}>{av.emoji}</div>
            <div style={{flex:1, minWidth:0}}>
              <input
                value={tweaks.userName || ''}
                onChange={e=>updateTweak('userName', e.target.value.slice(0, 18))}
                placeholder="Your name"
                style={{
                  fontFamily:'Fraunces, serif', fontWeight:900, fontSize:30,
                  color:'#1b1230', letterSpacing:'-0.02em',
                  background:'transparent', border:'none', outline:'none',
                  width:'100%', padding:0, margin:0,
                }}
              />
              <div style={{display:'flex', gap:6, marginTop:4, flexWrap:'wrap'}}>
                <MiniStat icon="🔥" val={`${tweaks.streakDays ?? 7} day streak`}/>
                <MiniStat icon="⭐" val={`${tweaks.xp ?? 240} XP`}/>
              </div>
            </div>
          </div>
        </div>

        {/* tabs */}
        <div style={{display:'flex', gap:4, padding:'14px 20px 0', borderBottom:'2px solid #f0e8d8'}}>
          {[
            {id:'learn', label:'Learn', emoji:'📚'},
            {id:'look', label:'Look', emoji:'🎨'},
            {id:'me', label:'Me', emoji:'😊'},
          ].map(t => (
            <button key={t.id} onClick={()=>setTab(t.id)} style={{
              background: tab===t.id ? '#1b1230' : 'transparent',
              color: tab===t.id ? '#ffc83d' : '#6b5c80',
              border:'none', borderRadius:'12px 12px 0 0',
              padding:'10px 16px', cursor:'pointer',
              fontWeight:800, fontSize:13, fontFamily:'Nunito, sans-serif',
              display:'flex', gap:6, alignItems:'center',
            }}>
              <span>{t.emoji}</span><span>{t.label}</span>
            </button>
          ))}
        </div>

        <div style={{padding:'20px 24px 40px'}}>
          {tab === 'me' && (
            <>
              <Section label="Pick your animal" sub="This is you around the site">
                <div style={{display:'grid', gridTemplateColumns:'repeat(6, 1fr)', gap:8}}>
                  {AVATARS.map(a => (
                    <button key={a.id} onClick={()=>updateTweak('avatar', a.id)} style={{
                      aspectRatio:'1', borderRadius:14, background:a.bg,
                      border: tweaks.avatar===a.id ? '3px solid #1b1230' : '2px solid transparent',
                      cursor:'pointer', fontSize:28, padding:0,
                      boxShadow: tweaks.avatar===a.id ? '0 3px 0 rgba(27,18,48,0.2)' : 'none',
                      transform: tweaks.avatar===a.id ? 'translateY(-2px)' : 'none',
                      transition:'all .15s',
                    }}>{a.emoji}</button>
                  ))}
                </div>
              </Section>

              <Section label="Daily goal" sub="Read 15 minutes a day to build your streak">
                <div style={{
                  background:'#fff9ef', border:'2px solid #f0e8d8', borderRadius:14,
                  padding:'12px 16px', display:'flex', alignItems:'center', gap:12,
                }}>
                  <div style={{
                    width:44, height:44, borderRadius:12, background:'#1b1230',
                    color:'#ffc83d', display:'flex', alignItems:'center', justifyContent:'center',
                    fontFamily:'Fraunces, serif', fontWeight:900, fontSize:20,
                  }}>15</div>
                  <div>
                    <div style={{fontFamily:'Fraunces, serif', fontWeight:900, fontSize:18, color:'#1b1230', lineHeight:1}}>15 min every day</div>
                    <div style={{fontSize:12, color:'#6b5c80', fontWeight:600, marginTop:4}}>One story from each category · just right for a daily habit</div>
                  </div>
                </div>
              </Section>

              <Section label="Language" sub="What language you want stories in">
                <div style={{display:'grid', gridTemplateColumns:'repeat(2, 1fr)', gap:8}}>
                  {LANGS.map(l => (
                    <button key={l.id} onClick={()=>{
                      updateTweak('language', l.id);
                      if (l.id === 'zh') setLevelBoth('Sprout');
                    }} style={{
                      background: tweaks.language===l.id ? '#1b1230' : '#fff',
                      color: tweaks.language===l.id ? '#fff' : '#1b1230',
                      border: tweaks.language===l.id ? '2px solid #1b1230' : '2px solid #f0e8d8',
                      borderRadius:14, padding:'10px 12px', cursor:'pointer',
                      fontWeight:800, fontSize:13, fontFamily:'Nunito, sans-serif',
                      display:'flex', gap:8, alignItems:'center', justifyContent:'flex-start',
                    }}>
                      <span style={{fontSize:20}}>{l.flag}</span>
                      <span>{l.label}</span>
                    </button>
                  ))}
                </div>
              </Section>
            </>
          )}

          {tab === 'look' && (
            <>
              <Section label="Color theme" sub="Change the vibe of the whole site">
                <div style={{display:'grid', gridTemplateColumns:'repeat(2, 1fr)', gap:10}}>
                  {THEMES.map(t => {
                    const active = tweaks.theme === t.id;
                    return (
                      <button key={t.id} onClick={()=>updateTweak('theme', t.id)} style={{
                        background:'#fff', padding:12, borderRadius:16,
                        border: active ? '3px solid #1b1230' : '2px solid #f0e8d8',
                        cursor:'pointer', textAlign:'left', fontFamily:'Nunito, sans-serif',
                        boxShadow: active ? '0 3px 0 rgba(27,18,48,0.15)' : 'none',
                      }}>
                        <div style={{height:38, borderRadius:10, background:`linear-gradient(135deg, ${t.sw1}, ${t.sw2})`, marginBottom:8}}/>
                        <div style={{fontWeight:900, fontSize:14, color:'#1b1230'}}>
                          {t.emoji} {t.label}
                        </div>
                      </button>
                    );
                  })}
                </div>
              </Section>

              <Section label="Home page style" sub="What greets you on the homepage">
                <div style={{display:'grid', gridTemplateColumns:'1fr 1fr', gap:10}}>
                  <HeroPick active={tweaks.heroVariant==='daily15'} onClick={()=>updateTweak('heroVariant','daily15')}
                    title="Today's 15" sub="Start reading fast"
                    preview={
                      <div style={{background:'linear-gradient(135deg,#ffe2a8,#ffc0a8)', borderRadius:8, padding:8, height:60}}>
                        <div style={{fontSize:9, fontWeight:800, color:'#c14e2a'}}>TODAY</div>
                        <div style={{fontSize:14, fontWeight:900, color:'#1b1230', fontFamily:'Fraunces, serif'}}>15 <span style={{background:'#ffc83d', padding:'0 4px', borderRadius:3}}>min</span></div>
                      </div>
                    }
                  />
                  <HeroPick active={tweaks.heroVariant==='streak'} onClick={()=>updateTweak('heroVariant','streak')}
                    title="Streak mode" sub="See your fire days"
                    preview={
                      <div style={{background:'linear-gradient(135deg,#ffe2a8,#ffc0a8)', borderRadius:8, padding:8, height:60, display:'flex', alignItems:'center', gap:6}}>
                        <div style={{fontSize:20}}>🔥</div>
                        <div>
                          <div style={{fontSize:14, fontWeight:900, color:'#1b1230', fontFamily:'Fraunces, serif'}}>7 days</div>
                          <div style={{display:'flex', gap:2}}>
                            {[1,1,1,1,1,1,0].map((d,i)=>(
                              <div key={i} style={{width:6, height:8, borderRadius:2, background: d?'#1b1230':'rgba(255,255,255,0.6)'}}/>
                            ))}
                          </div>
                        </div>
                      </div>
                    }
                  />
                </div>
              </Section>

              <Section label="Quiz celebration" sub="Confetti when you get things right">
                <label style={{display:'flex', alignItems:'center', gap:10, padding:'10px 14px', background:'#fff', border:'2px solid #f0e8d8', borderRadius:14, cursor:'pointer'}}>
                  <input type="checkbox" checked={tweaks.showConfetti} onChange={e=>updateTweak('showConfetti', e.target.checked)} style={{width:18, height:18}}/>
                  <span style={{fontWeight:700, fontSize:14, color:'#1b1230'}}>🎉 {tweaks.showConfetti ? 'Confetti on' : 'Confetti off'}</span>
                </label>
              </Section>
            </>
          )}

          {tab === 'learn' && (
            <>
              <Section label="Reading level" sub={tweaks.language === 'zh' ? 'Chinese stories are only available at Sprout level right now' : 'Harder or easier stories'}>
                <div style={{display:'flex', flexDirection:'column', gap:8}}>
                  {LEVEL_OPTIONS.map(l => {
                    const active = (level || tweaks.level) === l.id;
                    const zhLocked = tweaks.language === 'zh' && l.id !== 'Sprout';
                    return (
                      <button key={l.id} disabled={zhLocked} onClick={()=>!zhLocked && setLevelBoth(l.id)} style={{
                        background: active ? '#1b1230' : '#fff',
                        color: active ? '#fff' : '#1b1230',
                        border: active ? '2px solid #1b1230' : '2px solid #f0e8d8',
                        borderRadius:14, padding:'12px 16px', cursor: zhLocked ? 'not-allowed' : 'pointer',
                        fontFamily:'Nunito, sans-serif',
                        display:'flex', alignItems:'center', gap:12, textAlign:'left',
                        opacity: zhLocked ? 0.45 : 1,
                        position:'relative',
                      }}>
                        <div style={{fontSize:28}}>{l.emoji}</div>
                        <div>
                          <div style={{fontWeight:900, fontSize:16}}>{l.id}</div>
                          <div style={{fontSize:12, opacity:0.75, fontWeight:600}}>{l.sub}</div>
                        </div>
                        {active && !zhLocked && <div style={{marginLeft:'auto', fontSize:18, color:'#ffc83d'}}>✓</div>}
                        {zhLocked && <div style={{marginLeft:'auto', fontSize:11, fontWeight:800, color:'#9a8d7a', background:'#f6efe3', padding:'3px 8px', borderRadius:999}}>🔒 EN only</div>}
                      </button>
                    );
                  })}
                </div>
              </Section>

              <Section label="Your progress" sub="">
                <div style={{display:'grid', gridTemplateColumns:'1fr 1fr', gap:10}}>
                  <BigStat icon="🔥" val={`${tweaks.streakDays ?? 0}`} label="Day streak"/>
                  <BigStat icon="⭐" val={`${tweaks.xp ?? 0}`} label="XP earned"/>
                  <BigStat icon="📖" val={`${storiesRead}`} label="Stories today"/>
                  <BigStat icon="🏆" val={`${badges}`} label="Badges"/>
                </div>
              </Section>

              <Section label="Parent / teacher" sub="">
                <button style={{
                  width:'100%', background:'#fff', border:'2px solid #f0e8d8',
                  borderRadius:14, padding:'12px 16px', cursor:'pointer',
                  fontWeight:800, fontSize:14, color:'#1b1230',
                  fontFamily:'Nunito, sans-serif', textAlign:'left',
                  display:'flex', alignItems:'center', gap:10,
                }}>
                  <span style={{fontSize:20}}>👨‍👩‍👧</span>
                  <span style={{flex:1}}>Parent dashboard</span>
                  <span style={{color:'#9a8d7a'}}>›</span>
                </button>
              </Section>
            </>
          )}

          <div style={{display:'flex', gap:8, marginTop:12}}>
            <button onClick={onClose} style={{
              flex:1, background:'#1b1230', color:'#ffc83d', border:'none',
              borderRadius:14, padding:'14px', cursor:'pointer',
              fontWeight:900, fontSize:15, fontFamily:'Nunito, sans-serif',
              boxShadow:'0 3px 0 rgba(0,0,0,0.2)',
            }}>Done ✓</button>
            <button onClick={()=>{
              updateTweak('avatar','fox'); updateTweak('userName','Me');
              updateTweak('theme','sunny'); updateTweak('heroVariant','daily15');
              updateTweak('language','en'); updateTweak('dailyGoal',15);
              setLevelBoth('Sprout');
            }} style={{
              background:'#fff', color:'#6b5c80', border:'2px solid #f0e8d8',
              borderRadius:14, padding:'14px 16px', cursor:'pointer',
              fontWeight:800, fontSize:13, fontFamily:'Nunito, sans-serif',
            }}>Reset</button>
          </div>
        </div>
      </div>
    </>
  );
}

function MiniStat({ icon, val }) {
  return (
    <div style={{
      display:'inline-flex', alignItems:'center', gap:4,
      background:'rgba(255,255,255,0.7)', padding:'3px 10px', borderRadius:999,
      fontSize:12, fontWeight:800, color:'#1b1230',
    }}>
      <span>{icon}</span><span>{val}</span>
    </div>
  );
}

function BigStat({ icon, val, label }) {
  return (
    <div style={{
      background:'#fff', border:'2px solid #f0e8d8', borderRadius:14,
      padding:'14px', textAlign:'center',
    }}>
      <div style={{fontSize:24, marginBottom:2}}>{icon}</div>
      <div style={{fontFamily:'Fraunces, serif', fontWeight:900, fontSize:26, color:'#1b1230', lineHeight:1}}>{val}</div>
      <div style={{fontSize:11, color:'#6b5c80', fontWeight:700, marginTop:4, textTransform:'uppercase', letterSpacing:'.05em'}}>{label}</div>
    </div>
  );
}

function HeroPick({ active, onClick, title, sub, preview }) {
  return (
    <button onClick={onClick} style={{
      background:'#fff', padding:10, borderRadius:16,
      border: active ? '3px solid #1b1230' : '2px solid #f0e8d8',
      cursor:'pointer', textAlign:'left', fontFamily:'Nunito, sans-serif',
      boxShadow: active ? '0 3px 0 rgba(27,18,48,0.15)' : 'none',
    }}>
      {preview}
      <div style={{fontWeight:900, fontSize:13, color:'#1b1230', marginTop:8}}>{title}</div>
      <div style={{fontSize:11, color:'#6b5c80', fontWeight:600}}>{sub}</div>
    </button>
  );
}

function Section({ label, sub, children }) {
  return (
    <div style={{marginBottom:24}}>
      <div style={{fontFamily:'Fraunces, serif', fontWeight:900, fontSize:16, color:'#1b1230', marginBottom:2}}>{label}</div>
      {sub && <div style={{fontSize:12, color:'#6b5c80', fontWeight:600, marginBottom:12}}>{sub}</div>}
      {!sub && <div style={{height:10}}/>}
      {children}
    </div>
  );
}

Object.assign(window, { UserButton, UserPanel });
