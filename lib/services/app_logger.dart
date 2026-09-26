import 'package:flutter/foundation.dart';

/// Severity of an in-memory application log entry.
enum AppLogLevel { info, warning, error }

/// One timestamped diagnostic entry.
@immutable
class AppLogEntry {
  const AppLogEntry({
    required this.timestamp,
    required this.level,
    required this.message,
    this.error,
    this.stackTrace,
  });

  final DateTime timestamp;
  final AppLogLevel level;
  final String message;
  final Object? error;
  final StackTrace? stackTrace;

  String format() {
    final buffer = StringBuffer()
      ..write(timestamp.toIso8601String())
      ..write(' [${level.name.toUpperCase()}] ')
      ..write(message);
    if (error != null) buffer.write('\n$error');
    if (stackTrace != null) buffer.write('\n$stackTrace');
    return buffer.toString();
  }
}

/// Keeps the most recent application diagnostics in memory for user reports.
class AppLogger extends ChangeNotifier {
  AppLogger._();

  static final AppLogger instance = AppLogger._();
  static const int maxEntries = 20;

  final List<AppLogEntry> _entries = [];

  List<AppLogEntry> get entries => List.unmodifiable(_entries);

  void info(String message) => _write(AppLogLevel.info, message);

  void warning(String message, {Object? error, StackTrace? stackTrace}) =>
      _write(
        AppLogLevel.warning,
        message,
        error: error,
        stackTrace: stackTrace,
      );

  void error(String message, {Object? error, StackTrace? stackTrace}) => _write(
        AppLogLevel.error,
        message,
        error: error,
        stackTrace: stackTrace,
      );

  String export() {
    if (_entries.isEmpty) return 'Журнал пока пуст.';
    return _entries.map((entry) => entry.format()).join('\n\n');
  }

  void clear() {
    _entries.clear();
    notifyListeners();
  }

  void _write(
    AppLogLevel level,
    String message, {
    Object? error,
    StackTrace? stackTrace,
  }) {
    _entries.add(
      AppLogEntry(
        timestamp: DateTime.now().toUtc(),
        level: level,
        message: message,
        error: error,
        stackTrace: stackTrace,
      ),
    );
    if (_entries.length > maxEntries) {
      _entries.removeRange(0, _entries.length - maxEntries);
    }
    notifyListeners();
  }
}
