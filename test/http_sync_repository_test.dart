import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:calendai/models/event.dart';
import 'package:calendai/repositories/http_sync_repository.dart';
import 'package:calendai/services/api_exceptions.dart';
import 'package:calendai/services/auth_storage.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  const baseUrl = 'http://test.local/api/v1';

  final start = DateTime.parse('2026-09-08T09:00:00+07:00');
  final end = DateTime.parse('2026-09-08T10:35:00+07:00');

  Event sampleEvent() => Event(
        id: 'a1b2c3d4-0000-4000-8000-000000000001',
        title: 'Лекция: Математический анализ',
        eventType: EventType.lecture,
        startTime: start,
        endTime: end,
        location: 'Ауд. 214',
        updatedAt: DateTime.utc(2026, 9, 8, 2),
      );

  Map<String, dynamic> serverEventJson() => {
        'id': 'b2c3d4e5-0000-4000-8000-000000000002',
        'title': 'Лабораторная: Физика',
        'event_type': 'lab',
        'start_time': '2026-09-09T10:50:00+07:00',
        'end_time': '2026-09-09T12:25:00+07:00',
        'location': 'Лаб. 305',
        'teacher': null,
        'description': null,
        'recurrence_rule': null,
        'updated_at': '2026-09-19T09:00:00Z',
        'is_deleted': false,
      };

  AuthStorage storageWith(http.Client client) =>
      AuthStorage(client: client, baseUrl: baseUrl);

  setUp(() {
    SharedPreferences.setMockInitialValues({'auth_token': 'jwt-token'});
  });

  test('отправляет client_changes с Bearer-токеном и парсит server_changes',
      () async {
    late http.Request captured;
    final client = MockClient((request) async {
      captured = request;
      return http.Response(
        jsonEncode({
          'sync_timestamp': '2026-09-19T10:00:00Z',
          'server_changes': [serverEventJson()],
        }),
        200,
        headers: {'content-type': 'application/json; charset=utf-8'},
      );
    });
    final repository = HttpSyncRepository(
      client: client,
      baseUrl: baseUrl,
      authStorage: storageWith(client),
    );

    final result = await repository.sync(
      DateTime.utc(2026, 9, 8, 12),
      [sampleEvent()],
    );

    expect(captured.method, 'POST');
    expect(captured.url.toString(), '$baseUrl/sync');
    expect(captured.headers['Authorization'], 'Bearer jwt-token');
    expect(captured.headers['Content-Type'], contains('application/json'));

    final body = jsonDecode(captured.body) as Map<String, dynamic>;
    expect(body['last_sync_timestamp'], '2026-09-08T12:00:00.000Z');
    final changes = body['client_changes'] as List<dynamic>;
    expect(changes, hasLength(1));
    final sent = changes.single as Map<String, dynamic>;
    expect(sent['id'], 'a1b2c3d4-0000-4000-8000-000000000001');
    expect(sent['event_type'], 'lecture');
    expect(sent['updated_at'], '2026-09-08T02:00:00.000Z');
    expect(sent['is_deleted'], isFalse);

    expect(result, hasLength(1));
    expect(result.single.title, 'Лабораторная: Физика');
    expect(result.single.eventType, EventType.lab);
    expect(result.single.location, 'Лаб. 305');
    expect(result.single.updatedAt, DateTime.utc(2026, 9, 19, 9));
  });

  test('пустой server_changes -> пустой список', () async {
    final client = MockClient(
      (_) async => http.Response(
        '{"sync_timestamp":"2026-09-19T10:00:00Z","server_changes":[]}',
        200,
      ),
    );
    final repository = HttpSyncRepository(
      client: client,
      baseUrl: baseUrl,
      authStorage: storageWith(client),
    );

    final result = await repository.sync(DateTime.utc(2026, 9, 8), const []);
    expect(result, isEmpty);
  });

  test('отсутствие токена -> UnauthorizedException без сетевого запроса',
      () async {
    SharedPreferences.setMockInitialValues({});
    var called = false;
    final client = MockClient((_) async {
      called = true;
      return http.Response('{}', 200);
    });
    final repository = HttpSyncRepository(
      client: client,
      baseUrl: baseUrl,
      authStorage: storageWith(client),
    );

    await expectLater(
      repository.sync(DateTime.utc(2026, 9, 8), const []),
      throwsA(isA<UnauthorizedException>()),
    );
    expect(called, isFalse);
  });

  test('401 -> UnauthorizedException и токен сбрасывается', () async {
    final client = MockClient(
      (_) async => http.Response('{"detail":"Unauthorized"}', 401),
    );
    final authStorage = storageWith(client);
    final repository = HttpSyncRepository(
      client: client,
      baseUrl: baseUrl,
      authStorage: authStorage,
    );

    await expectLater(
      repository.sync(DateTime.utc(2026, 9, 8), const []),
      throwsA(isA<UnauthorizedException>()),
    );
    expect(await authStorage.token, isNull);
  });

  test('SocketException -> NetworkException', () async {
    final client = MockClient(
      (_) async => throw const SocketException('network is unreachable'),
    );
    final repository = HttpSyncRepository(
      client: client,
      baseUrl: baseUrl,
      authStorage: storageWith(client),
    );

    await expectLater(
      repository.sync(DateTime.utc(2026, 9, 8), const []),
      throwsA(
        isA<NetworkException>().having(
          (e) => e.message,
          'message',
          contains('Не удалось подключиться'),
        ),
      ),
    );
  });

  test('5xx -> ApiRequestException с кодом ответа', () async {
    final client = MockClient((_) async => http.Response('oops', 500));
    final repository = HttpSyncRepository(
      client: client,
      baseUrl: baseUrl,
      authStorage: storageWith(client),
    );

    await expectLater(
      repository.sync(DateTime.utc(2026, 9, 8), const []),
      throwsA(
        isA<ApiRequestException>()
            .having((e) => e.statusCode, 'statusCode', 500),
      ),
    );
  });

  test('некорректный JSON -> ApiRequestException без падения', () async {
    final client = MockClient((_) async => http.Response('not-json', 200));
    final repository = HttpSyncRepository(
      client: client,
      baseUrl: baseUrl,
      authStorage: storageWith(client),
    );

    await expectLater(
      repository.sync(DateTime.utc(2026, 9, 8), const []),
      throwsA(isA<ApiRequestException>()),
    );
  });
}
