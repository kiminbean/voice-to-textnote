"""
JSON 처리 공통 유틸리티

pipeline 모듈에서 공유하는 JSON 정제 헬퍼.
"""


def strip_json_comments(text: str) -> str:
    """
    JSON 텍스트에서 // 주석을 안전하게 제거.

    문자열 내부의 //는 보호 (문자 단위 따옴표 추적).
    """
    lines = text.split("\n")
    result: list[str] = []
    for line in lines:
        in_string = False
        i = 0
        stripped_line = line
        while i < len(line) - 1:
            ch = line[i]
            if ch == "\\" and in_string:
                i += 2  # 이스케이프 문자 건너뜀
                continue
            if ch == '"':
                in_string = not in_string
            elif ch == "/" and line[i + 1] == "/" and not in_string:
                # 문자열 밖의 // 발견 → 여기서 자름
                stripped_line = line[:i].rstrip()
                break
            i += 1
        result.append(stripped_line)
    return "\n".join(result)
