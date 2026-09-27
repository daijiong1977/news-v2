// Pick-3 flow — proposed reframe of the home experience.
// Three screens, read left-to-right:
//   1. Pick · "Choose your 3 for today" — kid actively curates
//   2. Today · "Locked in" — the chosen 3, ready to read
//   3. Read · article reader (just shows continuity, reuses ArticleReaderAfter)
//
// Pool of stories the kid picks from. Mix categories so it feels balanced.
const PICK_POOL = [
  { id: 'ocean',    cat:'Science', mins: 7, title:'Why scientists are racing to map the deep ocean before 2030', img:'audit-assets/article-1.webp', hook:'80% of the seafloor has never been seen.' },
  { id: 'iowa',     cat:'News',    mins: 7, title:'A small Iowa town just got a giant data center next door',     img:'audit-assets/article-2.webp', hook:'Locals are split on jobs vs. water and noise.' },
  { id: 'yoyo',     cat:'Fun',     mins: 6, title:'21 yo-yos balanced on one finger — a new world record',         img:'audit-assets/article-3.webp', hook:'A 14-year-old in Tokyo just pulled it off.' },
  { id: 'penguin',  cat:'Science', mins: 6, title:'Emperor penguins are crossing ice they\'ve never crossed before', img:'audit-assets/article-1.webp', hook:'Climate is rewriting their commute.' },
  { id: 'bus',      cat:'News',    mins: 8, title:'Why every school bus in this state is going electric next year', img:'audit-assets/article-2.webp', hook:'Kids breathe in a lot of bus exhaust.' },
  { id: 'lego',     cat:'Fun',     mins: 5, title:'A LEGO castle built without instructions — for science',         img:'audit-assets/article-3.webp', hook:'Researchers wanted to see how brains plan.' },
  { id: 'bees',     cat:'Science', mins: 7, title:'Bees can do math. New experiments prove they can subtract.',     img:'audit-assets/article-1.webp', hook:'They\'re better than some second graders.' },
  { id: 'mars',     cat:'News',    mins: 8, title:'NASA picked the next four people who\'ll fly around the Moon',   img:'audit-assets/article-2.webp', hook:'Launch is sooner than you think.' },
  { id: 'soup',     cat:'Fun',     mins: 5, title:'The world\'s longest noodle: 10,119 meters of one strand',       img:'audit-assets/article-3.webp', hook:'Yes, they measured it. Yes, they ate it.' },
];

// — Story card that toggles selected/unselected
function StoryCard({ story, picked, slot, onToggle }) {
  const cat = KN.cats[story.cat];
  return (
    <button
      onClick={onToggle}
      style={{
        position:'relative', textAlign:'left',
        background: picked ? cat.bg : '#fff',
        border: picked ? `3px solid ${cat.color}` : `2px solid ${KN.border}`,
        borderRadius: 18, padding: 0, overflow:'hidden', cursor:'pointer',
        boxShadow: picked ? `0 4px 0 ${cat.color}` : '0 2px 0 rgba(27,18,48,0.06)',
        transform: picked ? 'translateY(-2px)' : 'none',
        transition:'transform .15s, box-shadow .15s, background .15s',
        fontFamily:'Nunito, sans-serif',
      }}>
      {picked && (
        <div style={{
          position:'absolute', top: 10, right: 10, zIndex: 2,
          width: 32, height: 32, borderRadius: 999, background: cat.color, color:'#fff',
          display:'flex', alignItems:'center', justifyContent:'center',
          fontFamily:'Fraunces, serif', fontWeight: 900, fontSize: 17,
          boxShadow:'0 2px 0 rgba(27,18,48,0.2)',
        }}>{slot}</div>
      )}
      <div style={{
        aspectRatio: '16/10',
        background: `url(${story.img}) center/cover, ${cat.color}`,
      }}/>
      <div style={{padding: '14px 16px 16px'}}>
        <div style={{
          display:'inline-flex', alignItems:'center', gap: 5,
          background: picked ? '#fff' : cat.bg, color: cat.color,
          padding:'3px 10px', borderRadius: 999, fontWeight: 800, fontSize: 11,
          marginBottom: 8,
        }}>
          <span style={{fontSize: 13}}>{cat.emoji}</span>{story.cat} · {story.mins} min
        </div>
        <div style={{
          fontFamily:'Fraunces, serif', fontWeight: 700, fontSize: 16,
          lineHeight: 1.2, color: KN.ink, letterSpacing:'-0.01em', marginBottom: 6,
        }}>{story.title}</div>
        <div style={{fontSize: 12.5, color: '#5a4a6e', lineHeight: 1.5, fontWeight: 600}}>
          {story.hook}
        </div>
      </div>
    </button>
  );
}

// ─────────────────────────────────────────────────────────────
// Screen 1 · PICK
// ─────────────────────────────────────────────────────────────
function PickScreen() {
  // Pre-set demo state: kid has picked ocean (1) and iowa (2), browsing for #3.
  const picks = ['ocean', 'iowa']; // ordered = slot 1, 2
  const total = picks.reduce((m, id) => m + (PICK_POOL.find(s => s.id === id)?.mins || 0), 0);
  const need = 3 - picks.length;

  return (
    <div style={{background: KN.cream, height:'100%', overflow:'hidden', display:'flex', flexDirection:'column'}}>
      <HeaderAfter/>

      {/* Picker hero — much smaller than the v2 hero, since the work
          happens in the grid below */}
      <div style={{
        background: `linear-gradient(135deg, ${KN.goldHi} 0%, #ffc0a8 100%)`,
        padding: '24px 28px', borderBottom: `2px solid #f0c8a8`,
      }}>
        <div style={{maxWidth: 1180, margin:'0 auto', display:'flex', alignItems:'center', gap: 24}}>
          <div style={{flex: 1}}>
            <div style={{fontFamily:'Nunito, sans-serif', fontWeight: 800, color:'#c14e2a', fontSize: 12, letterSpacing:'.12em', textTransform:'uppercase', marginBottom: 4}}>
              Saturday, Apr 25 · Hi Mia 👋
            </div>
            <h1 style={{fontFamily:'Fraunces, serif', fontWeight:700, fontSize: 38, lineHeight: 1.0, color: KN.ink, margin:'0 0 4px', letterSpacing:'-0.025em'}}>
              Pick your <span style={{background: KN.gold, padding:'0 10px', borderRadius:10, display:'inline-block', transform:'rotate(-1.5deg)'}}>3 stories</span> for today
            </h1>
            <div style={{fontFamily:'Fraunces, serif', fontStyle:'italic', fontWeight: 600, fontSize: 17, color:'#c14e2a', marginTop: 8, letterSpacing:'-0.01em'}}>
              Little daily, big magic.
            </div>
          </div>

          {/* Pick tracker — 3 slots that fill as kid taps */}
          <div style={{
            background:'#fff', borderRadius: 18, padding: '14px 18px', minWidth: 320,
            border:`2px solid #fff`, boxShadow:'0 3px 0 rgba(27,18,48,0.1)',
          }}>
            <div style={{display:'flex', justifyContent:'space-between', alignItems:'baseline', marginBottom: 10}}>
              <div style={{fontFamily:'Nunito, sans-serif', fontWeight: 900, fontSize: 12, color: KN.ink, letterSpacing:'.08em', textTransform:'uppercase'}}>Your 3</div>
              <div style={{fontSize: 11, color: KN.muted, fontWeight: 700}}>{total}/21 min</div>
            </div>
            <div style={{display:'flex', gap: 8}}>
              {[0,1,2].map(i => {
                const id = picks[i];
                const story = id ? PICK_POOL.find(s => s.id === id) : null;
                if (!story) {
                  return (
                    <div key={i} style={{
                      flex: 1, aspectRatio:'1', borderRadius: 12,
                      border:`2px dashed ${KN.border}`, background:'#fffaf0',
                      display:'flex', alignItems:'center', justifyContent:'center',
                      fontFamily:'Fraunces, serif', fontWeight: 800, fontSize: 22, color: KN.muted,
                    }}>{i + 1}</div>
                  );
                }
                const cat = KN.cats[story.cat];
                return (
                  <div key={i} style={{
                    flex: 1, aspectRatio:'1', borderRadius: 12, position:'relative',
                    background: `url(${story.img}) center/cover`,
                    border:`2px solid ${cat.color}`, boxShadow:`0 2px 0 ${cat.color}`,
                  }}>
                    <div style={{position:'absolute', top: 4, left: 4, width: 22, height: 22, borderRadius: 999, background: cat.color, color:'#fff', display:'flex', alignItems:'center', justifyContent:'center', fontFamily:'Fraunces, serif', fontWeight: 900, fontSize: 12}}>{i+1}</div>
                  </div>
                );
              })}
            </div>
            <div style={{marginTop: 12, fontSize: 12, color: need > 0 ? KN.muted : '#0e8d82', fontWeight: 700, display:'flex', alignItems:'center', gap: 6}}>
              {need > 0 ? <><span>👆</span> Tap {need} more story{need === 1 ? '' : 's'} below</> : <><span>✓</span> Ready to read!</>}
            </div>
          </div>
        </div>
      </div>

      {/* Filter chips — smaller than v2, just a filter, no longer a primary nav */}
      <div style={{maxWidth:1180, margin:'0 auto', padding:'18px 28px 0', display:'flex', alignItems:'center', gap: 8}}>
        <span style={{fontSize: 12, color: KN.muted, fontWeight: 700, marginRight: 4}}>Filter:</span>
        {[{l:'All', e:'✨', a:true}, {l:'News', e:'📰'}, {l:'Science', e:'🔬'}, {l:'Fun', e:'🎈'}].map(c => (
          <button key={c.l} style={{
            background: c.a ? KN.ink : '#fff', color: c.a ? '#fff' : KN.ink,
            border: c.a ? `2px solid ${KN.ink}` : `2px solid ${KN.border}`,
            borderRadius: 999, padding:'5px 12px', fontWeight: 800, fontSize: 12,
            display:'inline-flex', alignItems:'center', gap: 5,
          }}>
            <span>{c.e}</span>{c.l}
          </button>
        ))}
        <div style={{flex: 1}}/>
        <span style={{fontSize: 12, color: KN.muted, fontWeight: 700}}>9 stories today</span>
      </div>

      {/* Story grid */}
      <div style={{maxWidth:1180, margin:'0 auto', padding:'14px 28px 32px', flex: 1, overflow:'hidden'}}>
        <div style={{display:'grid', gridTemplateColumns:'repeat(3, 1fr)', gap: 14}}>
          {PICK_POOL.map(s => {
            const slot = picks.indexOf(s.id);
            return <StoryCard key={s.id} story={s} picked={slot >= 0} slot={slot + 1}/>;
          })}
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Screen 2 · TODAY (after pick — locked in, ready to read)
// ─────────────────────────────────────────────────────────────
function TodayScreen() {
  const picks = [
    PICK_POOL.find(s => s.id === 'ocean'),
    PICK_POOL.find(s => s.id === 'iowa'),
    PICK_POOL.find(s => s.id === 'yoyo'),
  ];
  const total = picks.reduce((m, s) => m + s.mins, 0);

  return (
    <div style={{background: KN.cream, height:'100%', overflow:'hidden', display:'flex', flexDirection:'column'}}>
      <HeaderAfter/>

      <div style={{maxWidth: 880, margin:'0 auto', padding:'40px 28px 28px', textAlign:'center'}}>
        <div style={{fontFamily:'Nunito, sans-serif', fontWeight: 800, color:'#c14e2a', fontSize: 12, letterSpacing:'.12em', textTransform:'uppercase', marginBottom: 8}}>
          Saturday, Apr 25 · Locked in
        </div>
        <h1 style={{fontFamily:'Fraunces, serif', fontWeight:700, fontSize: 44, lineHeight: 1.05, color: KN.ink, margin:'0 0 10px', letterSpacing:'-0.025em'}}>
          Your <span style={{background: KN.gold, padding:'0 12px', borderRadius:12, display:'inline-block', transform:'rotate(-1.5deg)'}}>21 minutes</span>
        </h1>
        <div style={{fontFamily:'Fraunces, serif', fontStyle:'italic', fontWeight: 600, fontSize: 19, color:'#c14e2a', letterSpacing:'-0.01em'}}>
          Little daily, big magic.
        </div>
      </div>

      <div style={{maxWidth: 880, margin:'0 auto', padding:'0 28px', flex: 1, display:'flex', flexDirection:'column', gap: 14}}>
        {picks.map((s, i) => {
          const cat = KN.cats[s.cat];
          return (
            <div key={s.id} style={{
              background:'#fff', borderRadius: 20, padding: 14,
              display:'flex', gap: 16, alignItems:'center',
              border:`2px solid ${KN.border}`, boxShadow:'0 3px 0 rgba(27,18,48,0.06)',
            }}>
              <div style={{
                width: 56, height: 56, borderRadius: 16, flexShrink: 0,
                background: cat.color, color:'#fff',
                display:'flex', alignItems:'center', justifyContent:'center',
                fontFamily:'Fraunces, serif', fontWeight: 900, fontSize: 28,
              }}>{i + 1}</div>
              <div style={{
                width: 88, height: 88, borderRadius: 14, flexShrink: 0,
                background: `url(${s.img}) center/cover`,
                border:`2px solid ${cat.color}`,
              }}/>
              <div style={{flex: 1, minWidth: 0}}>
                <div style={{display:'flex', gap: 8, alignItems:'center', marginBottom: 6}}>
                  <span style={{display:'inline-flex', alignItems:'center', gap: 4, background: cat.bg, color: cat.color, padding:'2px 9px', borderRadius: 999, fontWeight: 800, fontSize: 11}}>
                    <span>{cat.emoji}</span>{s.cat}
                  </span>
                  <span style={{fontSize: 12, color: KN.muted, fontWeight: 700}}>⏱ {s.mins} min</span>
                </div>
                <div style={{fontFamily:'Fraunces, serif', fontWeight: 700, fontSize: 19, color: KN.ink, letterSpacing:'-0.015em', lineHeight: 1.2}}>
                  {s.title}
                </div>
              </div>
              <div style={{
                width: 38, height: 38, borderRadius: 999, background:'#f0e8d8',
                display:'flex', alignItems:'center', justifyContent:'center', fontSize: 14, color: KN.muted,
                flexShrink: 0,
              }}>›</div>
            </div>
          );
        })}
      </div>

      <div style={{maxWidth: 880, margin:'0 auto', padding:'24px 28px 36px', display:'flex', alignItems:'center', gap: 14}}>
        <button style={{
          background: KN.ink, color:'#fff', border:'none', borderRadius: 16,
          padding:'15px 26px', fontWeight: 900, fontSize: 16,
          fontFamily:'Nunito, sans-serif', boxShadow:'0 5px 0 rgba(0,0,0,0.18)',
          flex: 1,
        }}>▶  Start with story 1</button>
        <button style={{
          background:'#fff', color: KN.ink, border:`2px solid ${KN.border}`, borderRadius: 16,
          padding:'14px 18px', fontWeight: 800, fontSize: 13,
          fontFamily:'Nunito, sans-serif',
        }}>⇆ Re-pick</button>
        <div style={{fontSize: 13, color: KN.muted, fontWeight: 700}}>{total} min total</div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Screen 3 · READ (re-uses the after reader, just slightly trimmed for the artboard)
// ─────────────────────────────────────────────────────────────
function ReadScreen() {
  return (
    <div style={{background: KN.cream, height:'100%', overflow:'hidden'}}>
      <ArticleReaderAfter/>
    </div>
  );
}

Object.assign(window, { PickScreen, TodayScreen, ReadScreen, PICK_POOL });
