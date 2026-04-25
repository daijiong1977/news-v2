// 21mins parent mark — stacked "21 / bars / MINS"
// Drop-in React component. Scales off `size`. Pass `ink` / `accent` to override.
//
// Requires Fraunces (variable opsz, weight 500) and Nunito (800) loaded on the page.

// (Babel-standalone in this project uses script-level globals, not ES
// modules — exporting via export keyword would be a syntax error here.)
function Big21({ size = 96, ink = '#1b1230', accent = '#ffc83d' }) {
  const numSize  = size * 0.62;
  const minsSize = size * 0.13;
  const longW    = size * 0.18;
  const shortW   = size * 0.09;
  const barH     = Math.max(2, size * 0.022);
  const barGap   = Math.max(2, size * 0.025);
  const tightGap = size * 0.025;
  const blockGap = size * 0.10;

  return (
    <div style={{
      width: size, height: size,
      display: 'inline-flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center',
      lineHeight: 0.85,
    }}>
      <span style={{
        fontFamily: 'Fraunces, Georgia, serif',
        fontWeight: 500,
        fontSize: numSize,
        fontVariationSettings: '"opsz" 144',
        color: ink,
        letterSpacing: '-0.055em',
      }}>21</span>

      <div style={{
        display: 'flex', flexDirection: 'row', alignItems: 'center',
        gap: barGap, marginTop: tightGap, marginBottom: blockGap,
      }}>
        <span style={{ width: longW,  height: barH, background: accent, borderRadius: barH }} />
        <span style={{ width: longW,  height: barH, background: accent, borderRadius: barH }} />
        <span style={{ width: shortW, height: barH, background: accent, borderRadius: barH }} />
      </div>

      <span style={{
        fontFamily: 'Nunito, system-ui, sans-serif',
        fontWeight: 800,
        fontSize: minsSize,
        letterSpacing: '.34em',
        textTransform: 'uppercase',
        color: ink,
        paddingLeft: '.34em',
      }}>mins</span>
    </div>
  );
}
