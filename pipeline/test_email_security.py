"""Regression tests for the server-side mail relay caller."""
from pipeline import quality_digest as digest


def test_quality_digest_fails_closed_without_internal_secret(monkeypatch):
    monkeypatch.setattr(digest, "SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setattr(digest, "SUPABASE_KEY", "service-key")
    monkeypatch.setattr(digest, "SEND_EMAIL_SECRET", "")
    monkeypatch.setattr(digest.request, "urlopen", lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("must not call the open relay without a secret")))
    assert not digest.send_email("parent@example.com", "subject", "<p>body</p>")


def test_quality_digest_supplies_internal_secret(monkeypatch):
    monkeypatch.setattr(digest, "SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setattr(digest, "SUPABASE_KEY", "service-key")
    monkeypatch.setattr(digest, "SEND_EMAIL_SECRET", "test-secret")
    monkeypatch.setattr(digest, "SEND_EMAIL_URL", "https://example.supabase.co/functions/v1/send-email-v2")
    calls = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b'{"success": true}'

    def urlopen(req, timeout):
        calls.append(req)
        return Response()

    monkeypatch.setattr(digest.request, "urlopen", urlopen)
    assert digest.send_email("parent@example.com", "subject", "<p>body</p>")
    assert calls[0].get_header("X-internal-secret") == "test-secret"
