// 팀 관련 데이터 모델 (SPEC-TEAM-001 REQ-TEAM-006)

// 팀 기본 모델
class Team {
  final String id;
  final String name;
  final String? description;
  final String createdBy;
  final DateTime createdAt;
  final int memberCount;

  const Team({
    required this.id,
    required this.name,
    this.description,
    required this.createdBy,
    required this.createdAt,
    required this.memberCount,
  });

  // JSON에서 Team 객체 생성
  factory Team.fromJson(Map<String, dynamic> json) {
    return Team(
      id: json['id'] as String,
      name: json['name'] as String,
      description: json['description'] as String?,
      createdBy: json['created_by'] as String,
      createdAt: DateTime.parse(json['created_at'] as String),
      memberCount: json['member_count'] as int,
    );
  }

  // Team 객체를 JSON으로 변환
  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'name': name,
      'description': description,
      'created_by': createdBy,
      'created_at': createdAt.toIso8601String(),
      'member_count': memberCount,
    };
  }

  // 특정 필드만 변경한 복사본 반환
  Team copyWith({
    String? id,
    String? name,
    String? description,
    String? createdBy,
    DateTime? createdAt,
    int? memberCount,
  }) {
    return Team(
      id: id ?? this.id,
      name: name ?? this.name,
      description: description ?? this.description,
      createdBy: createdBy ?? this.createdBy,
      createdAt: createdAt ?? this.createdAt,
      memberCount: memberCount ?? this.memberCount,
    );
  }
}

// 팀 멤버 모델
class TeamMember {
  final String userId;
  final String email;
  final String displayName;
  // 역할: admin, member, viewer
  final String role;
  final DateTime joinedAt;

  const TeamMember({
    required this.userId,
    required this.email,
    required this.displayName,
    required this.role,
    required this.joinedAt,
  });

  // JSON에서 TeamMember 객체 생성
  factory TeamMember.fromJson(Map<String, dynamic> json) {
    return TeamMember(
      userId: json['user_id'] as String,
      email: json['email'] as String,
      displayName: json['display_name'] as String,
      role: json['role'] as String,
      joinedAt: DateTime.parse(json['joined_at'] as String),
    );
  }

  // TeamMember 객체를 JSON으로 변환
  Map<String, dynamic> toJson() {
    return {
      'user_id': userId,
      'email': email,
      'display_name': displayName,
      'role': role,
      'joined_at': joinedAt.toIso8601String(),
    };
  }

  // 특정 필드만 변경한 복사본 반환
  TeamMember copyWith({
    String? userId,
    String? email,
    String? displayName,
    String? role,
    DateTime? joinedAt,
  }) {
    return TeamMember(
      userId: userId ?? this.userId,
      email: email ?? this.email,
      displayName: displayName ?? this.displayName,
      role: role ?? this.role,
      joinedAt: joinedAt ?? this.joinedAt,
    );
  }

  // 관리자 여부 확인
  bool get isAdmin => role == 'admin';
}

// 팀 상세 모델 (Team + 멤버 목록)
class TeamDetail extends Team {
  final List<TeamMember> members;

  const TeamDetail({
    required super.id,
    required super.name,
    super.description,
    required super.createdBy,
    required super.createdAt,
    required super.memberCount,
    required this.members,
  });

  // JSON에서 TeamDetail 객체 생성
  factory TeamDetail.fromJson(Map<String, dynamic> json) {
    final membersList = (json['members'] as List<dynamic>?)
            ?.map((m) => TeamMember.fromJson(m as Map<String, dynamic>))
            .toList() ??
        [];

    return TeamDetail(
      id: json['id'] as String,
      name: json['name'] as String,
      description: json['description'] as String?,
      createdBy: json['created_by'] as String,
      createdAt: DateTime.parse(json['created_at'] as String),
      memberCount: json['member_count'] as int,
      members: membersList,
    );
  }

  @override
  Map<String, dynamic> toJson() {
    final base = super.toJson();
    base['members'] = members.map((m) => m.toJson()).toList();
    return base;
  }

  @override
  TeamDetail copyWith({
    String? id,
    String? name,
    String? description,
    String? createdBy,
    DateTime? createdAt,
    int? memberCount,
    List<TeamMember>? members,
  }) {
    return TeamDetail(
      id: id ?? this.id,
      name: name ?? this.name,
      description: description ?? this.description,
      createdBy: createdBy ?? this.createdBy,
      createdAt: createdAt ?? this.createdAt,
      memberCount: memberCount ?? this.memberCount,
      members: members ?? this.members,
    );
  }
}

// 미팅 공유 응답 모델
class MeetingShareResponse {
  final String taskId;
  final String teamId;
  final DateTime sharedAt;

  const MeetingShareResponse({
    required this.taskId,
    required this.teamId,
    required this.sharedAt,
  });

  factory MeetingShareResponse.fromJson(Map<String, dynamic> json) {
    return MeetingShareResponse(
      taskId: json['task_id'] as String,
      teamId: json['team_id'] as String,
      sharedAt: DateTime.parse(json['shared_at'] as String),
    );
  }
}
