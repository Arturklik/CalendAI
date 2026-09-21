// Smoke-тесты приложения: календарь отрисовывается на реальном
// (FFI) SQLite-движке, без обращений к сети.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:path/path.dart' as p;
import 'package:shared_preferences/shared_preferences.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

import 'package:calendai/database/app_database.dart';
import 'package:calendai/main.dart';

void main() {
  setUpAll(() {
    sqfliteFfiInit();
    databaseFactory = databaseFactoryFfi;
    // Изоляция от других файлов тестов, идущих параллельно.
    AppDatabase.databaseName = 'calendai_widget_test.db';
  });

  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  tearDown(() async {
    await AppDatabase.instance.close();
    final dbPath = p.join(
      await databaseFactory.getDatabasesPath(),
      AppDatabase.databaseName,
    );
    await databaseFactory.deleteDatabase(dbPath);
  });

  /// Прокачивает кадры с реальными задержками (для ffi-изолята SQLite)
  /// и продвигает анимации (pump с длительностью), чтобы тапы не
  /// «промахивались» мимо ещё анимируемых меню/диалогов.
  Future<void> settle(WidgetTester tester) async {
    for (var i = 0; i < 20; i++) {
      await Future<void>.delayed(const Duration(milliseconds: 20));
      await tester.pump(const Duration(milliseconds: 50));
    }
  }

  testWidgets('гость видит календарь и кнопку входа',
      (WidgetTester tester) async {
    // Телефонный размер экрана: на 800x600 месячная сетка не помещается.
    await tester.binding.setSurfaceSize(const Size(390, 844));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    // runAsync — реальный асинхронный I/O SQLite в обход fake-async.
    await tester.runAsync(() async {
      await tester.pumpWidget(const CalendAIApp());
      // Барьерный запрос: очередь SQLite сериализована (FIFO), поэтому
      // его завершение гарантирует, что initState-загрузка месяца тоже
      // завершилась и БД не закроется «под» висящим запросом.
      await AppDatabase.instance.getEventsInRange(
        DateTime(2000),
        DateTime(2100),
      );
      await settle(tester);
    });
    await tester.pump();

    expect(find.text('CalendAI'), findsOneWidget);
    expect(find.text('На этот день занятий нет'), findsOneWidget);
    expect(find.byTooltip('Синхронизировать'), findsOneWidget);
    expect(find.byTooltip('Добавить занятие'), findsOneWidget);
    // Неавторизованный пользователь: кнопка входа, без меню профиля.
    expect(find.byTooltip('Войти'), findsOneWidget);
    expect(find.byTooltip('Аккаунт'), findsNothing);
    // Заголовок дня: выбран сегодняшний день.
    expect(find.textContaining('Сегодня, '), findsOneWidget);
  });

  testWidgets('авторизованный пользователь видит профиль и может выйти',
      (WidgetTester tester) async {
    SharedPreferences.setMockInitialValues({
      'auth_token': 'test-token',
      'auth_email': 'student@example.com',
    });
    await tester.binding.setSurfaceSize(const Size(390, 844));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.runAsync(() async {
      await tester.pumpWidget(const CalendAIApp());
      await AppDatabase.instance.getEventsInRange(
        DateTime(2000),
        DateTime(2100),
      );
      await settle(tester);

      // Профиль авторизованного пользователя.
      expect(find.byTooltip('Аккаунт'), findsOneWidget);
      expect(find.byTooltip('Войти'), findsNothing);

      await tester.tap(find.byTooltip('Аккаунт'));
      await settle(tester);
      expect(find.text('student@example.com'), findsOneWidget);
      expect(find.text('Выйти из аккаунта'), findsOneWidget);

      // Выход: подтверждающий диалог с email.
      await tester.tap(find.text('Выйти из аккаунта'));
      await settle(tester);
      expect(
        find.text('Выйти из аккаунта student@example.com?'),
        findsOneWidget,
      );

      await tester.tap(find.text('Выйти'));
      await settle(tester);
    });
    await tester.pump();

    // После выхода — снова гость + информативный SnackBar.
    expect(find.byTooltip('Войти'), findsOneWidget);
    expect(find.text('Вы вышли из аккаунта'), findsOneWidget);
    final prefs = await SharedPreferences.getInstance();
    expect(prefs.getString('auth_token'), isNull);
  });
}
