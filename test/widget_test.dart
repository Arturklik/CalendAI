// Smoke-тест приложения: календарь отрисовывается на реальном
// (FFI) SQLite-движке, без обращений к сети.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:path/path.dart' as p;
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

import 'package:calendai/database/app_database.dart';
import 'package:calendai/main.dart';

void main() {
  setUpAll(() {
    sqfliteFfiInit();
    databaseFactory = databaseFactoryFfi;
  });

  tearDown(() async {
    await AppDatabase.instance.close();
    final dbPath = p.join(
      await databaseFactory.getDatabasesPath(),
      'calendai.db',
    );
    await databaseFactory.deleteDatabase(dbPath);
  });

  testWidgets('CalendAIApp отображает календарь на текущий месяц',
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
      await Future<void>.delayed(const Duration(milliseconds: 50));
    });
    await tester.pump();

    expect(find.text('CalendAI'), findsOneWidget);
    expect(find.text('Нет занятий на этот день'), findsOneWidget);
    expect(find.byTooltip('Синхронизировать'), findsOneWidget);
    expect(find.byTooltip('Добавить занятие'), findsOneWidget);
  });
}
