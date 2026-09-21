// Тесты карточки занятия и модальной шторки с деталями.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:calendai/models/event.dart';
import 'package:calendai/utils/date_time_format.dart';
import 'package:calendai/widgets/event_card.dart';
import 'package:calendai/widgets/event_details_sheet.dart';

void main() {
  // Локальные даты — форматирование не зависит от таймзоны машины.
  Event sampleEvent({String? location = 'Ауд. 214', String? teacher = 'Иванов А.П.'}) =>
      Event(
        id: 'a1b2c3d4-0000-4000-8000-000000000001',
        title: 'Лекция: Математический анализ',
        eventType: EventType.lecture,
        startTime: DateTime(2026, 9, 8, 9, 0),
        endTime: DateTime(2026, 9, 8, 10, 35),
        location: location,
        teacher: teacher,
        description: 'Принести конспект',
      );

  group('formatDuration', () {
    test('часы и минуты', () {
      expect(
        formatDuration(const Duration(hours: 1, minutes: 35)),
        '1 ч 35 мин',
      );
      expect(formatDuration(const Duration(hours: 2)), '2 ч');
      expect(formatDuration(const Duration(minutes: 45)), '45 мин');
    });
  });

  group('EventCard', () {
    testWidgets('показывает время, название, аудиторию, преподавателя и тип',
        (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: EventCard(event: sampleEvent(), onTap: () {}),
          ),
        ),
      );

      expect(find.text('09:00 – 10:35'), findsOneWidget);
      expect(find.text('Лекция: Математический анализ'), findsOneWidget);
      expect(find.text('Ауд. 214'), findsOneWidget);
      expect(find.text('Иванов А.П.'), findsOneWidget);
      expect(find.text('Лекция'), findsOneWidget); // Chip типа занятия
      expect(find.byIcon(Icons.place_outlined), findsOneWidget);
      expect(find.byIcon(Icons.person_outline), findsOneWidget);
    });

    testWidgets('без аудитории и преподавателя не показывает лишние строки',
        (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: EventCard(
              event: sampleEvent(location: null, teacher: null),
              onTap: () {},
            ),
          ),
        ),
      );

      expect(find.byIcon(Icons.place_outlined), findsNothing);
      expect(find.byIcon(Icons.person_outline), findsNothing);
    });

    testWidgets('тап по карточке вызывает onTap', (tester) async {
      var tapped = false;
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: EventCard(
              event: sampleEvent(),
              onTap: () => tapped = true,
            ),
          ),
        ),
      );

      await tester.tap(find.byType(EventCard));
      expect(tapped, isTrue);
    });
  });

  group('showEventDetailsSheet', () {
    testWidgets('показывает детали и возвращает true при удалении',
        (tester) async {
      bool? result;
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Builder(
              builder: (context) => Center(
                child: ElevatedButton(
                  onPressed: () async {
                    result = await showEventDetailsSheet(
                      context,
                      sampleEvent(),
                    );
                  },
                  child: const Text('Открыть'),
                ),
              ),
            ),
          ),
        ),
      );

      await tester.tap(find.text('Открыть'));
      await tester.pumpAndSettle();

      expect(find.text('Лекция: Математический анализ'), findsOneWidget);
      expect(find.text('09:00 – 10:35 · 1 ч 35 мин'), findsOneWidget);
      expect(find.text('Ауд. 214'), findsOneWidget);
      expect(find.text('Иванов А.П.'), findsOneWidget);
      expect(find.text('Принести конспект'), findsOneWidget);
      expect(find.text('Удалить занятие'), findsOneWidget);

      await tester.tap(find.text('Удалить занятие'));
      await tester.pumpAndSettle();

      expect(result, isTrue);
      expect(find.text('Удалить занятие'), findsNothing);
    });

    testWidgets('закрытие без удаления возвращает false', (tester) async {
      bool? result;
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Builder(
              builder: (context) => Center(
                child: ElevatedButton(
                  onPressed: () async {
                    result = await showEventDetailsSheet(
                      context,
                      sampleEvent(),
                    );
                  },
                  child: const Text('Открыть'),
                ),
              ),
            ),
          ),
        ),
      );

      await tester.tap(find.text('Открыть'));
      await tester.pumpAndSettle();
      expect(find.text('Удалить занятие'), findsOneWidget);

      // Свайп вниз закрывает шторку без удаления.
      await tester.drag(
        find.text('Лекция: Математический анализ'),
        const Offset(0, 400),
      );
      await tester.pumpAndSettle();

      expect(result, isFalse);
    });
  });
}
