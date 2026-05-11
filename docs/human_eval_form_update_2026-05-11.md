# Human Eval Form Update

작성일: 2026-05-11

## 목적

agent-assisted eval에서 나온 후속 과제를 먼저 해결하고, 실제 사람이 편하게 평가할 수 있는 정적 HTML 도구를 추가했습니다.

## 반영한 후속 과제

### 1. Data request 확인 질문 누락 보완

`config/ticket_templates.yml`의 `data_request`, `feature_request` 템플릿에 `suggested_next_question` 섹션을 추가했습니다.

예시:

```text
REQ-002
## 확인 질문
요청 처리를 위해 다음 정보를 알려 주세요: dataset_or_metric, purpose, deadline
```

LLM assist가 켜진 경우에는 `suggested_clarification`을 티켓 본문에 우선 반영합니다.

### 2. Person-like masking 활성화

`config/privacy_rules.yml`의 person rule을 활성화했습니다.

```text
김대리님 -> [PERSON]
고객님 -> 유지
```

외부 공유용 masked export에서 `김대리`, 전화번호, 주문번호가 노출되지 않는지 확인했습니다.

### 3. 사람 평가용 HTML 추가

추가 파일:

```text
docs/human_eval_form_2026-05-11.html
```

기능:

```text
1. 10개 표본 A/B 비교
2. 프로젝트를 모르는 평가자도 이해할 수 있는 평가 목적 설명
3. A/B가 무엇인지, 좋은 초안이 무엇인지, 진행 순서 안내
4. 1/3/5 점수 기준을 "다시 작성 / 일부 수정 / 바로 사용"으로 설명
5. 추출 필드, 누락 정보, 판단 근거가 무엇을 의미하는지 초안 안에서 설명
6. 티켓 본문을 섹션별로 렌더링해 평가자가 각 항목을 따로 이해할 수 있게 표시
7. factuality, actionability, completeness, privacy_safety, reviewer_effort 채점
8. 각 기준별 짧은 설명 표시
9. variant별 검토 시간 입력
10. 메모 입력
11. localStorage 자동 저장
12. CSV / JSON 내보내기
13. CSV 클립보드 복사
```

## 평가자 사용 방법

브라우저에서 아래 파일을 엽니다.

```text
docs/human_eval_form_2026-05-11.html
```

진행 절차:

```text
1. 왼쪽 목록에서 REQ-002부터 순서대로 선택합니다.
2. 원문 요청을 확인합니다.
3. Variant A와 Variant B를 비교합니다.
4. 각 variant에 대해 5개 기준을 1, 3, 5점으로 채점합니다.
5. 가능하면 검토 시간(초)을 입력합니다.
6. 필요한 메모를 남깁니다.
7. 모든 표본을 완료한 뒤 CSV 내보내기를 누릅니다.
```

평가자에게는 Variant A/B의 출처를 알려주지 않습니다. 내보낸 CSV에는 분석을 위해 source 컬럼이 포함됩니다.

## 최신 평가 산출물 생성 명령

```bash
python -m src.main run --input data/sample_requests.csv --config config --output outputs/human_eval_form_rule_only_2026-05-11 --dry-run --gold data/labeled_requests.csv
python -m src.main run --input data/sample_requests.csv --config config --output outputs/human_eval_form_llm_assist_2026-05-11 --dry-run --gold data/labeled_requests.csv --enable-llm-assist --prefer-dotenv
```

## 검증 결과

```text
pytest: 70 passed
ruff: All checks passed
sample CLI: 30 requests processed
QA assertions: 240 passed, 0 failed
HTML inline script syntax: checked 1 inline script
```

최신 LLM assist 실행:

```text
llm_used: 25
llm_assist_not_needed: 5
llm_errors: 0
```

masked export 확인:

```text
masked_normalized_requests.json: 김대리 / 010-1234-5678 / ORD-12345 미검출
masked_review_queue.csv: 김대리 / 010-1234-5678 / ORD-12345 미검출
```
