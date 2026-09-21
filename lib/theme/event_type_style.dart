import 'package:flutter/material.dart';

import '../models/event.dart';

/// Цветовая дифференциация типов занятий (единая для всего UI).
Color eventTypeColor(EventType type) => switch (type) {
      EventType.lecture => Colors.blue,
      EventType.lab => Colors.orange,
      EventType.practice => Colors.green,
      EventType.exam => Colors.red,
      EventType.other => Colors.grey,
    };

/// Человекочитаемые названия типов занятий.
const Map<EventType, String> eventTypeLabels = {
  EventType.lecture: 'Лекция',
  EventType.practice: 'Практика',
  EventType.lab: 'Лабораторная',
  EventType.exam: 'Экзамен',
  EventType.other: 'Другое',
};

/// Название типа занятия для UI (fallback — имя enum).
String eventTypeLabel(EventType type) => eventTypeLabels[type] ?? type.name;
