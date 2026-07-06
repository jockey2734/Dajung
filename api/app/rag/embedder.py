"""Embedding module for Dajung Ark RAG.

Dajung Ark RAG의 임베딩 모듈.
Wraps BGE-M3 to produce dense + sparse vectors for Qdrant hybrid search.
Qdrant 하이브리드 검색에 쓰는 dense + sparse 벡터를 BGE-M3로 생성한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from FlagEmbedding import BGEM3FlagModel

# =============================================================================
# Embedding Model Selection — Dajung Ark   (조사 기준: 2026-05)
# -----------------------------------------------------------------------------
# 기본값(DEFAULT_MODEL)은 BAAI/bge-m3 로 진행한다.
# PoC(dev-process Day 4-5)에서 실제 동아리 자료로 후보들을 직접 비교한 뒤
# 최종 확정한다. 공개 벤치마크 점수는 시작점일 뿐, 본 도메인 데이터로
# 검색 정확도를 측정해 결정한다.
#
# [실험 후보 4분류]
#
# 1) 가장 성능 좋은 모델 — 한국어 검색 특화, 본 사양 구동 가능
#    nlpai-lab/KURE-v1
#    - 고려대 한국어 검색 특화 임베딩. BAAI/bge-m3 기반 fine-tune. 0.6B.
#    - 한국어 retrieval 벤치마크에서 다국어/상용 모델을 상회, 장문 검색 강점.
#    - VRAM 약 1.1GB(fp16). RTX 2070 SUPER에서 구동 가능 — BGE-M3 직접 대안.
#    - 동아리 문서가 사실상 100% 한국어이므로 PoC에서 가장 유력한 경쟁자.
#    - 동급 후보: upskyy/bge-m3-korean (bge-m3 한국어 fine-tune 변형).
#
# 2) 잘 돌아갈 모델 — 안정적 기본값, 본 사양에서 여유 구동  ★ 현재 기본값
#    BAAI/bge-m3
#    - 다국어 70+개 지원. dense + sparse + colbert 벡터 동시 산출.
#    - sparse 벡터를 Qdrant 하이브리드(BM25+Dense)에 그대로 투입 가능 —
#      별도 BM25 인덱서 없이 단일 모델로 하이브리드 검색 구성.
#    - 0.6B, VRAM 약 1.1GB(fp16). 한국어 성능도 다국어 모델 중 최상급.
#
# 3) 빠른 모델 — 저사양/저지연 우선, 정확도 일부 양보
#    jhgan/ko-sroberta-multitask (~110M)
#    또는 Qwen/Qwen3-Embedding-0.6B, intfloat/multilingual-e5-small
#    - 110M~600M. CPU에서도 빠름. 대량 인덱싱·실시간성 우선 시 유리.
#    - 단 한국어 검색 정확도는 KURE-v1 / BGE-M3 대비 눈에 띄게 낮음.
#    - 본 프로젝트는 월 ~100건 규모라 속도보다 정확도 우선 — 비권장.
#
# 4) 안 돌아갈 사양이지만 성능 최고 — 참고용 (2070 SUPER 8GB 불가)
#    Qwen/Qwen3-Embedding-8B    (MTEB v2 약 70.6, 8B 파라미터)
#    Microsoft Harrier-OSS-v1 27B (MTEB v2 약 74.3, 27B)
#    - fp16 기준 VRAM 16~54GB+ 필요. 본 서버로는 구동 불가.
#    - API 대안(로컬 불가, 품질 최상위): Google Gemini Embedding 2,
#      Cohere embed-v4, Voyage voyage-3-large.
#      단 임베딩 시 텍스트가 외부로 전송됨 → 동아리 내부 자료
#      프라이버시 원칙상 비권장. 자가호스팅 결정과도 상충.
#
# [결론] 1번(KURE-v1) vs 2번(BGE-M3) PoC 비교 → 우세한 쪽 확정.
#        한국어 단일 도메인이라 KURE-v1이 이길 가능성이 높지만,
#        BGE-M3의 sparse 벡터 하이브리드 이점도 함께 저울질한다.
#        (KURE-v1도 bge-m3 기반이라 sparse 산출 가능 — PoC에서 확인.)
# =============================================================================

DEFAULT_MODEL = "BAAI/bge-m3"


@dataclass
class EmbeddingResult:
    """Single text's dense + sparse representation.

    한 텍스트의 dense + sparse 표현.
    """

    dense: list[float]
    sparse: dict[int, float]  # token_id -> weight


@lru_cache(maxsize=1)
def _load_model(model_name: str = DEFAULT_MODEL) -> BGEM3FlagModel:
    """Load the embedding model once and cache it.

    임베딩 모델을 한 번만 로드해 캐시한다.
    """
    # CPU-only by design — the GPU is reserved for Ollama (ARCHITECTURE.md §7).
    # 설계상 CPU 전용 — GPU는 Ollama가 전담한다 (ARCHITECTURE.md §7).
    # fp16 is a GPU optimization; keep fp32 on CPU (decided 2026-07-02).
    # fp16은 GPU 최적화라 CPU에서는 fp32를 쓴다 (2026-07-02 확정).
    return BGEM3FlagModel(model_name, use_fp16=False, devices="cpu")


class Embedder:
    """Encode text into dense + sparse vectors for Qdrant hybrid search.

    Qdrant 하이브리드 검색용 dense + sparse 벡터로 텍스트를 인코딩한다.
    """

    def __init__(self, model_name: str = DEFAULT_MODEL) -> None:
        self._model = _load_model(model_name)

    def encode(self, texts: list[str]) -> list[EmbeddingResult]:
        """Encode a batch of texts (ingest path).

        텍스트 배치를 인코딩한다 (인덱싱 경로).
        """
        out = self._model.encode(
            texts,
            return_dense=True,
            return_sparse=True,
            return_colbert_vecs=False,
        )
        results: list[EmbeddingResult] = []
        for dense, sparse in zip(out["dense_vecs"], out["lexical_weights"], strict=True):
            results.append(
                EmbeddingResult(
                    dense=dense.tolist(),
                    sparse={int(k): float(v) for k, v in sparse.items()},
                )
            )
        return results

    def encode_query(self, query: str) -> EmbeddingResult:
        """Encode a single query (retrieval path).

        단일 쿼리를 인코딩한다 (검색 경로).
        """
        return self.encode([query])[0]
