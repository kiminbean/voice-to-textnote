# Interview: 회의록 실시간 공동 편집

## Round 1: Scope
Question: 공동 편집의 대상은 어디까지인가요?
Answer: 회의록 전체 (STT/Diarization 결과 기반 회의록 전체를 공동 편집. 섹션 추가/수정/삭제, 텍스트 편집, 화자별 발화 수정 모두 포함)

Question: 동시 편집 시 최대 몇 명까지 지원해야 하나요?
Answer: 소규모 (2-5명). 팀 단위 협업에 적합. CRDT 없이 WebSocket + 낙관적 락킹으로 구현 가능.

Question: 명시적으로 제외할 기능은?
Answer: 버전 히스토리/복구만 제외. 실시간 편집, 커서 표시, 변경 사항 동기화는 포함. 버전 히스토리와 복구는 후속 SPEC으로 분리.

## Round 2: Constraints
Question: 실시간 동기화에 사용할 기술 스택은?
Answer: WebSocket + 낙관적 락킹. FastAPI WebSocket으로 변경 사항 브로드캐스트. 충돌 시 마지막 수정 우선(LWW). 소규모 2-5명에 적합.

Question: 기존 인증 시스템(SPEC-TEAM-001 JWT)과의 연동 방식은?
Answer: JWT 기존 인증 그대로 활용. WebSocket 연결 시 JWT 토큰 검증. 기존 RBAC(admin/member/viewer) 권한 그대로 적용. 편집 권한은 member 이상.

Question: 실시간 동기화의 목표 지연 시간은?
Answer: 1초 이내. WebSocket 기반으로 충분히 달성 가능. 타이핑 시 1초 이내 다른 사용자에게 반영.

## Clarity Score
Initial: 2/10
Final: 9/10
Rounds completed: 2
