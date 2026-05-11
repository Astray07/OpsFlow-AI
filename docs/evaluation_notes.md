# Evaluation Notes

Mini human-eval과 threshold sweep 결과를 기록하는 문서입니다.

## Phase 1 Dataset Preparation

작성일: 2026-05-11

이번 단계의 목적은 구현 전에 라벨링 기준이 실제 샘플 데이터에 적용 가능한지 확인하는 것입니다. 아직 rule engine이나 LLM assist 구현 결과를 평가한 것은 아닙니다.

### Prepared Files

| file | count | purpose |
| --- | ---: | --- |
| `data/sample_requests.csv` | 30 | 기본 synthetic 업무 요청 샘플 |
| `data/labeled_requests.csv` | 30 | sample request에 대한 gold label |
| `data/edge_cases.csv` | 15 | 구현 전 반드시 통과해야 할 edge case 목록 |
| `data/external_seed_requests.csv` | 8 | 공개 GitHub issue 기반 paraphrase seed pool |

### Label Coverage

요청 유형은 다음 범위를 포함하도록 구성했습니다.

```text
bug_report
data_request
customer_support
feature_request
approval_request
internal_ops
other
```

decision label은 다음 범위를 포함합니다.

```text
ready_for_approval
draft_only
review_required
reject
```

### Current Limitations

```text
1. 현재 데이터는 synthetic 중심입니다.
2. 외부 공개 seed 데이터는 아직 gold label로 편입하지 않은 seed pool입니다.
3. 라벨은 단일 작성자 기준이므로 편향 가능성이 있습니다.
4. 실제 구현 후 예측 결과와 gold label을 비교하며 라벨 기준을 재검토해야 합니다.
```

### Next Check Before Implementation

```text
1. CSV row 수와 request_id 정합성 확인
2. expected_request_type / team / priority / decision 값이 schema enum과 일치하는지 확인
3. reject, review_required, ready_for_approval 사례가 모두 있는지 확인
4. PII 포함 요청이 review_required로 라벨링됐는지 확인
```

## Planned Checks

- false automation rate
- review recall
- review precision
- human edit rate
- review handling time reduction
- QA assertion failures

## Phase 5 Rule-Only Baseline

작성일: 2026-05-11

실행 명령:

```bash
python -m src.main run --input data/sample_requests.csv --config config --output outputs --dry-run
```

이번 평가는 LLM assist를 비활성화한 rule-only baseline입니다. 목적은 LLM 적용 전 기준선을 만들고, false automation과 review recall을 확인하는 것입니다.

### Generated Outputs

| output | count | note |
| --- | ---: | --- |
| `outputs/normalized_requests.json` | 30 | 정규화 요청 |
| `outputs/ticket_drafts.json` | 1 | draft/ready 요청만 포함 |
| `outputs/review_queue.csv` | 29 | review/reject 요청 |
| `outputs/execution_log.json` | 30 | 판단 trace |
| `outputs/github_dry_run.json` | 1 | 외부 등록 없이 payload만 생성 |

### Metrics

| metric | value |
| --- | ---: |
| request_type_accuracy | 56.7% |
| target_team_accuracy | 56.7% |
| priority_accuracy | 56.7% |
| risk_level_accuracy | 66.7% |
| decision_accuracy | 53.3% |
| missing_fields_exact_match | 50.0% |
| automation_coverage | 3.3% |
| false_automation_rate | 0.0% |
| review_recall | 100.0% |
| review_precision | 55.2% |

### QA Assertions

```text
total_assertions: 210
passed: 210
failed: 0
```

### Interpretation

현재 baseline은 안전성 쪽으로 보수적입니다.

```text
좋은 점:
- false automation rate가 0.0%입니다.
- review recall이 100.0%입니다.
- QA assertion 실패가 없습니다.

한계:
- request_type과 target_team accuracy가 낮습니다.
- other fallback이 과도하게 발생합니다.
- ready_for_approval gold label 중 다수가 review_required로 분류됩니다.
- automation coverage가 3.3%로 낮습니다.
```

다음 개선은 다음 순서로 진행하는 것이 좋습니다.

```text
1. request_types.yml keyword coverage 보강
2. field extractor의 날짜, 목적, 고객, 영향 범위 추출 개선
3. LLM assist를 낮은 confidence/missing fields 요청에만 제한적으로 적용
4. threshold sweep 결과를 보고 ready/draft 기준 조정
```

## Phase 5 Rule Keyword / Extractor Tuning

작성일: 2026-05-11

목적:

```text
rule-only baseline에서 other fallback이 과도하게 발생하던 문제를 줄이고,
LLM 적용 전 rule 기반 분류/라우팅 기준선을 개선한다.
```

변경 요약:

```text
1. bug_report 키워드에 결제, 실패, timeout, API latency 계열을 추가했다.
2. data_request 키워드에 가입자, 전환율, 사용량, 매출, CSV/PDF 등을 추가했다.
3. feature_request 키워드에 필터, 옵션, 정렬, 템플릿, 위젯 계열을 추가했다.
4. approval/internal_ops 키워드에 결제 취소, 환불 처리, 삭제, 보안, 관리자 로그인 계열을 추가했다.
5. request_type fallback을 조정해 명시적 keyword signal이 있으면 other로 과도하게 떨어지지 않게 했다.
6. risk rule에서 고객사/enterprise 단어만으로 medium risk가 되던 문제를 완화했다.
7. 개인정보 원문, 보안 우회, 삭제, 운영 데이터 요청은 더 명확하게 high risk로 잡도록 했다.
```

비교 결과:

| metric | before tuning | after tuning |
| --- | ---: | ---: |
| request_type_accuracy | 56.7% | 100.0% |
| target_team_accuracy | 56.7% | 100.0% |
| priority_accuracy | 56.7% | 100.0% |
| risk_level_accuracy | 66.7% | 100.0% |
| decision_accuracy | 53.3% | 56.7% |
| missing_fields_exact_match | 50.0% | 73.3% |
| automation_coverage | 3.3% | 20.0% |
| false_automation_rate | 0.0% | 0.0% |
| review_recall | 100.0% | 100.0% |
| review_precision | 55.2% | 66.7% |

해석:

```text
rule tuning만으로 request_type, target_team, priority, risk_level의 gold label 일치율은 크게 개선됐다.
false automation rate와 review recall은 기존 안전성을 유지했다.
decision_accuracy는 여전히 낮은 편인데, 이는 ready_for_approval threshold가 보수적이기 때문이다.
threshold sweep 기준으로는 0.65에서도 false automation rate가 0.0%였으므로,
다음 실험에서는 ready/draft threshold 조정 여부를 별도로 검토할 수 있다.
```

## Phase 5 LLM Assist Activation Attempt

작성일: 2026-05-11

실행 명령:

```bash
python -m src.main run --input data/sample_requests.csv --config config --output outputs/rule_tuned_llm_enabled --dry-run --gold data/labeled_requests.csv --enable-llm-assist
```

초기 결과:

```text
llm_assist requested: 28
llm_used: 0
llm_errors: 28
fallback_applied: 28
```

초기 실행에서는 OpenAI API가 401 invalid API key를 반환했다. 키 값은 로그와 산출물에 저장하지 않도록 `[REDACTED_OPENAI_API_KEY]`로 마스킹했다.

LLM-enabled 실행의 평가 지표는 rule-tuned rule-only 실행과 동일하다.

```text
request_type_accuracy: 100.0%
target_team_accuracy: 100.0%
priority_accuracy: 100.0%
risk_level_accuracy: 100.0%
decision_accuracy: 56.7%
automation_coverage: 20.0%
false_automation_rate: 0.0%
review_recall: 100.0%
```

해석:

```text
이번 실행에서는 실제 LLM 응답을 받지 못했기 때문에 LLM assist 품질 비교는 수행되지 않았다.
다만 API 실패 시 rule-only fallback으로 전체 파이프라인과 QA assertion이 유지되는 것은 확인했다.
유효한 OpenAI API key로 재실행하면 ticket body와 clarification question 품질을 비교할 수 있다.
현재 설계상 LLM assist는 request_type/target_team/decision을 직접 덮어쓰지 않으므로,
정량 metric 변화보다는 티켓 초안 품질과 reviewer 보조 문구 품질을 별도 human-eval로 봐야 한다.
```

## Phase 5 LLM Assist Successful Run

작성일: 2026-05-11

유효한 `OPENAI_API_KEY`를 프로세스 환경변수로 주입해 다시 실행했다. 키 값은 출력하지 않았고, 산출물 내 `sk-` 문자열 잔존 여부도 확인했다.

실행 명령:

```bash
python -m src.main run --input data/sample_requests.csv --config config --output outputs/rule_tuned_llm_enabled_env_example --dry-run --gold data/labeled_requests.csv --enable-llm-assist
```

결과:

```text
llm_assist requested: 28
llm_used: 28
llm_errors: 0
llm_assist_not_needed: 2
```

정량 평가는 rule-tuned rule-only와 동일하다.

```text
request_type_accuracy: 100.0%
target_team_accuracy: 100.0%
priority_accuracy: 100.0%
risk_level_accuracy: 100.0%
decision_accuracy: 56.7%
automation_coverage: 20.0%
false_automation_rate: 0.0%
review_recall: 100.0%
QA assertion failures: 0
```

해석:

```text
LLM assist는 현재 request_type, target_team, priority, risk_level, automation_decision을 덮어쓰지 않는다.
따라서 gold label 기반 정량 지표는 변하지 않는다.
대신 suggested_ticket_body와 review 보조 문구 품질을 개선하는 역할이다.
실제 API 호출이 성공해도 정책 불변식과 QA assertion은 유지됐다.
```

보안 메모:

```text
실제 API key는 .env 또는 안전한 secret manager에만 보관한다.
.env.example은 placeholder만 포함해야 한다.
```

## Phase 5 Validation Feedback Patch

작성일: 2026-05-11

외부 검증 피드백을 반영해 다음 항목을 보강했다.

```text
1. .env.example의 LLM 모델 변수명을 OPSFLOW_LLM_MODEL로 통일하고 OPSFLOW_ENABLE_LLM_ASSIST placeholder를 추가했다.
2. execution_log.json의 ExecutionTrace.original_text는 PII 감지 시 masked_text를 저장하도록 변경했다.
3. ticket_builder의 original_request 섹션도 PII 감지 시 masked_text를 사용하도록 변경했다.
4. internal_ops side-effect keyword를 코드 하드코딩에서 risk_rules.yml로 이동했다.
5. review_policy.yml에 high_risk_action과 low_confidence 라우팅을 추가했다.
6. edge_cases.csv 15건을 실제 pipeline 결과와 비교하는 통합 테스트를 추가했다.
7. evaluate.py에 ready_for_approval 과승격을 잡는 over_automation_rate 지표를 추가했다.
```

Edge case 회귀 검증:

```text
data/edge_cases.csv: 15/15 expected_handling 일치
```

패치 후 최신 샘플 평가:

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

산출물 요약:

```text
normalized: 30
ticket_drafts: 8
github_dry_run: 8
review_queue: 22
execution_traces: 30
QA assertion failures: 0
```

## Phase 5 Remaining Feedback Patch

작성일: 2026-05-11

외부 검증 피드백에서 남아 있던 정책-코드 분리, 평가 재현성, 외부 seed, fail-soft 처리 항목을 추가로 정리했다.

변경 요약:

```text
1. field extraction regex를 src/rule_engine.py에서 config/extraction_rules.yml로 분리했다.
2. evaluate.py threshold sweep이 별도 하드코딩 조건이 아니라 decision.py의 decide_automation을 재사용하도록 변경했다.
3. risk_rules.yml의 matching_semantics와 side_effects를 실제 risk trace에 반영했다.
4. review_queue action priority를 코드 상수에서 config/review_policy.yml로 이동했다.
5. priority_rules.yml의 medium.default를 rule engine이 읽도록 반영했다.
6. batch normalize 중 단일 요청 예외가 발생해도 processing_status=failed로 남기고 다음 요청을 계속 처리하도록 했다.
7. 공개 GitHub issue 기반 external seed 8건을 paraphrase 형태로 수집했다.
8. LLM assist 품질 비교용 human-eval 템플릿을 추가했다.
9. PII 감지 요청의 summary, suggested ticket, extracted fields에는 masked_text 기준 값을 사용하도록 강화했다.
10. src/tracer.py를 실제 execution trace builder로 전환해 normalizer에서 trace 조립 책임을 분리했다.
```

새 문서:

```text
docs/external_seed_notes.md
docs/human_eval_template.md
```

최신 샘플 평가:

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

QA assertion:

```text
total_assertions: 240
passed: 240
failed: 0
```

Decision-layer 기반 threshold sweep:

| threshold | automation_coverage | false_automation_rate | review_recall |
| ---: | ---: | ---: | ---: |
| 0.65 | 40.0% | 8.3% | 93.8% |
| 0.75 | 26.7% | 0.0% | 100.0% |
| 0.85 | 16.7% | 0.0% | 100.0% |

해석:

```text
기존 threshold sweep은 evaluate.py 내부 조건으로만 자동화 가능 여부를 근사했다.
이번 변경 후 sweep은 실제 decision cascade를 재사용하므로 draft_only와 review_required 조건이 더 정확히 반영된다.
0.65에서는 automation coverage가 증가하지만 false automation이 발생하므로, 현재 기본 threshold 0.75를 유지하는 것이 안전하다.
```

Deferred note:

```text
config/localization.yml은 v0.3 확장 포인트로 유지한다.
현재 MVP에서는 한국어/영어 alias를 별도 동작 경로로 사용하지 않는다.
외부 공개 자료에서는 "v0.3 예정"으로 명시한다.
```

## Phase 6 External Seed Gold Evaluation

작성일: 2026-05-11

목적:

```text
공개 GitHub issue 기반 paraphrase seed를 실제 입력/라벨 세트로 편입해 synthetic-only 평가의 한계를 줄인다.
```

추가 파일:

```text
data/external_seed_samples.csv
data/external_seed_labeled_requests.csv
```

실행 명령:

```bash
python -m src.main run --input data/external_seed_samples.csv --config config --output outputs/external_seed_eval --dry-run --gold data/external_seed_labeled_requests.csv
```

결과:

| metric | value |
| --- | ---: |
| request_type_accuracy | 100.0% |
| target_team_accuracy | 100.0% |
| priority_accuracy | 100.0% |
| risk_level_accuracy | 100.0% |
| decision_accuracy | 100.0% |
| missing_fields_exact_match | 100.0% |
| automation_coverage | 25.0% |
| false_automation_rate | 0.0% |
| over_automation_rate | 0.0% |
| review_recall | 100.0% |
| review_precision | 100.0% |

해석:

```text
외부 seed 8건에서는 request classification, routing, priority, risk, decision이 모두 gold label과 일치했다.
403/Forbidden, dashboard filter, access permission 표현을 config keyword와 extraction rule에 추가해 generalization gap을 줄였다.
```

## Phase 6 Human-Eval Attempt

작성일: 2026-05-11

실행 명령:

```bash
python -m src.main run --input data/sample_requests.csv --config config --output outputs/human_eval_rule_only --dry-run --gold data/labeled_requests.csv
python -m src.main run --input data/sample_requests.csv --config config --output outputs/human_eval_llm_assist --dry-run --gold data/labeled_requests.csv --enable-llm-assist
```

결과:

```text
rule_only llm_used: 0
llm_assist llm_used: 0
llm_assist llm_errors: 25
error_type: OpenAI 401 invalid_api_key
QA assertion failures: 0
```

해석:

```text
이번 실행은 .env의 OPENAI_API_KEY가 API에서 invalid_api_key로 거절되어 실제 LLM assist 품질 비교를 수행하지 못했다.
오류 메시지는 key 값을 [REDACTED_OPENAI_API_KEY]로 마스킹한다.
유효한 키로 재실행하면 docs/human_eval_template.md 기준으로 rule-only 대비 ticket body와 reviewer assist 품질을 채점한다.
```
