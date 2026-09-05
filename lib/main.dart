import 'package:flutter/material.dart';

import 'screens/calendar_screen.dart';

void main() {
  runApp(const CalendAIApp());
}

class CalendAIApp extends StatelessWidget {
  const CalendAIApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'CalendAI',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: Colors.blue),
        useMaterial3: true,
      ),
      home: const CalendarScreen(),
    );
  }
}
