from ai.app.orchestration.harness import ProductContext, ProductFamily, ProductMatchVerifier
from ai.app.retrieval.models.retrieved_chunk import RetrievedChunk


def _chunk(chunk_id: str, model_code: str) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        document_title="official manual",
        manual_model=model_code,
        model_code=model_code,
        content="official evidence",
        similarity_score=0.9,
    )


def test_iac425_rejects_iac606_evidence():
    result = ProductMatchVerifier().verify(
        product=ProductContext(
            model_code="WPU-IAC425",
            product_family=ProductFamily.ICE_WATER_PURIFIER,
            supported_functions={"cold_water", "hot_water", "ice", "ice_water"},
        ),
        evidence_chunks=[_chunk("iac606", "WPU-IAC606")],
    )

    assert result.model_match_valid is False
    assert result.accepted_chunk_ids == []
    assert result.rejected_chunk_ids == ["iac606"]


def test_jac104_rejects_ice_function_request():
    result = ProductMatchVerifier().verify(
        product=ProductContext(
            model_code="WPU-JAC104",
            product_family=ProductFamily.DIRECT_WATER_PURIFIER,
            supported_functions={"cold_water", "hot_water", "ambient_water"},
        ),
        evidence_chunks=[_chunk("jac104", "WPU-JAC104")],
        required_functions={"ice"},
    )

    assert result.function_compatibility_valid is False
    assert any(issue.code.value == "UNSUPPORTED_FUNCTION" for issue in result.issues)


def test_jcc104_rejects_hot_water_function_request():
    result = ProductMatchVerifier().verify(
        product=ProductContext(
            model_code="WPU-JCC104",
            product_family=ProductFamily.DIRECT_WATER_PURIFIER,
            supported_functions={"cold_water", "ambient_water"},
        ),
        evidence_chunks=[_chunk("jcc104", "WPU-JCC104")],
        required_functions={"hot_water"},
    )

    assert result.function_compatibility_valid is False
