import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:path/path.dart' as p;
import 'package:shared_preferences/shared_preferences.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

import 'package:calendai/database/app_database.dart';
import 'package:calendai/models/event.dart';
import 'package:calendai/repositories/sync_repository.dart';
import 'package:calendai/screens/calendar_screen.dart';
import 'package:calendai/services/app_logger.dart';
import 'package:calendai/services/auth_storage.dart';
import 'package:calendai/utils/day_events.dart';
import 'package:calendai/widgets/event_card.dart';

class _FailingSyncRepository implements SyncRepository {
  _FailingSyncRepository(this.error);

  final Object error;

  @override
  Future<List<Event>> sync(DateTime lastSync, List<Event> localChanges) async {
    throw error;
  }
}

class _DeferredSyncRepository implements SyncRepository {
  final Completer<void> started = Completer<void>();
  final Completer<List<Event>> response = Completer<List<Event>>();

  @override
  Future<List<Event>> sync(DateTime lastSync, List<Event> localChanges) {
    if (!started.isCompleted) started.complete();
    return response.future;
  }
}

Event _event({
  String title = 'Test event',
  DateTime? startTime,
  DateTime? endTime,
  String? location,
  String? teacher,
}) {
  final start = startTime ?? DateTime(2026, 9, 20, 9);
  return Event(
    title: title,
    eventType: EventType.lecture,
    startTime: start,
    endTime: endTime ?? start.add(const Duration(minutes: 90)),
    location: location,
    teacher: teacher,
  );
}

Future<void> _settle(WidgetTester tester) async {
  for (var i = 0; i < 20; i++) {
    await Future<void>.delayed(const Duration(milliseconds: 20));
    await tester.pump(const Duration(milliseconds: 50));
  }
}

Future<void> _pumpCalendar(
  WidgetTester tester, {
  required SyncRepository repository,
}) async {
  await tester.pumpWidget(
    MaterialApp(
      home: CalendarScreen(
        syncRepository: repository,
        authStorage: AuthStorage(),
      ),
    ),
  );
  // Wait until the initial SQLite query has drained from the FFI queue.
  await AppDatabase.instance.getEventsInRange(DateTime(2000), DateTime(2100));
  await _settle(tester);
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUpAll(() {
    sqfliteFfiInit();
    databaseFactory = databaseFactoryFfi;
    AppDatabase.databaseName = 'calendai_stress_edge_cases.db';
  });

  setUp(() {
    SharedPreferences.setMockInitialValues({
      'auth_token': 'stress-test-token',
      'auth_email': 'stress@example.com',
    });
    AppLogger.instance.clear();
  });

  tearDown(() async {
    await AppDatabase.instance.close();
    final dbPath = p.join(
      await databaseFactory.getDatabasesPath(),
      AppDatabase.databaseName,
    );
    await databaseFactory.deleteDatabase(dbPath);
  });

  testWidgets('network timeout shows SnackBar and resets sync indicator',
      (tester) async {
    await tester.binding.setSurfaceSize(const Size(390, 844));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.runAsync(() async {
      await _pumpCalendar(
        tester,
        repository: _FailingSyncRepository(
          TimeoutException('simulated network timeout'),
        ),
      );

      await tester.tap(find.byTooltip('Синхронизировать'));
      await _settle(tester);
    });
    await tester.pump();

    expect(find.text('Нет связи с сервером. Проверьте подключение'),
        findsOneWidget);
    expect(find.byTooltip('Синхронизировать'), findsOneWidget);
    expect(find.byType(CircularProgressIndicator), findsNothing);
    expect(
      AppLogger.instance.entries
          .any((entry) => entry.level == AppLogLevel.error),
      isTrue,
    );
  });

  testWidgets('300-char title and 100-char metadata do not overflow EventCard',
      (tester) async {
    await tester.binding.setSurfaceSize(const Size(320, 568));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final longTitle = 'Д'.padRight(300, 'и');
    final longLocation = 'К'.padRight(100, 'а');
    final longTeacher = 'П'.padRight(100, 'р');

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: ListView(
            padding: const EdgeInsets.all(8),
            children: [
              EventCard(
                event: _event(
                  title: longTitle,
                  location: longLocation,
                  teacher: longTeacher,
                ),
                onTap: () {},
              ),
            ],
          ),
        ),
      ),
    );

    expect(find.text(longTitle), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  test('event spanning midnight is included on both local calendar days', () {
    final event = _event(
      startTime: DateTime(2026, 9, 20, 23, 50),
      endTime: DateTime(2026, 9, 21, 1, 20),
    );

    expect(eventsOnDay([event], DateTime(2026, 9, 20)), [event]);
    expect(eventsOnDay([event], DateTime(2026, 9, 21)), [event]);
  });

  testWidgets('sign-out during sync discards the stale response and clears DB',
      (tester) async {
    await tester.binding.setSurfaceSize(const Size(390, 844));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final repository = _DeferredSyncRepository();
    final localEvent = _event(title: 'Local event');
    final staleRemoteEvent = _event(title: 'Stale response event');

    await tester.runAsync(() async {
      await AppDatabase.instance.upsertEvent(localEvent);
      await _pumpCalendar(tester, repository: repository);

      await tester.tap(find.byTooltip('Синхронизировать'));
      await _settle(tester);
      expect(
        repository.started.isCompleted,
        isTrue,
        reason: AppLogger.instance.export(),
      );

      // Sign out while the repository request is still pending.
      await tester.tap(find.byTooltip('Аккаунт'));
      await _settle(tester);
      await tester.tap(find.text('Выйти из аккаунта'));
      await _settle(tester);
      await tester.tap(find.text('Выйти'));
      await _settle(tester);

      // Complete the old account's request after sign-out. Its response must
      // be discarded instead of repopulating the cleared local database.
      repository.response.complete([staleRemoteEvent]);
      await _settle(tester);

      final remaining = await AppDatabase.instance.getEventsInRange(
        DateTime(2000),
        DateTime(2100),
      );
      expect(remaining, isEmpty);
    });
    await tester.pump();

    expect(find.byTooltip('Войти'), findsOneWidget);
    expect(find.text('Вы вышли из аккаунта'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  test('AppLogger keeps only the latest 20 entries', () {
    final logger = AppLogger.instance;
    logger.clear();

    for (var i = 0; i < 25; i++) {
      logger.info('entry-$i');
    }

    expect(logger.entries, hasLength(AppLogger.maxEntries));
    expect(logger.export(), contains('entry-24'));
    expect(logger.export(), isNot(contains('entry-4')));
  });
}
