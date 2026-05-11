# OpsFlow AI

OpsFlow AI는 비정형 업무 요청을 표준 스키마로 정규화하고, 승인 가능한 티켓 초안과 사람 검토가 필요한 review queue로 분리하는 CLI 기반 업무 자동화 MVP입니다.

상세 설계는 [OpsFlow AI 프로젝트 기획서.md](OpsFlow%20AI%20%ED%94%84%EB%A1%9C%EC%A0%9D%ED%8A%B8%20%EA%B8%B0%ED%9A%8D%EC%84%9C.md)를 기준으로 합니다.

## Current Pipeline

```text
CSV/JSONL 입력
→ RawRequest 로딩
→ PII masking
→ rule-first 분류/필드 추출/우선순위/위험도 계산
→ automation decision
→ normalized request / ticket draft / review queue / trace 출력
→ evaluation report / QA assertion report 생성
→ GitHub Issue dry-run payload 생성
```

## CLI

```bash
python -m src.main run \
  --input data/sample_requests.csv \
  --config config/ \
  --output outputs/ \
  --dry-run
```

생성 산출물:

```text
outputs/normalized_requests.json
outputs/ticket_drafts.json
outputs/review_queue.csv
outputs/execution_log.json
outputs/evaluation_report.md
outputs/qa_assertion_report.md
outputs/github_dry_run.json
```

## Baseline Result

2026-05-11 기준 `data/sample_requests.csv`와 `data/labeled_requests.csv`로 실행한 rule-tuned rule-only baseline:

```text
request_type_accuracy: 100.0%
target_team_accuracy: 100.0%
priority_accuracy: 100.0%
risk_level_accuracy: 100.0%
decision_accuracy: 70.0%
automation_coverage: 26.7%
false_automation_rate: 0.0%
over_automation_rate: 20.0%
review_recall: 100.0%
QA assertion failures: 0
```

현재 baseline은 false automation을 피하는 방향으로 보수적입니다. 분류/라우팅 정확도는 rule tuning 이후 개선됐지만, `ready_for_approval` threshold가 보수적이어서 decision accuracy와 automation coverage는 추가 실험 여지가 있습니다.

## LLM Assist Boundary

LLM assist는 기본값으로 비활성화되어 있습니다. 재현 가능한 rule-only 실행을 기본으로 두고, 다음 환경변수가 있을 때만 외부 LLM 호출을 시도합니다.

```bash
OPSFLOW_ENABLE_LLM_ASSIST=1
OPSFLOW_LLM_MODEL=gpt-4.1-mini
OPENAI_API_KEY=<key>
```

PII가 감지된 요청은 LLM assist 계층에 `raw_text`가 아니라 `masked_text`만 전달하도록 구현되어 있습니다.

LLM assist 실행:

```bash
python -m src.main run \
  --input data/sample_requests.csv \
  --config config/ \
  --output outputs/rule_tuned_llm_enabled \
  --dry-run \
  --enable-llm-assist
```

API 오류가 발생하면 키는 로그에서 마스킹되고 rule-only fallback으로 계속 처리됩니다.

2026-05-11 LLM assist 실행 확인:

```text
llm_used: 28
llm_errors: 0
QA assertion failures: 0
```

LLM assist는 현재 분류/라우팅/결정을 덮어쓰지 않고 티켓 본문과 검토 보조 문구를 개선하는 계층입니다. 따라서 gold label 기반 정량 지표는 rule-tuned rule-only와 동일합니다.

보안 경계:

```text
PII 감지 시 LLM 입력, execution log, ticket body, generated summary, extracted fields는 masked_text 기준 값을 사용합니다.
.env.example은 placeholder만 포함하고 실제 키는 .env 또는 secret manager에 보관합니다.
```

## Project Layout

```text
config/   업무 정책, scoring, risk, privacy 설정
data/     샘플 요청과 라벨 데이터
docs/     문제 정의, 평가 노트, 면접용 노트
src/      CLI와 처리 레이어
tests/    단위 테스트
outputs/  실행 결과 산출물
```

추가 검증 문서:

```text
docs/external_seed_notes.md   공개 issue 기반 seed 수집 과정과 결과
docs/human_eval_template.md   LLM assist 품질 비교용 human-eval 양식
docs/human_eval_run_2026-05-11.md   LLM assist 비교 실행 시도와 invalid key 결과
docs/agent_validation_prompt.md     외부 검증 에이전트용 프롬프트
```

정책성 regex는 `config/extraction_rules.yml`, risk side-effect와 review action 우선순위는 각각 `config/risk_rules.yml`, `config/review_policy.yml`에서 관리합니다.
