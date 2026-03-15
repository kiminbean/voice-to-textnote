---
name: Flutter TDD 구현 규칙
description: Voice to TextNote 프로젝트의 Flutter TDD 구현 시 지켜야 할 패턴
type: feedback
---

# Flutter TDD 구현 규칙

## 규칙 1: mocktail 사용 (mockito 금지)
mocktail로 Dio를 모킹할 때 `class MockDio extends Mock implements Dio {}` 패턴 사용.

**Why:** 프로젝트 의존성이 mocktail로 고정됨
**How to apply:** 모든 Mock 클래스는 mocktail의 Mock 클래스 상속

## 규칙 2: 파일 업로드 테스트에서 실제 임시 파일 생성
TranscriptionApi.upload() 테스트 시 `/tmp/test.m4a` 같은 가상 경로는 실패.
`Directory.systemTemp.createTemp()` + `File.writeAsBytes([0, 1, 2, 3])` 패턴으로 임시 파일 생성 후 tearDownAll에서 정리.

**Why:** MultipartFile.fromFile()이 실제 파일 존재를 확인함
**How to apply:** setUpAll/tearDownAll에서 임시 파일 관리

## 규칙 3: 모든 Dart 코드 주석은 한국어
**Why:** language.yaml의 code_comments: ko 설정
**How to apply:** 모든 새 파일의 주석을 한국어로 작성

## 규칙 4: Riverpod NotifierProvider 패턴 사용
StateNotifier, ChangeNotifier 사용 금지. `class XxxNotifier extends Notifier<State>` 패턴 사용.

**Why:** SPEC 지침, 최신 Riverpod 패턴
**How to apply:** 모든 상태 관리는 NotifierProvider/Notifier 조합
