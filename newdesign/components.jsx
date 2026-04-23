// Shared components for News Oh,Ye!
const { useState, useEffect, useRef, useMemo } = React;

// ————————————————————————————————————————————————————————————
// LOGO — happy newspaper + "Ye!" + broadcast waves (latest news for kids)
// ————————————————————————————————————————————————————————————
function OhYeLogo({ size = 40 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" fill="none" style={{display:'block'}}>
      <defs>
        <linearGradient id="logoSky" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0" stopColor="#ffc83d" />
          <stop offset="1" stopColor="#ffa23d" />
        </linearGradient>
      </defs>

      {/* Broadcast waves — "latest news" signal radiating from top-right */}
      <g stroke="#ff6b5b" strokeWidth="1.8" strokeLinecap="round" fill="none" opacity="0.85">
        <path d="M54 14 q3 -1 4 -4"/>
        <path d="M57 19 q5 -1 7 -6"/>
      </g>
      {/* little sparkles */}
      <g fill="#ffb82e">
        <circle cx="6" cy="12" r="1.4"/>
        <circle cx="10" cy="8" r="1.1"/>
      </g>

      {/* Folded newspaper body — tilted like it's being held */}
      <g transform="rotate(-6 32 36)">
        {/* Back page (peeking) */}
        <rect x="11" y="17" width="42" height="38" rx="4" fill="#fff3d6" stroke="#1b1230" strokeWidth="2"/>
        {/* Front page */}
        <rect x="8" y="20" width="42" height="38" rx="4" fill="#ffffff" stroke="#1b1230" strokeWidth="2"/>
        {/* Masthead bar with "NEWS" */}
        <rect x="12" y="24" width="34" height="7" rx="2" fill="url(#logoSky)"/>
        <text x="29" y="29.8" textAnchor="middle" fontSize="6" fontWeight="900" fill="#1b1230" fontFamily="Fraunces, serif" letterSpacing="1">NEWS</text>
        {/* Headline lines */}
        <rect x="12" y="34.5" width="26" height="2.2" rx="1" fill="#d9cdb7"/>
        <rect x="12" y="39.2" width="20" height="2.2" rx="1" fill="#d9cdb7"/>
        {/* Smiling eyes on the paper (kids touch) */}
        <circle cx="19" cy="49" r="2" fill="#1b1230"/>
        <circle cx="27" cy="49" r="2" fill="#1b1230"/>
        {/* Smile */}
        <path d="M17 52.5 q6 4 12 0" stroke="#1b1230" strokeWidth="2" strokeLinecap="round" fill="none"/>
        {/* Rosy cheeks */}
        <circle cx="15" cy="52" r="1.3" fill="#ff9eb5" opacity="0.85"/>
        <circle cx="31" cy="52" r="1.3" fill="#ff9eb5" opacity="0.85"/>
      </g>

      {/* Speech bubble "Ye!" popping out (the happy/excited reaction) */}
      <g transform="rotate(8 48 16)">
        <path d="M38 6 h18 a4 4 0 0 1 4 4 v10 a4 4 0 0 1 -4 4 h-10 l-4 4 -1 -4 h-3 a4 4 0 0 1 -4 -4 v-10 a4 4 0 0 1 4 -4 z"
              fill="#ff6b5b" stroke="#1b1230" strokeWidth="2" strokeLinejoin="round"/>
        <text x="47" y="20" textAnchor="middle" fontSize="12" fontWeight="900" fill="#fff" fontFamily="Fraunces, serif">Ye!</text>
      </g>
    </svg>
  );
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
