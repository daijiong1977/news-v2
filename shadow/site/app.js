"use strict";
const category = document.querySelector("#category"), level = document.querySelector("#level");
const articles = document.querySelector("#articles"), message = document.querySelector("#message");
let generation = 0;
function node(tag, text, className) {
  const el = document.createElement(tag);
  if (text !== undefined) el.textContent = text;
  if (className) el.className = className;
  return el;
}
async function json(url) {
  const response = await fetch(url, {cache: "no-store"});
  if (!response.ok) throw new Error(`读取失败 (${response.status})`);
  return response.json();
}
async function render() {
  const current = ++generation, cat = category.value, lvl = level.value;
  articles.replaceChildren(); message.textContent = "正在读取文章…";
  try {
    const data = await json(`/payloads/articles_${cat}_${lvl}.json`);
    if (current !== generation) return;
    message.textContent = data.articles.length ? `${data.articles.length} 篇测试文章` : "尚未接入 Bot 生成结果。测试入口已准备好。";
    for (const item of data.articles) {
      const card = node("article"), copy = node("div", undefined, "copy");
      if (/^\/article_images\/[A-Za-z0-9_.-]+$/.test(item.image_url || "")) {
        const img = node("img"); img.src = item.image_url; img.alt = ""; img.loading = "lazy"; card.append(img);
      }
      copy.append(node("small", `${item.source} · ${item.id}`), node("h2", item.title), node("p", item.summary));
      if (lvl !== "cn") {
        const detail = node("details"), toggle = node("summary", "阅读全文");
        detail.append(toggle);
        detail.addEventListener("toggle", async () => {
          if (!detail.open || detail.dataset.loaded) return;
          detail.dataset.loaded = "yes";
          try {
            const body = await json(`/article_payloads/payload_${encodeURIComponent(item.id)}/${lvl}.json`);
            detail.append(node("p", body.summary, "body"));
            if (/^https?:\/\//.test(body.source_url || "")) {
              const link = node("a", "原始来源 ↗"); link.href = body.source_url;
              link.target = "_blank"; link.rel = "noopener noreferrer"; detail.append(link);
            }
          } catch (err) { detail.append(node("p", err.message)); }
        });
        copy.append(detail);
      }
      card.append(copy); articles.append(card);
    }
  } catch (err) { if (current === generation) message.textContent = err.message; }
}
async function start() {
  try {
    const run = await json("/shadow-run.json");
    document.querySelector("#run").textContent = run.status === "awaiting_agent"
      ? "影子站已建立；尚无 Agent 运行结果。"
      : `日期 ${run.date} · Agent ${run.provider} · 内容哈希 ${run.content_hash.slice(0,12)} · 审核状态：待人工核验`;
    if (run.status !== "awaiting_agent") { category.disabled = false; level.disabled = false; await render(); }
    else message.textContent = "尚未接入 Bot 生成结果。测试入口已准备好。";
  } catch (err) { document.querySelector("#run").textContent = err.message; }
}
category.addEventListener("change", render); level.addEventListener("change", render); start();
