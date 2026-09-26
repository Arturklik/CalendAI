import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';

import 'package:calendai/main.dart';

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('dismiss create-event sheet after focusing title on iOS',
      (tester) async {
    await tester.pumpWidget(const CalendAIApp());
    await tester.pumpAndSettle();

    await tester.tap(find.byTooltip('Добавить занятие'));
    await tester.pumpAndSettle();

    final titleField = find.byType(TextField).first;
    await tester.tap(titleField);
    await tester.pumpAndSettle();
    await tester.enterText(titleField, 'Проверка закрытия');
    await tester.pumpAndSettle();

    final screenSize = tester.view.physicalSize / tester.view.devicePixelRatio;
    await tester.tapAt(Offset(screenSize.width / 2, screenSize.height * 0.18));
    await tester.pumpAndSettle();

    expect(find.textContaining('Новое занятие'), findsNothing);
    final errors = <Object>[];
    Object? error;
    while ((error = tester.takeException()) != null) {
      errors.add(error!);
    }
    expect(errors, isEmpty, reason: 'Flutter reported: $errors');
  });
}
