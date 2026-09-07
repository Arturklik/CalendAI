import '../models/event.dart';
import 'sync_repository.dart';

/// Заглушка синхронизации до готовности backend API (AGENTS.md).
/// Эмулирует сетевую задержку и возвращает два тестовых занятия.
class MockSyncRepository implements SyncRepository {
  const MockSyncRepository();

  static const Duration networkDelay = Duration(milliseconds: 800);

  /// Фиксированные id, чтобы повторные синхронизации обновляли
  /// те же записи (upsert), а не плодили дубликаты.
  static const String _lectureId = 'a1b2c3d4-0000-4000-8000-000000000001';
  static const String _labId = 'a1b2c3d4-0000-4000-8000-000000000002';

  @override
  Future<List<Event>> sync(DateTime lastSync, List<Event> localChanges) async {
    await Future<void>.delayed(networkDelay);

    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);

    return [
      Event(
        id: _lectureId,
        title: 'Лекция: Математический анализ',
        eventType: EventType.lecture,
        startTime: today.add(const Duration(hours: 9)),
        endTime: today.add(const Duration(hours: 10, minutes: 35)),
        location: 'Ауд. 214',
        teacher: 'Иванов А.П.',
        recurrenceRule: 'FREQ=WEEKLY;INTERVAL=1',
      ),
      Event(
        id: _labId,
        title: 'Лабораторная: Физика',
        eventType: EventType.lab,
        startTime: today.add(const Duration(days: 1, hours: 10, minutes: 40)),
        endTime: today.add(const Duration(days: 1, hours: 12, minutes: 15)),
        location: 'Лаб. 305',
        teacher: 'Петрова М.С.',
        recurrenceRule: 'FREQ=WEEKLY;INTERVAL=2',
      ),
    ];
  }
}
