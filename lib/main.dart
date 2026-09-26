import 'package:flutter/material.dart';
import 'dart:ui' show PlatformDispatcher;

import 'screens/calendar_screen.dart';
import 'services/api_config.dart';
import 'services/app_logger.dart';

void _installGlobalErrorHandlers() {
  FlutterError.onError = (details) {
    AppLogger.instance.error(
      'Flutter framework error',
      error: details.exception,
      stackTrace: details.stack,
    );
    // Preserve Flutter's normal console/error presentation as well as the
    // in-app diagnostic log.
    FlutterError.presentError(details);
  };

  PlatformDispatcher.instance.onError = (error, stackTrace) {
    AppLogger.instance.error(
      'Uncaught asynchronous/platform error',
      error: error,
      stackTrace: stackTrace,
    );
    FlutterError.presentError(
      FlutterErrorDetails(
        exception: error,
        stack: stackTrace,
        library: 'CalendAI asynchronous error handler',
      ),
    );
    // It is captured and surfaced through FlutterError + AppLogger.
    return true;
  };
}

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  _installGlobalErrorHandlers();
  // Загружаем сохранённый кастомный адрес API (если задавался).
  try {
    await ApiConfig.load();
  } catch (error, stackTrace) {
    AppLogger.instance.error(
      'Failed to initialize API configuration',
      error: error,
      stackTrace: stackTrace,
    );
    rethrow;
  }
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
