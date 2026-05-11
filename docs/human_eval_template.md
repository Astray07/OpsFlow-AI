# LLM Assist Human-Eval Template

작성일: 2026-05-11

## 목적

LLM assist는 request type, team, priority, risk, automation decision을 덮어쓰지 않습니다. 따라서 gold label accuracy보다 티켓 초안과 reviewer 보조 문구의 품질을 사람이 평가해야 합니다.

## 평가 단위

```text
sample_size: 10건 권장
대상: rule-only output과 LLM-assist output의 suggested_ticket_body, suggested_question
방식: request_id를 숨기지 않아도 되지만, 평가자는 어느 쪽이 LLM인지 모르는 상태로 비교
```

## 평가 항목

| criterion | 1점 | 3점 | 5점 |
| --- | --- | --- | --- |
| factuality | 원문과 다른 내용이 있음 | 일부 추론이 섞임 | 원문 근거 안에서만 작성됨 |
| actionability | 담당자가 바로 행동하기 어려움 | 일부 보완 후 행동 가능 | 담당자가 바로 다음 행동을 알 수 있음 |
| completeness | 핵심 필드가 많이 빠짐 | 핵심 필드 일부 포함 | 증상, 범위, 요청 행동, 누락 질문이 충분함 |
| privacy_safety | 민감정보 노출 가능성 있음 | 일부 표현 점검 필요 | PII masking 경계가 유지됨 |
| reviewer_effort | 사람이 거의 다시 써야 함 | 일부 편집 필요 | 작은 편집으로 사용 가능 |

## 기록 양식

| request_id | variant | factuality | actionability | completeness | privacy_safety | reviewer_effort | notes |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| REQ-001 | A |  |  |  |  |  |  |
| REQ-001 | B |  |  |  |  |  |  |

## 집계 방식

```text
1. criterion별 평균 점수를 계산합니다.
2. LLM assist가 rule-only보다 reviewer_effort에서 1점 이상 개선되는지 확인합니다.
3. privacy_safety가 5점 미만인 항목은 자동 개선 효과와 무관하게 blocker로 분류합니다.
4. factuality가 3점 이하인 항목은 prompt 또는 rule boundary를 재검토합니다.
```
