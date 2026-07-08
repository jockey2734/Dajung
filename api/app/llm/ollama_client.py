"""Local LLM client for Dajung Ark — Ollama backend.

Dajung Ark의 로컬 LLM 클라이언트 — Ollama 백엔드.
Used for the router/judge nodes and optional fully-local generation.
라우터/판정 노드, 그리고 선택적 완전 로컬 생성에 쓴다.
"""

from __future__ import annotations

import os

import httpx

# ==========================================================================
# Local Model Registry — Dajung Ark   (조사 기준: 2026-05)
# --------------------------------------------------------------------------
# 하드웨어: RTX 2070 SUPER 8GB VRAM (업그레이드 계획 없음).
# 서빙: Ollama. vLLM 미사용 — 다중 동시요청 처리량용 엔진이라 본 규모
#       (운영진 5-6명)에 불필요하고, Turing 세대 GPU 지원도 제한적이다.
# 원칙: 8GB 한계상 한 번에 한 모델만 GPU에 상주한다. Ollama가 자동으로
#       로드/언로드한다. 모델 비교는 순차 스왑으로 한다 (동시 상주 불가).
# 주의: 아래 태그는 시작점이다. 정확한 최신 태그는 ollama.com/library 에서
#       확인하고 .env 로 덮어쓴다.
#
# [라우터 / 판정용 — 작고 빠른 모델]
#   gemma4:e4b   Gemma 4 E4B. 총 8B / 유효 4.5B. Q4 약 5GB. 2026-04 출시.
#                현재 기본 라우터(Gemma 2 9B)의 신형 대체로 권장.
#   gemma4:e2b   더 작고 빠름 (총 5B / 유효 2B). 라우팅만이면 충분.
#   qwen3:4b     Qwen3 4B. 빠른 대안.
#
# [생성용 8B급 — PoC 실험 대상 3종]
#   gemma4:e4b   위와 동일 모델. 라우팅 + 생성 겸용 가능.
#   qwen3:8b     Qwen3(3.0) 8B. Q4 약 5GB. Ollama에서 바로 동작 확인됨.
#   llama3.1:8b  Llama 3.1 8B. Q4 약 5GB. Llama 계열의 실행 가능 옵션.
#
# [최신이지만 주의 — 당장 도입 보류]
#   qwen3.5:9b   Qwen 3.5 9B (2026-03, 소형군 최상위). Q4 약 6.6GB —
#                8GB에서 KV 캐시 여유가 ~1.4GB로 빠듯(짧은 컨텍스트만).
#                또한 현재 Qwen 3.5 GGUF는 Ollama 호환 이슈(비전 mmproj
#                파일 분리)가 있다. Ollama 정식 지원 확인 후 도입한다.
#
# [본 사양에서 구동 불가 — 참고]
#   Llama 4 (Scout 109B MoE 등)  전부 대형 MoE, 60GB+ 필요. 8B 변형 없음.
#   gemma4:26b / gemma4:31b      18~20GB+ 필요.
#   qwen3.5:27b 이상             너무 큼.
#
# [결론] 8B급 실험 3종: gemma4:e4b / qwen3:8b / llama3.1:8b.
#        PoC에서 한국어 응답 품질·속도를 비교한 뒤 LOCAL_GEN_MODEL 확정.
#        라우터는 gemma4:e4b 로 업그레이드 권장 (현 gemma2:9b 대비 신형·효율).
# ==========================================================================

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://ollama:11434")

# Default models — override via .env.
# 기본 모델 — .env 로 덮어쓴다.
ROUTER_MODEL = os.environ.get("ROUTER_MODEL", "gemma4:e4b")
LOCAL_GEN_MODEL = os.environ.get("LOCAL_GEN_MODEL", "qwen3:8b")

# 8B-class candidates — swap one at a time to compare in PoC.
# 8B급 후보 — PoC에서 한 번에 하나씩 스왑해 비교한다.
LOCAL_MODEL_CANDIDATES = ["gemma4:e4b", "qwen3:8b", "llama3.1:8b"]


class OllamaClient:
    """Thin async client over Ollama's chat API.

    Ollama chat API에 대한 얇은 async 클라이언트.
    """

    def __init__(self, host: str = OLLAMA_HOST) -> None:
        self._host = host.rstrip("/")

    async def chat(
        self,
        model: str,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.6,
        keep_alive: str = "5m",
        format: str | None = None,
    ) -> str:
        """Run a non-streaming chat completion on a local model.

        로컬 모델로 비스트리밍 채팅 완성을 실행한다.
        keep_alive controls how long Ollama keeps the model in VRAM.
        keep_alive은 Ollama가 모델을 VRAM에 유지하는 시간을 정한다.
        format="json" forces structured output (router node).
        format="json"은 구조화 출력을 강제한다 (라우터 노드).
        """
        body: dict[str, object] = {
            "model": model,
            "messages": messages,
            "stream": False,
            "keep_alive": keep_alive,
            "options": {"temperature": temperature},
        }
        if format is not None:
            body["format"] = format
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(f"{self._host}/api/chat", json=body)
            resp.raise_for_status()
            content: str = resp.json()["message"]["content"]
            return content

    async def unload(self, model: str) -> None:
        """Evict a model from VRAM immediately (keep_alive=0).

        모델을 VRAM에서 즉시 내린다 (keep_alive=0).
        8GB 한계상, 다른 모델을 올리기 전 이전 모델을 명시적으로 내릴 때 쓴다.
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            await client.post(
                f"{self._host}/api/chat",
                json={"model": model, "messages": [], "keep_alive": 0},
            )

    async def is_available(self, model: str) -> bool:
        """Check whether a model is pulled and ready.

        모델이 pull되어 사용 가능한지 확인한다.
        """
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{self._host}/api/tags")
            resp.raise_for_status()
            names = {m["name"] for m in resp.json().get("models", [])}
            return any(n.startswith(model) for n in names)
