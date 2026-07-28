"""전처리 데이터 청크 로더 모듈."""

import json
import os
from typing import List, Optional
from ai.app.retrieval.models.retrieved_chunk import RetrievedChunk


class ChunkLoader:
    """data/processed/ 청크 데이터 파일 읽기 로더"""

    def __init__(self, data_dir: Optional[str] = None):
        if data_dir is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            self.data_dir = os.path.join(base_dir, "data", "processed")
        else:
            self.data_dir = data_dir

    def load_sample_chunks(self) -> List[RetrievedChunk]:
        """MVP 정수기 매뉴얼 기본 sample 청크 데이터 제공 (테스트 및 로컬 전용)"""
        return [
            RetrievedChunk(
                chunk_id="chunk_wpu_104_leak_01",
                document_title="WPU-JAC104D/JCC104D 사용 설명서",
                document_version="1.0",
                page=12,
                manual_model="WPUJAC104DWH",
                product_generation="D",
                content="제품 밑이나 전원선 주변에서 물이 새는 경우 즉시 원수 밸브를 잠그고 전원 플러그를 뽑으십시오.",
                similarity_score=0.92,
                official_url="https://example.com/manual/wpu-104d/p12",
                verification_status="official_verified",
                allowed_use=True
            ),
            RetrievedChunk(
                chunk_id="chunk_wpu_104_flow_02",
                document_title="WPU-JAC104D/JCC104D 사용 설명서",
                document_version="1.0",
                page=18,
                manual_model="WPUJAC104DWH",
                product_generation="D",
                content="출수량이 적거나 물이 졸졸 나오는 경우 필터 교체 주기 및 원수 공급 밸브가 열려 있는지 확인하세요.",
                similarity_score=0.85,
                official_url="https://example.com/manual/wpu-104d/p18",
                verification_status="official_verified",
                allowed_use=True
            ),
            RetrievedChunk(
                chunk_id="chunk_wpu_104_temp_03",
                document_title="WPU-JAC104D/JCC104D 사용 설명서",
                document_version="1.0",
                page=24,
                manual_model="WPUJAC104DWH",
                product_generation="D",
                content="냉수가 미지근하거나 온수가 안 나오는 경우 제품 후면 통풍 간격을 10cm 이상 확보했는지 점검해 주세요.",
                similarity_score=0.78,
                official_url="https://example.com/manual/wpu-104d/p24",
                verification_status="official_verified",
                allowed_use=True
            ),
            # S 세대 제외 테스트용 청크
            RetrievedChunk(
                chunk_id="chunk_s_gen_01",
                document_title="이전 S세대 구형 정수기 설명서",
                document_version="0.9",
                page=5,
                manual_model="WPU-OLD100",
                product_generation="S",
                content="S세대 구형 정수기 조치법",
                similarity_score=0.95,
                verification_status="official_verified",
                allowed_use=True
            ),
            # 제거 대상 모델 제외 테스트용 청크
            RetrievedChunk(
                chunk_id="chunk_excluded_01",
                document_title="WPU-IAC506 매뉴얼",
                document_version="1.0",
                page=8,
                manual_model="WPU-IAC506",
                product_generation="D",
                content="제거 대상 모델 관련 조치 가이드",
                similarity_score=0.89,
                verification_status="official_verified",
                allowed_use=True
            )
        ]
