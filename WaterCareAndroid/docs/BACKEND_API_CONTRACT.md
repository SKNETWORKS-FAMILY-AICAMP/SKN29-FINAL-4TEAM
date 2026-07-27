# 백엔드 API 계약 초안

## 문의

```http
POST /api/v1/inquiries
POST /api/v1/inquiries/{inquiryId}/symptom
POST /api/v1/inquiries/{inquiryId}/images
POST /api/v1/inquiries/{inquiryId}/analyze
GET  /api/v1/inquiries/{inquiryId}
POST /api/v1/inquiries/{inquiryId}/events
```

## 방문

```http
GET  /api/v1/technicians/me/visits
GET  /api/v1/visits/{visitId}
POST /api/v1/visits/{visitId}/events
POST /api/v1/visits/{visitId}/locations
GET  /api/v1/visits/{visitId}/tracking
POST /api/v1/visits/{visitId}/results
```

## 위치 전송 예시

```json
{
  "visit_request_id": "VISIT-20260723-001",
  "tracking_status": "EN_ROUTE",
  "latitude": 37.5661,
  "longitude": 126.9827,
  "accuracy_meters": 12.4,
  "speed_mps": 8.2,
  "heading": 135.0,
  "recorded_at": "2026-07-23T15:14:05+09:00"
}
```

## AI 이미지 분석 응답 예시

```json
{
  "detected_text": "순간온수 모듈 점검",
  "visible_symptoms": ["warning_display"],
  "suspected_symptom": "hot_water_module_warning",
  "confidence": 0.91,
  "risk_level": "DANGER",
  "requires_consultation": true,
  "usage_guidance_status": "TOTAL_STOP",
  "additional_questions": [
    "현재 온수 출수를 중지했나요?",
    "동일한 경고 문구가 계속 표시되나요?"
  ]
}
```
