# Agent Validation Prompt

다른 검증 에이전트에게 아래 프롬프트를 전달해 주세요.

```text
E:\AI\OpsFlow AI 프로젝트를 독립적으로 검증해 주세요.

검증 원칙:
1. 기획서 `OpsFlow AI 프로젝트 기획서.md`를 우선 기준으로 삼아 주세요.
2. 응답은 존대로 작성해 주세요.
3. 보안상 `.env`의 실제 값은 출력하지 말고, 키 존재 여부와 설정명 일치 여부만 확인해 주세요.
4. 코드 변경은 하지 말고 read-only 검증만 해 주세요.
5. 발견 사항은 High / Medium / Low로 분류하고, 파일 경로와 근거를 함께 적어 주세요.

필수 실행:
- python -m pytest
- python -m ruff check src tests
- python -m src.main run --input data/sample_requests.csv --config config --output outputs/agent_validation --dry-run --gold data/labeled_requests.csv
- python -m src.main run --input data/external_seed_samples.csv --config config --output outputs/agent_validation_external_seed --dry-run --gold data/external_seed_labeled_requests.csv

필수 확인:
1. sample baseline 지표
   - request_type/team/priority/risk accuracy
   - decision_accuracy
   - false_automation_rate
   - over_automation_rate
   - review_recall
   - QA assertion failures

2. external seed 평가
   - data/external_seed_samples.csv 8건과 data/external_seed_labeled_requests.csv 비교 결과
   - synthetic-only rule tuning이 external seed에도 과적합 없이 동작하는지

3. 보안/PII 경계
   - LLM 입력, execution_log, ticket body, generated summary, extracted fields에서 PII masking이 유지되는지
   - outputs 하위에 실제 OpenAI API key 형태 문자열이 남는지
   - `.env.example`에 실제 키가 없는지

4. Config-driven 원칙
   - field extraction regex가 config/extraction_rules.yml에서 관리되는지
   - risk side_effect와 matching_semantics가 코드에서 실제로 반영되는지
   - review action priority가 config/review_policy.yml에서 관리되는지

5. Fail-soft 처리
   - 단일 요청 처리 실패 시 batch 전체가 중단되지 않고 processing_status=failed로 남는지

6. LLM assist human-eval 상태
   - docs/human_eval_template.md와 docs/human_eval_run_2026-05-11.md를 검토해 주세요.
   - 현재 LLM run이 invalid_api_key로 실패한 경우, 이것을 blocker로 볼지 operational note로 볼지 판단해 주세요.

보고서 형식:
1. 실행 결과 요약
2. 발견한 문제 목록
3. 추가 테스트/평가 보강 제안
4. 전반적인 완료도 판단
5. 수정이 꼭 필요한 최소 패치 범위
```
