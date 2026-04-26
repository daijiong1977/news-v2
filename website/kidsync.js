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
          auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true },
        }));
        return;
      }
      var s = document.createElement('script');
      s.src = 'https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2/dist/umd/supabase.js';
      s.async = true;
      s.onload = function () {
        try {
          resolve(window.supabase.createClient(SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY, {
            auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true },
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

    // ── Identity transfer (kid self-claim) ─────────────────────────
    // Kid types a 6-digit code on a new device. Server returns the
    // canonical client_id; we rewrite localStorage so all subsequent
    // kidsync calls use the claimed identity. Returns the new id on
    // success, null on failure (UI shows "code is invalid or expired").
    lookupCode: function (code) {
      if (!code || typeof code !== 'string') return Promise.resolve(null);
      return ensureSupabase().then(function (sb) {
        if (!sb) return null;
        return sb.rpc('lookup_pairing_code', { p_code: code.trim() }).then(function (res) {
          if (res && res.error) {
            console.warn('[kidsync] lookup_pairing_code failed:', res.error.message);
            return null;
          }
          var cid = res && res.data;
          if (!cid) return null;
          // Swap the local client_id. Future events belong to this id.
          try { window.safeStorage && window.safeStorage.set('ohye_client_id', cid); } catch (e) {}
          return cid;
        });
      });
    },

    // Gmail SSO. Returns a Promise resolving to { redirected: true } —
    // Supabase redirects the page to Google. After the redirect comes
    // back, the app should call linkCurrentSession() to bind the
    // signed-in email to a client_id.
    signInWithGoogle: function () {
      return ensureSupabase().then(function (sb) {
        if (!sb) return { redirected: false, error: 'auth unavailable' };
        return sb.auth.signInWithOAuth({
          provider: 'google',
          options: { redirectTo: window.location.origin + window.location.pathname },
        }).then(function (res) {
          return { redirected: !res.error, error: res.error ? res.error.message : null };
        });
      });
    },

    // After OAuth redirect lands, call this. It fetches the session,
    // reads auth.email(), and binds it server-side. Returns the
    // canonical client_id (which may differ from the local one if the
    // email was already linked from another device). Caller should
    // rewrite localStorage if the returned id != current.
    linkCurrentSession: function () {
      var localCid = clientId();
      return ensureSupabase().then(function (sb) {
        if (!sb) return null;
        return sb.auth.getSession().then(function (sess) {
          if (!sess.data.session) return null;
          return sb.rpc('claim_or_create_kid_for_email', {
            p_local_client_id: localCid,
          }).then(function (res) {
            if (res && res.error) {
              console.warn('[kidsync] claim_or_create_kid_for_email failed:', res.error.message);
              return null;
            }
            var canonical = res && res.data;
            if (canonical && canonical !== localCid) {
              try { window.safeStorage && window.safeStorage.set('ohye_client_id', canonical); } catch (e) {}
            }
            return {
              clientId: canonical || localCid,
              email: sess.data.session.user && sess.data.session.user.email || null,
            };
          });
        });
      });
    },

    signOut: function () {
      return ensureSupabase().then(function (sb) {
        if (!sb) return null;
        return sb.auth.signOut();
      });
    },

    // Returns { type: 'anon'|'google', clientId, email? }.
    // Used by the Profile panel to render "Signed in as …" vs
    // "Your code: 123456".
    getIdentity: function () {
      var localCid = clientId();
      return ensureSupabase().then(function (sb) {
        if (!sb) return { type: 'anon', clientId: localCid };
        return sb.auth.getSession().then(function (sess) {
          var email = sess && sess.data && sess.data.session
            && sess.data.session.user && sess.data.session.user.email;
          return email
            ? { type: 'google', clientId: localCid, email: email }
            : { type: 'anon',   clientId: localCid };
        });
      });
    },

    // ── Magic link via email ───────────────────────────────────────
    // Kid (or parent) types any email; we ask the server for a token,
    // then post the link to send-email-v2. Returns true on success.
    requestMagicLink: function (email) {
      var to = (email || '').trim().toLowerCase();
      if (!to || to.indexOf('@') < 1) {
        return Promise.reject(new Error('Please enter a valid email.'));
      }
      return ensureSupabase().then(function (sb) {
        if (!sb) throw new Error('Cloud sync not available.');
        return sb.rpc('issue_magic_link', { p_email: to }).then(function (res) {
          if (res && res.error) throw new Error(res.error.message);
          var token = res && res.data;
          if (!token) throw new Error('No token returned.');
          var link = window.location.origin + window.location.pathname + '?magic=' + encodeURIComponent(token);
          var html = '<div style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;background:#fff9ef;padding:24px;color:#1b1230;">'
            + '<h2 style="font-family:Georgia,serif;margin:0 0 12px;font-weight:900;">Sign in to kidsnews</h2>'
            + '<p style="font-size:14px;color:#3a2a4a;line-height:1.5;">'
            + 'Tap the button below to sync your reading streak to this email. After this, you can come back from any browser.'
            + '</p>'
            + '<div style="margin:18px 0;"><a href="' + link + '" '
            + 'style="display:inline-block;background:#1b1230;color:#ffc83d;font-family:Nunito,sans-serif;font-weight:900;'
            + 'font-size:15px;padding:14px 22px;border-radius:14px;text-decoration:none;border:2px solid #1b1230;">'
            + '✨ Sync this email to kidsnews</a></div>'
            + '<p style="font-size:12px;color:#9a8d7a;line-height:1.5;">'
            + 'This link is single-use and expires in 30 minutes. If you didn\'t ask for this, ignore this email.'
            + '</p></div>';
          var text = 'Sign in to kidsnews\n\nTap to sync this email to your reading streak:\n' + link
            + '\n\n(Single-use, expires in 30 minutes. Ignore if you didn\'t ask for this.)';
          return fetch(SUPABASE_URL + '/functions/v1/send-email-v2', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              to_email: to,
              subject: 'Your kidsnews sign-in link',
              html: html, message: text,
              from_name: 'kidsnews',
            }),
          }).then(function (r) {
            return r.json().then(function (data) {
              if (data && data.success) return true;
              throw new Error((data && data.error) || ('send-email-v2 ' + r.status));
            });
          });
        });
      });
    },

    // Called from the URL handler when ?magic=<token> shows up. Returns
    // the canonical client_id (which may differ from the local one if
    // the email was already linked from another device). Caller handles
    // localStorage rewrite + URL cleanup.
    consumeMagicLink: function (token) {
      var localCid = clientId(); if (!localCid) return Promise.resolve(null);
      return ensureSupabase().then(function (sb) {
        if (!sb) return null;
        return sb.rpc('consume_magic_link', {
          p_token: token,
          p_local_client_id: localCid,
        }).then(function (res) {
          if (res && res.error) {
            console.warn('[kidsync] consume_magic_link failed:', res.error.message);
            return { ok: false, error: res.error.message };
          }
          var canonical = res && res.data;
          if (!canonical) return { ok: false, error: 'No client_id returned' };
          if (canonical !== localCid) {
            try { window.safeStorage && window.safeStorage.set('ohye_client_id', canonical); } catch (e) {}
          }
          return { ok: true, clientId: canonical };
        });
      });
    },

    // ── Cloud history hydration ────────────────────────────────────
    // Called on every app boot. Returns the kid's last N reading
    // events from Supabase so the streak popover + Continue rail
    // can render even after a localStorage clear or a fresh device.
    // Resolves to [] on any failure (offline, RPC error). Never throws.
    fetchHistory: function (limit) {
      var cid = clientId(); if (!cid) return Promise.resolve([]);
      var n = Number(limit) || 100;
      return ensureSupabase().then(function (sb) {
        if (!sb) return [];
        return sb.rpc('get_reading_history', { p_client_id: cid, p_limit: n })
          .then(function (res) {
            if (res && res.error) {
              console.warn('[kidsync] get_reading_history failed:', res.error.message);
              return [];
            }
            return Array.isArray(res.data) ? res.data : [];
          })
          .catch(function (e) { console.warn('[kidsync] history threw:', e); return []; });
      });
    },
  };
})();
