# Agent-Assisted Human-Eval Surrogate

작성일: 2026-05-11

후속 반영: `docs/human_eval_form_update_2026-05-11.md`에서 data request 확인 질문, person-like masking, 사람 평가용 HTML 도구를 보완했습니다.

## 성격

이 문서는 실제 사람 참여자가 수행한 human-eval이 아닙니다. Codex가 `docs/human_eval_template.md`의 기준으로 rule-only 산출물과 LLM-assist 산출물을 비교 채점한 예비 평가입니다.

포트폴리오에는 다음처럼 표기합니다.

```text
agent-assisted rubric review, not a replacement for independent human evaluation
```

## 실행 명령

```bash
python -m src.main run --input data/sample_requests.csv --config config --output outputs/agent_eval_rule_only_2026-05-11 --dry-run --gold data/labeled_requests.csv
python -m src.main run --input data/sample_requests.csv --config config --output outputs/agent_eval_llm_assist_2026-05-11 --dry-run --gold data/labeled_requests.csv --enable-llm-assist --prefer-dotenv
```

## 실행 결과

```text
rule_only:
  processed: 30

llm_assist:
  processed: 30
  llm_used: 25
  llm_assist_not_needed: 5
  llm_errors: 0

QA assertion:
  total_assertions: 240
  passed: 240
  failed: 0
```

티켓 초안 수:

| source_decision | count |
| --- | ---: |
| draft_only | 3 |
| ready_for_approval | 5 |
| review_required | 21 |

## 표본

review_required 중심으로 10건을 선정했습니다.

```text
REQ-002, REQ-003, REQ-005, REQ-007, REQ-009,
REQ-013, REQ-017, REQ-020, REQ-024, REQ-028
```

선정 이유:

```text
1. 정보 부족 요청 포함
2. 고객/장애/데이터/권한/환불/PII 케이스 포함
3. structured LLM assist가 실제로 사용된 요청 중심
```

## 채점 기준

각 항목은 `docs/human_eval_template.md` 기준으로 1, 3, 5점 중 하나로 채점했습니다.

| criterion | 의미 |
| --- | --- |
| factuality | 원문에 없는 사실을 만들지 않았는지 |
| actionability | 담당자가 다음 행동을 바로 알 수 있는지 |
| completeness | 증상, 범위, 요청 행동, 누락 질문이 충분한지 |
| privacy_safety | PII masking 경계가 유지되는지 |
| reviewer_effort | 사람이 다시 써야 하는 양이 줄었는지 |

## 상세 채점

Variant A는 rule-only, Variant B는 LLM-assist입니다.

| request_id | variant | factuality | actionability | completeness | privacy_safety | reviewer_effort | notes |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| REQ-002 | A | 5 | 3 | 3 | 5 | 3 | 데이터 대상/목적/마감일 누락을 잡았지만 본문에 확인 질문이 없음 |
| REQ-002 | B | 5 | 3 | 3 | 5 | 3 | 제목/요약은 더 자연스럽지만 본문 구조는 A와 거의 동일 |
| REQ-003 | A | 5 | 5 | 5 | 5 | 5 | 영향 범위 누락과 후보 충돌이 잘 드러남 |
| REQ-003 | B | 5 | 5 | 5 | 5 | 5 | 제목/요약이 더 명확하지만 구조적 정보량은 동일 |
| REQ-005 | A | 5 | 5 | 5 | 5 | 5 | 고객명만 있는 긴급 요청에서 누락 필드를 잘 제시 |
| REQ-005 | B | 5 | 5 | 5 | 5 | 5 | 표현은 자연스러우나 실무 판단 정보는 동일 |
| REQ-007 | A | 5 | 5 | 5 | 3 | 5 | 권한 요청 high risk는 잘 잡음. 다만 `김대리님` person-like 값은 남음 |
| REQ-007 | B | 5 | 5 | 5 | 3 | 5 | A와 같은 privacy limitation. person masking은 v2로 남아 있음 |
| REQ-009 | A | 5 | 5 | 5 | 5 | 5 | 짧은 결제 장애 요청에서 고객/영향 범위 누락 질문이 적절함 |
| REQ-009 | B | 5 | 5 | 5 | 5 | 5 | 제목은 더 설명적이나 본문 점수 차이는 없음 |
| REQ-013 | A | 5 | 5 | 5 | 5 | 5 | 주문번호가 `[ORDER_ID]`로 마스킹되고 high risk가 표시됨 |
| REQ-013 | B | 5 | 5 | 5 | 5 | 5 | 제목이 더 자연스럽고 PII 경계 유지 |
| REQ-017 | A | 5 | 5 | 5 | 5 | 5 | required_action 누락을 명확히 표시 |
| REQ-017 | B | 5 | 5 | 5 | 5 | 5 | 제목/요약 개선 외 본문 정보량은 동일 |
| REQ-020 | A | 5 | 3 | 3 | 5 | 3 | 데이터/목적/마감일 누락은 잡지만 질문 문장이 없음 |
| REQ-020 | B | 5 | 3 | 3 | 5 | 3 | LLM 제목은 더 좋지만 본문 템플릿 한계는 동일 |
| REQ-024 | A | 5 | 5 | 5 | 5 | 5 | 전화번호가 `[PHONE]`으로 유지되고 PII review가 표시됨 |
| REQ-024 | B | 5 | 5 | 5 | 5 | 5 | 제목에서 `[PHONE]` 노출 없이 자연스럽게 요약함 |
| REQ-028 | A | 5 | 5 | 5 | 5 | 5 | 승인 플로우 500 에러의 재현 조건과 영향 범위가 충분함 |
| REQ-028 | B | 5 | 5 | 5 | 5 | 5 | 제목/요약이 더 구체적이나 본문 점수 차이는 없음 |

## 평균 점수

| variant | factuality | actionability | completeness | privacy_safety | reviewer_effort |
| --- | ---: | ---: | ---: | ---: | ---: |
| rule-only | 5.0 | 4.6 | 4.6 | 4.8 | 4.6 |
| LLM-assist | 5.0 | 4.6 | 4.6 | 4.8 | 4.6 |

## 해석

LLM-assist는 제목과 요약의 자연스러움은 개선했습니다. 특히 `REQ-013`, `REQ-024`, `REQ-028`처럼 PII 또는 긴 문장이 포함된 요청에서 사람이 읽기 쉬운 제목을 만들었습니다.

하지만 현재 `ticket_builder.py`가 대부분의 본문을 템플릿 섹션으로 재구성하므로, LLM이 만든 `suggested_ticket_body`와 `suggested_clarification`이 최종 티켓 본문 개선으로 충분히 반영되지 않습니다. 이 때문에 루브릭 평균 점수는 rule-only와 동일하게 나왔습니다.

핵심 결론:

```text
1. structured LLM assist는 정상 호출되고 오류 없이 동작했다.
2. LLM은 제목/요약 품질을 개선한다.
3. 현재 티켓 템플릿 구조에서는 LLM 개선 효과가 reviewer_effort 점수로 크게 드러나지 않는다.
4. privacy_safety는 전화번호/주문번호 기준으로는 통과하지만, person-like 값은 v2 과제로 남는다.
```

## Blocker / Follow-up

### 1. LLM clarification을 티켓 본문에 반영

`data_request` 템플릿은 `suggested_next_question` 섹션이 없어 `REQ-002`, `REQ-020`에서 확인 질문이 본문에 나오지 않습니다.

권장:

```text
1. NormalizedRequest에 suggested_clarification 필드를 추가하거나
2. ticket_builder가 llm_assist trace의 suggested_clarification을 사용할 수 있게 구조 변경
3. 모든 request type 템플릿에 suggested_next_question 섹션 포함
```

### 2. Person-like masking 정책 결정

`REQ-007`의 `김대리님`은 현재 정책상 masking하지 않습니다. 내부 운영용이면 허용 가능하지만, 외부 공유용 masked export라면 person masking v2를 앞당기는 것이 안전합니다.

### 3. 실제 human-eval 필요

이 문서는 독립 사람 평가가 아닙니다. 포트폴리오 최종본에는 최소 1명의 외부 평가자가 같은 표본을 10~20분 내로 채점한 결과를 별도로 남기는 것이 좋습니다.
