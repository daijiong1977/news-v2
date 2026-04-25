// Shared components for kidsnews · 21mins
const { useState, useEffect, useRef, useMemo } = React;

// ————————————————————————————————————————————————————————————
// KIDSNEWS LOCKUP — sun-face mark + "kids/news" wordmark + endorsement
// (Renders the locked brand from `21mins-brand` handoff. SunFace21 is the
//  canonical mark; the wordmark + endorsement are styled inline below.)
// ————————————————————————————————————————————————————————————
function KidsNewsLockup({ size = 100, compact = false, hideEndorsement = false }) {
  const cfg = window.SITE_CONFIG || {};
  const wordHi = cfg.brandWordHi || 'news';   // "news" by default
  const brand = cfg.brand || 'kidsnews';
  // brand = "kidsnews" → split into hi="news" prefix="kids"
  const prefix = brand.toLowerCase().endsWith(wordHi.toLowerCase())
    ? brand.slice(0, brand.length - wordHi.length)
    : brand;
  const wordSize = compact ? Math.round(size * 0.42) : Math.round(size * 0.46);
  const endorseSize = compact ? 8.5 : 10;

  // Endorsement: render two SITE_CONFIG fields on a single line
  // ("21MINS DAILY NEWS. LEARN THE REAL WORLD."). Periods come from
  // the config strings themselves so the join just adds a space.
  const endorseLine = !hideEndorsement
    ? [cfg.endorsement, cfg.endorsement2].filter(Boolean).join(' ')
    : '';

  return (
    <div style={{display:'inline-flex', alignItems:'center', gap: compact ? 10 : 14}}>
      <SunFace21 size={size} />
      <div style={{
        display:'flex', flexDirection:'column', gap: 4,
        lineHeight: 1, paddingTop: 2,
      }}>
        <div style={{
          fontFamily:'Fraunces, serif', fontWeight: 700,
          fontSize: wordSize, letterSpacing: '-0.02em',
          color: 'var(--twentyone-ink, #1b1230)',
        }}>
          {prefix}<span style={{color: 'var(--twentyone-coral, #ff6b5b)'}}>{wordHi}</span>
        </div>
        {endorseLine && (
          <div style={{
            fontFamily:'Nunito, sans-serif', fontWeight: 800,
            fontSize: endorseSize, letterSpacing: '.18em',
            textTransform:'uppercase', color: 'var(--twentyone-muted, #9a8d7a)',
            lineHeight: 1.25, whiteSpace: 'nowrap',
          }}>
            {endorseLine}
          </div>
        )}
      </div>
    </div>
  );
}

// Backward-compat shim — many call sites still reference `OhYeLogo`.
// Route through the new lockup until every callsite is migrated.
function OhYeLogo({ size = 40 }) {
  return <KidsNewsLockup size={size} compact={size < 40} hideEndorsement={size < 36}/>;
}

// ————————————————————————————————————————————————————————————
// STREAK RING — circular progress for daily 15-min goal
// ————————————————————————————————————————————————————————————
function StreakRing({ minutes, goal, streak, size = 72 }) {
  const r = size/2 - 6;
  const c = 2 * Math.PI * r;
  const pct = Math.min(1, minutes/goal);
  return (
    <div style={{position:'relative', width:size, height:size}}>
      <svg width={size} height={size} style={{transform:'rotate(-90deg)'}}>
        <circle cx={size/2} cy={size/2} r={r} stroke="#f0ebe3" strokeWidth="6" fill="none"/>
        <circle cx={size/2} cy={size/2} r={r} stroke="#ff8a3d" strokeWidth="6" fill="none"
          strokeDasharray={c} strokeDashoffset={c*(1-pct)} strokeLinecap="round"
          style={{transition:'stroke-dashoffset .6s ease'}}/>
      </svg>
      <div style={{position:'absolute', inset:0, display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center', lineHeight:1}}>
        <div style={{fontSize:22}}>🔥</div>
        <div style={{fontFamily:'Fraunces, serif', fontWeight:800, fontSize:14, color:'#1b1230', marginTop:2}}>{streak}</div>
      </div>
    </div>
  );
}

// ————————————————————————————————————————————————————————————
// CATEGORY CHIP
// ————————————————————————————————————————————————————————————
function CatChip({ cat, small }) {
  const c = CATEGORIES.find(x => x.label === cat) || CATEGORIES[0];
  return (
    <span style={{
      display:'inline-flex', alignItems:'center', gap:6,
      background: c.bg, color: c.color,
      padding: small ? '3px 10px' : '5px 12px',
      borderRadius: 999, fontWeight:800,
      fontSize: small ? 11 : 13,
      letterSpacing: '0.02em',
    }}>
      <span style={{fontSize: small ? 12 : 14}}>{c.emoji}</span>{c.label}
    </span>
  );
}

function LevelChip({ level, small }) {
  const l = LEVELS.find(x => x.id === level) || LEVELS[1];
  return (
    <span style={{
      display:'inline-flex', alignItems:'center', gap:5,
      background:'#fff', color:'#1b1230',
      padding: small ? '3px 9px' : '4px 11px',
      borderRadius:999, fontWeight:700,
      fontSize: small ? 11 : 12,
      border:'1.5px solid #eee3d7',
    }}>
      <span>{l.emoji}</span>{l.label}
    </span>
  );
}

// ————————————————————————————————————————————————————————————
// XP BADGE
// ————————————————————————————————————————————————————————————
function XpBadge({ xp, small }) {
  return (
    <span style={{
      display:'inline-flex', alignItems:'center', gap:4,
      background:'#fff4c2', color:'#8a6d00',
      padding: small ? '2px 8px' : '3px 10px',
      borderRadius:999, fontWeight:800, fontSize: small ? 11 : 12,
    }}>
      <span>⭐</span>+{xp} XP
    </span>
  );
}

// ————————————————————————————————————————————————————————————
// BIG BUTTON
// ————————————————————————————————————————————————————————————
function BigButton({ children, onClick, color='#1b1230', bg='#ffc83d', style, disabled }) {
  const [press, setPress] = useState(false);
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      onMouseDown={()=>setPress(true)}
      onMouseUp={()=>setPress(false)}
      onMouseLeave={()=>setPress(false)}
      style={{
        background: disabled ? '#e8dfd3' : bg,
        color: disabled ? '#9a8d7a' : color,
        border:'none',
        borderRadius:16,
        padding:'14px 22px',
        fontWeight:800,
        fontSize:16,
        fontFamily:'Nunito, sans-serif',
        cursor: disabled ? 'not-allowed' : 'pointer',
        boxShadow: disabled ? 'none' : (press ? '0 2px 0 rgba(0,0,0,0.15)' : '0 5px 0 rgba(0,0,0,0.18)'),
        transform: press ? 'translateY(3px)' : 'translateY(0)',
        transition:'transform .08s, box-shadow .08s',
        letterSpacing:'0.01em',
        ...style,
      }}
    >{children}</button>
  );
}

// ————————————————————————————————————————————————————————————
// STAR METER (quiz progress)
// ————————————————————————————————————————————————————————————
function StarMeter({ filled, total }) {
  return (
    <div style={{display:'inline-flex', gap:4}}>
      {Array.from({length: total}).map((_,i) => (
        <span key={i} style={{fontSize:18, filter: i < filled ? 'none' : 'grayscale(1) opacity(0.3)'}}>⭐</span>
      ))}
    </div>
  );
}

// ————————————————————————————————————————————————————————————
// HELPERS
// ————————————————————————————————————————————————————————————
function timeAgo(s){ return s; }

function getCatColor(cat){
  const c = CATEGORIES.find(x => x.label === cat);
  return c ? c.color : '#1b1230';
}
function getCatBg(cat){
  const c = CATEGORIES.find(x => x.label === cat);
  return c ? c.bg : '#f6efe3';
}

Object.assign(window, {
  OhYeLogo, StreakRing, CatChip, LevelChip, XpBadge, BigButton, StarMeter,
  timeAgo, getCatColor, getCatBg,
});
