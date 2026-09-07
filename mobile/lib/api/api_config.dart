class ApiConfig {
  /// Android emulator: 10.0.2.2 — host machine localhost.
  /// iOS simulator / Windows desktop: 127.0.0.1
  static const String baseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://127.0.0.1:8000',
  );
}
