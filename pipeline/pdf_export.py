"""Generate 4-page printable PDFs from detail-payload JSON.

For each (story_id, level in {easy, middle}) we emit one PDF:
  Page 1 — Read & Words: title + body + Word Treasure
  Page 2 — Background you need + Break it down + Why it matters
  Page 3 — Quiz: 6 MCQs with bubble options + answer key
  Page 4 — Think & Share: discussion questions + ruled lines

Output goes to `website/article_pdfs/<story_id>-<level>.pdf` so it ships in
the daily zip + per-day flat upload (Supabase). UI fetches via simple
<a href download>.

Uses fpdf2 — pure Python, no native deps, works on any CI runner.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from fpdf import FPDF, XPos, YPos

log = logging.getLogger("pdf-export")

# ─── visual constants ───────────────────────────────────────────────────
CAT_COLORS = {
    "News":    (255, 107, 91),    # #ff6b5b
    "Science": (23, 179, 166),    # #17b3a6
    "Fun":     (144, 97, 249),    # #9061f9
}
INK = (27, 18, 48)              # #1b1230
MUTED = (107, 92, 128)          # #6b5c80
DIM = (154, 141, 122)           # #9a8d7a
RULE = (208, 196, 180)           # #d0c4b4
WARM_BG = (255, 249, 239)        # #fff9ef
QUESTION_BG = (255, 244, 194)    # #fff4c2
QUESTION_BORDER = (255, 226, 138)  # #ffe28a
WHITE = (255, 255, 255)


def _strip_md_bold(s: str) -> str:
    """`**word**` → `word` (kid-rewrite markup not relevant in PDF print)."""
    return re.sub(r"\*\*([^*]+)\*\*", r"\1", s or "")


# Common English suffixes — same pattern the UI uses for highlightText().
# Keeps "ban" → "banned" / "banning" matched.
_KW_SUFFIX = r"(?:s|es|ed|d|ing|ning|ned|ting|ted|er|ers|ion|ions|ly)?"


def _bold_keywords_in_text(text: str, keyword_terms: list[str]) -> str:
    """Wrap each keyword (and common inflections) in `**...**` so fpdf2's
    markdown=True renders them bold in the body. Caller MUST first strip
    any pre-existing `**` to avoid double-wrapping."""
    if not text or not keyword_terms:
        return text
    cleaned = _strip_md_bold(text)
    # Sort longest-first so substrings don't shadow longer matches
    terms = sorted({t.strip() for t in keyword_terms if t and t.strip()},
                   key=len, reverse=True)
    for term in terms:
        # Build a word-boundary, suffix-tolerant, case-insensitive pattern
        escaped = re.escape(term)
        pat = re.compile(rf"\b({escaped}{_KW_SUFFIX})\b", re.IGNORECASE)
        # Use a lambda so we don't accidentally bold something already bolded.
        cleaned = pat.sub(lambda m: f"**{m.group(1)}**", cleaned)
    # Collapse any accidental `****` (a word that ends right before another
    # word starting with the same term — uncommon but possible).
    cleaned = re.sub(r"\*{4,}", "**", cleaned)
    return cleaned


# fpdf2's built-in Helvetica is Latin-1 only. Articles use smart quotes,
# em dashes, ellipses, etc. Map them to Latin-1 safe equivalents so we
# don't have to embed a unicode font (saves ~750 KB per PDF).
_UNICODE_REPLACEMENTS = {
    "—": "--",   # em dash
    "–": "-",    # en dash
    "‘": "'",    # curly single open
    "’": "'",    # curly single close / apostrophe
    "“": '"',    # curly double open
    "”": '"',    # curly double close
    "…": "...",  # ellipsis
    " ": " ",    # non-breaking space
    "•": "*",    # bullet
    "·": "*",    # middle dot
    "→": "->",   # right arrow
    "←": "<-",   # left arrow
    "✓": "OK",   # check
    "✗": "X",    # x-mark
    "—": "--",
    "─": "-",    # box drawings horizontal
    "│": "|",    # vertical
    "├": "+",    # tee
    "└": "+",    # corner
    "▀": "_",    # block — used in mind-tree (not common but defensive)
    "…": "...",
}


def _to_latin1(s: str) -> str:
    """Make text printable by Helvetica-core. Replaces well-known unicode
    chars; falls back to '?' for anything else outside Latin-1."""
    if not s:
        return s or ""
    for src, dst in _UNICODE_REPLACEMENTS.items():
        s = s.replace(src, dst)
    # Catch anything else outside Latin-1 (e.g. CJK, emoji)
    return s.encode("latin-1", "replace").decode("latin-1")


def _wrap_para_breaks(s: str) -> list[str]:
    """Split on blank lines to form paragraphs."""
    return [p.strip() for p in re.split(r"\n\n+", s or "") if p.strip()]


# ─── PDF builder ────────────────────────────────────────────────────────

class ArticlePDF(FPDF):
    """One PDF document per (story, level)."""

    def __init__(self, title: str, category: str):
        super().__init__(orientation="portrait", unit="in", format="Letter")
        self.set_auto_page_break(auto=True, margin=0.5)
        self.set_margins(0.5, 0.5, 0.5)
        self.set_compression(True)
        self.set_creator("News Oh,Ye!")
        self.set_title(title[:200])
        self._cat_color = CAT_COLORS.get(category, INK)
        self._category = category
        self._title = title

    def header_bar(self, step_label: str):
        """Category-colored top bar with step label."""
        # Category pill
        c = self._cat_color
        self.set_fill_color(*c)
        self.set_text_color(*WHITE)
        self.set_font("Helvetica", "B", 9)
        cat_text = self._category.upper()
        cat_w = self.get_string_width(cat_text) + 0.16
        self.set_xy(0.5, 0.5)
        self.cell(cat_w, 0.18, cat_text, align="C", fill=True,
                  new_x=XPos.RIGHT, new_y=YPos.TOP)
        # Step label
        self.set_text_color(*MUTED)
        self.set_font("Helvetica", "B", 9)
        self.cell(0, 0.18, "  " + step_label,
                  new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        # Underline
        self.set_draw_color(*c)
        self.set_line_width(0.025)
        self.line(0.5, 0.74, 8.0, 0.74)
        self.set_y(0.85)

    def footer(self):
        self.set_y(-0.5)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*DIM)
        # Page-number ratio
        page_no = self.page_no()
        self.cell(0, 0.18,
                  f"News Oh,Ye!  ·  Step {page_no} of 4",
                  new_x=XPos.RIGHT, new_y=YPos.TOP)
        self.cell(0, 0.18, f"Page {page_no} / {{nb}}", align="R")

    def heading(self, text: str, size: int = 16):
        # Pages 1/2/4 use 16; Page 3 (quiz) callers can pass 14 explicitly.
        self.set_text_color(*INK)
        self.set_font("Helvetica", "B", size)
        self.cell(0, 0.32, _to_latin1(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(0.04)

    def subheading(self, text: str):
        self.set_text_color(*self._cat_color)
        self.set_font("Helvetica", "B", 13)
        self.cell(0, 0.24, _to_latin1(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(0.02)

    def body_text(self, text: str, size: float = 13, markdown: bool = False):
        self.set_text_color(*INK)
        self.set_font("Helvetica", "", size)
        # markdown=True enables fpdf2's `**bold**` inline syntax — used for
        # keyword highlighting in the article body.
        self.multi_cell(0, 0.22, _to_latin1(text), markdown=markdown)
        self.ln(0.04)

    def body_paragraphs(self, paragraphs: list[str], size: float = 13,
                        markdown: bool = False):
        for p in paragraphs:
            self.body_text(p, size=size, markdown=markdown)

    # ─── Page 1: Read & Words ────────────────────────────────────────
    def render_page_read(self, detail: dict, source: str, mined_at: str, read_mins: int):
        self.add_page()
        self.header_bar("Step 1  ·  Read & Words")

        # Title (bumped 18 → 20)
        self.set_text_color(*INK)
        self.set_font("Helvetica", "B", 20)
        self.multi_cell(0, 0.36, _to_latin1(self._title))
        self.ln(0.05)

        # Meta (bumped 9 → 10)
        self.set_text_color(*MUTED)
        self.set_font("Helvetica", "", 10)
        meta = f"From: {source}"
        if mined_at:
            meta += f"   Mined: {mined_at}"
        meta += f"   {read_mins} min read"
        self.cell(0, 0.20, _to_latin1(meta), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(0.12)

        # Body — wrap each keyword in `**...**` so fpdf2 renders them bold
        # via markdown=True. Makes the keywords pop in the printed copy
        # so kids can spot them while reading.
        body = _strip_md_bold(detail.get("summary") or "")
        keyword_terms = [(k.get("term") or "") for k in (detail.get("keywords") or [])]
        body_with_bold = _bold_keywords_in_text(body, keyword_terms)
        self.body_paragraphs(_wrap_para_breaks(body_with_bold), size=13, markdown=True)

        # Word Treasure (term 11→13, explanation 11→13)
        keywords = detail.get("keywords") or []
        if keywords:
            self.ln(0.05)
            self.subheading("Word Treasure")
            for kw in keywords:
                term = (kw.get("term") or "").strip()
                expl = (kw.get("explanation") or kw.get("def") or "").strip()
                term_safe = _to_latin1(term)
                # Term
                self.set_text_color(*self._cat_color)
                self.set_font("Helvetica", "B", 13)
                term_w = self.get_string_width(term_safe) + 0.05
                self.cell(term_w, 0.22, term_safe, new_x=XPos.RIGHT, new_y=YPos.TOP)
                # Separator + explanation
                self.set_text_color(*INK)
                self.set_font("Helvetica", "", 13)
                self.multi_cell(0, 0.22, _to_latin1(" -- " + expl))
                self.ln(0.02)

    # ─── Page 2: Background ───────────────────────────────────────────
    def render_page_background(self, detail: dict):
        self.add_page()
        self.header_bar("Step 2  ·  Background & Structure")

        bg = detail.get("background_read")
        if isinstance(bg, list):
            paras = [str(p) for p in bg if p]
        elif isinstance(bg, str):
            paras = _wrap_para_breaks(bg)
        else:
            paras = []
        if paras:
            self.heading("Background you need")
            self.body_paragraphs(paras)
            self.ln(0.08)

        struct = detail.get("Article_Structure") or []
        if struct:
            self.heading("Break it down")
            self.set_text_color(*INK)
            # Bumped 10.5 → 12.5 (+2)
            self.set_font("Helvetica", "", 12.5)
            for line in struct:
                if not isinstance(line, str):
                    line = str(line)
                # Preserve indent — count leading whitespace
                m = re.match(r"^(\s*)(.*)$", line)
                indent = (len(m.group(1)) if m else 0) * 0.06  # in inches
                content = m.group(2) if m else line
                # Bold the LABEL: prefix
                lm = re.match(r"^([A-Z][A-Z \\/]*[A-Z]|[A-Z][a-z]+):\s*(.*)$", content)
                self.set_x(0.5 + indent)
                if lm:
                    self.set_font("Helvetica", "B", 12.5)
                    self.set_text_color(*INK)
                    label = lm.group(1) + ":"
                    label_safe = _to_latin1(label)
                    label_w = self.get_string_width(label_safe) + 0.04
                    self.cell(label_w, 0.20, label_safe,
                              new_x=XPos.RIGHT, new_y=YPos.TOP)
                    self.set_font("Helvetica", "", 12.5)
                    self.multi_cell(0, 0.20, _to_latin1(" " + lm.group(2)))
                else:
                    self.set_font("Helvetica", "", 12.5)
                    self.multi_cell(0, 0.20, _to_latin1(content))
                self.ln(0.01)
            self.ln(0.06)

        wim = detail.get("why_it_matters")
        if wim:
            self.heading("Why it matters")
            self.body_text(_strip_md_bold(wim))

    # ─── Page 3: Quiz ────────────────────────────────────────────────
    # Quiz page keeps its original (smaller) font sizes — the +2 bump is
    # for the reading/background/think pages only, since the quiz already
    # has tight per-question layout that gets cramped at larger sizes.
    def render_page_quiz(self, detail: dict):
        self.add_page()
        self.header_bar("Step 3  ·  Quiz")

        self.heading("Test what you remember", size=14)
        self.ln(0.04)

        questions = detail.get("questions") or []
        answer_letters = []
        for i, q in enumerate(questions):
            qtext = (q.get("question") or q.get("q") or "").strip()
            opts = q.get("options") or []
            correct = q.get("correct_answer") or ""

            # Question number + text
            self.set_text_color(*self._cat_color)
            self.set_font("Helvetica", "B", 13)
            num = f"{i + 1}."
            num_w = self.get_string_width(num) + 0.05
            y_start = self.get_y()
            self.cell(num_w, 0.22, num, new_x=XPos.RIGHT, new_y=YPos.TOP)
            self.set_text_color(*INK)
            self.set_font("Helvetica", "B", 11)
            self.multi_cell(0, 0.22, _to_latin1(qtext))

            # Options as A/B/C/D
            for oi, opt in enumerate(opts):
                letter = chr(65 + oi)
                if str(opt) == str(correct):
                    answer_letters.append(f"{i + 1}: {letter}")
                self.set_x(0.5 + 0.25)  # indent under the number
                # Bubble (small circle) — fpdf2 has ellipse()
                bubble_x = self.get_x()
                bubble_y = self.get_y() + 0.04
                self.set_draw_color(*INK)
                self.set_line_width(0.012)
                self.ellipse(bubble_x, bubble_y, 0.16, 0.16)
                self.set_font("Helvetica", "B", 8)
                self.set_text_color(*INK)
                self.text(bubble_x + 0.045, bubble_y + 0.115, letter)
                # Option text
                self.set_x(bubble_x + 0.22)
                self.set_font("Helvetica", "", 10.5)
                self.set_text_color(*INK)
                self.multi_cell(0, 0.18, _to_latin1(str(opt)))
                self.ln(0.01)
            self.ln(0.05)

        # Answer key boxed at bottom
        if answer_letters:
            self.ln(0.1)
            self.set_fill_color(240, 235, 255)  # #f0ebff
            self.set_draw_color(201, 184, 255)
            self.set_text_color(*MUTED)
            self.set_font("Helvetica", "", 9)
            ak_text = ("Answer key (try the quiz first!):  "
                       + "   ".join(answer_letters))
            self.set_x(0.5)
            self.cell(0, 0.3, ak_text, fill=True, border=1,
                      new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # ─── Page 4: Think & Share ────────────────────────────────────────
    def render_page_think(self, detail: dict, perspectives: list = None):
        self.add_page()
        self.header_bar("Step 4  ·  Think & Share")

        self.heading("Questions to think about")
        self.ln(0.02)

        # Use perspectives as discussion questions (descriptions)
        # if no explicit discussion field. Detail JSON has perspectives;
        # the UI maps those to discussion strings.
        questions = []
        for p in (perspectives or detail.get("perspectives") or []):
            if isinstance(p, dict):
                pers = p.get("perspective", "")
                desc = p.get("description", "")
                questions.append(f"{pers}: {desc}" if pers else desc)
            else:
                questions.append(str(p))

        for i, q in enumerate(questions):
            # Yellow box per question (font 11→13, +2)
            self.set_fill_color(*QUESTION_BG)
            self.set_draw_color(*QUESTION_BORDER)
            self.set_text_color(*INK)
            self.set_font("Helvetica", "B", 13)
            x0 = self.get_x()
            y0 = self.get_y()
            # Multi-cell with fill
            self.set_x(0.5)
            self.multi_cell(0, 0.26, _to_latin1(f"{i + 1}.  {_strip_md_bold(q)}"),
                            border=1, fill=True)
            self.ln(0.06)

        # Ruled lines for handwriting (label 10→12, +2)
        self.ln(0.08)
        self.set_text_color(*MUTED)
        self.set_font("Helvetica", "B", 12)
        self.cell(0, 0.22, "MY THOUGHTS (at least 20 words):",
                  new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(0.04)
        self.set_draw_color(*RULE)
        self.set_line_width(0.008)
        # As many ruled lines as fit until bottom margin
        y = self.get_y()
        while y < 10.0:  # ~bottom margin
            self.line(0.5, y, 8.0, y)
            y += 0.3
        self.set_y(10.0)


def render_article_pdf(detail: dict, level: str, category: str,
                        source: str, mined_at: str, read_mins: int,
                        out_path: Path) -> None:
    """Render one article's 4-page PDF to `out_path`."""
    pdf = ArticlePDF(detail.get("title") or "(untitled)", category)
    pdf.alias_nb_pages()
    pdf.render_page_read(detail, source, mined_at, read_mins)
    pdf.render_page_background(detail)
    pdf.render_page_quiz(detail)
    pdf.render_page_think(detail)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(out_path))


def generate_all_pdfs(stories_by_cat: dict, today: str, website_dir: Path) -> int:
    """Write one PDF per (story, level=easy|middle). Returns count emitted."""
    pdfs_dir = website_dir / "article_pdfs"
    pdfs_dir.mkdir(parents=True, exist_ok=True)

    detail_dir = website_dir / "article_payloads"
    count = 0
    for category, stories in stories_by_cat.items():
        for slot, s in enumerate(stories, start=1):
            story_id = s.get("_story_id") or f"{today}-{category.lower()}-{slot}"
            source = s["source"].name
            for level in ("easy", "middle"):
                detail_path = detail_dir / f"payload_{story_id}" / f"{level}.json"
                if not detail_path.is_file():
                    log.warning("PDF skip: missing detail %s", detail_path)
                    continue
                try:
                    detail = json.loads(detail_path.read_text())
                except Exception as e:
                    log.warning("PDF skip: %s parse fail: %s", detail_path, e)
                    continue
                mined_at = (detail.get("mined_at") or "")[:10]
                read_mins = 3 if level == "easy" else 5
                out_path = pdfs_dir / f"{story_id}-{level}.pdf"
                try:
                    render_article_pdf(
                        detail=detail, level=level, category=category,
                        source=source, mined_at=mined_at, read_mins=read_mins,
                        out_path=out_path,
                    )
                    count += 1
                except Exception as e:
                    log.error("PDF render failed for %s/%s: %s",
                              story_id, level, e)
    log.info("PDF export: %d files written under %s", count, pdfs_dir)
    return count
