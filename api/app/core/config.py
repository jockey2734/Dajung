"""Central settings for Dajung Ark.

Dajung Ark의 중앙 설정.
Every tunable lives here — no magic numbers anywhere else (Dajung.md §8.1).
모든 조정값은 여기에만 둔다 — 다른 곳에 매직 넘버 금지 (Dajung.md §8.1).
"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration, loaded from env vars with the DAJUNG_ prefix.

    DAJUNG_ 접두사 환경변수에서 로드하는 런타임 설정.
    """

    model_config = SettingsConfigDict(env_prefix="DAJUNG_", env_file=".env", extra="ignore")

    # --- paths ---
    data_dir: Path = Path("data")
    # File inventory lives under data/ so the api container sees it through the
    # existing data mount; the repo root is not mounted (webapp-spec S31 follow-up).
    # 파일 목록은 data/ 아래에 둔다 — api 컨테이너는 기존 data 마운트로만 볼 수 있고
    # 레포 루트는 마운트되지 않는다 (webapp-spec S31 후속).
    csv_path: Path = Path("data/다정_파일목록.csv")
    manifest_path: Path = Path("data/.ingest_manifest.json")
    prompts_dir: Path = Path("prompts")
    upload_dir: Path = Path("data/uploads")

    # --- anthropic ---
    anthropic_api_key: str = ""
    model_haiku: str = "claude-haiku-4-5"
    model_sonnet: str = "claude-sonnet-5"
    # Used from MVP2 (budget HITL) onward.
    # MVP2(예산 HITL)부터 사용한다.
    model_opus: str = "claude-opus-5"
    max_tokens_generate: int = 2048
    max_tokens_header: int = 200

    # --- ollama ---
    ollama_base_url: str = "http://localhost:11434"
    router_model: str = "gemma4:e4b"
    router_timeout_s: float = 20.0

    # --- auth ---
    # Set via .env: DAJUNG_JWT_SECRET=$(openssl rand -hex 32). Empty = refuse to sign.
    # .env로 주입: DAJUNG_JWT_SECRET=$(openssl rand -hex 32). 비어 있으면 서명 거부.
    jwt_secret: str = ""
    # 6-month absolute expiry, no sliding renewal (SECURITY.md §3).
    # 6개월 absolute 만료, 슬라이딩 갱신 없음 (SECURITY.md §3).
    jwt_expires_days: int = 180
    bcrypt_rounds: int = 12
    # Login lockout: 5 failures within 5 min locks the email for 1 h (SECURITY.md §3).
    # 로그인 잠금: 5분 내 5회 실패 시 해당 이메일 1시간 잠금 (SECURITY.md §3).
    login_max_fails: int = 5
    login_window_s: int = 300
    login_lock_s: int = 3600
    # Per-IP request budget on auth endpoints (slowapi format).
    # 인증 엔드포인트의 IP당 요청 예산 (slowapi 형식).
    rate_limit_ip: str = "20/minute"

    # --- chat serving ---
    # Daily question budget per user (2026-07-07 decision: 20).
    # 사용자당 일일 질문 한도 (2026-07-07 결정: 20회).
    daily_chat_limit: int = 20
    # SSE pseudo-token chunk size in chars (whole answers re-chunked).
    # SSE 유사 토큰 조각 크기(문자) — 통째 답변을 재분할한다.
    sse_chunk_chars: int = 60
    # Health-probe timeout for qdrant/ollama.
    # qdrant/ollama 헬스 프로브 타임아웃.
    health_probe_timeout_s: float = 2.0
    # Uploads are conversation attachments, not knowledge-base ingestion (S2).
    # 업로드는 대화 첨부이며 지식베이스 ingest가 아니다 (S2).
    upload_max_file_bytes: int = 20 * 1024 * 1024
    upload_max_files: int = 5
    attachment_max_chars: int = 12000
    # Same-session prompt context bounds (webapp-spec S24).
    # 같은 세션 프롬프트 맥락 상한 (webapp-spec S24).
    history_max_messages: int = 10
    history_message_max_chars: int = 500
    history_total_max_chars: int = 4000
    # Anthropic server-side web search cost/latency bound (webapp-spec S26).
    # Anthropic 서버측 웹 검색 비용·지연 상한 (webapp-spec S26).
    web_search_max_uses: int = 3
    # Conditional exchange-rate lookup via 한국수출입은행 오픈API (ADR-028, webapp-spec S30).
    # 한국수출입은행 오픈API 조건부 환율 조회 (ADR-028, webapp-spec S30).
    # Key comes from .env only: DAJUNG_KOREAEXIM_API_KEY. Empty = lookup reports no_key.
    # 키는 .env로만 주입: DAJUNG_KOREAEXIM_API_KEY. 비어 있으면 조회가 no_key를 보고한다.
    koreaexim_api_key: str = ""
    fx_timeout_s: float = 5.0
    # Quotes post once per business day; 1 h TTL keeps well under the 1,000/day key cap.
    # 고시는 영업일 1회라 1시간 TTL이면 키당 일 1,000회 한도에 한참 못 미친다.
    fx_cache_ttl_s: int = 3600
    # Weekday attempts (weekends skipped, uncounted) when walking back to the latest quote.
    # 10 clears a 추석-length holiday from any weekday after it (S30 2nd correction 11).
    # 최신 고시를 찾아 역행할 평일 시도 횟수 (주말은 건너뛰고 세지 않음).
    # 10이면 추석급 연휴 직후 어느 평일에 물어도 닿는다 (S30 2차 정정 11).
    fx_lookback_days: int = 10
    # Personal-use customs de minimis in USD: all origins vs US-origin (운하 확정 2026-07-26).
    # 개인 자가사용 면세 한도(USD): 일반 vs 미국발 (운하 확정 2026-07-26).
    fx_de_minimis_usd: int = 150
    fx_de_minimis_usd_us: int = 200
    # Weekly user-memory batch input/output bounds (webapp-spec S6).
    # 주간 사용자 메모리 배치 입력/출력 한계 (webapp-spec S6).
    memory_input_chars: int = 30000
    memory_output_chars: int = 1000
    max_tokens_memory: int = 1000

    # --- database ---
    # Dev default only — production URL comes from .env (DAJUNG_DATABASE_URL).
    # 개발용 기본값 — 운영 URL은 .env(DAJUNG_DATABASE_URL)에서 주입한다.
    database_url: str = "postgresql+asyncpg://dajung:dajung@localhost:5432/dajung"

    # --- qdrant ---
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""
    collection: str = "dajung"

    # --- embedding / rerank ---
    embed_model: str = "BAAI/bge-m3"
    rerank_model: str = "BAAI/bge-reranker-v2-m3"
    embed_batch_size: int = 16
    rerank_batch_size: int = 8

    # --- retrieval tuning ---
    retrieve_limit: int = 20
    rerank_top_k: int = 5
    rerank_threshold: float = 0.5
    max_retries: int = 2

    # --- chunking (chars, not tokens — 한국어 기준 근사) ---
    chunk_max_chars: int = 1600
    chunk_min_chars: int = 200
    chunk_overlap_chars: int = 300
    xlsx_row_block: int = 30


settings = Settings()
