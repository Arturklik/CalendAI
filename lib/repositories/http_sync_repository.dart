import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;

import '../models/event.dart';
import '../services/api_config.dart';
import '../services/api_exceptions.dart';
import '../services/auth_storage.dart';
import 'sync_repository.dart';

/// Реальная реализация [SyncRepository] поверх backend API
/// (`POST /api/v1/sync`, дифференциальная синхронизация Last-Write-Wins).
///
/// Отправляет локальные изменения [localChanges] с меткой [lastSync]
/// и возвращает события, изменённые на сервере (включая soft-deleted),
/// которые клиент применяет через upsert.
class HttpSyncRepository implements SyncRepository {
  HttpSyncRepository({
    AuthStorage? authStorage,
    http.Client? client,
    String? baseUrl,
  })  : _authStorage = authStorage ?? AuthStorage(),
        _client = client ?? http.Client(),
        _baseUrl = baseUrl ?? ApiConfig.baseUrl;

  static const Duration _timeout = Duration(seconds: 30);

  final AuthStorage _authStorage;
  final http.Client _client;
  final String _baseUrl;

  @override
  Future<List<Event>> sync(
    DateTime lastSync,
    List<Event> localChanges,
  ) async {
    final token = await _authStorage.token;
    if (token == null) {
      throw const UnauthorizedException(
        'Для синхронизации необходимо войти в аккаунт.',
      );
    }

    final payload = <String, dynamic>{
      'last_sync_timestamp': lastSync.toUtc().toIso8601String(),
      'client_changes': localChanges.map((event) => event.toJson()).toList(),
    };

    http.Response response;
    try {
      response = await _client
          .post(
            Uri.parse('$_baseUrl/sync'),
            headers: {
              'Content-Type': 'application/json; charset=utf-8',
              'Authorization': 'Bearer $token',
            },
            body: jsonEncode(payload),
          )
          .timeout(_timeout);
    } on SocketException {
      throw const NetworkException();
    } on http.ClientException {
      throw const NetworkException();
    } on TimeoutException {
      throw const NetworkException(
        'Сервер не ответил вовремя. Проверьте соединение и повторите.',
      );
    }

    if (response.statusCode == 401) {
      // Токен истёк или отозван — сбрасываем, чтобы UI запросил вход.
      await _authStorage.clear();
      throw const UnauthorizedException();
    }

    if (response.statusCode != 200) {
      throw ApiRequestException(
        'Ошибка синхронизации (${response.statusCode}). Попробуйте позже.',
        statusCode: response.statusCode,
      );
    }

    return _parseServerChanges(response.bodyBytes);
  }

  /// Разбирает `server_changes` ответа в список [Event].
  List<Event> _parseServerChanges(List<int> bodyBytes) {
    try {
      final decoded = jsonDecode(utf8.decode(bodyBytes));
      if (decoded is! Map<String, dynamic>) {
        throw const FormatException('Ожидался JSON-объект');
      }
      final changes = decoded['server_changes'];
      if (changes == null) return const [];
      if (changes is! List) {
        throw const FormatException('server_changes должен быть списком');
      }
      return changes
          .map((item) => Event.fromJson(item as Map<String, dynamic>))
          .toList();
    } on FormatException {
      throw const ApiRequestException(
        'Сервер вернул некорректный ответ синхронизации.',
        statusCode: 200,
      );
    } on TypeError {
      throw const ApiRequestException(
        'Сервер вернул некорректный ответ синхронизации.',
        statusCode: 200,
      );
    }
  }
}
