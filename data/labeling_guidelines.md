# Labeling Guidelines

이 문서는 OpsFlow AI 평가 데이터셋의 정답 라벨을 일관되게 작성하기 위한 기준입니다. 라벨은 모델이나 rule engine의 예측 결과가 아니라, 사람이 원문 요청을 보고 판단한 gold label입니다.

## Core Principle

라벨링의 목표는 자동화율을 높이는 것이 아닙니다. 애매하거나 위험한 요청을 안전하게 review queue로 보내는지 평가할 수 있어야 합니다.

따라서 판단이 애매하면 보수적으로 라벨링합니다.

```text
reject > review_required > draft_only > ready_for_approval
```

위 순서가 decision priority입니다. 여러 decision에 동시에 해당하면 더 왼쪽 decision을 gold label로 사용합니다.

## Required Columns

`labeled_requests.csv`는 최소한 다음 컬럼을 가집니다.

| column | meaning |
| --- | --- |
| request_id | 입력 요청 ID |
| expected_request_type | 사람이 판단한 요청 유형 |
| expected_target_team | 사람이 판단한 1순위 담당 팀 |
| expected_priority | 사람이 판단한 우선순위 |
| expected_automation_decision | 사람이 판단한 최종 decision |
| expected_missing_fields | 누락된 required field 목록. `;`로 구분 |

선택적으로 다음 컬럼을 추가할 수 있습니다.

| column | meaning |
| --- | --- |
| expected_risk_level | 사람이 판단한 위험도 |
| expected_review_reason | review_required 또는 reject 사유 |
| notes | 라벨링 판단 근거 |
| source_type | `synthetic`, `edge_case`, `external_seed` 중 하나 |

## Request Type Labels

### `bug_report`

시스템 오류, 장애, 버그, 재현 문제, 500 에러, 결제 실패처럼 제품 또는 시스템 동작이 기대와 다르다는 요청입니다.

Required fields:

```text
symptom
affected_customer_or_user
impact_scope
```

예시:

```text
"A 고객사에서 결제 버튼 클릭 시 500 에러가 발생합니다."
```

### `data_request`

데이터 추출, 리포트, 쿼리, 대시보드, 지표 확인 요청입니다.

Required fields:

```text
dataset_or_metric
purpose
deadline
```

예시:

```text
"지난번 데이터 다시 주세요."
```

### `feature_request`

기능 추가, 개선, 제품 요구사항, 사용성 개선 요청입니다.

Required fields:

```text
user_need
expected_outcome
```

### `customer_support`

고객 문의, 고객 이슈 확인, 고객 대응 요청입니다. 기술 오류가 명확하면 `bug_report`를 우선합니다. 고객 대응 중심이면 `customer_support`로 둡니다.

Required fields:

```text
customer
issue_detail
required_action
```

### `approval_request`

승인, 결재, 권한 허가, 금액 또는 범위 승인처럼 사람의 승인 행위가 필요한 요청입니다.

Required fields:

```text
approval_target
scope_or_amount
deadline
```

### `internal_ops`

계정 생성, 권한 설정, 온보딩, 내부 운영 절차, 배포 일정 조율 같은 내부 운영 요청입니다.

Required fields:

```text
requested_action
target_user_or_system
```

### `other`

정의된 유형으로 설명하기 어렵거나 요청 의도가 너무 불명확한 경우입니다. `other`는 `ready_for_approval`이 될 수 없습니다.

## Target Team Labels

| team | criteria |
| --- | --- |
| engineering | 버그, 장애, API, 시스템 오류, 재현 조사 |
| data | 데이터 추출, 리포트, 대시보드, 쿼리 |
| product | 기능 요청, 요구사항, 우선순위 판단 |
| cs | 고객 문의 대응, 고객 커뮤니케이션 |
| ops | 계정, 권한, 승인, 내부 운영 |
| unassigned | 담당 팀 판단 불가 |

담당 팀이 둘 이상 가능하고 1순위를 정하기 어렵다면 `expected_target_team`은 가장 가능성 높은 팀으로 적되, `expected_automation_decision`은 `review_required`로 둡니다.

## Priority Labels

| priority | criteria |
| --- | --- |
| urgent | 운영 중단, 결제 불가, 전체 고객 영향, enterprise 고객의 심각한 장애 |
| high | 오늘 중 처리 필요, 고객사 영향, 긴급성이 있으나 전체 장애는 아님 |
| medium | 일반 업무 요청, 기본값 |
| low | 참고성 요청, 마감이 없거나 영향이 낮음 |

“급해요”만 있고 영향 범위나 문제 내용이 없으면 priority는 `high` 후보일 수 있지만 decision은 `review_required`로 둡니다.

## Automation Decision Labels

### `ready_for_approval`

다음 조건을 모두 만족합니다.

```text
required field가 모두 있음
담당 팀이 명확함
risk_level이 low
외부 시스템 등록 전 사람 승인만 남음
```

### `draft_only`

티켓 초안은 만들 수 있지만 일부 optional field 보완이나 문장 수정이 필요합니다. required field가 빠져 있으면 `draft_only`가 아니라 `review_required`입니다.

### `review_required`

다음 중 하나라도 해당하면 사용합니다.

```text
required field 누락
담당 팀이 모호함
request_type이 모호함
risk_level이 medium 또는 high
PII가 감지됨
과거 요청을 참조하지만 ID가 없음
```

### `reject`

다음 경우 사용합니다.

```text
지원하지 않는 요청
정책상 처리하면 안 되는 요청
보안 우회, 개인정보 원문 추출, 데이터 삭제처럼 초안 생성도 제한해야 하는 요청
```

## Missing Field Labels

`expected_missing_fields`는 누락된 required field만 기록합니다. optional field는 기록하지 않습니다.

여러 필드는 세미콜론으로 구분합니다.

```csv
impact_scope;reproduction_steps
```

누락 필드가 없으면 빈 문자열로 둡니다.

## Risk Level Labels

| risk_level | criteria |
| --- | --- |
| low | 초안 생성 또는 읽기 중심 요청 |
| medium | 고객사 영향, PII 감지, 긴급 요청, enterprise 고객 관련 요청 |
| high | 환불, 결제 취소, 권한 변경, 계정 삭제, 운영 데이터 수정, 보안 사고 |

high risk라고 해서 항상 `reject`는 아닙니다. 검토 후 처리 가능한 요청이면 `review_required`, 정책상 초안 생성도 부적절하면 `reject`입니다.

## Ambiguity Rules

1. 정보가 부족하면 자동 승인 쪽으로 해석하지 않습니다.
2. 여러 팀이 가능하면 `review_required`로 둡니다.
3. “지난번”, “어제 말한 것”처럼 외부 맥락이 필요한 요청은 required field 누락으로 봅니다.
4. 고객명만 있고 문제 내용이 없으면 `customer_support` 후보이지만 `review_required`입니다.
5. 자동 실행하면 실제 시스템에 부작용이 생길 수 있는 요청은 최소 `review_required`입니다.

## External Seed Data

공개 issue tracker나 공개 업무 요청 패턴에서 가져온 데이터는 원문을 그대로 노출하지 않습니다.

기록할 항목:

```text
source_url
collected_at
raw_text_pattern
notes
```

개인정보, 토큰, 내부 URL, 실명, 이메일, 전화번호가 포함된 경우 익명화하거나 패턴화합니다.
