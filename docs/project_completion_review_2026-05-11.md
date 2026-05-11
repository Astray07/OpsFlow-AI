# Project Completion Review

작성일: 2026-05-11

후속 반영: `docs/review_required_structured_masked_update_2026-05-11.md`에서
`review_required` 티켓 초안 생성, structured LLM 응답, masked export 항목을 보완했습니다.

## 검토 기준

- 루트 기획서: `OpsFlow AI 프로젝트 기획서.md`
- 보조 문서: `README.md`, `docs/evaluation_notes.md`, `docs/human_eval_run_2026-05-11.md`, `docs/external_seed_notes.md`
- 실제 구현: `src/`, `config/`, `data/`, `tests/`

## 검증 명령

```bash
pytest -q
python -m ruff check .
python -m src.main run --input data/sample_requests.csv --config config --output outputs/review_check_2026-05-11 --dry-run --gold data/labeled_requests.csv
python -m src.main run --input data/external_seed_samples.csv --config config --output outputs/review_check_external_seed_2026-05-11 --dry-run --gold data/external_seed_labeled_requests.csv
python -m src.main run --input data/edge_cases.csv --config config --output outputs/review_check_edge_cases_2026-05-11 --dry-run
```

## 검증 결과

- 테스트: 65 passed
- 정적 검사: ruff 통과
- 샘플 30건 CLI 실행: 정상 완료
- 샘플 QA assertion: 240 passed, 0 failed
- 외부 seed 8건 CLI 실행: 정상 완료
- 외부 seed QA assertion: 64 passed, 0 failed
- edge case 15건 CLI 실행: 정상 완료
- edge case QA assertion: 120 passed, 0 failed

샘플 평가 지표:

| metric | value |
| --- | ---: |
| request_type_accuracy | 100.0% |
| target_team_accuracy | 100.0% |
| priority_accuracy | 100.0% |
| risk_level_accuracy | 100.0% |
| decision_accuracy | 70.0% |
| missing_fields_exact_match | 76.7% |
| automation_coverage | 26.7% |
| false_automation_rate | 0.0% |
| over_automation_rate | 20.0% |
| review_recall | 100.0% |
| review_precision | 72.7% |

## 종합 판정

OpsFlow AI는 MVP v1의 핵심 파이프라인, rule-first 분류, review queue, trace, QA assertion, dry-run payload까지 구현되어 있습니다. 재현 가능한 CLI와 테스트도 갖춰져 있어 동작 가능한 MVP로 볼 수 있습니다.

다만 기획서 기준으로 "완성"이라고 보기에는 남은 차이가 있습니다. 특히 review_required 요청의 티켓 초안 미생성, human-eval 미완료, 비용/속도 지표 부재, 개인정보 포함 산출물의 공유 경계, 데이터셋 규모 축소가 주요 미완 항목입니다.

## 주요 피드백

### 1. Review 대상 티켓 초안 생성 범위 불일치

기획서 FR-8은 승인 가능 또는 검토 대상 요청에 대해 티켓 초안을 만든다고 정의합니다. 현재 구현은 `ready_for_approval`과 `draft_only`만 티켓 초안을 만들고, `review_required`는 제외합니다.

결과적으로 샘플 30건 중 `ticket_drafts.json`은 8건만 생성되고, review queue 21건은 검토자가 바로 수정할 수 있는 초안이 없습니다. Human-in-the-loop 관점에서는 review item에도 초안이 붙어야 기획 의도와 맞습니다.

### 2. Decision 품질은 안전하지만 gold label과 차이가 큼

false automation rate 0.0%, review recall 100.0%는 기획서의 안전성 목표에 부합합니다. 반면 decision_accuracy 70.0%, over_automation_rate 20.0%, review_precision 72.7%는 완성도 측면에서 아직 보수적입니다.

주요 mismatch는 gold label상 `ready_for_approval`인 요청이 `low_confidence` 또는 `multiple_team_candidates`로 review에 남는 패턴입니다. 현재 정책은 안전 쪽으로 잘 기울어져 있지만, "사람이 수정해야 하는 양을 줄인다"는 목표까지는 덜 도달했습니다.

### 3. Structured output 기반 LLM assist는 아직 아님

기획서 Phase 3에는 structured output schema 적용이 포함되어 있습니다. 현재 LLM assist 구현은 `chat.completions.create()`에 자유 텍스트 프롬프트를 보내고, 응답 본문을 `suggested_ticket_body`로 넣는 방식입니다.

따라서 LLM assist가 켜져도 구조화된 `summary`, `title`, `clarification`, `extracted_fields`를 검증 가능한 스키마로 받는 단계는 미구현입니다.

### 4. Human-eval은 템플릿과 실행 로그만 있고 실제 평가 결과가 없음

기획서는 review handling time, human edit rate, handling time reduction을 mini human-eval로 확인하라고 요구합니다. 현재 `docs/human_eval_template.md`와 LLM assist 실행 기록은 있지만, 참여자별 처리 시간/수정 필드/점수 기록은 없습니다.

이 상태에서는 "AI 정리본이 reviewer의 시간을 줄였다"는 포트폴리오 주장을 강하게 하기 어렵습니다.

### 5. 개인정보 포함 산출물의 공유 경계가 더 명확해야 함

PII 감지 시 LLM 입력, ticket body, trace original_text는 마스킹 쪽으로 보강되어 있습니다. 하지만 `normalized_requests.json`과 `review_queue.csv`에는 PII 요청의 `raw_text`가 그대로 남습니다.

`outputs/`가 gitignore되어 있어 로컬 실행 기준으로는 큰 문제를 줄였지만, review queue를 외부 공유하거나 포트폴리오 산출물로 붙일 때는 masked export가 별도 명령으로 제공되는 편이 안전합니다.

### 6. 비용/속도 지표는 산출물에 없음

기획서 비기능 요구사항에는 LLM 호출 비율과 요청당 예상 비용 리포트, 처리 속도 목표가 있습니다. 현재 평가 리포트에는 token usage, cost estimate, per-request latency가 없습니다.

LLM assist가 포트폴리오에서 중요한 차별점이라면 최소한 `llm_requested`, `llm_used`, `llm_errors`, 평균 처리 시간, 예상 비용 필드를 report에 넣는 것이 좋습니다.

### 7. 데이터셋 규모와 포트폴리오 산출물이 축소됨

로드맵은 synthetic 100건, edge case 20건, external seed 20~30건을 제시하지만 현재는 sample 30건, edge 15건, external seed 8건입니다. 문서에서 한계를 인정하고 있어 정직하지만, 기획서 기준 완료라고 보려면 규모 확장이 필요합니다.

예상 산출물 중 demo GIF 또는 실행 캡처, architecture diagram도 아직 저장소에서 확인되지 않았습니다. `docs/project_plan.md`도 상세 계획 문서라기보다 루트 기획서 링크용 placeholder에 가깝습니다.

## 권장 보완 순서

1. `review_required` 요청에도 티켓 초안을 생성하되, GitHub dry-run payload는 `ready_for_approval`로 제한합니다.
2. decision mismatch 9건을 분석해 threshold, team candidate gap, feature/data keyword를 조정합니다.
3. LLM assist 응답을 구조화된 모델로 분리하고 테스트를 추가합니다.
4. masked review queue export를 추가해 공유용 산출물을 분리합니다.
5. 평가 리포트에 LLM 호출 수, 오류 수, latency, 비용 추정치를 추가합니다.
6. mini human-eval을 실제로 10~20건 수행해 시간/수정량 결과를 문서화합니다.
7. external seed를 rule freeze 이후 신규 30건 이상으로 확장합니다.
8. README용 architecture diagram과 CLI 실행 캡처를 추가합니다.
