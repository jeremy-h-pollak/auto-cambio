"""Unit tests for the OpenRouter client (game/llm_client.py).

No real network: requests.post and time.sleep are monkeypatched throughout.
"""

import pytest

from game import llm_client


class FakeResp:
    def __init__(self, status=200, body="default", text="", headers=None):
        self.status_code = status
        if body == "default":
            body = {
                "choices": [{"message": {"content": '{"action": "draw_deck"}'}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 2, "cost": 0.0001},
            }
        self._body = body
        self.text = text
        self.headers = headers or {}

    def json(self):
        if self._body is None:
            raise ValueError("no json body")
        return self._body


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    llm_client.reset_usage()
    monkeypatch.setattr(llm_client.time, "sleep", lambda *_: None)
    yield


def _set_key(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")


# ── model_name / api key ─────────────────────────────────────────────────────
def test_model_name_default(monkeypatch):
    monkeypatch.delenv("OPENROUTER_MODEL", raising=False)
    assert llm_client.model_name() == llm_client.DEFAULT_MODEL


def test_model_name_override(monkeypatch):
    monkeypatch.setenv("OPENROUTER_MODEL", "vendor/model")
    assert llm_client.model_name() == "vendor/model"


def test_api_key_missing_raises(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(llm_client.LLMError):
        llm_client._api_key()


# ── usage accounting ─────────────────────────────────────────────────────────
def test_record_usage_accumulates_and_summary():
    llm_client._record_usage({"prompt_tokens": 5, "completion_tokens": 1, "cost": 0.002})
    llm_client._record_usage(None)            # non-dict path still counts the call
    u = llm_client.usage()
    assert u["calls"] == 2
    assert u["prompt_tokens"] == 5 and u["completion_tokens"] == 1
    assert u["cost"] == pytest.approx(0.002)
    assert "tokens" in llm_client.summary_line()


def test_record_usage_bad_cost_ignored():
    llm_client._record_usage({"cost": "not-a-number"})
    assert llm_client.usage()["cost"] == 0.0


def test_summary_line_without_cost():
    llm_client._record_usage({"prompt_tokens": 3, "completion_tokens": 0})
    assert "cost n/a" in llm_client.summary_line()


# ── chat ─────────────────────────────────────────────────────────────────────
def test_chat_success(monkeypatch):
    _set_key(monkeypatch)
    monkeypatch.setattr(llm_client.requests, "post", lambda *a, **k: FakeResp())
    out = llm_client.chat([{"role": "user", "content": "hi"}])
    assert out == '{"action": "draw_deck"}'
    assert llm_client.usage()["calls"] == 1


def test_chat_non_retryable_4xx_raises_immediately(monkeypatch):
    _set_key(monkeypatch)
    calls = []

    def post(*a, **k):
        calls.append(1)
        return FakeResp(status=401, text="bad key")

    monkeypatch.setattr(llm_client.requests, "post", post)
    with pytest.raises(llm_client.LLMError):
        llm_client.chat([{"role": "user", "content": "x"}])
    assert len(calls) == 1                     # no retries on a hard 4xx


def test_chat_retries_429_then_succeeds(monkeypatch):
    _set_key(monkeypatch)
    seq = [FakeResp(status=429, headers={"Retry-After": "0"}), FakeResp()]
    monkeypatch.setattr(llm_client.requests, "post", lambda *a, **k: seq.pop(0))
    assert llm_client.chat([{"role": "user", "content": "x"}]) == '{"action": "draw_deck"}'


def test_chat_persistent_5xx_raises_after_retries(monkeypatch):
    _set_key(monkeypatch)
    monkeypatch.setattr(llm_client.requests, "post",
                        lambda *a, **k: FakeResp(status=503, text="down"))
    with pytest.raises(llm_client.LLMError):
        llm_client.chat([{"role": "user", "content": "x"}])


def test_chat_transport_error_retried_then_raises(monkeypatch):
    _set_key(monkeypatch)

    def post(*a, **k):
        raise llm_client.requests.RequestException("boom")

    monkeypatch.setattr(llm_client.requests, "post", post)
    with pytest.raises(llm_client.LLMError):
        llm_client.chat([{"role": "user", "content": "x"}])


def test_chat_malformed_body_raises(monkeypatch):
    _set_key(monkeypatch)
    monkeypatch.setattr(llm_client.requests, "post",
                        lambda *a, **k: FakeResp(body={"no": "choices"}))
    with pytest.raises(llm_client.LLMError):
        llm_client.chat([{"role": "user", "content": "x"}])


def test_chat_force_json_toggles_response_format(monkeypatch):
    _set_key(monkeypatch)
    captured = {}

    def post(url, headers=None, json=None, timeout=None):
        captured["json"] = json
        return FakeResp()

    monkeypatch.setattr(llm_client.requests, "post", post)
    llm_client.chat([{"role": "user", "content": "x"}], force_json=True)
    assert captured["json"]["response_format"] == {"type": "json_object"}
    llm_client.chat([{"role": "user", "content": "x"}], force_json=False)
    assert "response_format" not in captured["json"]
