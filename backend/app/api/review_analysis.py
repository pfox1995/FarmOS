"""리뷰 분석 API 라우터.

# Design Ref: §4 — API Design
# Plan SC: SC-01~SC-07 통합

엔드포인트:
    POST /api/v1/reviews/analyze       분석 실행 (수동)
    GET  /api/v1/reviews/analysis      최신 분석 결과 조회
    POST /api/v1/reviews/search        RAG 의미 검색
    GET  /api/v1/reviews/trends        트렌드/이상 탐지
    GET  /api/v1/reviews/report/pdf    PDF 리포트 다운로드
    POST /api/v1/reviews/embed         리뷰 임베딩 저장
    GET  /api/v1/reviews/settings      자동 분석 설정 조회
    PUT  /api/v1/reviews/settings      자동 분석 설정 변경
"""

import asyncio
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.core.review_rag import ReviewRAG
from app.core.review_analyzer import ReviewAnalyzer
from app.core.trend_detector import TrendDetector
from app.core.review_report import ReviewReportGenerator
from app.models.review_analysis import ReviewAnalysis
from app.schemas.review_analysis import (
    AnalyzeRequest,
    AnalyzeResponse,
    AnalysisSettings,
    AnalysisSettingsUpdate,
    AnalysisListItem,
    AnomalyAlert,
    EmbedRequest,
    EmbedResponse,
    KeywordItem,
    SearchRequest,
    SearchResponse,
    SearchResult,
    SentimentSummary,
    SummaryData,
    TrendData,
    TrendsResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reviews", tags=["review-analysis"])

# 서비스 인스턴스 (싱글턴)
_rag = ReviewRAG()
_analyzer = ReviewAnalyzer()
_trend_detector = TrendDetector()
_report_generator = ReviewReportGenerator()

# 인메모리 설정 (추후 DB로 이동 가능)
_settings = AnalysisSettings()

# Mock 리뷰 데이터 (개발용, 프론트엔드 mocks/reviews.ts와 동일한 150건)
MOCK_REVIEWS = [
    {"id": "rev-01", "text": "당도가 정말 높고 아삭해요! 포장도 꼼꼼하게 해주셔서 감사합니다.", "rating": 5, "platform": "네이버스마트스토어", "date": "2026-03-02"},
    {"id": "rev-02", "text": "사과가 크고 맛있어요. 재구매 의사 있습니다.", "rating": 5, "platform": "쿠팡", "date": "2026-03-02"},
    {"id": "rev-03", "text": "배송이 좀 느렸지만 사과 품질은 좋아요.", "rating": 4, "platform": "네이버스마트스토어", "date": "2026-03-03"},
    {"id": "rev-04", "text": "하나가 멍이 들어있었어요. 나머지는 괜찮았습니다.", "rating": 3, "platform": "쿠팡", "date": "2026-03-03"},
    {"id": "rev-05", "text": "색깔이 예쁘고 신선해요. 선물용으로 좋았습니다.", "rating": 5, "platform": "네이버스마트스토어", "date": "2026-03-04"},
    {"id": "rev-06", "text": "가성비 좋은 사과입니다. 맛도 괜찮아요.", "rating": 4, "platform": "쿠팡", "date": "2026-03-04"},
    {"id": "rev-07", "text": "크기가 제각각이에요. 좀 아쉽습니다.", "rating": 3, "platform": "네이버스마트스토어", "date": "2026-03-05"},
    {"id": "rev-08", "text": "아이들이 너무 좋아해요! 단맛이 딱 좋아요.", "rating": 5, "platform": "쿠팡", "date": "2026-03-05"},
    {"id": "rev-09", "text": "영주 사과 역시 맛있네요. 껍질째 먹었어요.", "rating": 5, "platform": "네이버스마트스토어", "date": "2026-03-06"},
    {"id": "rev-10", "text": "보통이에요. 특별한 맛은 아닙니다.", "rating": 3, "platform": "쿠팡", "date": "2026-03-06"},
    {"id": "rev-11", "text": "포장이 정말 깔끔해요. 사과도 싱싱합니다.", "rating": 5, "platform": "네이버스마트스토어", "date": "2026-03-07"},
    {"id": "rev-12", "text": "맛있게 잘 먹었습니다. 감사합니다.", "rating": 4, "platform": "쿠팡", "date": "2026-03-07"},
    {"id": "rev-13", "text": "사과즙 만들어 먹었어요. 달달해요!", "rating": 5, "platform": "네이버스마트스토어", "date": "2026-03-08"},
    {"id": "rev-14", "text": "이 가격에 이 품질이면 합격!", "rating": 4, "platform": "쿠팡", "date": "2026-03-08"},
    {"id": "rev-15", "text": "배송 중 하나 깨졌어요. 교환해 주시면 좋겠습니다.", "rating": 2, "platform": "네이버스마트스토어", "date": "2026-03-09"},
    {"id": "rev-16", "text": "단맛과 신맛의 밸런스가 좋아요.", "rating": 5, "platform": "쿠팡", "date": "2026-03-09"},
    {"id": "rev-17", "text": "친환경이라 안심하고 먹어요.", "rating": 5, "platform": "네이버스마트스토어", "date": "2026-03-10"},
    {"id": "rev-18", "text": "그냥 그래요. 기대보다는 좀...", "rating": 2, "platform": "쿠팡", "date": "2026-03-10"},
    {"id": "rev-19", "text": "다음에도 꼭 구매할게요!", "rating": 5, "platform": "네이버스마트스토어", "date": "2026-03-11"},
    {"id": "rev-20", "text": "프리미엄 사과 느낌이에요. 만족합니다.", "rating": 5, "platform": "쿠팡", "date": "2026-03-11"},
    {"id": "rev-21", "text": "할머니 선물로 보냈더니 너무 좋아하세요.", "rating": 5, "platform": "네이버스마트스토어", "date": "2026-03-12"},
    {"id": "rev-22", "text": "상태 별로. 물러진 것이 2개 있었음.", "rating": 2, "platform": "쿠팡", "date": "2026-03-12"},
    {"id": "rev-23", "text": "아삭아삭 맛있어요. 영주 사과 최고!", "rating": 5, "platform": "네이버스마트스토어", "date": "2026-03-13"},
    {"id": "rev-24", "text": "일반 마트보다 맛있네요. 직거래의 매력.", "rating": 4, "platform": "쿠팡", "date": "2026-03-13"},
    {"id": "rev-25", "text": "크기도 균일하고 맛도 좋아요. 추천!", "rating": 5, "platform": "네이버스마트스토어", "date": "2026-03-14"},
    {"id": "rev-26", "text": "빠른 배송 감사합니다.", "rating": 4, "platform": "쿠팡", "date": "2026-03-14"},
    {"id": "rev-27", "text": "사무실 간식으로 샀는데 동료들이 맛있대요.", "rating": 5, "platform": "네이버스마트스토어", "date": "2026-03-14"},
    {"id": "rev-28", "text": "포장 박스가 약해서 좀 걱정했는데 다행히 괜찮았어요.", "rating": 3, "platform": "쿠팡", "date": "2026-03-15"},
    {"id": "rev-29", "text": "당도 14Brix 이상! 최고의 사과입니다.", "rating": 5, "platform": "네이버스마트스토어", "date": "2026-03-15"},
    {"id": "rev-30", "text": "사과잼 만들어 먹으려고 샀어요. 적합합니다.", "rating": 4, "platform": "쿠팡", "date": "2026-03-15"},
    {"id": "rev-31", "text": "매년 이맘때 주문해요. 올해도 맛있네요.", "rating": 5, "platform": "네이버스마트스토어", "date": "2026-03-15"},
    {"id": "rev-32", "text": "기대했는데 좀 시큼해요.", "rating": 3, "platform": "쿠팡", "date": "2026-03-15"},
    {"id": "rev-33", "text": "10kg 세트 알차게 왔어요.", "rating": 4, "platform": "네이버스마트스토어", "date": "2026-03-15"},
    {"id": "rev-34", "text": "가격 대비 양이 많아요. 좋습니다.", "rating": 4, "platform": "쿠팡", "date": "2026-03-15"},
    {"id": "rev-35", "text": "향이 정말 좋아요. 사과 냄새가 집 안에 가득!", "rating": 5, "platform": "네이버스마트스토어", "date": "2026-03-15"},
    {"id": "rev-36", "text": "괜찮은 사과예요.", "rating": 3, "platform": "쿠팡", "date": "2026-03-15"},
    {"id": "rev-37", "text": "아이 간식으로 최고예요.", "rating": 5, "platform": "네이버스마트스토어", "date": "2026-03-15"},
    {"id": "rev-38", "text": "색감이 예뻐서 선물용으로 좋아요.", "rating": 5, "platform": "쿠팡", "date": "2026-03-15"},
    {"id": "rev-39", "text": "껍질이 얇아서 먹기 편해요.", "rating": 4, "platform": "네이버스마트스토어", "date": "2026-03-15"},
    {"id": "rev-40", "text": "상자 찌그러져서 왔어요. 사과는 괜찮았지만.", "rating": 3, "platform": "쿠팡", "date": "2026-03-15"},
    {"id": "rev-41", "text": "부사보다 홍로가 더 맛있는 것 같아요.", "rating": 4, "platform": "네이버스마트스토어", "date": "2026-03-15"},
    {"id": "rev-42", "text": "좋습니다. 다음에 또 살게요.", "rating": 4, "platform": "쿠팡", "date": "2026-03-15"},
    {"id": "rev-43", "text": "시어머니가 맛있다고 하세요.", "rating": 5, "platform": "네이버스마트스토어", "date": "2026-03-15"},
    {"id": "rev-44", "text": "별로...", "rating": 1, "platform": "쿠팡", "date": "2026-03-15"},
    {"id": "rev-45", "text": "건강한 사과! 유기농이라 더 좋아요.", "rating": 5, "platform": "네이버스마트스토어", "date": "2026-03-15"},
    {"id": "rev-46", "text": "달아요. 아이들 좋아합니다.", "rating": 4, "platform": "쿠팡", "date": "2026-03-15"},
    {"id": "rev-47", "text": "항상 믿고 삽니다.", "rating": 5, "platform": "네이버스마트스토어", "date": "2026-03-15"},
    {"id": "rev-48", "text": "보통 수준이에요.", "rating": 3, "platform": "쿠팡", "date": "2026-03-15"},
    {"id": "rev-49", "text": "사과파이 만들었어요. 최고!", "rating": 5, "platform": "네이버스마트스토어", "date": "2026-03-15"},
    {"id": "rev-50", "text": "잘 받았습니다. 신선하네요.", "rating": 4, "platform": "쿠팡", "date": "2026-03-15"},
    {"id": "rev-51", "text": "올해 사과 중 최고예요. 당도가 장난 아닙니다.", "rating": 5, "platform": "네이버스마트스토어", "date": "2026-03-16"},
    {"id": "rev-52", "text": "배송은 빨랐는데 사과 2개가 물렀어요.", "rating": 2, "platform": "쿠팡", "date": "2026-03-16"},
    {"id": "rev-53", "text": "아이 도시락에 넣어주기 좋은 크기예요.", "rating": 4, "platform": "네이버스마트스토어", "date": "2026-03-16"},
    {"id": "rev-54", "text": "사과 향이 진해서 좋아요. 방 안에 두면 향기가 나요.", "rating": 5, "platform": "쿠팡", "date": "2026-03-16"},
    {"id": "rev-55", "text": "작년보다 맛이 떨어진 것 같아요.", "rating": 3, "platform": "네이버스마트스토어", "date": "2026-03-17"},
    {"id": "rev-56", "text": "가족 모두 맛있게 먹었습니다!", "rating": 5, "platform": "쿠팡", "date": "2026-03-17"},
    {"id": "rev-57", "text": "유기농 인증 사과라 믿고 삽니다.", "rating": 5, "platform": "네이버스마트스토어", "date": "2026-03-17"},
    {"id": "rev-58", "text": "상자 모서리가 찢어져서 왔어요.", "rating": 2, "platform": "쿠팡", "date": "2026-03-17"},
    {"id": "rev-59", "text": "즙이 많고 씹는 맛이 좋아요.", "rating": 5, "platform": "네이버스마트스토어", "date": "2026-03-18"},
    {"id": "rev-60", "text": "그럭저럭이에요. 특별하지 않습니다.", "rating": 3, "platform": "쿠팡", "date": "2026-03-18"},
    {"id": "rev-61", "text": "명절 선물세트로 주문했어요. 포장이 고급스러워요.", "rating": 5, "platform": "네이버스마트스토어", "date": "2026-03-18"},
    {"id": "rev-62", "text": "사과가 너무 작아요. 사진이랑 다릅니다.", "rating": 1, "platform": "쿠팡", "date": "2026-03-18"},
    {"id": "rev-63", "text": "껍질째 먹어도 안심되는 친환경 사과!", "rating": 5, "platform": "네이버스마트스토어", "date": "2026-03-19"},
    {"id": "rev-64", "text": "단맛이 강해서 아이들이 좋아해요.", "rating": 4, "platform": "쿠팡", "date": "2026-03-19"},
    {"id": "rev-65", "text": "벌레 먹은 사과가 하나 있었어요. 실망입니다.", "rating": 1, "platform": "네이버스마트스토어", "date": "2026-03-19"},
    {"id": "rev-66", "text": "주스 만들어 먹으려고 샀어요. 적합합니다.", "rating": 4, "platform": "쿠팡", "date": "2026-03-19"},
    {"id": "rev-67", "text": "부사 사과인데 홍옥 맛이 나요. 품종이 맞나요?", "rating": 2, "platform": "네이버스마트스토어", "date": "2026-03-20"},
    {"id": "rev-68", "text": "매번 주문하는 단골입니다. 항상 만족!", "rating": 5, "platform": "쿠팡", "date": "2026-03-20"},
    {"id": "rev-69", "text": "어머니 생신 선물로 보냈는데 아주 좋아하세요.", "rating": 5, "platform": "네이버스마트스토어", "date": "2026-03-20"},
    {"id": "rev-70", "text": "포장 완충재가 부족해요. 개선 바랍니다.", "rating": 2, "platform": "쿠팡", "date": "2026-03-20"},
    {"id": "rev-71", "text": "당도 15Brix 넘는 것 같아요. 꿀맛!", "rating": 5, "platform": "네이버스마트스토어", "date": "2026-03-21"},
    {"id": "rev-72", "text": "보관법을 같이 보내주시면 좋겠어요.", "rating": 3, "platform": "쿠팡", "date": "2026-03-21"},
    {"id": "rev-73", "text": "아삭하고 달아서 샐러드에 넣어 먹었어요.", "rating": 5, "platform": "네이버스마트스토어", "date": "2026-03-21"},
    {"id": "rev-74", "text": "배송 3일 걸렸어요. 좀 느립니다.", "rating": 3, "platform": "쿠팡", "date": "2026-03-21"},
    {"id": "rev-75", "text": "회사 동료들한테 나눠줬더니 어디서 샀냐고 물어봐요.", "rating": 5, "platform": "네이버스마트스토어", "date": "2026-03-22"},
    {"id": "rev-76", "text": "사과잼 만들기 딱 좋은 당도예요.", "rating": 4, "platform": "쿠팡", "date": "2026-03-22"},
    {"id": "rev-77", "text": "5kg 세트 주문했는데 무게가 좀 부족한 것 같아요.", "rating": 3, "platform": "네이버스마트스토어", "date": "2026-03-22"},
    {"id": "rev-78", "text": "색깔이 빨갛고 예뻐요. 선물용으로 딱!", "rating": 5, "platform": "쿠팡", "date": "2026-03-22"},
    {"id": "rev-79", "text": "아침에 사과 하나씩 먹고 있어요. 건강해지는 느낌!", "rating": 5, "platform": "네이버스마트스토어", "date": "2026-03-23"},
    {"id": "rev-80", "text": "사과 식초 담그려고 주문했습니다.", "rating": 4, "platform": "쿠팡", "date": "2026-03-23"},
    {"id": "rev-81", "text": "간식 대용으로 딱이에요. 칼로리 걱정 없이!", "rating": 5, "platform": "네이버스마트스토어", "date": "2026-03-23"},
    {"id": "rev-82", "text": "택배 기사님이 던지셨는지 멍투성이에요.", "rating": 1, "platform": "쿠팡", "date": "2026-03-23"},
    {"id": "rev-83", "text": "신맛과 단맛 밸런스가 완벽해요.", "rating": 5, "platform": "네이버스마트스토어", "date": "2026-03-24"},
    {"id": "rev-84", "text": "가격이 좀 비싼 편이지만 품질은 좋습니다.", "rating": 4, "platform": "쿠팡", "date": "2026-03-24"},
    {"id": "rev-85", "text": "지인 추천으로 처음 구매했는데 만족스럽습니다.", "rating": 5, "platform": "네이버스마트스토어", "date": "2026-03-24"},
    {"id": "rev-86", "text": "사과가 다 익지 않은 상태로 왔어요.", "rating": 2, "platform": "쿠팡", "date": "2026-03-24"},
    {"id": "rev-87", "text": "과즙이 풍부해요. 한 입 베어물면 즙이 뚝뚝!", "rating": 5, "platform": "네이버스마트스토어", "date": "2026-03-25"},
    {"id": "rev-88", "text": "평범한 사과예요. 특별할 건 없습니다.", "rating": 3, "platform": "쿠팡", "date": "2026-03-25"},
    {"id": "rev-89", "text": "영주 사과라서 믿고 주문합니다.", "rating": 5, "platform": "네이버스마트스토어", "date": "2026-03-25"},
    {"id": "rev-90", "text": "교환 요청했는데 빠르게 처리해주셨어요. 감사합니다.", "rating": 3, "platform": "쿠팡", "date": "2026-03-25"},
    {"id": "rev-91", "text": "사과 칩 만들어 먹었어요. 아이들 간식으로 최고!", "rating": 5, "platform": "네이버스마트스토어", "date": "2026-03-26"},
    {"id": "rev-92", "text": "농장에서 직접 보내주시는 거라 신선해요.", "rating": 5, "platform": "쿠팡", "date": "2026-03-26"},
    {"id": "rev-93", "text": "작은 사이즈로 주문했는데 생각보다 커서 좋았어요.", "rating": 4, "platform": "네이버스마트스토어", "date": "2026-03-26"},
    {"id": "rev-94", "text": "반품하고 싶은데 절차가 복잡해요.", "rating": 1, "platform": "쿠팡", "date": "2026-03-26"},
    {"id": "rev-95", "text": "추석 때 또 주문할게요!", "rating": 5, "platform": "네이버스마트스토어", "date": "2026-03-27"},
    {"id": "rev-96", "text": "무농약이라 안심하고 먹을 수 있어요.", "rating": 5, "platform": "쿠팡", "date": "2026-03-27"},
    {"id": "rev-97", "text": "사과 타르트 만들었는데 대성공이에요!", "rating": 5, "platform": "네이버스마트스토어", "date": "2026-03-27"},
    {"id": "rev-98", "text": "상품 설명이랑 실제가 좀 달라요.", "rating": 2, "platform": "쿠팡", "date": "2026-03-27"},
    {"id": "rev-99", "text": "냉장 보관하면 한 달은 거뜬해요.", "rating": 4, "platform": "네이버스마트스토어", "date": "2026-03-28"},
    {"id": "rev-100", "text": "두 번째 구매인데 이번에도 만족합니다.", "rating": 5, "platform": "쿠팡", "date": "2026-03-28"},
    {"id": "rev-101", "text": "세 박스 주문했어요. 친척들한테 나눠줬습니다.", "rating": 5, "platform": "네이버스마트스토어", "date": "2026-03-28"},
    {"id": "rev-102", "text": "비닐 포장만 되어있고 완충재가 없었어요.", "rating": 2, "platform": "쿠팡", "date": "2026-03-28"},
    {"id": "rev-103", "text": "다이어트 중인데 사과로 대체하고 있어요. 맛있어서 가능!", "rating": 5, "platform": "네이버스마트스토어", "date": "2026-03-29"},
    {"id": "rev-104", "text": "시큼한 맛을 좋아하는데 너무 달아요.", "rating": 3, "platform": "쿠팡", "date": "2026-03-29"},
    {"id": "rev-105", "text": "포장 박스 디자인이 귀여워요.", "rating": 4, "platform": "네이버스마트스토어", "date": "2026-03-29"},
    {"id": "rev-106", "text": "주문한 지 5일이나 걸렸어요.", "rating": 2, "platform": "쿠팡", "date": "2026-03-29"},
    {"id": "rev-107", "text": "할아버지 댁에 보내드렸더니 손자가 왔다고 좋아하세요.", "rating": 5, "platform": "네이버스마트스토어", "date": "2026-03-30"},
    {"id": "rev-108", "text": "사과 하나에 500원도 안 하는 가성비!", "rating": 5, "platform": "쿠팡", "date": "2026-03-30"},
    {"id": "rev-109", "text": "새벽 배송으로 받았는데 신선도가 최고예요.", "rating": 5, "platform": "네이버스마트스토어", "date": "2026-03-30"},
    {"id": "rev-110", "text": "흠집 있는 사과가 몇 개 있었어요.", "rating": 3, "platform": "쿠팡", "date": "2026-03-30"},
    {"id": "rev-111", "text": "영주 고랭지 사과라 그런지 맛이 진해요.", "rating": 5, "platform": "네이버스마트스토어", "date": "2026-03-31"},
    {"id": "rev-112", "text": "박스 안에 감사 카드가 있어서 감동받았어요.", "rating": 5, "platform": "쿠팡", "date": "2026-03-31"},
    {"id": "rev-113", "text": "알이 굵고 탱탱해요. 품질 최고!", "rating": 5, "platform": "네이버스마트스토어", "date": "2026-03-31"},
    {"id": "rev-114", "text": "기대 이하예요. 마트에서 사는 게 나을 것 같아요.", "rating": 2, "platform": "쿠팡", "date": "2026-03-31"},
    {"id": "rev-115", "text": "올해 세 번째 주문이에요. 꾸준히 맛있습니다.", "rating": 5, "platform": "네이버스마트스토어", "date": "2026-04-01"},
    {"id": "rev-116", "text": "아이 유치원 간식으로 가져갔더니 인기 최고!", "rating": 5, "platform": "쿠팡", "date": "2026-04-01"},
    {"id": "rev-117", "text": "깎아서 접시에 담으면 디저트 느낌이에요.", "rating": 4, "platform": "네이버스마트스토어", "date": "2026-04-01"},
    {"id": "rev-118", "text": "썩은 사과가 2개 들어있었습니다. 환불 원합니다.", "rating": 1, "platform": "쿠팡", "date": "2026-04-01"},
    {"id": "rev-119", "text": "시골 할머니 사과 맛이 나요. 정겨워요.", "rating": 5, "platform": "네이버스마트스토어", "date": "2026-04-02"},
    {"id": "rev-120", "text": "가격 대비 괜찮습니다.", "rating": 4, "platform": "쿠팡", "date": "2026-04-02"},
    {"id": "rev-121", "text": "사과잼 레시피도 같이 보내주셔서 감사해요!", "rating": 5, "platform": "네이버스마트스토어", "date": "2026-04-02"},
    {"id": "rev-122", "text": "어제 주문했는데 오늘 도착! 역시 로켓배송.", "rating": 4, "platform": "쿠팡", "date": "2026-04-02"},
    {"id": "rev-123", "text": "아버지가 직접 키우신 사과라니 더 맛있게 느껴져요.", "rating": 5, "platform": "네이버스마트스토어", "date": "2026-04-03"},
    {"id": "rev-124", "text": "왁스 안 바른 사과라 좋아요.", "rating": 5, "platform": "쿠팡", "date": "2026-04-03"},
    {"id": "rev-125", "text": "사과 향초보다 이 사과가 더 향기로워요.", "rating": 5, "platform": "네이버스마트스토어", "date": "2026-04-03"},
    {"id": "rev-126", "text": "지난번보다 크기가 작아진 것 같아요.", "rating": 3, "platform": "쿠팡", "date": "2026-04-03"},
    {"id": "rev-127", "text": "요즘 과일값이 비싼데 여기는 합리적이에요.", "rating": 4, "platform": "네이버스마트스토어", "date": "2026-04-04"},
    {"id": "rev-128", "text": "배송 중 온도 관리가 안 된 것 같아요.", "rating": 2, "platform": "쿠팡", "date": "2026-04-04"},
    {"id": "rev-129", "text": "사과를 깎으면 갈변이 느려요. 신선한 증거!", "rating": 5, "platform": "네이버스마트스토어", "date": "2026-04-04"},
    {"id": "rev-130", "text": "맛은 좋은데 양이 좀 적어요.", "rating": 3, "platform": "쿠팡", "date": "2026-04-04"},
    {"id": "rev-131", "text": "오가닉 사과 찾기 힘든데 여기서 발견해서 기뻐요.", "rating": 5, "platform": "네이버스마트스토어", "date": "2026-04-05"},
    {"id": "rev-132", "text": "쿠팡 가격이 네이버보다 2천원 비싸요.", "rating": 3, "platform": "쿠팡", "date": "2026-04-05"},
    {"id": "rev-133", "text": "피부에 좋다고 해서 매일 하나씩 먹고 있어요.", "rating": 5, "platform": "네이버스마트스토어", "date": "2026-04-05"},
    {"id": "rev-134", "text": "시원하게 냉장해서 먹으면 정말 맛있어요.", "rating": 5, "platform": "쿠팡", "date": "2026-04-05"},
    {"id": "rev-135", "text": "스무디 재료로 최고입니다.", "rating": 5, "platform": "네이버스마트스토어", "date": "2026-04-06"},
    {"id": "rev-136", "text": "문의 답변이 빨라서 좋았어요.", "rating": 4, "platform": "쿠팡", "date": "2026-04-06"},
    {"id": "rev-137", "text": "사과 박스 위에 고양이가 올라갔어요. 튼튼하네요.", "rating": 4, "platform": "네이버스마트스토어", "date": "2026-04-06"},
    {"id": "rev-138", "text": "이건 솔직히 별로였어요. 재구매 안 할 듯.", "rating": 1, "platform": "쿠팡", "date": "2026-04-06"},
    {"id": "rev-139", "text": "10kg 주문했는데 실측 10.3kg이었어요. 양심적!", "rating": 5, "platform": "네이버스마트스토어", "date": "2026-04-07"},
    {"id": "rev-140", "text": "사과와 함께 온 편지가 따뜻했어요.", "rating": 5, "platform": "쿠팡", "date": "2026-04-07"},
    {"id": "rev-141", "text": "캠핑 갈 때 가져갔더니 분위기 최고!", "rating": 5, "platform": "네이버스마트스토어", "date": "2026-04-07"},
    {"id": "rev-142", "text": "수분감이 적고 퍽퍽해요.", "rating": 2, "platform": "쿠팡", "date": "2026-04-07"},
    {"id": "rev-143", "text": "해외 직구보다 국산 사과가 훨씬 맛있네요.", "rating": 5, "platform": "네이버스마트스토어", "date": "2026-04-08"},
    {"id": "rev-144", "text": "포장 테이프가 과하게 붙어있어 열기 힘들었어요.", "rating": 3, "platform": "쿠팡", "date": "2026-04-08"},
    {"id": "rev-145", "text": "임산부인데 사과가 입덧에 좋다고 해서 매일 먹어요.", "rating": 5, "platform": "네이버스마트스토어", "date": "2026-04-08"},
    {"id": "rev-146", "text": "재구매 5회째. 언제나 한결같은 맛!", "rating": 5, "platform": "쿠팡", "date": "2026-04-08"},
    {"id": "rev-147", "text": "사과즙 내려 먹었더니 온 가족이 좋아해요.", "rating": 5, "platform": "네이버스마트스토어", "date": "2026-04-09"},
    {"id": "rev-148", "text": "가격 인상 없이 유지해주세요!", "rating": 4, "platform": "쿠팡", "date": "2026-04-09"},
    {"id": "rev-149", "text": "선생님 선물로 드렸더니 좋아하셨어요.", "rating": 5, "platform": "네이버스마트스토어", "date": "2026-04-09"},
    {"id": "rev-150", "text": "총평: 가성비 좋고 맛있는 사과. 추천합니다!", "rating": 5, "platform": "쿠팡", "date": "2026-04-09"},
]


# ---------------------------------------------------------------------------
# POST /reviews/embed — 리뷰 임베딩 저장
# ---------------------------------------------------------------------------

@router.post("/embed", response_model=EmbedResponse)
async def embed_reviews(req: EmbedRequest, _user: User = Depends(get_current_user)):
    """리뷰 데이터를 ChromaDB에 임베딩 저장합니다.

    source="mock": Mock 데이터 동기화 (개발용)
    source="db": shop_reviews 테이블에서 가져오기 (추후)
    """
    if req.source == "mock":
        added = _rag.sync_from_mock(MOCK_REVIEWS)
        total = _rag.get_count()
        return EmbedResponse(embedded_count=added, total_count=total, source="mock")
    else:
        raise HTTPException(400, f"지원하지 않는 source: {req.source}. 현재 'mock'만 지원됩니다.")


@router.get("/embed/stream")
async def embed_reviews_stream(_user: User = Depends(get_current_user)):
    """SSE로 임베딩 진행률을 스트리밍합니다."""

    async def event_generator():
        existing = _rag.collection.get()
        existing_ids = set(existing["ids"]) if existing["ids"] else set()
        new_reviews = [r for r in MOCK_REVIEWS if str(r["id"]) not in existing_ids]

        if not new_reviews:
            yield {"data": json.dumps({"progress": 100, "embedded": 0, "total": len(MOCK_REVIEWS), "message": "이미 모든 리뷰가 임베딩되어 있습니다."})}
            return

        for update in _rag.embed_reviews_chunked(new_reviews, chunk_size=10):
            yield {"data": json.dumps(update, ensure_ascii=False)}
            await asyncio.sleep(0)  # 이벤트 루프 양보

    return EventSourceResponse(event_generator())


@router.get("/analyze/stream")
async def analyze_reviews_stream(
    batch_size: int = Query(20, ge=5, le=50),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """SSE로 분석 진행률을 스트리밍합니다."""

    async def event_generator():
        # 임베딩 없으면 자동 동기화
        if _rag.get_count() == 0:
            yield {"data": json.dumps({"progress": 0, "message": "리뷰 임베딩 중..."}, ensure_ascii=False)}
            _rag.sync_from_mock(MOCK_REVIEWS)

        reviews = _rag.get_all_reviews(limit=200)
        if not reviews:
            yield {"data": json.dumps({"progress": 100, "error": "분석할 리뷰가 없습니다."}, ensure_ascii=False)}
            return

        analysis_reviews = [
            {"id": r["id"], "text": r["text"], "rating": r["metadata"].get("rating", 0),
             "platform": r["metadata"].get("platform", ""), "date": r["metadata"].get("date", "")}
            for r in reviews
        ]

        final_result = None
        async for update in _analyzer.analyze_batch_with_progress(analysis_reviews, batch_size=batch_size):
            if "result" in update:
                final_result = update["result"]
            yield {"data": json.dumps(
                {k: v for k, v in update.items() if k != "result"},
                ensure_ascii=False,
            )}
            await asyncio.sleep(0)

        # DB 저장
        if final_result:
            summary_data = final_result.get("summary", {})
            trends = _trend_detector.calculate_weekly_trends([
                {**s, "date": next((r["date"] for r in analysis_reviews if str(r["id"]) == str(s.get("id"))), "")}
                for s in final_result.get("sentiments", [])
            ])
            anomalies = _trend_detector.detect_anomalies(trends)

            analysis_record = ReviewAnalysis(
                analysis_type="manual", target_scope="all",
                review_count=len(analysis_reviews),
                sentiment_summary=final_result.get("sentiment_summary"),
                keywords=final_result.get("keywords", []),
                summary=json.dumps(summary_data, ensure_ascii=False) if summary_data else None,
                trends=trends, anomalies=anomalies,
                llm_provider=final_result.get("llm_provider", ""),
                llm_model=final_result.get("llm_model", ""),
                processing_time_ms=final_result.get("processing_time_ms", 0),
            )
            db.add(analysis_record)
            await db.commit()

            yield {"data": json.dumps({"progress": 100, "message": "분석 완료! DB 저장됨."}, ensure_ascii=False)}

    return EventSourceResponse(event_generator())


# ---------------------------------------------------------------------------
# POST /reviews/analyze — 분석 실행
# ---------------------------------------------------------------------------

@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_reviews(req: AnalyzeRequest, db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user)):
    """리뷰 분석을 실행합니다 (수동).

    1. ChromaDB에서 리뷰 조회
    2. LLM으로 감성분석 + 키워드 + 요약
    3. 트렌드/이상 탐지
    4. DB에 결과 저장
    """
    # 임베딩된 리뷰가 없으면 자동 동기화
    if _rag.get_count() == 0:
        _rag.sync_from_mock(MOCK_REVIEWS)

    # 리뷰 조회
    reviews = _rag.get_all_reviews(limit=200)
    if not reviews:
        raise HTTPException(404, "분석할 리뷰가 없습니다. 먼저 /embed를 실행하세요.")

    # 분석용 데이터 준비
    analysis_reviews = [
        {
            "id": r["id"],
            "text": r["text"],
            "rating": r["metadata"].get("rating", 0),
            "platform": r["metadata"].get("platform", ""),
            "date": r["metadata"].get("date", ""),
        }
        for r in reviews
    ]

    # LLM 분석 실행
    result = await _analyzer.analyze_batch(analysis_reviews, batch_size=req.batch_size)

    # 트렌드/이상 탐지
    sentiments_with_date = [
        {**s, "date": next((r["date"] for r in analysis_reviews if str(r["id"]) == str(s.get("id"))), "")}
        for s in result.get("sentiments", [])
    ]
    trends = _trend_detector.calculate_weekly_trends(sentiments_with_date)
    anomalies = _trend_detector.detect_anomalies(trends)

    # DB 저장
    summary_data = result.get("summary", {})
    analysis_record = ReviewAnalysis(
        analysis_type="manual",
        target_scope=req.scope,
        review_count=len(analysis_reviews),
        sentiment_summary=result.get("sentiment_summary"),
        keywords=[kw if isinstance(kw, dict) else kw for kw in result.get("keywords", [])],
        summary=json.dumps(summary_data, ensure_ascii=False) if summary_data else None,
        trends=[t if isinstance(t, dict) else t for t in trends],
        anomalies=[a if isinstance(a, dict) else a for a in anomalies],
        llm_provider=result.get("llm_provider", ""),
        llm_model=result.get("llm_model", ""),
        processing_time_ms=result.get("processing_time_ms", 0),
    )
    db.add(analysis_record)
    await db.commit()
    await db.refresh(analysis_record)

    return AnalyzeResponse(
        analysis_id=analysis_record.id,
        status="completed",
        review_count=len(analysis_reviews),
        sentiment_summary=SentimentSummary(**result.get("sentiment_summary", {})),
        keywords=[KeywordItem(**kw) for kw in result.get("keywords", [])],
        summary=SummaryData(**summary_data) if isinstance(summary_data, dict) else SummaryData(),
        anomalies=[AnomalyAlert(**a) for a in anomalies],
        processing_time_ms=result.get("processing_time_ms", 0),
        llm_provider=result.get("llm_provider", ""),
        llm_model=result.get("llm_model", ""),
    )


# ---------------------------------------------------------------------------
# GET /reviews/analysis — 분석 결과 조회
# ---------------------------------------------------------------------------

@router.get("/analysis")
async def get_latest_analysis(db: AsyncSession = Depends(get_db), _user: User = Depends(get_current_user)):
    """최신 분석 결과를 조회합니다."""
    stmt = select(ReviewAnalysis).order_by(desc(ReviewAnalysis.created_at)).limit(1)
    result = await db.execute(stmt)
    record = result.scalar_one_or_none()

    if not record:
        raise HTTPException(404, "분석 결과가 없습니다. 먼저 /analyze를 실행하세요.")

    summary_data = {}
    if record.summary:
        try:
            summary_data = json.loads(record.summary) if isinstance(record.summary, str) else record.summary
        except (json.JSONDecodeError, TypeError):
            summary_data = {}

    return {
        "analysis_id": record.id,
        "analysis_type": record.analysis_type,
        "target_scope": record.target_scope,
        "review_count": record.review_count,
        "sentiment_summary": record.sentiment_summary or {},
        "keywords": record.keywords or [],
        "summary": summary_data,
        "trends": record.trends or [],
        "anomalies": record.anomalies or [],
        "processing_time_ms": record.processing_time_ms,
        "llm_provider": record.llm_provider,
        "llm_model": record.llm_model,
        "created_at": record.created_at.isoformat() if record.created_at else None,
    }


# ---------------------------------------------------------------------------
# POST /reviews/search — RAG 의미 검색
# ---------------------------------------------------------------------------

@router.post("/search", response_model=SearchResponse)
async def search_reviews(req: SearchRequest, _user: User = Depends(get_current_user)):
    """자연어 질의로 유사 리뷰를 검색합니다 (RAG)."""
    if _rag.get_count() == 0:
        _rag.sync_from_mock(MOCK_REVIEWS)

    filters = None
    if req.filters:
        filters = req.filters.model_dump(exclude_none=True)

    results = _rag.search(query=req.query, top_k=req.top_k, filters=filters)

    return SearchResponse(
        results=[SearchResult(**r) for r in results],
        total=len(results),
    )


# ---------------------------------------------------------------------------
# GET /reviews/trends — 트렌드 데이터
# ---------------------------------------------------------------------------

@router.get("/trends", response_model=TrendsResponse)
async def get_trends(
    period: str = Query("weekly", description="weekly 또는 monthly"),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """트렌드/이상 탐지 데이터를 반환합니다."""
    stmt = select(ReviewAnalysis).order_by(desc(ReviewAnalysis.created_at)).limit(1)
    result = await db.execute(stmt)
    record = result.scalar_one_or_none()

    if not record or not record.trends:
        # DB에 결과 없으면 Mock 데이터 기반으로 생성
        mock_trends = _trend_detector.generate_simple_trends([
            {"week": "1주차", "positive": 7, "negative": 2, "neutral": 1},
            {"week": "2주차", "positive": 9, "negative": 2, "neutral": 2},
            {"week": "3주차", "positive": 10, "negative": 2, "neutral": 2},
            {"week": "4주차", "positive": 9, "negative": 2, "neutral": 2},
        ])
        return TrendsResponse(
            trends=[TrendData(**t) for t in mock_trends],
            anomalies=[],
        )

    return TrendsResponse(
        trends=[TrendData(**t) for t in (record.trends or [])],
        anomalies=[AnomalyAlert(**a) for a in (record.anomalies or [])],
    )


# ---------------------------------------------------------------------------
# GET /reviews/report/pdf — PDF 리포트 다운로드
# ---------------------------------------------------------------------------

@router.get("/report/pdf")
async def download_report(
    analysis_id: int | None = Query(None, description="특정 분석 ID (미지정 시 최신)"),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """분석 결과를 PDF 리포트로 다운로드합니다."""
    if analysis_id:
        stmt = select(ReviewAnalysis).where(ReviewAnalysis.id == analysis_id)
    else:
        stmt = select(ReviewAnalysis).order_by(desc(ReviewAnalysis.created_at)).limit(1)
    result = await db.execute(stmt)
    record = result.scalar_one_or_none()

    if not record:
        raise HTTPException(404, "분석 결과가 없습니다. 먼저 /analyze를 실행하세요.")

    summary_data = {}
    if record.summary:
        try:
            summary_data = json.loads(record.summary) if isinstance(record.summary, str) else record.summary
        except (json.JSONDecodeError, TypeError):
            summary_data = {}

    analysis_data = {
        "sentiment_summary": record.sentiment_summary or {},
        "keywords": record.keywords or [],
        "summary": summary_data,
        "anomalies": record.anomalies or [],
        "processing_time_ms": record.processing_time_ms or 0,
        "llm_provider": record.llm_provider or "",
        "llm_model": record.llm_model or "",
    }

    pdf_bytes = _report_generator.generate_pdf(analysis_data)

    return StreamingResponse(
        pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=review-analysis-report.pdf"},
    )


# ---------------------------------------------------------------------------
# GET/PUT /reviews/settings — 자동 분석 설정
# ---------------------------------------------------------------------------

@router.get("/settings", response_model=AnalysisSettings)
async def get_settings(_user: User = Depends(get_current_user)):
    """자동 분석 설정을 조회합니다."""
    return _settings


@router.put("/settings", response_model=AnalysisSettings)
async def update_settings(req: AnalysisSettingsUpdate, _user: User = Depends(get_current_user)):
    """자동 분석 설정을 변경합니다."""
    global _settings

    update_data = req.model_dump(exclude_none=True)
    current = _settings.model_dump()
    current.update(update_data)
    _settings = AnalysisSettings(**current)

    return _settings
