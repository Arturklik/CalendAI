/// Форматирование дат и времени для UI (локальная таймзона устройства).
library;

String _twoDigits(int value) => value.toString().padLeft(2, '0');

/// Время в локальной таймзоне, `HH:mm`.
String formatTime(DateTime dateTime) {
  final local = dateTime.toLocal();
  return '${_twoDigits(local.hour)}:${_twoDigits(local.minute)}';
}

/// Интервал `HH:mm – HH:mm` в локальной таймзоне.
String formatTimeRange(DateTime start, DateTime end) =>
    '${formatTime(start)} – ${formatTime(end)}';

/// Длительность занятия: `1 ч 35 мин`, `2 ч`, `45 мин`.
String formatDuration(Duration duration) {
  final totalMinutes = duration.inMinutes;
  final hours = totalMinutes ~/ 60;
  final minutes = totalMinutes % 60;
  if (hours == 0) return '$minutes мин';
  if (minutes == 0) return '$hours ч';
  return '$hours ч $minutes мин';
}
