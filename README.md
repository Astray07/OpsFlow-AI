# OpsFlow AI

OpsFlow AI는 비정형 업무 요청을 표준 스키마로 정규화하고, 승인 가능한 티켓 초안과 사람 검토가 필요한 review queue로 분리하는 CLI 기반 업무 자동화 MVP입니다.

상세 설계는 [OpsFlow AI 프로젝트 기획서.md](OpsFlow%20AI%20%ED%94%84%EB%A1%9C%EC%A0%9D%ED%8A%B8%20%EA%B8%B0%ED%9A%8D%EC%84%9C.md)를 기준으로 합니다.

## Portfolio Report

- [최종 포트폴리오 보고서 Markdown](docs/final_project_report_2026-05-11.md)
- [최종 포트폴리오 보고서 PDF](docs/final_project_report_2026-05-11.pdf)

## Current Pipeline

```text
CSV/JSONL 입력
→ RawRequest 로딩
→ PII masking
→ rule-first 분류/필드 추출/우선순위/위험도 계산
→ automation decision
→ normalized request / ticket draft / review queue / trace 출력
→ masked export / evaluation report / QA assertion report 생성
→ GitHub Issue dry-run payload 생성
```

## CLI

의존성 설치:

```bash
python -m pip install -e ".[dev]"
```

LLM assist를 실제 API로 재현하려면 위 설치로 `openai>=1.0.0`이 설치되어 있어야 하고, 유효한 `OPENAI_API_KEY`가 필요합니다.

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
outputs/masked_normalized_requests.json
outputs/ticket_drafts.json
outputs/review_queue.csv
outputs/masked_review_queue.csv
outputs/execution_log.json
outputs/evaluation_report.md
outputs/qa_assertion_report.md
outputs/github_dry_run.json
```

## Baseline Result

2026-05-11 기준 `data/sample_requests.csv`와 `data/labeled_requests.csv`로 실행한 최종 rule-only baseline:

```text
request_type_accuracy: 100.0%
target_team_accuracy: 100.0%
priority_accuracy: 100.0%
risk_level_accuracy: 100.0%
decision_accuracy: 76.7%
missing_fields_exact_match: 80.0%
automation_coverage: 33.3%
false_automation_rate: 0.0%
over_automation_rate: 14.3%
review_recall: 100.0%
review_precision: 80.0%
QA assertion failures: 0
```

현재 baseline은 false automation을 피하는 방향으로 보수적입니다. Human eval 후속 개선으로 티켓 초안과 review queue는 내부 필드명 대신 한국어 라벨, 누락 정보 설명, 판단 근거 문장을 표시합니다.

`external_seed` 8건 100% 결과는 독립 OOD 일반화 성능이 아니라, seed 관찰 후 config 보강이 포함된 regression smoke test로 해석합니다.

## LLM Assist Boundary

LLM assist는 기본값으로 비활성화되어 있습니다. 재현 가능한 rule-only 실행을 기본으로 두고, 다음 환경변수가 있을 때만 외부 LLM 호출을 시도합니다.

```bash
OPSFLOW_ENABLE_LLM_ASSIST=1
OPSFLOW_LLM_MODEL=gpt-4.1-mini
OPENAI_API_KEY=<key>
```

PII가 감지된 요청은 LLM assist 계층에 `raw_text`가 아니라 `masked_text`만 전달하도록 구현되어 있습니다.
기본 우선순위는 운영 안전성을 위해 상위 프로세스 환경변수 > `.env`입니다. 로컬에서 상위 환경변수에 오래된 키가 남아 있을 때만 `--prefer-dotenv` 또는 `OPSFLOW_ENV=local`로 프로젝트 `.env`를 우선할 수 있습니다.

LLM assist 실행:

```bash
python -m src.main run \
  --input data/sample_requests.csv \
  --config config/ \
  --output outputs/rule_tuned_llm_enabled \
  --dry-run \
  --enable-llm-assist \
  --prefer-dotenv
```

API 오류가 발생하면 키는 로그에서 마스킹되고 rule-only fallback으로 계속 처리됩니다.

2026-05-11 LLM assist 실행 확인:

```text
llm_used: 25
llm_errors: 0
llm_assist_not_needed: 5
QA assertion failures: 0
```

이 결과는 `openai>=1.0.0`과 유효한 `OPENAI_API_KEY`가 모두 갖춰진 로컬 검증 환경의 스냅샷입니다. 패키지 미설치, 키 만료, 권한 오류가 있으면 `llm_assist_error_fallback`으로 처리되고 rule-only 결과로 계속 진행됩니다.

rule tuning 이후 confidence가 충분한 케이스가 늘면서 LLM 호출 후보는 28건에서 25건으로 줄었습니다.

LLM assist는 현재 분류/라우팅/결정을 덮어쓰지 않고 티켓 본문과 검토 보조 문구를 개선하는 계층입니다. 따라서 gold label 기반 정량 지표는 rule-tuned rule-only와 동일합니다.

보안 경계:

```text
PII 감지 시 LLM 입력, execution log, ticket body, generated summary, extracted fields는 masked_text 기준 값을 사용합니다.
.env.example은 placeholder만 포함하고 실제 키는 .env 또는 secret manager에 보관합니다.
review_queue.csv에는 reviewer 확인용 raw_text 컬럼이 있으므로 외부 공유 시에는 `masked_review_queue.csv`와 `masked_normalized_requests.json`만 사용합니다.
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
docs/human_eval_run_2026-05-11.md   LLM assist 비교 실행과 dotenv 우선순위 검증
docs/security_notes.md        로컬 dotenv와 운영 secret 우선순위 가이드
docs/agent_validation_prompt.md     외부 검증 에이전트용 프롬프트
docs/human_eval_form_2026-05-11.html  사람 평가자가 A/B 초안을 채점하는 정적 HTML 도구
docs/final_human_eval_improvement_2026-05-11.md  human eval 피드백 반영 내역과 최종 검증 결과
docs/final_project_report_2026-05-11.md  프로젝트 최종 완료 보고서
docs/final_project_report_2026-05-11.pdf  포트폴리오 제출용 PDF 보고서
```

정책성 regex는 `config/extraction_rules.yml`, risk side-effect와 review action 우선순위는 각각 `config/risk_rules.yml`, `config/review_policy.yml`에서 관리합니다.
