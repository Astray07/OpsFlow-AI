# Human Eval Feedback Follow-up

작성일: 2026-05-11

## 배경

`docs/opsflow-human-eval-2026-05-11.csv` 평가 메모에서 티켓 초안의 내부 필드명, 판단 근거, 확인 질문이 평가자에게 충분히 설명되지 않는 문제가 확인되었다.

특히 다음 문제가 있었다.

- `dataset_or_metric`, `impact_scope`, `required_action`, `low_confidence` 같은 내부 키가 그대로 노출됨
- `누락 정보`가 현재 무엇이 부족한지 설명하지 못함
- `판단 근거`가 왜 필요한 정보인지 연결되지 않음
- 결제 취소 요청에서 마감일을 묻는 질문이 부적절함
- 고객지원 요청에서 조치 의도가 명확한데 `required_action`을 다시 묻는 병목이 있음

## 개선 내용

### 1. 사람용 표시 계층 추가

`src/human_text.py`를 추가해 내부 필드와 판단 트리거를 사람이 읽는 한국어 문장으로 변환한다.

- 누락 필드: `impact_scope` -> `영향 범위: 일부 사용자 문제인지, 전체 요청/고객에 영향을 주는지`
- 판단 근거: `low_confidence` -> `분류 신뢰도가 기준보다 낮습니다 (요청 유형 0.xx, 담당 팀 0.xx, 기준 0.75).`
- 개인정보: `pii_detected` -> `개인정보 또는 식별자가 포함되어 마스킹 후 검토가 필요합니다.`

### 2. 티켓 초안 본문 개선

`src/ticket_builder.py`에서 `추출 필드`, `누락 정보`, `확인 질문`, `판단 근거`를 모두 사람용 문구로 렌더링하도록 변경했다.

기존 JSON 블록 중심 표시를 다음 형식으로 바꿨다.

```text
## 누락 정보
- 영향 범위: 일부 사용자 문제인지, 전체 요청/고객에 영향을 주는지

## 확인 질문
영향 범위가 특정 고객/사용자에 한정되는지, 전체에 영향을 주는지 알려 주세요.
```

### 3. 리뷰 큐 CSV 개선

`src/review_queue.py`에서 `review_reason`, `suggested_question`도 사람이 읽는 문장으로 변환했다.

CSV를 보는 평가자가 내부 트리거를 몰라도 검토 이유와 다음 질문을 이해할 수 있게 했다.

### 4. 결제 취소/환불 승인 질문 개선

`approval_request`의 필수 필드를 조정했다.

- 기존: `approval_target`, `scope_or_amount`, `deadline`
- 변경: `approval_target`, `scope_or_amount`, `approval_owner`

또한 주문번호는 승인 범위/금액으로 보지 않도록 `ORD-*`, `ORDER-*`를 `scope_or_amount` 추출 패턴에서 제거했다.

결과적으로 `REQ-013`은 `deadline` 대신 `scope_or_amount`, `approval_owner`를 누락 정보로 표시한다.

### 5. 고객지원 조치 추론

고객지원 요청에서 고객과 문제 내용이 있고, "안 온다고", "문의", "오류", "상태", "로그인" 같은 지원 맥락이 확인되면 `required_action`을 `문제 원인 확인 및 고객 응대`로 보수적으로 추론한다.

이로써 `REQ-017`처럼 조치 의도가 명확한 요청은 `required_action`을 다시 묻지 않는다.

### 6. 버그/승인 혼동 완화

`REQ-028`처럼 "결재 승인 플로우"라는 도메인 단어 때문에 버그가 승인 요청으로 흔들리는 문제를 줄이기 위해 engineering 팀 키워드에 `에러`, `재현`을 보강했다.

## 검증 결과

실행 명령:

```powershell
pytest -q
ruff check .
python -m src.main run --input data\sample_requests.csv --config config --output outputs\final_improvement_check_2026-05-11 --gold data\labeled_requests.csv --dry-run
```

결과:

- 테스트: 73 passed
- Ruff: all checks passed
- 샘플 파이프라인: 30 requests processed
- QA assertion: 240 passed, 0 failed
- request_type_accuracy: 100.0%
- target_team_accuracy: 100.0%
- priority_accuracy: 100.0%
- risk_level_accuracy: 100.0%
- decision_accuracy: 76.7%
- false_automation_rate: 0.0%
- review_recall: 100.0%

## 주요 케이스 확인

| request_id | 개선 전 문제 | 개선 후 |
| --- | --- | --- |
| REQ-002 | 요약이 원문 반복에 가까움 | `이전 데이터 재요청으로, 데이터 대상과 목적 확인 필요`로 표시 |
| REQ-003 | `impact_scope`가 그대로 노출됨 | `영향 범위`와 설명, 구체 질문으로 표시 |
| REQ-013 | 결제 취소 요청에 마감일을 질문함 | 승인권자, 정책, 처리 범위/금액 확인 질문으로 변경 |
| REQ-017 | 명확한 고객지원 조치도 `required_action`을 다시 물음 | `문제 원인 확인 및 고객 응대`로 추론 |
| REQ-028 | `low_confidence` 이유를 이해하기 어려움 | bug로 안정 분류되어 `ready_for_approval` 처리 |

## 남은 범위

개인정보 위험 등급 세분화는 이번 마무리 범위에서 제외했다. 전화번호, 주문번호, 사람 이름을 모두 같은 review 트리거로 처리하는 현재 정책은 안전하지만, 실제 운영에서는 `privacy risk tiering`을 별도 v2 과제로 다루는 것이 적절하다.
