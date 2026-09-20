import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:calendai/services/auth_storage.dart';
import 'package:calendai/widgets/auth_dialog.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  const baseUrl = 'http://test.local/api/v1';

  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  /// Открывает диалог кнопкой и возвращает Future с результатом.
  Future<Future<bool?>> openDialog(
    WidgetTester tester,
    AuthStorage storage,
  ) async {
    // Телефонная ширина: ловим переполнение вёрстки диалога.
    await tester.binding.setSurfaceSize(const Size(390, 844));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    Future<bool>? resultFuture;
    await tester.pumpWidget(
      MaterialApp(
        home: Builder(
          builder: (context) => Scaffold(
            body: Center(
              child: ElevatedButton(
                onPressed: () {
                  resultFuture = AuthDialog.show(context, storage);
                },
                child: const Text('Открыть'),
              ),
            ),
          ),
        ),
      ),
    );
    await tester.tap(find.text('Открыть'));
    await tester.pumpAndSettle();
    return resultFuture!;
  }

  testWidgets('валидация: пустые поля не отправляются на сервер',
      (tester) async {
    var networkCalled = false;
    final client = MockClient((_) async {
      networkCalled = true;
      return http.Response('{}', 200);
    });
    final storage = AuthStorage(client: client, baseUrl: baseUrl);

    await openDialog(tester, storage);
    expect(find.text('Вход в CalendAI'), findsOneWidget);

    await tester.tap(find.text('Войти'));
    await tester.pumpAndSettle();

    expect(find.text('Введите email'), findsOneWidget);
    expect(find.text('Введите пароль'), findsOneWidget);
    expect(networkCalled, isFalse);

    await tester.tap(find.text('Отмена'));
    await tester.pumpAndSettle();
  });

  testWidgets('успешный вход закрывает диалог с результатом true',
      (tester) async {
    final client = MockClient(
      (_) async => http.Response(
        jsonEncode({'access_token': 'jwt-x', 'token_type': 'bearer'}),
        200,
      ),
    );
    final storage = AuthStorage(client: client, baseUrl: baseUrl);

    final resultFuture = await openDialog(tester, storage);
    await tester.enterText(
      find.byType(TextFormField).first,
      'user@example.com',
    );
    await tester.enterText(
      find.byType(TextFormField).last,
      'password123',
    );
    await tester.tap(find.text('Войти'));
    await tester.pumpAndSettle();

    expect(await resultFuture, isTrue);
    expect(find.text('Вход в CalendAI'), findsNothing);
    expect(await storage.token, 'jwt-x');
  });

  testWidgets('неверные данные показывают ошибку внутри диалога',
      (tester) async {
    final client = MockClient(
      (_) async => http.Response('{"detail":"Unauthorized"}', 401),
    );
    final storage = AuthStorage(client: client, baseUrl: baseUrl);

    final resultFuture = await openDialog(tester, storage);
    await tester.enterText(
      find.byType(TextFormField).first,
      'user@example.com',
    );
    await tester.enterText(
      find.byType(TextFormField).last,
      'wrong-pass',
    );
    await tester.tap(find.text('Войти'));
    await tester.pumpAndSettle();

    expect(find.text('Неверный email или пароль.'), findsOneWidget);
    expect(find.text('Вход в CalendAI'), findsOneWidget);

    await tester.tap(find.text('Отмена'));
    await tester.pumpAndSettle();
    expect(await resultFuture, isFalse);
  });

  testWidgets('режим регистрации требует пароль не короче 8 символов',
      (tester) async {
    final client = MockClient((_) async => http.Response('{}', 201));
    final storage = AuthStorage(client: client, baseUrl: baseUrl);

    await openDialog(tester, storage);
    await tester.tap(find.text('Создать аккаунт'));
    await tester.pumpAndSettle();
    expect(find.text('Регистрация в CalendAI'), findsOneWidget);

    await tester.enterText(
      find.byType(TextFormField).first,
      'new@example.com',
    );
    await tester.enterText(find.byType(TextFormField).last, 'short');
    await tester.tap(find.text('Зарегистрироваться'));
    await tester.pumpAndSettle();

    expect(
      find.text('Пароль должен быть не короче 8 символов'),
      findsOneWidget,
    );

    await tester.tap(find.text('Отмена'));
    await tester.pumpAndSettle();
  });
}
