import 'package:flutter/material.dart';

import '../services/api_exceptions.dart';
import '../services/auth_storage.dart';

/// Диалог входа/регистрации перед синхронизацией.
///
/// Возвращает `true` через [Navigator.pop], если пользователь успешно
/// авторизовался (токен сохранён в [AuthStorage]).
class AuthDialog extends StatefulWidget {
  const AuthDialog({super.key, required this.authStorage});

  final AuthStorage authStorage;

  /// Показывает диалог и сообщает результат авторизации.
  static Future<bool> show(BuildContext context, AuthStorage authStorage) async {
    final result = await showDialog<bool>(
      context: context,
      barrierDismissible: false,
      builder: (_) => AuthDialog(authStorage: authStorage),
    );
    return result ?? false;
  }

  @override
  State<AuthDialog> createState() => _AuthDialogState();
}

class _AuthDialogState extends State<AuthDialog> {
  final _formKey = GlobalKey<FormState>();
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();

  bool _isLogin = true;
  bool _loading = false;
  bool _obscurePassword = true;
  String? _errorText;

  @override
  void initState() {
    super.initState();
    _prefillEmail();
  }

  Future<void> _prefillEmail() async {
    final saved = await widget.authStorage.email;
    if (saved != null && mounted) {
      _emailController.text = saved;
    }
  }

  @override
  void dispose() {
    _emailController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (_loading) return;
    if (!(_formKey.currentState?.validate() ?? false)) return;

    setState(() {
      _loading = true;
      _errorText = null;
    });

    final email = _emailController.text.trim();
    final password = _passwordController.text;
    try {
      if (_isLogin) {
        await widget.authStorage.login(email, password);
      } else {
        await widget.authStorage.register(email, password);
      }
      if (mounted) Navigator.of(context).pop(true);
    } on ApiException catch (exception) {
      setState(() => _errorText = exception.message);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  void _toggleMode() {
    if (_loading) return;
    setState(() {
      _isLogin = !_isLogin;
      _errorText = null;
    });
  }

  @override
  Widget build(BuildContext context) {
    final title = _isLogin ? 'Вход в CalendAI' : 'Регистрация в CalendAI';
    final submitLabel = _isLogin ? 'Войти' : 'Зарегистрироваться';

    return AlertDialog(
      title: Text(title),
      content: Form(
        key: _formKey,
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              TextFormField(
                controller: _emailController,
                enabled: !_loading,
                keyboardType: TextInputType.emailAddress,
                autofillHints: const [AutofillHints.email],
                textInputAction: TextInputAction.next,
                decoration: const InputDecoration(
                  labelText: 'Email',
                  prefixIcon: Icon(Icons.email_outlined),
                  border: OutlineInputBorder(),
                ),
                validator: (value) {
                  final email = value?.trim() ?? '';
                  if (email.isEmpty) return 'Введите email';
                  if (!email.contains('@') || !email.contains('.')) {
                    return 'Некорректный email';
                  }
                  return null;
                },
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: _passwordController,
                enabled: !_loading,
                obscureText: _obscurePassword,
                autofillHints: const [AutofillHints.password],
                textInputAction: TextInputAction.done,
                onFieldSubmitted: (_) => _submit(),
                decoration: InputDecoration(
                  labelText: 'Пароль',
                  prefixIcon: const Icon(Icons.lock_outline),
                  border: const OutlineInputBorder(),
                  suffixIcon: IconButton(
                    icon: Icon(
                      _obscurePassword
                          ? Icons.visibility_outlined
                          : Icons.visibility_off_outlined,
                    ),
                    onPressed: () => setState(
                      () => _obscurePassword = !_obscurePassword,
                    ),
                  ),
                ),
                validator: (value) {
                  final password = value ?? '';
                  if (password.isEmpty) return 'Введите пароль';
                  if (!_isLogin && password.length < 8) {
                    return 'Пароль должен быть не короче 8 символов';
                  }
                  return null;
                },
              ),
              if (_errorText != null) ...[
                const SizedBox(height: 12),
                Text(
                  _errorText!,
                  style: TextStyle(
                    color: Theme.of(context).colorScheme.error,
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
      // OverflowBar сам переносит кнопки на новую строку на узких экранах.
      actions: [
        TextButton(
          onPressed: _loading ? null : _toggleMode,
          child: Text(_isLogin ? 'Создать аккаунт' : 'У меня есть аккаунт'),
        ),
        TextButton(
          onPressed: _loading ? null : () => Navigator.of(context).pop(false),
          child: const Text('Отмена'),
        ),
        FilledButton(
          onPressed: _loading ? null : _submit,
          child: _loading
              ? const SizedBox(
                  width: 18,
                  height: 18,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : Text(submitLabel),
        ),
      ],
    );
  }
}
