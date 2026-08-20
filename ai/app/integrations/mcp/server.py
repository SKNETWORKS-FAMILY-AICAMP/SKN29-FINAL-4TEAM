# MCP 서버를 만들기 위해 MCPServer 클래스를 가져옵니다.
# 쉽게 말하면 "AI가 사용할 수 있는 도구 상자"를 만드는 기능입니다.
from mcp.server import MCPServer

# UUID 형식의 inquiry_id를 사용하기 위해 가져옵니다.
from uuid import UUID

# Backend Context 연동 설정이 아직 없는 경우 사용하는 전용 오류입니다.
from .errors import (
    MCPContextConfigurationError,
)

# 문의 Context 조회 MCP Tool에 필요한 부품들을 가져옵니다.
from .tools.get_inquiry_context import (
    # Backend에서 받아온 문의 전체 정보를 담는 형태
    BackendInquiryContext,

    # Backend 문의 정보를 MCP 출력 형태로 바꿔주는 Adapter
    GetInquiryContextAdapter,

    # MCP Tool이 받을 입력 형태
    GetInquiryContextInput,

    # MCP Tool이 반환할 출력 형태
    GetInquiryContextOutput,

    # 문의 정보를 읽는 객체가 따라야 하는 규칙
    InquiryContextReader,
)

# lookup_product_context.py에서
# 제품 정보를 조회할 때 필요한 부품들을 가져옵니다.
from .tools.lookup_product_context import (
    BackendProductContext, # Backend에서 받아온 제품 정보를 담는 데이터 형태
    LookupProductContextAdapter, # Backend 제품 정보를 MCP가 사용할 형태로 바꿔주는 변환기
    LookupProductContextInput, # lookup_product_context Tool이 받을 입력 형식
    LookupProductContextOutput, # lookup_product_context Tool이 반환할 출력 형식
    ProductContextReader,  # "제품 정보를 조회하는 객체는 이런 기능을 가져야 한다"라는 규칙
)

# search_official_evidence.py에서
# 공식 문서 검색에 필요한 부품들을 가져옵니다.
from .tools.search_official_evidence import (
    SearchOfficialEvidenceAdapter, # MCP 요청을 기존 검색 시스템에 연결해주는 변환기
    SearchOfficialEvidenceInput, # 공식 근거 검색 Tool의 입력 형식
    SearchOfficialEvidenceOutput, # 공식 근거 검색 Tool의 출력 형식
)
from ...orchestration.pipeline_router import PipelineRouter # 이미 AI Runtime에서 사용 중인 검색 서비스가 있는지 확인하기 위해 가져옵니다.
from ...retrieval import RetrievalConfigurationError # 검색 환경이 없거나 잘못 설정되었을 때 발생시키는 전용 오류입니다.
from ...retrieval.search.vector_search import VectorSearchService # 실제 Vector DB 검색을 담당하는 기존 검색 서비스입니다.


# 1. Vector Store가 준비되지 않았을 때 사용하는 안전장치
class _UnconfiguredEmbeddingProvider:
    """
    Vector Store 환경이 없는 경우 사용하는 MCP용 Fail-closed Provider.

    정책 Gate에서 차단되는 요청은 실제 Embedding까지 도달하지 않는다.
    검색이 허용된 요청이 Embedding 단계까지 오면 설정 오류를 명시적으로 발생시킨다.
    """
    # 이 클래스는 실제 Embedding을 수행하는 클래스가 아닙니다.
    #
    # 실제 Embedding 환경이 없는 상황에서
    # AI가 임의로 검색을 진행하지 못하도록 막는 안전장치입니다.
    #
    # 즉:
    #
    # Embedding 환경 있음
    # → 실제 Embedding 사용
    #
    # Embedding 환경 없음
    # → 가짜 값 생성 X
    # → 오류 발생
    #
    # 이런 방식을 Fail-closed라고 합니다.

    # 현재 프로젝트에서 사용하는 Embedding Vector 크기입니다.

    dimension = 1024

    def embed_query(self, text: str) -> list[float]:
        # 고객 질문 하나를 Vector로 바꾸려고 했는데
        # Embedding 환경이 없다면 검색을 진행하지 않고 오류를 발생시킵니다.
        raise RetrievalConfigurationError(
            "Vector Store가 설정되지 않아 공식 근거 검색을 실행할 수 없습니다."
        )

    def embed_documents(
        self,
        texts,
    ) -> list[list[float]]:
        # 여러 문서를 Vector로 바꾸려고 했는데
        # Embedding 환경이 없다면 역시 오류를 발생시킵니다.
        raise RetrievalConfigurationError(
            "Vector Store가 설정되지 않아 공식 근거 검색을 실행할 수 없습니다."
        )

# 2. 실제 Vector DB가 연결되지 않았을 때 사용하는 안전장치
class _UnconfiguredVectorStore:
    """
    실제 Vector Store가 구성되지 않은 환경에서 DB 접근을 차단한다.
    """
    # Vector DB가 없는 상태에서
    # 검색 결과를 임의로 만들어내지 못하게 막는 클래스입니다.
    #
    # 실제 DB 없음
    # → "아마 이런 결과일 것이다"라고 반환하지 않음
    # → 명확하게 오류 발생

    def search(
        self,
        vector,
        *,
        model_code: str,
        product_generation: str,
        top_k: int,
    ):
        raise RetrievalConfigurationError(
            "Vector Store가 설정되지 않아 공식 근거 검색을 실행할 수 없습니다."
        )

# 3. Backend 제품 정보 API가 아직 연결되지 않았을 때 사용하는 안전장치
class _UnconfiguredProductContextReader:
    """
    Backend Product Context API가 아직 연결되지 않은 경우
    제품 정보를 임의로 생성하지 않고 명시적으로 실패한다.
    """
    # 앞으로는 Backend 내부 API를 통해
    # 실제 제품 정보를 가져오게 됩니다.
    #
    # 하지만 현재 Backend Product Context API가 아직 연결되지 않았으므로
    # 가짜 제품 정보를 만들어 반환하지 않고 오류를 발생시킵니다.
    #
    # 예:
    #
    # 잘못된 방식
    # Backend 연결 안 됨
    # → "그냥 JAC104라고 하자" X
    #
    # 현재 방식
    # Backend 연결 안 됨
    # → 오류 발생 O

    def get_product_context(
        self,
        model_code: str,
    ) -> BackendProductContext:
        raise MCPContextConfigurationError(
            "Backend Product Context API가 아직 설정되지 않았습니다."
        )

class _UnconfiguredInquiryContextReader:
    # 앞으로 Backend 내부 Context API가 완성되면
    # 실제 문의 정보를 Backend에서 가져오게 됩니다.
    #
    # 현재는 API가 아직 연결되지 않았기 때문에
    # 가짜 문의 데이터를 만들어 반환하지 않습니다.
    #
    # 즉:
    #
    # Backend 연결 안 됨
    # → 임의의 문의 정보 생성 X
    # → 명확한 오류 발생
    #
    # 이것도 Fail-closed 방식입니다.

    def get_inquiry_context(
        self,
        inquiry_id: UUID,
    ) -> BackendInquiryContext:
        raise RuntimeError(
            "Backend Inquiry Context API가 아직 설정되지 않았습니다."
        )

# 4. 공식 근거 검색에 사용할 검색 서비스를 결정하는 함수
def _resolve_search_service() -> VectorSearchService:
    """
    실제 Runtime 검색 서비스가 구성되어 있으면 재사용하고,
    없으면 Policy Gate만 실행 가능한 Fail-closed Service를 만든다.
    """
    # 쉽게 말하면:
    #
    # "지금 사용할 수 있는 실제 검색 서비스가 있나?"
    #
    # 를 확인하는 함수입니다.

    # PipelineRouter에 이미 설정되어 있는
    # VectorSearchService가 있는지 확인합니다

    search_service = PipelineRouter._configured_search_service()


    # 실제 검색 서비스가 준비되어 있다면
    # 새로 만들지 않고 기존 검색 서비스를 그대로 사용합니다.
    if search_service is not None:
        return search_service

    # 실제 검색 환경이 없다면
    # 가짜 검색 결과를 반환하는 것이 아니라
    # 오류를 발생시키는 Fail-closed 검색 서비스를 만듭니다.
    return VectorSearchService( # 임시 가짜 제품을 반환하지 않습니다.
        _UnconfiguredEmbeddingProvider(),
        _UnconfiguredVectorStore(),
    )

# 5. 제품 정보를 어디에서 가져올지 결정하는 함수
def _resolve_product_context_reader() -> ProductContextReader:
    """
    Product Context 조회 구현체를 반환한다.

    Backend API 계약이 확정되면
    이 함수에서 실제 BackendContextClient를 반환하도록 교체한다.
    """
    # 쉽게 말하면:
    #
    # "제품 정보는 누구한테 물어볼 것인가?"
    #
    # 를 정하는 함수입니다.
    #
    # 현재:
    # MCP
    # → _UnconfiguredProductContextReader
    # → Backend API 미연결 오류
    #
    # 나중:
    # MCP
    # → BackendContextClient
    # → 실제 Django Backend 내부 API
    #
    # 로 바뀔 예정입니다.

    return _UnconfiguredProductContextReader()

# 6. WaterBridge MCP Server 생성
# "WaterBridge MCP"라는 이름의 MCP 서버를 만듭니다.
# 비유하면 지금부터 AI가 사용할
# "도구 상자" 하나를 만드는 것입니다.

mcp = MCPServer("WaterBridge MCP")

# 7. 서버 상태 확인 Tool
@mcp.tool()
# @mcp.tool()은
# "이 Python 함수를 MCP Tool로 등록해라"라는 뜻입니다.
# 따라서 AI는 MCP Client를 통해
# health_check라는 이름으로 이 기능을 찾을 수 있습니다.
def health_check() -> dict[str, str]:
    # 서버가 정상적으로 실행되고 있는지만 확인합니다.
    #
    # 쉽게 말하면:
    #
    # Client: "MCP 서버 살아 있어?"
    # Server: "응, 정상 작동 중이야."
    return {
        "status": "ok",
        "service": "waterbridge-mcp",
    }

def _resolve_inquiry_context_reader() -> InquiryContextReader:
    # 쉽게 말하면:
    #
    # "문의 정보는 어디에서 가져올 것인가?"
    #
    # 를 결정하는 함수입니다.
    #
    # 현재:
    # MCP
    # → _UnconfiguredInquiryContextReader
    # → Backend 미연결 오류
    #
    # 나중:
    # MCP
    # → BackendContextClient
    # → Django Backend 내부 API
    #
    # 로 교체할 예정입니다.

    return _UnconfiguredInquiryContextReader()

# 8. 공식 근거 검색 Tool
@mcp.tool()
def search_official_evidence(
    # 고객이 입력한 실제 질문
    customer_query: str,
    # 고객이 사용 중인 정확한 제품 판매 코드
    model_code: str,
    # 구조화된 증상 종류
    # 값이 없을 수도 있기 때문에 | None을 사용합니다.
    symptom_type: str | None = None,
    # 이전 문진에서 고객이 답한 내용
    # 역시 아직 답변이 없을 수도 있습니다.
    previous_answers: list[dict[str, str]] | None = None,
) -> SearchOfficialEvidenceOutput:
    # 이 Tool의 목적:
    #
    # 고객 질문에 답하기 위해 사용할 수 있는
    # "공식 문서 근거"를 찾는 것입니다.
    #
    # 중요한 점:
    # MCP가 Vector DB를 직접 검색하지 않습니다.
    #
    # MCP
    # → SearchOfficialEvidenceAdapter
    # → VectorSearchService
    # → 기존 검색 시스템
    #
    # 구조로 동작합니다.

    # 현재 사용할 수 있는 검색 서비스를 가져옵니다.
    search_service = _resolve_search_service()

    # Adapter를 생성합니다.
    #
    # Adapter는 쉽게 말하면 "번역기"입니다.
    #
    # MCP가 받은 데이터를
    # 기존 검색 서비스가 이해할 수 있는 형태로 변환해줍니다.
    adapter = SearchOfficialEvidenceAdapter(
        search_service
    )
    # 사용자가 전달한 여러 값을
    # 정해진 SearchOfficialEvidenceInput 형태로 묶습니다.
    request = SearchOfficialEvidenceInput(
        customer_query=customer_query,
        model_code=model_code,
        symptom_type=symptom_type,
        # previous_answers가 None이면
            # 빈 리스트 []로 바꿔서 전달합니다.
        previous_answers=previous_answers or [],
    )

    # Adapter에게 실제 검색 작업을 실행하도록 요청합니다.
    #
    # 실행 과정 예:
    #
    # 고객 질문
    # → 정책 검사
    # → 모델 검사
    # → Vector 검색
    # → 공식 문서 검증
    # → Evidence 반환

    return adapter.execute(request)

# 9. 제품 정보 조회 Tool
@mcp.tool()
def lookup_product_context(
    model_code: str,   # 고객이 사용 중인 정확한 제품 판매 코드
) -> LookupProductContextOutput:
    # 이 Tool의 역할은:
    # "이 모델 번호가 어떤 제품인지 알려줘"
    # 입니다.
    # 예:
    # 입력
    # WPUJAC104DWH
    # ↓
    # 제품군
    # DIRECT_WATER_PURIFIER
    # 지원 기능
    # cold_water, hot_water 등
    # AI Runtime 사용 가능 여부
    # True / False
    # 같은 제품 Context를 반환하는 역할입니다.

    # 제품 정보를 어디에서 가져올지 결정합니다.
    #
    # 현재는 Backend API가 연결되지 않았기 때문에
    # _UnconfiguredProductContextReader가 반환됩니다.
    context_reader = _resolve_product_context_reader()

    # Adapter를 생성합니다.
    #
    # Adapter는 Backend에서 받은 제품 정보를
    # MCP가 사용할 수 있는 형태로 변환하는 역할을 합니다.
    adapter = LookupProductContextAdapter(
        context_reader
    )

    # 사용자가 입력한 model_code를
    # 정식 MCP Input 객체로 묶습니다.
    request = LookupProductContextInput(
        model_code=model_code,
    )
    # 실제 제품 정보 조회를 실행합니다.
    #
    # 현재 Backend가 연결되지 않았기 때문에
    # 실제 호출 시에는
    #
    # "Backend Product Context API가 아직 설정되지 않았습니다."
    #
    # 오류가 발생하는 것이 정상입니다.
    #
    # 나중에 BackendContextClient가 연결되면
    # 실제 제품 정보가 반환됩니다.

    return adapter.execute(request)


@mcp.tool()
def get_inquiry_context(
    inquiry_id: str,
) -> GetInquiryContextOutput:
    # 이 Tool의 역할:
    #
    # inquiry_id 하나를 받아서
    # 해당 고객 문의를 처리하는 데 필요한 Context를 조회합니다.
    #
    # 예:
    #
    # inquiry_id
    # ↓
    # 문의 추적 ID
    # 제품 정보
    # 고객 증상
    # 이전 문진 답변
    # AI Runtime 허용 여부
    #
    # 등을 하나로 묶어서 반환합니다.


    # 문의 정보를 실제로 어디에서 가져올지 결정합니다.
    #
    # 현재는 Backend 내부 API가 아직 연결되지 않았기 때문에
    # _UnconfiguredInquiryContextReader가 사용됩니다.
    context_reader = _resolve_inquiry_context_reader()


    # Adapter를 만듭니다.
    #
    # Adapter 역할:
    #
    # Backend 문의 데이터
    # ↓
    # GetInquiryContextAdapter
    # ↓
    # MCP가 사용할 데이터
    adapter = GetInquiryContextAdapter(
        context_reader
    )


    # MCP로 받은 문자열 inquiry_id를
    # 정식 입력 객체로 변환합니다.
    #
    # UUID 형식이 잘못되어 있다면
    # Pydantic이 여기에서 오류를 잡아줍니다.
    request = GetInquiryContextInput(
        inquiry_id=inquiry_id,
    )


    # 실제 문의 Context 조회를 실행합니다.
    #
    # 현재 Backend가 연결되지 않은 상태이므로
    # 실제 Tool 호출 시에는
    #
    # "Backend Inquiry Context API가 아직 설정되지 않았습니다."
    #
    # 오류가 발생하는 것이 정상입니다.
    return adapter.execute(request)



# 10. 이 파일을 직접 실행했을 때 MCP Server 시작
if __name__ == "__main__":
    mcp.run()