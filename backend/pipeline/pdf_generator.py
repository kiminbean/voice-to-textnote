"""
SPEC-EXPORT-001: 회의록 PDF 생성기

fpdf2 라이브러리를 사용하여 회의록 데이터를 PDF로 변환합니다.
NotoSansKR 폰트를 사용하여 한국어 텍스트를 렌더링합니다.
"""

from pathlib import Path

from fpdf import FPDF


class MinutesPDFGenerator:
    """
    회의록 PDF 생성기 - fpdf2 기반

    회의록 데이터와 선택적 요약 데이터를 받아 PDF bytes를 반환합니다.

    # @MX:ANCHOR: PDF 생성 핵심 클래스 - export API의 유일한 의존 지점
    # @MX:REASON: MinutesPDFGenerator.generate()는 export_pdf 엔드포인트에서 직접 호출됨
    """

    # 폰트 파일 경로 (프로젝트 루트 기준)
    FONT_DIR = Path(__file__).parent.parent / "assets" / "fonts"
    FONT_REGULAR = "NotoSansKR-Regular.ttf"

    # 페이지 여백 (mm)
    MARGIN = 15

    # 색상 정의 (RGB)
    COLOR_TITLE = (30, 30, 100)      # 진한 남색 - 제목
    COLOR_SECTION = (50, 50, 150)    # 남색 - 섹션 헤더
    COLOR_BORDER = (180, 180, 200)   # 연한 회색 - 테이블 테두리
    COLOR_HEADER_BG = (230, 230, 245)  # 연한 라벤더 - 테이블 헤더 배경
    COLOR_TEXT = (40, 40, 40)        # 거의 검정 - 본문

    def __init__(self) -> None:
        """PDF 객체 초기화 및 폰트 등록"""
        self.pdf = FPDF()
        self.pdf.set_margins(self.MARGIN, self.MARGIN, self.MARGIN)
        self.pdf.set_auto_page_break(auto=True, margin=self.MARGIN)
        self._register_fonts()

    def _register_fonts(self) -> None:
        """
        NotoSansKR 폰트 등록

        variable weight TTF 파일로 regular/bold 모두 동일 파일 사용
        (fpdf2는 variable TTF를 지원하므로 uni=True 불필요 - 자동 처리)
        """
        font_path = str(self.FONT_DIR / self.FONT_REGULAR)
        # regular 스타일 등록
        self.pdf.add_font("NotoSansKR", "", font_path)
        # bold 스타일 (동일 파일 - variable weight)
        self.pdf.add_font("NotoSansKR", "B", font_path)

    def generate(
        self,
        minutes_data: dict,
        summary_data: dict | None = None,
    ) -> bytes:
        """
        회의록 + 요약 데이터로 PDF 생성하여 bytes 반환

        Args:
            minutes_data: 회의록 결과 데이터 (segments 필수)
            summary_data: 요약 결과 데이터 (선택, 없으면 요약 섹션 생략)

        Returns:
            PDF 파일 bytes

        Raises:
            ValueError: segments가 비어있으면 발생
        """
        # segments 필수 검증
        segments = minutes_data.get("segments", [])
        if not segments:
            raise ValueError("Incomplete minutes data: segments is empty")

        self.pdf.add_page()

        # 양식 테이블이 있으면 양식 형태로 렌더링 (화면과 동일)
        if (summary_data
                and summary_data.get("template_structure")
                and summary_data["template_structure"].get("table_layout")):
            self._render_template_table(minutes_data, summary_data)
        else:
            # 기존 기본 레이아웃
            self._render_header(minutes_data)
            self._render_speaker_stats(minutes_data)
            self._render_minutes_body(minutes_data)
            if summary_data:
                self._render_summary(summary_data)
                self._render_key_decisions(summary_data)
                self._render_action_items(summary_data)

        return bytes(self.pdf.output())

    # ---------------------------------------------------------------------------
    # 내부 렌더링 메서드
    # ---------------------------------------------------------------------------

    def _render_header(self, minutes_data: dict) -> None:
        """
        헤더 섹션 렌더링

        - 제목: '회의록'
        - 작성일: created_at
        - 총 길이: total_duration (HH:MM:SS 형식)
        """
        pdf = self.pdf

        # 제목
        pdf.set_font("NotoSansKR", "B", 20)
        pdf.set_text_color(*self.COLOR_TITLE)
        pdf.cell(0, 12, "회의록", align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

        # 구분선
        pdf.set_draw_color(*self.COLOR_BORDER)
        pdf.set_line_width(0.5)
        pdf.line(
            self.MARGIN,
            pdf.get_y(),
            pdf.w - self.MARGIN,
            pdf.get_y(),
        )
        pdf.ln(4)

        # 메타 정보 (작성일, 총 길이)
        pdf.set_font("NotoSansKR", "", 10)
        pdf.set_text_color(*self.COLOR_TEXT)

        created_at = minutes_data.get("created_at", "")
        total_duration = minutes_data.get("total_duration", 0.0)
        duration_str = self._format_duration_hhmmss(total_duration)
        total_speakers = minutes_data.get("total_speakers", 0)

        pdf.cell(40, 7, "작성일:", new_x="RIGHT", new_y="TOP")
        pdf.cell(0, 7, created_at[:19] if len(created_at) >= 19 else created_at,
                 new_x="LMARGIN", new_y="NEXT")
        pdf.cell(40, 7, "총 길이:", new_x="RIGHT", new_y="TOP")
        pdf.cell(0, 7, duration_str, new_x="LMARGIN", new_y="NEXT")
        pdf.cell(40, 7, "참여자 수:", new_x="RIGHT", new_y="TOP")
        pdf.cell(0, 7, f"{total_speakers}명", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)

    def _render_speaker_stats(self, minutes_data: dict) -> None:
        """
        발화자 통계 테이블 렌더링

        컬럼: 발화자 | 발화 횟수 | 발화 시간 | 비율
        """
        pdf = self.pdf
        speakers = minutes_data.get("speakers", [])
        if not speakers:
            return

        # 섹션 헤더
        self._render_section_title("발화자 통계")

        # 테이블 컬럼 너비 설정
        usable_width = pdf.w - 2 * self.MARGIN
        col_widths = [
            usable_width * 0.35,  # 발화자
            usable_width * 0.20,  # 발화 횟수
            usable_width * 0.25,  # 발화 시간
            usable_width * 0.20,  # 비율
        ]
        headers = ["발화자", "발화 횟수", "발화 시간", "비율"]
        row_height = 8

        # 헤더 행
        pdf.set_fill_color(*self.COLOR_HEADER_BG)
        pdf.set_draw_color(*self.COLOR_BORDER)
        pdf.set_font("NotoSansKR", "B", 9)
        pdf.set_text_color(*self.COLOR_TEXT)
        for i, (header, width) in enumerate(zip(headers, col_widths)):
            pdf.cell(width, row_height, header, border=1, align="C", fill=True)
        pdf.ln()

        # 데이터 행
        pdf.set_font("NotoSansKR", "", 9)
        pdf.set_fill_color(255, 255, 255)
        for speaker in speakers:
            name = speaker.get("speaker_name", "")
            count = str(speaker.get("segment_count", 0))
            speaking_time = self._format_duration_mmss(speaker.get("total_speaking_time", 0.0))
            ratio = f"{speaker.get('speaking_ratio', 0.0):.1f}%"

            values = [name, count, speaking_time, ratio]
            aligns = ["L", "C", "C", "C"]
            for val, width, align in zip(values, col_widths, aligns):
                pdf.cell(width, row_height, val, border=1, align=align)
            pdf.ln()

        pdf.ln(4)

    def _render_minutes_body(self, minutes_data: dict) -> None:
        """
        회의록 본문 렌더링

        각 세그먼트를 '[MM:SS~MM:SS] 발화자: 텍스트' 형식으로 출력
        """
        pdf = self.pdf
        segments = minutes_data.get("segments", [])

        # 섹션 헤더
        self._render_section_title("회의록 본문")

        pdf.set_font("NotoSansKR", "", 9)
        pdf.set_text_color(*self.COLOR_TEXT)
        usable_width = pdf.w - 2 * self.MARGIN

        for segment in segments:
            speaker = segment.get("speaker_name", "")
            text = segment.get("text", "")
            start = segment.get("start", 0.0)
            end = segment.get("end", 0.0)

            # 시간 형식: [MM:SS~MM:SS]
            time_str = f"[{self._format_duration_mmss(start)}~{self._format_duration_mmss(end)}]"

            # 발화자 + 시간 (볼드)
            pdf.set_font("NotoSansKR", "B", 9)
            label = f"{time_str} {speaker}: "
            pdf.cell(0, 6, label, new_x="LMARGIN", new_y="NEXT")

            # 텍스트 (일반)
            pdf.set_font("NotoSansKR", "", 9)
            pdf.set_x(self.MARGIN + 5)  # 들여쓰기
            pdf.multi_cell(usable_width - 5, 5, text)
            pdf.ln(1)

        pdf.ln(4)

    def _render_summary(self, summary_data: dict) -> None:
        """
        요약 섹션 렌더링

        summary_text를 multi_cell로 출력
        """
        pdf = self.pdf
        summary_text = summary_data.get("summary_text", "")
        if not summary_text:
            return
        # JSON 문자열이면 내부 summary_text 추출
        if summary_text.strip().startswith("{"):
            try:
                import json as _json
                parsed = _json.loads(summary_text)
                if isinstance(parsed, dict) and "summary_text" in parsed:
                    summary_text = parsed["summary_text"]
            except Exception:
                pass

        self._render_section_title("회의 요약")

        pdf.set_font("NotoSansKR", "", 9)
        pdf.set_text_color(*self.COLOR_TEXT)
        usable_width = pdf.w - 2 * self.MARGIN
        pdf.multi_cell(usable_width, 6, summary_text)
        pdf.ln(4)

    def _render_key_decisions(self, summary_data: dict) -> None:
        """
        주요 결정 사항 섹션 렌더링 (번호 목록)
        """
        pdf = self.pdf
        key_decisions = summary_data.get("key_decisions", [])
        if not key_decisions:
            return

        self._render_section_title("주요 결정 사항")

        pdf.set_font("NotoSansKR", "", 9)
        pdf.set_text_color(*self.COLOR_TEXT)
        usable_width = pdf.w - 2 * self.MARGIN

        for i, decision in enumerate(key_decisions, 1):
            # dict 형태인 경우 "decision" 키에서 추출
            if isinstance(decision, dict):
                decision = decision.get("decision", str(decision))
            decision = str(decision or "")
            pdf.set_x(self.MARGIN + 3)
            pdf.multi_cell(usable_width - 3, 6, f"{i}. {decision}")

        pdf.ln(4)

    def _render_action_items(self, summary_data: dict) -> None:
        """
        액션 아이템 테이블 렌더링

        컬럼: 담당자 | 작업 | 기한 | 우선순위
        """
        pdf = self.pdf
        action_items = summary_data.get("action_items", [])
        if not action_items:
            return

        self._render_section_title("액션 아이템")

        # 컬럼 너비
        usable_width = pdf.w - 2 * self.MARGIN
        col_widths = [
            usable_width * 0.20,  # 담당자
            usable_width * 0.45,  # 작업
            usable_width * 0.20,  # 기한
            usable_width * 0.15,  # 우선순위
        ]
        headers = ["담당자", "작업", "기한", "우선순위"]
        row_height = 8

        # 헤더 행
        pdf.set_fill_color(*self.COLOR_HEADER_BG)
        pdf.set_draw_color(*self.COLOR_BORDER)
        pdf.set_font("NotoSansKR", "B", 9)
        pdf.set_text_color(*self.COLOR_TEXT)
        for header, width in zip(headers, col_widths):
            pdf.cell(width, row_height, header, border=1, align="C", fill=True)
        pdf.ln()

        # 데이터 행
        pdf.set_font("NotoSansKR", "", 9)
        pdf.set_fill_color(255, 255, 255)

        # 우선순위 한국어 변환
        priority_map = {"high": "높음", "medium": "중간", "low": "낮음"}

        for item in action_items:
            assignee = str(item.get("assignee", "") or "")
            task = str(item.get("task", "") or "")
            deadline = str(item.get("deadline", "") or "")
            raw_priority = str(item.get("priority", "") or "")
            priority = priority_map.get(raw_priority, raw_priority)

            values = [assignee, task, deadline, priority]
            aligns = ["C", "L", "C", "C"]
            for val, width, align in zip(values, col_widths, aligns):
                pdf.cell(width, row_height, val, border=1, align=align)
            pdf.ln()

        pdf.ln(4)

    # ---------------------------------------------------------------------------
    # 양식 테이블 렌더링 (화면과 동일한 형태)
    # ---------------------------------------------------------------------------

    def _render_template_table(self, minutes_data: dict, summary_data: dict) -> None:
        """화면의 회의록 양식 테이블과 동일한 형태로 PDF 생성"""
        pdf = self.pdf
        template = summary_data.get("template_structure", {})
        sections = summary_data.get("sections", {})
        table_layout = template.get("table_layout", [])
        created_at = minutes_data.get("created_at", "")

        # 고정값
        course_name = "심화 ROS2와 AI를 이용한 자율주행&로봇팔 개발자 부트캠프"
        date_str = created_at[:16] if len(created_at) >= 16 else created_at

        # 제목
        pdf.set_font("NotoSansKR", "B", 16)
        pdf.set_text_color(*self.COLOR_TITLE)
        pdf.cell(0, 10, f"회의록_{created_at[:10] if created_at else ''}", align="L",
                 new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)

        usable_width = pdf.w - 2 * self.MARGIN
        label_width = usable_width * 0.22
        value_width = usable_width * 0.78

        def resolve_value(label: str) -> str:
            if label == "과정명":
                return course_name
            if label in ("미팅시간", "회의일시"):
                return date_str
            return str(sections.get(label, "-") or "-")

        def render_full_row(label: str, large: bool = False) -> None:
            """2열 행: 라벨 | 내용"""
            value = resolve_value(label)
            row_h = 8

            # 라벨 셀
            pdf.set_fill_color(*self.COLOR_HEADER_BG)
            pdf.set_font("NotoSansKR", "B", 9)
            pdf.set_text_color(*self.COLOR_TEXT)

            # 내용이 긴 경우 multi_cell 사용
            if large or len(value) > 60:
                # 라벨
                pdf.cell(label_width, row_h, label, border=1, fill=True)
                # 내용 multi_cell
                pdf.set_font("NotoSansKR", "", 9)
                pdf.set_fill_color(255, 255, 240)  # 연한 노란색
                pdf.multi_cell(value_width, 6, value, border=1, fill=True)
                # 라벨 높이 맞추기 (multi_cell이 y를 이동하므로)
            else:
                pdf.cell(label_width, row_h, label, border=1, fill=True)
                pdf.set_font("NotoSansKR", "", 9)
                pdf.set_fill_color(255, 255, 255)
                pdf.cell(value_width, row_h, value, border=1,
                         new_x="LMARGIN", new_y="NEXT")

        def render_split_row(labels: list[str]) -> None:
            """N열 행: 라벨1 | 내용1 | 라벨2 | 내용2 ..."""
            n = len(labels)
            if n == 0:
                return
            cell_w = usable_width / (n * 2)  # 각 라벨+값 쌍의 너비
            lbl_w = cell_w * 0.45
            val_w = cell_w * 0.55
            row_h = 8

            for label in labels:
                value = resolve_value(label)
                # 라벨
                pdf.set_fill_color(*self.COLOR_HEADER_BG)
                pdf.set_font("NotoSansKR", "B", 9)
                pdf.cell(lbl_w, row_h, label, border=1, fill=True)
                # 값
                pdf.set_font("NotoSansKR", "", 9)
                pdf.set_fill_color(255, 255, 255)
                pdf.cell(val_w, row_h, value[:30], border=1)  # 30자 제한 (셀 크기)

            pdf.ln()

        # 테이블 레이아웃 렌더링
        for row_def in table_layout:
            row_type = row_def.get("type", "full")
            if row_type == "split":
                cells = row_def.get("cells", [])
                labels = [c.get("label", "") for c in cells]
                render_split_row(labels)
            else:
                label = row_def.get("label", "")
                is_large = "내용" in label or "이슈" in label or "논의" in label
                render_full_row(label, large=is_large)

        pdf.ln(6)

    # ---------------------------------------------------------------------------
    # 유틸리티 메서드
    # ---------------------------------------------------------------------------

    def _render_section_title(self, title: str) -> None:
        """섹션 헤더 (볼드, 남색) 렌더링"""
        pdf = self.pdf
        pdf.set_font("NotoSansKR", "B", 12)
        pdf.set_text_color(*self.COLOR_SECTION)
        pdf.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")

        # 섹션 구분선
        pdf.set_draw_color(*self.COLOR_BORDER)
        pdf.set_line_width(0.3)
        pdf.line(
            self.MARGIN,
            pdf.get_y(),
            pdf.w - self.MARGIN,
            pdf.get_y(),
        )
        pdf.ln(3)

    @staticmethod
    def _format_duration_mmss(seconds: float) -> str:
        """
        초를 MM:SS 형식으로 변환

        Args:
            seconds: 초 단위 시간

        Returns:
            'MM:SS' 형식 문자열 (예: '02:35')
        """
        total_seconds = int(seconds)
        minutes = total_seconds // 60
        secs = total_seconds % 60
        return f"{minutes:02d}:{secs:02d}"

    @staticmethod
    def _format_duration_hhmmss(seconds: float) -> str:
        """
        초를 HH:MM:SS 형식으로 변환

        Args:
            seconds: 초 단위 시간

        Returns:
            'HH:MM:SS' 형식 문자열 (예: '01:23:45')
        """
        total_seconds = int(seconds)
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        secs = total_seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
