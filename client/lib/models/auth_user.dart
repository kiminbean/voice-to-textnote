// 인증된 사용자 데이터 모델
class AuthUser {
  final String id;
  final String email;
  final String displayName;
  final bool isActive;
  final DateTime? createdAt;
  final String provider;
  final String? avatarUrl;

  const AuthUser({
    required this.id,
    required this.email,
    required this.displayName,
    required this.isActive,
    this.createdAt,
    this.provider = 'email',
    this.avatarUrl,
  });

  factory AuthUser.fromJson(Map<String, dynamic> json) {
    return AuthUser(
      id: json['id'] as String,
      email: json['email'] as String,
      displayName: json['display_name'] as String,
      isActive: json['is_active'] as bool? ?? true,
      createdAt: json['created_at'] != null
          ? DateTime.tryParse(json['created_at'] as String)
          : null,
      provider: json['provider'] as String? ?? 'email',
      avatarUrl: json['avatar_url'] as String?,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'email': email,
      'display_name': displayName,
      'is_active': isActive,
      'created_at': createdAt?.toIso8601String(),
      'provider': provider,
      'avatar_url': avatarUrl,
    };
  }

  AuthUser copyWith({
    String? id,
    String? email,
    String? displayName,
    bool? isActive,
    DateTime? createdAt,
    String? provider,
    String? avatarUrl,
  }) {
    return AuthUser(
      id: id ?? this.id,
      email: email ?? this.email,
      displayName: displayName ?? this.displayName,
      isActive: isActive ?? this.isActive,
      createdAt: createdAt ?? this.createdAt,
      provider: provider ?? this.provider,
      avatarUrl: avatarUrl ?? this.avatarUrl,
    );
  }
}

// 인증 응답 모델 (로그인/회원가입 공통)
// 서버는 {access_token, refresh_token, token_type}만 반환 (user 필드 없음)
class AuthResponse {
  final String accessToken;
  final String refreshToken;
  final String tokenType;

  const AuthResponse({
    required this.accessToken,
    required this.refreshToken,
    required this.tokenType,
  });

  factory AuthResponse.fromJson(Map<String, dynamic> json) {
    return AuthResponse(
      accessToken: json['access_token'] as String,
      refreshToken: json['refresh_token'] as String,
      tokenType: json['token_type'] as String,
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
