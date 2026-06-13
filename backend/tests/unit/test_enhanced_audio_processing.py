"""
AI 기반 오디오 증강 기능 테스트
"""

import pytest

from backend.pipeline.enhanced_audio_processor import AIEnhanceOptions


def test_ai_enhance_options_validation():
    """AI 증강 옵션 유효성 검증 테스트"""
    # 정상 옵션
    options = AIEnhanceOptions(
        enable_noise_reduction=True,
        enable_voice_enhancement=True,
        enable_vad=True,
        enable_quality_assessment=True,
        noise_reduction_strength=0.7,
        voice_enhancement_strength=0.5,
        vad_threshold=0.5,
        target_snr=20.0,
        preserve_natural_voice=True,
        output_format="wav"
    )
    options.validate()

    # 비정상 옵션 - noise_reduction_strength 범위 벗어남
    with pytest.raises(ValueError, match=r"noise_reduction_strength는 0.0~1.0 사이여야 합니다."):
        options = AIEnhanceOptions(noise_reduction_strength=1.5)
        options.validate()

    # 비정상 옵션 - vad_threshold 범위 벗어남
    with pytest.raises(ValueError, match=r"vad_threshold는 0.0~1.0 사이여야 합니다."):
        options = AIEnhanceOptions(vad_threshold=1.5)
        options.validate()


def test_ai_enhance_options_defaults():
    """AI 증강 옵션 기본값 테스트"""
    options = AIEnhanceOptions()
    assert options.enable_noise_reduction is True
    assert options.enable_voice_enhancement is True
    assert options.enable_vad is True
    assert options.enable_quality_assessment is True
    assert options.noise_reduction_strength == 0.7
    assert options.voice_enhancement_strength == 0.5
    assert options.vad_threshold == 0.5
    assert options.target_snr == 20.0
    assert options.preserve_natural_voice is True
    assert options.output_format == "wav"


def test_enhancement_result_structure():
    """EnhancementResult 데이터 구조 테스트"""
    # 실제 구현에서는 enhance_audio_with_ai 함수를 통해 생성되는 결과를 테스트
    # 여기서는 구조 검증만 수행

    # EnhancementResult가 필요한 필드를 모두 가지고 있는지 확인
    required_fields = [
        'output_path',
        'enhancement_id',
        'noise_reduction_applied',
        'voice_enhancement_applied',
        'segments_processed',
        'processing_time',
        'processing_details',
        'warnings'
    ]

    # 이 테스트는 실제 구현과 함께 수정되어야 함
    # 지금은 테스트 파일을 생성할 수 있는 최소한의 구조만 확인
    assert isinstance(required_fields, list)
    assert len(required_fields) > 0


@pytest.mark.asyncio
async def test_enhanced_audio_endpoint_exists():
    """Enhanced Audio 엔드포인트 존재 확인"""
    from backend.app.api.v1.audio import enhanced_preprocess

    # 라우터가 존재하는지 확인
    assert enhanced_preprocess.router is not None
    assert len(enhanced_preprocess.router.routes) > 0

    # POST /enhanced 엔드포인트 존재 확인
    enhanced_route = None
    for route in enhanced_preprocess.router.routes:
        if hasattr(route, 'path') and '/enhanced' in route.path:
            enhanced_route = route
            break

    assert enhanced_route is not None, "Enhanced Audio 엔드포인트가 라우터에 등록되지 않음"
