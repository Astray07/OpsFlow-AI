# Security Notes

작성일: 2026-05-11

## Dotenv Priority

기본 원칙은 운영 안전성을 위해 다음 우선순위를 따릅니다.

```text
프로세스 환경변수 > 프로젝트 .env
```

운영에서는 Kubernetes Secret, AWS Secrets Manager, GitHub Actions secrets처럼 배포 환경이 주입한 값이 디스크 파일보다 신뢰도가 높습니다. 따라서 라이브러리 함수인 `assist_request()`는 `.env`를 직접 로드하거나 기존 환경변수를 덮어쓰지 않습니다.

## Local Override

로컬 개발에서는 Codex나 IDE 상위 프로세스에 오래된 `OPENAI_API_KEY`가 남아 있을 수 있습니다. 이 경우에만 명시적으로 프로젝트 `.env`를 우선합니다.

```bash
python -m src.main run ... --enable-llm-assist --prefer-dotenv
```

또는:

```bash
OPSFLOW_ENV=local
```

지원되는 신호:

```text
--prefer-dotenv
OPSFLOW_ENV=local
OPSFLOW_DOTENV_OVERRIDE=1
```

## Production Guidance

```text
1. 운영 이미지나 배포 패키지에 .env를 포함하지 않습니다.
2. 운영 secret은 프로세스 환경변수 또는 secret manager로 주입합니다.
3. 운영에서는 --prefer-dotenv, OPSFLOW_ENV=local, OPSFLOW_DOTENV_OVERRIDE=1을 사용하지 않습니다.
4. 오류 메시지는 OpenAI API key 형태 문자열을 [REDACTED_OPENAI_API_KEY]로 마스킹합니다.
```
