import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import '../database/app_database.dart';
import 'api_config.dart';
import 'api_exceptions.dart';

/// JWT-авторизация: хранение токена в SharedPreferences
/// и запросы регистрации/входа к backend API.
class AuthStorage {
  AuthStorage({http.Client? client, String? baseUrl})
      : _client = client ?? http.Client(),
        _baseUrl = baseUrl ?? ApiConfig.baseUrl;

  static const String _tokenKey = 'auth_token';
  static const String _emailKey = 'auth_email';
  static const Duration _timeout = Duration(seconds: 20);

  final http.Client _client;
  final String _baseUrl;

  // ---------------- Токен ----------------

  /// Сохранённый JWT или `null`, если пользователь не авторизован.
  Future<String?> get token async {
    final prefs = await SharedPreferences.getInstance();
    final value = prefs.getString(_tokenKey);
    return (value == null || value.isEmpty) ? null : value;
  }

  /// Email последнего успешного входа (для подстановки в диалог).
  Future<String?> get email async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(_emailKey);
  }

  Future<bool> get isAuthenticated async => (await token) != null;

  Future<void> saveToken(String token, {String? email}) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_tokenKey, token);
    if (email != null && email.isNotEmpty) {
      await prefs.setString(_emailKey, email);
    }
  }

  /// Сброс авторизации (выход или истёкший токен).
  Future<void> clear({bool clearDatabase = false}) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_tokenKey);
    if (clearDatabase) {
      await AppDatabase.instance.clearAll();
      await prefs.remove(_emailKey);
    }
  }

  // ---------------- Аккаунт ----------------

  /// Вход: `POST /auth/login`, сохраняет полученный JWT.
  Future<void> login(String email, String password) async {
    final previousEmail = await this.email;
    final normalizedEmail = email.trim();
    final body = await _post(
      '/auth/login',
      {'email': normalizedEmail, 'password': password},
    );
    final accessToken = body['access_token'];
    if (accessToken is! String || accessToken.isEmpty) {
      throw const ApiRequestException(
        'Сервер не вернул токен авторизации.',
        statusCode: 200,
      );
    }
    // Если произошла смена пользователя на устройстве — очищаем локальную базу
    if (previousEmail != null &&
        previousEmail.toLowerCase() != normalizedEmail.toLowerCase()) {
      await AppDatabase.instance.clearAll();
    }
    await saveToken(accessToken, email: normalizedEmail);
  }

  /// Регистрация: `POST /auth/register`, затем автоматический вход.
  Future<void> register(String email, String password) async {
    await _post(
      '/auth/register',
      {'email': email.trim(), 'password': password},
      expectedStatus: 201,
    );
    // Сервер при регистрации возвращает профиль без токена —
    // сразу выполняем вход, чтобы получить JWT.
    await login(email, password);
  }

  // ---------------- HTTP ----------------

  Future<Map<String, dynamic>> _post(
    String path,
    Map<String, dynamic> body, {
    int expectedStatus = 200,
  }) async {
    http.Response response;
    try {
      response = await _client
          .post(
            Uri.parse('$_baseUrl$path'),
            headers: const {
              'Content-Type': 'application/json; charset=utf-8',
            },
            body: jsonEncode(body),
          )
          .timeout(_timeout);
    } on SocketException {
      throw const NetworkException();
    } on http.ClientException {
      throw const NetworkException();
    } on TimeoutException {
      throw const NetworkException(
        'Сервер не ответил вовремя. Попробуйте ещё раз.',
      );
    }

    final decoded = _decodeBody(response);
    if (response.statusCode == expectedStatus) return decoded;
    throw _mapError(response.statusCode, decoded);
  }

  Map<String, dynamic> _decodeBody(http.Response response) {
    if (response.bodyBytes.isEmpty) return const {};
    try {
      final decoded = jsonDecode(utf8.decode(response.bodyBytes));
      return decoded is Map<String, dynamic> ? decoded : const {};
    } on FormatException {
      return const {};
    }
  }

  /// Преобразует HTTP-ошибку в понятное пользователю исключение.
  ApiException _mapError(int statusCode, Map<String, dynamic> body) {
    switch (statusCode) {
      case 401:
        return const AuthException(
          'Неверный email или пароль.',
          statusCode: 401,
        );
      case 409:
        return const AuthException(
          'Пользователь с таким email уже зарегистрирован. Выполните вход.',
          statusCode: 409,
        );
      case 422:
        return const AuthException(
          'Проверьте email и пароль (не короче 8 символов).',
          statusCode: 422,
        );
      default:
        return ApiRequestException(
          _detail(body) ?? 'Ошибка сервера ($statusCode). Попробуйте позже.',
          statusCode: statusCode,
        );
    }
  }

  /// Извлекает `detail` из ответа FastAPI (строка или список ошибок).
  String? _detail(Map<String, dynamic> body) {
    final detail = body['detail'];
    if (detail is String && detail.isNotEmpty) return detail;
    if (detail is List && detail.isNotEmpty) {
      final first = detail.first;
      if (first is Map && first['msg'] is String) {
        return first['msg'] as String;
      }
    }
    return null;
  }
}
