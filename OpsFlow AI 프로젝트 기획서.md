# OpsFlow AI 프로젝트 기획서

## 프로젝트명

**OpsFlow AI**

## 부제

**비정형 업무 요청을 표준 티켓과 검토 큐로 변환하는 AI 업무 자동화 시스템**

---

# 1. 프로젝트 한 줄 정의

> **OpsFlow AI는 Slack, Form, CSV 등으로 들어오는 비정형 업무 요청을 표준 업무 처리 스키마로 정규화하고, 명확한 요청은 승인 가능한 티켓 초안으로 변환하며, 애매하거나 위험한 요청은 사람 검토 큐로 분리하는 FDE형 업무 자동화 프로젝트이다.**

이 프로젝트의 핵심은 “AI가 모든 업무를 대신 처리한다”가 아니다.

핵심은 다음 흐름이다.

```text
비정형 요청
→ 표준 스키마 정규화
→ 규칙 기반 판단
→ LLM 보조 판단
→ 검토 필요 여부 결정
→ 티켓 초안 생성
→ 사람 승인
→ 업무 시스템 등록
→ 로그와 평가 데이터 축적
```

OpenAI의 Structured Outputs는 모델 응답이 개발자가 정의한 JSON Schema를 따르도록 하는 기능이므로, 비정형 요청을 `request_type`, `target_team`, `priority`, `missing_fields`, `needs_review` 같은 표준 필드로 변환하는 데 적합하다. 다만 스키마 준수와 업무 판단 정확도는 별개의 문제이므로, OpsFlow AI는 구조화된 출력 이후에도 규칙 검증과 사람 검토를 둔다. ([OpenAI 개발자][1])

---

# 2. 프로젝트 배경

현업에서 업무 요청은 보통 정리된 티켓으로 바로 들어오지 않는다.

대부분은 다음처럼 비정형 문장으로 들어온다.

```text
“A 고객사 결제 오류 또 발생했습니다. 급해요.”
“지난번에 뽑았던 데이터 다시 받을 수 있을까요?”
“이번 주 리포트 업데이트 부탁드립니다.”
“신규 기능 요청인데 우선순위 높게 봐야 할 것 같아요.”
“어제 말한 건 GitHub에 올려주세요.”
```

문제는 요청을 받은 사람이 매번 다음을 판단해야 한다는 점이다.

```text
이 요청은 어떤 유형인가?
어느 팀이 처리해야 하는가?
우선순위는 어느 정도인가?
필수 정보가 빠져 있지는 않은가?
지금 바로 티켓으로 만들어도 되는가?
사람이 먼저 확인해야 하는가?
```

따라서 이 프로젝트는 단순히 “요청을 요약하는 AI”가 아니라, **요청을 업무 시스템에 넣을 수 있는 표준 구조로 바꾸는 자동화 시스템**이다.

---

# 3. 문제 재정의

## 겉문제

> “업무 요청을 AI가 자동으로 처리해주면 좋겠다.”

## 진짜 병목

> **비정형 요청을 표준 업무 처리 단위로 정규화하는 과정이 반복적으로 사람에게 의존한다.**

즉, 핵심 병목은 “AI 답변 생성”이 아니라 다음 과정이다.

```text
요청 읽기
→ 요청 유형 판단
→ 담당 팀 판단
→ 우선순위 판단
→ 누락 정보 확인
→ 티켓 제목/본문 작성
→ 업무툴에 등록
```

OpsFlow AI는 이 반복 병목을 줄이되, 모든 판단을 자동 확정하지 않는다.

```text
명확한 요청
→ 자동 정규화 + 티켓 초안 생성

애매한 요청
→ review queue로 분리

위험한 요청
→ 자동 실행 차단
```

---

# 4. 프로젝트 최상위 원칙

이 프로젝트의 최상위 원칙은 다음 문장으로 정리한다.

> **현업 자동화는 AI를 많이 쓰는 문제가 아니라, 반복되는 요청 분류·라우팅·티켓 생성 병목을 가장 작고 안정적인 흐름으로 줄이고, 사람이 다시 실행·검토할 수 있게 만드는 문제다.**

이 원칙에 따라 OpsFlow AI는 다음 기준을 따른다.

| 원칙                | OpsFlow AI에서의 적용                            |
| ----------------- | ------------------------------------------- |
| 문제 재정의            | 챗봇이 아니라 비정형 요청 정규화 시스템으로 설계                 |
| 출력 우선             | 최종 티켓/검토 큐 스키마를 먼저 고정                       |
| 범위 절단             | 1차 목표는 티켓 초안과 review queue 생성               |
| Rule-first        | 반복 가능하고 기준이 명확한 판단은 규칙 기반 처리                |
| LLM 최소 사용         | LLM은 모호한 의미 판단과 초안 작성에만 사용                  |
| Human-in-the-loop | 불확실하거나 위험한 요청은 사람 검토로 분리                    |
| 재실행 가능성           | CLI + config 기반으로 다음 주에도 다시 실행 가능           |
| 설명 가능성            | 어떤 규칙과 판단으로 결과가 나왔는지 trace 저장               |
| 평가 가능성            | 자동화율보다 false automation, review recall, human edit rate 측정 |

OpenAI의 Function Calling 문서는 모델이 도구 호출을 제안하고, 실제 도구 실행은 애플리케이션 쪽 코드에서 수행한 뒤 결과를 다시 모델에 전달하는 흐름을 설명한다. OpsFlow AI도 이 원칙을 따른다. 즉, 모델이 직접 외부 시스템을 마음대로 조작하는 것이 아니라, 서버 코드가 승인·정책·도구 실행 경계를 통제한다. ([OpenAI 개발자][2])

---

# 5. 프로젝트 목표

## 5.1 1차 목표

> **비정형 업무 요청을 표준 스키마로 변환하고, 승인 가능한 티켓 초안으로 만들 수 있는 요청과 사람 검토가 필요한 요청을 분리한다.**

1차 MVP는 “완전 자동화”가 아니라 다음을 증명하는 것이다.

```text
요청을 읽을 수 있다
→ 표준 스키마로 바꿀 수 있다
→ 규칙 기반으로 1차 판단할 수 있다
→ 애매한 요청을 분리할 수 있다
→ 티켓 초안을 만들 수 있다
→ 사람이 검토할 수 있는 큐를 만들 수 있다
→ 결과를 평가할 수 있다
```

## 5.2 포트폴리오 목표

이 프로젝트를 통해 보여주고 싶은 역량은 다음이다.

```text
1. 현업 문제를 기술 문제로 재정의하는 능력
2. AI를 어디에 쓰고 어디에 쓰지 않을지 나누는 능력
3. Rule-based, LLM-assisted, Human-review 경계를 설계하는 능력
4. 외부 업무툴 연동 가능성을 고려한 시스템 설계 능력
5. 자동화 결과를 검증 가능한 지표로 평가하는 능력
```

---

# 6. 사용자와 사용 시나리오

## 6.1 주요 사용자

| 사용자    | 니즈                                       |
| ------ | ---------------------------------------- |
| 운영 담당자 | 반복 요청을 빠르게 분류하고 티켓화하고 싶음                 |
| CS 담당자 | 고객 이슈를 적절한 팀으로 넘기고 싶음                    |
| PM/PO  | 기능 요청과 버그 요청을 분리하고 싶음                    |
| 데이터팀   | 불명확한 데이터 요청을 바로 받지 않고 필요한 정보를 먼저 확인하고 싶음 |
| 엔지니어링팀 | 재현 정보가 부족한 버그 티켓이 무분별하게 생성되는 것을 줄이고 싶음   |

## 6.2 대표 시나리오

### 시나리오 A: 명확한 버그 요청

```text
입력:
“A 고객사에서 결제 버튼 클릭 시 500 에러가 발생합니다. 전체 결제 시도 중 30% 정도 실패하고 있습니다.”

처리:
- request_type: bug_report
- target_team: engineering
- priority: urgent
- missing_fields: []
- automation_decision: ready_for_approval 또는 draft_only
```

### 시나리오 B: 정보가 부족한 데이터 요청

```text
입력:
“지난번 데이터 다시 주세요.”

처리:
- request_type: data_request
- target_team: data
- priority: medium
- missing_fields: ["dataset_or_metric", "deadline", "purpose"]
- automation_decision: review_required
- clarification_question: “어떤 데이터 또는 리포트를 의미하나요?”
```

### 시나리오 C: 긴급하지만 근거가 부족한 요청

```text
입력:
“A 고객사 건 급해요. 바로 처리해주세요.”

처리:
- request_type: customer_support 또는 other
- target_team: cs 후보
- priority: high 후보
- missing_fields: ["issue_detail", "impact", "required_action"]
- automation_decision: review_required
```

---

# 7. MVP 범위

## 7.1 MVP v1 범위

MVP v1은 CLI 기반으로 만든다.

```text
입력:
- CSV 또는 JSONL 업무 요청 데이터
- Slack export를 흉내낸 정적 JSON 입력

처리:
- 요청 정규화
- 규칙 기반 요청 유형 분류
- 담당 팀 추천
- confidence score 계산
- risk level 계산
- 필수 정보 누락 검사
- 우선순위 판단
- LLM 보조 판단
- 티켓 초안 생성
- review queue 생성
- execution log 생성
- eval report 생성

출력:
- normalized_requests.json
- ticket_drafts.json
- review_queue.csv
- execution_log.json
- evaluation_report.md
- qa_assertion_report.md
```

MVP v1에서 말하는 `Slack-style`은 실시간 Slack 봇이나 Slack API 연동이 아니다.

```text
Slack-style 입력
→ Slack 메시지 export와 유사한 정적 JSON 샘플
→ channel, user, thread_ts, raw_text 같은 필드를 가진 테스트 입력
→ CLI에서 파일로 읽어 재실행 가능한 데이터
```

즉, MVP v1은 입력 포맷만 Slack 메시지에 가깝게 흉내 낸다. 실제 Slack 이벤트 수신, OAuth, bot token, slash command, workflow step 연동은 MVP v3 이후로 미룬다.

### 7.1.1 MVP 성공 기준

MVP v1은 다음 조건을 만족하면 성공으로 본다.

```text
1. 동일 입력과 동일 config에서 동일한 결과가 재현된다.
2. 각 요청에 request_type_confidence, target_team_confidence, risk_level이 기록된다.
3. 모호하거나 위험한 요청은 review_required로 분리된다.
4. ready_for_approval 요청도 외부 시스템에 실제 등록하지 않고 티켓 초안만 만든다.
5. execution_log.json으로 어떤 rule version과 scoring rule이 적용됐는지 추적할 수 있다.
6. evaluation_report.md에서 false automation rate, review recall, threshold별 trade-off를 확인할 수 있다.
7. qa_assertion_report.md에서 schema/policy 충돌을 확인할 수 있다.
```

## 7.2 MVP v1에서 하지 않을 것

```text
1. 완전 자율 에이전트
2. 복잡한 멀티 에이전트 구조
3. 전사 지식베이스 RAG
4. 실시간 Slack 봇 또는 Slack API 연동
5. 복잡한 관리자 대시보드
6. 승인 없이 외부 시스템에 실제 티켓 생성
```

## 7.3 확장 범위

```text
MVP v2:
- Streamlit review UI
- 사람이 approve/edit/reject 가능
- GitHub Issue dry-run
- 승인 후 실제 GitHub Issue 생성

MVP v3:
- 실시간 Slack 입력 연동
- Jira 또는 Notion Task 연동
- 팀별 자동화율 대시보드
- 반복 요청 패턴 분석
```

GitHub Issues REST API는 이슈, 담당자, 댓글, 라벨, 마일스톤을 보고 관리하는 엔드포인트를 제공하므로, OpsFlow AI의 “승인된 요청만 GitHub Issue로 생성”하는 확장 기능에 적합하다. ([GitHub Docs][3]) Slack의 custom workflow step은 Workflow Builder에서 사용할 수 있는 앱 함수로 설명되므로, MVP 이후 Slack 입력을 workflow step 형태로 감싸는 확장도 가능하다. ([Slack 개발자 문서][4])

---

# 8. 핵심 기능 요구사항

## FR-1. 요청 입력

사용자는 CSV 또는 JSONL 형태로 업무 요청을 입력한다.

예시 CSV:

```csv
request_id,requester,channel,raw_text,created_at
REQ-001,kim,slack,"A 고객사 결제 오류가 발생했습니다",2026-05-11
REQ-002,lee,form,"지난번 데이터 다시 주세요",2026-05-11
```

Slack-style JSONL 예시:

```json
{
  "request_id": "REQ-003",
  "channel": "slack",
  "channel_id": "C0123",
  "user_id": "U0456",
  "thread_ts": "1789000000.000100",
  "raw_text": "A 고객사 결제 오류 또 발생했습니다. 급해요.",
  "created_at": "2026-05-11T09:00:00+09:00"
}
```

이 포맷은 Slack API 응답을 그대로 저장하는 것이 아니라, Slack 메시지에서 필요한 필드만 흉내 낸 정적 테스트 입력이다.

---

## FR-2. 표준 스키마 정규화

모든 요청은 다음 표준 스키마로 변환된다.

```json
{
  "schema_version": "normalized_request.v1",
  "rule_config_version": "2026-05-11",
  "scoring_policy_version": "scoring.2026-05-11",
  "risk_policy_version": "risk.2026-05-11",
  "privacy_policy_version": "privacy_rules.2026-05-11",
  "request_id": "REQ-001",
  "raw_text": "A 고객사 결제 오류가 발생했습니다",
  "request_type": "bug_report",
  "request_type_confidence": 0.88,
  "request_type_candidates": [
    {
      "type": "bug_report",
      "confidence": 0.88,
      "matched_signals": ["오류", "결제"]
    },
    {
      "type": "customer_support",
      "confidence": 0.64,
      "matched_signals": ["고객사"]
    }
  ],
  "summary": "A 고객사 결제 오류 확인 요청",
  "required_action": "결제 오류 원인 확인 및 재현",
  "target_team": "engineering",
  "target_team_confidence": 0.86,
  "target_team_candidates": [
    {
      "team": "engineering",
      "confidence": 0.86,
      "reason": "bug_report default_team"
    },
    {
      "team": "cs",
      "confidence": 0.58,
      "reason": "customer keyword matched"
    }
  ],
  "priority": "high",
  "risk_level": "medium",
  "pii_detected": false,
  "masked_text": "A 고객사 결제 오류가 발생했습니다",
  "extracted_fields": {
    "symptom": "결제 오류",
    "affected_customer_or_user": "A 고객사",
    "impact_scope": null,
    "reproduction_steps": null
  },
  "missing_fields": ["impact_scope"],
  "needs_review": true,
  "review_reason": "고객 영향 범위가 명확하지 않음",
  "decision_reasons": [
    "impact_scope 필드 누락",
    "risk_level이 medium이므로 자동 승인 불가"
  ],
  "llm_used": true,
  "model_name": "<llm_model_id>",
  "suggested_ticket_title": "[Bug] A 고객사 결제 오류 확인",
  "suggested_ticket_body": "원문 요청, 판단 근거, 누락 정보 포함",
  "automation_decision": "review_required"
}
```

Structured Outputs를 사용하면 모델 응답을 사전에 정의한 JSON Schema에 맞게 받을 수 있으므로, `request_type`, `priority`, `automation_decision` 같은 enum 필드를 안정적으로 관리할 수 있다. 이 프로젝트에서는 해당 기능을 “업무 판단 자동화” 자체가 아니라 “판단 결과를 일관된 구조로 받는 장치”로 사용한다. ([OpenAI 개발자][1])

---

## FR-3. Rule-first 요청 분류

반복 가능하고 기준이 명확한 판단은 LLM보다 규칙 기반으로 처리한다.

예시 규칙:

```yaml
request_type_rules:
  bug_report:
    keywords: ["오류", "버그", "장애", "재현", "에러", "안됨"]
    required_fields:
      - symptom
      - affected_customer_or_user
      - impact
    default_team: "engineering"

  data_request:
    keywords: ["데이터", "추출", "리포트", "쿼리", "대시보드"]
    required_fields:
      - dataset_or_metric
      - deadline
      - purpose
    default_team: "data"

  feature_request:
    keywords: ["기능", "개선", "요청", "추가", "지원"]
    required_fields:
      - user_need
      - expected_outcome
    default_team: "product"
```

이 설계의 이유는 명확하다.

```text
업무 기준은 조직마다 다르다
→ 코드에 하드코딩하면 유지보수가 어렵다
→ config로 분리하면 현업 기준 변경을 빠르게 반영할 수 있다
```

### Confidence score 산출

`request_type_confidence`와 `target_team_confidence`는 LLM이 스스로 보고한 확신도를 사용하지 않는다. LLM의 confidence는 calibration이 어렵기 때문에, OpsFlow AI에서는 규칙 엔진이 관측 가능한 신호를 기준으로 점수를 계산한다.

confidence는 확정된 `request_type` 하나에 대해 한 번만 계산하지 않는다. 각 후보 request type마다 독립적으로 계산한 뒤 가장 높은 후보를 top-level `request_type`으로 올린다.

계산 순서는 다음과 같다.

```text
1. keyword와 metadata만으로 request_type 후보를 만든다.
2. 후보별 pre_score를 계산하고 상위 N개 후보만 남긴다.
3. rule 기반 field extractor가 날짜, 고객명, 오류 신호, 수치, 요청 액션을 먼저 추출한다.
4. 필요한 경우에만 PII masking 이후 LLM assist가 부족한 extracted_fields를 보조 추출한다.
5. 후보 request_type별 required_fields / optional_fields 기준으로 required_field_score를 계산한다.
6. 최종 request_type_confidence를 후보별로 다시 계산한다.
7. top candidate를 top-level request_type과 request_type_confidence에 mirror한다.
```

따라서 `required_field_score`가 `request_type`을 알아야 계산된다는 문제는 “후보 type별 점수 계산”으로 처리한다. 예를 들어 같은 요청에 대해 `bug_report`, `customer_support` 후보가 있으면 두 후보 각각의 required field set으로 점수를 따로 계산한다.

```text
request_type_confidence
= clamp(
    0.50 * keyword_score
  + 0.35 * required_field_score
  + 0.15 * metadata_score
  - conflict_penalty,
  0,
  1
)
```

각 항목의 의미는 다음과 같다.

| 항목 | 계산 방식 |
| --- | --- |
| keyword_score | 해당 request_type의 active keyword group에서 `matched_weight_sum / total_weight_sum`으로 계산 |
| required_field_score | 해당 request_type의 required_fields 중 추출된 필드 비율 |
| metadata_score | request_types.yml 또는 priority_rules.yml에 정의된 metadata_conditions 매칭 비율 |
| conflict_penalty | 후보 request_type이 2개 이상이고 점수 차가 작을 때 감점 |

예시:

```text
bug_report active keywords: 오류(0.4), 결제(0.3), 재현(0.3)
active keyword total_weight_sum = 1.0
입력 매칭: 오류, 결제
keyword_score = (0.4 + 0.3) / 1.0 = 0.70

required_fields: symptom, affected_customer_or_user, impact_scope
추출 필드: symptom, affected_customer_or_user
required_field_score = 2 / 3 = 0.67

metadata_score = 0.8
conflict_penalty = 0.05

request_type_confidence
= 0.50*0.70 + 0.35*0.67 + 0.15*0.80 - 0.05
= 0.65
```

`target_team_confidence`는 다음 기준으로 계산한다.

```text
target_team_confidence
= clamp(
    0.55 * request_type_confidence
  + 0.30 * team_mapping_score
  + 0.15 * team_keyword_score
  - multi_team_penalty,
  0,
  1
)
```

`target_team_candidates`는 항상 배열로 저장한다. 상위 후보가 2개 이상이고 점수 차가 `0.15` 미만이면 단일 팀으로 확정하지 않고 `review_required`로 보낸다.

`team_mapping_score`와 `team_keyword_score`는 `team_mapping.yml`을 기준으로 계산한다.

| 항목 | 계산 방식 |
| --- | --- |
| team_mapping_score | request_type의 default_team과 후보 team이 같으면 1.0, secondary team이면 0.5, 매핑이 없으면 0 |
| team_keyword_score | 후보 team의 keyword set에서 `matched_weight_sum / team_keyword_total_weight`로 계산 |

fallback 규칙:

```text
모든 request_type 후보 confidence < 0.50
→ request_type = other
→ automation_decision = review_required

internal_ops는 조직 내부 운영 요청을 의미한다.
예: 계정 생성, 권한 요청, 온보딩, 정기 리포트 운영, 배포 일정 조율

other는 정의된 request_type으로 설명하기 어려운 요청이다.
other는 자동 승인 후보가 될 수 없고 항상 review_required 또는 reject로 간다.
```

---

## FR-4. 필수 정보 누락 검사

요청 유형별로 반드시 필요한 필드를 검사한다.

예시:

| 요청 유형            | 필수 정보                   |
| ---------------- | ----------------------- |
| bug_report       | 증상, 영향 고객, 재현 조건, 영향 범위 |
| data_request     | 필요한 데이터/지표, 목적, 마감일     |
| feature_request  | 사용자 니즈, 기대 결과, 우선순위 근거  |
| approval_request | 승인 대상, 금액/범위, 마감일       |
| customer_support | 고객명, 문제 상황, 원하는 조치      |

필수 정보가 빠진 요청은 바로 티켓으로 생성하지 않고 review queue로 보낸다.

누락 검사는 원문에서 바로 `missing_fields`를 찍는 방식이 아니라, 먼저 `extracted_fields`를 만든 뒤 계산한다.

```json
{
  "request_type": "bug_report",
  "extracted_fields": {
    "symptom": "결제 버튼 클릭 시 500 에러",
    "affected_customer_or_user": "A 고객사",
    "reproduction_steps": null,
    "impact_scope": "전체 결제 시도 중 30%"
  },
  "required_fields": [
    "symptom",
    "affected_customer_or_user",
    "reproduction_steps",
    "impact_scope"
  ],
  "missing_fields": ["reproduction_steps"]
}
```

top-level의 `request_type_confidence`와 `target_team_confidence`는 각각 `request_type_candidates[0].confidence`, `target_team_candidates[0].confidence`를 mirror한 값이다. decision layer는 top-level 값을 읽고, review 화면은 candidates 배열을 함께 보여준다.

이 구조를 쓰면 왜 누락으로 판단했는지 설명할 수 있고, 이후 사람이 수정한 필드를 평가 데이터로 다시 축적할 수 있다.

---

## FR-5. LLM 보조 판단

LLM은 다음 작업에만 사용한다.

```text
1. 요청 요약
2. 모호한 요청의 의도 후보 제안
3. 티켓 제목/본문 초안 작성
4. 누락 정보를 자연어 질문으로 변환
5. review 담당자가 볼 판단 근거 생성
```

LLM에게 맡기지 않는 작업은 다음이다.

```text
1. 최종 자동 실행 여부 결정
2. 승인 없이 외부 시스템 등록
3. 우선순위 정책 임의 변경
4. 담당 팀 최종 확정
5. 권한이 필요한 업무 실행
```

OpenAI Agents SDK 문서는 서버가 orchestration, tool execution, state, approvals를 소유하려는 경우 SDK 방식이 적합하다고 설명한다. OpsFlow AI도 이 방향을 따른다. 즉, 모델은 보조 판단과 도구 호출 제안을 할 수 있지만, 상태 관리·승인·실제 실행은 애플리케이션 서버가 통제한다. ([OpenAI 개발자][5])

---

## FR-6. 자동화 결정

각 요청은 최종적으로 네 가지 상태 중 하나를 가진다.

```text
ready_for_approval
→ 규칙상 명확하고 필수 정보가 충분하며 위험도가 낮아 승인만 남은 티켓 초안

draft_only
→ 티켓 초안은 만들 수 있지만 일부 필드 수정이나 확인이 필요

review_required
→ 정보 부족, 판단 불확실, 담당 팀 애매함

reject
→ 자동화 대상이 아니거나 정책상 처리 불가
```

예시 정책:

```yaml
automation_policy:
  ready_for_approval:
    match: ALL
    conditions:
      - request_type_confidence >= 0.85
      - target_team_confidence >= 0.85
      - missing_fields == []
      - risk_level == "low"

  draft_only:
    match: ALL
    conditions:
      - request_type_confidence >= 0.75
      - target_team_confidence >= 0.75
      - risk_level in ["low", "medium"]
      - missing_fields only contains optional_fields

  review_required:
    match: ANY
    conditions:
      - required_missing_fields_present
      - request_type_confidence < 0.85
      - top_two_team_confidence_gap < 0.15
      - risk_level in ["medium", "high"]
```

MVP v1에서는 `ready_for_approval`도 외부 시스템에 실제 등록하지 않는다. 이 상태는 “자동 생성”이 아니라 “사람이 승인하면 등록 가능한 초안”을 뜻한다. 실제 GitHub Issue 또는 Jira Ticket 생성은 v2 이후 `approval_status == approved`일 때만 수행한다.

decision layer는 다음 우선순위로 cascade 평가한다.

```text
reject
→ review_required
→ draft_only
→ ready_for_approval
```

위 단계에서 한 번 매칭되면 아래 단계는 평가하지 않는다. 즉, optional field만 비어 있으면 `draft_only`가 될 수 있지만, required field 누락, 복수 팀 후보, high risk action이 있으면 `review_required`가 먼저 적용된다.

### Risk level 산출

`risk_level`도 LLM의 주관적 판단을 그대로 쓰지 않는다. 요청 유형, 키워드, 메타데이터, 실행 대상의 부작용 여부를 기준으로 config에서 계산한다.

```yaml
risk_rules:
  high:
    request_types:
      - approval_request
    keywords:
      - 환불
      - 결제 취소
      - 권한 부여
      - 계정 삭제
      - 운영 데이터 수정
      - 보안 사고
    side_effects:
      - external_write
      - permission_change
      - payment_or_refund

  medium:
    keywords:
      - 고객사
      - 장애
      - 개인정보
      - 긴급
    conditions:
      - customer_tier == "enterprise"
      - contains_possible_pii == true

  low:
    request_types:
      - bug_report
      - feature_request
      - data_request
    side_effects:
      - draft_only
      - read_only
```

여러 risk rule이 동시에 매칭되면 가장 높은 risk를 사용한다.

```text
high rule 하나라도 매칭
→ risk_level = high

high는 없고 medium rule 매칭
→ risk_level = medium

high와 medium 모두 없음
→ risk_level = low
```

LLM은 “이 문장에 환불, 권한, 개인정보 같은 위험 신호가 있는지”를 보조적으로 추출할 수 있지만, 최종 `risk_level`은 `risk_rules.yml`과 decision layer가 결정한다.

---

## FR-7. Review queue 생성

자동 확정이 어려운 요청은 review queue로 분리한다.

예시 출력:

| request_id | 원문 요청          | 1순위 판단                  | 후보 팀              | review 사유       | 추천 질문                        | 담당자 액션 |
| ---------- | -------------- | ------------------------ | ---------------- | --------------- | ---------------------------- | ------ |
| REQ-002    | 지난번 데이터 다시 주세요 | data_request / data      | data             | 어떤 데이터인지 불명확    | 어떤 리포트 또는 지표를 의미하나요?         | 정보 요청  |
| REQ-005    | A 고객사 건 급해요    | customer_support / cs    | cs, engineering  | 문제 내용과 영향 범위 누락 | 어떤 문제가 발생했고 영향 범위는 어느 정도인가요? | 보류     |
| REQ-009    | 결제 안 됩니다       | bug_report / engineering | engineering, cs  | 재현 조건과 영향 범위 부족 | 특정 고객 문제인가요, 전체 고객 문제인가요?    | 검토     |

review queue는 단순히 “AI가 실패한 요청 목록”이 아니다. 사람이 빠르게 판단할 수 있도록 후보 유형, 후보 팀, 누락 필드, 추천 질문, 판단 근거를 함께 제공한다. 따라서 평가에서는 review queue에 들어간 건수뿐 아니라, reviewer가 한 건을 처리하는 데 걸리는 시간도 측정한다.

OpenAI의 guardrails and human review 문서는 guardrails가 자동 검증을 수행하고, human review는 민감한 액션 전에 실행을 멈춰 사람이 승인·거절할 수 있게 한다고 설명한다. OpsFlow AI의 review queue는 이 원칙을 업무 요청 자동화에 적용한 것이다. ([OpenAI 개발자][6])

---

## FR-8. 티켓 초안 생성

승인 가능 또는 검토 대상 요청에 대해 티켓 초안을 만든다.

예시:

```markdown
## Summary
A 고객사 결제 오류 확인 요청

## Original Request
“A 고객사에서 결제 버튼 클릭 시 500 에러가 발생합니다.”

## Suggested Type
bug_report

## Target Team
engineering

## Priority
high

## Missing Information
- 영향 범위
- 재현 조건
- 발생 시각

## Suggested Next Question
전체 고객 영향인지, 특정 고객사에만 발생하는지 확인이 필요합니다.

## Trace
- keyword_match: "결제", "오류"
- rule_id: bug_report.keyword.v1
- review_reason: impact_scope_missing
```

---

## FR-9. 판단 trace 저장

각 요청마다 판단 경로를 저장한다.

```json
{
  "request_id": "REQ-002",
  "original_text": "지난번 데이터 다시 주세요",
  "schema_version": "normalized_request.v1",
  "rule_config_version": "2026-05-11",
  "scoring_policy_version": "scoring.2026-05-11",
  "risk_policy_version": "risk.2026-05-11",
  "privacy_policy_version": "privacy_rules.2026-05-11",
  "rule_matches": [
    {
      "rule_id": "data_request.keyword.v1",
      "matched_keyword": "데이터",
      "suggested_type": "data_request",
      "weight": 0.4
    }
  ],
  "candidate_scores": {
    "request_type_candidates": [
      {
        "type": "data_request",
        "confidence": 0.62
      },
      {
        "type": "internal_ops",
        "confidence": 0.41
      }
    ],
    "target_team_candidates": [
      {
        "team": "data",
        "confidence": 0.68
      }
    ]
  },
  "risk_eval": {
    "risk_level": "low",
    "matched_rules": []
  },
  "evaluated_decisions": [
    {
      "step": "reject",
      "matched": false
    },
    {
      "step": "review_required",
      "matched": true,
      "trigger": "required_missing_fields_present"
    }
  ],
  "llm_assist": {
    "used": true,
    "reason": "요청 대상 데이터가 불명확함",
    "suggested_clarification": "어떤 데이터 또는 리포트를 의미하나요?"
  },
  "final_decision": {
    "automation_decision": "review_required",
    "decision_reasons": [
      "dataset_or_metric 필드 누락",
      "request_type_confidence가 ready_for_approval 기준 미달"
    ],
    "review_reason": "dataset_or_metric 필드 누락"
  }
}
```

trace에는 rule id만 남기지 않고, rule config version, scoring policy version, risk policy version, privacy policy version, cascade 평가 경로를 함께 저장한다. 같은 요청이라도 config가 바뀌면 결과가 달라질 수 있기 때문에, 6개월 뒤에도 “그 당시 어떤 기준으로 분류됐는지”를 재현할 수 있어야 한다.

OpenAI Agents SDK의 tracing 문서는 LLM 생성, tool call, handoff, guardrail, custom event 같은 실행 이벤트를 기록해 개발과 운영에서 디버깅·모니터링할 수 있다고 설명한다. OpsFlow AI는 포트폴리오 수준에서 이 개념을 간단한 `execution_log.json`으로 구현한다. ([OpenAI GitHub][7])

---

## FR-10. PII masking

LLM Assist Layer로 원문을 보내기 전에 개인정보 후보를 마스킹한다.

```text
raw_text
→ pii_detector
→ masked_text
→ LLM Assist Layer
```

예시:

```json
{
  "raw_text": "010-1234-5678 고객 결제 오류 확인해주세요. 주문번호 ORD-12345입니다.",
  "masked_text": "[PHONE] 고객 결제 오류 확인해주세요. 주문번호 [ORDER_ID]입니다.",
  "pii_detected": true,
  "pii_types": ["PHONE", "ORDER_ID"]
}
```

MVP v1에서는 완전한 개인정보 탐지 모델을 만들지 않는다. 대신 이메일, 전화번호, 주문번호, 주민등록번호 형태처럼 regex로 명확하게 잡히는 패턴부터 마스킹한다. 사람 이름처럼 오탐 가능성이 큰 PERSON masking은 v2 확장으로 미룬다. PII가 감지된 요청은 `risk_level`을 최소 medium 이상으로 올리고, 원문은 로컬 `execution_log.json`에만 저장한다.

이 정책은 보수적이다. PII가 많은 실제 업무 환경에서는 review queue 비율이 의도적으로 높아질 수 있으며, MVP에서는 false automation을 줄이는 쪽을 우선한다.

---

# 9. 비기능 요구사항

| 항목     | 요구사항                                             | 측정 기준 |
| ------ | ------------------------------------------------ | --- |
| 재현성    | 같은 입력과 같은 config에서는 같은 판단 결과가 나와야 함              | LLM 미사용 경로는 100% deterministic, LLM 사용 경로는 model/version/seed 가능 여부 기록 |
| 안전성    | 위험하거나 정보가 부족한 요청은 자동 실행하지 않음                     | false automation rate 5% 이하 목표 |
| 설명 가능성 | 분류·라우팅·review 결정 근거를 로그로 남김                      | 모든 요청에 decision_reasons 1개 이상 |
| 추적 가능성 | rule_config_version, scoring_policy_version, risk_policy_version, privacy_policy_version 저장 | execution_log 100% 포함 |
| 개인정보 보호 | LLM 전송 전 PII 후보를 마스킹 | pii_detected 요청은 masked_text만 LLM 전송 |
| 처리 속도 | CLI 배치 처리에서 병목을 줄임 | LLM 미사용 요청 1건당 1초 이내, LLM 사용 요청 1건당 5초 이내 목표 |
| 비용 통제 | 불필요한 LLM 호출을 줄임 | 전체 요청 중 LLM 호출 비율과 요청당 예상 비용 리포트 |
| 유지보수성  | 요청 유형, 팀 매핑, 우선순위 기준은 config로 분리                 | 정책 변경 시 코드 수정 없이 config 수정으로 반영 |
| 확장성    | CLI → Review UI → GitHub/Jira/Slack 연동 순서로 확장 가능 | MVP 단계별 architecture level 명시 |
| 평가 가능성 | 정답 라벨과 비교해 분류 정확도, review recall 등을 측정           | evaluation_report.md 자동 생성 |
| 다국어 확장성 | MVP는 한국어 중심으로 구현하되 핵심 keyword config에 영어 alias를 일부 포함 | localization.yml에 ko/en alias 유지 |
| 최소 의존성 | MVP는 로컬 실행 가능한 CLI 중심으로 구현                       | Docker 없이도 샘플 실행 가능 |

---

# 10. 시스템 아키텍처

## 10.1 전체 흐름

```text
[Input Layer]
CSV / JSONL / Slack-style request

        ↓

[Normalization Layer]
request_id 생성
raw_text 저장
기본 메타데이터 정리

        ↓

[Rule Engine]
키워드 매칭
요청 유형 후보 생성
담당 팀 후보 생성
rule 기반 field extraction
request_type 후보 pre-score 계산
PII masking 필요 여부 판단

        ↓

[Privacy Guard]
raw_text 내 개인정보 후보 탐지
LLM 전송용 masked_text 생성

        ↓

[LLM Assist Layer]
요약 생성
모호한 의도 후보 제안
누락 필드 보조 추출
누락 정보 질문 생성
티켓 초안 작성

        ↓

[Scoring & Decision Prep]
후보별 필수 필드 검사
우선순위 규칙 적용
최종 confidence score 계산
risk level 계산

        ↓

[Decision Layer]
ready_for_approval
draft_only
review_required
reject

        ↓

[Human Review Layer]
review_queue.csv
approve / edit / reject

        ↓

[Tool Execution Layer]
GitHub Issue / Jira Ticket / Notion Task
초기에는 dry-run

        ↓

[Trace & Evaluation Layer]
execution_log.json
evaluation_report.md
qa_assertion_report.md
실패 케이스 축적
```

## 10.2 계층별 설계 의도

| 계층                       | 역할           | 설계 의도                                  |
| ------------------------ | ------------ | -------------------------------------- |
| Input Layer              | 요청 입력        | 처음부터 Slack 실시간 봇으로 가지 않고 파일 기반 재실행성 확보 |
| Normalization Layer      | 공통 데이터 구조화   | 입력 채널이 달라도 동일한 처리 흐름 유지                |
| Rule Engine              | 반복 판단 처리     | 재현성과 안정성이 필요한 부분은 LLM보다 규칙 기반 처리       |
| Privacy Guard            | 개인정보 보호      | LLM 전송 전 PII 후보를 마스킹하고 원문은 로컬 로그로만 관리    |
| LLM Assist Layer         | 모호한 의미 판단 보조 | AI는 판단 보조와 초안 생성에 제한적으로 사용             |
| Scoring & Decision Prep  | 점수와 위험도 계산   | 후보별 필드 충족률과 정책 조건을 계산해 decision layer에 전달 |
| Decision Layer           | 승인 가능 여부 결정   | 자동화율보다 안전한 분기 우선                       |
| Human Review Layer       | 검토 큐         | 사람이 봐야 할 요청만 남김                        |
| Tool Execution Layer     | 외부 업무툴 연동    | 승인된 요청만 실제 등록                          |
| Trace & Evaluation Layer | 개선 루프        | 결과를 평가 데이터로 축적                         |

## 10.3 에러 처리 정책

| 위치 | 실패 상황 | 처리 방식 |
| --- | --- | --- |
| Input Layer | CSV/JSONL 파싱 실패 | 해당 row를 `processing_status=failed`로 기록하고 다음 row 계속 처리 |
| Rule Engine | config 누락 또는 rule 오류 | 요청을 `review_required`로 보내고 `error_code=rule_config_error` 기록 |
| Privacy Guard | PII masking 실패 | LLM 호출을 생략하고 `review_required`로 보냄 |
| LLM Assist Layer | API timeout 또는 응답 schema 불일치 | rule-only 결과로 fallback하고 `llm_used=false`, `llm_error` 기록 |
| Decision Layer | 서로 충돌하는 policy 결과 | `decision_order`에 따라 상위 decision 적용 |
| Tool Execution Layer | GitHub/Jira rate limit | exponential backoff 후 dry-run 결과만 저장, 중복 생성 방지를 위해 idempotency key 유지 |

MVP v1에서는 외부 시스템 write가 없으므로 장애 범위가 파일 출력과 로그 기록으로 제한된다. v2 이후 외부 연동을 추가할 때는 retry, idempotency, rate limit 처리를 별도 client 계층에 둔다.

---

# 11. 데이터 구조

## 11.1 입력 데이터

```json
{
  "request_id": "REQ-001",
  "requester": "kim",
  "channel": "slack",
  "raw_text": "A 고객사 결제 오류가 발생했습니다. 급합니다.",
  "created_at": "2026-05-11T09:00:00+09:00",
  "metadata": {
    "customer_tier": "enterprise",
    "source": "sample"
  }
}
```

## 11.2 정규화 결과

```json
{
  "schema_version": "normalized_request.v1",
  "rule_config_version": "2026-05-11",
  "scoring_policy_version": "scoring.2026-05-11",
  "risk_policy_version": "risk.2026-05-11",
  "privacy_policy_version": "privacy_rules.2026-05-11",
  "request_id": "REQ-001",
  "request_type": "bug_report",
  "request_type_confidence": 0.82,
  "request_type_candidates": [
    {
      "type": "bug_report",
      "confidence": 0.82
    },
    {
      "type": "customer_support",
      "confidence": 0.66
    }
  ],
  "summary": "A 고객사 결제 오류 확인 요청",
  "required_action": "결제 오류 원인 확인",
  "target_team": "engineering",
  "target_team_confidence": 0.8,
  "target_team_candidates": [
    {
      "team": "engineering",
      "confidence": 0.8
    },
    {
      "team": "cs",
      "confidence": 0.68
    }
  ],
  "priority": "urgent",
  "risk_level": "medium",
  "pii_detected": false,
  "masked_text": "A 고객사 결제 오류가 발생했습니다. 급합니다.",
  "extracted_fields": {
    "symptom": "결제 오류",
    "affected_customer_or_user": "A 고객사",
    "impact_scope": null,
    "reproduction_steps": null
  },
  "missing_fields": ["impact_scope", "reproduction_steps"],
  "needs_review": true,
  "review_reason": "영향 범위와 재현 조건이 누락됨",
  "automation_decision": "review_required"
}
```

## 11.3 티켓 초안

```json
{
  "request_id": "REQ-001",
  "title": "[Bug] A 고객사 결제 오류 확인",
  "body": "원문 요청, 현재 판단, 누락 정보, 추천 질문, trace 포함",
  "labels": ["bug", "payment", "review-required"],
  "assignee_team": "engineering",
  "priority": "urgent"
}
```

## 11.4 Review queue

```json
{
  "request_id": "REQ-001",
  "raw_text": "A 고객사 결제 오류가 발생했습니다. 급합니다.",
  "suggested_type": "bug_report",
  "suggested_team": "engineering",
  "type_candidates": ["bug_report", "customer_support"],
  "team_candidates": ["engineering", "cs"],
  "review_reason": "영향 범위와 재현 조건이 누락됨",
  "suggested_question": "전체 고객 영향인지, 특정 고객사 문제인지 확인이 필요합니다.",
  "decision_reasons": [
    "impact_scope 누락",
    "reproduction_steps 누락",
    "risk_level medium"
  ],
  "review_action": "ask_clarification"
}
```

---

# 12. Config 설계

업무 기준은 코드와 분리한다.

```text
config/
  request_types.yml
  team_mapping.yml
  priority_rules.yml
  required_fields.yml
  scoring_policy.yml
  risk_rules.yml
  automation_policy.yml
  privacy_rules.yml
  ticket_templates.yml
  review_policy.yml
  localization.yml
```

## 12.1 request_types.yml

```yaml
version: "request_types.2026-05-11"

bug_report:
  keywords:
    오류: 0.4
    버그: 0.4
    장애: 0.5
    에러: 0.4
    재현: 0.3
    안됨: 0.3
    error: 0.4
    bug: 0.4
    outage: 0.5
  metadata_conditions:
    channel:
      - slack
      - form
  default_team: engineering
  required_fields:
    - symptom
    - affected_customer_or_user
    - impact_scope

data_request:
  keywords:
    데이터: 0.4
    추출: 0.4
    리포트: 0.3
    쿼리: 0.3
    대시보드: 0.3
    data: 0.4
    report: 0.3
    query: 0.3
    dashboard: 0.3
  default_team: data
  required_fields:
    - dataset_or_metric
    - purpose
    - deadline

internal_ops:
  keywords:
    계정: 0.3
    권한: 0.4
    온보딩: 0.3
    설정: 0.2
    account: 0.3
    permission: 0.4
    onboarding: 0.3
  default_team: ops
  required_fields:
    - requested_action
    - target_user_or_system
    - deadline

other:
  keywords: {}
  default_team: unassigned
  required_fields: []
  fallback_only: true
```

keyword weight는 사람이 관리하기 쉽도록 config에 원시 weight로 적고, scoring 단계에서 request type별 active keyword group의 총합으로 나눠 정규화한다. 따라서 각 keyword weight 합이 반드시 1.0일 필요는 없다.

## 12.2 required_fields.yml

필드 누락 판단은 required와 optional을 구분한다.

```yaml
version: "required_fields.2026-05-11"

bug_report:
  required:
    - symptom
    - affected_customer_or_user
    - impact_scope
  optional:
    - reproduction_steps
    - first_seen_at
    - environment

data_request:
  required:
    - dataset_or_metric
    - purpose
    - deadline
  optional:
    - format
    - delivery_channel
    - refresh_frequency

feature_request:
  required:
    - user_need
    - expected_outcome
  optional:
    - priority_reason
    - target_release

internal_ops:
  required:
    - requested_action
    - target_user_or_system
  optional:
    - deadline
    - approval_owner
```

`missing_fields`는 required 필드가 비어 있을 때만 review_required를 강제한다. optional 필드만 비어 있으면 `draft_only`가 될 수 있다.

## 12.3 priority_rules.yml

```yaml
version: "priority_rules.2026-05-11"

urgent:
  keywords:
    - 장애
    - 결제 불가
    - 전체 고객
    - 운영 중단
  metadata_conditions:
    customer_tier:
      - enterprise

high:
  keywords:
    - 급해요
    - 오늘 중
    - 고객사
    - urgent
    - today
    - customer
```

## 12.4 team_mapping.yml

`target_team_confidence`의 `team_mapping_score`와 `team_keyword_score`는 이 설정을 기준으로 계산한다.

```yaml
version: "team_mapping.2026-05-11"

engineering:
  request_types:
    primary:
      - bug_report
    secondary:
      - customer_support
  keywords:
    결제: 0.3
    오류: 0.4
    장애: 0.4
    api: 0.3
    error: 0.4

data:
  request_types:
    primary:
      - data_request
  keywords:
    데이터: 0.4
    리포트: 0.3
    쿼리: 0.3
    data: 0.4
    report: 0.3

cs:
  request_types:
    primary:
      - customer_support
    secondary:
      - bug_report
  keywords:
    고객: 0.4
    문의: 0.3
    customer: 0.4
```

계산 기준:

```text
team_mapping_score
→ 후보 team의 primary request_types에 request_type이 있으면 1.0
→ secondary request_types에 있으면 0.5
→ 없으면 0

team_keyword_score
→ matched_weight_sum / team_keyword_total_weight
```

## 12.5 scoring_policy.yml

```yaml
version: "scoring.2026-05-11"

request_type_confidence:
  calculation_mode: "per_candidate"
  candidate_preselect_top_n: 3
  keyword_weight_normalization: "matched_weight_sum / active_keyword_total_weight"
  keyword_score_weight: 0.50
  required_field_score_weight: 0.35
  metadata_score_weight: 0.15
  close_candidate_gap: 0.15
  close_candidate_penalty: 0.10

target_team_confidence:
  request_type_confidence_weight: 0.55
  team_mapping_score_weight: 0.30
  team_keyword_score_weight: 0.15
  multi_team_gap: 0.15
  multi_team_penalty: 0.10
```

## 12.6 risk_rules.yml

```yaml
version: "risk.2026-05-11"
matching_semantics:
  within_same_bucket: "OR"
  between_buckets: "OR"
  final_risk: "highest_matched_level_wins"

high:
  request_types:
    - approval_request
  keywords:
    - 환불
    - 결제 취소
    - 권한 부여
    - 계정 삭제
    - 운영 데이터 수정
    - 보안 사고
    - refund
    - permission
    - delete account
    - security incident
  side_effects:
    - external_write
    - permission_change
    - payment_or_refund

medium:
  keywords:
    - 고객사
    - 장애
    - 개인정보
    - 긴급
    - customer
    - outage
    - pii
    - urgent
  metadata_conditions:
    customer_tier:
      - enterprise

low:
  side_effects:
    - draft_only
    - read_only
```

`matching_semantics`는 risk rule의 해석을 고정한다. 예를 들어 `medium.keywords` 중 하나만 매칭되거나 `medium.metadata_conditions.customer_tier == enterprise`만 매칭되어도 medium risk 후보가 된다. high와 medium이 동시에 매칭되면 high가 최종 risk_level이 된다.

## 12.7 automation_policy.yml

```yaml
version: "automation_policy.2026-05-11"

decision_order:
  - reject
  - review_required
  - draft_only
  - ready_for_approval

ready_for_approval:
  match: "ALL"
  min_request_type_confidence: 0.85
  min_team_confidence: 0.85
  allow_missing_fields: false
  max_risk_level: low
  external_create: false

draft_only:
  match: "ALL"
  min_request_type_confidence: 0.75
  min_team_confidence: 0.75
  allow_missing_fields: "optional_only"
  max_risk_level: medium
  requires_human_approval: true

review_required:
  match: "ANY"
  triggers:
    - required_missing_fields_present
    - multiple_team_candidates
    - low_confidence
    - high_risk_action

reject:
  match: "ANY"
  triggers:
    - unsupported_request_type
    - policy_blocked
    - unsafe_or_disallowed_request
```

decision은 cascade 방식으로 평가한다.

```text
1. reject 조건을 먼저 평가한다.
2. reject가 아니면 review_required 조건을 평가한다.
3. review_required가 아니면 draft_only 조건을 평가한다.
4. 마지막으로 ready_for_approval 조건을 평가한다.
```

같은 요청이 여러 조건에 동시에 걸릴 때는 `decision_order`가 우선한다. 예를 들어 optional field만 누락되어 `draft_only` 조건을 만족하더라도, high risk action이 함께 감지되면 `review_required`가 먼저 적용된다.

reject trigger 정의:

| trigger | 의미 |
| --- | --- |
| unsupported_request_type | 지원하지 않는 업무 유형이며 티켓 초안 생성도 의미가 없음 |
| policy_blocked | 조직 정책상 자동화 파이프라인에서 처리하면 안 되는 요청 |
| unsafe_or_disallowed_request | 권한 상승, 보안 우회, 개인정보 노출, 데이터 삭제처럼 자동화 시스템이 초안 생성도 제한해야 하는 요청 |

`unsafe_or_disallowed_request`는 단순히 `risk_level == high`와 같지 않다. high risk는 review_required로 갈 수 있지만, 보안 우회나 개인정보 원문 추출처럼 정책상 다루면 안 되는 요청은 reject로 보낸다.

## 12.8 privacy_rules.yml

```yaml
version: "privacy_rules.2026-05-11"

masking:
  email:
    pattern: "[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}"
    replacement: "[EMAIL]"
  phone:
    pattern: "(01[016789])-?\\d{3,4}-?\\d{4}"
    replacement: "[PHONE]"
  rrn_like:
    pattern: "\\d{6}-\\d{7}"
    replacement: "[ID_NUMBER]"
  order_id:
    pattern: "(ORD|ORDER)-\\d+"
    replacement: "[ORDER_ID]"

policy:
  pii_detected_min_risk_level: medium
  send_raw_text_to_llm: false
  store_raw_text_local_only: true
```

MVP에서는 완벽한 PII 탐지를 목표로 하지 않는다. 명확한 패턴부터 마스킹하고, PII가 감지된 요청은 reviewer가 원문을 확인하도록 review queue에서 표시한다.

## 12.9 ticket_templates.yml

티켓 본문은 요청 유형별 템플릿으로 관리한다.

```yaml
version: "ticket_templates.2026-05-11"

bug_report:
  title: "[Bug] {summary}"
  labels:
    - bug
    - "{priority}"
  body_sections:
    - summary
    - original_request
    - extracted_fields
    - missing_information
    - suggested_next_question
    - trace

data_request:
  title: "[Data] {summary}"
  labels:
    - data-request
    - "{priority}"
  body_sections:
    - summary
    - requested_dataset
    - purpose
    - deadline
    - missing_information
```

## 12.10 review_policy.yml

review queue에서 사람이 취할 액션과 기본 담당자를 정의한다.

```yaml
version: "review_policy.2026-05-11"

actions:
  ask_clarification:
    when:
      - required_missing_fields_present
    default_owner: requester

  route_to_owner:
    when:
      - multiple_team_candidates
    default_owner: ops_triage

  security_review:
    when:
      - unsafe_or_disallowed_request
      - pii_detected
    default_owner: security_or_admin
```

## 12.11 localization.yml

MVP는 한국어 업무 요청을 우선 대상으로 하지만, FDE 포트폴리오 관점에서는 영어 요청도 최소한의 확장 가능성을 보여준다. 따라서 핵심 keyword config에는 한국어와 영어 alias를 함께 둘 수 있게 한다.

```yaml
version: "localization.2026-05-11"

default_language: ko

supported_languages:
  - ko
  - en

aliases:
  bug_report:
    ko:
      - 오류
      - 버그
      - 장애
    en:
      - error
      - bug
      - outage

  data_request:
    ko:
      - 데이터
      - 리포트
      - 쿼리
    en:
      - data
      - report
      - query
```

다국어 품질 자체는 MVP의 핵심 목표가 아니다. v1에서는 한국어 중심으로 구현하되, config 구조가 특정 언어에 고정되지 않음을 보여주는 정도로 제한한다.

---

# 13. 기술 스택

## 13.1 MVP v1 추천 스택

| 영역     | 기술                              |
| ------ | ------------------------------- |
| 실행 방식  | Python CLI                      |
| 데이터 처리 | pandas, pydantic                |
| 설정 파일  | YAML                            |
| LLM    | OpenAI API                      |
| 구조화 출력 | JSON Schema / Pydantic          |
| 저장     | JSONL, CSV, SQLite 선택           |
| 평가     | Python script + Markdown report |
| 배포     | 로컬 실행, Docker 선택                |

## 13.2 MVP v2 확장 스택

| 영역        | 기술                                |
| --------- | --------------------------------- |
| Review UI | Streamlit 또는 FastAPI + 간단한 HTML   |
| 외부 연동     | GitHub Issues API                 |
| 승인 흐름     | approve/edit/reject 상태 저장         |
| 로그        | SQLite 또는 PostgreSQL              |
| 배포        | Render, Fly.io, Railway, AWS 중 하나 |

## 13.3 MVP v3 확장 스택

| 영역       | 기술                               |
| -------- | -------------------------------- |
| Slack 입력 | Slack Workflow Step 또는 Slack App |
| Jira 연동  | Jira Cloud REST API              |
| 대시보드     | Streamlit / Metabase / Superset  |
| 운영 로그    | PostgreSQL                       |
| 스케줄링     | cron / Prefect                   |

Jira Cloud REST API는 issue 생성 API를 제공하지만, description이나 multi-line custom field는 Atlassian Document Format을 요구할 수 있다. 따라서 GitHub Issue 이후 Jira Ticket으로 확장할 때는 단순 Markdown 본문을 그대로 보내지 않고, Jira용 payload 변환 계층을 별도로 둔다. ([Atlassian Developer][8])

## 13.4 Architecture level

bkit 관점에서는 MVP 단계별 복잡도를 다음처럼 나눈다.

| 단계 | Architecture level | 기준 |
| --- | --- | --- |
| MVP v1 | Starter | 로컬 CLI, 파일 입출력, config 기반 rule engine |
| MVP v2 | Dynamic | Review UI, SQLite 상태 저장, GitHub dry-run/approved create |
| MVP v3 | Enterprise-ready | Slack 이벤트, Jira/Notion 연동, 운영 로그, 스케줄링, rate limit/retry 정책 |

v1에서는 Enterprise 구조를 미리 만들지 않는다. 대신 config, schema, trace, eval을 안정적으로 고정해 v2/v3로 확장할 때 바꿔야 할 부분과 유지해야 할 부분을 분리한다.

---

# 14. 평가 설계

이 프로젝트에서 중요한 것은 “얼마나 많이 자동화했는가”가 아니다.

더 중요한 것은 다음이다.

```text
자동화하면 안 되는 요청을 잘 걸러냈는가?
사람이 수정해야 하는 양이 줄었는가?
반복 요청을 안정적으로 처리했는가?
```

OpenAI의 evals 문서는 LLM 애플리케이션을 테스트하고 개선하기 위한 평가 흐름을 제공하며, 프로그래밍 방식으로 eval을 구성할 수 있다고 설명한다. OpsFlow AI에서는 이 개념을 포트폴리오 수준에서 labeled request dataset과 custom metric으로 구현한다. ([OpenAI 개발자][9])

## 14.1 주요 평가 지표

| 지표                              | 의미                        | 목표 예시    |
| ------------------------------- | ------------------------- | -------- |
| request type accuracy           | 요청 유형 분류 정확도              | 85% 이상   |
| team routing accuracy           | 담당 팀 추천 정확도               | 80% 이상   |
| missing field detection rate    | 누락 정보 탐지율                 | 85% 이상   |
| review recall                   | 검토가 필요한 요청을 review로 보낸 비율 | 90% 이상   |
| false automation rate           | 자동화하면 안 되는 요청을 자동 처리한 비율  | 5% 이하    |
| human edit rate                 | 사람이 티켓 초안을 수정한 비율         | 낮을수록 좋음  |
| review precision                | review queue에 들어간 요청 중 실제 검토가 필요했던 비율 | 75% 이상 |
| review handling time per item   | reviewer가 review queue 1건을 처리하는 평균 시간 | mini human-eval로 측정 |
| automation coverage             | 전체 요청 중 자동 초안 생성 비율       | 상황별 측정   |
| average handling time reduction | 요청 처리 시간 감소율              | mini human-eval 보조 측정 |

## 14.2 가장 중요한 지표

이 프로젝트에서 가장 중요한 지표는 두 개다.

```text
1. false automation rate
2. review recall
```

이유는 명확하다.

```text
자동화율만 높이면 위험하다.
잘못된 요청을 자동 실행하는 것이 가장 큰 리스크다.
따라서 애매하거나 위험한 요청을 review로 보내는 능력이 중요하다.
```

계산식:

```text
false automation rate
= ready_for_approval 또는 draft_only로 분류했지만 gold label상 review_required 또는 reject였던 요청 수
  / ready_for_approval 또는 draft_only로 분류한 전체 요청 수

review recall
= gold label상 review_required 또는 reject인 요청 중 실제 review_required/reject로 분류한 요청 수
  / gold label상 review_required 또는 reject인 전체 요청 수

review precision
= 실제 review queue에 들어간 요청 중 gold label상 review_required 또는 reject인 요청 수
  / 실제 review queue에 들어간 전체 요청 수

human edit rate
= 사람이 제목, 본문, request_type, target_team, priority 중 하나 이상 수정한 티켓 수
  / 사람이 검토한 전체 티켓 수

review handling time reduction
= (AI 보조 없이 review 1건 처리 평균 시간 - AI 보조 review 1건 처리 평균 시간)
  / AI 보조 없이 review 1건 처리 평균 시간
```

confidence threshold는 고정값 하나만 보지 않고 threshold sweep으로 비교한다. 아래 표는 기대 방향을 설명하는 placeholder이며, 실제 수치는 Phase 5에서 `evaluation_report.md`에 채운다.

| threshold | automation coverage | false automation rate | review recall |
| --------- | ------------------- | --------------------- | ------------- |
| 0.65      | 높음                | 높아질 수 있음          | 낮아질 수 있음 |
| 0.75      | 중간                | 중간                  | 중간          |
| 0.85      | 낮음                | 낮음                  | 높음          |

포트폴리오에서는 이 표를 실제 평가 결과로 채워, 자동화율과 안전성의 trade-off를 보여준다.

## 14.3 평가 데이터셋 구성

```text
data/
  sample_requests.csv
  labeled_requests.csv
  edge_cases.csv
  external_seed_requests.csv
  labeling_guidelines.md
```

데이터셋은 세 층으로 구성한다.

| 데이터 | 목적 |
| --- | --- |
| sample_requests.csv | 직접 만든 기본 업무 요청 샘플 |
| edge_cases.csv | 의도적으로 어려운 케이스와 위험 케이스 |
| external_seed_requests.csv | 공개 issue tracker나 공개 업무 요청 패턴에서 가져와 익명화한 샘플 |
| labeled_requests.csv | 위 데이터를 통합해 정답 라벨을 붙인 평가 데이터 |

직접 만든 샘플만으로 평가하면 self-confirmation bias가 생길 수 있다. 따라서 MVP 평가에서는 공개 GitHub Issues, 공개 Jira issue, 오픈소스 프로젝트의 issue title/body처럼 공개적으로 접근 가능한 요청 패턴 일부를 참고해 `external_seed_requests.csv`를 만든다.

단, 외부 데이터는 그대로 복사해 포트폴리오에 노출하지 않는다. 라이선스와 개인정보 리스크를 줄이기 위해 원문 URL, 출처, 수집일, 익명화 여부를 별도로 기록하고, 필요한 경우 원문을 요약·패턴화한 형태로 저장한다.

요청 유형:

```text
1. bug_report
2. data_request
3. customer_support
4. feature_request
5. approval_request
6. internal_ops
7. other
```

edge case:

```text
1. 너무 짧은 요청
2. 담당 팀이 애매한 요청
3. 긴급하다고 말하지만 근거가 없는 요청
4. 고객명만 있고 증상이 없는 요청
5. 과거 요청을 참조하지만 ID가 없는 요청
6. 두 팀이 모두 관련된 요청
7. 자동 실행하면 위험한 요청
8. 필수 정보가 누락된 요청
```

초기 평가 데이터의 한계도 README에 명시한다.

```text
1. 초기 데이터는 합성 데이터와 공개 issue 기반 샘플이 섞여 있다.
2. 실제 회사 내부 요청의 분포와 다를 수 있다.
3. 정답 라벨은 단일 작성자 기준이므로 편향이 있을 수 있다.
4. v2에서는 다른 사람이 라벨링한 holdout set을 추가해 평가 신뢰도를 높인다.
```

## 14.4 Mini human-eval

review handling time은 단순 가정값으로만 두지 않는다. MVP 포트폴리오에서는 작은 human-eval을 수행한다.

```text
참여자:
- 본인 + 1~2명

데이터:
- review_required 후보 10건
- ready_for_approval 후보 10건

조건 A:
- raw_text만 보고 request_type, target_team, missing_fields, next question 작성

조건 B:
- OpsFlow AI가 만든 후보 유형, 후보 팀, missing_fields, suggested_question을 함께 보고 검토

절차:
- 참여자는 조건 A를 먼저 수행한 뒤 조건 B를 수행한다.
- 본인은 측정 운영과 결과 정리만 담당하고, 가능하면 본인 측정값은 별도 표기하거나 제외한다.
- 조건 A와 조건 B의 요청 순서를 섞어 단순 암기 효과를 줄인다.

측정:
- 건당 처리 시간
- 사람이 수정한 필드 수
- 최종 판단과 gold label 일치 여부
```

결과는 `docs/evaluation_notes.md`에 기록한다. 표본 수가 작기 때문에 통계적 결론으로 주장하지 않고, “AI 정리본이 reviewer의 판단 시간을 줄일 가능성이 있는지”를 확인하는 보조 평가로만 사용한다.

## 14.5 로그 기반 QA assertion

`execution_log.json`은 단순 기록이 아니라 자동 검증 대상이다. MVP에서는 다음 assertion을 `src/evaluate.py` 또는 별도 QA 스크립트에서 검사한다.

```text
1. automation_decision == ready_for_approval이면 missing_fields == []이어야 한다.
2. risk_level == high이면 automation_decision은 ready_for_approval이 될 수 없다.
3. pii_detected == true이면 llm_input_text는 masked_text여야 한다.
4. request_type_confidence는 request_type_candidates[0].confidence와 같아야 한다.
5. target_team_confidence는 target_team_candidates[0].confidence와 같아야 한다.
6. other request_type은 ready_for_approval이 될 수 없다.
7. rule_config_version, scoring_policy_version, risk_policy_version, privacy_policy_version은 모든 요청에 존재해야 한다.
```

이 QA는 bkit의 Check 단계에 해당한다. CI/CD까지 붙이지 않더라도, 로컬에서 `python -m src.evaluate`를 실행하면 metric report와 assertion failure 목록을 함께 출력하도록 설계한다.

---

# 15. 구현 로드맵

## Phase 1. 문제 구조화와 샘플 데이터

목표:

```text
비정형 요청 데이터와 정답 라벨을 만든다.
```

산출물:

```text
data/sample_requests.csv
data/labeled_requests.csv
data/edge_cases.csv
data/external_seed_requests.csv
data/labeling_guidelines.md
docs/problem_definition.md
```

작업:

```text
1. 요청 유형 6~7개 정의
2. 요청 유형별 필수 정보 정의
3. 샘플 요청 100개 생성
4. edge case 20개 생성
5. 공개 issue tracker 기반 외부 seed 샘플 20~30개 추가
6. 라벨링 가이드 작성
7. 정답 라벨 작성
8. 합성 데이터와 외부 seed 데이터의 한계 문서화
```

---

## Phase 2. Rule Engine 구현

목표:

```text
LLM 없이도 기본 요청 분류와 누락 정보 검사를 수행한다.
```

산출물:

```text
config/request_types.yml
config/team_mapping.yml
config/priority_rules.yml
config/required_fields.yml
config/scoring_policy.yml
config/risk_rules.yml
config/privacy_rules.yml
src/privacy.py
src/rule_engine.py
```

작업:

```text
1. 키워드 기반 요청 유형 후보 생성
2. 담당 팀 매핑
3. 필수 필드 누락 검사
4. 우선순위 규칙 적용
5. request_type_confidence 계산
6. target_team_confidence 계산
7. risk_level 계산
8. PII masking 적용
9. multi-candidate 생성
```

---

## Phase 3. LLM Assist Layer 구현

목표:

```text
규칙으로 애매한 요청에 대해서만 LLM을 사용한다.
```

산출물:

```text
src/llm_assist.py
src/schema.py
```

작업:

```text
1. 요청 요약 생성
2. 티켓 제목/본문 초안 생성
3. 누락 정보 질문 생성
4. structured output schema 적용
5. masked_text만 LLM에 전달
6. LLM 사용 여부 조건화
```

---

## Phase 4. Decision Layer와 Review Queue

목표:

```text
승인 가능한 티켓 초안 요청과 사람 검토 요청을 분리한다.
```

산출물:

```text
src/decision.py
outputs/review_queue.csv
outputs/ticket_drafts.json
```

작업:

```text
1. ready_for_approval / draft_only / review_required / reject 분기
2. review reason 생성
3. review queue 출력
4. ticket draft 출력
5. 후보 팀이 복수인 요청은 review_required로 분기
```

---

## Phase 5. Trace와 Evaluation

목표:

```text
판단 경로와 평가 리포트를 만든다.
```

산출물:

```text
outputs/execution_log.json
outputs/evaluation_report.md
outputs/qa_assertion_report.md
docs/evaluation_notes.md
src/evaluate.py
src/qa_assertions.py
```

작업:

```text
1. rule match log 저장
2. LLM 사용 여부 저장
3. rule_config_version, scoring_policy_version, risk_policy_version, privacy_policy_version 저장
4. final decision 저장
5. labeled dataset과 비교
6. metric 계산
7. threshold sweep으로 automation coverage와 false automation trade-off 분석
8. mini human-eval로 review handling time 측정
9. 로그 기반 QA assertion 검사
10. 실패 케이스 분석
```

---

## Phase 6. 외부 업무툴 연동

목표:

```text
승인된 요청만 GitHub Issue로 생성한다.
```

산출물:

```text
src/github_client.py
outputs/github_dry_run.json
```

작업:

```text
1. GitHub Issue payload 생성
2. dry-run 모드 구현
3. request_id 기반 idempotency key 생성
4. 승인된 요청만 실제 생성
5. 중복 생성 방지
6. 생성 결과 log 저장
```

---

# 16. 폴더 구조

```text
opsflow-ai/
  README.md
  docs/
    project_plan.md
    problem_definition.md
    interview_notes.md
    evaluation_notes.md
  data/
    sample_requests.csv
    labeled_requests.csv
    edge_cases.csv
    external_seed_requests.csv
    labeling_guidelines.md
  config/
    request_types.yml
    team_mapping.yml
    priority_rules.yml
    required_fields.yml
    scoring_policy.yml
    risk_rules.yml
    privacy_rules.yml
    automation_policy.yml
    ticket_templates.yml
    review_policy.yml
    localization.yml
  src/
    main.py
    schema.py
    loader.py
    normalizer.py
    privacy.py
    rule_engine.py
    llm_assist.py
    decision.py
    ticket_builder.py
    review_queue.py
    tracer.py
    evaluate.py
    qa_assertions.py
    github_client.py
  outputs/
    normalized_requests.json
    ticket_drafts.json
    review_queue.csv
    execution_log.json
    evaluation_report.md
    qa_assertion_report.md
  tests/
    test_rule_engine.py
    test_decision.py
    test_missing_fields.py
    test_scoring_policy.py
    test_risk_rules.py
    test_privacy.py
    test_qa_assertions.py
  pyproject.toml
  .env.example
```

---

# 17. CLI 실행 예시

```bash
python -m src.main run \
  --input data/sample_requests.csv \
  --config config/ \
  --output outputs/ \
  --dry-run
```

실행 결과:

```text
✅ normalized_requests.json 생성
✅ ticket_drafts.json 생성
✅ review_queue.csv 생성
✅ execution_log.json 생성
✅ evaluation_report.md 생성
✅ qa_assertion_report.md 생성
```

평가 실행:

```bash
python -m src.evaluate \
  --pred outputs/normalized_requests.json \
  --gold data/labeled_requests.csv \
  --output outputs/evaluation_report.md
```

---

# 18. 예상 산출물

## 18.1 포트폴리오 산출물

```text
1. GitHub Repository
2. README.md
3. project_plan.md
4. sample_requests.csv
5. external_seed_requests.csv
6. demo GIF 또는 실행 캡처
7. review_queue 예시
8. evaluation_report.md
9. threshold trade-off 표
10. architecture diagram
11. interview_notes.md
```

## 18.2 README 핵심 구성

```text
1. 프로젝트 소개
2. 문제 재정의
3. 핵심 원칙
4. 시스템 흐름
5. 실행 방법
6. 입력/출력 예시
7. Rule-first 설계
8. LLM 사용 경계
9. Human-in-the-loop 설계
10. 평가 지표
11. confidence와 risk 산출 방식
12. 평가 데이터 한계
13. 확장 계획
14. 면접용 요약
```

---

# 19. 리스크와 대응 전략

| 리스크                 | 설명                                | 대응                                        |
| ------------------- | --------------------------------- | ----------------------------------------- |
| LLM이 그럴듯하게 틀린 판단을 함 | 업무 요청을 잘못 분류할 수 있음                | 규칙 기반 1차 판단 + review queue                |
| 자동화율에만 집중하게 됨       | 위험한 요청까지 자동 처리할 수 있음              | false automation rate를 핵심 지표로 설정          |
| 프로젝트 범위가 커짐         | Slack, Jira, UI까지 한 번에 붙이면 완성도 저하 | CLI MVP → UI → 외부 연동 순서                   |
| RAG 프로젝트와 겹쳐 보임     | 문서 검색 챗봇처럼 보일 수 있음                | 핵심을 “정규화, 라우팅, 검토 큐”로 고정                  |
| 업무 기준이 바뀜           | 팀 매핑, 우선순위 기준이 조직마다 다름            | config 기반 정책 분리                           |
| 평가가 약해 보임           | 데모만 있으면 설득력 부족                    | labeled dataset + edge case + eval report |
| confidence 기준이 불명확함  | 자동화 결정의 근거를 설명하기 어려움              | scoring_policy.yml과 명시적 계산식 사용             |
| risk_level이 자의적으로 보임 | 위험도 판단이 LLM 주관으로 보일 수 있음           | risk_rules.yml에서 side effect와 keyword 기반 산출 |
| 자체 제작 데이터 편향        | 만든 사람이 만든 데이터로 평가하는 문제가 생김        | external_seed_requests와 데이터 한계 명시            |
| 담당 팀이 복수인 요청        | 단일 target_team 필드로는 모호성을 표현하기 어려움  | target_team_candidates 저장 후 review_required 처리 |
| LLM 비용 증가             | 애매한 요청이 많으면 API 호출 비용이 증가          | keyword pre-score와 rule-only 처리로 LLM 호출 조건 제한 |
| LLM 응답 지연             | 배치 처리 시간이 길어질 수 있음                 | timeout 설정, rule-only fallback, 요청당 처리 시간 리포트 |
| 개인정보 전송 위험          | raw_text에 PII가 포함될 수 있음               | LLM 호출 전 PII masking, pii_detected 요청은 risk 상향 |
| 외부 API rate limit       | GitHub/Jira 연동 시 생성 실패나 지연 발생        | dry-run 우선, retry/backoff, idempotency key 저장 |
| 정책 충돌                 | draft_only와 review_required가 동시에 매칭될 수 있음 | decision_order로 reject > review_required > draft_only > ready_for_approval 적용 |

---

# 20. 이 프로젝트가 FDE 포트폴리오로 좋은 이유

OpsFlow AI는 단순 AI 앱이 아니라, FDE가 현장에서 해야 하는 사고 흐름을 보여준다.

```text
현업 문제 관찰
→ 반복 병목 식별
→ 진짜 문제 재정의
→ 출력 스키마 고정
→ 최소 자동화 범위 설정
→ 규칙/LLM/사람의 경계 설계
→ 외부 업무툴 연동 가능성 확보
→ 로그와 평가로 개선 루프 구성
```

특히 다음 메시지가 강하다.

> **AI를 많이 쓰는 것이 아니라, AI가 들어가야 할 위치를 제한적으로 설계했다.**

이것이 일반적인 AI 데모와 차별화되는 지점이다.

---

# 21. 면접용 프로젝트 설명

면접에서는 이렇게 설명하면 좋다.

> OpsFlow AI는 비정형으로 들어오는 업무 요청을 표준 업무 처리 스키마로 정규화하는 자동화 프로젝트입니다. 처음에는 AI가 요청을 자동 처리하는 에이전트처럼 보일 수 있지만, 저는 실제 병목이 요청 유형, 담당 팀, 우선순위, 필수 정보 누락 여부를 사람이 매번 판단하는 데 있다고 봤습니다.
>
> 그래서 입력 채널을 먼저 확장하기보다, 최종적으로 업무 시스템에 들어갈 표준 스키마를 먼저 고정했습니다. 그다음 요청 유형, 담당 팀, 우선순위, 누락 정보, review 필요 여부를 판단하는 흐름을 만들었습니다.
>
> 반복 가능하고 기준이 명확한 부분은 LLM이 아니라 규칙 기반으로 처리했습니다. 예를 들어 요청 유형별 필수 필드, 담당 팀 매핑, 우선순위 상향 조건, 승인 가능 초안 조건은 설정 파일로 분리했습니다. LLM은 애매한 요청의 의도 후보를 제안하거나, 티켓 제목과 본문 초안을 만들거나, 누락 정보를 질문으로 바꾸는 보조 역할로만 사용했습니다.
>
> confidence도 LLM이 스스로 말한 점수를 쓰지 않았습니다. 키워드 매칭, 필수 필드 충족률, 메타데이터 매칭, 후보 간 충돌 여부를 기준으로 계산했습니다. risk_level도 환불, 권한 변경, 외부 시스템 write 같은 side effect와 risk keyword를 config로 관리했습니다.
>
> 특히 모든 요청을 자동 확정하지 않고, confidence가 낮거나 필수 정보가 빠졌거나 자동 실행이 위험한 요청은 review queue로 분리했습니다. 자동화의 목표는 사람을 없애는 것이 아니라, 사람이 봐야 할 요청만 남기는 것이라고 봤기 때문입니다.
>
> 1차 MVP는 CLI 기반으로 설계했습니다. CSV나 Slack-style 정적 JSON 요청 데이터를 입력하면 normalized request, ticket draft, review queue, execution log를 생성합니다. 실시간 Slack 봇은 v1 범위에서 제외했고, 이후 사람이 승인한 요청만 GitHub Issue나 Jira Ticket으로 등록하는 방식으로 확장할 수 있게 했습니다.
>
> 평가 지표도 단순 자동화율이 아니라, 요청 유형 분류 정확도, 담당 팀 라우팅 정확도, review recall, false automation rate, human edit rate, review handling time reduction을 보도록 설계했습니다. 또한 threshold별 trade-off를 비교해서 자동화율을 높일 때 false automation이 얼마나 증가하는지 확인하도록 했습니다. 이 프로젝트의 핵심은 AI를 많이 쓰는 것이 아니라, 반복 업무 병목을 안정적인 흐름으로 줄이고, 애매한 판단은 검토 가능하게 남기는 것입니다.

---

# 22. 최종 요약

OpsFlow AI의 핵심은 다음이다.

```text
비정형 요청을 받는다
→ 표준 스키마로 바꾼다
→ 규칙으로 먼저 판단한다
→ 애매한 부분만 LLM이 보조한다
→ 위험하거나 불완전한 요청은 review queue로 보낸다
→ 승인된 요청만 티켓화한다
→ 모든 판단 경로를 로그로 남긴다
→ 평가 지표로 개선한다
```

최종 포트폴리오 메시지는 이 문장으로 정리할 수 있다.

> **OpsFlow AI는 AI가 모든 요청을 대신 처리하는 에이전트가 아니라, 비정형 업무 요청을 표준 스키마로 정규화하고, 명확한 요청은 승인 가능한 티켓 초안으로 만들며, 애매한 요청은 review queue로 분리하는 현업형 업무 자동화 시스템이다.**

[1]: https://developers.openai.com/api/docs/guides/structured-outputs "Structured model outputs | OpenAI API"
[2]: https://developers.openai.com/api/docs/guides/function-calling "Function calling | OpenAI API"
[3]: https://docs.github.com/en/rest/issues "REST API endpoints for issues"
[4]: https://docs.slack.dev/workflows/workflow-steps/ "Workflow steps | Slack Developer Docs"
[5]: https://developers.openai.com/api/docs/guides/agents "Agents SDK | OpenAI API"
[6]: https://developers.openai.com/api/docs/guides/agents/guardrails-approvals "Guardrails and human review | OpenAI API"
[7]: https://openai.github.io/openai-agents-python/tracing/ "Tracing - OpenAI Agents SDK"
[8]: https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issues/ "Jira Cloud Rest API Create Issue"
[9]: https://developers.openai.com/api/docs/guides/evals "Working with evals | OpenAI API"
