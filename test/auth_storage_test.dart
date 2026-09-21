import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:calendai/services/api_exceptions.dart';
import 'package:calendai/services/auth_storage.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  const baseUrl = 'http://test.local/api/v1';

  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  AuthStorage storageWith(http.Client client) =>
      AuthStorage(client: client, baseUrl: baseUrl);

  test('login сохраняет JWT и email', () async {
    late http.Request captured;
    final client = MockClient((request) async {
      captured = request;
      return http.Response(
        jsonEncode({'access_token': 'jwt-1', 'token_type': 'bearer'}),
        200,
      );
    });
    final storage = storageWith(client);

    await storage.login('Student@Example.com', 'password123');

    expect(captured.url.toString(), '$baseUrl/auth/login');
    final body = jsonDecode(captured.body) as Map<String, dynamic>;
    expect(body['email'], 'Student@Example.com');
    expect(body['password'], 'password123');

    expect(await storage.token, 'jwt-1');
    expect(await storage.isAuthenticated, isTrue);
    expect(await storage.userEmail, 'Student@Example.com');
  });

  test('login 401 -> AuthException', () async {
    final client = MockClient(
      (_) async => http.Response('{"detail":"Unauthorized"}', 401),
    );
    await expectLater(
      storageWith(client).login('user@example.com', 'wrong-pass'),
      throwsA(
        isA<AuthException>().having((e) => e.statusCode, 'statusCode', 401),
      ),
    );
  });

  test('login при недоступной сети -> NetworkException', () async {
    final client = MockClient(
      (_) async => throw const SocketException('no route to host'),
    );
    await expectLater(
      storageWith(client).login('user@example.com', 'password123'),
      throwsA(isA<NetworkException>()),
    );
  });

  test('register выполняет POST /auth/register, затем логин', () async {
    final paths = <String>[];
    final client = MockClient((request) async {
      paths.add(request.url.path);
      if (request.url.path.endsWith('/register')) {
        return http.Response(
          jsonEncode({
            'id': '6e583075-c8f0-49ab-903f-eab7175fb78f',
            'email': 'new@example.com',
            'telegram_id': null,
            'subscription_tier': 'free',
            'created_at': '2026-09-19T10:00:00Z',
          }),
          201,
        );
      }
      return http.Response(
        jsonEncode({'access_token': 'jwt-2', 'token_type': 'bearer'}),
        200,
      );
    });
    final storage = storageWith(client);

    await storage.register('new@example.com', 'password123');

    expect(paths, [
      '/api/v1/auth/register',
      '/api/v1/auth/login',
    ]);
    expect(await storage.token, 'jwt-2');
  });

  test('register 409 -> понятная AuthException', () async {
    final client = MockClient(
      (_) async => http.Response.bytes(
        utf8.encode('{"detail":"Пользователь с таким email уже существует"}'),
        409,
        headers: {'content-type': 'application/json; charset=utf-8'},
      ),
    );
    await expectLater(
      storageWith(client).register('dup@example.com', 'password123'),
      throwsA(
        isA<AuthException>().having((e) => e.statusCode, 'statusCode', 409),
      ),
    );
  });

  test('register 422 -> понятная AuthException', () async {
    final client = MockClient(
      (_) async => http.Response('{"detail":[]}', 422),
    );
    await expectLater(
      storageWith(client).register('bad', 'short'),
      throwsA(
        isA<AuthException>().having((e) => e.statusCode, 'statusCode', 422),
      ),
    );
  });

  test('clear удаляет сохранённый токен', () async {
    final client = MockClient(
      (_) async => http.Response(
        '{"access_token":"jwt-3","token_type":"bearer"}',
        200,
      ),
    );
    final storage = storageWith(client);
    await storage.login('user@example.com', 'password123');
    expect(await storage.token, isNotNull);

    await storage.clear();
    expect(await storage.token, isNull);
    expect(await storage.isAuthenticated, isFalse);
  });
}
