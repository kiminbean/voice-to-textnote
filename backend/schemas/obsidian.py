"""SPEC-OBSIDIAN-001: Obsidian 연계 Pydantic 스키마."""

from pydantic import BaseModel, Field


class ObsidianConfigRequest(BaseModel):
    """POST/PUT /api/v1/obsidian/config 요청 본문."""

    vault_path: str = Field(..., description="Obsidian vault 절대 경로")
    folder_pattern: str = Field(
        default="Voice-to-TextNote/{{date}}",
        description="노트 저장 폴더 패턴 (변수: {{date}}, {{year}}, {{month}}, {{title}})",
    )
    filename_pattern: str = Field(
        default="{{date}}_{{title}}",
        description="노트 파일명 패턴 (변수: {{date}}, {{time}}, {{title}}, {{meeting_id}})",
    )
    auto_export: bool = Field(default=False, description="파이프라인 완료 시 자동 export")
    conflict_policy: str = Field(
        default="overwrite",
        description="파일 충돌 정책 (overwrite | skip)",
    )
    frontmatter_custom: dict | None = Field(
        default=None,
        description="추가 frontmatter 필드 (additional_tags, custom_fields 등)",
    )
    note_template_id: str | None = Field(
        default=None, description="노트 템플릿 ID (null = 기본 템플릿)"
    )


class ObsidianConfigResponse(BaseModel):
    """설정 조회 응답."""

    vault_path: str
    vault_name: str
    vault_valid: bool
    folder_pattern: str
    filename_pattern: str
    auto_export: bool
    conflict_policy: str
    frontmatter_custom: dict | None = None
    note_template_id: str | None = None


class ObsidianValidateRequest(BaseModel):
    """Vault 경로 검증 요청."""

    vault_path: str = Field(..., description="검증할 vault 절대 경로")


class ObsidianValidateResponse(BaseModel):
    """Vault 검증 응답."""

    valid: bool
    vault_name: str = ""
    obsidian_folder_exists: bool = False
    writable: bool = False
    is_symlink: bool = False


class ObsidianExportResponse(BaseModel):
    """Export 결과 응답."""

    success: bool
    file_path: str = ""
    obsidian_uri: str = ""
    error: str | None = None
