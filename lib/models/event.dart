import 'package:uuid/uuid.dart';

/// Тип события согласно каноническому контракту (AGENTS.md).
enum EventType {
  lecture,
  practice,
  lab,
  exam,
  other;

  /// Парсинг строки из JSON. Неизвестные значения безопасно
  /// сводятся к [EventType.other] (defensive typing).
  static EventType fromString(String? value) {
    for (final type in EventType.values) {
      if (type.name == value) return type;
    }
    return EventType.other;
  }
}

/// Календарное событие. Строго соответствует схеме данных из AGENTS.md:
/// id (UUIDv4), title, event_type, start_time/end_time (ISO 8601 с таймзоной),
/// location, teacher, description, recurrence_rule (RFC 5545),
/// updated_at (ISO 8601 UTC), is_deleted (soft delete).
class Event {
  final String id;
  final String title;
  final EventType eventType;
  final DateTime startTime;
  final DateTime endTime;
  final String? location;
  final String? teacher;
  final String? description;
  final String? recurrenceRule;

  /// Всегда хранится в UTC.
  final DateTime updatedAt;
  final bool isDeleted;

  Event({
    String? id,
    required this.title,
    required this.eventType,
    required this.startTime,
    required this.endTime,
    this.location,
    this.teacher,
    this.description,
    this.recurrenceRule,
    DateTime? updatedAt,
    this.isDeleted = false,
  })  : id = id ?? const Uuid().v4(),
        updatedAt = (updatedAt ?? DateTime.now()).toUtc() {
    validate();
  }

  /// Инварианты контракта. Выбрасывает [ArgumentError] при нарушении.
  void validate() {
    if (id.trim().isEmpty) {
      throw ArgumentError.value(id, 'id', 'must not be empty');
    }
    if (title.trim().isEmpty) {
      throw ArgumentError.value(title, 'title', 'must not be empty');
    }
    if (!endTime.isAfter(startTime)) {
      throw ArgumentError(
        'end_time ($endTime) must be after start_time ($startTime)',
      );
    }
  }

  static const Object _sentinel = Object();

  /// Копия с изменёнными полями. Для nullable-полей (location, teacher,
  /// description, recurrenceRule) явный `null` очищает значение,
  /// а пропуск аргумента — сохраняет текущее.
  Event copyWith({
    String? id,
    String? title,
    EventType? eventType,
    DateTime? startTime,
    DateTime? endTime,
    Object? location = _sentinel,
    Object? teacher = _sentinel,
    Object? description = _sentinel,
    Object? recurrenceRule = _sentinel,
    DateTime? updatedAt,
    bool? isDeleted,
  }) {
    return Event(
      id: id ?? this.id,
      title: title ?? this.title,
      eventType: eventType ?? this.eventType,
      startTime: startTime ?? this.startTime,
      endTime: endTime ?? this.endTime,
      location: identical(location, _sentinel) ? this.location : location as String?,
      teacher: identical(teacher, _sentinel) ? this.teacher : teacher as String?,
      description: identical(description, _sentinel) ? this.description : description as String?,
      recurrenceRule:
          identical(recurrenceRule, _sentinel) ? this.recurrenceRule : recurrenceRule as String?,
      updatedAt: updatedAt ?? this.updatedAt,
      isDeleted: isDeleted ?? this.isDeleted,
    );
  }

  /// Сериализация в канонический JSON-контракт (snake_case, ISO 8601).
  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'title': title,
      'event_type': eventType.name,
      'start_time': startTime.toIso8601String(),
      'end_time': endTime.toIso8601String(),
      'location': location,
      'teacher': teacher,
      'description': description,
      'recurrence_rule': recurrenceRule,
      'updated_at': updatedAt.toUtc().toIso8601String(),
      'is_deleted': isDeleted,
    };
  }

  /// Десериализация. Толерантна к `is_deleted` в виде int (0/1) из SQLite.
  /// Выбрасывает [FormatException] при битых датах.
  factory Event.fromJson(Map<String, dynamic> json) {
    DateTime parseTime(String key) {
      final raw = json[key];
      if (raw is! String) {
        throw FormatException('Field "$key" must be an ISO 8601 string, got: $raw');
      }
      final parsed = DateTime.tryParse(raw);
      if (parsed == null) {
        throw FormatException('Field "$key" has invalid date value: $raw');
      }
      return parsed;
    }

    String? optString(String key) {
      final value = json[key];
      return value is String && value.isNotEmpty ? value : null;
    }

    return Event(
      id: json['id'] as String?,
      title: (json['title'] as String?) ?? '',
      eventType: EventType.fromString(json['event_type'] as String?),
      startTime: parseTime('start_time'),
      endTime: parseTime('end_time'),
      location: optString('location'),
      teacher: optString('teacher'),
      description: optString('description'),
      recurrenceRule: optString('recurrence_rule'),
      updatedAt: parseTime('updated_at'),
      isDeleted: json['is_deleted'] == true || json['is_deleted'] == 1,
    );
  }
}
