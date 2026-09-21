import '../models/event.dart';

/// События, попадающие на локальный календарный день [day],
/// отсортированные по времени начала.
///
/// Сравнение ведётся в локальной таймзоне устройства (`toLocal()`),
/// поэтому занятия не «сдвигаются» на соседнюю дату из-за UTC-хранения.
/// Границы дня строятся конструктором (day + 1) — это корректно
/// учитывает переходы на летнее время.
List<Event> eventsOnDay(Iterable<Event> events, DateTime day) {
  final dayStart = DateTime(day.year, day.month, day.day);
  final dayEnd = DateTime(day.year, day.month, day.day + 1);
  final result = events
      .where(
        (event) =>
            event.startTime.toLocal().isBefore(dayEnd) &&
            event.endTime.toLocal().isAfter(dayStart),
      )
      .toList();
  result.sort((a, b) => a.startTime.compareTo(b.startTime));
  return result;
}
