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
    csv_path: Path = Path("다정_파일목록.csv")
    manifest_path: Path = Path("data/.ingest_manifest.json")
    prompts_dir: Path = Path("prompts")

    # --- anthropic ---
    anthropic_api_key: str = ""
    model_haiku: str = "claude-haiku-4-5"
    model_sonnet: str = "claude-sonnet-5"
    # Used from MVP2 (budget HITL) onward.
    # MVP2(예산 HITL)부터 사용한다.
    model_opus: str = "claude-opus-4-8"
    max_tokens_generate: int = 2048
    max_tokens_header: int = 200

    # --- ollama ---
    ollama_base_url: str = "http://localhost:11434"
    router_model: str = "gemma4:e4b"
    router_timeout_s: float = 20.0

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
    max_retries: int = 1

    # --- chunking (chars, not tokens — 한국어 기준 근사) ---
    chunk_max_chars: int = 1600
    chunk_min_chars: int = 200
    chunk_overlap_chars: int = 300
    xlsx_row_block: int = 30


settings = Settings()
