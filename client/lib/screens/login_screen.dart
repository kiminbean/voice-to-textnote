// 로그인 화면 — 모던 미니멀
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:voice_to_textnote/providers/auth_provider.dart';
import 'package:voice_to_textnote/theme/app_colors.dart';
import 'package:voice_to_textnote/theme/app_spacing.dart';

class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key});

  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  final _formKey = GlobalKey<FormState>();
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();
  bool _obscurePassword = true;

  @override
  void dispose() {
    _emailController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  // 로그인 처리
  Future<void> _handleLogin() async {
    if (!_formKey.currentState!.validate()) return;
    await ref.read(authStateProvider.notifier).login(
          _emailController.text.trim(),
          _passwordController.text,
        );
  }

  // 게스트로 시작 처리 (SPEC-GUEST-001)
  Future<void> _handleGuestStart() async {
    await ref.read(authStateProvider.notifier).startAsGuest();
  }

  // Google 소셜 로그인 (REQ-OAUTH-001)
  Future<void> _handleGoogleLogin() async {
    await ref.read(authStateProvider.notifier).loginWithGoogle();
  }

  // Apple 소셜 로그인 (REQ-OAUTH-001)
  Future<void> _handleAppleLogin() async {
    await ref.read(authStateProvider.notifier).loginWithApple();
  }

  @override
  Widget build(BuildContext context) {
    final scheme = AppColors.of(context);
    final authState = ref.watch(authStateProvider);
    final isLoading = authState.isLoading;

    // 에러 메시지 스낵바 표시
    ref.listen<AuthState>(authStateProvider, (_, next) {
      if (next.status == AuthStatus.unauthenticated &&
          next.errorMessage != null) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(next.errorMessage!)),
        );
      }
    });

    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.symmetric(horizontal: AppSpacing.xl),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 400),
              child: Form(
                key: _formKey,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    const SizedBox(height: AppSpacing.xxxl),
                    // 브랜드 로고
                    Center(child: _buildLogo()),
                    const SizedBox(height: AppSpacing.xl),
                    // 타이틀
                    Text(
                      'Voice to TextNote',
                      textAlign: TextAlign.center,
                      style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                            fontWeight: FontWeight.w700,
                            letterSpacing: -0.3,
                          ),
                    ),
                    const SizedBox(height: AppSpacing.sm),
                    Text(
                      '프라이버시 우선 회의 자동 기록',
                      textAlign: TextAlign.center,
                      style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                            color: scheme.textTertiary,
                          ),
                    ),
                    const SizedBox(height: AppSpacing.xxl),

                    // 이메일 입력
                    TextFormField(
                      controller: _emailController,
                      keyboardType: TextInputType.emailAddress,
                      textInputAction: TextInputAction.next,
                      enabled: !isLoading,
                      decoration: const InputDecoration(
                        labelText: '이메일',
                        prefixIcon: Icon(Icons.mail_outline_rounded),
                      ),
                      validator: (value) {
                        if (value == null || value.trim().isEmpty) {
                          return '이메일을 입력해주세요.';
                        }
                        final emailRegex =
                            RegExp(r'^[\w-\.]+@([\w-]+\.)+[\w-]{2,4}$');
                        if (!emailRegex.hasMatch(value.trim())) {
                          return '올바른 이메일 형식을 입력해주세요.';
                        }
                        return null;
                      },
                    ),
                    const SizedBox(height: AppSpacing.md),

                    // 비밀번호 입력
                    TextFormField(
                      controller: _passwordController,
                      obscureText: _obscurePassword,
                      textInputAction: TextInputAction.done,
                      enabled: !isLoading,
                      onFieldSubmitted: (_) => _handleLogin(),
                      decoration: InputDecoration(
                        labelText: '비밀번호',
                        prefixIcon: const Icon(Icons.lock_outline_rounded),
                        suffixIcon: IconButton(
                          icon: Icon(
                            _obscurePassword
                                ? Icons.visibility_off_outlined
                                : Icons.visibility_outlined,
                          ),
                          onPressed: () {
                            setState(() => _obscurePassword = !_obscurePassword);
                          },
                        ),
                      ),
                      validator: (value) {
                        if (value == null || value.isEmpty) {
                          return '비밀번호를 입력해주세요.';
                        }
                        if (value.length < 8) {
                          return '비밀번호는 8자 이상이어야 합니다.';
                        }
                        return null;
                      },
                    ),
                    const SizedBox(height: AppSpacing.xl),

                    // 로그인 버튼
                    FilledButton(
                      onPressed: isLoading ? null : _handleLogin,
                      child: isLoading
                          ? const SizedBox(
                              height: 20,
                              width: 20,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            )
                          : const Text('로그인'),
                    ),
                    const SizedBox(height: AppSpacing.xl),

                    // 소셜 로그인 구분선
                    Row(
                      children: [
                        Expanded(child: Divider(color: scheme.border)),
                        Padding(
                          padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md),
                          child: Text(
                            '또는',
                            style: Theme.of(context).textTheme.bodySmall?.copyWith(
                                  color: scheme.textTertiary,
                                ),
                          ),
                        ),
                        Expanded(child: Divider(color: scheme.border)),
                      ],
                    ),
                    const SizedBox(height: AppSpacing.md),

                    // Google 로그인
                    _SocialButton(
                      icon: const Icon(Icons.g_mobiledata, size: 22),
                      label: 'Google로 계속하기',
                      onPressed: isLoading ? null : _handleGoogleLogin,
                    ),
                    const SizedBox(height: AppSpacing.sm),

                    // Apple 로그인
                    _SocialButton(
                      icon: const Icon(Icons.apple, size: 22),
                      label: 'Apple로 계속하기',
                      onPressed: isLoading ? null : _handleAppleLogin,
                    ),
                    const SizedBox(height: AppSpacing.xxl),

                    // 회원가입 링크
                    Center(
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Text(
                            '계정이 없으신가요?',
                            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                                  color: scheme.textTertiary,
                                ),
                          ),
                          TextButton(
                            onPressed: isLoading
                                ? null
                                : () => context.push('/register'),
                            child: const Text('회원가입'),
                          ),
                        ],
                      ),
                    ),

                    // 게스트로 시작
                    TextButton(
                      onPressed: isLoading ? null : _handleGuestStart,
                      child: Text(
                        '게스트로 시작 (24시간 저장)',
                        style: TextStyle(color: scheme.textTertiary),
                      ),
                    ),
                    const SizedBox(height: AppSpacing.xxl),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }

  // 브랜드 로고 — 그라데이션 원 + 마이크 아이콘
  Widget _buildLogo() {
    return Container(
      width: 72,
      height: 72,
      decoration: const BoxDecoration(
        gradient: AppColors.brandGradient,
        shape: BoxShape.circle,
        boxShadow: [
          BoxShadow(
            color: Color(0x334F46E5),
            blurRadius: 24,
            offset: Offset(0, 8),
          ),
        ],
      ),
      child: const Icon(Icons.mic_rounded, color: Colors.white, size: 34),
    );
  }
}

/// 소셜 로그인 보조 버튼
class _SocialButton extends StatelessWidget {
  final Widget icon;
  final String label;
  final VoidCallback? onPressed;

  const _SocialButton({
    required this.icon,
    required this.label,
    this.onPressed,
  });

  @override
  Widget build(BuildContext context) {
    final scheme = AppColors.of(context);
    return OutlinedButton.icon(
      onPressed: onPressed,
      icon: icon,
      label: Text(label),
      style: OutlinedButton.styleFrom(
        foregroundColor: scheme.textPrimary,
        side: BorderSide(color: scheme.border),
      ),
    );
  }
}
