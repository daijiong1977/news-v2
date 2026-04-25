// Article detail page — News Oh,Ye!
const { useState: useStateA, useMemo: useMemoA, useEffect: useEffectA } = React;

// Format an ISO-8601 timestamp as "Apr 24, 2026". Returns "" on bad input
// so callers can safely conditionally render.
function formatDate(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  if (isNaN(d.getTime())) return '';
  return d.toLocaleDateString('en-US', { month:'short', day:'numeric', year:'numeric' });
}

function ArticlePage({ articleId, onBack, onComplete, progress, setProgress }) {
  const baseArticle = ARTICLES.find(a => a.id === articleId) || ARTICLES[0];
  const [tab, setTab] = useStateA('read');
  const [tabsVisited, setTabsVisited] = useStateA({ read: true });
  const [detail, setDetail] = useStateA(null);
  const [detailError, setDetailError] = useStateA(null);

  // Lazy-fetch v1 detail payload for this article. Chinese cards (noDetail) are
  // routed away before reaching this page, so we only fetch English variants.
  useEffectA(() => {
    if (!baseArticle || baseArticle.noDetail) { setDetail(null); return; }
    let cancelled = false;
    setDetail(null);
    setDetailError(null);
    const payloadLevel = baseArticle.level === 'Sprout' ? 'easy' : 'middle';
    // Archive mode (baseArticle.archiveDate set) fetches from Supabase dated
    // prefix; today's content stays local.
    const detailBase = baseArticle.archiveDate
      ? `${window.ARCHIVE_BASE}/${baseArticle.archiveDate}/article_payloads`
      : 'article_payloads';
    const url = `${detailBase}/payload_${baseArticle.storyId}/${payloadLevel}.json`;
    fetch(url)
      .then(r => r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)))
      .then(d => {
        if (cancelled) return;
        // Map v1 field shapes to the prototype's expected shape.
        // v1 detail pattern: full body lives in `summary`; `background_read` is
        // supplementary context (for the Analyze tab), not the body.
        const bgRead = Array.isArray(d.background_read)
          ? d.background_read.join('\n\n')
          : (typeof d.background_read === 'string' ? d.background_read : '');
        const mapped = {
          body: d.summary || '',                        // FULL regenerated article body
          summary: d.summary || baseArticle.summary,
          backgroundRead: bgRead,                       // shown on Analyze tab
          whyItMatters: d.why_it_matters || '',
          keywords: (d.keywords || []).map(k => ({ term: k.term, def: k.explanation })),
          quiz: (d.questions || []).map(q => {
            const idx = q.options.findIndex(opt => opt === q.correct_answer);
            return { q: q.question, options: q.options, a: Math.max(0, idx) };
          }),
          discussion: (d.perspectives || []).map(p => `${p.perspective}: ${p.description}`),
          articleStructure: Array.isArray(d.Article_Structure) ? d.Article_Structure : [],
        };
        setDetail(mapped);
      })
      .catch(e => { if (!cancelled) { console.warn('[article] detail fetch failed', url, e); setDetailError(e); } });
    return () => { cancelled = true; };
  }, [articleId]);

  // Merged article object: prefer detail fields when loaded, fall back to the
  // listing-level stub so the title block + header render even before detail
  // arrives.
  const article = useMemoA(() => {
    const d = detail || {};
    return {
      ...baseArticle,
      summary: d.summary || baseArticle.summary,
      body: d.body || '',
      backgroundRead: d.backgroundRead || '',
      whyItMatters: d.whyItMatters || '',
      keywords: d.keywords || [],
      quiz: d.quiz || [],
      discussion: d.discussion || [],
      articleStructure: d.articleStructure || [],
    };
  }, [articleId, detail]);

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

  // Build paragraphs for the Read tab from detail.body (preferred) or a
  // sentence-grouped fallback over the summary while detail is loading.
  const paragraphs = useMemoA(() => {
    const text = article.body || article.summary || '';
    if (article.body) {
      // Detail body has explicit paragraph breaks ("\n\n") we can honor.
      const paras = text.split(/\n\n+/).map(s => s.trim()).filter(Boolean);
      if (paras.length > 0) return paras;
    }
    // Fallback: group sentences into 3-sentence paragraphs (prototype behavior).
    const sentences = text.split(/(?<=\.)\s+/);
    const groups = [];
    for (let i=0; i<sentences.length; i+=3) groups.push(sentences.slice(i, i+3).join(' '));
    return groups;
  }, [article.id, article.body, article.summary]);

  const switchTab = (id) => {
    setTab(id);
    setTabsVisited(v => ({...v, [id]: true}));
  };

  // Block tabs until detail is loaded. Header/title block still render so the
  // user gets feedback while the payload arrives.
  const detailReady = !!detail;

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
            <div style={{display:'flex', gap:14, color:'#6b5c80', fontSize:13, fontWeight:700, flexWrap:'wrap', alignItems:'center'}}>
              <span>📰 {article.source}</span><span>·</span>
              <span>⏱ {article.readMins} min read</span>
              {article.minedAt && (<>
                <span>·</span>
                <span title={`Mined ${article.minedAt}${article.sourcePublishedAt ? ' · source published ' + article.sourcePublishedAt : ''}`}>
                  🗞 Mined {formatDate(article.minedAt)}
                </span>
              </>)}
            </div>
          </div>
          <div style={{borderRadius:22, overflow:'hidden', border:`3px solid ${catColor}`, background:`url(${article.image}) center/cover`, minHeight:220, position:'relative'}}>
            <div style={{position:'absolute', bottom:12, right:12, background:'rgba(255,255,255,0.9)', padding:'6px 12px', borderRadius:999, fontSize:11, fontWeight:700, color:'#6b5c80'}}>
              📷 {article.source}
            </div>
          </div>
        </div>

        {/* ——— TABS CONTENT ——— */}
        {!detailReady && !detailError && (
          <div style={{background:'#fff', borderRadius:22, padding:'40px 32px', border:'2px dashed #f0e8d8', textAlign:'center', color:'#6b5c80'}}>
            <div style={{fontSize:36, marginBottom:10}}>📡</div>
            <div style={{fontFamily:'Fraunces, serif', fontWeight:800, fontSize:20, color:'#1b1230', marginBottom:6}}>Loading the full story…</div>
            <div style={{fontSize:13}}>Fetching keywords, quiz, and background.</div>
          </div>
        )}
        {detailError && (
          <div style={{background:'#fff', borderRadius:22, padding:'40px 32px', border:'2px solid #ffb98a', textAlign:'center', color:'#6b5c80'}}>
            <div style={{fontSize:36, marginBottom:10}}>⚠️</div>
            <div style={{fontFamily:'Fraunces, serif', fontWeight:800, fontSize:20, color:'#1b1230', marginBottom:6}}>Couldn't load this story.</div>
            <div style={{fontSize:13}}>Try again in a moment.</div>
          </div>
        )}

        {detailReady && tab === 'read' && (
          <ReadAndWordsTab
            article={article}
            paragraphs={paragraphs}
            expanded={expandedKw}
            setExpanded={setExpandedKw}
            onFinish={() => { bumpProgress(25); switchTab('analyze'); }}
          />
        )}

        {detailReady && tab === 'analyze' && (
          <AnalyzeTab article={article} paragraphs={paragraphs} onNext={()=>{ bumpProgress(50); switchTab('quiz'); }} />
        )}

        {detailReady && tab === 'quiz' && (
          <QuizTab
            article={article} paragraphs={paragraphs}
            quizIdx={quizIdx} setQuizIdx={setQuizIdx}
            quizAns={quizAns} setQuizAns={setQuizAns}
            quizShow={quizShow} setQuizShow={setQuizShow}
            onFinish={() => { bumpProgress(75); setConfetti(true); setTimeout(()=>setConfetti(false), 1800); switchTab('discuss'); }}
          />
        )}

        {detailReady && tab === 'discuss' && (
          <DiscussTab article={article} paragraphs={paragraphs} onDone={()=>{ bumpProgress(100); onComplete(); }} />
        )}
      </div>

      {confetti && <Confetti/>}
    </div>
  );
}

// ——— Highlight keywords in a text string ———
// Matches base terms AND common English inflections (ban → banned, fine → fined).
// The base term is captured as group 1 so we can look up the definition even
// when the matched text is an inflected form like "banned".
function highlightText(text, keywords, catColor) {
  if (!keywords || !keywords.length) return [text];
  const termMap = {};
  keywords.forEach(k => { termMap[k.term.toLowerCase()] = k; });
  // Sort longer-first so multi-word terms ("prediction market") win over
  // single-word subsets ("prediction").
  const terms = keywords.map(k => k.term).sort((a, b) => b.length - a.length);
  const SUFFIX = '(?:s|es|ed|d|ing|ning|ned|ting|ted|er|ers)?';
  const alt = terms.map(t => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|');
  const pattern = new RegExp(`\\b(${alt})${SUFFIX}\\b`, 'gi');
  const result = [];
  let last = 0, m, idx = 0;
  while ((m = pattern.exec(text)) !== null) {
    if (m.index > last) result.push(text.substring(last, m.index));
    const base = (m[1] || '').toLowerCase();   // captured base term
    const kw = termMap[base];
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

// ——————— PRINTABLE PDF DOWNLOAD ———————
// PDFs are pre-generated by the daily pipeline (pipeline/pdf_export.py)
// and shipped in the daily zip + per-day flat upload to Supabase. The
// button is just an <a href download> pointing to the right path. No
// client-side rendering needed — fast, no extra dependencies, archived
// alongside the rest of the daily content.
function pdfUrlForArticle(article) {
  const lvl = article.level === 'Tree' ? 'middle' : 'easy';
  const filename = `${article.storyId}-${lvl}.pdf`;
  // Today's PDF lives in the deploy bundle (same origin); past days come
  // from the dated Supabase prefix.
  if (article.archiveDate) {
    return `${window.ARCHIVE_BASE}/${article.archiveDate}/article_pdfs/${filename}`;
  }
  return `article_pdfs/${filename}`;
}

// ——————— READ & WORDS TAB (combined) ———————
function ReadAndWordsTab({ article, paragraphs, expanded, setExpanded, onFinish }) {
  const catColor = getCatColor(article.category);
  const [gameOpen, setGameOpen] = useStateA(false);
  return (
    <div style={{display:'grid', gridTemplateColumns:'1.6fr 1fr', gap:24}}>
      <div style={{background:'#fff', borderRadius:22, padding:'30px 34px', border:'2px solid #f0e8d8'}}>
        <div style={{display:'flex', alignItems:'center', gap:10, marginBottom:18, paddingBottom:14, borderBottom:'2px dashed #f0e8d8'}}>
          <div style={{fontSize:26}}>📖</div>
          <h2 style={{fontFamily:'Fraunces, serif', fontWeight:800, fontSize:22, color:'#1b1230', margin:0}}>The Story</h2>
          <div style={{flex:1}}/>
          <a href={pdfUrlForArticle(article)} download
            title="Download a 4-page printable PDF — story, background, quiz, and a worksheet. Pre-generated by the daily pipeline; opens in any PDF reader."
            style={{
              background:'#fff', color:'#1b1230', border:`2px solid ${catColor}`,
              borderRadius:999, padding:'6px 14px', fontWeight:800, fontSize:12,
              cursor:'pointer', fontFamily:'Nunito, sans-serif',
              textDecoration:'none', display:'flex', alignItems:'center', gap:6,
            }}>
            📥 Download PDF
          </a>
          <div style={{fontSize:12, color:'#9a8d7a', fontWeight:700}}>Hover the colored words!</div>
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
          {article.keywords.length >= 2 && (
            <button onClick={()=>setGameOpen(true)} style={{
              marginTop:12, width:'100%', background:`linear-gradient(135deg, ${catColor}, #1b1230)`,
              color:'#fff', border:'none', borderRadius:12, padding:'10px 12px',
              fontWeight:800, fontSize:13, cursor:'pointer', fontFamily:'Nunito, sans-serif',
              display:'flex', alignItems:'center', justifyContent:'center', gap:8,
              boxShadow:'0 2px 0 rgba(27,18,48,0.1)',
            }}>🎮 Match the meanings</button>
          )}
        </div>
        {article.whyItMatters && (
          <div style={{background:'#fff4c2', border:'2px solid #ffe28a', borderRadius:18, padding:18}}>
            <div style={{display:'flex', alignItems:'center', gap:8, marginBottom:10}}>
              <div style={{fontSize:22}}>💡</div>
              <div style={{fontFamily:'Fraunces, serif', fontWeight:800, fontSize:16, color:'#1b1230'}}>Why it matters</div>
            </div>
            <p style={{fontSize:13.5, lineHeight:1.6, color:'#2a1f3d', margin:0, fontFamily:'Nunito, sans-serif'}}>
              {highlightText(article.whyItMatters, article.keywords, catColor)}
            </p>
          </div>
        )}
      </aside>
      {gameOpen && <WordMatchGame keywords={article.keywords} catColor={catColor} onClose={()=>setGameOpen(false)}/>}
    </div>
  );
}

function WordMatchGame({ keywords, catColor, onClose }) {
  // Shuffle definitions once per open so user matches term → meaning.
  const shuffledDefs = useMemoA(() => {
    const defs = keywords.map((k, i) => ({ def: k.def, idx: i }));
    for (let i = defs.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [defs[i], defs[j]] = [defs[j], defs[i]];
    }
    return defs;
  }, [keywords]);
  const [picks, setPicks] = useStateA(Array(keywords.length).fill(''));
  const [checked, setChecked] = useStateA(false);
  const correct = picks.filter((p, i) => String(p) === String(i)).length;
  const total = keywords.length;
  const stars = Math.round((correct / Math.max(total,1)) * 5);

  return (
    <div onClick={onClose} style={{
      position:'fixed', inset:0, background:'rgba(27,18,48,0.5)',
      display:'flex', alignItems:'center', justifyContent:'center', zIndex:100, padding:20,
    }}>
      <div onClick={e=>e.stopPropagation()} style={{
        background:'#fff', borderRadius:22, padding:'26px 28px', maxWidth:560, width:'100%',
        maxHeight:'90vh', overflowY:'auto', boxShadow:'0 20px 60px rgba(27,18,48,0.3)',
      }}>
        <div style={{display:'flex', alignItems:'center', gap:10, marginBottom:14}}>
          <div style={{fontSize:26}}>🎮</div>
          <h2 style={{fontFamily:'Fraunces, serif', fontWeight:800, fontSize:20, color:'#1b1230', margin:0, flex:1}}>Match the meanings</h2>
          <button onClick={onClose} style={{background:'transparent', border:'none', fontSize:22, cursor:'pointer', color:'#6b5c80'}}>✕</button>
        </div>
        <p style={{fontSize:13, color:'#6b5c80', marginTop:0, marginBottom:16}}>Pick the right meaning for each word.</p>
        <div style={{display:'flex', flexDirection:'column', gap:10}}>
          {keywords.map((kw, i) => {
            const isRight = checked && String(picks[i]) === String(i);
            const isWrong = checked && picks[i] !== '' && String(picks[i]) !== String(i);
            return (
              <div key={i} style={{display:'flex', gap:10, alignItems:'center'}}>
                <div style={{
                  flex:'0 0 30%', background: catColor+'22', color: catColor,
                  fontWeight:800, padding:'10px 12px', borderRadius:10, fontSize:14, textAlign:'center',
                }}>{kw.term}</div>
                <select value={picks[i]} disabled={checked} onChange={e=>{
                  const v = e.target.value;
                  setPicks(prev => { const n = [...prev]; n[i] = v; return n; });
                }} style={{
                  flex:1, padding:'10px 12px', borderRadius:10, fontSize:13,
                  border: `2px solid ${isRight ? '#17b3a6' : isWrong ? '#ff6b5b' : '#f0e8d8'}`,
                  background:'#fff9ef', color:'#1b1230', fontFamily:'Nunito, sans-serif', cursor: checked ? 'default' : 'pointer',
                }}>
                  <option value="">Pick a meaning…</option>
                  {shuffledDefs.map(({ def, idx }) => (
                    <option key={idx} value={idx}>{def}</option>
                  ))}
                </select>
              </div>
            );
          })}
        </div>
        {checked ? (
          <div style={{marginTop:16, background: correct === total ? '#e0f6f3' : '#fff4c2', borderRadius:14, padding:'14px 16px', textAlign:'center'}}>
            <div style={{fontSize:28, marginBottom:4}}>{'⭐'.repeat(stars)}{'☆'.repeat(5 - stars)}</div>
            <div style={{fontFamily:'Fraunces, serif', fontWeight:800, fontSize:18, color:'#1b1230'}}>
              {correct} / {total} correct {correct === total ? '🎉' : ''}
            </div>
            <div style={{display:'flex', gap:8, marginTop:12, justifyContent:'center'}}>
              <button onClick={()=>{setPicks(Array(total).fill('')); setChecked(false);}} style={{
                background: catColor, color:'#fff', border:'none', borderRadius:10, padding:'10px 18px',
                fontWeight:800, fontSize:13, cursor:'pointer',
              }}>↻ Try again</button>
              <button onClick={onClose} style={{
                background:'#fff9ef', color:'#1b1230', border:'2px solid #f0e8d8', borderRadius:10, padding:'10px 18px',
                fontWeight:800, fontSize:13, cursor:'pointer',
              }}>Done</button>
            </div>
          </div>
        ) : (
          <div style={{display:'flex', justifyContent:'flex-end', marginTop:16}}>
            <button onClick={()=>setChecked(true)} disabled={picks.some(p => p === '')} style={{
              background: picks.some(p => p === '') ? '#d8cfb8' : '#ffc83d',
              color:'#1b1230', border:'none', borderRadius:10, padding:'10px 22px',
              fontWeight:800, fontSize:14, cursor: picks.some(p => p === '') ? 'not-allowed' : 'pointer',
            }}>Check answers</button>
          </div>
        )}
      </div>
    </div>
  );
}

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

  const isTree = article.level === 'Tree';

  // Background paragraphs: prefer payload's background_read (deeper at middle,
  // simpler at easy). Fall back to a generic intro sentence only if missing.
  const bgParagraphs = (article.backgroundRead || '').trim()
    ? article.backgroundRead.split(/\n\n+/).map(s => s.trim()).filter(Boolean)
    : [`This story comes from ${article.source}, a ${article.category === 'Science' ? 'science source' : 'news source'} that covers stories for kids. When you read, think about WHO is doing something, WHAT is happening, WHERE it takes place, and WHY it matters.`];

  // Easy level: parse WHO/WHAT/WHERE/WHY into a 5W grid.
  // Tree level: render Article_Structure as a nested mind-tree preserving
  // leading-whitespace + └─/├─ indentation from the payload.
  let structureBlock = null;
  if (isTree) {
    structureBlock = (
      <div style={{display:'flex', flexDirection:'column', gap:6}}>
        {(article.articleStructure || []).map((line, i) => {
          const raw = typeof line === 'string' ? line : String(line);
          const m = raw.match(/^(\s*)(.*)$/);
          const indent = m ? m[1].length : 0;
          const text = m ? m[2] : raw;
          // Split "LABEL: rest" so label can be bolded
          const lm = text.match(/^([A-Z][A-Z \/]*[A-Z]|[A-Z][a-z]+):\s*(.*)$/);
          return (
            <div key={i} style={{
              paddingLeft: indent * 8,
              fontSize:14, lineHeight:1.55, color:'#2a1f3d',
              fontFamily:'Nunito, sans-serif',
            }}>
              {lm ? (
                <span>
                  <span style={{fontWeight:800, color:'#1b1230'}}>{lm[1]}</span>
                  <span>: </span>
                  <span>{highlightText(lm[2], article.keywords, catColor)}</span>
                </span>
              ) : (
                <span>{highlightText(text, article.keywords, catColor)}</span>
              )}
            </div>
          );
        })}
      </div>
    );
  } else {
    const structure = {};
    for (const line of (article.articleStructure || [])) {
      const m = typeof line === 'string' ? line.match(/^\s*([A-Za-z]+)\s*:\s*(.*)$/) : null;
      if (m) structure[m[1].toUpperCase()] = m[2].trim();
    }
    const who = structure.WHO || (article.title.split(' ').slice(0, 3).join(' ') + '…');
    const what = structure.WHAT || ((article.summary || '').split('.')[0] + '.');
    const where = structure.WHERE || (article.category === 'Science' ? 'In labs, field studies, or around the world' : 'Mentioned in the story');
    const why = structure.WHY || `It matters because it affects ${article.category === 'Science' ? 'how we understand the world' : 'people, animals, or the planet'}.`;
    structureBlock = (
      <div style={{display:'flex', flexDirection:'column', gap:10}}>
        <WRow label="Who" emoji="👤" value={who}/>
        <WRow label="What" emoji="💡" value={what}/>
        <WRow label="Where" emoji="📍" value={where}/>
        <WRow label="Why" emoji="❓" value={why}/>
      </div>
    );
  }

  return (
    <div style={{display:'grid', gridTemplateColumns:'1fr 1fr', gap:20}}>
      {/* Left: Background */}
      <div style={{background:'#fff', borderRadius:22, padding:'26px 30px', border:'2px solid #f0e8d8'}}>
        <div style={{display:'flex', alignItems:'center', gap:10, marginBottom:14}}>
          <div style={{fontSize:26}}>🧭</div>
          <h2 style={{fontFamily:'Fraunces, serif', fontWeight:800, fontSize:20, color:'#1b1230', margin:0}}>Background you need</h2>
        </div>
        {bgParagraphs.map((p, i) => (
          <p key={i} style={{fontSize:15, lineHeight:1.7, color:'#2a1f3d', margin: i === 0 ? 0 : '12px 0 0'}}>
            {highlightText(p, article.keywords, catColor)}
          </p>
        ))}
      </div>

      {/* Right: Structure (5W for easy, mind-tree for middle) */}
      <div style={{background:'#fff', borderRadius:22, padding:'26px 30px', border:'2px solid #f0e8d8'}}>
        <div style={{display:'flex', alignItems:'center', gap:10, marginBottom:14}}>
          <div style={{fontSize:26}}>🔍</div>
          <h2 style={{fontFamily:'Fraunces, serif', fontWeight:800, fontSize:20, color:'#1b1230', margin:0}}>Break it down</h2>
        </div>
        {structureBlock}
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
const MIN_WORDS = 20;

function countWords(s) {
  return (s || '').trim().split(/\s+/).filter(Boolean).length;
}

// Render rewrite text with **kid-contributed** bold spans highlighted.
function RewriteText({ text }) {
  if (!text) return null;
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return (
    <>{parts.map((p, i) => {
      const m = p.match(/^\*\*([^*]+)\*\*$/);
      if (m) return <mark key={i} style={{background:'#ffec99', padding:'1px 4px', borderRadius:4, fontWeight:700}}>{m[1]}</mark>;
      return <span key={i}>{p}</span>;
    })}</>
  );
}

function ScorePills({ scores, color = '#9061f9' }) {
  if (!scores) return null;
  return (
    <div style={{display:'flex', gap:6, fontSize:11, color:'#6b5c80', fontWeight:700, flexWrap:'wrap'}}>
      {['clarity','evidence','voice','depth'].map(k => (
        <span key={k} style={{background:'#fff', padding:'3px 8px', borderRadius:999, border:'1.5px solid #e5dcf5', whiteSpace:'nowrap'}}>
          {k}: <b style={{color}}>{scores[k] ?? '–'}</b>/5
        </span>
      ))}
    </div>
  );
}

// Side-by-side comparison: kid's draft (Round N) vs coach's polish.
// Used both for the "current round" panel and for collapsed history rows.
function RoundCompare({ round, n, total, defaultOpen = true }) {
  const [open, setOpen] = useStateA(defaultOpen);
  return (
    <div style={{background:open ? 'linear-gradient(135deg, #f0ebff, #fff9ef)' : '#fff', border:`2px solid ${open ? '#c9b8ff' : '#e5dcf5'}`, borderRadius:18, padding: open ? '22px 24px' : '14px 18px', marginBottom:14}}>
      <button onClick={()=>setOpen(!open)} style={{width:'100%', background:'transparent', border:'none', padding:0, cursor:'pointer', display:'flex', alignItems:'center', gap:10, marginBottom: open ? 14 : 0}}>
        <div style={{fontSize:open ? 24 : 18}}>✨</div>
        <h3 style={{fontFamily:'Fraunces, serif', fontWeight:800, fontSize: open ? 18 : 15, color:'#1b1230', margin:0, textAlign:'left'}}>
          Round {n}{n < total ? ` of ${total}` : ''} — what the coach thinks
        </h3>
        <div style={{flex:1}}/>
        {!open && round.aiResult?.scores && <ScorePills scores={round.aiResult.scores}/>}
        <div style={{fontSize:14, color:'#9a8d7a', transform: open ? 'rotate(180deg)' : 'rotate(0)'}}>⌄</div>
      </button>
      {open && (
        <>
          <div style={{display:'grid', gridTemplateColumns:'1fr 1fr', gap:14, marginBottom:14}}>
            <div style={{background:'#fff', border:'2px solid #f0e8d8', borderRadius:14, padding:'14px 16px'}}>
              <div style={{fontSize:11, fontWeight:800, color:'#6b5c80', letterSpacing:'.08em', textTransform:'uppercase', marginBottom:6}}>
                What you wrote
              </div>
              <p style={{fontSize:14.5, lineHeight:1.6, color:'#2a1f3d', margin:0, whiteSpace:'pre-wrap'}}>{round.userText}</p>
              <div style={{fontSize:10, color:'#9a8d7a', marginTop:8, fontWeight:600}}>
                {countWords(round.userText)} words
              </div>
            </div>
            <div style={{background:'#fff', border:'2px solid #e5dcf5', borderRadius:14, padding:'14px 16px'}}>
              <div style={{fontSize:11, fontWeight:800, color:'#9061f9', letterSpacing:'.08em', textTransform:'uppercase', marginBottom:6}}>
                Coach's polish
              </div>
              <p style={{fontSize:14.5, lineHeight:1.65, color:'#1b1230', margin:0, whiteSpace:'pre-wrap'}}>
                <RewriteText text={round.aiResult?.rewrite || ''}/>
              </p>
            </div>
          </div>
          <p style={{fontSize:14, lineHeight:1.6, color:'#2a1f3d', margin:'0 0 10px', fontStyle:'italic'}}>
            💬 {round.aiResult?.feedback}
          </p>
          <ScorePills scores={round.aiResult?.scores}/>
        </>
      )}
    </div>
  );
}

function DiscussTab({ article, paragraphs, onDone }) {
  // Restore iteration history for THIS article — survives reloads.
  // Shape: { rounds: [{userText, aiResult, at}], currentDraft, savedFinal }
  const draftKey = `ohye_response_${article.storyId}_${article.level || 'unk'}`;
  const ss = window.safeStorage;
  const initial = (ss && ss.getJSON(draftKey)) || {};

  const [rounds, setRounds] = useStateA(initial.rounds || []);
  const [currentDraft, setCurrentDraft] = useStateA(initial.currentDraft || '');
  const [aiState, setAiState] = useStateA('idle'); // 'idle' | 'loading' | 'error'
  const [aiError, setAiError] = useStateA(null);
  const [savedFinal, setSavedFinal] = useStateA(!!initial.savedFinal);
  const [articleOpen, setArticleOpen] = useStateA(false);
  const catColor = getCatColor(article.category);

  // Persist on every change so a reload preserves all rounds + current draft.
  useEffectA(() => {
    if (!ss) return;
    ss.setJSON(draftKey, { rounds, currentDraft, savedFinal });
  }, [rounds, currentDraft, savedFinal]);

  const wordCount = countWords(currentDraft);
  const meetsMin = wordCount >= MIN_WORDS;
  const lastRound = rounds.length > 0 ? rounds[rounds.length - 1] : null;
  // Don't let user pay for an AI call on the IDENTICAL text they just submitted
  const sameAsLast = lastRound && currentDraft.trim() === lastRound.userText.trim();

  const onGetFeedback = async () => {
    if (!meetsMin || aiState === 'loading' || sameAsLast) return;
    setAiState('loading'); setAiError(null);
    const res = await window.fetchAIFeedback({
      text: currentDraft,
      articleId: article.id,
      articleTitle: article.title,
      articleSummary: (article.summary || '').slice(0, 1500),
      // Send the full article body so the coach knows what the kid is
      // responding TO and can check evidence-from-text. Edge Function
      // caps at 6KB on its side as a safety guard.
      articleBody: (article.body || '').slice(0, 6000),
      level: article.level,
    });
    if (res.error) {
      setAiError(res.error); setAiState('error');
    } else {
      setRounds([...rounds, { userText: currentDraft, aiResult: res, at: new Date().toISOString() }]);
      setAiState('idle');
      // Keep currentDraft populated so the kid sees the side-by-side
      // immediately. They can then edit it, or click "Use polished".
    }
  };

  const onUsePolished = () => {
    if (lastRound?.aiResult?.rewrite) {
      setCurrentDraft(lastRound.aiResult.rewrite.replace(/\*\*/g, ''));
    }
  };

  const onSaveFinal = () => setSavedFinal(true);
  const onUnlock = () => setSavedFinal(false);
  const onResetAll = () => {
    if (confirm('Start over? Your saved drafts and coach feedback will be cleared.')) {
      setRounds([]); setCurrentDraft(''); setSavedFinal(false);
    }
  };

  // Action-button label depends on iteration state
  const isFirstRound = rounds.length === 0;
  const feedbackBtnLabel = aiState === 'loading'
    ? '✨ Thinking…'
    : isFirstRound ? '✨ Get AI feedback'
                   : `✨ Get feedback again (round ${rounds.length + 1})`;

  return (
    <div style={{display:'grid', gridTemplateColumns:'1fr 320px', gap:24}}>
      <div style={{background:'#fff', borderRadius:22, padding:'28px 32px', border:'2px solid #f0e8d8'}}>
        <div style={{display:'flex', alignItems:'center', gap:10, marginBottom:16}}>
          <div style={{fontSize:26}}>💭</div>
          <h2 style={{fontFamily:'Fraunces, serif', fontWeight:800, fontSize:22, color:'#1b1230', margin:0}}>Think & share</h2>
          {rounds.length > 0 && (
            <span style={{marginLeft:'auto', fontSize:12, color:'#9061f9', fontWeight:800, background:'#f0ebff', padding:'4px 10px', borderRadius:999}}>
              {rounds.length} {rounds.length === 1 ? 'round' : 'rounds'} with the coach
            </span>
          )}
        </div>

        {article.discussion.map((d, i) => (
          <div key={i} style={{background:'#fff4c2', borderRadius:16, padding:'16px 18px', marginBottom:14, border:'2px solid #ffe28a'}}>
            <div style={{fontFamily:'Fraunces, serif', fontWeight:700, fontSize:18, color:'#1b1230', lineHeight:1.3}}>{d}</div>
          </div>
        ))}

        {/* Round history — older rounds collapsed by default */}
        {rounds.length > 1 && rounds.slice(0, -1).map((r, i) => (
          <RoundCompare key={i} round={r} n={i + 1} total={rounds.length} defaultOpen={false}/>
        ))}

        {/* Latest round — always expanded */}
        {lastRound && (
          <RoundCompare round={lastRound} n={rounds.length} total={rounds.length} defaultOpen={true}/>
        )}

        {/* Current draft — for NEXT round */}
        {!savedFinal && (
          <>
            <label style={{display:'flex', alignItems:'baseline', justifyContent:'space-between', fontWeight:800, fontSize:13, color:'#6b5c80', marginBottom:8, letterSpacing:'.05em', textTransform:'uppercase', marginTop:rounds.length > 0 ? 4 : 8}}>
              <span>{isFirstRound ? 'Your thoughts' : `Try again — round ${rounds.length + 1} draft`}</span>
              <span style={{fontSize:11, color: meetsMin ? '#17b3a6' : '#c14e2a', textTransform:'none', letterSpacing:0, fontWeight:700}}>
                {wordCount} / {MIN_WORDS}+ words {meetsMin ? '✓' : ''}
              </span>
            </label>
            <textarea value={currentDraft} onChange={e=>setCurrentDraft(e.target.value)}
              placeholder={isFirstRound
                ? `Write at least ${MIN_WORDS} words. What surprised you? What do you think should happen next?`
                : "Take what helped from the polish, but keep your voice. What did you want to say even more clearly?"}
              rows={5}
              style={{width:'100%', border:`2px solid ${meetsMin ? '#cfe6cd' : '#f0e8d8'}`, borderRadius:14, padding:'12px 14px', fontSize:14.5, fontFamily:'Nunito, sans-serif', resize:'vertical', outline:'none', background:'#fff9ef', color:'#1b1230', lineHeight:1.55}}/>

            <div style={{display:'flex', justifyContent:'space-between', alignItems:'center', marginTop:12, flexWrap:'wrap', gap:10}}>
              <div style={{fontSize:12, color:'#9a8d7a'}}>
                {sameAsLast ? '💡 Edit your draft to ask the coach again'
                            : meetsMin ? '✨ AI feedback ready'
                                       : `Add ${MIN_WORDS - wordCount} more word${MIN_WORDS - wordCount === 1 ? '' : 's'} to unlock`}
              </div>
              <div style={{display:'flex', gap:10, flexWrap:'wrap'}}>
                {lastRound && (
                  <button onClick={onUsePolished}
                    style={{background:'#fff', color:'#9061f9', border:'2px solid #c9b8ff', borderRadius:10, padding:'10px 16px', fontWeight:800, fontSize:13, cursor:'pointer', fontFamily:'Nunito, sans-serif'}}>
                    ↑ Use polished as my draft
                  </button>
                )}
                <BigButton bg={meetsMin && !sameAsLast ? '#9061f9' : '#d8cfb8'} color="#fff"
                           onClick={onGetFeedback} disabled={!meetsMin || aiState === 'loading' || sameAsLast}>
                  {feedbackBtnLabel}
                </BigButton>
                <BigButton bg="#ffc83d" color="#1b1230" onClick={onSaveFinal} disabled={!meetsMin}>
                  ✓ Save final answer
                </BigButton>
              </div>
            </div>

            {aiError && (
              <div style={{marginTop:14, background:'#ffece8', border:'2px solid #ff9b8a', borderRadius:14, padding:'14px 18px', color:'#a3321b', fontWeight:600, fontSize:14}}>
                ⚠️ {aiError}
              </div>
            )}
          </>
        )}

        {/* Final state */}
        {savedFinal && (
          <div style={{background:'linear-gradient(135deg, #d6f3ed, #fff9ef)', border:'2px solid #17b3a6', borderRadius:18, padding:'22px 24px', marginTop:8}}>
            <div style={{display:'flex', alignItems:'center', gap:10, marginBottom:10}}>
              <div style={{fontSize:24}}>🌟</div>
              <h3 style={{fontFamily:'Fraunces, serif', fontWeight:800, fontSize:18, color:'#1b1230', margin:0}}>Your final answer is saved</h3>
            </div>
            <div style={{background:'#fff', border:'2px solid #c8ebe3', borderRadius:14, padding:'14px 16px', marginBottom:12}}>
              <p style={{fontSize:14.5, lineHeight:1.6, color:'#1b1230', margin:0, whiteSpace:'pre-wrap'}}>{currentDraft}</p>
              <div style={{fontSize:10, color:'#9a8d7a', marginTop:8, fontWeight:600}}>
                {countWords(currentDraft)} words · {rounds.length} round{rounds.length === 1 ? '' : 's'} of coaching
              </div>
            </div>
            <div style={{display:'flex', gap:10, flexWrap:'wrap'}}>
              <button onClick={onUnlock}
                style={{background:'#fff', color:'#17b3a6', border:'2px solid #17b3a6', borderRadius:10, padding:'8px 14px', fontWeight:800, fontSize:13, cursor:'pointer', fontFamily:'Nunito, sans-serif'}}>
                ✏️ Edit again
              </button>
              <button onClick={onResetAll}
                style={{background:'transparent', color:'#9a8d7a', border:'1.5px dashed #d0c4b4', borderRadius:10, padding:'8px 14px', fontWeight:700, fontSize:12, cursor:'pointer', fontFamily:'Nunito, sans-serif'}}>
                ↺ Start over
              </button>
              <BigButton bg="#17b3a6" color="#fff" onClick={onDone}>✓ All done →</BigButton>
            </div>
          </div>
        )}

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
