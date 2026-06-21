"""
SPEC-SEC-002 파일 시그니처(매직 바이트) 검증 단위 테스트
REQ-SEC-040~043: 오디오 및 템플릿 파일 매직 바이트 검증
"""

from backend.utils.file_signature import (
    get_required_header_size,
    verify_file_signature,
)


class TestVerifyFileSignatureAudio:
    def test_wav_valid(self):
        header = b"RIFF\x24\x00\x00\x00WAVEfmt "
        assert verify_file_signature(header, ".wav") is True

    def test_wav_missing_wave(self):
        header = b"RIFF\x24\x00\x00\x00XXXXfmt "
        assert verify_file_signature(header, ".wav") is False

    def test_wav_missing_riff(self):
        header = b"XXXX\x24\x00\x00\x00WAVEfmt "
        assert verify_file_signature(header, ".wav") is False

    def test_mp3_with_id3(self):
        header = b"ID3\x03\x00\x00\x00\x00\x00\x00"
        assert verify_file_signature(header, ".mp3") is True

    def test_mp3_with_fffb(self):
        header = b"\xff\xfb\x90\x00\x00\x00\x00\x00"
        assert verify_file_signature(header, ".mp3") is True

    def test_mp3_with_ffxf2(self):
        header = b"\xff\xf2\x50\x00\x00\x00\x00\x00"
        assert verify_file_signature(header, ".mp3") is True

    def test_mp3_invalid(self):
        header = b"\x00\x00\x00\x00\x00\x00\x00\x00"
        assert verify_file_signature(header, ".mp3") is False

    def test_m4a_valid(self):
        header = b"\x00\x00\x00\x20ftypM4A \x00"
        assert verify_file_signature(header, ".m4a") is True

    def test_m4a_invalid(self):
        header = b"\x00\x00\x00\x00XXXXM4A \x00"
        assert verify_file_signature(header, ".m4a") is False

    def test_mp4_valid(self):
        header = b"\x00\x00\x00\x20ftypisom\x00"
        assert verify_file_signature(header, ".mp4") is True

    def test_mp4_invalid(self):
        header = b"\x00\x00\x00\x00XXXXisom\x00"
        assert verify_file_signature(header, ".mp4") is False

    def test_ogg_valid(self):
        header = b"OggS\x00\x02\x00\x00\x00\x00"
        assert verify_file_signature(header, ".ogg") is True

    def test_ogg_invalid(self):
        header = b"XXXX\x00\x02\x00\x00\x00\x00"
        assert verify_file_signature(header, ".ogg") is False


class TestVerifyFileSignatureTemplate:
    def test_pdf_valid(self):
        header = b"%PDF-1.7\n\x00\x00\x00\x00\x00\x00"
        assert verify_file_signature(header, ".pdf") is True

    def test_pdf_invalid(self):
        header = b"\x00\x00\x00\x00\x00\x00\x00\x00"
        assert verify_file_signature(header, ".pdf") is False

    def test_docx_valid(self):
        header = b"PK\x03\x04\x14\x00\x00\x00\x08\x00"
        assert verify_file_signature(header, ".docx") is True

    def test_docx_invalid(self):
        header = b"\x00\x00\x00\x00\x00\x00\x00\x00"
        assert verify_file_signature(header, ".docx") is False


class TestVerifyFileSignatureImage:
    def test_png_valid(self):
        assert verify_file_signature(b"\x89PNG\r\n\x1a\n\x00\x00", ".png") is True

    def test_jpeg_valid(self):
        assert verify_file_signature(b"\xff\xd8\xff\xe0\x00\x10JFIF", ".jpg") is True
        assert verify_file_signature(b"\xff\xd8\xff\xe0\x00\x10JFIF", ".jpeg") is True

    def test_webp_requires_riff_and_webp(self):
        assert verify_file_signature(b"RIFF\x00\x00\x00\x00WEBP", ".webp") is True
        assert verify_file_signature(b"RIFF\x00\x00\x00\x00XXXX", ".webp") is False

    def test_heic_valid(self):
        assert verify_file_signature(b"\x00\x00\x00\x18ftypheic", ".heic") is True


class TestVerifyFileSignatureEdgeCases:
    def test_unknown_extension_passes(self):
        header = b"\x00\x00\x00\x00"
        assert verify_file_signature(header, ".xyz") is True

    def test_extension_case_insensitive(self):
        header = b"RIFF\x24\x00\x00\x00WAVEfmt "
        assert verify_file_signature(header, ".WAV") is True

    def test_short_header_wav(self):
        header = b"RIFF"
        assert verify_file_signature(header, ".wav") is False

    def test_empty_header(self):
        assert verify_file_signature(b"", ".wav") is False

    def test_exact_16_byte_header(self):
        header = b"RIFF\x24\x00\x00\x00WAVEfmt "
        assert len(header) == 16
        assert verify_file_signature(header, ".wav") is True

    def test_longer_header_works(self):
        header = b"RIFF\x24\x00\x00\x00WAVEfmt " + b"\x00" * 100
        assert verify_file_signature(header, ".wav") is True


class TestGetRequiredHeaderSize:
    def test_returns_positive_int(self):
        size = get_required_header_size()
        assert isinstance(size, int)
        assert size > 0

    def test_returns_at_least_12(self):
        size = get_required_header_size()
        assert size >= 12
