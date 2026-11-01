# ADR-030: PDF 파서 — opendataloader-pdf(로컬 모드) 기본 + PyMuPDF 페이지별 폴백

**상태:** 채택 (2026-11-01) · 결정 2026-10-01 운하(표 많은 PDF 5쌍 육안 비교) · 작성 Sonnet(운하 지시로 Claude Code 대행) · 구현 `feat/sn-pdf-odl`(이 ADR 동봉)

## 배경

`system-design.md` 파서 표와 `RAG.md`는 표 많은 PDF(인수인계 확인서·재등록 서류)를 **"PyMuPDF 또는 Docling — PoC에서 비교"** 로 열어 두었다. 실제 구현(`api/app/ingest/parsers.py`)은 PyMuPDF `page.get_text("text")` 평문이고, 합계 50자 미만이면 docling으로 넘긴다.

평문 추출의 문제:

- **표와 제목 구조가 사라진다.** 인수인계 확인서·재등록 서류·예산안처럼 행·열 관계가 곧 내용인 문서에서 "어느 칸이 어느 항목의 값인지"가 청크에 남지 않는다.
- 일부 파일은 폰트 디코딩이 깨져 제어문자가 섞이거나(6건) 한글이 아예 안 나온다(1건).
- 부수 발견: 컨테이너의 docling OCR은 **한 번도 동작한 적이 없다.** `No OCR engine found` → `ImportError`를 `_parse_pdf_docling`이 `except Exception: return ""`로 삼켜, 스캔 PDF 4건이 전부 `ParserEmptyError`로 끝난다. 이 ADR은 OCR을 다루지 않는다(후속 1).

경과: 2026-09-29 opendataloader-pdf(ODL) 저장소 조사·bake-off → 2026-10-01 운하 육안 비교 후 **ODL 채택**("PyMuPDF가 ODL보다 나쁘다"), 지적 2건 해결 → 2026-10-29 갱신판(PyMuPDF 2.0·ODL 2.5.16)과 MarkItDown 0.1.9를 넣어 3자 재비교 → 선행 의존성 PR #65(PyMuPDF 2.0·MarkItDown 0.1.9) 머지(2026-11-01).

## 검토한 선택지

1. **현행 유지** — PyMuPDF 평문 + 50자 미만 docling 폴백
2. **ODL 로컬 모드 + PyMuPDF 페이지별 폴백**
3. **ODL 하이브리드 모드** — 별도 서버(내부는 docling)로 OCR·복잡한 표
4. **docling 전면 사용**
5. **MarkItDown PDF 변환기** — pdfplumber(양식형 페이지 표 감지) + pdfminer.six

## 결정

선택지 2를 채택한다. 나머지는 기각(아래).

- **패키지**: `opendataloader-pdf==2.5.16` 정확히 고정(Apache-2.0, JAR 번들 wheel 22.6MB, 파이썬 의존성 0). api 이미지 runtime 스테이지에 `default-jre-headless`(OpenJDK 21)를 넣는다.
- **변환 설정**: 파일마다 임시 디렉터리에 `format="markdown"`, `image_output="off"`, **`include_header_footer=True`**, 페이지 구분자 `<!-- dajung-page N -->`. 구분자로 쪼개 페이지 리스트를 만든다.
- **페이지별 병합**: 같은 파일을 PyMuPDF로도 읽는다. ODL 페이지의 단어 수가 `pdf_odl_min_word_ratio`(0.85) × PyMuPDF 단어 수보다 적고, PyMuPDF 페이지가 깨지지 않았으면(제어·사용자정의 문자 비율 < `pdf_garbled_char_ratio` 0.05) **그 페이지만** PyMuPDF 텍스트를 쓴다. 쪽수가 서로 다르면 병합하지 않고 ODL 전체를 쓴다. 폴백한 페이지는 `pdf_page_fallback` 로그로 남긴다(파일명·본문 비출력 원칙 준수).
- **파일 단위 폴백**: ODL이 예외를 내면(Java 부재 `FileNotFoundError`, 변환 실패 `CalledProcessError`) 경고 로그 후 파일 전체를 PyMuPDF로 읽는다. ingest가 Java 때문에 멈추지 않는다.
- **롤백 스위치**: `settings.pdf_parser: Literal["odl", "pymupdf"] = "odl"`(env `DAJUNG_PDF_PARSER`). 코드 변경 없이 현행 동작으로 되돌린다.
- **PyMuPDF는 2.0으로 유지**한다 — 폴백이자 단어 수 기준선. AGPL 의존 제거는 후속 결정(후속 2).
- **스캔 판정은 본문 글자로 센다**: ODL은 일부 스캔 페이지를 빈 표 격자(`|  |  |`, `|---|`)로 내놓아, 원시 글자 수로는 50자 판정을 통과해 버린다(실제 스캔 2건 — 구현 중 발견, 2026-11-01). 판정 전에 표 구분 행·표 행(`|`로 시작하고 끝나는 줄)·제목 표식·`<br>`만 걷어내고, 평문은 건드리지 않는다. 결과: 후보 PDF 71건에서 두 설정(`odl`·`pymupdf`) 모두 **이전과 정확히 같은 4건**을 스캔으로 판정하고, `pymupdf` 롤백은 옛 동작(청크 368개)을 그대로 재현한다.
- **유지하는 것**: 스캔 의심(<50자) 시 docling 경로, `chunker._chunk_pdf`(무변경 — `p.N` 페이지 로케이터·인용 계약 그대로), 오피스 파일은 MarkItDown 전용(0.1.9).
- **적용 순서**: 구현 PR 머지 → api 이미지 재빌드(lock·Dockerfile 변경) → dry-run 수치 확인 → **PDF 재ingest**(청크 내용이 바뀌므로). 실데이터 ingest는 이 PR 이후에 한 번만 한다.

## 사유

**3자 비교** (2026-10-29, CSV 색인 후보 PDF 71건·666쪽, 일회용 컨테이너, `data/` 읽기 전용, 수치만. ODL은 위 결정 설정):

| | PyMuPDF 2.0 (현행) | ODL 2.5.16 | MarkItDown 0.1.9 |
|---|---|---|---|
| 한글 글자 | 147,541 | 148,263 | 148,271 |
| 한글 커버리지 | 99.0% | **99.5%** | **99.5%** |
| 제어문자 ≥5% 파일 | 6 | **0** | 5 |
| 텍스트 없음(스캔) | 10 | 8 | 10 |
| 표 행 | 0 | **3,162** | 2,952 |
| 제목(`#`) | 0 | **987** | 0 |
| 페이지 경계 보존 | 전부 | 전부(구분자) | **37/71만** |
| 소요(666쪽) | 5.3초 | 9.2초(배치) / 파일당 호출 ~1초 | 74.9초 |
| 런타임 추가 | 없음 | Java 11+ (+194MB) | pdfminer.six·pdfplumber |
| 라이선스 | AGPL-3.0 | Apache-2.0 | MIT |

- **텍스트는 동등, 구조는 새로 생긴다.** ODL만 표·제목·페이지 경계·제어문자 정리를 모두 갖췄다. PyMuPDF가 한글 0자인 파일(폰트 디코딩 실패)도 ODL은 1,444자로 복원한다.
- **PyMuPDF 1.28 → 2.0 회귀 없음**: 71건 `get_text` 결과 71/71 동일. 2.0은 1.28.x `get_text()` 무한 대기(#5082)·메모리 누수를 고친다.
- **운하 육안 판정**(표 많은 실제 PDF 5쌍 — 인수인계·신청 서류·회칙·행사 기획서·교육 자료): 채택. 지적 2건은 아래처럼 해결했다.

**지적 ① 재등록 서류의 "활동 설명" 누락 → `include_header_footer=True` + 페이지별 폴백.**
누락 글자는 다른 본문과 같은 검은색·12pt였고 이미지 위도 아니었다. 옵션별 복원(누락 63단어): `include_header_footer=True` **63/63**, `use_struct_tree` 62/63(태그 PDF 한정), 나머지 옵션 20/63. 원인은 ODL이 **매 페이지 같은 위치의 문단을 머리말·꼬리말로 분류해 제거**하는 것. 이 옵션으로 "ODL < PyMuPDF 85%" 쪽이 54 → 16으로 줄고, 남은 16쪽은 페이지별 폴백이 맡는다. 임계 스윕: 80·85% 16쪽, 90% 19쪽, 95% 23쪽 → 85%. 폴백하지 않은 쪽의 잔여 "누락 단어"는 띄어쓰기 차이이며, 한글 글자 기준 실손실은 125,515자 중 42자(0.03%). 2.5.16 재실행에서도 폴백 16쪽·쪽수 불일치 0으로 같다.

**지적 ② 도식 라벨 자간(차 종류 이름이 글자마다 띄어져 `######` 제목으로 나옴) → 문제 아님, 기본값 유지.**
자간 넓은 라벨을 ODL이 글자 단위로 띄운다(`space_ratio` 기본 0.17). 0.25/0.33/0.5 스윕은 단어 일치율을 96.8% → 90.1/83.3/56.3%로 떨어뜨리고 영문 단어 사이 공백을 없애며, 0.5에서도 라벨은 그대로다. 검색 실측(bge-m3 dense+sparse, 질의 4 × 변형 3): dense 차이 ±0.03, sparse는 3/4에서 ODL 쪽이 더 높다. bge-m3 토크나이저가 `녹차`→`▁녹`+`차`, `녹 차`→`▁녹`+`▁차`로 쪼개 변별 음절이 그대로 맞기 때문이다. `######` 제목 수준은 PDF 페이지 청킹에 영향이 없다.

**라이선스**: PyMuPDF는 AGPL-3.0, ODL은 Apache-2.0. 기본 경로가 Apache-2.0이 되어, 포트폴리오 공개 시 AGPL 의존을 걷어낼 길이 생긴다(폴백 유지 중에는 여전히 의존).

## 보안 경계

- **로컬 모드는 네트워크를 쓰지 않는다.** 변환은 `java -jar` 서브프로세스, 입출력은 파일마다 만든 임시 디렉터리. 외부 전송 없음 — ADR-029 경계와 무관.
- **하이브리드 서버(선택지 3)는 기본 `0.0.0.0` 바인드·인증 없음.** 도입하려면 이 ADR 개정과 함께 compose 내부망(backnet) 전용·포트 비공개를 조건으로 한다.
- OCR을 외부 LLM 비전(예: `markitdown-ocr`에 클라우드 클라이언트)으로 하는 안은 회원 데이터가 담긴 문서를 밖으로 보내므로 **ADR-029 범위** — 이 ADR로 허용하지 않는다.
- Java 런타임이 이미지 공격면을 늘린다(+194MB). 보안 갱신은 베이스 이미지 재빌드로 따라간다. JVM은 ingest 중에만 뜨고 상주하지 않는다.
- bake-off·검증 산출물은 수치만 남긴다. 비교본·후보 목록(실파일명)은 레포 밖에 두고 삭제한다.

## 트레이드오프와 결과

- 이미지 +194MB(JRE) + 22.6MB(wheel).
- 파일당 JVM 기동 ~1초, PDF마다 파서 2회(ODL + 병합용 PyMuPDF). 71건 기준 ingest 파싱이 수 초 → 1분 남짓. ingest 빈도가 낮아 수용한다.
- ODL은 페이지 테두리를 표로 보는 경우가 있다(1칸짜리 행 428개, 회칙 사례) — 청크에 잡음. 운영 후 관찰.
- 스캔 PDF 8건은 여전히 텍스트가 없다(ODL 로컬 모드는 OCR 없음).
- PDF 전체 재ingest가 필요하다.
- **구현 실측**(2026-11-01, 별도 태그 이미지·`--network none`·`data/` 읽기 전용, 수치만): dry-run scanned 205·제외 동일·errors 7(스캔 4·Thumbs.db 3 — main과 동일) · ODL 실패 폴백 0 · 쪽수 불일치 0 · 페이지 폴백 16쪽 · PDF 청크 368 → **410**, 표가 든 청크 0 → **245**, 제목으로 시작 0 → **164** · dry-run 전체 43초 → 92초 · JRE 레이어 211MB.
- 문서 갱신: `system-design.md` 파서 표, `CLAUDE.md` 스택 줄, `ARCHITECTURE.md` 인덱싱 경로, `RAG.md` 파서 표에 ADR-030을 반영한다(2026-11-01 반영).

## 기각한 대안

- **선택지 1 (현행 유지)**: 표·제목 구조 0, 제어문자 6파일, 한글 0자 1파일. 육안 판정에서 ODL보다 나쁨.
- **선택지 3 (ODL 하이브리드)**: OCR과 복잡한 표(ODL 공식 벤치마크 표 점수 로컬 0.489 → 하이브리드 0.928)는 이점이지만, 별도 서버·무인증·`0.0.0.0` 기본값이고 `[hybrid]` extra가 `docling[easyocr]>=2.126`을 요구한다(현재 2.94 — 대규모 의존성 갱신). OCR 계획(후속 1)에서 내부망 전용 조건으로 재검토.
- **선택지 4 (docling 전면)**: **실측하지 않았다.** CPU 전용 서버에서 페이지마다 레이아웃 모델을 돌리는 부담(추정), 현재 OCR 엔진도 미설치 상태라 스캔 문제를 풀지 못하고, 하이브리드 모드가 내부적으로 docling이라 선택지 3으로 흡수된다.
- **선택지 5 (MarkItDown PDF)**: 텍스트·표는 대등(커버리지 99.5%, 표 2,952행)하지만, "양식형" 페이지가 하나라도 있으면 페이지를 `\n\n`으로 이어 붙여 **쪽 경계가 37/71건에서만 복원**되고, 제목이 0이며, 14배 느리다(74.9초). 청커의 `p.N` 인용 로케이터와 청킹 계약을 지킬 수 없다. 우회하려면 PDF를 한 쪽씩 쪼개 666번 변환해야 한다. MarkItDown은 **오피스(DOCX·XLSX·PPTX) 전용**으로 유지한다(0.1.9: xlsx 17/17 동일, pptx 한글 +187자).

## 후속

1. **OCR 계획**(스캔 8~10건): ⓐ api 이미지 docling에 OCR 엔진 연결(외부 전송 없음, 우선) ⓑ ODL 하이브리드 서버(내부망 전용) ⓒ `markitdown-ocr` + 로컬 Ollama OpenAI 호환 엔드포인트 비전 모델(비전 모델 실측 필요). 아울러 `_parse_pdf_docling`의 예외 삼킴을 고친다.
2. **PyMuPDF(AGPL) 제거 여부** — 폴백을 ODL 텍스트 모드나 pdfminer로 바꿀 수 있는지.
3. **점 폴더 ingest 제외 결함** — `run_ingest`의 `rglob("*")`가 점 폴더로 들어가고 hidden 규칙은 파일명만 본다.
4. **긴 표 청킹** — 표가 페이지 청크 크기를 넘을 때의 분할 규칙.

## 근거 기록

- 구현 계획: `docs/superpowers/plans/2026-09-29-pdf-parser-opendataloader.md`(2.5.16 갱신판) · 3자 비교: `docs/superpowers/plans/2026-10-29-pdf-parser-3way-markitdown.md`
- 실측 이력: `~/Develop_records.md` 2026-09-29 · 2026-10-01 · 2026-10-29 · 2026-11-01
- 선행 PR: #65 `chore(deps): bump pymupdf to 2.0 and markitdown to 0.1.9`
- opendataloader-pdf: https://github.com/opendataloader-project/opendataloader-pdf
- MarkItDown: https://github.com/microsoft/markitdown
- PyMuPDF 변경 내역: https://pymupdf.readthedocs.io/en/latest/changes.html
