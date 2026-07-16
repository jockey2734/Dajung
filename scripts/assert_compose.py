"""Validate deployment invariants in rendered Docker Compose configuration.

렌더링된 Docker Compose 설정의 배포 불변 조건을 검증한다.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_SERVICES = {"api", "caddy", "ollama", "postgres", "qdrant", "web"}
EXPECTED_QDRANT_TEST = [
    "CMD-SHELL",
    "bash -c ':> /dev/tcp/127.0.0.1/6333' || exit 1",
]
EXPECTED_MAKE_COMMANDS = {
    "ingest": "docker compose exec api dajung ingest $(or $(DIR),data/knowledge)",
    "dry": "docker compose exec api dajung ingest $(or $(DIR),data) --dry-run",
    "ask": 'docker compose exec api dajung ask "$(Q)"',
    "stats": "docker compose exec api dajung stats",
}


def require(condition: bool, message: str) -> None:
    """Raise a readable validation error when a deployment invariant fails.

    배포 불변 조건이 깨지면 읽기 쉬운 검증 오류를 발생시킨다.
    """
    if not condition:
        raise RuntimeError(message)


def compose_config(*files: str) -> dict[str, Any]:
    """Render a Compose configuration as structured JSON.

    Compose 설정을 구조화된 JSON으로 렌더링한다.
    """
    command = ["docker", "compose", "--env-file", ".env.example"]
    for file in files:
        command.extend(("-f", file))
    command.extend(("config", "--format", "json"))
    completed = subprocess.run(
        command,
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return cast(dict[str, Any], json.loads(completed.stdout))


def validate_services(config: dict[str, Any]) -> None:
    """Validate service membership, healthchecks, and production ports.

    서비스 구성, 헬스체크, 운영 포트를 검증한다.
    """
    services = config["services"]
    require(set(services) == EXPECTED_SERVICES, "compose must define exactly six expected services")
    missing_healthchecks = [
        name for name, service in services.items() if not service.get("healthcheck")
    ]
    require(not missing_healthchecks, f"services missing healthchecks: {missing_healthchecks}")

    port_publishers = {name for name, service in services.items() if service.get("ports")}
    require(port_publishers == {"caddy"}, "production ports must be published only by caddy")


def validate_s25(config: dict[str, Any]) -> None:
    """Validate the S25 Qdrant probe and writable API data bind.

    S25 Qdrant probe와 쓰기 가능한 API data bind를 검증한다.
    """
    services = config["services"]
    qdrant_test = services["qdrant"]["healthcheck"]["test"]
    require(qdrant_test == EXPECTED_QDRANT_TEST, "qdrant must use the bash /dev/tcp probe")

    data_volumes = [
        volume
        for volume in services["api"].get("volumes", [])
        if volume.get("target") == "/app/data"
    ]
    require(len(data_volumes) == 1, "api must have exactly one /app/data volume")
    data_volume = data_volumes[0]
    require(data_volume.get("type") == "bind", "/app/data must be a bind mount")
    require(
        Path(data_volume["source"]).resolve() == (ROOT / "data").resolve(),
        "/app/data must bind the repository data directory",
    )
    require(not data_volume.get("read_only", False), "/app/data must be writable")


def validate_dev_ports(config: dict[str, Any]) -> None:
    """Validate that every development port is loopback-only.

    모든 개발 포트가 loopback에만 바인딩되는지 검증한다.
    """
    ports = [
        (name, port)
        for name, service in config["services"].items()
        for port in service.get("ports", [])
    ]
    require(ports, "development compose must publish loopback ports")
    public_ports = [(name, port) for name, port in ports if port.get("host_ip") != "127.0.0.1"]
    require(not public_ports, f"development ports must be loopback-only: {public_ports}")


def validate_makefile() -> None:
    """Validate that server RAG targets execute inside the API container.

    서버 RAG target이 API 컨테이너 내부에서 실행되는지 검증한다.
    """
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    for target, expected in EXPECTED_MAKE_COMMANDS.items():
        match = re.search(rf"(?m)^{target}:.*\n((?:\t.*\n)+)", makefile)
        require(match is not None, f"missing Makefile target: {target}")
        recipe = match.group(1)
        require(f"\t{expected}\n" in recipe, f"{target} must run through docker compose exec api")
        require("uv run dajung" not in recipe, f"{target} must not run dajung on the host")


def main() -> None:
    """Run all production, development, and operator assertions.

    운영, 개발, operator assertion을 모두 실행한다.
    """
    production = compose_config("compose.yml")
    development = compose_config("compose.yml", "compose.dev.yml")
    validate_services(production)
    validate_s25(production)
    validate_dev_ports(development)
    validate_makefile()
    print("compose assertions passed")


if __name__ == "__main__":
    main()
