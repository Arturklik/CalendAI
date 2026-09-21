// Регрессионный тест: шторка «Новое занятие» должна корректно
// закрываться по тапу вне шторки (барьеру), без исключений фреймворка.

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
    AppDatabase.databaseName = 'calendai_create_event_test.db';
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

  Future<void> settle(WidgetTester tester) async {
    for (var i = 0; i < 20; i++) {
      await Future<void>.delayed(const Duration(milliseconds: 20));
      await tester.pump(const Duration(milliseconds: 50));
    }
  }

  testWidgets('закрытие шторки «Новое занятие» тапом по барьеру без ошибок',
      (WidgetTester tester) async {
    await tester.binding.setSurfaceSize(const Size(390, 844));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.runAsync(() async {
      await tester.pumpWidget(const CalendAIApp());
      await AppDatabase.instance.getEventsInRange(
        DateTime(2000),
        DateTime(2100),
      );
      await settle(tester);

      // Открываем форму создания занятия.
      await tester.tap(find.byTooltip('Добавить занятие'));
      await settle(tester);
      expect(find.textContaining('Новое занятие'), findsOneWidget);

      // Начинаем вводить название, как это сделал пользователь.
      await tester.enterText(find.byType(TextField).first, 'Моя заметка');
      await settle(tester);

      // Тап по экрану выше шторки — попытка вернуться назад.
      await tester.tapAt(const Offset(195, 120));
      await settle(tester);
    });
    await tester.pump();

    // Шторка закрылась, исключений нет.
    expect(find.textContaining('Новое занятие'), findsNothing);
    expect(tester.takeException(), isNull);
  });

  testWidgets('создание занятия через шторку сохраняет событие в списке',
      (WidgetTester tester) async {
    await tester.binding.setSurfaceSize(const Size(390, 844));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.runAsync(() async {
      await tester.pumpWidget(const CalendAIApp());
      await AppDatabase.instance.getEventsInRange(
        DateTime(2000),
        DateTime(2100),
      );
      await settle(tester);

      await tester.tap(find.byTooltip('Добавить занятие'));
      await settle(tester);

      await tester.enterText(
        find.byType(TextField).first,
        'Семинар по истории',
      );
      await settle(tester);

      await tester.tap(find.text('Сохранить'));
      await settle(tester);
    });
    await tester.pump();

    expect(find.text('Семинар по истории'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
