# Backend API to mobile mapping

| Backend route | Customer app | Technician app | Implementation |
|---|---|---|---|
| `GET /health` | connection badge | connection badge | actual |
| `POST /api/v1/auth/demo-login` | Demo customer | Demo technician | actual |
| `POST /api/v1/auth/refresh` | automatic once after 401 | automatic once after 401 | actual core authenticator |
| `POST /api/v1/auth/logout` | logout | logout | actual |
| `GET /api/v1/me` | authenticated user projection | role projection | actual |
| `POST /api/v1/inquiries` | remote repository replacement point | not used | actual contract/client |
| `POST /api/v1/inquiries/{id}/cancel` | remote repository replacement point | not used | actual contract/client |
| product/subscription read | CUST-01 synthetic fixture | pending | Backend route absent |
| questionnaire/guidance | CUST-02/04 deterministic Fake | report pending | Backend route absent |
| consultation/visit/location | button/pending state only | pending cards | Backend route absent |

Unsupported password login, registration and customer-profile routes were removed from the Retrofit interface because they are not present in `backend/config/api_urls.py`.

The UI depends on repository interfaces. When a contract and Backend route are merged, add a Remote implementation and replace the repository assignment without rewriting screens or ViewModels.
