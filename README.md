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

## Local development · 로컬 개발

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
make dry DIR=data/knowledge        # parse without Qdrant upserts · Qdrant 업서트 없이 파싱
make ingest DIR=data/knowledge     # index from inside the API container · API 컨테이너에서 인덱싱
make stats                         # inspect the server index · 서버 인덱스 통계
make ask Q="개완 우리는 법"        # ask through the server stack · 서버 스택으로 질문
```

**EN** — Compose bind-mounts the host `./data` directory read-write at `/app/data` in the
API container. Admin uploads, recoverable `.trash` moves, and `.ingest_manifest.json` therefore
remain on the host across API restarts. The `make` RAG commands require the Compose stack; use
the host `uv run dajung ...` commands above for local development.

**KO** — Compose는 호스트 `./data`를 API 컨테이너의 `/app/data`에 읽기·쓰기 방식으로
마운트한다. 따라서 관리자 업로드, 복구 가능한 `.trash` 이동, `.ingest_manifest.json`은
API 재시작 후에도 호스트에 남는다. `make` RAG 명령은 Compose 스택이 필요하며 로컬 개발은
위의 호스트 `uv run dajung ...` 명령을 사용한다.

### First administrator · 최초 관리자

**EN** — On a fresh database, issue one invitation and complete web signup for the initial
account. Then claim the one-time owner slot from the server shell. After that, invite the
current president 서지선 and appoint that signed-up account as president. Replace the example
emails below; never record the plaintext invitation codes in files or logs.

**KO** — fresh DB에서는 통과번호 하나를 발급해 최초 계정의 웹 가입을 마친 뒤 서버 셸에서
1회용 owner 자리를 승격한다. 이후 현 회장 서지선을 초대해 가입을 마치고 president로 임명한다.
아래 이메일은 실제 가입 이메일로 바꾸며, 통과번호 평문은 파일이나 로그에 기록하지 않는다.

```sh
docker compose exec api dajung invite create --note "운하"
# Complete web signup as owner@example.com. · owner@example.com으로 웹 가입 완료
docker compose exec api dajung owner claim owner@example.com
docker compose exec api dajung invite create --note "서지선"
# Complete web signup as president@example.com. · president@example.com으로 웹 가입 완료
docker compose exec api dajung president set president@example.com
```

## Notes · 참고

**EN** — Internal design docs and all club data are intentionally not in this repository. Permission filtering is enforced at retrieval time and re-checked in process; the regression suite (`api/tests/test_permission.py`) gates every merge.

**KO** — 내부 설계 문서와 동아리 자료는 의도적으로 리포에 없다. 권한 필터링은 검색 단계에서 강제되고 프로세스 내에서 재검사되며, 회귀 테스트(`api/tests/test_permission.py`)가 모든 머지를 게이트한다.
