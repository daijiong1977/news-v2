// Parent dashboard — kidsnews
// - Local mode (default): reads everything from kid's localStorage on this device
// - Cloud mode (Google sign-in): Supabase RLS-gated reads from per-kid tables.
const { useState, useEffect, useMemo } = React;

// Supabase init — same project + publishable key as admin.html. The
// publishable key is anon-equivalent; RLS gates every read to the
// signed-in parent's own kids only.
const SUPABASE_URL = 'https://lfknsvavhiqrsasdfyrs.supabase.co';
const SUPABASE_PUBLISHABLE_KEY = 'sb_publishable_C0UF9RR0ui0XnmF5OdYwGg_W7628Yex';
const sb = (window.supabase && window.supabase.createClient)
  ? window.supabase.createClient(SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY, {
      auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true },
    })
  : null;

// ──────────────────────────────────────────────────────────────────────
// Helpers
// ──────────────────────────────────────────────────────────────────────

const REACTION_LABELS = {
  love:    { emoji: '💖', label: 'Loved it',     color: '#ff6b9c', bg: '#ffe4ef' },
  thinky:  { emoji: '🤔', label: 'Made me think', color: '#9061f9', bg: '#efe9ff' },
  meh:     { emoji: '😐', label: 'It was okay',  color: '#9a8d7a', bg: '#f5f0e8' },
  dislike: { emoji: '👎', label: 'Did not like',  color: '#b22525', bg: '#ffe4e4' },
};

const CATEGORY_COLORS = {
  News:    { color: '#c14e2a', bg: '#ffe5d8', emoji: '📰' },
  Science: { color: '#0e8d82', bg: '#d4f3ef', emoji: '🔬' },
  Fun:     { color: '#9061f9', bg: '#efe9ff', emoji: '🎈' },
};

function formatRelative(iso) {
  if (!iso) return '';
  const d = new Date(iso); if (isNaN(d.getTime())) return '';
  const now = Date.now();
  const diff = now - d.getTime();
  const min = Math.floor(diff / 60000);
  if (min < 1) return 'just now';
  if (min < 60) return `${min} min ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr} hr ago`;
  const day = Math.floor(hr / 24);
  if (day < 7) return `${day} day${day > 1 ? 's' : ''} ago`;
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

function fmtMs(ms) {
  if (!ms || ms < 1000) return '–';
  const sec = Math.round(ms / 1000);
  if (sec < 60) return `${sec}s`;
  const min = Math.floor(sec / 60);
  const rem = sec % 60;
  if (min < 60) return rem ? `${min}m ${rem}s` : `${min}m`;
  return `${Math.floor(min / 60)}h ${min % 60}m`;
}

function pct(num, den) { return den ? Math.round((num / den) * 100) : 0; }

// Local-TZ "YYYY-MM-DD" — used for matching quiz/discussion timestamps to
// the parent's day filter. Keeps day boundaries aligned with the kid's
// reading calendar (which is also local-TZ in progress.dayKey).
function localDayKey(iso) {
  if (!iso) return null;
  const d = new Date(iso); if (isNaN(d.getTime())) return null;
  return d.getFullYear() + '-'
    + String(d.getMonth() + 1).padStart(2, '0') + '-'
    + String(d.getDate()).padStart(2, '0');
}

function dayLabel(key) {
  if (!key) return '';
  const [y, m, d] = key.split('-').map(Number);
  const dt = new Date(y, m - 1, d);
  const today = new Date(); today.setHours(0,0,0,0);
  const diff = Math.round((today - dt) / 86400000);
  if (diff === 0) return `Today · ${dt.toLocaleDateString(undefined, {month:'short', day:'numeric'})}`;
  if (diff === 1) return `Yesterday · ${dt.toLocaleDateString(undefined, {month:'short', day:'numeric'})}`;
  if (diff < 7) return dt.toLocaleDateString(undefined, {weekday:'long', month:'short', day:'numeric'});
  return dt.toLocaleDateString(undefined, {month:'short', day:'numeric', year:'numeric'});
}

// Collect everything the kid has touched. Returns a single shape that
// every section below renders from. Pure read-only.
//
// `dayFilter` (string|null): if a 'YYYY-MM-DD' day is given, narrows the
// quiz/discussion data to entries on that day. Lifetime totals (reactions,
// article time) are NOT filterable since the underlying storage doesn't
// keep per-day timestamps for them.
function collectStats(dayFilter) {
  const ss = window.safeStorage;
  const tweaks = ss.getJSON('ohye_tweaks') || {};
  const progress = ss.getJSON('ohye_progress') || { readToday: [], minutesToday: 0, articleProgress: {}, dayKey: null };
  const quizLog = ss.getJSON('ohye_quiz_log_v1') || {};
  const reactions = ss.getJSON('ohye_reactions_v1') || {};
  const articleTime = ss.getJSON('ohye_article_time_v1') || {};
  const clientId = ss.get('ohye_client_id') || '';

  // Discussion drafts: scan every key starting with 'ohye_response_'
  const discussions = {};
  try {
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key && key.startsWith('ohye_response_')) {
        // key shape: ohye_response_<storyId>_<level>
        // storyId is a slug that may contain dashes; level is one of unk|Sprout|Tree.
        // Match level off the end conservatively.
        const m = key.match(/^ohye_response_(.+)_(unk|Sprout|Tree)$/);
        if (m) {
          discussions[`${m[1]}|${m[2]}`] = ss.getJSON(key);
        } else {
          // Fallback: take everything after the prefix as composite key.
          const tail = key.slice('ohye_response_'.length);
          discussions[tail] = ss.getJSON(key);
        }
      }
    }
  } catch (e) {/* localStorage iteration can throw under tight CSP */}

  const articles = window.ARTICLES || [];
  const byStoryLevel = {};
  for (const a of articles) {
    byStoryLevel[`${a.storyId}|${a.level || ''}`] = a;
  }

  // Days where any quiz attempt or discussion round happened. Today's
  // progress.dayKey gets folded in too so a "Today" entry exists even
  // before any quiz/discussion activity. Sorted newest-first.
  const daysSeen = new Set();
  for (const arr of Object.values(quizLog)) {
    for (const e of arr) { const dk = localDayKey(e.at); if (dk) daysSeen.add(dk); }
  }
  for (const d of Object.values(discussions)) {
    for (const r of (d.rounds || [])) { const dk = localDayKey(r.at); if (dk) daysSeen.add(dk); }
  }
  if (progress.dayKey) {
    // progress.dayKey is a "Sat Apr 25 2026" string — convert via Date.parse.
    const dk = localDayKey(new Date(progress.dayKey).toISOString());
    if (dk) daysSeen.add(dk);
  }
  const availableDays = Array.from(daysSeen).sort().reverse();

  // Day-filter the raw maps in place so downstream aggregations are correct.
  // Reactions / articleTime aren't day-stamped so they pass through unchanged.
  const filteredQuizLog = {};
  if (dayFilter) {
    for (const [k, arr] of Object.entries(quizLog)) {
      const kept = (arr || []).filter(e => localDayKey(e.at) === dayFilter);
      if (kept.length) filteredQuizLog[k] = kept;
    }
  } else {
    Object.assign(filteredQuizLog, quizLog);
  }
  const filteredDiscussions = {};
  if (dayFilter) {
    for (const [k, d] of Object.entries(discussions)) {
      const rounds = (d.rounds || []).filter(r => localDayKey(r.at) === dayFilter);
      if (rounds.length) filteredDiscussions[k] = { ...d, rounds };
    }
  } else {
    Object.assign(filteredDiscussions, discussions);
  }

  // Every story|level the kid has touched (post-filter).
  const touched = new Set();
  Object.keys(filteredQuizLog).forEach(k => touched.add(k));
  Object.keys(filteredDiscussions).forEach(k => touched.add(k));
  // Lifetime sources (reactions, article time) only contribute when no
  // day filter is active — otherwise they'd polute a day-specific view.
  if (!dayFilter) {
    Object.keys(reactions).forEach(k => touched.add(k));
    Object.keys(articleTime).forEach(k => touched.add(k));
    for (const id of Object.keys(progress.articleProgress || {})) {
      const a = articles.find(x => x.id === id);
      if (a) touched.add(`${a.storyId}|${a.level || ''}`);
    }
  }

  const articleStats = Array.from(touched).map(k => {
    const [storyId, level] = k.split('|');
    const article = byStoryLevel[k] || articles.find(a => a.storyId === storyId) || {};
    const articleId = article.id || `${storyId}-${level}`;
    const aProgress = (progress.articleProgress || {})[articleId] || null;
    const steps = (aProgress && aProgress.steps) || [];
    const quizAttempts = filteredQuizLog[k] || [];
    const lastQuiz = quizAttempts.length ? quizAttempts[quizAttempts.length - 1] : null;
    const bestQuiz = quizAttempts.reduce((b, q) => (!b || q.correct > b.correct ? q : b), null);
    const reaction = dayFilter ? null : (reactions[k] || null);
    const timeMs = dayFilter ? 0 : (articleTime[k] || 0);
    const discussion = filteredDiscussions[k] || null;
    return {
      key: k, storyId, level, articleId,
      title: article.title || '(unknown article)',
      category: article.category || null,
      image: article.image || null,
      quizDef: article.quiz || [],
      steps, quizAttempts, lastQuiz, bestQuiz,
      reaction, timeMs, discussion,
    };
  }).sort((a, b) => {
    const ta = a.lastQuiz ? Date.parse(a.lastQuiz.at) : 0;
    const tb = b.lastQuiz ? Date.parse(b.lastQuiz.at) : 0;
    if (ta !== tb) return tb - ta;
    return (b.timeMs || 0) - (a.timeMs || 0);
  });

  // Aggregate quiz stats — uses the LAST attempt per article (kid's
  // current proficiency), but also tracks total tries for the "retried" call-out.
  const allAttempts = Object.values(filteredQuizLog).flat();
  const totalAttempts = allAttempts.length;
  const totalCorrect = allAttempts.reduce((s, a) => s + (a.correct || 0), 0);
  const totalQuestions = allAttempts.reduce((s, a) => s + (a.total || 0), 0);
  const avgPct = pct(totalCorrect, totalQuestions);
  const retried = articleStats.filter(s => (s.quizAttempts || []).length > 1).length;

  // Wrong answers (using the LAST attempt per article) — joined with quiz def
  // so the parent sees the question text + correct answer.
  const wrongAnswers = [];
  for (const s of articleStats) {
    if (!s.lastQuiz || !s.quizDef.length) continue;
    s.lastQuiz.picks.forEach((pick, i) => {
      if (i >= s.quizDef.length) return;
      const q = s.quizDef[i];
      if (pick !== q.a) {
        wrongAnswers.push({
          articleTitle: s.title,
          category: s.category,
          question: q.q,
          picked: q.options[pick],
          correct: q.options[q.a],
          at: s.lastQuiz.at,
        });
      }
    });
  }
  wrongAnswers.sort((a, b) => Date.parse(b.at || 0) - Date.parse(a.at || 0));

  // Wrong-rate per category
  const catStats = {};
  for (const s of articleStats) {
    if (!s.lastQuiz) continue;
    const c = s.category || 'Unknown';
    if (!catStats[c]) catStats[c] = { correct: 0, total: 0, articles: 0 };
    catStats[c].correct += s.lastQuiz.correct;
    catStats[c].total += s.lastQuiz.total;
    catStats[c].articles += 1;
  }

  // Reactions tally — lifetime only (no per-day data on disk).
  const reactionCounts = { love: 0, thinky: 0, meh: 0, dislike: 0 };
  for (const r of Object.values(reactions)) {
    if (reactionCounts[r] !== undefined) reactionCounts[r]++;
  }

  // Discussion list — ordered by recent activity (last round 'at')
  const discussionList = Object.entries(filteredDiscussions).map(([k, d]) => {
    const article = byStoryLevel[k] || {};
    const rounds = d.rounds || [];
    const lastRound = rounds.length ? rounds[rounds.length - 1] : null;
    const finalText = (d.savedFinal && d.currentDraft)
      ? d.currentDraft
      : (lastRound ? lastRound.userText : '');
    const wc = (finalText || '').trim().split(/\s+/).filter(Boolean).length;
    return {
      key: k,
      title: article.title || '(unknown article)',
      category: article.category || null,
      rounds: rounds.length,
      savedFinal: !!d.savedFinal,
      finalText, wordCount: wc,
      updatedAt: lastRound ? lastRound.at : null,
    };
  }).sort((a, b) => Date.parse(b.updatedAt || 0) - Date.parse(a.updatedAt || 0));

  // Lifetime summary numbers
  const totalReadingMs = Object.values(articleTime).reduce((s, v) => s + (v || 0), 0);
  const articlesTouched = articleStats.length;
  const articlesAllStepsDone = articleStats.filter(s =>
    ['read', 'analyze', 'quiz', 'discuss'].every(st => s.steps.includes(st))
  ).length;

  return {
    tweaks, progress, clientId,
    availableDays, dayFilter: dayFilter || null,
    articleStats, discussionList, wrongAnswers,
    reactionCounts, catStats,
    totalAttempts, totalCorrect, totalQuestions, avgPct, retried,
    totalReadingMs, articlesTouched, articlesAllStepsDone,
  };
}

// ──────────────────────────────────────────────────────────────────────
// Cloud mode — Google auth + Supabase reads
// ──────────────────────────────────────────────────────────────────────

// Subscribe to Supabase auth state. Returns { session, signIn, signOut }.
function useAuth() {
  const [session, setSession] = useState(null);
  useEffect(() => {
    if (!sb) return;
    sb.auth.getSession().then(({ data }) => setSession(data.session || null));
    const { data: sub } = sb.auth.onAuthStateChange((_evt, s) => setSession(s));
    return () => sub.subscription && sub.subscription.unsubscribe();
  }, []);
  const signIn = () => {
    if (!sb) return;
    sb.auth.signInWithOAuth({
      provider: 'google',
      options: { redirectTo: window.location.origin + window.location.pathname },
    });
  };
  const signOut = async () => { if (sb) { await sb.auth.signOut(); setSession(null); } };
  return { session, signIn, signOut };
}

// On first sign-in, register the parent row + claim the local kid (if a
// client_id sits in this device's localStorage), then fetch the parent's
// full kid roster. Returns { kids, loading, error, refresh }.
function useKids(session) {
  const [kids, setKids] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const [parentRow, setParentRow] = useState(null);
  const refresh = async () => {
    if (!sb || !session) { setKids([]); setParentRow(null); return; }
    setLoading(true); setError(null);
    try {
      // upsert_parent_self() is idempotent; safe to call on every mount.
      await sb.rpc('upsert_parent_self', { p_name: session.user.user_metadata?.full_name || null });
      // After upsert we can read back our parent row (RLS allows self-select).
      const { data: prow } = await sb
        .from('redesign_parent_users')
        .select('*')
        .eq('email', session.user.email)
        .maybeSingle();
      setParentRow(prow || null);
      // Same-device claim — links the kid on this device to the parent
      // who just signed in. Errors silently if already linked elsewhere
      // (RLS will simply hide the row instead).
      const cid = window.safeStorage.get('ohye_client_id');
      if (cid) {
        const { error: claimErr } = await sb.rpc('claim_kid_for_caller', { p_client_id: cid });
        if (claimErr && !/already linked/i.test(claimErr.message || '')) {
          console.warn('[parent] claim_kid_for_caller', claimErr.message);
        }
      }
      const { data, error: kerr } = await sb
        .from('redesign_kid_profiles')
        .select('*')
        .order('last_seen_at', { ascending: false });
      if (kerr) throw kerr;
      setKids(data || []);
    } catch (e) {
      setError(e.message || String(e));
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { refresh(); }, [session && session.user && session.user.id]);
  return { kids, loading, error, refresh, parentRow };
}

// Cadence toggle + "Send me a copy now" button. The "Send now" button
// posts to send-digest with ?force=1&email=<self> so the parent can preview
// the email format without waiting for the cron.
function DigestCadenceToggle({ parentRow, session, onChanged }) {
  const [busy, setBusy] = useState(false);
  const [busySend, setBusySend] = useState(false);
  const [sendStatus, setSendStatus] = useState(null); // null | 'ok' | string(err)
  const cur = (parentRow && parentRow.digest_cadence) || 'off';

  const setCadence = async (c) => {
    if (!sb || c === cur) return;
    setBusy(true);
    const { error } = await sb.rpc('set_digest_cadence', { p_cadence: c });
    setBusy(false);
    if (error) { console.warn('[parent] set_digest_cadence', error.message); return; }
    onChanged && onChanged();
  };

  const sendNow = async () => {
    if (!session || !session.user || !session.user.email) return;
    setBusySend(true); setSendStatus(null);
    try {
      const url = SUPABASE_URL + '/functions/v1/send-digest?force=1&email=' + encodeURIComponent(session.user.email);
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: '{}',
      });
      const data = await res.json();
      if (data && data.sent === 1) {
        setSendStatus('ok');
        onChanged && onChanged();
      } else {
        const reason = (data && data.results && data.results[0] && data.results[0].reason)
          || (data && data.error)
          || 'No kids linked yet — claim a kid first.';
        setSendStatus(reason);
      }
    } catch (e) {
      setSendStatus(e.message || String(e));
    }
    setBusySend(false);
    // Auto-dismiss after a few seconds.
    setTimeout(() => setSendStatus(null), 6000);
  };

  return (
    <div style={{ marginTop: 12, display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap', fontSize: 12 }}>
      <span style={{ color: '#6b5c80', fontWeight: 700 }}>📬 Email digest:</span>
      {[
        { id: 'off', label: 'Off' },
        { id: 'weekly', label: 'Weekly · Sun morning' },
        { id: 'daily', label: 'Daily' },
      ].map(c => (
        <button key={c.id} onClick={() => setCadence(c.id)} disabled={busy} style={{
          background: cur === c.id ? '#1b1230' : '#fff',
          color: cur === c.id ? '#ffc83d' : '#1b1230',
          border: `2px solid ${cur === c.id ? '#1b1230' : '#f0e8d8'}`,
          borderRadius: 999, padding: '4px 12px', fontWeight: 700, fontSize: 12,
          cursor: busy ? 'wait' : 'pointer', fontFamily: 'Nunito, sans-serif',
        }}>{c.label}</button>
      ))}
      <button onClick={sendNow} disabled={busySend || cur === 'off'}
        title={cur === 'off' ? 'Set a cadence first' : 'Send a digest to your inbox right now'}
        style={{
          background: '#fff', color: '#1b1230',
          border: '2px solid #ffc83d', borderRadius: 999,
          padding: '4px 12px', fontWeight: 800, fontSize: 12,
          cursor: (busySend || cur === 'off') ? 'not-allowed' : 'pointer',
          opacity: cur === 'off' ? 0.55 : 1,
          fontFamily: 'Nunito, sans-serif',
        }}>{busySend ? 'Sending…' : '📤 Send me a copy now'}</button>
      {sendStatus === 'ok' && (
        <span style={{ color: '#0e8d82', fontWeight: 800 }}>✓ Sent — check your inbox.</span>
      )}
      {sendStatus && sendStatus !== 'ok' && (
        <span style={{ color: '#b22525', fontWeight: 700 }}>✗ {sendStatus}</span>
      )}
      {parentRow && parentRow.digest_last_sent_at && (
        <span style={{ color: '#9a8d7a' }}>· last sent {formatRelative(parentRow.digest_last_sent_at)}</span>
      )}
    </div>
  );
}

// Convert Supabase rows into the same `stats` shape the local collector
// produces, so every existing render component just works.
//
// dayFilter (string|null) — same semantics as local mode.
async function cloudCollectStats(clientId, dayFilter) {
  if (!sb || !clientId) return null;
  const baseEvents = sb.from('redesign_reading_events').select('*').eq('client_id', clientId);
  const baseQuiz = sb.from('redesign_quiz_attempts').select('*').eq('client_id', clientId);
  const baseDisc = sb.from('redesign_discussion_responses').select('*').eq('client_id', clientId);

  const [profileRes, eventsRes, quizRes, reactionsRes, discRes] = await Promise.all([
    sb.from('redesign_kid_profiles').select('*').eq('client_id', clientId).maybeSingle(),
    (dayFilter ? baseEvents.eq('day_key', dayFilter) : baseEvents).order('occurred_at', { ascending: false }),
    (dayFilter ? baseQuiz.eq('day_key', dayFilter) : baseQuiz).order('attempted_at', { ascending: false }),
    sb.from('redesign_article_reactions').select('*').eq('client_id', clientId),
    baseDisc.order('updated_at', { ascending: false }),
  ]);

  const profile = profileRes.data || {};
  const events = eventsRes.data || [];
  const quizzes = quizRes.data || [];
  const reactionRows = reactionsRes.data || [];
  const discRows = discRes.data || [];

  const articles = window.ARTICLES || [];
  const byStoryLevel = {};
  for (const a of articles) byStoryLevel[`${a.storyId}|${a.level || ''}`] = a;

  // Aggregate quiz attempts per (story|level)
  const quizByKey = {};
  for (const q of quizzes) {
    const k = `${q.story_id}|${q.level || ''}`;
    if (!quizByKey[k]) quizByKey[k] = [];
    // Re-shape to match localStorage entry: { at, picks, correct, total, durationMs }
    quizByKey[k].push({
      at: q.attempted_at, picks: q.picks || [],
      correct: q.correct, total: q.total, durationMs: q.duration_ms,
    });
  }
  // Sort each by `at` ASC so "last attempt" matches local-mode semantics.
  for (const k of Object.keys(quizByKey)) quizByKey[k].sort((a, b) => Date.parse(a.at) - Date.parse(b.at));

  // Group events for time-spent + steps inferred from event log.
  const eventsByKey = {};
  for (const e of events) {
    const k = `${e.story_id}|${e.level || ''}`;
    if (!eventsByKey[k]) eventsByKey[k] = [];
    eventsByKey[k].push(e);
  }

  // Reactions table → {key: reaction}
  const reactions = {};
  for (const r of reactionRows) reactions[`${r.story_id}|${r.level || ''}`] = r.reaction;

  // Discussions table → {key: {rounds, savedFinal, currentDraft?}}
  const discussions = {};
  for (const d of discRows) {
    const lastRound = (d.rounds && d.rounds.length) ? d.rounds[d.rounds.length - 1] : null;
    discussions[`${d.story_id}|${d.level || ''}`] = {
      rounds: d.rounds || [],
      savedFinal: !!d.saved_final,
      // Cloud table doesn't store currentDraft separately; falls back to
      // last round's userText so the parent dashboard's "final saved"
      // panel still renders meaningful text.
      currentDraft: d.saved_final && lastRound ? lastRound.userText : '',
      updated_at: d.updated_at,
    };
  }

  // Days seen — from quiz attempts + discussion rounds
  const daysSeen = new Set();
  for (const q of quizzes) { const dk = q.day_key || localDayKey(q.attempted_at); if (dk) daysSeen.add(dk); }
  for (const k of Object.keys(discussions)) {
    for (const r of (discussions[k].rounds || [])) { const dk = localDayKey(r.at); if (dk) daysSeen.add(dk); }
  }
  for (const e of events) { if (e.day_key) daysSeen.add(e.day_key); }
  const availableDays = Array.from(daysSeen).sort().reverse();

  // Touched articles — union of every source.
  const touched = new Set();
  Object.keys(quizByKey).forEach(k => touched.add(k));
  Object.keys(discussions).forEach(k => touched.add(k));
  if (!dayFilter) {
    Object.keys(reactions).forEach(k => touched.add(k));
    Object.keys(eventsByKey).forEach(k => touched.add(k));
  }

  const articleStats = Array.from(touched).map(k => {
    const [storyId, level] = k.split('|');
    const article = byStoryLevel[k] || articles.find(a => a.storyId === storyId) || {};
    const events = eventsByKey[k] || [];
    // Steps: compute from the unique step values in events for this article
    // ('open' is excluded — it's just the visit marker).
    const stepSet = new Set(events.map(e => e.step).filter(s => ['read','analyze','quiz','discuss'].includes(s)));
    const steps = ['read','analyze','quiz','discuss'].filter(s => stepSet.has(s));
    const quizAttempts = quizByKey[k] || [];
    const lastQuiz = quizAttempts.length ? quizAttempts[quizAttempts.length - 1] : null;
    const bestQuiz = quizAttempts.reduce((b, q) => (!b || q.correct > b.correct ? q : b), null);
    // Time on article: sum of duration_ms across events
    const timeMs = events.reduce((s, e) => s + (e.duration_ms || 0), 0);
    return {
      key: k, storyId, level,
      articleId: article.id || `${storyId}-${level}`,
      title: article.title || '(unknown article)',
      category: article.category || null,
      image: article.image || null,
      quizDef: article.quiz || [],
      steps, quizAttempts, lastQuiz, bestQuiz,
      reaction: dayFilter ? null : (reactions[k] || null),
      timeMs: dayFilter ? 0 : timeMs,
      discussion: discussions[k] || null,
    };
  }).sort((a, b) => {
    const ta = a.lastQuiz ? Date.parse(a.lastQuiz.at) : 0;
    const tb = b.lastQuiz ? Date.parse(b.lastQuiz.at) : 0;
    if (ta !== tb) return tb - ta;
    return (b.timeMs || 0) - (a.timeMs || 0);
  });

  // Aggregate quiz stats — same calculation as local mode.
  const allAttempts = Object.values(quizByKey).flat();
  const totalAttempts = allAttempts.length;
  const totalCorrect = allAttempts.reduce((s, a) => s + (a.correct || 0), 0);
  const totalQuestions = allAttempts.reduce((s, a) => s + (a.total || 0), 0);
  const avgPct = pct(totalCorrect, totalQuestions);
  const retried = articleStats.filter(s => (s.quizAttempts || []).length > 1).length;

  // Wrong answers
  const wrongAnswers = [];
  for (const s of articleStats) {
    if (!s.lastQuiz || !s.quizDef.length) continue;
    s.lastQuiz.picks.forEach((pick, i) => {
      if (i >= s.quizDef.length) return;
      const q = s.quizDef[i];
      if (pick !== q.a) {
        wrongAnswers.push({
          articleTitle: s.title, category: s.category,
          question: q.q, picked: q.options[pick], correct: q.options[q.a],
          at: s.lastQuiz.at,
        });
      }
    });
  }
  wrongAnswers.sort((a, b) => Date.parse(b.at || 0) - Date.parse(a.at || 0));

  // Wrong-rate per category
  const catStats = {};
  for (const s of articleStats) {
    if (!s.lastQuiz) continue;
    const c = s.category || 'Unknown';
    if (!catStats[c]) catStats[c] = { correct: 0, total: 0, articles: 0 };
    catStats[c].correct += s.lastQuiz.correct;
    catStats[c].total += s.lastQuiz.total;
    catStats[c].articles += 1;
  }

  // Reactions tally (lifetime only)
  const reactionCounts = { love: 0, thinky: 0, meh: 0, dislike: 0 };
  for (const r of Object.values(reactions)) {
    if (reactionCounts[r] !== undefined) reactionCounts[r]++;
  }

  // Discussion list
  const discussionList = Object.entries(discussions).map(([k, d]) => {
    const article = byStoryLevel[k] || {};
    const lastRound = d.rounds && d.rounds.length ? d.rounds[d.rounds.length - 1] : null;
    const finalText = (d.savedFinal && d.currentDraft) ? d.currentDraft : (lastRound ? lastRound.userText : '');
    const wc = (finalText || '').trim().split(/\s+/).filter(Boolean).length;
    return {
      key: k,
      title: article.title || '(unknown article)',
      category: article.category || null,
      rounds: (d.rounds || []).length,
      savedFinal: !!d.savedFinal,
      finalText, wordCount: wc,
      updatedAt: lastRound ? lastRound.at : d.updated_at,
    };
  }).sort((a, b) => Date.parse(b.updatedAt || 0) - Date.parse(a.updatedAt || 0));

  // Lifetime totals
  const totalReadingMs = events.reduce((s, e) => s + (e.duration_ms || 0), 0);
  const articlesTouched = articleStats.length;
  const articlesAllStepsDone = articleStats.filter(s =>
    ['read','analyze','quiz','discuss'].every(st => s.steps.includes(st))
  ).length;

  // Today's progress reconstructed from today's events.
  const today = localDayKey(new Date().toISOString());
  const todaysEvents = events.filter(e => e.day_key === today);
  const minutesToday = todaysEvents.reduce((s, e) => s + (parseFloat(e.minutes_added) || 0), 0);
  const readToday = Array.from(new Set(todaysEvents.filter(e => e.step === 'finish').map(e => e.story_id)));
  const startedToday = new Set(todaysEvents.map(e => e.story_id)).size;

  // tweaks-shaped object pulled from kid_profile so HeaderStrip + Settings render.
  const tweaks = {
    userName: profile.display_name || '',
    avatar: profile.avatar || 'panda',
    level: profile.level || '',
    language: profile.language || '',
    theme: profile.theme || '',
    dailyGoal: profile.daily_goal || 21,
    streakDays: 0, // streak compute lives in app state on the kid's device
  };
  const progress = {
    readToday, minutesToday,
    articleProgress: Object.fromEntries(articleStats.map(s => [s.articleId, { steps: s.steps, lastTab: s.steps[s.steps.length - 1] || 'read' }])),
    dayKey: today,
  };

  // Synthetic "started today" — for TodayTile we expose articleProgress.length.
  // (TodayTile reads `Object.keys(progress.articleProgress).length` — that's
  // already accurate from the construction above.)

  return {
    tweaks, progress, clientId,
    availableDays, dayFilter: dayFilter || null,
    articleStats, discussionList, wrongAnswers,
    reactionCounts, catStats,
    totalAttempts, totalCorrect, totalQuestions, avgPct, retried,
    totalReadingMs, articlesTouched, articlesAllStepsDone,
  };
}

// ──────────────────────────────────────────────────────────────────────
// Components
// ──────────────────────────────────────────────────────────────────────

function CategoryChip({ cat, small }) {
  const c = CATEGORY_COLORS[cat] || { color: '#1b1230', bg: '#f0e8d8', emoji: '·' };
  return (
    <span className="pd-pill" style={{ background: c.bg, color: c.color, fontSize: small ? 11 : 12 }}>
      {c.emoji} {cat || '—'}
    </span>
  );
}

function ReactionChip({ reaction, small }) {
  if (!reaction) return null;
  const r = REACTION_LABELS[reaction];
  if (!r) return null;
  return (
    <span className="pd-pill" style={{ background: r.bg, color: r.color, fontSize: small ? 11 : 12 }}>
      {r.emoji} {r.label}
    </span>
  );
}

function HeaderStrip({ stats }) {
  const t = stats.tweaks || {};
  const avatar = t.avatar || 'panda';
  const avatarEmoji = ({
    fox:'🦊', panda:'🐼', octopus:'🐙', unicorn:'🦄', frog:'🐸', lion:'🦁',
    penguin:'🐧', tiger:'🐯', cat:'🐱', rocket:'🚀', turtle:'🐢', bear:'🐻'
  })[avatar] || '🐼';
  return (
    <div className="pd-card" style={{ display: 'flex', alignItems: 'center', gap: 18, flexWrap: 'wrap' }}>
      <div style={{
        width: 72, height: 72, borderRadius: 18, background: '#ffe2a8',
        display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 40, flexShrink: 0,
      }}>{avatarEmoji}</div>
      <div style={{ flex: 1, minWidth: 220 }}>
        <div style={{ fontFamily: 'Fraunces, serif', fontWeight: 900, fontSize: 28, color: '#1b1230', lineHeight: 1.05 }}>
          {t.userName || 'kidsnews reader'}
        </div>
        <div style={{ display: 'flex', gap: 8, marginTop: 8, flexWrap: 'wrap' }}>
          {t.level && <span className="pd-pill" style={{ background: '#fff4c2', color: '#8a6d00' }}>{t.level === 'Tree' ? '🌳 Tree' : '🌱 Sprout'}</span>}
          {t.language && <span className="pd-pill" style={{ background: '#e7f0ff', color: '#1f5fd1' }}>{t.language === 'zh' ? '🇨🇳 中文' : '🇬🇧 English'}</span>}
          <span className="pd-pill" style={{ background: '#ffe5d8', color: '#c14e2a' }}>🎯 {t.dailyGoal || 21} min/day</span>
          <span className="pd-pill" style={{ background: '#f5f0e8', color: '#6b5c80' }}>🔥 {t.streakDays || 0}-day streak</span>
        </div>
      </div>
      <div style={{ textAlign: 'right' }}>
        <div className="pd-num">{stats.articlesTouched}</div>
        <div className="pd-lab">articles read</div>
      </div>
      <div style={{ textAlign: 'right' }}>
        <div className="pd-num">{fmtMs(stats.totalReadingMs)}</div>
        <div className="pd-lab">reading time</div>
      </div>
    </div>
  );
}

// Small input row for the cross-device parent: enter a code the kid
// generated on their device, get linked. Posted to consume_pairing_code.
function PairingCodeInput({ onLinked }) {
  const [code, setCode] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const submit = async () => {
    if (!sb || !code) return;
    setBusy(true); setErr(null);
    const { error } = await sb.rpc('consume_pairing_code', { p_code: code.trim() });
    setBusy(false);
    if (error) { setErr(error.message); return; }
    setCode('');
    onLinked && onLinked();
  };
  return (
    <div style={{ marginTop: 10, display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
      <span style={{ fontSize: 12, fontWeight: 700, color: '#6b5c80' }}>Add a kid by code:</span>
      <input
        value={code}
        onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
        placeholder="000000"
        inputMode="numeric"
        style={{
          background: '#fff', border: '2px solid #f0e8d8', borderRadius: 10,
          padding: '5px 10px', fontSize: 16, fontFamily: 'Fraunces, serif',
          letterSpacing: '.2em', width: 110, textAlign: 'center',
        }}/>
      <button onClick={submit} disabled={busy || code.length !== 6} style={{
        background: code.length === 6 ? '#1b1230' : '#e8dfd3',
        color: code.length === 6 ? '#ffc83d' : '#9a8d7a',
        border: 'none', borderRadius: 10, padding: '6px 14px', fontWeight: 800, fontSize: 12,
        cursor: code.length === 6 ? 'pointer' : 'not-allowed',
        fontFamily: 'Nunito, sans-serif',
      }}>{busy ? '…' : 'Link'}</button>
      {err && <span style={{ fontSize: 12, color: '#b22525' }}>{err}</span>}
    </div>
  );
}

function CloudBanner({ session, kids, signIn, signOut, source, setSource, selectedKidId, setSelectedKidId, refreshKids, parentRow }) {
  if (!session) {
    return (
      <div style={{
        background: 'linear-gradient(135deg, #ffe2a8 0%, #ffc0a8 100%)',
        border: '2px solid #ffb98a', borderRadius: 18, padding: '14px 18px',
        display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap',
      }}>
        <div style={{ fontSize: 28 }}>📬</div>
        <div style={{ flex: 1, minWidth: 220 }}>
          <div style={{ fontFamily: 'Fraunces, serif', fontWeight: 800, fontSize: 16, color: '#1b1230' }}>
            Want a weekly email digest?
          </div>
          <div style={{ fontSize: 13, color: '#3a2a4a', marginTop: 2 }}>
            Sign in with Google to keep history beyond this device, view from anywhere, and get a Sunday morning summary.
          </div>
        </div>
        <button onClick={signIn} style={{
          background: '#1b1230', color: '#ffc83d', border: 'none', borderRadius: 14,
          padding: '10px 18px', fontWeight: 900, fontSize: 14, cursor: 'pointer',
          fontFamily: 'Nunito, sans-serif', boxShadow: '0 4px 0 rgba(0,0,0,0.18)',
        }}>Sign in with Google</button>
      </div>
    );
  }
  return (
    <div style={{
      background: '#fff', border: '2px solid #c8ebe3', borderRadius: 18, padding: '14px 18px',
      display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap',
    }}>
      <div style={{ fontSize: 28 }}>☁️</div>
      <div style={{ flex: 1, minWidth: 220 }}>
        <div style={{ fontFamily: 'Fraunces, serif', fontWeight: 800, fontSize: 15, color: '#1b1230' }}>
          Signed in as {session.user.email}
        </div>
        <div style={{ fontSize: 12, color: '#6b5c80', marginTop: 4 }}>
          {kids.length === 0 && 'No kids linked yet — open this dashboard from the kid\'s device to claim, or use a pairing code.'}
          {kids.length > 0 && <>Linked kid{kids.length === 1 ? '' : 's'}:</>}
        </div>
        {kids.length > 0 && (
          <div style={{ display: 'flex', gap: 8, marginTop: 8, flexWrap: 'wrap' }}>
            {kids.map(k => (
              <button key={k.client_id} onClick={() => setSelectedKidId(k.client_id)} style={{
                background: selectedKidId === k.client_id ? '#1b1230' : '#fff',
                color: selectedKidId === k.client_id ? '#ffc83d' : '#1b1230',
                border: `2px solid ${selectedKidId === k.client_id ? '#1b1230' : '#f0e8d8'}`,
                borderRadius: 999, padding: '5px 12px', fontWeight: 800, fontSize: 12, cursor: 'pointer',
                fontFamily: 'Nunito, sans-serif',
              }}>
                {(k.display_name || 'kid')} {k.level ? `· ${k.level}` : ''}
              </button>
            ))}
          </div>
        )}
        <PairingCodeInput onLinked={() => refreshKids && refreshKids()}/>
        <DigestCadenceToggle parentRow={parentRow} session={session} onChanged={() => refreshKids && refreshKids()}/>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <div style={{ display: 'inline-flex', borderRadius: 10, overflow: 'hidden', border: '2px solid #f0e8d8' }}>
          {['local', 'cloud'].map(s => (
            <button key={s} onClick={() => setSource(s)}
              disabled={s === 'cloud' && kids.length === 0}
              title={s === 'cloud' && kids.length === 0 ? 'No kids linked yet' : ''}
              style={{
                background: source === s ? '#1b1230' : '#fff',
                color: source === s ? '#ffc83d' : '#1b1230',
                border: 'none', padding: '6px 12px', fontWeight: 800, fontSize: 12,
                cursor: (s === 'cloud' && kids.length === 0) ? 'not-allowed' : 'pointer',
                opacity: (s === 'cloud' && kids.length === 0) ? 0.45 : 1,
                fontFamily: 'Nunito, sans-serif',
              }}>{s === 'local' ? '📱 This device' : '☁️ Cloud'}</button>
          ))}
        </div>
        <button onClick={signOut} style={{
          background: 'transparent', color: '#6b5c80', border: '1.5px solid #f0e8d8',
          borderRadius: 10, padding: '6px 12px', fontWeight: 700, fontSize: 12, cursor: 'pointer',
          fontFamily: 'Nunito, sans-serif',
        }}>Sign out</button>
      </div>
    </div>
  );
}

function TodayTile({ stats }) {
  const goal = stats.tweaks.dailyGoal || 21;
  const min = stats.progress.minutesToday || 0;
  const readToday = (stats.progress.readToday || []).length;
  const startedToday = Object.keys(stats.progress.articleProgress || {}).length;
  return (
    <div className="pd-card">
      <h2>Today</h2>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 12 }}>
        <div className="pd-tile">
          <div className="pd-num">{min}</div>
          <div className="pd-lab">of {goal} min</div>
          <div style={{ height: 8, background: '#f0e8d8', borderRadius: 999, marginTop: 10, overflow: 'hidden' }}>
            <div style={{
              width: `${Math.min(100, pct(min, goal))}%`, height: '100%',
              background: 'linear-gradient(90deg, #ffc83d, #ff8a3d)', borderRadius: 999,
            }}/>
          </div>
        </div>
        <div className="pd-tile"><div className="pd-num">{readToday}</div><div className="pd-lab">finished today</div></div>
        <div className="pd-tile"><div className="pd-num">{startedToday}</div><div className="pd-lab">started today</div></div>
      </div>
    </div>
  );
}

function ArticleRow({ s, expanded, onToggle }) {
  const cat = CATEGORY_COLORS[s.category] || {};
  const stepBadge = (id, label, emoji) => {
    const done = s.steps.includes(id);
    return (
      <span className="pd-pill" style={{
        background: done ? '#d4f3ef' : '#f5f0e8',
        color: done ? '#0e8d82' : '#9a8d7a',
        fontSize: 11, marginRight: 6,
      }}>{done ? '✅' : emoji} {label}</span>
    );
  };
  return (
    <div style={{ borderBottom: '1px dashed #f0e8d8', padding: '12px 0' }}>
      <div style={{ display: 'flex', gap: 14, alignItems: 'flex-start', flexWrap: 'wrap' }}>
        {s.image
          ? <div style={{ width: 64, height: 64, borderRadius: 10, flexShrink: 0, background: `url(${s.image}) center/cover, ${cat.color || '#ddd'}`, border: '2px solid #f0e8d8' }}/>
          : <div style={{ width: 64, height: 64, borderRadius: 10, flexShrink: 0, background: '#f5f0e8' }}/>
        }
        <div style={{ flex: 1, minWidth: 220 }}>
          <div style={{ fontFamily: 'Fraunces, serif', fontWeight: 800, fontSize: 16, color: '#1b1230', lineHeight: 1.3 }}>
            {s.title}
          </div>
          <div style={{ marginTop: 6, display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
            <CategoryChip cat={s.category} small/>
            {s.level && <span className="pd-pill" style={{ background: '#fff4c2', color: '#8a6d00', fontSize: 11 }}>{s.level}</span>}
            <span style={{ fontSize: 11, color: '#9a8d7a' }}>· {fmtMs(s.timeMs)} reading time</span>
            {s.lastQuiz && <span style={{ fontSize: 11, color: '#9a8d7a' }}>· {formatRelative(s.lastQuiz.at)}</span>}
          </div>
          <div style={{ marginTop: 8 }}>
            {stepBadge('read', 'Read', '📖')}
            {stepBadge('analyze', 'Background', '🔍')}
            {s.lastQuiz
              ? <span className="pd-pill" style={{ background: '#fff4c2', color: '#8a6d00', fontSize: 11, marginRight: 6 }}>🎯 {s.lastQuiz.correct}/{s.lastQuiz.total} {s.quizAttempts.length > 1 ? `· tried ${s.quizAttempts.length}×` : ''}</span>
              : stepBadge('quiz', 'Quiz', '🎯')}
            {s.discussion && s.discussion.rounds && s.discussion.rounds.length
              ? <span className="pd-pill" style={{ background: '#efe9ff', color: '#9061f9', fontSize: 11, marginRight: 6 }}>✏️ {s.discussion.rounds.length} round{s.discussion.rounds.length === 1 ? '' : 's'}{s.discussion.savedFinal ? ' · final saved' : ''}</span>
              : stepBadge('discuss', 'Discussion', '✏️')}
            <ReactionChip reaction={s.reaction} small/>
          </div>
        </div>
        <button onClick={onToggle} style={{
          background: '#fff', border: '2px solid #f0e8d8', borderRadius: 10,
          padding: '6px 12px', cursor: 'pointer', fontWeight: 700, fontSize: 12, color: '#1b1230',
        }}>{expanded ? 'Hide' : 'Details'}</button>
      </div>
      {expanded && <ArticleDetail s={s}/>}
    </div>
  );
}

function ArticleDetail({ s }) {
  return (
    <div style={{ marginTop: 14, padding: '14px 16px', background: '#fff9ef', borderRadius: 12, border: '1px dashed #e8dcc6' }}>
      {s.lastQuiz && s.quizDef.length > 0 && (
        <div>
          <div style={{ fontSize: 12, fontWeight: 800, color: '#6b5c80', textTransform: 'uppercase', letterSpacing: '.06em', marginBottom: 8 }}>
            Last quiz attempt — {s.lastQuiz.correct}/{s.lastQuiz.total} correct {s.lastQuiz.durationMs ? `· ${fmtMs(s.lastQuiz.durationMs)}` : ''}
          </div>
          {s.lastQuiz.picks.map((pick, i) => {
            if (i >= s.quizDef.length) return null;
            const q = s.quizDef[i];
            const right = pick === q.a;
            return (
              <div key={i} style={{ marginBottom: 10, padding: '8px 12px', background: '#fff', border: `1.5px solid ${right ? '#c8ebe3' : '#ffd0d0'}`, borderRadius: 8 }}>
                <div style={{ fontSize: 13, fontWeight: 700, color: '#1b1230' }}>{i + 1}. {q.q}</div>
                <div style={{ fontSize: 12, marginTop: 4, color: right ? '#0e8d82' : '#b22525' }}>
                  {right ? '✓' : '✗'} Picked: <i>{q.options[pick] ?? '(no answer)'}</i>
                  {!right && <> &nbsp;·&nbsp; Correct: <b>{q.options[q.a]}</b></>}
                </div>
              </div>
            );
          })}
          {s.quizAttempts.length > 1 && (
            <div style={{ marginTop: 6, fontSize: 11, color: '#9a8d7a' }}>
              {s.quizAttempts.length} attempts total · best score {s.bestQuiz?.correct}/{s.bestQuiz?.total}
            </div>
          )}
        </div>
      )}
      {s.discussion && s.discussion.rounds && s.discussion.rounds.length > 0 && (
        <div style={{ marginTop: 14 }}>
          <div style={{ fontSize: 12, fontWeight: 800, color: '#6b5c80', textTransform: 'uppercase', letterSpacing: '.06em', marginBottom: 8 }}>
            Discussion drafts ({s.discussion.rounds.length} round{s.discussion.rounds.length === 1 ? '' : 's'})
            {s.discussion.savedFinal && ' · ⭐ saved as final'}
          </div>
          {s.discussion.rounds.map((r, i) => (
            <div key={i} style={{ marginBottom: 10, padding: '10px 12px', background: '#fff', borderRadius: 8, border: '1.5px solid #f0e8d8' }}>
              <div style={{ fontSize: 11, color: '#6b5c80', fontWeight: 700, marginBottom: 6 }}>
                Round {i + 1} · {formatRelative(r.at)}
              </div>
              <div style={{ fontSize: 13.5, color: '#1b1230', whiteSpace: 'pre-wrap', lineHeight: 1.5 }}>{r.userText}</div>
            </div>
          ))}
          {s.discussion.savedFinal && s.discussion.currentDraft && (
            <div style={{ padding: '10px 12px', background: '#d6f3ed', borderRadius: 8, border: '1.5px solid #17b3a6' }}>
              <div style={{ fontSize: 11, color: '#0e8d82', fontWeight: 800, marginBottom: 6 }}>⭐ Final saved answer</div>
              <div style={{ fontSize: 13.5, color: '#1b1230', whiteSpace: 'pre-wrap', lineHeight: 1.5 }}>{s.discussion.currentDraft}</div>
            </div>
          )}
        </div>
      )}
      {!s.lastQuiz && (!s.discussion || !s.discussion.rounds || s.discussion.rounds.length === 0) && (
        <div className="pd-empty">No quiz attempts or discussion drafts yet.</div>
      )}
    </div>
  );
}

function ArticlesList({ stats }) {
  const [expanded, setExpanded] = useState({});
  const toggle = (k) => setExpanded(p => ({ ...p, [k]: !p[k] }));
  if (!stats.articleStats.length) {
    return (
      <div className="pd-card">
        <h2>Articles</h2>
        <div className="pd-empty">No articles touched yet on this device.</div>
      </div>
    );
  }
  return (
    <div className="pd-card">
      <h2>Articles ({stats.articleStats.length})</h2>
      {stats.articleStats.map(s => (
        <ArticleRow key={s.key} s={s} expanded={!!expanded[s.key]} onToggle={() => toggle(s.key)}/>
      ))}
    </div>
  );
}

function QuizSummary({ stats }) {
  return (
    <div className="pd-card">
      <h2>Quiz performance</h2>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 12, marginBottom: 18 }}>
        <div className="pd-tile"><div className="pd-num">{stats.totalAttempts}</div><div className="pd-lab">quizzes taken</div></div>
        <div className="pd-tile"><div className="pd-num">{stats.avgPct}%</div><div className="pd-lab">avg correct</div></div>
        <div className="pd-tile"><div className="pd-num">{stats.totalCorrect}</div><div className="pd-lab">questions right</div></div>
        <div className="pd-tile"><div className="pd-num">{stats.retried}</div><div className="pd-lab">articles retried</div></div>
      </div>

      {Object.keys(stats.catStats).length > 0 && (
        <div style={{ marginBottom: 18 }}>
          <div style={{ fontSize: 12, fontWeight: 800, color: '#6b5c80', textTransform: 'uppercase', letterSpacing: '.06em', marginBottom: 8 }}>
            By category (last attempt per article)
          </div>
          {Object.entries(stats.catStats).map(([cat, s]) => {
            const right = s.total ? Math.round((s.correct / s.total) * 100) : 0;
            const wrong = 100 - right;
            const c = CATEGORY_COLORS[cat] || { color: '#1b1230' };
            return (
              <div key={cat} style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
                <div style={{ width: 100, fontWeight: 800, fontSize: 13, color: c.color }}>
                  {(c.emoji || '·')} {cat}
                </div>
                <div style={{ flex: 1, height: 14, background: '#ffe4e4', borderRadius: 999, position: 'relative', overflow: 'hidden' }}>
                  <div style={{ width: `${right}%`, height: '100%', background: c.color, borderRadius: 999 }}/>
                </div>
                <div style={{ width: 110, textAlign: 'right', fontSize: 12, fontWeight: 700, color: '#6b5c80' }}>
                  {right}% right · {wrong}% wrong
                </div>
              </div>
            );
          })}
        </div>
      )}

      {stats.wrongAnswers.length > 0 && (
        <div>
          <div style={{ fontSize: 12, fontWeight: 800, color: '#6b5c80', textTransform: 'uppercase', letterSpacing: '.06em', marginBottom: 8 }}>
            Recent wrong answers ({stats.wrongAnswers.length})
          </div>
          {stats.wrongAnswers.slice(0, 10).map((w, i) => (
            <div key={i} style={{ marginBottom: 10, padding: '10px 12px', background: '#fff9ef', borderRadius: 8, border: '1px dashed #e8dcc6' }}>
              <div style={{ fontSize: 11, color: '#6b5c80', fontWeight: 700, marginBottom: 4 }}>
                <CategoryChip cat={w.category} small/> · {w.articleTitle.slice(0, 60)}{w.articleTitle.length > 60 ? '…' : ''}
              </div>
              <div style={{ fontSize: 13, fontWeight: 700, color: '#1b1230', marginBottom: 4 }}>{w.question}</div>
              <div style={{ fontSize: 12, color: '#b22525' }}>✗ Picked: <i>{w.picked || '(blank)'}</i></div>
              <div style={{ fontSize: 12, color: '#0e8d82' }}>✓ Correct: <b>{w.correct}</b></div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function DiscussionPanel({ stats }) {
  const list = stats.discussionList;
  if (!list.length) {
    return (
      <div className="pd-card">
        <h2>Discussion drafts</h2>
        <div className="pd-empty">No discussion drafts saved yet.</div>
      </div>
    );
  }
  const totalRounds = list.reduce((s, d) => s + d.rounds, 0);
  const totalWords = list.reduce((s, d) => s + d.wordCount, 0);
  const finals = list.filter(d => d.savedFinal).length;
  return (
    <div className="pd-card">
      <h2>Discussion drafts</h2>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 12, marginBottom: 18 }}>
        <div className="pd-tile"><div className="pd-num">{list.length}</div><div className="pd-lab">articles written</div></div>
        <div className="pd-tile"><div className="pd-num">{totalRounds}</div><div className="pd-lab">coach rounds</div></div>
        <div className="pd-tile"><div className="pd-num">{totalWords}</div><div className="pd-lab">total words</div></div>
        <div className="pd-tile"><div className="pd-num">{finals}</div><div className="pd-lab">final saves</div></div>
      </div>
      {list.slice(0, 5).map(d => (
        <div key={d.key} style={{ marginBottom: 12, padding: '12px 14px', background: '#fff9ef', borderRadius: 10, border: '1px dashed #e8dcc6' }}>
          <div style={{ fontFamily: 'Fraunces, serif', fontWeight: 800, fontSize: 14, color: '#1b1230', marginBottom: 4 }}>
            {d.savedFinal ? '⭐ ' : ''}{d.title}
          </div>
          <div style={{ fontSize: 11, color: '#9a8d7a', marginBottom: 8 }}>
            <CategoryChip cat={d.category} small/> · {d.wordCount} words · {d.rounds} round{d.rounds === 1 ? '' : 's'} · {formatRelative(d.updatedAt)}
          </div>
          <div style={{ fontSize: 13, lineHeight: 1.5, color: '#1b1230', whiteSpace: 'pre-wrap' }}>
            {(d.finalText || '').slice(0, 280)}{(d.finalText || '').length > 280 ? '…' : ''}
          </div>
        </div>
      ))}
    </div>
  );
}

function ReactionsPanel({ stats }) {
  const counts = stats.reactionCounts;
  const total = counts.love + counts.thinky + counts.meh + counts.dislike;
  if (total === 0) {
    return (
      <div className="pd-card">
        <h2>Reactions</h2>
        <div className="pd-empty">No reactions saved yet.</div>
      </div>
    );
  }
  return (
    <div className="pd-card">
      <h2>Reactions</h2>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 12 }}>
        {['love', 'thinky', 'meh', 'dislike'].map(k => {
          const r = REACTION_LABELS[k];
          return (
            <div key={k} className="pd-tile" style={{ background: r.bg, borderColor: r.color, borderWidth: 2 }}>
              <div style={{ fontSize: 28 }}>{r.emoji}</div>
              <div className="pd-num" style={{ color: r.color, fontSize: 28 }}>{counts[k]}</div>
              <div className="pd-lab" style={{ color: r.color }}>{r.label}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function SettingsPanel({ stats }) {
  const t = stats.tweaks || {};
  return (
    <div className="pd-card">
      <h2>Kid settings <span style={{ fontSize: 12, fontWeight: 600, color: '#9a8d7a' }}>(read-only)</span></h2>
      <div style={{ display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '8px 16px', fontSize: 14 }}>
        {[
          ['Name', t.userName || '—'],
          ['Avatar', t.avatar || '—'],
          ['Reading level', t.level === 'Tree' ? '🌳 Tree (ages 11–13)' : t.level === 'Sprout' ? '🌱 Sprout (ages 8–10)' : '—'],
          ['Language', t.language === 'zh' ? '🇨🇳 中文' : t.language === 'en' ? '🇬🇧 English' : '—'],
          ['Theme', t.theme || '—'],
          ['Daily goal', `${t.dailyGoal || 21} minutes`],
          ['Client ID', stats.clientId || '— (not set on this device)'],
        ].map(([k, v]) => (
          <React.Fragment key={k}>
            <div style={{ fontWeight: 700, color: '#6b5c80' }}>{k}</div>
            <div style={{ color: '#1b1230', wordBreak: 'break-all' }}>{v}</div>
          </React.Fragment>
        ))}
      </div>
    </div>
  );
}

function Dashboard() {
  const { session, signIn, signOut } = useAuth();
  const { kids, refresh: refreshKids, parentRow } = useKids(session);

  const [tick, setTick] = useState(0);
  const [selectedDay, setSelectedDay] = useState('all');
  const [source, setSource] = useState('local');           // 'local' | 'cloud'
  const [selectedKidId, setSelectedKidId] = useState(null);
  const dayArg = selectedDay === 'all' ? null : selectedDay;

  // Auto-pick first kid (and switch to cloud) when a roster shows up.
  useEffect(() => {
    if (kids.length && !selectedKidId) {
      setSelectedKidId(kids[0].client_id);
    }
  }, [kids.length]);
  // If signed in WITH at least one kid, default the source to 'cloud' on
  // first roster load — but only ONCE so the user's later toggle sticks.
  const _autoSwitched = React.useRef(false);
  useEffect(() => {
    if (!_autoSwitched.current && session && kids.length > 0) {
      setSource('cloud');
      _autoSwitched.current = true;
    }
  }, [session && session.user && session.user.id, kids.length]);

  // Local stats — always available as the device-side source.
  const localStats = useMemo(() => collectStats(dayArg), [tick, dayArg]);

  // Cloud stats — async, recomputed on (kid|day|tick) change while in cloud mode.
  const [cloudStats, setCloudStats] = useState(null);
  const [cloudErr, setCloudErr] = useState(null);
  const [cloudLoading, setCloudLoading] = useState(false);
  useEffect(() => {
    if (source !== 'cloud' || !selectedKidId) { setCloudStats(null); setCloudErr(null); return; }
    let cancelled = false;
    setCloudLoading(true); setCloudErr(null);
    cloudCollectStats(selectedKidId, dayArg).then(s => {
      if (!cancelled) setCloudStats(s);
    }).catch(e => {
      if (!cancelled) setCloudErr(e.message || String(e));
    }).finally(() => { if (!cancelled) setCloudLoading(false); });
    return () => { cancelled = true; };
  }, [source, selectedKidId, dayArg, tick]);

  useEffect(() => {
    const onStorage = () => setTick(t => t + 1);
    window.addEventListener('storage', onStorage);
    return () => window.removeEventListener('storage', onStorage);
  }, []);

  const isCloud = source === 'cloud' && !!cloudStats;
  const stats = isCloud ? cloudStats : localStats;
  const isLifetime = !dayArg;

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto', padding: '24px 20px 60px', display: 'flex', flexDirection: 'column', gap: 18 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4, flexWrap: 'wrap' }}>
        <a href="/index.html" style={{ background: '#fff', border: '2px solid #f0e8d8', borderRadius: 10, padding: '6px 12px', fontSize: 13, fontWeight: 700, color: '#1b1230', textDecoration: 'none' }}>← Kid app</a>
        <h1 style={{ fontFamily: 'Fraunces, serif', fontWeight: 900, fontSize: 24, margin: 0, color: '#1b1230' }}>Parent dashboard</h1>
        <span className="pd-pill" style={{ background: isCloud ? '#d4f3ef' : '#fff4c2', color: isCloud ? '#0e8d82' : '#8a6d00' }}>
          {isCloud ? '☁️ Cloud' : '📱 This device'}
        </span>
        <div style={{ flex: 1 }}/>
        <label style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 13, fontWeight: 700, color: '#6b5c80' }}>
          <span>📅 Show:</span>
          <select value={selectedDay} onChange={(e) => setSelectedDay(e.target.value)} style={{
            background: '#fff', border: '2px solid #f0e8d8', borderRadius: 10,
            padding: '6px 10px', fontSize: 13, fontWeight: 700, color: '#1b1230',
            fontFamily: 'Nunito, sans-serif', cursor: 'pointer',
          }}>
            <option value="all">All time</option>
            {(stats.availableDays || []).map(d => (
              <option key={d} value={d}>{dayLabel(d)}</option>
            ))}
            {(!stats.availableDays || !stats.availableDays.length) && (
              <option disabled>No activity recorded yet</option>
            )}
          </select>
        </label>
        <button onClick={() => { setTick(t => t + 1); refreshKids && refreshKids(); }} style={{
          background: '#1b1230', color: '#ffc83d', border: 'none', borderRadius: 10,
          padding: '6px 14px', fontWeight: 800, fontSize: 13, cursor: 'pointer',
        }}>↻ Refresh</button>
      </div>

      {cloudErr && (
        <div style={{ background: '#ffe4e4', border: '1.5px solid #ff6b5b', borderRadius: 12, padding: '10px 14px', fontSize: 13, color: '#b22525' }}>
          Cloud fetch failed: {cloudErr}. Falling back to local view.
        </div>
      )}
      {!isLifetime && (
        <div style={{ background: '#fff4c2', border: '1.5px solid #f0e8d8', borderRadius: 12, padding: '10px 14px', fontSize: 13, color: '#6b5c80' }}>
          Showing <b style={{ color: '#1b1230' }}>{dayLabel(dayArg)}</b> only — quiz attempts &amp; discussion drafts on that day.
          Reactions, reading-time, and settings are lifetime totals.
        </div>
      )}
      <HeaderStrip stats={stats}/>
      <CloudBanner
        session={session} kids={kids} signIn={signIn} signOut={signOut}
        source={source} setSource={setSource}
        selectedKidId={selectedKidId} setSelectedKidId={setSelectedKidId}
        refreshKids={refreshKids} parentRow={parentRow}
      />
      {source === 'cloud' && cloudLoading && (
        <div className="pd-card" style={{ textAlign: 'center', color: '#9a8d7a' }}>Loading from the cloud…</div>
      )}
      {isLifetime && <TodayTile stats={stats}/>}
      <ArticlesList stats={stats}/>
      <QuizSummary stats={stats}/>
      <DiscussionPanel stats={stats}/>
      {isLifetime && <ReactionsPanel stats={stats}/>}
      {isLifetime && <SettingsPanel stats={stats}/>}
    </div>
  );
}

function App() {
  // ARTICLES bundle is async-loaded by data.jsx. Wait for it so titles +
  // quiz definitions are available — otherwise quiz wrong-answer joins
  // would have no question text to show.
  const [ready, setReady] = useState(() => Array.isArray(window.ARTICLES) && window.ARTICLES.length > 0);
  useEffect(() => {
    if (ready) return;
    const p = window.__payloadsLoaded;
    if (p && typeof p.then === 'function') p.then(() => setReady(true)).catch(() => setReady(true));
    else setTimeout(() => setReady(true), 800);  // bundle may already be done
  }, []);
  if (!ready) {
    return <div style={{ padding: 40, textAlign: 'center', color: '#9a8d7a', fontSize: 14 }}>Loading kid data…</div>;
  }
  return <Dashboard/>;
}

ReactDOM.createRoot(document.getElementById('root')).render(<App/>);
