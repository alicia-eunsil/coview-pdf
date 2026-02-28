# coview-pdf

# PDF Mirror (GJF00) — 실시간 PDF 동기화 뷰어

조정자(Controller/Host)가 선택한 **PDF 파일과 페이지**를 관전자(Viewer)가 **새로고침 없이 실시간으로 따라보는** 웹 서비스입니다.  
WebSocket 기반으로 상태(pdf 번호, 페이지, 조정권)를 동기화합니다.

- 기본 Room: **GJF00** (URL에 `?room=` 파라미터 없이 고정)
- PDF 3개(pdf1.pdf, pdf2.pdf, pdf3.pdf) 지원
- 조정권(Control) **즉시 takeover** 방식 (누가 ON 누르면 조정권을 가져감)

---

## 주요 기능

- **실시간 동기화**
  - 조정자가 PDF 1~3 선택, 페이지 이동 시 관전자 화면이 즉시 변경
- **조정권 ON/OFF**
  - ON: 즉시 조정권 takeover
  - OFF: 조정권 해제(비움)
- **현재 페이지/전체 페이지 표시**
  - 예: `PDF 2 | 17 / 42 pages`
- **성능/안정성 개선**
  - 같은 PDF 내 페이지 이동은 **재로딩 없이 캐싱 문서 사용**
  - PDF.js `render()` 충돌 방지(이전 렌더 작업 cancel)
  - iOS/Safari 캔버스 뒤집힘 방지(DPR + transform 초기화)

---

## 파일 구조

```text
.
├─ main.py
├─ requirements.txt
└─ static/
   ├─ host.html          # 조정자 화면
   ├─ view.html          # 관전자 화면
   ├─ pdf/
   │  ├─ pdf1.pdf
   │  ├─ pdf2.pdf
   │  └─ pdf3.pdf
   └─ pdfjs/
      ├─ pdf.min.js
      └─ pdf.worker.min.js
