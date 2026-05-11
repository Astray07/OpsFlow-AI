# External Seed Collection Notes

작성일: 2026-05-11

## 목적

synthetic 샘플만으로 rule을 조정할 때 생길 수 있는 자기확증 편향을 줄이기 위해 공개 이슈에서 업무 요청 패턴을 수집했습니다. 원문을 그대로 평가 데이터로 복사하지 않고, OpsFlow AI의 입력 형식에 맞게 익명화된 paraphrase만 `data/external_seed_requests.csv`에 기록했습니다.

## 수집 기준

```text
1. 공개 GitHub issue 또는 discussion URL만 사용한다.
2. 개인 식별 정보, 계정명, 토큰, 구체 조직 정보는 데이터에 넣지 않는다.
3. raw_text_pattern은 원문 복사가 아니라 업무 요청 패턴 요약으로 작성한다.
4. source_url을 남겨 향후 라벨 확장 시 재검토할 수 있게 한다.
```

## 수집 결과

| seed_id | source | mapped pattern |
| --- | --- | --- |
| EXT-001 | OpenSearch Dashboards issue #10439 | dashboard 500 error bug |
| EXT-002 | Metabase issue #14508 | login failure customer support |
| EXT-003 | Apache Superset issue #32552 | embedded dashboard permission failure |
| EXT-004 | AG Grid issue #3842 | CSV/Excel export support request |
| EXT-005 | Grafana issue #74891 | dashboard panel filtering feature request |
| EXT-006 | PostHog issue #15999 | dashboard filter propagation feature request |
| EXT-007 | Wazuh issue #32193 | dashboard filter and restricted access request |
| EXT-008 | Apache Superset issue #25870 | embedded dashboard 403 support case |

## 한계

```text
1. 현재 외부 seed 라벨과 config 보강은 같은 작성자가 수행했습니다.
2. seed 관찰 후 403/Forbidden, dashboard filter, access permission 표현을 config에 추가했으므로 train-test leakage 가능성을 배제할 수 없습니다.
3. 따라서 external seed 8건 100%는 OOD generalization이 아니라 in-distribution regression smoke test로만 해석합니다.
4. 공개 issue는 개발자 커뮤니티 표현이 많아 실제 사내 업무 요청보다 기술적으로 상세할 수 있습니다.
5. v0.3에서는 rule을 freeze한 뒤 신규 seed 30~50건을 별도 라벨러가 라벨링해 독립 평가합니다.
```
