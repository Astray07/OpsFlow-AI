# Review Draft, Structured LLM, Masked Export Update

작성일: 2026-05-11

## 목적

이 변경은 기획서 점검에서 나온 세 가지 미완 항목을 보완합니다.

1. `review_required` 요청에도 티켓 초안을 생성합니다.
2. LLM assist 응답을 자유 텍스트가 아니라 JSON Schema 기반 구조화 응답으로 받습니다.
3. 외부 공유용 masked export를 별도로 생성합니다.

## 변경 요약

### Review-required ticket draft

`src/ticket_builder.py`에서 티켓 초안 생성 대상을 다음으로 확장했습니다.

```text
ready_for_approval
draft_only
review_required
```

`reject` 요청은 계속 티켓 초안을 만들지 않습니다. `src/github_client.py`는 기존 정책대로 `ready_for_approval`과 `draft_only`만 dry-run payload로 변환하므로, 검토 대상 초안이 외부 등록 후보로 섞이지 않습니다.

### Structured LLM response

`src/llm_assist.py`에 `LlmAssistStructuredResponse`를 추가하고 Chat Completions 호출에 `response_format.type=json_schema`를 적용했습니다.

구조화 응답 필드:

```text
summary
suggested_ticket_title
suggested_ticket_body
suggested_clarification
```

응답 JSON이 파싱 또는 검증에 실패하면 기존처럼 rule-only fallback을 사용합니다. OpenAI API key나 응답 오류는 로그에 민감값을 노출하지 않는 기존 redaction 경계를 유지합니다.

### Masked export

CLI 실행 시 다음 공유용 산출물이 추가됩니다.

```text
masked_normalized_requests.json
masked_review_queue.csv
```

원본 로컬 산출물인 `normalized_requests.json`과 `review_queue.csv`는 디버깅을 위해 유지합니다. 단, 외부 공유나 포트폴리오 첨부에는 masked 파일만 사용합니다.

## 검증 명령

```bash
python -m ruff check .
pytest -q
python -m src.main run --input data/sample_requests.csv --config config --output outputs/review_required_structured_masked_check_2026-05-11 --dry-run --gold data/labeled_requests.csv
```

## 검증 결과

```text
ruff: All checks passed
pytest: 68 passed
sample CLI: 30 requests processed
QA assertions: 240 passed, 0 failed
```

티켓 초안 생성 결과:

| source_decision | count |
| --- | ---: |
| draft_only | 3 |
| ready_for_approval | 5 |
| review_required | 21 |

GitHub dry-run payload:

```text
8건
```

즉, 검토 대상 초안은 생성되지만 외부 등록 후보는 기존처럼 approval-safe decision으로 제한됩니다.

PII 확인:

```text
masked_normalized_requests.json: 010-1234-5678 / ORD-12345 미검출
masked_review_queue.csv: 010-1234-5678 / ORD-12345 미검출
```

## Human-eval 진행 방법

### 1. 평가 산출물 생성

rule-only와 LLM-assist 산출물을 각각 생성합니다.

```bash
python -m src.main run --input data/sample_requests.csv --config config --output outputs/human_eval_rule_only --dry-run --gold data/labeled_requests.csv
python -m src.main run --input data/sample_requests.csv --config config --output outputs/human_eval_llm_assist --dry-run --gold data/labeled_requests.csv --enable-llm-assist --prefer-dotenv
```

운영 환경에서는 `--prefer-dotenv`를 사용하지 않고 프로세스 환경변수 또는 secret manager의 `OPENAI_API_KEY`를 사용합니다.

### 2. 평가 대상 선정

권장 표본은 10~20건입니다.

우선순위:

```text
1. review_required 요청 10건
2. ready_for_approval 또는 draft_only 요청 5~10건
3. PII 포함 요청은 privacy_safety 확인용으로 1~2건 포함
```

각 request_id마다 rule-only와 LLM-assist의 `ticket_drafts.json`, `masked_review_queue.csv`를 비교합니다. 평가자는 어느 쪽이 LLM 결과인지 모르는 상태로 A/B 채점하는 편이 좋습니다.

### 3. 채점 항목

`docs/human_eval_template.md`의 5개 기준을 그대로 사용합니다.

| criterion | 의미 |
| --- | --- |
| factuality | 원문에 없는 사실을 만들지 않았는지 |
| actionability | 담당자가 다음 행동을 바로 알 수 있는지 |
| completeness | 증상, 범위, 요청 행동, 누락 질문이 충분한지 |
| privacy_safety | PII masking 경계가 유지되는지 |
| reviewer_effort | 사람이 다시 써야 하는 양이 줄었는지 |

각 항목은 1, 3, 5점 중 하나로 기록합니다.

### 4. 시간 측정

요청별로 다음 시간을 재면 됩니다.

```text
raw_only_seconds: 원문만 보고 초안/질문을 만드는 시간
opsflow_seconds: OpsFlow 산출물을 보고 수정 완료하는 시간
```

계산식:

```text
handling_time_reduction
= (raw_only_seconds 평균 - opsflow_seconds 평균) / raw_only_seconds 평균
```

### 5. 통과 기준

MVP 포트폴리오 기준으로는 다음을 통과 기준으로 둡니다.

```text
privacy_safety 평균 5.0
factuality 평균 4.0 이상
reviewer_effort 평균이 rule-only 대비 1점 이상 개선
handling_time_reduction 양수
```

privacy_safety가 5점 미만인 항목은 자동 개선 효과와 무관하게 blocker로 분류합니다.

### 6. 결과 기록 위치

실행 조건, 표본 request_id, 점수표, 해석은 다음 파일에 기록합니다.

```text
docs/human_eval_run_YYYY-MM-DD.md
```

기존 `docs/human_eval_run_2026-05-11.md`는 API key 이슈와 LLM assist 재실행 기록입니다. 실제 사람 채점 결과는 별도 날짜 파일로 분리하는 편이 좋습니다.

