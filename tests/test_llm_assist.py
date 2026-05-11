import builtins
import json
import os
import sys
from types import SimpleNamespace
from pathlib import Path

from src.decision import decide_automation
from src.llm_assist import (
    assist_request,
    load_env_file,
    should_override_env_file,
    should_use_llm_assist,
)
from src.privacy import mask_pii
from src.rule_engine import evaluate_request
from src.schema import AutomationDecision, RawRequest


def test_should_use_llm_assist_for_missing_fields_review_request() -> None:
    raw_request = RawRequest(
        request_id="REQ-LLM-001",
        channel="form",
        raw_text="A 고객사 결제 오류 에러 장애 재현 bug outage가 발생합니다.",
    )
    privacy_result = mask_pii(raw_request.raw_text)
    evaluation = evaluate_request(raw_request, pii_detected=privacy_result.pii_detected)
    decision = decide_automation(
        raw_request,
        evaluation,
        pii_detected=privacy_result.pii_detected,
    )

    assert decision.automation_decision == AutomationDecision.REVIEW_REQUIRED
    assert should_use_llm_assist(evaluation, decision.automation_decision) is True


def test_assist_request_uses_masked_text_for_pii_when_llm_is_skipped() -> None:
    raw_request = RawRequest(
        request_id="REQ-LLM-PII",
        channel="form",
        raw_text="010-1234-5678 고객에게 연락처 확인 안내를 보내주세요.",
    )
    privacy_result = mask_pii(raw_request.raw_text)
    evaluation = evaluate_request(raw_request, pii_detected=privacy_result.pii_detected)
    decision = decide_automation(
        raw_request,
        evaluation,
        pii_detected=privacy_result.pii_detected,
    )

    result = assist_request(
        raw_request,
        evaluation,
        privacy_result,
        decision.automation_decision,
        enabled=False,
    )

    assert result.trace.used is False
    assert result.input_text == "[PHONE] 고객에게 연락처 확인 안내를 보내주세요."
    assert "010-1234-5678" not in result.suggested_ticket_body
    assert result.trace.suggested_clarification is not None


def test_assist_request_can_use_raw_text_only_when_explicitly_configured() -> None:
    raw_request = RawRequest(
        request_id="REQ-LLM-RAW-OVERRIDE",
        channel="form",
        raw_text="010-1234-5678 고객에게 연락처 확인 안내를 보내주세요.",
    )
    privacy_result = mask_pii(raw_request.raw_text)
    evaluation = evaluate_request(raw_request, pii_detected=privacy_result.pii_detected)
    decision = decide_automation(
        raw_request,
        evaluation,
        pii_detected=privacy_result.pii_detected,
    )

    result = assist_request(
        raw_request,
        evaluation,
        privacy_result,
        decision.automation_decision,
        enabled=False,
        send_raw_text_to_llm=True,
    )

    assert result.trace.used is False
    assert result.input_text == raw_request.raw_text


def test_llm_import_error_falls_back_without_leaking_key(monkeypatch) -> None:
    raw_request = RawRequest(
        request_id="REQ-LLM-IMPORT-ERROR",
        channel="form",
        raw_text="010-1234-5678 고객에게 연락처 확인 안내를 보내주세요.",
    )
    privacy_result = mask_pii(raw_request.raw_text)
    evaluation = evaluate_request(raw_request, pii_detected=privacy_result.pii_detected)
    decision = decide_automation(
        raw_request,
        evaluation,
        pii_detected=privacy_result.pii_detected,
    )
    original_import = builtins.__import__

    def fail_openai_import(name, *args, **kwargs):
        if name == "openai":
            raise ModuleNotFoundError("No module named 'openai'")
        return original_import(name, *args, **kwargs)

    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-real")
    monkeypatch.setattr(builtins, "__import__", fail_openai_import)

    result = assist_request(
        raw_request,
        evaluation,
        privacy_result,
        decision.automation_decision,
        enabled=True,
    )

    assert result.trace.used is False
    assert result.trace.reason == "llm_assist_error_fallback"
    assert result.trace.error == "No module named 'openai'"
    assert "test-key-not-real" not in (result.trace.error or "")
    assert result.input_text == "[PHONE] 고객에게 연락처 확인 안내를 보내주세요."


def test_assist_request_uses_structured_openai_response(monkeypatch) -> None:
    raw_request = RawRequest(
        request_id="REQ-LLM-STRUCTURED",
        channel="form",
        raw_text="결제 안 됩니다.",
    )
    privacy_result = mask_pii(raw_request.raw_text)
    evaluation = evaluate_request(raw_request, pii_detected=privacy_result.pii_detected)
    decision = decide_automation(
        raw_request,
        evaluation,
        pii_detected=privacy_result.pii_detected,
    )
    calls: list[dict[str, object]] = []

    class FakeCompletions:
        def create(self, **kwargs):
            calls.append(kwargs)
            content = json.dumps(
                {
                    "summary": "결제 오류 확인 요청",
                    "suggested_ticket_title": "[Bug] 결제 오류 확인",
                    "suggested_ticket_body": "원문 근거 기준의 결제 오류 검토 초안입니다.",
                    "suggested_clarification": "영향 고객과 재현 조건을 알려 주세요.",
                },
                ensure_ascii=False,
            )
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content=content, refusal=None)
                    )
                ]
            )

    class FakeOpenAI:
        def __init__(self):
            self.chat = SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=FakeOpenAI))
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    result = assist_request(
        raw_request,
        evaluation,
        privacy_result,
        decision.automation_decision,
        enabled=True,
    )

    assert result.trace.used is True
    assert result.summary == "결제 오류 확인 요청"
    assert result.suggested_ticket_title == "[Bug] 결제 오류 확인"
    assert result.suggested_ticket_body == "원문 근거 기준의 결제 오류 검토 초안입니다."
    assert result.trace.suggested_clarification == "영향 고객과 재현 조건을 알려 주세요."
    assert calls[0]["response_format"]["type"] == "json_schema"
    assert calls[0]["response_format"]["json_schema"]["strict"] is True


def test_env_example_uses_supported_llm_variable_names(monkeypatch) -> None:
    monkeypatch.delenv("OPSFLOW_LLM_MODEL", raising=False)
    monkeypatch.delenv("OPS_FLOW_MODEL", raising=False)
    monkeypatch.delenv("OPSFLOW_ENV", raising=False)

    load_env_file(".env.example")

    assert "OPSFLOW_LLM_MODEL" in os.environ
    assert "OPSFLOW_ENV" in os.environ
    assert "OPS_FLOW_MODEL" not in os.environ


def test_load_env_file_can_override_inherited_environment(
    monkeypatch,
    tmp_path: Path,
) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("OPENAI_API_KEY=sk-from-file\n", encoding="utf-8")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-from-parent")

    load_env_file(env_path)
    assert os.environ["OPENAI_API_KEY"] == "sk-from-parent"

    load_env_file(env_path, override_existing=True)
    assert os.environ["OPENAI_API_KEY"] == "sk-from-file"


def test_should_override_env_file_requires_local_signal(monkeypatch) -> None:
    monkeypatch.delenv("OPSFLOW_ENV", raising=False)
    monkeypatch.delenv("OPSFLOW_DOTENV_OVERRIDE", raising=False)

    assert should_override_env_file() is False

    monkeypatch.setenv("OPSFLOW_ENV", "local")
    assert should_override_env_file() is True

    monkeypatch.setenv("OPSFLOW_ENV", "prod")
    monkeypatch.setenv("OPSFLOW_DOTENV_OVERRIDE", "1")
    assert should_override_env_file() is True
