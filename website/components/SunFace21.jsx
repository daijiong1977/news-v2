// Kidsnews sun-face mark — built from the parent's DNA.
//   · eyes: Roman II (open) + I (winking)
//   · nose: "MINS" caps
//   · smile: arc with the parent's long·long·short rhythm
//   · 12 rays radiating outward
//
// Drop-in React component. Pure SVG — no font dependency on render
// (the "MINS" nose uses Nunito if available, falls back to system sans).

// (Babel-standalone in this project uses script-level globals, not ES
// modules — exporting via export keyword would be a syntax error here.)
function SunFace21({
  size   = 160,
  ink    = '#1b1230',
  accent = '#ffc83d',
  ray    = '#ffc83d',
}) {
  const cx = 100, cy = 100, r = 54;
  const rays = Array.from({ length: 12 }, (_, i) => {
    const a = (i * 30 - 90) * Math.PI / 180;
    const r1 = r + 14, r2 = r + 30;
    return (
      <line key={i}
        x1={cx + Math.cos(a) * r1} y1={cy + Math.sin(a) * r1}
        x2={cx + Math.cos(a) * r2} y2={cy + Math.sin(a) * r2}
        stroke={ray} strokeWidth="6" strokeLinecap="round" />
    );
  });

  return (
    <svg width={size} height={size} viewBox="0 0 200 200" style={{ display: 'block' }}>
      <g>{rays}</g>
      <circle cx={cx} cy={cy} r={r} fill={accent} />
      <g fill={ink}>
        <rect x={cx - 22 - 8} y={cy - 24} width="6" height="16" rx="2.5" />
        <rect x={cx - 22 + 2} y={cy - 24} width="6" height="16" rx="2.5" />
        <rect x={cx + 22 - 3} y={cy - 20} width="6" height="8"  rx="2.5" />
      </g>
      <text x={cx} y={cy + 9}
        textAnchor="middle" dominantBaseline="middle"
        fontFamily="Nunito, system-ui, sans-serif" fontWeight="800" fontSize="7"
        fill={ink} letterSpacing="2.6">MINS</text>
      <path
        d={`M ${cx - 22} ${cy + 22} Q ${cx} ${cy + 36} ${cx + 22} ${cy + 22}`}
        fill="none" stroke={ink} strokeWidth="3.2" strokeLinecap="round"
        strokeDasharray="14 4 14 4 7" />
    </svg>
  );
}
