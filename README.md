# Dajung Ark

**EN** — A self-hosted knowledge & handover assistant for a university coffee/tea club ("Dajung", SKKU). Retrieval-augmented answers over the club's own documents, with a budget-drafting HITL agent planned next. Runs entirely on a home server; club data never leaves it.

**KO** — 성균관대 커피·차 동아리 '다정'의 자가호스팅 지식·인수인계 어시스턴트. 동아리 자료 기반 RAG 답변을 제공하며, 다음 단계로 예산안 작성 HITL 에이전트를 붙인다. 홈서버에서만 구동 — 동아리 자료는 서버 밖으로 나가지 않는다.

## Status · 현재 상태

**EN** — MVP1 (CLI) in development: ingest → hybrid search (BGE-M3 dense+sparse, RRF) → rerank → cited answers in the terminal. Web serving (FastAPI + Next.js) comes after the CLI is validated.

**KO** — MVP1 (CLI) 개발 중: 인덱싱 → 하이브리드 검색(BGE-M3 dense+sparse, RRF) → 리랭크 → 터미널 인용 답변. 웹 서빙(FastAPI + Next.js)은 CLI 검증 후.

## Stack · 스택

- Python 3.12 · uv · typer CLI · LangGraph
- Qdrant (hybrid dense+sparse) · BGE-M3 / bge-reranker-v2-m3 (CPU)
- Ollama `gemma4:e4b` (local router) · Anthropic API (generation)
- FastAPI + Next.js 15 (serving phase · 서빙 단계)

## Layout · 구조

```
api/app/    core/ ingest/ rag/ llm/ graph/   # Python package
api/tests/                                    # pytest only — no tests in source dirs
prompts/    scripts/    docker/ compose/
data/       # local only, gitignored — real club documents
```

## Quickstart · 빠른 시작

```sh
uv sync
uv run dajung ingest data/      # index local documents · 로컬 문서 인덱싱
uv run dajung ask "질문"         # cited answer in terminal · 인용 포함 답변
uv run pytest                   # quality gate (external services excluded)
```

## Compose Serving · Compose 서빙

```sh
cp .env.example .env              # fill secrets and PUBLIC_HOST before production
docker compose config             # validate caddy-only public ports and env wiring
docker compose up -d --build       # run on the server after docs/SECURITY.md §5.7 gates
```

## Notes · 참고

**EN** — Internal design docs and all club data are intentionally not in this repository. Permission filtering is enforced at retrieval time and re-checked in process; the regression suite (`api/tests/test_permission.py`) gates every merge.

**KO** — 내부 설계 문서와 동아리 자료는 의도적으로 리포에 없다. 권한 필터링은 검색 단계에서 강제되고 프로세스 내에서 재검사되며, 회귀 테스트(`api/tests/test_permission.py`)가 모든 머지를 게이트한다.
