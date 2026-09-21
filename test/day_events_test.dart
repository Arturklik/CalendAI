// Тесты фильтрации событий по локальному календарному дню (таймзоны).

import 'package:flutter_test/flutter_test.dart';

import 'package:calendai/models/event.dart';
import 'package:calendai/utils/day_events.dart';

void main() {
  Event eventAt(DateTime start, DateTime end, {String title = 'Пара'}) => Event(
        title: title,
        eventType: EventType.lecture,
        startTime: start,
        endTime: end,
      );

  test('событие попадает на свой локальный день и не попадает на соседние', () {
    // Вечер по UTC может быть уже следующим днём в локальной таймзоне —
    // ожидания вычисляются от локальной даты, поэтому тест не зависит от TZ.
    final startUtc = DateTime.utc(2026, 9, 7, 20, 0);
    final endUtc = DateTime.utc(2026, 9, 7, 21, 35);
    final localStart = startUtc.toLocal();
    final localDay = DateTime(localStart.year, localStart.month, localStart.day);

    final events = [eventAt(startUtc, endUtc)];

    expect(eventsOnDay(events, localDay), hasLength(1));
    expect(
      eventsOnDay(events, localDay.subtract(const Duration(days: 1))),
      isEmpty,
    );
    expect(
      eventsOnDay(events, localDay.add(const Duration(days: 1))),
      isEmpty,
    );
  });

  test('возвращает только события выбранного дня и сортирует по времени', () {
    final day = DateTime(2026, 9, 8);
    final events = [
      eventAt(
        DateTime(2026, 9, 8, 13, 0),
        DateTime(2026, 9, 8, 14, 35),
        title: 'Вторая пара',
      ),
      eventAt(
        DateTime(2026, 9, 8, 9, 0),
        DateTime(2026, 9, 8, 10, 35),
        title: 'Первая пара',
      ),
      eventAt(
        DateTime(2026, 9, 9, 9, 0),
        DateTime(2026, 9, 9, 10, 35),
        title: 'Завтра',
      ),
    ];

    final result = eventsOnDay(events, day);
    expect(result.map((e) => e.title), ['Первая пара', 'Вторая пара']);
  });

  test('событие, пересекающее полночь, видно в обоих днях', () {
    final events = [
      eventAt(
        DateTime(2026, 9, 8, 23, 30),
        DateTime(2026, 9, 9, 1, 0),
        title: 'Ночное',
      ),
    ];

    expect(eventsOnDay(events, DateTime(2026, 9, 8)), hasLength(1));
    expect(eventsOnDay(events, DateTime(2026, 9, 9)), hasLength(1));
  });

  test('пустой список и день без событий', () {
    expect(eventsOnDay(const [], DateTime(2026, 9, 8)), isEmpty);
    final events = [
      eventAt(
        DateTime(2026, 9, 8, 9, 0),
        DateTime(2026, 9, 8, 10, 35),
      ),
    ];
    expect(eventsOnDay(events, DateTime(2026, 9, 10)), isEmpty);
  });
}
