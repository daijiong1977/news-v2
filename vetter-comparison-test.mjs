#!/usr/bin/env node
/**
 * News Oh,Ye! — Vetter Comparison Test
 * Compares DeepSeek V3 vs Claude (Haiku) vetting scores on 6 sample articles.
 *
 * Usage:
 *   node vetter-comparison-test.mjs
 *
 * Requirements:
 *   - DEEPSEEK_API_KEY env var
 *   - ANTHROPIC_API_KEY env var (for Claude comparison)
 *   - Node 18+ (for native fetch)
 */

const DEEPSEEK_KEY = process.env.DEEPSEEK_API_KEY || '';
const ANTHROPIC_KEY = process.env.ANTHROPIC_API_KEY || '';

const VETTER_PROMPT = `You are a content safety reviewer for a kids news site (ages 8-13, grades 3-8).

Rate this article on each dimension (0=none, 1=minimal, 2=mild, 3=moderate, 4=significant, 5=severe):
- Violence/Conflict
- Sexual Content
- Substance Use
- Profanity/Language
- Fear/Horror
- Complex Adult Themes
- Emotional Distress
- Bias/Stereotypes

Return ONLY valid JSON (no markdown, no code blocks, no explanation):
{
  "scores": { "violence": 0, "sexual": 0, "substance": 0, "language": 0, "fear": 0, "adult_themes": 0, "distress": 0, "bias": 0 },
  "total": 0,
  "verdict": "SAFE|CAUTION|REJECT",
  "flags": ["any specific concerns"],
  "rewrite_notes": "suggestions if CAUTION"
}`;

const ARTICLES = [
  {
    name: "Apple CEO",
    text: `Apple announced on April 20, 2026 that Tim Cook will step down as CEO on August 31. John Ternus will take over as the new CEO on September 1. Cook has led Apple for nearly 15 years, growing it to a $4 trillion company. He will become Executive Chairman. Ternus, 50, joined Apple in 2001 and has led hardware engineering, overseeing iPhone, iPad, Mac, AirPods, and Apple Vision Pro. Before tech, he was a competitive swimmer. The board voted unanimously for the change.`
  },
  {
    name: "Earth Day",
    text: `Earth Day 2026 is April 22, with the theme "Our Power, Our Planet." More than 10,000 events are planned worldwide. Earth Day has been celebrated since 1970 — 56 years. Communities are organizing cleanups, tree plantings, workshops, and marches. In Detroit, families can pack seeds and build rain barrels. In NYC, Union Square hosts environmental exhibits, climate art, and kids activities. In NJ, ACUA Environmental Park has science exhibits and crafts. Kids can decorate ceramic pots, plant flowers, and build DIY water filters using cotton, sand, charcoal and gravel.`
  },
  {
    name: "Moringa Seeds",
    text: `Scientists at São Paulo State University in Brazil discovered that moringa seeds can remove 98.5% of microplastics from drinking water, published April 20, 2026 in ACS Omega. Microplastics carry negative electrical charges that help them slip through filters. Moringa seed extract neutralizes the charge, causing plastic particles to clump together for easy filtering. This nearly matches aluminum sulfate at 98.7%. In alkaline water, moringa outperformed the chemical. Unlike synthetic chemicals, moringa is biodegradable, non-toxic, and widely available in tropical regions, making it cheap and accessible for communities without expensive filtration. Microplastics are found in water, food, and even human bodies.`
  },
  {
    name: "Murder Muppet Dinosaur",
    text: `Virginia Tech senior Simba Srivastava spent two years reconstructing a crushed dinosaur skull found in 1982 at Ghost Ranch, New Mexico by Carnegie Museum. The skull sat forgotten in a museum drawer for 30+ years. Professor Sterling Nesbitt rediscovered it. Using CT scanning and 3D printing, Srivastava revealed a new species with massive cheekbones, wide braincase, and short deep snout — features never seen in early dinosaurs. Named Ptychotherates bucculentus ("folded hunter with full cheeks"), nicknamed "Murder Muppet" by a paleo-artist. Published April 15, 2026 in Papers in Palaeontology. It belonged to Herrerasauria, one of the earliest carnivorous dinosaur families, living three times longer ago than T. rex. It may have been one of the last of its kind.`
  },
  {
    name: "Barcelona Open Tennis",
    text: `Arthur Fils, 21, from France won the Barcelona Open on April 19, 2026, beating Andrey Rublev 6-2, 7-6(7-2) in the final. This was his comeback after an 8-month back injury layoff. His fourth ATP title and second ATP 500 on clay after Hamburg 2024. He won six straight games in set one with powerful groundstrokes, then dominated the tiebreak with seven straight points. He celebrated with the traditional champion's pool dive, cheered by fans. Tennis experts now consider him a serious French Open contender on the same type of clay courts.`
  },
  {
    name: "Madrid Open Tennis",
    text: `The Mutua Madrid Open 2026 runs April 21 to May 3 at Caja Mágica, Madrid, Spain. ATP Masters 1000 and WTA 1000 event — one of the biggest outside Grand Slams. Draw made April 20. World No. 1 Jannik Sinner is top seed, fresh off winning Monte Carlo Masters. He could face Tommy Paul in round 4 and Alex de Minaur in quarterfinals. No. 2 Alexander Zverev, 2021 Madrid champion, could meet Daniil Medvedev in quarterfinals. Notable withdrawals: Carlos Alcaraz (local hero), Novak Djokovic, Emma Raducanu — 17 stars total withdrew. Winner gets 1,000 ranking points heading into French Open next month.`
  }
];

// ---- DeepSeek API call ----
async function vetWithDeepSeek(articleText) {
  const resp = await fetch('https://api.deepseek.com/chat/completions', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${DEEPSEEK_KEY}`
    },
    body: JSON.stringify({
      model: 'deepseek-chat',
      messages: [
        { role: 'system', content: VETTER_PROMPT },
        { role: 'user', content: `Article to review:\n\n${articleText}` }
      ],
      temperature: 0.1,
      max_tokens: 500
    })
  });
  const data = await resp.json();
  if (data.error) throw new Error(data.error.message);
  const content = data.choices[0].message.content;
  // Try to parse JSON from response (strip markdown code blocks if present)
  const cleaned = content.replace(/```json\n?/g, '').replace(/```\n?/g, '').trim();
  return JSON.parse(cleaned);
}

// ---- Claude API call ----
async function vetWithClaude(articleText) {
  if (!ANTHROPIC_KEY) return null;
  const resp = await fetch('https://api.anthropic.com/v1/messages', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'x-api-key': ANTHROPIC_KEY,
      'anthropic-version': '2023-06-01'
    },
    body: JSON.stringify({
      model: 'claude-haiku-4-5-20251001',
      max_tokens: 500,
      temperature: 0.1,
      system: VETTER_PROMPT,
      messages: [
        { role: 'user', content: `Article to review:\n\n${articleText}` }
      ]
    })
  });
  const data = await resp.json();
  if (data.error) throw new Error(data.error.message);
  const content = data.content[0].text;
  const cleaned = content.replace(/```json\n?/g, '').replace(/```\n?/g, '').trim();
  return JSON.parse(cleaned);
}

// ---- Main ----
async function main() {
  if (!DEEPSEEK_KEY) {
    throw new Error('DEEPSEEK_API_KEY is required');
  }

  console.log('='.repeat(80));
  console.log('NEWS OH,YE! — VETTER COMPARISON: DeepSeek V3 vs Claude Haiku');
  console.log('='.repeat(80));
  console.log(`Testing ${ARTICLES.length} articles...\n`);

  const results = [];

  for (const article of ARTICLES) {
    process.stdout.write(`Vetting "${article.name}"...`);

    let dsResult, claudeResult;

    // DeepSeek
    try {
      dsResult = await vetWithDeepSeek(article.text);
      process.stdout.write(' DS✅');
    } catch (e) {
      dsResult = { error: e.message, total: '?', verdict: 'ERROR' };
      process.stdout.write(' DS❌');
    }

    // Claude (if key available)
    if (ANTHROPIC_KEY) {
      try {
        claudeResult = await vetWithClaude(article.text);
        process.stdout.write(' CL✅');
      } catch (e) {
        claudeResult = { error: e.message, total: '?', verdict: 'ERROR' };
        process.stdout.write(' CL❌');
      }
    } else {
      claudeResult = null;
      process.stdout.write(' CL⏭️ (no key)');
    }

    console.log('');
    results.push({ name: article.name, deepseek: dsResult, claude: claudeResult });
  }

  // ---- Print comparison table ----
  console.log('\n' + '='.repeat(80));
  console.log('RESULTS COMPARISON');
  console.log('='.repeat(80));

  const dims = ['violence', 'sexual', 'substance', 'language', 'fear', 'adult_themes', 'distress', 'bias'];
  const header = 'Article'.padEnd(25) + '| DeepSeek         | Claude           | Match?';
  console.log(header);
  console.log('-'.repeat(80));

  for (const r of results) {
    const ds = r.deepseek;
    const cl = r.claude;

    const dsTotal = ds.total ?? '?';
    const dsVerdict = ds.verdict ?? 'ERR';
    const clTotal = cl ? (cl.total ?? '?') : 'N/A';
    const clVerdict = cl ? (cl.verdict ?? 'ERR') : 'N/A';

    const match = cl ? (dsVerdict === clVerdict ? '✅ YES' : '⚠️ DIFFER') : '—';

    console.log(
      r.name.padEnd(25) +
      `| ${String(dsTotal).padStart(2)}/40 ${dsVerdict.padEnd(12)}` +
      `| ${String(clTotal).padStart(2)}/40 ${clVerdict.padEnd(12)}` +
      `| ${match}`
    );
  }

  // ---- Detailed dimension breakdown ----
  console.log('\n' + '='.repeat(80));
  console.log('DETAILED DIMENSION SCORES');
  console.log('='.repeat(80));

  for (const r of results) {
    console.log(`\n📰 ${r.name}:`);
    const ds = r.deepseek;
    const cl = r.claude;

    if (ds.error) {
      console.log(`  DeepSeek ERROR: ${ds.error}`);
    }
    if (cl && cl.error) {
      console.log(`  Claude ERROR: ${cl.error}`);
    }

    if (ds.scores) {
      console.log('  Dimension        DeepSeek  Claude    Delta');
      console.log('  ' + '-'.repeat(50));
      for (const dim of dims) {
        const dsVal = ds.scores[dim] ?? '?';
        const clVal = cl?.scores?.[dim] ?? 'N/A';
        const delta = (typeof dsVal === 'number' && typeof clVal === 'number') ? (dsVal - clVal) : '—';
        const deltaStr = typeof delta === 'number' ? (delta > 0 ? `+${delta}` : `${delta}`) : delta;
        console.log(`  ${dim.padEnd(18)} ${String(dsVal).padStart(3)}       ${String(clVal).padStart(3)}       ${deltaStr}`);
      }
    }

    // Flags
    if (ds.flags?.length) console.log(`  DS flags: ${ds.flags.join(', ')}`);
    if (cl?.flags?.length) console.log(`  CL flags: ${cl.flags.join(', ')}`);
  }

  // ---- Summary ----
  console.log('\n' + '='.repeat(80));
  console.log('SUMMARY');
  console.log('='.repeat(80));

  const agreements = results.filter(r => r.claude && r.deepseek.verdict === r.claude.verdict).length;
  const total = results.filter(r => r.claude).length;

  if (total > 0) {
    console.log(`Verdict agreement: ${agreements}/${total} (${Math.round(agreements/total*100)}%)`);
  }
  console.log(`DeepSeek model: deepseek-chat (V3)`);
  console.log(`Claude model: claude-haiku-4-5-20251001`);
  console.log(`\nTo run with both models, set ANTHROPIC_API_KEY env var.`);
  console.log(`Example: ANTHROPIC_API_KEY=sk-ant-... node vetter-comparison-test.mjs`);
}

main().catch(e => console.error('Fatal:', e));
