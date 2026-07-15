# Dajung Ark — operator shortcuts over docker compose / uv / dajung CLI.
# 다정 Ark — docker compose / uv / dajung CLI 단축 명령. 상세: ~/CLI.md
#
# Server ops need the compose stack up (make up). Local dev commands (ingest/
# ask/stats/test/lint) run via uv on the host.
# 서버 명령은 compose 기동(make up) 후 사용. 로컬 개발 명령(ingest/ask/stats/
# test/lint)은 호스트 uv로 실행한다.

.DEFAULT_GOAL := help
.PHONY: help up down ps logs router invite invites revoke ingest dry ask stats test lint web-test check

help: ## 명령 목록
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[1m%-10s\033[0m %s\n", $$1, $$2}'

## ── 서버 (docker compose) ────────────────────────────────────────────────

up: ## 전체 스택 기동 (.env 먼저 채울 것)
	docker compose up -d --build

down: ## 전체 스택 중지
	docker compose down

ps: ## 컨테이너 상태
	docker compose ps

logs: ## 로그 팔로우 (S=서비스명 지정 가능: make logs S=api)
	docker compose logs -f --tail=100 $(S)

router: ## 라우터 모델 받기 (최초 1회)
	docker compose exec ollama ollama pull gemma4:e4b

## ── 통과번호 (가입 게이트, 서버에서) ─────────────────────────────────────

invite: ## 통과번호 발급: make invite NOTE="서지선" [DAYS=7]
	docker compose exec api dajung invite create --note "$(NOTE)" --days $(or $(DAYS),7)

invites: ## 통과번호 목록·상태
	docker compose exec api dajung invite list

revoke: ## 통과번호 폐기: make revoke ID=1a2b3c4d
	@test -n "$(ID)" || (echo 'usage: make revoke ID=<ID 앞 8자>'; exit 1)
	docker compose exec api dajung invite revoke $(ID)

## ── RAG (로컬 uv) ────────────────────────────────────────────────────────

ingest: ## 인덱싱: make ingest [DIR=data/knowledge]
	uv run dajung ingest $(or $(DIR),data/knowledge)

dry: ## 인덱싱 예행연습(업서트 없음): make dry [DIR=data]
	uv run dajung ingest $(or $(DIR),data) --dry-run

ask: ## 터미널 질문: make ask Q="개완 우리는 법"
	@test -n "$(Q)" || (echo 'usage: make ask Q="질문"'; exit 1)
	uv run dajung ask "$(Q)"

stats: ## 인덱스 통계
	uv run dajung stats

## ── 품질 게이트 (CI와 동일) ──────────────────────────────────────────────

test: ## 백엔드 테스트
	uv run pytest

lint: ## ruff + mypy strict
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy .

web-test: ## 프론트 테스트+타입체크
	cd web && pnpm exec tsc --noEmit && pnpm test

check: lint test ## lint + test 한 번에
