# WaterCare customer app

Week 3 mandatory customer flow:

- actual Backend health and Demo customer authentication
- CUST-01 product/subscription summary with synthetic marker
- CUST-02 symptom selection and validated intake state
- CUST-04 safe guidance and official evidence presentation
- deterministic normal, caution, danger, no-evidence, AI-failure and network-failure fixtures

The app defaults to `http://127.0.0.1:8000/` for a physical device using `adb reverse`. Override `BACKEND_BASE_URL` in untracked `mobile/local.properties` for an emulator.
