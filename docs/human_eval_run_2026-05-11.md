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

## Retry

작성일: 2026-05-11

키 값을 출력하지 않고 `.env` 로딩과 OpenAI smoke test를 다시 확인했습니다.

확인 결과:

```text
OPENAI_API_KEY_present: true
OPENAI_API_KEY_prefix_ok: true
OPENAI_API_KEY_has_outer_quotes: false
OPSFLOW_LLM_MODEL: default(gpt-4.1-mini)
```

최소 OpenAI 호출:

```text
result: failed
status: 401
code: invalid_api_key
message: Incorrect API key provided: [REDACTED_OPENAI_API_KEY]
```

파이프라인 재실행:

```bash
python -m src.main run --input data/sample_requests.csv --config config --output outputs/human_eval_llm_assist_retry --dry-run --gold data/labeled_requests.csv --enable-llm-assist
```

결과:

```text
llm_used: 0
llm_errors: 25
QA assertion failures: 0
```

판정:

```text
.env 파싱, prefix, 따옴표 문제는 확인되지 않았다.
OpenAI API 서버가 해당 키를 invalid_api_key로 거절하고 있으므로, 현재 남은 원인은 키 자체가 폐기/오입력/비활성 상태인 경우가 가장 유력하다.
```

## Root Cause and Fix

작성일: 2026-05-11

추가 확인에서 상위 프로세스 환경변수의 `OPENAI_API_KEY`와 `.env`의 `OPENAI_API_KEY`가 서로 다르다는 점을 확인했습니다.

```text
env_before_present: true
env_equals_file: false
file_prefix_ok: true
```

기존 `load_env_file()`은 이미 같은 이름의 환경변수가 있으면 `.env` 값을 덮어쓰지 않았습니다. 따라서 CLI는 `.env`의 정상 키가 아니라 상위 환경에 남아 있던 오래된/잘못된 키로 OpenAI를 호출하고 있었습니다.

초기 로컬 수정:

```text
assist_request()에서 load_env_file(override_existing=True)를 사용하도록 변경했다.
로컬 MVP 실행에서는 프로젝트 .env가 상위 프로세스 환경변수보다 우선한다.
```

수정 후 실행:

```bash
python -m src.main run --input data/sample_requests.csv --config config --output outputs/human_eval_llm_assist_fixed --dry-run --gold data/labeled_requests.csv --enable-llm-assist
```

결과:

```text
llm_used: 25
llm_errors: 0
llm_assist_not_needed: 5
QA assertion failures: 0
```

정량 지표:

```text
request_type_accuracy: 100.0%
target_team_accuracy: 100.0%
priority_accuracy: 100.0%
risk_level_accuracy: 100.0%
decision_accuracy: 70.0%
false_automation_rate: 0.0%
review_recall: 100.0%
```

## Operational Safety Follow-up

작성일: 2026-05-11

외부 검증 피드백을 반영해 dotenv override를 운영 기본 동작에서 제거했습니다.

최종 설계:

```text
1. assist_request()는 .env를 직접 로드하지 않는다.
2. CLI 진입점에서 load_env_file()을 1회 호출한다.
3. 기본 우선순위는 프로세스 환경변수 > .env다.
4. 로컬 디버깅에서만 --prefer-dotenv, OPSFLOW_ENV=local, OPSFLOW_DOTENV_OVERRIDE=1로 .env override를 명시한다.
```

최종 재실행 명령:

```bash
python -m src.main run --input data/sample_requests.csv --config config --output outputs/human_eval_llm_assist_fixed --dry-run --gold data/labeled_requests.csv --enable-llm-assist --prefer-dotenv
```

최종 결과:

```text
llm_used: 25
llm_errors: 0
llm_assist_not_needed: 5
QA assertion failures: 0
```

운영 메모:

```text
운영에서는 --prefer-dotenv를 사용하지 않고, secret manager 또는 프로세스 환경변수 주입값을 우선한다.
운영 이미지에는 .env를 포함하지 않는다.
```
