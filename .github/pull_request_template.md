<!-- 제목: Conventional Commits — feat|fix|refactor|docs|test|chore: 요약 (영어) -->
<!-- 브랜치: feat/<agent>-<area> · 담당 규칙은 ~/Dajung.md §3 -->

## 담당

- 에이전트: <!-- Claude Code | Codex | Agy -->
- 브랜치 번호: <!-- Dajung.md §3 표의 # -->
- 명세 근거: <!-- 예: Dajung.md §8.6, system-design.md §4.3 -->

## 변경 요약

<!-- 무엇을 바꿨나. 파일별 한 줄. -->

-

## 변경 이유

<!-- 왜 필요한가. 어떤 브랜치/기능을 unblock 하는가. -->

-

## 테스트

<!-- 실행 결과 그대로. 전부 체크돼야 머지 가능. -->

- [ ] `uv run ruff check .` ✅
- [ ] `uv run ruff format --check .` ✅
- [ ] `uv run mypy api` ✅ (strict)
- [ ] `uv run pytest` ✅ — `N passed` 숫자 기입:
- [ ] 새 기능이면 신규 테스트 동봉 (`api/tests/` 하위 — 소스 폴더 금지)

## 체크리스트 (CLAUDE.md §5 / Dajung.md §11)

- [ ] 명세에 없는 라이브러리·config 키·CLI 플래그 추가 없음
- [ ] 시크릿·실자료(`data/`)·PII 포함 없음 (`detect-secrets` 통과)
- [ ] docstring·주석 언어 규칙 준수 (영어 → 한국어)
- [ ] 권한 관련 코드 변경 시 `test_permission.py` 통과 확인
- [ ] 명세와 다르게 구현한 부분 없음 — 있으면 아래에 사유 기재

## 명세 이탈 / 질문

<!-- 명세대로 안 되는 부분, Claude Code에 물어볼 것. 없으면 "없음". -->

없음

## 관련 ADR

<!-- 예: ADR-012, ADR-013. 없으면 "해당 없음". -->

🤖 Generated with [Claude Code](https://claude.com/claude-code)
