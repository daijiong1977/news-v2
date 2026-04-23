// Article detail page — News Oh,Ye!
const { useState: useStateA, useMemo: useMemoA } = React;

function ArticlePage({ articleId, onBack, onComplete, progress, setProgress }) {
  const article = ARTICLES.find(a => a.id === articleId) || ARTICLES[0];
  const [tab, setTab] = useStateA('read');
  const [tabsVisited, setTabsVisited] = useStateA({ read: true });

  // Each step completion bumps progress by 25%: read→25, analyze→50, quiz→75, discuss→100
  const bumpProgress = (pct) => {
    setProgress(p => {
      const ap = p.articleProgress || {};
      const cur = ap[article.id] || 0;
      if (cur >= pct) return p;
      const next = { ...p, articleProgress: { ...ap, [article.id]: pct } };
      // When reaching 100, mark as fully read + add minutes
      if (pct === 100 && !p.readToday.includes(article.id)) {
        next.readToday = [...p.readToday, article.id];
        next.minutesToday = (p.minutesToday || 0) + article.readMins;
      }
      return next;
    });
  };
  const [expandedKw, setExpandedKw] = useStateA(null);
  const [quizIdx, setQuizIdx] = useStateA(0);
  const [quizAns, setQuizAns] = useStateA([]);
  const [quizShow, setQuizShow] = useStateA(false);
  const [confetti, setConfetti] = useStateA(false);

  const stages = [
    { id:'read', label:'Read & Words', emoji:'📖' },
    { id:'analyze', label:'Background', emoji:'🔍' },
    { id:'quiz', label:'Quiz', emoji:'🎯' },
    { id:'discuss', label:'Think', emoji:'💭' },
  ];

  const catColor = getCatColor(article.category);

  // Build paragraphs with keyword highlighting markup
  const paragraphs = useMemoA(() => {
    const sentences = article.summary.split(/(?<=\.)\s+/);
    const groups = [];
    for (let i=0; i<sentences.length; i+=3) groups.push(sentences.slice(i, i+3).join(' '));
    return groups;
  }, [article.id]);

  const switchTab = (id) => {
    setTab(id);
    setTabsVisited(v => ({...v, [id]: true}));
  };

  return (
    <div style={{background:'#fff9ef', minHeight:'100vh'}}>
      {/* ——— Top bar ——— */}
      <div style={{background:'#fff9ef', borderBottom:'2px solid #f0e8d8', position:'sticky', top:0, zIndex:30}}>
        <div style={{maxWidth:1180, margin:'0 auto', padding:'14px 28px', display:'flex', alignItems:'center', gap:14}}>
          <button onClick={onBack} style={{
            background:'#fff', border:'2px solid #f0e8d8', borderRadius:14, padding:'8px 14px',
            fontWeight:800, fontSize:14, cursor:'pointer', color:'#1b1230',
            display:'inline-flex', alignItems:'center', gap:6,
          }}>← Back</button>
          <div style={{display:'flex', alignItems:'center', gap:10}}>
            <OhYeLogo size={32}/>
            <div style={{fontFamily:'Fraunces, serif', fontWeight:900, fontSize:18, color:'#1b1230'}}>News Oh,Ye!</div>
          </div>
          <div style={{flex:1}}/>
          <div style={{display:'flex', alignItems:'center', gap:6}}>
            {stages.map((s, i) => {
              const curPct = (progress.articleProgress || {})[article.id] || 0;
              const stepPct = (i + 1) * 25;
              const stepDone = curPct >= stepPct;
              return (
                <React.Fragment key={s.id}>
                  <button onClick={()=>switchTab(s.id)} style={{
                    background: tab===s.id ? catColor : (stepDone ? '#d4f3ef' : '#fff'),
                    color: tab===s.id ? '#fff' : (stepDone ? '#0e8d82' : '#6b5c80'),
                    border: `2px solid ${tab===s.id ? catColor : (stepDone ? '#8fd6cd' : '#f0e8d8')}`,
                    borderRadius:999, padding:'6px 12px', fontWeight:800, fontSize:13, cursor:'pointer',
                    display:'inline-flex', alignItems:'center', gap:5,
                  }}>
                    <span>{stepDone && tab !== s.id ? '✓' : s.emoji}</span>{s.label}
                  </button>
                  {i < stages.length-1 && <div style={{width:8, height:2, background: stepDone ? '#8fd6cd' : '#f0e8d8', borderRadius:2}}/>}
                </React.Fragment>
              );
            })}
          </div>
        </div>
      </div>

      <div style={{maxWidth:1180, margin:'0 auto', padding:'24px 28px 60px'}}>

        {/* ——— Title block ——— */}
        <div style={{display:'grid', gridTemplateColumns:'1.1fr 1fr', gap:28, alignItems:'stretch', marginBottom:24}}>
          <div>
            <div style={{display:'flex', gap:8, marginBottom:14, flexWrap:'wrap'}}>
              <CatChip cat={article.category}/>
              <XpBadge xp={article.xp}/>
            </div>
            <h1 style={{fontFamily:'Fraunces, serif', fontWeight:900, fontSize:40, lineHeight:1.05, color:'#1b1230', margin:'0 0 14px', letterSpacing:'-0.02em'}}>{article.title}</h1>
            <div style={{display:'flex', gap:14, color:'#6b5c80', fontSize:13, fontWeight:700, flexWrap:'wrap'}}>
              <span>📰 {article.source}</span><span>·</span>
              <span>{article.time}</span><span>·</span>
              <span>⏱ {article.readMins} min read</span>
            </div>
          </div>
          <div style={{borderRadius:22, overflow:'hidden', border:`3px solid ${catColor}`, background:`url(${article.image}) center/cover`, minHeight:220, position:'relative'}}>
            <div style={{position:'absolute', bottom:12, right:12, background:'rgba(255,255,255,0.9)', padding:'6px 12px', borderRadius:999, fontSize:11, fontWeight:700, color:'#6b5c80'}}>
              📷 {article.source}
            </div>
          </div>
        </div>

        {/* ——— TABS CONTENT ——— */}
        {tab === 'read' && (
          <ReadAndWordsTab
            article={article}
            paragraphs={paragraphs}
            expanded={expandedKw}
            setExpanded={setExpandedKw}
            onFinish={() => { bumpProgress(25); switchTab('analyze'); }}
          />
        )}

        {tab === 'analyze' && (
          <AnalyzeTab article={article} paragraphs={paragraphs} onNext={()=>{ bumpProgress(50); switchTab('quiz'); }} />
        )}

        {tab === 'quiz' && (
          <QuizTab
            article={article} paragraphs={paragraphs}
            quizIdx={quizIdx} setQuizIdx={setQuizIdx}
            quizAns={quizAns} setQuizAns={setQuizAns}
            quizShow={quizShow} setQuizShow={setQuizShow}
            onFinish={() => { bumpProgress(75); setConfetti(true); setTimeout(()=>setConfetti(false), 1800); switchTab('discuss'); }}
          />
        )}

        {tab === 'discuss' && (
          <DiscussTab article={article} paragraphs={paragraphs} onDone={()=>{ bumpProgress(100); onComplete(); }} />
        )}
      </div>

      {confetti && <Confetti/>}
    </div>
  );
}

// ——— Highlight keywords in a text string ———
function highlightText(text, keywords, catColor) {
  if (!keywords || !keywords.length) return [text];
  const parts = [];
  let working = text;
  const termMap = {};
  keywords.forEach(k => { termMap[k.term.toLowerCase()] = k; });
  const terms = keywords.map(k => k.term).sort((a,b)=>b.length-a.length);
  const pattern = new RegExp(`\\b(${terms.map(t=>t.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')).join('|')})\\b`, 'gi');
  let last = 0, m;
  const result = [];
  let idx = 0;
  while ((m = pattern.exec(text)) !== null) {
    if (m.index > last) result.push(text.substring(last, m.index));
    const kw = termMap[m[0].toLowerCase()];
    result.push(<KwTip key={`kw-${idx++}`} text={m[0]} def={kw?.def || ''} color={catColor}/>);
    last = m.index + m[0].length;
  }
  if (last < text.length) result.push(text.substring(last));
  return result;
}

function KwTip({ text, def, color }) {
  const [show, setShow] = useStateA(false);
  return (
    <span style={{position:'relative', display:'inline-block'}}
          onMouseEnter={()=>setShow(true)} onMouseLeave={()=>setShow(false)}>
      <span style={{
        color, fontWeight:800, borderBottom:`2px dotted ${color}`,
        cursor:'help', padding:'0 1px',
      }}>{text}</span>
      {show && (
        <span style={{
          position:'absolute', bottom:'calc(100% + 8px)', left:'50%', transform:'translateX(-50%)',
          background:'#1b1230', color:'#fff', padding:'8px 12px', borderRadius:10,
          fontSize:12, fontWeight:600, whiteSpace:'normal', minWidth:180, maxWidth:260, zIndex:40,
          lineHeight:1.4, pointerEvents:'none',
          boxShadow:'0 6px 20px rgba(27,18,48,0.25)',
        }}>
          <b style={{color:'#ffc83d'}}>{text}:</b> {def}
        </span>
      )}
    </span>
  );
}

// ——————— READ & WORDS TAB (combined) ———————
function ReadAndWordsTab({ article, paragraphs, expanded, setExpanded, onFinish }) {
  const catColor = getCatColor(article.category);
  return (
    <div style={{display:'grid', gridTemplateColumns:'1.6fr 1fr', gap:24}}>
      <div style={{background:'#fff', borderRadius:22, padding:'30px 34px', border:'2px solid #f0e8d8'}}>
        <div style={{display:'flex', alignItems:'center', gap:10, marginBottom:18, paddingBottom:14, borderBottom:'2px dashed #f0e8d8'}}>
          <div style={{fontSize:26}}>📖</div>
          <h2 style={{fontFamily:'Fraunces, serif', fontWeight:800, fontSize:22, color:'#1b1230', margin:0}}>The Story</h2>
          <div style={{flex:1}}/>
          <div style={{fontSize:12, color:'#9a8d7a', fontWeight:700}}>Hover on the colored words!</div>
        </div>
        {paragraphs.map((p, i) => (
          <p key={i} style={{fontSize:18, lineHeight:1.7, color:'#2a1f3d', marginBottom:16, fontFamily:'Nunito, sans-serif'}}>
            {i === 0 && <span style={{float:'left', fontSize:48, fontFamily:'Fraunces, serif', fontWeight:900, lineHeight:.9, marginRight:8, marginTop:4, color: catColor}}>{p[0]}</span>}
            {highlightText(i === 0 ? p.substring(1) : p, article.keywords, catColor)}
          </p>
        ))}
        <div style={{display:'flex', justifyContent:'center', marginTop:24, paddingTop:20, borderTop:'2px dashed #f0e8d8'}}>
          <BigButton onClick={onFinish} bg="#17b3a6" color="#fff">
            ✓ I read it! Next: Background →
          </BigButton>
        </div>
      </div>

      <aside style={{display:'flex', flexDirection:'column', gap:14}}>
        <div style={{background:'#fff', border:'2px solid #f0e8d8', borderRadius:18, padding:18}}>
          <div style={{display:'flex', alignItems:'center', gap:8, marginBottom:12}}>
            <div style={{fontSize:22}}>🔑</div>
            <div style={{fontFamily:'Fraunces, serif', fontWeight:800, fontSize:17, color:'#1b1230'}}>Word Treasure</div>
          </div>
          <div style={{display:'flex', flexDirection:'column', gap:8}}>
            {article.keywords.map((k, i) => (
              <KeywordCard key={i} kw={k} idx={i} expanded={expanded===i} onToggle={()=>setExpanded(expanded===i ? null : i)}/>
            ))}
          </div>
        </div>
        <div style={{background:'#fff', border:'2px solid #f0e8d8', borderRadius:18, padding:16}}>
          <div style={{fontFamily:'Fraunces, serif', fontWeight:800, fontSize:15, marginBottom:10, color:'#1b1230'}}>🎧 Reading tools</div>
          <button style={toolBtn}>🔊 Read aloud</button>
          <button style={toolBtn}>🔤 Bigger text</button>
          <button style={toolBtn}>🔖 Save for later</button>
        </div>
      </aside>
    </div>
  );
}

const toolBtn = {
  width:'100%', textAlign:'left', background:'#fff9ef', border:'1.5px solid #f0e8d8',
  borderRadius:12, padding:'9px 12px', marginBottom:6, fontWeight:700, fontSize:13,
  cursor:'pointer', color:'#1b1230', display:'flex', alignItems:'center', gap:8,
  fontFamily:'Nunito, sans-serif',
};

function KeywordCard({ kw, idx, expanded, onToggle }) {
  const palette = [
    {bg:'#ffece8', c:'#ff6b5b'}, {bg:'#e0f6f3', c:'#17b3a6'}, {bg:'#eee5ff', c:'#9061f9'},
    {bg:'#fff4c2', c:'#c9931f'}, {bg:'#ffe4ef', c:'#ff6ba0'},
  ][idx % 5];
  return (
    <button onClick={onToggle} style={{
      background: expanded ? palette.c : palette.bg,
      color: expanded ? '#fff' : '#1b1230',
      border:'none', borderRadius:12, padding:'12px 14px', textAlign:'left',
      cursor:'pointer', display:'flex', flexDirection:'column', gap:4,
      transition:'all .2s',
      boxShadow:'0 2px 0 rgba(27,18,48,0.06)',
    }}>
      <div style={{fontFamily:'Fraunces, serif', fontWeight:800, fontSize:16, color: expanded ? '#fff' : palette.c}}>{kw.term}</div>
      {expanded && <div style={{fontSize:12, lineHeight:1.4}}>{kw.def}</div>}
      {!expanded && <div style={{fontSize:11, fontWeight:700, opacity:.65}}>Tap to reveal →</div>}
    </button>
  );
}

// ——————— ANALYZE TAB (Background + Structure, with article reference) ———————
function AnalyzeTab({ article, paragraphs, onNext }) {
  const [articleOpen, setArticleOpen] = useStateA(false);
  const catColor = getCatColor(article.category);

  const bgText = `This story comes from ${article.source}, a ${article.category === 'Science' ? 'science source' : 'news source'} that covers stories for kids. Reporters gather facts by talking to scientists, officials, and people involved, then write what they learned. When you read, think about WHO is doing something, WHAT is happening, WHERE it takes place, WHY it matters, and WHEN it happened. Learning to spot these parts helps you become a sharp news reader!`;

  const who = article.title.split(' ').slice(0, 3).join(' ') + '…';
  const what = article.summary.split('.')[0] + '.';
  const where = article.category === 'Science' ? 'In labs, field studies, or around the world' : 'Mentioned in the story';
  const why = `It matters because it affects ${article.category === 'Science' ? 'how we understand the world' : 'people, animals, or the planet'}.`;

  return (
    <div style={{display:'grid', gridTemplateColumns:'1fr 1fr', gap:20}}>
      {/* Left: Background */}
      <div style={{background:'#fff', borderRadius:22, padding:'26px 30px', border:'2px solid #f0e8d8'}}>
        <div style={{display:'flex', alignItems:'center', gap:10, marginBottom:14}}>
          <div style={{fontSize:26}}>🧭</div>
          <h2 style={{fontFamily:'Fraunces, serif', fontWeight:800, fontSize:20, color:'#1b1230', margin:0}}>Background you need</h2>
        </div>
        <p style={{fontSize:15, lineHeight:1.7, color:'#2a1f3d', margin:0}}>
          {highlightText(bgText, article.keywords, catColor)}
        </p>
      </div>

      {/* Right: 5W Structure */}
      <div style={{background:'#fff', borderRadius:22, padding:'26px 30px', border:'2px solid #f0e8d8'}}>
        <div style={{display:'flex', alignItems:'center', gap:10, marginBottom:14}}>
          <div style={{fontSize:26}}>🔍</div>
          <h2 style={{fontFamily:'Fraunces, serif', fontWeight:800, fontSize:20, color:'#1b1230', margin:0}}>Break it down</h2>
        </div>
        <div style={{display:'flex', flexDirection:'column', gap:10}}>
          <WRow label="Who" emoji="👤" value={who}/>
          <WRow label="What" emoji="💡" value={what}/>
          <WRow label="Where" emoji="📍" value={where}/>
          <WRow label="Why" emoji="❓" value={why}/>
        </div>
      </div>

      {/* Full-width: Article reference collapsible */}
      <div style={{gridColumn:'span 2', background:'#fff9ef', border:'2px solid #f0e8d8', borderRadius:22, padding:0, overflow:'hidden'}}>
        <button onClick={()=>setArticleOpen(!articleOpen)} style={{
          width:'100%', background:'transparent', border:'none', padding:'16px 22px',
          display:'flex', alignItems:'center', gap:10, cursor:'pointer', color:'#1b1230',
          fontFamily:'Nunito, sans-serif',
        }}>
          <div style={{fontSize:20}}>📖</div>
          <div style={{fontFamily:'Fraunces, serif', fontWeight:800, fontSize:16, flex:1, textAlign:'left'}}>
            {articleOpen ? 'Hide the story' : 'Peek at the story again'}
          </div>
          <div style={{fontSize:20, transform: articleOpen ? 'rotate(180deg)' : 'rotate(0)', transition:'transform .2s'}}>⌄</div>
        </button>
        {articleOpen && (
          <div style={{padding:'0 22px 22px', borderTop:'2px dashed #f0e8d8'}}>
            <div style={{paddingTop:16}}>
              {paragraphs.map((p, i) => (
                <p key={i} style={{fontSize:15, lineHeight:1.65, color:'#2a1f3d', marginBottom:12}}>
                  {highlightText(p, article.keywords, catColor)}
                </p>
              ))}
            </div>
          </div>
        )}
      </div>

      <div style={{gridColumn:'span 2', display:'flex', justifyContent:'center', marginTop:8}}>
        <BigButton bg="#ffc83d" color="#1b1230" onClick={onNext}>Ready for the quiz →</BigButton>
      </div>
    </div>
  );
}

function WRow({ label, emoji, value }) {
  return (
    <div style={{display:'flex', gap:12, background:'#fff9ef', padding:'10px 14px', borderRadius:12, border:'1.5px solid #f0e8d8'}}>
      <div style={{fontSize:22}}>{emoji}</div>
      <div style={{flex:1}}>
        <div style={{fontSize:11, fontWeight:800, color:'#9061f9', letterSpacing:'.08em', textTransform:'uppercase'}}>{label}</div>
        <div style={{fontSize:14, color:'#1b1230', lineHeight:1.4, fontWeight:600}}>{value}</div>
      </div>
    </div>
  );
}

// ——————— QUIZ TAB (split view with article reference) ———————
function QuizTab({ article, paragraphs, quizIdx, setQuizIdx, quizAns, setQuizAns, quizShow, setQuizShow, onFinish }) {
  const q = article.quiz[quizIdx];
  const done = quizAns.length === article.quiz.length && quizAns.every(a => a !== undefined);
  const correct = quizAns.filter((a,i) => a === article.quiz[i].a).length;
  const catColor = getCatColor(article.category);

  if (done) {
    return (
      <div style={{background:'#fff', borderRadius:22, padding:'44px', border:'2px solid #f0e8d8', textAlign:'center', maxWidth:560, margin:'0 auto'}}>
        <div style={{fontSize:64, marginBottom:8}}>🎉</div>
        <h2 style={{fontFamily:'Fraunces, serif', fontWeight:900, fontSize:36, color:'#1b1230', margin:'0 0 6px'}}>
          {correct === article.quiz.length ? 'Perfect!' : correct >= article.quiz.length/2 ? 'Nice work!' : 'Good try!'}
        </h2>
        <p style={{fontSize:16, color:'#6b5c80', margin:'0 0 18px'}}>
          You got <b>{correct}</b> out of <b>{article.quiz.length}</b> right.
        </p>
        <div style={{marginBottom:20}}><StarMeter filled={correct} total={article.quiz.length}/></div>
        <div style={{display:'inline-flex', gap:10, padding:'10px 16px', background:'#fff4c2', borderRadius:14, marginBottom:28}}>
          <span style={{fontWeight:800, color:'#8a6d00'}}>⭐ +{article.xp} XP earned!</span>
        </div>
        <div style={{display:'flex', justifyContent:'center', gap:12}}>
          <BigButton bg="#fff" color="#1b1230" onClick={()=>{ setQuizAns([]); setQuizIdx(0); setQuizShow(false);}} style={{boxShadow:'0 4px 0 rgba(0,0,0,0.08)', border:'2px solid #f0e8d8'}}>🔁 Try again</BigButton>
          <BigButton bg="#17b3a6" color="#fff" onClick={onFinish}>Next: Think time →</BigButton>
        </div>
      </div>
    );
  }

  return (
    <div style={{display:'grid', gridTemplateColumns:'1fr 1fr', gap:24}}>
      {/* Left: article reference (scrollable, sticky) */}
      <div style={{background:'#fff', borderRadius:22, padding:'24px 28px', border:'2px solid #f0e8d8', position:'sticky', top:90, maxHeight:'calc(100vh - 110px)', overflow:'auto'}}>
        <div style={{display:'flex', alignItems:'center', gap:10, marginBottom:14, paddingBottom:12, borderBottom:'2px dashed #f0e8d8'}}>
          <div style={{fontSize:22}}>📖</div>
          <div style={{fontFamily:'Fraunces, serif', fontWeight:800, fontSize:17, color:'#1b1230'}}>Look back at the story</div>
        </div>
        <div>
          {paragraphs.map((p, i) => (
            <p key={i} style={{fontSize:14.5, lineHeight:1.65, color:'#2a1f3d', marginBottom:12}}>
              {highlightText(p, article.keywords, catColor)}
            </p>
          ))}
        </div>
      </div>

      {/* Right: quiz */}
      <div style={{background:'#fff', borderRadius:22, padding:'28px 32px', border:'2px solid #f0e8d8'}}>
        <div style={{display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:16}}>
          <div style={{display:'flex', alignItems:'center', gap:10}}>
            <div style={{fontSize:24}}>🎯</div>
            <h2 style={{fontFamily:'Fraunces, serif', fontWeight:800, fontSize:20, color:'#1b1230', margin:0}}>Quick quiz</h2>
          </div>
          <div style={{fontSize:13, fontWeight:800, color:'#6b5c80'}}>Q {quizIdx+1}/{article.quiz.length}</div>
        </div>
        <div style={{height:8, background:'#f0e8d8', borderRadius:999, marginBottom:22, overflow:'hidden'}}>
          <div style={{height:'100%', width:`${(quizIdx/article.quiz.length)*100}%`, background:'#17b3a6', borderRadius:999, transition:'width .4s'}}/>
        </div>

        <h3 style={{fontFamily:'Fraunces, serif', fontWeight:800, fontSize:22, color:'#1b1230', marginBottom:18, lineHeight:1.25}}>{q.q}</h3>

        <div style={{display:'flex', flexDirection:'column', gap:10}}>
          {q.options.map((opt, i) => {
            const picked = quizShow && quizAns[quizIdx] === i;
            const isRight = quizShow && i === q.a;
            const isWrong = quizShow && picked && i !== q.a;
            return (
              <button key={i} onClick={()=>{
                if (quizShow) return;
                const newAns = [...quizAns]; newAns[quizIdx] = i;
                setQuizAns(newAns); setQuizShow(true);
              }} style={{
                background: isRight ? '#e0f6f3' : isWrong ? '#ffe4ef' : '#fff9ef',
                border:`2px solid ${isRight ? '#17b3a6' : isWrong ? '#ff6b5b' : '#f0e8d8'}`,
                borderRadius:14, padding:'13px 16px', textAlign:'left', cursor: quizShow ? 'default' : 'pointer',
                fontSize:14.5, fontWeight:700, color:'#1b1230', fontFamily:'Nunito, sans-serif',
                display:'flex', alignItems:'center', gap:12, transition:'all .15s',
              }}>
                <div style={{
                  width:26, height:26, borderRadius:8, background: isRight ? '#17b3a6' : isWrong ? '#ff6b5b' : '#fff',
                  color: (isRight||isWrong) ? '#fff' : '#1b1230', border:'2px solid #f0e8d8',
                  display:'flex', alignItems:'center', justifyContent:'center', fontWeight:900, fontSize:12, flexShrink:0,
                }}>{isRight ? '✓' : isWrong ? '✗' : String.fromCharCode(65+i)}</div>
                {opt}
              </button>
            );
          })}
        </div>

        {quizShow && (
          <div style={{marginTop:18, display:'flex', justifyContent:'flex-end'}}>
            <BigButton bg="#ffc83d" color="#1b1230" onClick={()=>{ setQuizShow(false); setQuizIdx(quizIdx+1); }}>
              {quizIdx+1 < article.quiz.length ? 'Next question →' : 'See results →'}
            </BigButton>
          </div>
        )}
      </div>
    </div>
  );
}

// ——————— DISCUSS TAB ———————
function DiscussTab({ article, paragraphs, onDone }) {
  const [answer, setAnswer] = useStateA('');
  const [submitted, setSubmitted] = useStateA(false);
  const [articleOpen, setArticleOpen] = useStateA(false);
  const catColor = getCatColor(article.category);

  return (
    <div style={{display:'grid', gridTemplateColumns:'1fr 320px', gap:24}}>
      <div style={{background:'#fff', borderRadius:22, padding:'28px 32px', border:'2px solid #f0e8d8'}}>
        <div style={{display:'flex', alignItems:'center', gap:10, marginBottom:16}}>
          <div style={{fontSize:26}}>💭</div>
          <h2 style={{fontFamily:'Fraunces, serif', fontWeight:800, fontSize:22, color:'#1b1230', margin:0}}>Think & share</h2>
        </div>

        {article.discussion.map((d, i) => (
          <div key={i} style={{background:'#fff4c2', borderRadius:16, padding:'16px 18px', marginBottom:14, border:'2px solid #ffe28a'}}>
            <div style={{fontSize:11, fontWeight:800, color:'#8a6d00', letterSpacing:'.1em', textTransform:'uppercase', marginBottom:6}}>Question {i+1}</div>
            <div style={{fontFamily:'Fraunces, serif', fontWeight:700, fontSize:18, color:'#1b1230', lineHeight:1.3}}>{d}</div>
          </div>
        ))}

        <label style={{display:'block', fontWeight:800, fontSize:13, color:'#6b5c80', marginBottom:8, letterSpacing:'.05em', textTransform:'uppercase', marginTop:8}}>Your thoughts</label>
        <textarea value={answer} onChange={e=>setAnswer(e.target.value)} placeholder="Type your answer here..." rows={4}
          style={{width:'100%', border:'2px solid #f0e8d8', borderRadius:14, padding:'12px 14px', fontSize:14.5, fontFamily:'Nunito, sans-serif', resize:'vertical', outline:'none', background:'#fff9ef', color:'#1b1230'}}/>
        <div style={{display:'flex', justifyContent:'space-between', alignItems:'center', marginTop:12, flexWrap:'wrap', gap:10}}>
          <div style={{fontSize:12, color:'#9a8d7a'}}>💡 Your answers are private — just for you!</div>
          {submitted ? (
            <BigButton bg="#17b3a6" color="#fff" onClick={onDone}>✓ All done! Back to home →</BigButton>
          ) : (
            <BigButton bg="#ffc83d" color="#1b1230" onClick={()=>setSubmitted(true)} disabled={!answer.trim()}>Save my answer</BigButton>
          )}
        </div>

        <div style={{marginTop:18, background:'#fff9ef', border:'2px solid #f0e8d8', borderRadius:16, overflow:'hidden'}}>
          <button onClick={()=>setArticleOpen(!articleOpen)} style={{width:'100%', background:'transparent', border:'none', padding:'12px 16px', display:'flex', alignItems:'center', gap:8, cursor:'pointer', color:'#1b1230', fontFamily:'Nunito, sans-serif'}}>
            <div style={{fontSize:18}}>📖</div>
            <div style={{fontFamily:'Fraunces, serif', fontWeight:800, fontSize:14, flex:1, textAlign:'left'}}>{articleOpen ? 'Hide story' : 'Peek at the story again'}</div>
            <div style={{fontSize:16, transform: articleOpen ? 'rotate(180deg)' : 'rotate(0)'}}>⌄</div>
          </button>
          {articleOpen && (
            <div style={{padding:'0 16px 14px', borderTop:'2px dashed #f0e8d8'}}>
              <div style={{paddingTop:12}}>
                {paragraphs.map((p, i) => (
                  <p key={i} style={{fontSize:13.5, lineHeight:1.6, color:'#2a1f3d', marginBottom:10}}>
                    {highlightText(p, article.keywords, catColor)}
                  </p>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      <aside style={{display:'flex', flexDirection:'column', gap:14}}>
        <div style={{background:'linear-gradient(135deg, #ffd3c2, #ffc83d)', border:'2px solid #ffb98a', borderRadius:18, padding:20}}>
          <div style={{fontSize:36, marginBottom:4}}>🏆</div>
          <div style={{fontFamily:'Fraunces, serif', fontWeight:800, fontSize:20, color:'#1b1230', marginBottom:6}}>You did it!</div>
          <div style={{fontSize:14, color:'#3a2a4a', lineHeight:1.5, marginBottom:14}}>That's one more story on your reading journey. 🌟</div>
          <div style={{background:'rgba(255,255,255,0.7)', borderRadius:12, padding:12, fontSize:13, fontWeight:700, color:'#1b1230'}}>
            <div style={{display:'flex', justifyContent:'space-between', marginBottom:4}}><span>Minutes</span><b>{article.readMins} min</b></div>
            <div style={{display:'flex', justifyContent:'space-between', marginBottom:4}}><span>Words learned</span><b>{article.keywords.length}</b></div>
            <div style={{display:'flex', justifyContent:'space-between'}}><span>XP earned</span><b>+{article.xp}</b></div>
          </div>
        </div>
        <div style={{background:'#fff', border:'2px solid #f0e8d8', borderRadius:18, padding:18}}>
          <div style={{fontFamily:'Fraunces, serif', fontWeight:800, fontSize:15, marginBottom:8, color:'#1b1230'}}>💬 Share with a grown-up</div>
          <div style={{fontSize:13, color:'#6b5c80', lineHeight:1.5}}>Talk about one of these questions with a parent or friend. You'll remember more by saying it out loud!</div>
        </div>
      </aside>
    </div>
  );
}

function Confetti() {
  const bits = Array.from({length: 40}).map((_,i) => ({
    left: Math.random()*100, delay: Math.random()*0.4, rot: Math.random()*360,
    color: ['#ff6b5b','#ffc83d','#17b3a6','#9061f9','#ff6ba0'][i%5],
  }));
  return (
    <div style={{position:'fixed', inset:0, pointerEvents:'none', zIndex:50, overflow:'hidden'}}>
      {bits.map((b, i) => (
        <div key={i} style={{
          position:'absolute', left:`${b.left}%`, top:-20, width:10, height:14, background:b.color,
          animation:`confetti 1.8s ${b.delay}s ease-in forwards`, transform:`rotate(${b.rot}deg)`, borderRadius:2,
        }}/>
      ))}
      <style>{`@keyframes confetti { to { top: 110vh; transform: rotate(720deg); } }`}</style>
    </div>
  );
}

Object.assign(window, { ArticlePage });
