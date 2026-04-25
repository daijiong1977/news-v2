# Progress-counter cross-check

## Code review findings

- **[BLOCKER] Legacy progress is wiped on first load after deploy** (`website/index.html:78-94`). Older `ohye_progress` records did not have `dayKey`, so `saved.dayKey !== todayKey` treats every pre-change record as stale and resets `readToday`, `minutesToday`, and `articleProgress` immediately. The next save persists that empty base, so an existing reader can lose same-day progress just by loading the new app once.
- **[IMPORTANT] Legacy numeric `articleProgress[id]` only works on the home page, not on the article page** (`website/article.jsx:20-30,99-124,157-167,190-193`). Home safely maps legacy `0/25/50/75/100` values through `_articlePct()`, but `ArticlePage` coerces any non-object entry to `{ steps: [], lastTab: 'read' }`. That means a user with legacy `75` or `100` can reopen the article on the wrong tab, see an empty stepper, and re-earn steps that were already complete.

I did **not** find a counter-inflation issue in `website/data.jsx`: `MOCK_USER.minutesToday` is `0` and `MOCK_USER.readToday` is `[]`. I also did **not** find a missed call site in `website/home.jsx`: all five `articleProgress` reads route through `_articlePct(...)`, so homepage rendering is backward-compatible with both shapes.

## Smoke test results

1. **Pass:** `http://localhost:18100/index.html` served over local Python HTTP with **HTTP 200** and the SPA stayed mounted through the whole flow.
2. **Pass:** With `localStorage` cleared before load, `ohye_progress` initialized to `{ readToday: [], minutesToday: 0, articleProgress: {}, dayKey: "Sat Apr 25 2026" }`, and the home banner showed **`0/15 min today`**.
3. **Pass:** Clicking **Start today's read** opened article **`2026-04-24-news-1-easy`** (“Oops! Three Politicians Get Caught Betting on Themselves”). Clicking **“I read it! Next: Background →”** moved `minutesToday` from **0 → 1** and stored `articleProgress["2026-04-24-news-1-easy"] = { steps: ["read"], lastTab: "analyze" }`.
4. **Pass:** Returning home showed **`1/15 min today`**.
5. **Pass:** Reopening the same article resumed on **analyze**, not **read**: the page showed **“Background you need”** and did **not** show **“The Story”**.
6. **Pass:** Clicking through **analyze → quiz → discuss** and saving a final answer ended with `minutesToday: 5`, `readToday: ["2026-04-24-news-1-easy"]`, `steps: ["read", "analyze", "quiz", "discuss"]`, route `{ page: "home", articleId: null }`, and the banner **`5/15 min today`**.
7. **Non-fatal console noise:** I saw one browser console **404 resource** error and one React **`validateDOMNesting`** warning about a `<button>` inside another `<button>` in `KeywordCard`. I saw **no `pageerror` exceptions**, and neither message prevented the React tree from rendering or completing the flow above.
