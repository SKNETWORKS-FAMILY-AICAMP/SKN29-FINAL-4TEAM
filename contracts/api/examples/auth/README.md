# auth examples

구현된 Auth 4개 Endpoint의 요청·정상 응답 예시를 저장한다.
토큰 문자열은 실제 인증에 사용할 수 없는 Placeholder다.

- Demo Login: `demo-login-request.json` → `demo-login-success-response.json`
- Refresh: `refresh-request.json` → `refresh-success-response.json`
- Logout: `logout-request.json` → `logout-success-response.json`
- Me: `me-success-response.json`

`Authorization: Bearer <access_token>`은 `/me` 호출 Header이며 JSON 본문에
넣지 않는다. Refresh Token 재사용은 성공 Replay가 아니라
`401 AUTH_REQUIRED`다.
