# Human-Eval Result

작성일: 2026-05-11

## 입력 파일

```text
docs/opsflow-human-eval-2026-05-11.csv
```

평가 방식:

```text
1. 사람 평가자가 `docs/human_eval_form_2026-05-11.html`에서 10개 요청을 A/B 비교했다.
2. 각 variant는 factuality, actionability, completeness, privacy_safety, reviewer_effort 5개 기준으로 1/3/5점 채점했다.
3. 정량 점수 외에 각 요청별 메모를 남겼다.
```

## 정량 결과

| source | factuality | actionability | completeness | privacy_safety | reviewer_effort |
| --- | ---: | ---: | ---: | ---: | ---: |
| rule-only | 5.00 | 4.60 | 5.00 | 5.00 | 4.80 |
| llm-assist | 5.00 | 4.60 | 5.00 | 5.00 | 4.80 |

정량 점수만 보면 rule-only와 llm-assist의 차이는 거의 없습니다. 두 variant 모두 사실성, 완결성, 개인정보 안전성에서 높은 점수를 받았습니다.

다만 메모를 보면 점수보다 더 중요한 개선 지점이 드러납니다. 평가자는 대부분의 초안을 실무적으로 사용할 수 있다고 보았지만, 내부 필드명과 판단 근거가 평가자 또는 실제 업무 담당자에게 충분히 설명되지 않는다고 느꼈습니다.

## 평가자 전체 의견

요약:

```text
1. A(rule-only)는 요약이 원문을 그대로 반복하는 경우가 있어 다소 아쉽다.
2. B(llm-assist)는 요약과 질문이 더 자연스럽지만, 일부 표현은 오해를 만들 수 있다.
3. 누락 정보가 영문 필드명으로 표시되어 비개발자/비내부자에게 의미가 불명확할 수 있다.
4. 판단 근거의 `low_confidence` 같은 내부 용어는 왜 중요한지 설명이 부족하다.
5. 일부 required field는 실제 업무 맥락에서는 이미 추론 가능한데도 누락으로 잡혀 병목처럼 보인다.
```

## 주요 발견

### 1. 누락 정보 필드명이 평가자 친화적이지 않음

`dataset_or_metric`, `purpose`, `deadline`, `impact_scope`, `required_action` 같은 필드명이 그대로 노출됩니다.

평가자는 `impact_scope`가 “영향 범위”라는 뜻을 이해해야만 확인 질문을 제대로 해석할 수 있다고 지적했습니다. 현재 HTML에 설명이 추가되어 있더라도, 실제 티켓 초안 자체가 사람이 읽기 좋은 표현을 제공해야 합니다.

권장:

```text
dataset_or_metric -> 필요한 데이터/지표
purpose -> 사용 목적
deadline -> 마감일
impact_scope -> 영향 범위
required_action -> 원하는 조치
```

티켓 본문에서는 가능하면 다음처럼 표시합니다.

```text
## 누락 정보
- 필요한 데이터/지표 (`dataset_or_metric`)
- 사용 목적 (`purpose`)
- 마감일 (`deadline`)
```

### 2. 확인 질문은 더 자연스럽지만, 누락 정보와 연결이 약할 수 있음

LLM-assist variant는 확인 질문이 더 자연스럽습니다. 예를 들어 `REQ-020`은 “어떤 데이터셋 또는 지표, 사용 목적, 마감일”을 물어 rule-only보다 낫다는 평가를 받았습니다.

하지만 `REQ-002`, `REQ-003`처럼 누락 정보의 내부 필드명과 자연어 질문이 함께 표시될 때, 평가자는 두 표현이 같은 의미인지 확신하기 어려울 수 있다고 봤습니다.

권장:

```text
확인 질문 아래에 어떤 누락 정보를 채우기 위한 질문인지 함께 표시한다.
예: 이 질문은 "영향 범위"를 확인하기 위한 질문입니다.
```

### 3. 판단 근거가 내부 로그처럼 보임

`review_required: low_confidence`, `review_required: multiple_team_candidates`, `review_required: pii_detected` 같은 근거는 시스템 내부적으로는 유용하지만, 사람 평가자에게는 설명이 부족합니다.

특히 `REQ-028`에서 “왜 낮은 자신감인가?”라는 메모가 나왔습니다. 요청 자체는 버그로 명확해 보이는데 `low_confidence`가 표시되어 납득이 어렵다는 뜻입니다.

권장:

```text
low_confidence -> 분류 또는 담당 팀 확신도가 기준보다 낮음
multiple_team_candidates -> 담당 후보가 여러 팀으로 갈려 검토 필요
pii_detected -> 개인정보 또는 민감 식별자 후보가 포함됨
high_risk_action -> 권한/환불/삭제처럼 사람 승인 필요
required_missing_fields_present -> 필수 정보가 부족함
```

그리고 가능하면 실제 점수도 같이 표시합니다.

```text
담당 팀 확신도 0.67 < 기준 0.75
```

### 4. REQ-013의 질문은 업무 목적과 어긋나 보임

`REQ-013`은 “결제 취소 처리 가능 여부”를 묻는 요청인데, 초안은 `deadline`을 누락 정보로 질문합니다.

평가자는 마감 기한을 물어보는 것보다, 결제 취소 가능 여부를 판단하기 위한 정책/승인/권한 확인이 더 중요하지 않느냐고 지적했습니다.

권장:

```text
approval_request 또는 refund/cancel 계열은 deadline보다 policy/approval/scope 확인 질문을 우선한다.
예: 결제 취소 승인권자와 취소 가능 조건을 확인해 주세요.
```

### 5. REQ-017의 required_action 누락은 과도하게 보임

`REQ-017`은 “비밀번호 재설정 메일이 안 온다”는 고객지원 요청입니다. 평가자는 이 요청 자체에서 원하는 조치가 이미 “메일 미수신 문제 해결”로 충분히 추론된다고 봤습니다.

그런데 `required_action`이 누락으로 잡혀 추가 질문을 요구하므로, 오히려 병목처럼 보였습니다.

권장:

```text
customer_support에서 issue_detail이 명확하고 문제 해결 의도가 자연스럽게 드러나면 required_action을 inferred로 채운다.
```

예:

```text
required_action = "비밀번호 재설정 메일 미수신 원인 확인 및 안내"
```

### 6. 개인정보 review는 안전하지만 tiering 여지가 있음

`REQ-024`에서 평가자는 개인정보가 감지되어 사람 판단으로 넘긴 것은 이해했지만, 개인정보에도 위험 등급을 나눌 수 있으면 더 빠른 처리가 가능할 수 있다고 적었습니다.

권장:

```text
low privacy risk: 마스킹된 전화번호, 단순 연락 안내
medium/high privacy risk: 주문번호, 환불, 결제 취소, 주민번호, 토큰, 원문 추출 요청
```

다만 보안 영역이므로 기본값은 지금처럼 보수적으로 유지하고, v2 개선 항목으로 분리하는 것이 안전합니다.

## A/B 해석

### Rule-only 장점

```text
1. 사실을 덜 꾸미고 원문을 그대로 보존한다.
2. 과도한 추론이 적다.
3. 구조화된 누락 필드와 판단 근거가 안정적으로 나온다.
```

### Rule-only 한계

```text
1. 요약이 원문 반복에 가까운 경우가 있다.
2. 영문 필드명이 그대로 노출되어 비친절하다.
3. 확인 질문이 기계적으로 느껴질 수 있다.
```

### LLM-assist 장점

```text
1. 요약과 제목이 더 자연스럽다.
2. 일부 확인 질문은 사람이 바로 요청자에게 보낼 수 있을 정도로 자연스럽다.
3. 짧은 요청에서 필요한 정보를 더 잘 풀어 설명한다.
```

### LLM-assist 한계

```text
1. 자연어 질문과 내부 누락 필드 사이의 연결이 약하면 오해 소지가 있다.
2. 자연스러운 표현이 항상 더 정확한 것은 아니다.
3. 실제 업무 맥락과 어긋난 질문이 생성될 수 있다.
```

## 후속 구현 우선순위

1. 누락 필드 표시명을 한국어 라벨로 바꾼다.
2. 확인 질문 옆에 어떤 누락 필드를 채우기 위한 질문인지 표시한다.
3. 판단 근거를 사용자 친화적인 문장으로 번역한다.
4. `low_confidence`에는 실제 confidence와 기준값을 함께 표시한다.
5. `approval_request`의 refund/cancel 계열 질문 우선순위를 조정한다.
6. `customer_support`에서 조치 의도가 명확하면 `required_action`을 추론한다.
7. privacy risk tiering은 별도 v2 과제로 둔다.

## 후속 구현 완료

위 1~6번은 `docs/final_human_eval_improvement_2026-05-11.md` 기준으로 반영했다.

검증 산출물:

```text
outputs/final_improvement_check_2026-05-11
```

최종 확인 결과:

```text
pytest: 73 passed
ruff: all checks passed
QA assertion: 240 passed, 0 failed
request_type_accuracy: 100.0%
target_team_accuracy: 100.0%
priority_accuracy: 100.0%
risk_level_accuracy: 100.0%
decision_accuracy: 76.7%
false_automation_rate: 0.0%
review_recall: 100.0%
```

7번 privacy risk tiering은 보안 정책 결정이 필요한 영역이므로 v2 과제로 남겼다.
