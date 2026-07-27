from __future__ import annotations

from typing import Any

import requests
from django.conf import settings

KAKAO_DIRECTIONS_URL = "https://apis-navi.kakaomobility.com/v1/directions"


class KakaoDirectionsError(Exception):
    """카카오 자동차 길찾기 API 처리 실패."""


def get_driving_route(
    *,
    origin_lat: float,
    origin_lng: float,
    destination_lat: float,
    destination_lng: float,
) -> dict[str, Any]:
    rest_api_key = settings.KAKAO_REST_API_KEY.strip()
    if not rest_api_key:
        raise KakaoDirectionsError(
            "서버 환경변수 KAKAO_REST_API_KEY가 설정되지 않았습니다."
        )

    try:
        response = requests.get(
            KAKAO_DIRECTIONS_URL,
            headers={
                "Authorization": f"KakaoAK {rest_api_key}",
                "Accept": "application/json",
            },
            params={
                "origin": f"{origin_lng},{origin_lat}",
                "destination": f"{destination_lng},{destination_lat}",
                "priority": "RECOMMEND",
                "summary": "false",
            },
            timeout=12,
        )
    except requests.RequestException as exc:
        raise KakaoDirectionsError(
            f"카카오 길찾기 API 연결 실패: {exc}"
        ) from exc

    if response.status_code != 200:
        raise KakaoDirectionsError(
            f"카카오 길찾기 API 오류({response.status_code}): "
            f"{response.text[:500]}"
        )

    payload = response.json()
    routes = payload.get("routes") or []
    if not routes:
        raise KakaoDirectionsError("사용 가능한 자동차 경로가 없습니다.")

    route = routes[0]
    if route.get("result_code") != 0:
        raise KakaoDirectionsError(
            route.get("result_msg") or "자동차 경로 탐색에 실패했습니다."
        )

    points: list[dict[str, float]] = []
    for section in route.get("sections") or []:
        for road in section.get("roads") or []:
            vertexes = road.get("vertexes") or []
            for index in range(0, len(vertexes) - 1, 2):
                point = {
                    "lat": float(vertexes[index + 1]),
                    "lng": float(vertexes[index]),
                }
                if not points or points[-1] != point:
                    points.append(point)

    if len(points) < 2:
        raise KakaoDirectionsError("도로 경로 좌표가 부족합니다.")

    summary = route.get("summary") or {}
    return {
        "route_type": "DRIVING",
        "distance_meters": int(summary.get("distance") or 0),
        "duration_seconds": int(summary.get("duration") or 0),
        "points": points,
    }
