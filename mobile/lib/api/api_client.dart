import 'dart:convert';

import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import 'api_config.dart';

class ApiException implements Exception {
  ApiException(this.message, {this.statusCode});

  final String message;
  final int? statusCode;

  @override
  String toString() => message;
}

/// HTTP-клиент к FastAPI (`/api/v1`). Хранит JWT в SharedPreferences.
class ApiClient {
  ApiClient({http.Client? httpClient}) : _http = httpClient ?? http.Client();

  static const _tokenKey = 'access_token';

  final http.Client _http;
  String? _token;

  Future<void> loadToken() async {
    final prefs = await SharedPreferences.getInstance();
    _token = prefs.getString(_tokenKey);
  }

  bool get hasToken => _token != null && _token!.isNotEmpty;

  Future<void> _saveToken(String token) async {
    _token = token;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_tokenKey, token);
  }

  Future<void> logout() async {
    _token = null;
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_tokenKey);
  }

  Future<void> register({
    required String email,
    required String password,
    String? displayName,
  }) async {
    final data = await _post(
      '/api/v1/auth/register',
      {
        'email': email,
        'password': password,
        if (displayName != null) 'display_name': displayName,
      },
      auth: false,
    );
    await _saveToken(data['access_token'] as String);
  }

  Future<void> login({required String email, required String password}) async {
    final data = await _post(
      '/api/v1/auth/login',
      {'email': email, 'password': password},
      auth: false,
    );
    await _saveToken(data['access_token'] as String);
  }

  Future<Map<String, dynamic>> post(String path, Map<String, dynamic> body) {
    return _post(path, body);
  }

  Future<Map<String, dynamic>> _post(
    String path,
    Map<String, dynamic> body, {
    bool auth = true,
  }) async {
    final uri = Uri.parse('${ApiConfig.baseUrl}$path');
    final headers = {
      'Content-Type': 'application/json',
      if (auth && _token != null) 'Authorization': 'Bearer $_token',
    };
    final response = await _http.post(
      uri,
      headers: headers,
      body: jsonEncode(body),
    );
    if (response.statusCode >= 400) {
      throw ApiException(
        _extractDetail(response.body) ?? 'HTTP ${response.statusCode}',
        statusCode: response.statusCode,
      );
    }
    if (response.body.isEmpty) return {};
    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  String? _extractDetail(String body) {
    try {
      final decoded = jsonDecode(body);
      if (decoded is Map && decoded['detail'] is String) {
        return decoded['detail'] as String;
      }
    } catch (_) {}
    return null;
  }
}
