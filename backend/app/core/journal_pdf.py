"""영농일지 PDF 생성 — fpdf2 (세련된 디자인, 농업ON 양식 기반)."""

from datetime import date
from itertools import groupby

from fpdf import FPDF

from app.core.config import settings
from app.models.journal import JournalEntry

# ── 색상 팔레트 ──

PRIMARY = (45, 95, 45)  # #2D5F2D 진한 녹색
PRIMARY_LIGHT = (240, 253, 244)  # #f0fdf4 연한 녹색
GRAY_50 = (249, 250, 251)
GRAY_200 = (180, 180, 180)
GRAY_400 = (156, 163, 175)
GRAY_700 = (55, 65, 81)
GRAY_900 = (17, 24, 39)
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
BORDER_COLOR = (100, 100, 100)

STAGE_STYLES = {
    "사전준비": {"fg": (107, 114, 128), "bg": (243, 244, 246)},
    "경운": {"fg": (180, 83, 9), "bg": (254, 243, 199)},
    "파종": {"fg": (21, 128, 61), "bg": (220, 252, 231)},
    "정식": {"fg": (4, 120, 87), "bg": (209, 250, 229)},
    "작물관리": {"fg": (29, 78, 216), "bg": (219, 234, 254)},
    "수확": {"fg": (194, 65, 12), "bg": (255, 237, 213)},
}

# ── 레이아웃 상수 ──

PAGE_W = 210
MARGIN = 15
CONTENT_W = PAGE_W - MARGIN * 2  # 180mm
ROW_H = 7
CARD_PAD = 4
MAX_Y = 265


class JournalPDF(FPDF):
    """영농일지 전용 PDF."""

    def __init__(self, farm_name: str, date_from: date, date_to: date):
        super().__init__(orientation="P", format="A4")
        self.farm_name = farm_name
        self.date_from = date_from
        self.date_to = date_to
        self.add_font("malgun", "", settings.FONT_PATH, uni=True)
        # Bold 폰트: malgunbd.ttf (같은 폴더)
        import os

        bold_path = os.path.join(os.path.dirname(settings.FONT_PATH), "malgunbd.ttf")
        self.add_font("malgun", "B", bold_path, uni=True)
        self.set_auto_page_break(auto=False)
        self.set_margins(MARGIN, MARGIN, MARGIN)

    def header(self):
        # 상단 녹색 바
        self.set_fill_color(*PRIMARY)
        self.rect(0, 0, PAGE_W, 3, "F")

        self.ln(8)
        # 타이틀
        self.set_font("malgun", "B", 18)
        self.set_text_color(*PRIMARY)
        self.cell(0, 10, "영 농 일 지", align="C", new_x="LMARGIN", new_y="NEXT")

        # 부제
        self.set_font("malgun", "", 9)
        self.set_text_color(*GRAY_400)
        self.cell(
            0,
            6,
            f"{self.farm_name}  |  {self.date_from} ~ {self.date_to}",
            align="C",
            new_x="LMARGIN",
            new_y="NEXT",
        )

        # 구분선
        self.ln(2)
        self.set_draw_color(*PRIMARY)
        self.set_line_width(0.5)
        self.line(MARGIN, self.get_y(), PAGE_W - MARGIN, self.get_y())
        self.ln(6)

    def footer(self):
        self.set_y(-12)
        self.set_font("malgun", "", 7)
        self.set_text_color(*GRAY_400)
        self.cell(0, 10, f"- {self.page_no()} -", align="C")


def _draw_badge(pdf: FPDF, text: str, x: float, y: float, style: dict):
    """작업단계 배지 (둥근 사각형 + 배경색)."""
    pdf.set_font("malgun", "B", 7)
    w = pdf.get_string_width(text) + 8
    h = 5.5

    # 둥근 배경
    pdf.set_fill_color(*style["bg"])
    pdf.set_draw_color(*style["bg"])
    pdf.rect(x, y, w, h, round_corners=True, style="FD", corner_radius=2)

    # 텍스트
    pdf.set_xy(x, y + 0.3)
    pdf.set_text_color(*style["fg"])
    pdf.cell(w, h, text, align="C")

    return w


def _draw_card_header(pdf: FPDF, entry: JournalEntry, x: float, y: float):
    """카드 헤더 (배지 + 작목 + 필지 + 날씨)."""
    # 배경 (채우기만, 외곽선은 카드 외곽선이 담당)
    pdf.set_fill_color(*GRAY_50)
    pdf.rect(x + 0.2, y + 0.2, CONTENT_W - 0.4, 9.8, style="F")

    # 배지
    style = STAGE_STYLES.get(entry.work_stage, STAGE_STYLES["사전준비"])
    badge_w = _draw_badge(pdf, entry.work_stage, x + 3, y + 2.2, style)

    # 작목
    cx = x + 3 + badge_w + 4
    pdf.set_xy(cx, y)
    pdf.set_font("malgun", "B", 9)
    pdf.set_text_color(*BLACK)
    pdf.cell(0, 10, entry.crop)

    # 필지
    cx += pdf.get_string_width(entry.crop) + 4
    pdf.set_xy(cx, y)
    pdf.set_font("malgun", "", 8)
    pdf.set_text_color(*BLACK)
    pdf.cell(0, 10, entry.field_name)

    # 날씨 (오른쪽)
    if entry.weather:
        pdf.set_font("malgun", "", 8)
        pdf.set_text_color(*BLACK)
        w = pdf.get_string_width(entry.weather)
        pdf.set_xy(x + CONTENT_W - w - 4, y)
        pdf.cell(w, 10, entry.weather)


def _draw_chem_row(
    pdf: FPDF, label: str, product: str, amount: str, x: float, y: float
):
    """농약/비료 한 줄."""
    col_w = [25, 95, 60]

    pdf.set_xy(x, y)
    pdf.set_text_color(*BLACK)
    pdf.set_draw_color(*BORDER_COLOR)

    pdf.set_fill_color(*WHITE)
    pdf.set_font("malgun", "B", 7.5)
    pdf.cell(col_w[0], ROW_H, f" {label}", border=1, fill=True)
    pdf.set_font("malgun", "", 7.5)
    pdf.cell(col_w[1], ROW_H, f" {product}", border=1, fill=True)
    pdf.cell(col_w[2], ROW_H, f" {amount or '-'}", border=1, fill=True)


def _draw_chem_section(pdf: FPDF, title: str, rows: list, x: float, y: float) -> float:
    """농약/비료 섹션 (제목 + 헤더 + 데이터 행). 사용한 높이 반환."""
    if not rows:
        return 0

    # 섹션 제목
    pdf.set_xy(x, y)
    pdf.set_font("malgun", "B", 7.5)
    pdf.set_fill_color(*PRIMARY_LIGHT)
    pdf.set_text_color(*BLACK)
    pdf.set_draw_color(*BORDER_COLOR)
    pdf.cell(CONTENT_W, ROW_H, f"  {title}", fill=True, border=1)
    cy = y + ROW_H

    # 헤더
    col_w = [25, 95, 60]
    headers = ["구분", "제품명", "수량/사용량"]
    pdf.set_xy(x, cy)
    pdf.set_font("malgun", "B", 7)
    pdf.set_fill_color(248, 250, 252)
    pdf.set_text_color(*BLACK)
    for i, h in enumerate(headers):
        pdf.cell(col_w[i], ROW_H, h, border=1, fill=True, align="C")
    cy += ROW_H

    # 데이터 행
    for label, product, amount in rows:
        _draw_chem_row(pdf, label, product, amount, x, cy)
        cy += ROW_H

    return cy - y


def _draw_entry_card(pdf: JournalPDF, entry: JournalEntry):
    """일지 1건을 카드 형태로 그리기."""
    x = MARGIN
    y = pdf.get_y()

    # 카드 높이 예측 (대략)
    card_h = 12  # 헤더
    has_purchase = entry.purchase_pesticide_product or entry.purchase_fertilizer_product
    has_usage = entry.usage_pesticide_product or entry.usage_fertilizer_product
    if has_purchase:
        card_h += (
            ROW_H * 2
            + (ROW_H if entry.purchase_pesticide_product else 0)
            + (ROW_H if entry.purchase_fertilizer_product else 0)
        )
    if has_usage:
        card_h += (
            ROW_H * 2
            + (ROW_H if entry.usage_pesticide_product else 0)
            + (ROW_H if entry.usage_fertilizer_product else 0)
        )
    card_h += 12  # 세부작업내용 (항상 표시)

    # 페이지 넘김 체크
    if y + card_h > MAX_Y:
        pdf.add_page()
        y = pdf.get_y()

    # 카드 외곽선 (둥근 모서리)
    card_start_y = y
    pdf.set_draw_color(*GRAY_200)
    pdf.set_line_width(0.3)

    # 헤더
    _draw_card_header(pdf, entry, x, y)
    y += 10

    # 농약/비료 구입
    if has_purchase:
        rows = []
        if entry.purchase_pesticide_product:
            rows.append(
                (
                    "농약",
                    entry.purchase_pesticide_product,
                    entry.purchase_pesticide_amount or "",
                )
            )
        if entry.purchase_fertilizer_product:
            rows.append(
                (
                    "비료",
                    entry.purchase_fertilizer_product,
                    entry.purchase_fertilizer_amount or "",
                )
            )
        h = _draw_chem_section(pdf, "농약/비료 구입", rows, x, y)
        y += h

    # 농약/비료 사용
    if has_usage:
        rows = []
        if entry.usage_pesticide_product:
            rows.append(
                (
                    "농약",
                    entry.usage_pesticide_product,
                    entry.usage_pesticide_amount or "",
                )
            )
        if entry.usage_fertilizer_product:
            rows.append(
                (
                    "비료",
                    entry.usage_fertilizer_product,
                    entry.usage_fertilizer_amount or "",
                )
            )
        h = _draw_chem_section(pdf, "농약/비료 사용", rows, x, y)
        y += h

    # 세부작업내용
    detail_text = entry.detail if entry.detail else " "
    pdf.set_xy(x + 3, y + 2)
    pdf.set_font("malgun", "", 8)
    pdf.set_text_color(*BLACK)
    pdf.multi_cell(CONTENT_W - 6, 5, detail_text, max_line_height=5)
    y = pdf.get_y() + 2

    # 카드 외곽선 그리기
    card_h_actual = y - card_start_y + 1
    pdf.set_draw_color(*BORDER_COLOR)
    pdf.set_line_width(0.4)
    pdf.rect(
        x,
        card_start_y,
        CONTENT_W,
        card_h_actual,
        round_corners=True,
        style="D",
        corner_radius=2,
    )

    pdf.set_y(y + 4)


def generate_journal_pdf(
    entries: list[JournalEntry],
    farm_name: str,
    date_from: date,
    date_to: date,
) -> bytes:
    """영농일지 목록을 PDF로 생성."""
    pdf = JournalPDF(farm_name, date_from, date_to)
    pdf.add_page()

    sorted_entries = sorted(entries, key=lambda e: (e.work_date, e.id))

    if not sorted_entries:
        pdf.set_font("malgun", "", 10)
        pdf.set_text_color(*GRAY_400)
        pdf.ln(30)
        pdf.cell(0, 10, "해당 기간에 기록된 영농일지가 없습니다.", align="C")
        return bytes(pdf.output())

    # 날짜별 그룹핑
    for work_date, group in groupby(sorted_entries, key=lambda e: e.work_date):
        entries_list = list(group)
        date_label = work_date.strftime("%Y년 %m월 %d일")

        # 날짜 라벨
        if pdf.get_y() > MAX_Y - 40:
            pdf.add_page()

        pdf.set_font("malgun", "B", 10)
        pdf.set_text_color(*BLACK)
        pdf.cell(0, 8, date_label, new_x="LMARGIN", new_y="NEXT")

        # 날짜 밑줄
        pdf.set_draw_color(*BORDER_COLOR)
        pdf.set_line_width(0.3)
        pdf.line(MARGIN, pdf.get_y(), PAGE_W - MARGIN, pdf.get_y())
        pdf.ln(3)

        # 각 일지 카드
        for entry in entries_list:
            _draw_entry_card(pdf, entry)

    return bytes(pdf.output())
