// Audit shared primitives — recreate the kidsnews UI vocabulary so we can
// render BEFORE/AFTER frames at full fidelity inside the design canvas.
//
// All non-trivial components live in their own files (kn-screens-before.jsx,
// kn-screens-after.jsx). This file is just tokens + atoms that both share.

const KN = {
  // Brand
  ink:    '#1b1230',
  cream:  '#fff9ef',
  paper:  '#fff',
  border: '#f0e8d8',
  muted:  '#9a8d7a',
  gold:   '#ffc83d',
  goldHi: '#ffe2a8',
  coral:  '#ff6b5b',
  // Categories
  cats: {
    News:    { color: '#ff6b5b', bg: '#ffece8', emoji: '📰' },
    Science: { color: '#17b3a6', bg: '#e0f6f3', emoji: '🔬' },
    Fun:     { color: '#9061f9', bg: '#eee5ff', emoji: '🎈' },
  },
};

// — The locked parent "21" mark (pure SVG version, scales like Big21 React)
function Mark21({ size = 36, ink = KN.ink, accent = KN.gold }) {
  return (
    <svg width={size} height={size} viewBox="0 0 200 200" style={{display:'block', flexShrink:0}}>
      <text x="100" y="118" textAnchor="middle"
        fontFamily="Fraunces, Georgia, serif" fontWeight="500" fontSize="124"
        style={{fontVariationSettings: '"opsz" 144'}}
        letterSpacing="-6.8" fill={ink}>21</text>
      <g fill={accent}>
        <rect x="62"  y="135" width="36" height="4.4" rx="2.2"/>
        <rect x="103" y="135" width="36" height="4.4" rx="2.2"/>
        <rect x="144" y="135" width="18" height="4.4" rx="2.2"/>
      </g>
      <text x="100" y="166" textAnchor="middle"
        fontFamily="Nunito, system-ui, sans-serif" fontWeight="800" fontSize="26"
        letterSpacing="8.84" fill={ink}>MINS</text>
    </svg>
  );
}

// — The locked kidsnews sun-face mark
function MarkKids({ size = 64, ink = KN.ink, accent = KN.gold, ray = KN.gold }) {
  const cx = 100, cy = 100, r = 54;
  return (
    <svg width={size} height={size} viewBox="0 0 200 200" style={{display:'block', flexShrink:0}}>
      {Array.from({length: 12}).map((_, i) => {
        const a = (i * 30 - 90) * Math.PI / 180;
        const r1 = r + 14, r2 = r + 30;
        return <line key={i}
          x1={cx + Math.cos(a)*r1} y1={cy + Math.sin(a)*r1}
          x2={cx + Math.cos(a)*r2} y2={cy + Math.sin(a)*r2}
          stroke={ray} strokeWidth="6" strokeLinecap="round"/>;
      })}
      <circle cx={cx} cy={cy} r={r} fill={accent}/>
      <g fill={ink}>
        <rect x={cx-22-8} y={cy-24} width="6" height="16" rx="2.5"/>
        <rect x={cx-22+2} y={cy-24} width="6" height="16" rx="2.5"/>
        <rect x={cx+22-3} y={cy-20} width="6" height="8" rx="2.5"/>
      </g>
      <text x={cx} y={cy+9} textAnchor="middle" dominantBaseline="middle"
        fontFamily="Nunito, system-ui, sans-serif" fontWeight="800" fontSize="7"
        letterSpacing="2.6" fill={ink}>MINS</text>
      <path d={`M ${cx-22} ${cy+22} Q ${cx} ${cy+36} ${cx+22} ${cy+22}`}
        fill="none" stroke={ink} strokeWidth="3.2" strokeLinecap="round"
        strokeDasharray="14 4 14 4 7"/>
    </svg>
  );
}

// — Annotation badges that sit on top of frames in the audit
function Note({ kind = 'fix', children, top, right, left, bottom }) {
  const palette = {
    fix:  { bg: '#fff0e8', border: '#ff7a3d', dot: '#ff7a3d' },
    keep: { bg: '#e0f6f3', border: '#17b3a6', dot: '#17b3a6' },
    new:  { bg: '#fff4d6', border: '#d89b4a', dot: '#d89b4a' },
  }[kind];
  return (
    <div style={{
      position:'absolute', top, right, left, bottom,
      background: palette.bg,
      border: `2px solid ${palette.border}`,
      borderRadius: 14,
      padding: '10px 14px',
      maxWidth: 280,
      fontFamily:'Nunito, sans-serif',
      fontSize: 12, fontWeight: 600, lineHeight: 1.4,
      color: KN.ink,
      boxShadow:'0 4px 12px rgba(27,18,48,0.08)',
      zIndex: 5,
    }}>
      <div style={{
        display:'inline-flex', alignItems:'center', gap:6, marginBottom: 4,
      }}>
        <span style={{
          width:8, height:8, borderRadius:999, background: palette.dot,
        }}/>
        <span style={{
          fontSize:10, fontWeight:900, color: palette.dot,
          textTransform:'uppercase', letterSpacing:'.1em',
        }}>{kind === 'fix' ? 'Change' : kind === 'keep' ? 'Keep' : 'New'}</span>
      </div>
      <div>{children}</div>
    </div>
  );
}

// — Page label that sits above each artboard pair
function PageLabel({ tag, title, subtitle }) {
  return (
    <div style={{
      fontFamily:'Nunito, sans-serif',
      padding: '0 0 16px',
    }}>
      <div style={{
        fontSize: 11, fontWeight: 900, color: KN.coral,
        letterSpacing: '.14em', textTransform:'uppercase',
        marginBottom: 4,
      }}>{tag}</div>
      <div style={{
        fontFamily:'Fraunces, Georgia, serif',
        fontWeight: 700, fontSize: 28, color: KN.ink,
        lineHeight: 1.1, letterSpacing: '-0.015em',
        marginBottom: 6,
      }}>{title}</div>
      {subtitle && <div style={{
        fontSize: 14, color: KN.muted, fontWeight: 600, lineHeight: 1.5, maxWidth: 800,
      }}>{subtitle}</div>}
    </div>
  );
}

// — A "Before / After" stamp inside the artboard
function Stamp({ kind = 'before' }) {
  const cfg = kind === 'before'
    ? { bg: '#1b1230', fg: '#fff', label: 'BEFORE' }
    : { bg: KN.gold, fg: KN.ink, label: 'AFTER' };
  return (
    <div style={{
      position:'absolute', top: 14, left: 14, zIndex: 4,
      background: cfg.bg, color: cfg.fg,
      padding: '6px 12px', borderRadius: 999,
      fontFamily:'Nunito, sans-serif', fontWeight: 900, fontSize: 11,
      letterSpacing: '.14em',
      boxShadow: '0 2px 0 rgba(27,18,48,0.15)',
    }}>{cfg.label}</div>
  );
}

Object.assign(window, { KN, Mark21, MarkKids, Note, PageLabel, Stamp });
