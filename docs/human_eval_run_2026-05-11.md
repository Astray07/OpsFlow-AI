# LLM Assist Human-Eval Run

작성일: 2026-05-11

## 목적

rule-only 산출물과 LLM assist 산출물을 비교해 티켓 초안과 reviewer 보조 문구 품질을 평가하려고 했습니다.

## 실행 명령

```bash
python -m src.main run --input data/sample_requests.csv --config config --output outputs/human_eval_rule_only --dry-run --gold data/labeled_requests.csv
python -m src.main run --input data/sample_requests.csv --config config --output outputs/human_eval_llm_assist --dry-run --gold data/labeled_requests.csv --enable-llm-assist
```

## 결과

```text
rule_only:
  llm_used: 0
  llm_errors: 0

llm_assist:
  llm_used: 0
  llm_errors: 25
  error_type: OpenAI 401 invalid_api_key
```

API key 값은 출력하지 않았고, execution log의 오류 메시지는 `[REDACTED_OPENAI_API_KEY]`로 마스킹되어 있습니다.

## 판정

이번 실행은 실제 LLM 응답을 받지 못했으므로 human-eval 점수를 산출하지 않습니다. `docs/human_eval_template.md`의 양식은 유지하고, 유효한 `OPENAI_API_KEY`로 재실행한 뒤 같은 기준으로 채점합니다.

## 재실행 조건

```text
1. .env의 OPENAI_API_KEY를 유효한 값으로 교체한다.
2. 필요하면 OPSFLOW_LLM_MODEL을 명시한다. 기본값은 gpt-4.1-mini다.
3. 위 명령 두 개를 다시 실행한다.
4. outputs/human_eval_rule_only와 outputs/human_eval_llm_assist에서 같은 request_id의 suggested_ticket_body, suggested_question을 비교한다.
5. docs/human_eval_template.md 기준으로 1~5점을 기록한다.
```
