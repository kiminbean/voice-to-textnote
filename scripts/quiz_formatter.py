#!/usr/bin/env python3
import json
import sys
from datetime import datetime

def format_quiz_for_telegram():
    # JSON 파일 읽기
    quiz_file = "/Users/ibkim/Projects/openclaw/qnet-quiz/questions-2026-06-24.json"
    
    try:
        with open(quiz_file, 'r', encoding='utf-8') as f:
            quiz_data = json.load(f)
    except FileNotFoundError:
        print("퀴즈 파일을 찾을 수 없습니다.")
        return
    except json.JSONDecodeError:
        print("JSON 파일 파싱 오류")
        return
    
    # 출력 시작
    print("📝 정보처리기사 기출 퀴즈 — 20문제 (시험 D-146)")
    print("━━━━━━━━━━━━━━━━━━")
    print()
    
    # 각 과목별로 출력
    for subject_name, questions in quiz_data['subjects'].items():
        # 과목명 출력
        print(f"**[{subject_name}]**")
        print()
        
        # 각 문제 출력
        for i, question in enumerate(questions, 1):
            question_num = i
            
            # 문제 내용 출력
            print(f"🔁 **Q{question_num}. {question['question']}**")
            
            # 보기 출력 (정답에 ✅ 표시)
            options = question['options']
            answer_index = question['answer']
            
            for j, option in enumerate(options):
                option_marker = ['①', '②', '③', '④'][j]
                if j == answer_index:
                    print(f"{option_marker} {option} ✅")
                else:
                    print(f"{option_marker} {option}")
            
            # 해설 출력
            print(f"📖 {question['explanation']}")
            print()
        
        # 과목 변경 시 구분선 추가 (마지막 과목 제외)
        if subject_name != "정보시스템":
            print("━━━━━━━━━━━━━━━━━━")
            print()
    
    # 출력 끝
    print("━━━━━━━━━━━━━━━━━━")
    print("정답은 ✅ 표시! 맞힌 개수 세어보세요 😎")
    print("📊 출처: 2024-2025 기출문제")
    print()
    print("**주의:**")
    print("- 요약만 보내지 말고, 전체 20문제를 텔레그램에 직접 출력")
    print("- 정답은 각 문제 옆에 ✅로 표시")
    print("- 과목별로 묶어서 출력 (소프트웨어 설계 → 개발 → DB → 프로그래밍 → 정보시스템)")
    print("- answer는 0-indexed이므로: 0=①, 1=②, 2=③, 3=④")
    print("- 해설(explanation)도 반드시 포함")
    print("- 과목 변경 시 구분선 추가")

if __name__ == "__main__":
    format_quiz_for_telegram()