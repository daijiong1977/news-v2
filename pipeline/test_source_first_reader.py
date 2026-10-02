"""No mutation of production shell: deterministic, fail-closed package adapter."""
import pytest


def template():
    return '''const mapped = { body: d.summary };
const STEP_IDS = ['read', 'analyze', 'quiz', 'discuss'];
  const stages = [
    { id:'read', label:'Read & Words', emoji:'📖' },
    { id:'analyze', label:'Background', emoji:'🔍' },
    { id:'quiz', label:'Quiz', emoji:'🎯' },
    { id:'discuss', label:'Think', emoji:'💭' },
  ];
{detailReady && tab === 'read' && (
{detailReady && tab === 'analyze' && (
{detailReady && tab === 'quiz' && (
{detailReady && tab === 'discuss' && (
onFinish={() => { bumpStep('read'); switchTab('analyze'); }}
'''


def test_reader_omitted_level_read_only_no_fake_quiz_award_or_progress():
    from pipeline.source_first_reader import adapt_article_shell
    adapted = adapt_article_shell(template().encode()).decode()
    assert "filter(s => detail?.detail_status !== 'omitted' || s === 'read')" in adapted
    assert "filter(s => detail?.detail_status !== 'omitted' || s.id === 'read')" in adapted
    for tab in ('analyze', 'quiz', 'discuss'):
        assert f"detail.detail_status !== 'omitted' && tab === '{tab}'" in adapted
    assert "bumpStep('read'); onComplete()" in adapted
    assert "(tab === 'read' || detail.detail_status === 'omitted')" in adapted


def test_reader_changed_template_fails_before_publish_not_silent_best_effort():
    from pipeline.source_first_reader import adapt_article_shell
    with pytest.raises(ValueError, match='anchor'):
        adapt_article_shell(b'changed official template')
