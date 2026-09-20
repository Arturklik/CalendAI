import 'package:flutter/foundation.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:calendai/services/api_config.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() async {
    SharedPreferences.setMockInitialValues({});
    await ApiConfig.setCustomHost(null);
  });

  tearDown(() {
    debugDefaultTargetPlatformOverride = null;
  });

  test('Android использует хост эмулятора 10.0.2.2', () {
    debugDefaultTargetPlatformOverride = TargetPlatform.android;
    expect(ApiConfig.host, ApiConfig.androidEmulatorHost);
    expect(ApiConfig.baseUrl, 'http://10.0.2.2:8000/api/v1');
  });

  test('iOS использует 127.0.0.1', () {
    debugDefaultTargetPlatformOverride = TargetPlatform.iOS;
    expect(ApiConfig.host, ApiConfig.localhost);
    expect(ApiConfig.baseUrl, 'http://127.0.0.1:8000/api/v1');
  });

  test('macOS (Desktop) использует 127.0.0.1', () {
    debugDefaultTargetPlatformOverride = TargetPlatform.macOS;
    expect(ApiConfig.baseUrl, 'http://127.0.0.1:8000/api/v1');
  });

  test('кастомный IP перекрывает платформенный хост и сохраняется', () async {
    debugDefaultTargetPlatformOverride = TargetPlatform.android;

    await ApiConfig.setCustomHost('192.168.1.42');
    expect(ApiConfig.baseUrl, 'http://192.168.1.42:8000/api/v1');

    // Значение персистится в SharedPreferences.
    final prefs = await SharedPreferences.getInstance();
    expect(prefs.getString('api_custom_host'), '192.168.1.42');

    // Сброс возвращает платформенное значение.
    await ApiConfig.setCustomHost(null);
    expect(ApiConfig.baseUrl, 'http://10.0.2.2:8000/api/v1');
    expect(prefs.getString('api_custom_host'), isNull);
  });

  test('кастомный порт учитывается', () async {
    await ApiConfig.setCustomHost('192.168.1.42', port: 9000);
    expect(ApiConfig.port, 9000);
    expect(ApiConfig.baseUrl, 'http://192.168.1.42:9000/api/v1');

    await ApiConfig.setCustomHost('192.168.1.42');
    expect(ApiConfig.port, ApiConfig.defaultPort);
  });

  test('пустая строка сбрасывает переопределение', () async {
    debugDefaultTargetPlatformOverride = TargetPlatform.iOS;
    await ApiConfig.setCustomHost('   ');
    expect(ApiConfig.baseUrl, 'http://127.0.0.1:8000/api/v1');
  });
}
