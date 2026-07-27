# Raw Data

공식 원본을 외부 백업에서 검증할 때만 입력 위치로 사용하는 비보관 영역입니다.

## 임시 입력 경로

- `manuals/mvp/skmagic_wpu_jac104d_jcc104d_rev00.pdf`
- `manuals/expansion/skmagic_wpu_iac425_rev02.pdf`

공식 PDF 원본과 FAQ 스냅샷은 재배포 권한이 확인되지 않았으므로 Git에 커밋하지
않습니다. 검증 후 삭제하며 현재는 `.gitkeep`만 배치했습니다. WPU-IAC425는
무결성·표지 검증만 완료했고 processed·RAG 데이터는 후속 생성 예정입니다.


## 최종 상태

6단계 승인 후 공식 원본은 저장소에 보관하지 않습니다. 현재 이 디렉터리에는
정책 파일과 빈 디렉터리 유지용 파일만 있습니다. 공식 URL·크기·SHA-256은
`processed/metadata/source_inventory.csv`에서 확인합니다.
