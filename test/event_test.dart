import 'package:calendai/models/event.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  final start = DateTime.parse('2026-09-08T09:00:00+07:00');
  final end = DateTime.parse('2026-09-08T10:35:00+07:00');

  Event sample() => Event(
        title: 'Лекция: Математический анализ',
        eventType: EventType.lecture,
        startTime: start,
        endTime: end,
        location: 'Ауд. 214',
        teacher: 'Иванов А.П.',
      );

  group('validation', () {
    test('валидное событие создаётся, id генерируется как UUIDv4', () {
      final event = sample();
      expect(event.id, isNotEmpty);
      expect(
        RegExp(
          r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$',
        ).hasMatch(event.id),
        isTrue,
      );
      expect(event.isDeleted, isFalse);
      expect(event.updatedAt.isUtc, isTrue);
    });

    test('пустое название запрещено', () {
      expect(
        () => Event(
          title: '  ',
          eventType: EventType.other,
          startTime: start,
          endTime: end,
        ),
        throwsArgumentError,
      );
    });

    test('end_time должен быть позже start_time', () {
      expect(
        () => Event(
          title: 'X',
          eventType: EventType.other,
          startTime: end,
          endTime: start,
        ),
        throwsArgumentError,
      );
    });
  });

  group('toJson/fromJson', () {
    test('round-trip сохраняет все поля канонического контракта', () {
      final original = Event(
        title: 'Лабораторная: Физика',
        eventType: EventType.lab,
        startTime: start,
        endTime: end,
        location: 'Лаб. 305',
        teacher: 'Петрова М.С.',
        description: 'Принести отчёт',
        recurrenceRule: 'FREQ=WEEKLY;INTERVAL=2',
        updatedAt: DateTime.utc(2026, 9, 5, 12),
      );

      final restored = Event.fromJson(original.toJson());

      expect(restored.id, original.id);
      expect(restored.title, original.title);
      expect(restored.eventType, EventType.lab);
      expect(restored.startTime.toUtc(), start.toUtc());
      expect(restored.endTime.toUtc(), end.toUtc());
      expect(restored.location, 'Лаб. 305');
      expect(restored.teacher, 'Петрова М.С.');
      expect(restored.description, 'Принести отчёт');
      expect(restored.recurrenceRule, 'FREQ=WEEKLY;INTERVAL=2');
      expect(restored.updatedAt, DateTime.utc(2026, 9, 5, 12));
      expect(restored.isDeleted, isFalse);
    });

    test('ключи JSON соответствуют схеме AGENTS.md', () {
      final json = sample().toJson();
      expect(json.keys, containsAll([
        'id', 'title', 'event_type', 'start_time', 'end_time',
        'location', 'teacher', 'description', 'recurrence_rule',
        'updated_at', 'is_deleted',
      ]));
      expect(json['event_type'], 'lecture');
      expect(json['is_deleted'], isA<bool>());
    });

    test('fromJson толерантен к is_deleted в виде int из SQLite', () {
      final json = sample().toJson()..['is_deleted'] = 1;
      expect(Event.fromJson(json).isDeleted, isTrue);
      json['is_deleted'] = 0;
      expect(Event.fromJson(json).isDeleted, isFalse);
    });

    test('неизвестный event_type сводится к other', () {
      final json = sample().toJson()..['event_type'] = 'webinar';
      expect(Event.fromJson(json).eventType, EventType.other);
    });

    test('битая дата вызывает FormatException', () {
      final json = sample().toJson()..['start_time'] = 'не дата';
      expect(() => Event.fromJson(json), throwsFormatException);
    });
  });

  group('copyWith', () {
    test('обновляет указанные поля и сохраняет остальные', () {
      final event = sample();
      final copy = event.copyWith(title: 'Новое название');
      expect(copy.title, 'Новое название');
      expect(copy.id, event.id);
      expect(copy.location, event.location);
      expect(copy.updatedAt, event.updatedAt);
    });

    test('явный null очищает nullable-поле, пропуск — сохраняет', () {
      final event = sample();
      final cleared = event.copyWith(location: null);
      expect(cleared.location, isNull);
      final kept = event.copyWith(description: 'Заметка');
      expect(kept.location, event.location);
      expect(kept.description, 'Заметка');
    });

    test('copyWith проходит валидацию при смене времён', () {
      final event = sample();
      expect(
        () => event.copyWith(startTime: end),
        throwsArgumentError,
      );
    });
  });

  group('EventType.fromString', () {
    test('все канонические значения', () {
      for (final name in ['lecture', 'practice', 'lab', 'exam', 'other']) {
        expect(EventType.fromString(name).name, name);
      }
    });
    test('null и мусор -> other', () {
      expect(EventType.fromString(null), EventType.other);
      expect(EventType.fromString('???'), EventType.other);
    });
  });
}
