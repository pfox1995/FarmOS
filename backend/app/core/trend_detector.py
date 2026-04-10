"""트렌드/이상 탐지 서비스 (통계 기반, LLM 불필요).

# Design Ref: §3.4 — 트렌드/이상 탐지
# Plan SC: SC-05 (트렌드 차트와 이상 탐지 알림이 대시보드에 표시)

학습 포인트:
    이동평균 (Moving Average):
        최근 N기간의 값을 평균내어 추세를 파악하는 방법입니다.
        예: 최근 4주간 부정 리뷰 비율 = [15%, 12%, 14%, 13%]
        이동평균 = 13.5%
        → 이번주에 갑자기 30%가 되면 이상(anomaly)으로 판정

    표준편차 (Standard Deviation):
        데이터가 평균에서 얼마나 퍼져있는지를 나타내는 수치입니다.
        표준편차가 작으면 = 데이터가 평균 근처에 모여있음
        표준편차가 크면 = 데이터가 넓게 퍼져있음

    이상 탐지 (Anomaly Detection):
        "이동평균 ± N × 표준편차" 범위를 벗어나면 이상으로 판정합니다.
        N=2이면 약 95%의 정상 데이터가 이 범위 안에 들어옵니다.
        → 범위를 벗어난 5%가 잠재적 이상 데이터

    이 모듈은 LLM을 호출하지 않으므로 비용이 0원입니다.

사용 예시:
    from app.core.trend_detector import TrendDetector

    detector = TrendDetector()

    # 주간 트렌드 계산
    trends = detector.calculate_weekly_trends(analyses)

    # 이상 탐지
    anomalies = detector.detect_anomalies(trends)
"""

import logging
from collections import defaultdict
from datetime import datetime, timedelta
from statistics import mean, stdev

logger = logging.getLogger(__name__)


class TrendDetector:
    """감성 추이 및 이상 패턴 탐지기.

    학습 포인트:
        anomaly_threshold는 표준편차의 배수입니다.
        기본값 2.0은 "평균에서 표준편차 2배 이상 벗어나면 이상"을 의미합니다.
        값을 낮추면 더 민감하게, 높이면 덜 민감하게 탐지합니다.
    """

    def __init__(self, anomaly_threshold: float = 2.0):
        self.anomaly_threshold = anomaly_threshold

    # ------------------------------------------------------------------
    # 주간 트렌드 계산
    # ------------------------------------------------------------------

    def calculate_weekly_trends(self, sentiments: list[dict]) -> list[dict]:
        """개별 감성 결과를 주간 트렌드로 집계합니다.

        학습 포인트:
            날짜별 감성 결과를 ISO 주차(isocalendar)로 그룹핑합니다.
            각 주차의 긍정/부정/중립 비율을 계산합니다.

        Args:
            sentiments: 개별 감성 분석 결과
                [{ id, sentiment, date }]
                date가 없으면 해당 항목은 건너뜁니다.

        Returns:
            주간 트렌드 리스트 (날짜 오름차순)
            [{ week, positive_ratio, negative_ratio, neutral_ratio, total,
               positive, negative, neutral }]
        """
        if not sentiments:
            return []

        # 주차별 그룹핑
        weekly: dict[str, dict] = defaultdict(
            lambda: {"positive": 0, "negative": 0, "neutral": 0, "total": 0}
        )

        for s in sentiments:
            date_str = s.get("date", "")
            if not date_str:
                continue

            try:
                dt = datetime.strptime(date_str, "%Y-%m-%d")
                iso = dt.isocalendar()
                week_key = f"{iso[0]}-W{iso[1]:02d}"
            except (ValueError, TypeError):
                continue

            sentiment = s.get("sentiment", "neutral").lower()
            if sentiment not in ("positive", "negative", "neutral"):
                sentiment = "neutral"

            weekly[week_key][sentiment] += 1
            weekly[week_key]["total"] += 1

        # 정렬 후 비율 계산
        trends = []
        for week_key in sorted(weekly.keys()):
            w = weekly[week_key]
            total = w["total"]
            if total == 0:
                continue

            trends.append({
                "week": week_key,
                "positive": w["positive"],
                "negative": w["negative"],
                "neutral": w["neutral"],
                "total": total,
                "positive_ratio": round(w["positive"] / total, 3),
                "negative_ratio": round(w["negative"] / total, 3),
                "neutral_ratio": round(w["neutral"] / total, 3),
            })

        return trends

    # ------------------------------------------------------------------
    # 이상 탐지: 부정 리뷰 급증
    # ------------------------------------------------------------------

    def detect_anomalies(self, weekly_trends: list[dict]) -> list[dict]:
        """부정 리뷰 비율의 이상 급증을 탐지합니다.

        학습 포인트:
            이동평균(Moving Average) 기반 이상 탐지:

            1. 현재 주 이전 4주의 부정 비율을 가져옵니다 (윈도우)
            2. 윈도우의 평균(mean)과 표준편차(stdev)를 계산합니다
            3. 현재 값이 "평균 + threshold × 표준편차"를 초과하면 이상입니다

            예시:
                이전 4주 부정 비율: [0.15, 0.12, 0.14, 0.13]
                평균 = 0.135, 표준편차 = 0.013
                임계값 = 0.135 + 2.0 × 0.013 = 0.161
                이번주 0.35 → 0.161 초과 → 이상 탐지!

        Args:
            weekly_trends: calculate_weekly_trends()의 결과

        Returns:
            이상 탐지 리스트
            [{ week, type, value, expected, deviation, message }]
        """
        if len(weekly_trends) < 3:
            return []

        anomalies = []
        negative_ratios = [w["negative_ratio"] for w in weekly_trends]

        for i in range(2, len(negative_ratios)):
            # 최근 4주 윈도우 (현재 제외)
            window_start = max(0, i - 4)
            window = negative_ratios[window_start:i]

            if len(window) < 2:
                continue

            avg = mean(window)
            std = stdev(window)
            current = negative_ratios[i]

            # 표준편차가 0이면 (모든 값이 동일) 비율 변화 자체로 판단
            if std == 0:
                if current > avg * 1.5 and current - avg > 0.1:
                    anomalies.append({
                        "week": weekly_trends[i]["week"],
                        "type": "negative_spike",
                        "value": round(current, 3),
                        "expected": round(avg, 3),
                        "deviation": 0,
                        "message": (
                            f"부정 리뷰 비율 급증: {current:.0%} "
                            f"(평소 {avg:.0%})"
                        ),
                    })
                continue

            z_score = (current - avg) / std
            if z_score > self.anomaly_threshold:
                anomalies.append({
                    "week": weekly_trends[i]["week"],
                    "type": "negative_spike",
                    "value": round(current, 3),
                    "expected": round(avg, 3),
                    "deviation": round(z_score, 2),
                    "message": (
                        f"부정 리뷰 비율 급증: {current:.0%} "
                        f"(평소 {avg:.0%}, {z_score:.1f}σ 편차)"
                    ),
                })

        return anomalies

    # ------------------------------------------------------------------
    # 이상 탐지: 키워드 급등
    # ------------------------------------------------------------------

    def detect_keyword_surge(
        self,
        current_keywords: list[dict],
        previous_keywords: list[dict],
        threshold: float = 2.0,
    ) -> list[dict]:
        """특정 키워드의 급등을 탐지합니다.

        학습 포인트:
            이전 분석 대비 키워드 출현 빈도가 threshold배 이상 증가하면 급등입니다.
            예: "멍" 키워드가 이전 3회 → 이번 9회 (3.0배) → 급등!
            이는 상품 품질 이슈의 초기 신호일 수 있습니다.

        Args:
            current_keywords: 현재 분석의 키워드 [{ word, count, sentiment }]
            previous_keywords: 이전 분석의 키워드 [{ word, count, sentiment }]
            threshold: 급등 판정 배수 (기본 2.0 = 2배 이상 증가)

        Returns:
            급등 키워드 리스트
            [{ keyword, current_count, previous_count, growth_rate, sentiment }]
        """
        prev_map = {kw["word"]: kw["count"] for kw in previous_keywords}
        surges = []

        for kw in current_keywords:
            word = kw.get("word", "")
            current_count = kw.get("count", 0)
            prev_count = prev_map.get(word, 0)

            if prev_count > 0 and current_count / prev_count >= threshold:
                surges.append({
                    "keyword": word,
                    "current_count": current_count,
                    "previous_count": prev_count,
                    "growth_rate": round(current_count / prev_count, 1),
                    "sentiment": kw.get("sentiment", "neutral"),
                    "message": (
                        f"'{word}' 키워드 급등: "
                        f"{prev_count}회 → {current_count}회 "
                        f"({current_count / prev_count:.1f}배)"
                    ),
                })

        return sorted(surges, key=lambda x: x["growth_rate"], reverse=True)

    # ------------------------------------------------------------------
    # 간편 트렌드 생성 (Mock 데이터 호환)
    # ------------------------------------------------------------------

    def generate_simple_trends(
        self,
        sentiment_summary_history: list[dict],
    ) -> list[dict]:
        """주차별 감성 통계로부터 간편 트렌드를 생성합니다.

        Args:
            sentiment_summary_history: 주차별 감성 통계
                [{ week, positive, negative, neutral }]

        Returns:
            비율이 추가된 트렌드 리스트
        """
        trends = []
        for entry in sentiment_summary_history:
            total = entry.get("positive", 0) + entry.get("negative", 0) + entry.get("neutral", 0)
            if total == 0:
                continue
            trends.append({
                "week": entry["week"],
                "positive": entry["positive"],
                "negative": entry["negative"],
                "neutral": entry["neutral"],
                "total": total,
                "positive_ratio": round(entry["positive"] / total, 3),
                "negative_ratio": round(entry["negative"] / total, 3),
                "neutral_ratio": round(entry["neutral"] / total, 3),
            })
        return trends
