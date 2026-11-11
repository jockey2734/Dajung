"""Club term list for generated header wording (prompts/terms.yaml).

생성되는 헤더 문구용 동아리 용어 사전 (prompts/terms.yaml).
Applies only to model output (headers, document descriptions), never to source text.
모델 출력(헤더·문서 설명)에만 적용하고 원문은 바꾸지 않는다.
"""

from __future__ import annotations

import functools
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from api.app.core.config import settings

_Word = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]

# Uppercase runs of 2+ chars (ISS, OT, Q1) not glued to other Latin letters.
# 다른 라틴 문자에 붙지 않은 2자 이상 대문자 묶음 (ISS, OT, Q1).
_ACRONYM = re.compile(r"(?<![A-Za-z])[A-Z][A-Z0-9]+(?![A-Za-z])")


class _Conditional(BaseModel):
    model_config = ConfigDict(extra="forbid")

    wrong: _Word
    right: _Word
    when_source_has: list[_Word] = Field(min_length=1)


class _TermsFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    unify: dict[_Word, list[_Word]] = Field(default_factory=dict)
    conditional: list[_Conditional] = Field(default_factory=list)
    protect: list[_Word] = Field(default_factory=list)
    keep: list[_Word] = Field(default_factory=list)

    @model_validator(mode="after")
    def _aliases_are_unambiguous(self) -> _TermsFile:
        seen: set[str] = set()
        for canonical, aliases in self.unify.items():
            for alias in aliases:
                if alias == canonical or alias in self.unify:
                    raise ValueError(f"alias {alias!r} is itself a canonical term")
                if alias in seen:
                    raise ValueError(f"alias {alias!r} is listed twice")
                seen.add(alias)
        return self


def _alternation(words: list[str]) -> str:
    # Longest first so a longer word wins over its own prefix; never-match when empty.
    # 긴 단어 먼저 — 접두어보다 긴 단어가 이긴다. 비어 있으면 절대 매치 안 함.
    if not words:
        return "(?!)"
    return "|".join(re.escape(w) for w in sorted(set(words), key=len, reverse=True))


def _shielded(shield: list[str], words: list[str]) -> re.Pattern[str]:
    # Group 1 = shielded word (left as is), group 2 = target word.
    # 1번 그룹 = 보호 단어(그대로 둠), 2번 그룹 = 대상 단어.
    return re.compile(f"({_alternation(shield)})|({_alternation(words)})")


@dataclass(frozen=True)
class _Rule:
    wrong: str
    right: str
    room: re.Pattern[str]


@dataclass(frozen=True)
class Terms:
    """Compiled term rules: unify aliases in output, list terms to keep verbatim.

    컴파일된 용어 규칙: 출력의 별칭 통일, 원문 그대로 쓸 용어 목록.
    """

    keep: tuple[str, ...]
    _canonical: dict[str, str]
    _alias: re.Pattern[str]
    _rules: tuple[_Rule, ...]

    def unify(self, text: str, source: str) -> str:
        """Rewrite aliases to canonical terms; apply conditional fixes checked on source.

        별칭을 표준어로 바꾸고, 원문으로 조건을 확인한 교체를 적용한다.
        """
        out = self._alias.sub(lambda m: self._canonical.get(m.group(2), m.group(0)), text)
        for rule in self._rules:
            if rule.wrong in source:
                continue
            if any(m.group(2) for m in rule.room.finditer(source)):
                out = out.replace(rule.wrong, rule.right)
        return out

    def to_keep(self, source: str, max_acronyms: int, max_terms: int) -> list[str]:
        """Acronyms and listed club terms found in source, each list sorted and capped.

        원문에서 찾은 영문 약어와 사전의 동아리 용어 — 각각 정렬 후 상한 적용.
        """
        acronyms = sorted(set(_ACRONYM.findall(source)))[:max_acronyms]
        found = [t for t in self.keep if t in source]
        standalone = [t for t in found if _stands_alone(t, found, source)]
        return acronyms + sorted(set(standalone))[:max_terms]


def _stands_alone(term: str, found: list[str], source: str) -> bool:
    # A term seen only inside a longer found term (다회 in 연합다회) is not listed.
    # 더 긴 용어 안에서만 보이는 용어(연합다회 속 다회)는 넣지 않는다.
    longer = [t for t in found if term in t and t != term]
    if not longer:
        return True
    return any(m.group(2) for m in _shielded(longer, [term]).finditer(source))


def parse_terms(raw: Any) -> Terms:
    """Validate and compile term rules from parsed YAML (None = no rules).

    파싱된 YAML에서 용어 규칙을 검증·컴파일한다 (None = 규칙 없음).
    """
    spec = _TermsFile.model_validate(raw or {})
    canonical = {a: c for c, aliases in spec.unify.items() for a in aliases}
    return Terms(
        keep=tuple(spec.keep),
        _canonical=canonical,
        _alias=_shielded(spec.protect + list(spec.unify), list(canonical)),
        _rules=tuple(
            _Rule(r.wrong, r.right, _shielded(spec.protect, r.when_source_has))
            for r in spec.conditional
        ),
    )


@functools.cache
def load_terms(path: Path) -> Terms:
    """Load prompts/terms.yaml once per path; a bad file raises with its path.

    경로당 한 번 로드한다. 잘못된 파일은 경로와 함께 예외를 낸다.
    """
    try:
        return parse_terms(yaml.safe_load(path.read_text(encoding="utf-8")))
    except (ValueError, yaml.YAMLError) as exc:
        raise ValueError(f"invalid term list {path}: {exc}") from exc


def get_terms() -> Terms:
    """Term rules from the configured prompts directory.

    설정된 prompts 디렉토리의 용어 규칙.
    """
    return load_terms(settings.prompts_dir / "terms.yaml")
