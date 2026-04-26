// kidsync — kid-side mirror for Supabase RPCs.
// Loaded by index.html; exposes window.kidsync with fire-and-forget
// methods called from article.jsx (KidStats helpers) and from index.html's
// tweaks/progress effects. Cloud writes are best-effort — they NEVER
// block the kid's UI and they NEVER fail visibly. localStorage stays the
// source of truth on this device; Supabase is just a remote mirror so
// parents can view from another device + receive email digests.
(function () {
  'use strict';

  var SUPABASE_URL = 'https://lfknsvavhiqrsasdfyrs.supabase.co';
  var SUPABASE_PUBLISHABLE_KEY = 'sb_publishable_C0UF9RR0ui0XnmF5OdYwGg_W7628Yex';

  // The Supabase JS UMD bundle is not loaded by default on index.html. We
  // pull it in lazily so the kid's first paint isn't blocked. If the load
  // fails (offline / CSP), kidsync silently no-ops — KidStats keeps
  // localStorage updated and the parent can still use the local-mode
  // dashboard on this device.
  var sbPromise = null;
  function ensureSupabase() {
    if (sbPromise) return sbPromise;
    sbPromise = new Promise(function (resolve) {
      if (window.supabase && window.supabase.createClient) {
        resolve(window.supabase.createClient(SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY, {
          auth: { persistSession: false, autoRefreshToken: false, detectSessionInUrl: false },
        }));
        return;
      }
      var s = document.createElement('script');
      s.src = 'https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2/dist/umd/supabase.js';
      s.async = true;
      s.onload = function () {
        try {
          resolve(window.supabase.createClient(SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY, {
            auth: { persistSession: false, autoRefreshToken: false, detectSessionInUrl: false },
          }));
        } catch (e) { resolve(null); }
      };
      s.onerror = function () { resolve(null); };
      document.head.appendChild(s);
    });
    return sbPromise;
  }

  function clientId() {
    try {
      var ss = window.safeStorage;
      var id = ss && ss.get('ohye_client_id');
      if (typeof id === 'string' && id.length > 8) return id;
      // Lazily mint the id via data.jsx's getClientId() if it's available
      // (it persists to localStorage). Otherwise generate a UUID-shaped
      // string here. Without this, kidsync silently no-ops for any kid
      // who never triggered fetchAIFeedback — i.e. most of them — and
      // the parent dashboard's auto-claim has nothing to claim.
      if (typeof window.getClientId === 'function') {
        var minted = window.getClientId();
        if (typeof minted === 'string' && minted.length > 8) return minted;
      }
      var newId = 'cid-' + Date.now().toString(36) + '-'
        + Math.random().toString(36).slice(2, 10);
      if (ss) ss.set('ohye_client_id', newId);
      return newId;
    } catch (e) { return null; }
  }

  function todayKey() {
    var d = new Date();
    return d.getFullYear() + '-'
      + String(d.getMonth() + 1).padStart(2, '0') + '-'
      + String(d.getDate()).padStart(2, '0');
  }

  // Fire-and-forget RPC. Never throws. Logs warn on failure for debugging.
  function rpc(name, args) {
    var cid = clientId(); if (!cid) return;
    ensureSupabase().then(function (sb) {
      if (!sb) return;
      sb.rpc(name, args).then(function (res) {
        if (res && res.error) console.warn('[kidsync]', name, 'failed:', res.error.message);
      }).catch(function (e) { console.warn('[kidsync]', name, 'threw:', e); });
    });
  }

  window.kidsync = {
    // Called from index.html whenever tweaks change.
    upsertKidProfile: function (tweaks) {
      var cid = clientId(); if (!cid || !tweaks) return;
      rpc('upsert_kid_profile', {
        p_client_id: cid,
        p_display_name: tweaks.userName || null,
        p_avatar: tweaks.avatar || null,
        p_level: tweaks.level || null,
        p_language: tweaks.language || null,
        p_theme: tweaks.theme || null,
        p_daily_goal: tweaks.dailyGoal || 21,
      });
    },
    // Called from article.jsx bumpStep — one row per step transition. The
    // append-only event log is what drives the parent's day-by-day chart.
    recordReadingEvent: function (storyId, step, opts) {
      var cid = clientId(); if (!cid || !storyId || !step) return;
      opts = opts || {};
      rpc('record_reading_event', {
        p_client_id: cid,
        p_story_id: storyId,
        p_step: step,
        p_category: opts.category || null,
        p_level: opts.level || null,
        p_language: opts.language || null,
        p_minutes_added: opts.minutesAdded || 0,
        p_duration_ms: opts.durationMs || null,
        p_day_key: opts.dayKey || todayKey(),
      });
    },
    // Called from KidStats.logQuizAttempt. picks is the kid's array of
    // chosen indices in question order.
    recordQuizAttempt: function (storyId, level, picks, correct, total, durationMs) {
      var cid = clientId(); if (!cid || !storyId) return;
      rpc('record_quiz_attempt', {
        p_client_id: cid,
        p_story_id: storyId,
        p_level: level || '',
        p_picks: picks || [],
        p_correct: correct || 0,
        p_total: total || 0,
        p_duration_ms: durationMs || null,
        p_day_key: todayKey(),
      });
    },
    // Called from KidStats.setReaction. Upsert — last reaction wins.
    recordArticleReaction: function (storyId, level, reaction) {
      var cid = clientId(); if (!cid || !storyId || !reaction) return;
      rpc('record_article_reaction', {
        p_client_id: cid,
        p_story_id: storyId,
        p_level: level || '',
        p_reaction: reaction,
      });
    },
    // Called from article.jsx DiscussTab's persist effect. Mirrors the
    // full rounds[] + savedFinal flag — last write wins per (kid, story, level).
    upsertDiscussion: function (storyId, level, rounds, savedFinal) {
      var cid = clientId(); if (!cid || !storyId) return;
      rpc('upsert_discussion_response', {
        p_client_id: cid,
        p_story_id: storyId,
        p_level: level || '',
        p_rounds: rounds || [],
        p_saved_final: !!savedFinal,
      });
    },
    // Async — returns a Promise<{code, expiresAt}|null>. Used by the
    // user-panel's "Pair with parent" expander when parent is on a
    // different device. Waits for Supabase JS to load.
    generatePairingCode: function () {
      var cid = clientId(); if (!cid) return Promise.resolve(null);
      return ensureSupabase().then(function (sb) {
        if (!sb) return null;
        return sb.rpc('generate_pairing_code', { p_client_id: cid }).then(function (res) {
          if (res && res.error) {
            console.warn('[kidsync] generate_pairing_code failed:', res.error.message);
            return null;
          }
          return {
            code: res.data || null,
            // Server enforces 10-min TTL; mirror so UI can show countdown.
            expiresAt: new Date(Date.now() + 10 * 60 * 1000).toISOString(),
          };
        });
      });
    },
  };
})();
