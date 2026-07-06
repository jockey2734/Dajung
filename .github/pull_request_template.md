<!-- Title: Conventional Commits — feat|fix|refactor|docs|test|chore: summary (English) -->
<!-- 제목: Conventional Commits — feat|fix|refactor|docs|test|chore: 요약 (영어) -->
<!-- Branch: feat/<agent>-<area> · ownership rules in ~/Dajung.md §3 -->
<!-- 브랜치: feat/<agent>-<area> · 담당 규칙은 ~/Dajung.md §3 -->

## Owner · 담당

- Agent · 에이전트: <!-- Claude Code | Codex | Agy -->
- Branch # · 브랜치 번호: <!-- # in Dajung.md §3 table · Dajung.md §3 표의 # -->
- Spec basis · 명세 근거: <!-- e.g. Dajung.md §8.6, system-design.md §4.3 -->

## Summary · 변경 요약

<!-- What changed — one line per file. · 무엇을 바꿨나 — 파일별 한 줄. -->

-

## Why · 변경 이유

<!-- Why needed; what it unblocks. · 왜 필요한가; 무엇을 unblock 하는가. -->

-

## Tests · 테스트

<!-- Paste actual results. All boxes required to merge. -->
<!-- 실행 결과 그대로. 전부 체크돼야 머지 가능. -->

- [ ] `uv run ruff check .` ✅
- [ ] `uv run ruff format --check .` ✅
- [ ] `uv run mypy api` ✅ (strict)
- [ ] `uv run pytest` ✅ — fill in `N passed` · `N passed` 숫자 기입:
- [ ] New feature ships with new tests under `api/tests/` (never in source dirs)
      · 새 기능이면 신규 테스트 동봉 (`api/tests/` 하위 — 소스 폴더 금지)

## Checklist · 체크리스트 (CLAUDE.md §5 / Dajung.md §11)

- [ ] No libraries/config keys/CLI flags beyond spec · 명세에 없는 라이브러리·config 키·CLI 플래그 없음
- [ ] No secrets, real club data (`data/`), or PII (`detect-secrets` passes)
      · 시크릿·실자료(`data/`)·PII 없음 (`detect-secrets` 통과)
- [ ] Bilingual docstrings/comments (English → Korean) · 주석 언어 규칙 준수 (영어 → 한국어)
- [ ] `test_permission.py` green if permission code touched · 권한 코드 변경 시 `test_permission.py` 통과
- [ ] No undeclared spec deviations — declare below · 명세 이탈 무기재 없음 — 있으면 아래 기재

## Spec deviations / Questions · 명세 이탈 / 질문

<!-- Anything differing from spec; questions for Claude Code. "None" if none. -->
<!-- 명세와 다른 부분, Claude Code에 물어볼 것. 없으면 "없음". -->

None · 없음

## Related ADR · 관련 ADR

<!-- e.g. ADR-012, ADR-013. "N/A" if none. · 없으면 "해당 없음". -->

🤖 Generated with [Claude Code](https://claude.com/claude-code)
