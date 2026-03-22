// 인증된 사용자 데이터 모델
class AuthUser {
  final String id;
  final String email;
  final String displayName;
  final bool isActive;
  final DateTime? createdAt;

  const AuthUser({
    required this.id,
    required this.email,
    required this.displayName,
    required this.isActive,
    this.createdAt,
  });

  // JSON에서 AuthUser 객체 생성
  factory AuthUser.fromJson(Map<String, dynamic> json) {
    return AuthUser(
      id: json['id'] as String,
      email: json['email'] as String,
      displayName: json['display_name'] as String,
      isActive: json['is_active'] as bool? ?? true,
      createdAt: json['created_at'] != null
          ? DateTime.tryParse(json['created_at'] as String)
          : null,
    );
  }

  // AuthUser 객체를 JSON으로 변환
  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'email': email,
      'display_name': displayName,
      'is_active': isActive,
      'created_at': createdAt?.toIso8601String(),
    };
  }

  // 특정 필드만 변경한 복사본 반환
  AuthUser copyWith({
    String? id,
    String? email,
    String? displayName,
    bool? isActive,
    DateTime? createdAt,
  }) {
    return AuthUser(
      id: id ?? this.id,
      email: email ?? this.email,
      displayName: displayName ?? this.displayName,
      isActive: isActive ?? this.isActive,
      createdAt: createdAt ?? this.createdAt,
    );
  }
}

// 인증 응답 모델 (로그인/회원가입 공통)
class AuthResponse {
  final String accessToken;
  final String refreshToken;
  final String tokenType;
  final AuthUser user;

  const AuthResponse({
    required this.accessToken,
    required this.refreshToken,
    required this.tokenType,
    required this.user,
  });

  factory AuthResponse.fromJson(Map<String, dynamic> json) {
    return AuthResponse(
      accessToken: json['access_token'] as String,
      refreshToken: json['refresh_token'] as String,
      tokenType: json['token_type'] as String,
      user: AuthUser.fromJson(json['user'] as Map<String, dynamic>),
    );
  }
}

// 토큰 갱신 응답 모델
class TokenResponse {
  final String accessToken;
  final String refreshToken;
  final String tokenType;

  const TokenResponse({
    required this.accessToken,
    required this.refreshToken,
    required this.tokenType,
  });

  factory TokenResponse.fromJson(Map<String, dynamic> json) {
    return TokenResponse(
      accessToken: json['access_token'] as String,
      refreshToken: json['refresh_token'] as String,
      tokenType: json['token_type'] as String,
    );
  }
}
