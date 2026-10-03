"""Package-only adaptation for explicitly omitted source-first detail levels."""
ADAPTER_VERSION = 'source-first-detail-availability-v2'


def adapt_article_shell(data):
    text = data.decode('utf-8')
    changes = {
        'const mapped = {':
        'const mapped = {\n          detail_status: d.detail_status,',
        "const STEP_IDS = ['read', 'analyze', 'quiz', 'discuss'];":
        "const STEP_IDS = ['read', 'analyze', 'quiz', 'discuss'].filter(s => detail?.detail_status !== 'omitted' || s === 'read');",
        "    { id:'discuss', label:'Think', emoji:'💭' },\n  ];":
        "    { id:'discuss', label:'Think', emoji:'💭' },\n  ].filter(s => detail?.detail_status !== 'omitted' || s.id === 'read');",
        "detailReady && tab === 'read'":
        "detailReady && (tab === 'read' || detail.detail_status === 'omitted')",
        "onFinish={() => { bumpStep('read'); switchTab('analyze'); }}":
        "onFinish={() => { if (detail.detail_status === 'omitted') { bumpStep('read'); onComplete(); } else { bumpStep('read'); switchTab('analyze'); } }}",
    }
    for tab in ('analyze', 'quiz', 'discuss'):
        changes[f"detailReady && tab === '{tab}'"] = f"detailReady && detail.detail_status !== 'omitted' && tab === '{tab}'"
    for anchor, replacement in changes.items():
        if text.count(anchor) != 1:
            raise ValueError('Reader adapter anchor changed: ' + anchor)
        text = text.replace(anchor, replacement)
    return text.encode('utf-8')
