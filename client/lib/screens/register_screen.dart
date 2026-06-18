// 회원가입 화면 — 모던 미니멀
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:voice_to_textnote/providers/auth_provider.dart';
import 'package:voice_to_textnote/theme/app_spacing.dart';

class RegisterScreen extends ConsumerStatefulWidget {
  const RegisterScreen({super.key});

  @override
  ConsumerState<RegisterScreen> createState() => _RegisterScreenState();
}

class _RegisterScreenState extends ConsumerState<RegisterScreen> {
  final _formKey = GlobalKey<FormState>();
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();
  final _confirmPasswordController = TextEditingController();
  final _displayNameController = TextEditingController();
  bool _obscurePassword = true;
  bool _obscureConfirmPassword = true;

  @override
  void dispose() {
    _emailController.dispose();
    _passwordController.dispose();
    _confirmPasswordController.dispose();
    _displayNameController.dispose();
    super.dispose();
  }

  String? _validatePassword(String? value) {
    if (value == null || value.isEmpty) return '비밀번호를 입력해주세요.';
    if (value.length < 8) return '비밀번호는 8자 이상이어야 합니다.';
    final hasLetter = RegExp(r'[a-zA-Z]').hasMatch(value);
    final hasDigit = RegExp(r'[0-9]').hasMatch(value);
    if (!hasLetter || !hasDigit) return '영문과 숫자를 조합해주세요.';
    return null;
  }

  Future<void> _handleRegister() async {
    if (!_formKey.currentState!.validate()) return;
    await ref.read(authStateProvider.notifier).register(
          _emailController.text.trim(),
          _passwordController.text,
          _displayNameController.text.trim(),
        );
  }

  @override
  Widget build(BuildContext context) {
    final authState = ref.watch(authStateProvider);
    final isLoading = authState.isLoading;

    ref.listen<AuthState>(authStateProvider, (_, next) {
      if (next.status == AuthStatus.unauthenticated && next.errorMessage != null) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(next.errorMessage!)));
      }
    });

    return Scaffold(
      appBar: AppBar(
        title: const Text('회원가입'),
        leading: BackButton(onPressed: isLoading ? null : () => context.pop()),
      ),
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.symmetric(
                horizontal: AppSpacing.xl, vertical: AppSpacing.lg),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 400),
              child: Form(
                key: _formKey,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    // 환영 메시지
                    Text(
                      '환영합니다',
                      style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                            fontWeight: FontWeight.w700,
                            letterSpacing: -0.3,
                          ),
                    ),
                    const SizedBox(height: AppSpacing.sm),
                    Text(
                      '회의 기록을 시작하려면 계정을 만드세요',
                      style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                            color: Theme.of(context).colorScheme.outline,
                          ),
                    ),
                    const SizedBox(height: AppSpacing.xl),

                    TextFormField(
                      controller: _displayNameController,
                      textInputAction: TextInputAction.next,
                      enabled: !isLoading,
                      decoration: const InputDecoration(
                        labelText: '이름',
                        prefixIcon: Icon(Icons.person_outline_rounded),
                      ),
                      validator: (value) {
                        if (value == null || value.trim().isEmpty) return '이름을 입력해주세요.';
                        if (value.trim().length < 2) return '이름은 2자 이상이어야 합니다.';
                        return null;
                      },
                    ),
                    const SizedBox(height: AppSpacing.md),

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
                        if (value == null || value.trim().isEmpty) return '이메일을 입력해주세요.';
                        final emailRegex = RegExp(r'^[\w-\.]+@([\w-]+\.)+[\w-]{2,4}$');
                        if (!emailRegex.hasMatch(value.trim())) return '올바른 이메일 형식을 입력해주세요.';
                        return null;
                      },
                    ),
                    const SizedBox(height: AppSpacing.md),

                    TextFormField(
                      controller: _passwordController,
                      obscureText: _obscurePassword,
                      textInputAction: TextInputAction.next,
                      enabled: !isLoading,
                      decoration: InputDecoration(
                        labelText: '비밀번호',
                        hintText: '영문+숫자 8자 이상',
                        prefixIcon: const Icon(Icons.lock_outline_rounded),
                        suffixIcon: IconButton(
                          icon: Icon(_obscurePassword
                              ? Icons.visibility_off_outlined
                              : Icons.visibility_outlined),
                          onPressed: () => setState(() => _obscurePassword = !_obscurePassword),
                        ),
                      ),
                      validator: _validatePassword,
                    ),
                    const SizedBox(height: AppSpacing.md),

                    TextFormField(
                      controller: _confirmPasswordController,
                      obscureText: _obscureConfirmPassword,
                      textInputAction: TextInputAction.done,
                      enabled: !isLoading,
                      onFieldSubmitted: (_) => _handleRegister(),
                      decoration: InputDecoration(
                        labelText: '비밀번호 확인',
                        prefixIcon: const Icon(Icons.lock_outline_rounded),
                        suffixIcon: IconButton(
                          icon: Icon(_obscureConfirmPassword
                              ? Icons.visibility_off_outlined
                              : Icons.visibility_outlined),
                          onPressed: () => setState(
                              () => _obscureConfirmPassword = !_obscureConfirmPassword),
                        ),
                      ),
                      validator: (value) {
                        if (value == null || value.isEmpty) return '비밀번호를 다시 입력해주세요.';
                        if (value != _passwordController.text) return '비밀번호가 일치하지 않습니다.';
                        return null;
                      },
                    ),
                    const SizedBox(height: AppSpacing.xl),

                    FilledButton(
                      onPressed: isLoading ? null : _handleRegister,
                      child: isLoading
                          ? const SizedBox(
                              height: 20,
                              width: 20,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            )
                          : const Text('가입하기'),
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
}
