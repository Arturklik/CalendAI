import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Конфигурация адреса backend API.
///
/// Базовый адрес зависит от платформы:
///  - Android (эмулятор): http://10.0.2.2:8000/api/v1
///  - iOS / Desktop:      http://127.0.0.1:8000/api/v1
///
/// Для тестирования на реальном телефоне по Wi-Fi задайте IP компьютера
/// через [setCustomHost] (значение сохраняется в SharedPreferences).
class ApiConfig {
  ApiConfig._();

  static const String _hostKey = 'api_custom_host';
  static const String _portKey = 'api_custom_port';

  static const int defaultPort = 8000;
  static const String apiPath = '/api/v1';

  /// Хост Android-эмулятора, через который доступен localhost машины.
  static const String androidEmulatorHost = '10.0.2.2';
  static const String localhost = '127.0.0.1';

  static String? _customHost;
  static int? _customPort;

  /// Загружает сохранённый кастомный адрес. Вызывать в `main()`
  /// после `WidgetsFlutterBinding.ensureInitialized()`.
  static Future<void> load() async {
    final prefs = await SharedPreferences.getInstance();
    _customHost = prefs.getString(_hostKey);
    _customPort = prefs.getInt(_portKey);
  }

  /// Задаёт кастомный хост/порт (например, IP компьютера в Wi-Fi).
  /// `null` сбрасывает переопределение к платформенному значению.
  static Future<void> setCustomHost(String? host, {int? port}) async {
    final prefs = await SharedPreferences.getInstance();
    final normalized = host?.trim();
    if (normalized == null || normalized.isEmpty) {
      _customHost = null;
      _customPort = null;
      await prefs.remove(_hostKey);
      await prefs.remove(_portKey);
      return;
    }
    _customHost = normalized;
    _customPort = port;
    await prefs.setString(_hostKey, normalized);
    if (port != null) {
      await prefs.setInt(_portKey, port);
    } else {
      await prefs.remove(_portKey);
    }
  }

  /// Текущий хост: кастомный или платформенный по умолчанию.
  static String get host {
    final custom = _customHost;
    if (custom != null && custom.isNotEmpty) return custom;
    if (!kIsWeb && defaultTargetPlatform == TargetPlatform.android) {
      return androidEmulatorHost;
    }
    return localhost;
  }

  /// Текущий порт API.
  static int get port => _customPort ?? defaultPort;

  /// Базовый URL API, например `http://10.0.2.2:8000/api/v1`.
  static String get baseUrl => 'http://$host:$port$apiPath';
}
