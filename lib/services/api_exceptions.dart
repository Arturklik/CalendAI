/// Типизированные исключения API-слоя.
///
/// UI перехватывает [ApiException] и показывает [message] пользователю,
/// не роняя приложение при сетевых сбоях и истёкшей авторизации.
sealed class ApiException implements Exception {
  const ApiException(this.message);

  /// Понятное пользователю описание ошибки (на русском).
  final String message;

  @override
  String toString() => '$runtimeType: $message';
}

/// Сервер недоступен: нет сети, таймаут или обрыв соединения.
class NetworkException extends ApiException {
  const NetworkException([
    super.message =
        'Не удалось подключиться к серверу. Проверьте интернет-соединение.',
  ]);
}

/// 401 Unauthorized: токен отсутствует, истёк или отвергнут сервером.
class UnauthorizedException extends ApiException {
  const UnauthorizedException([
    super.message = 'Сессия истекла. Войдите в аккаунт заново.',
  ]);
}

/// Ошибка входа/регистрации (неверные данные, email занят и т.п.).
class AuthException extends ApiException {
  const AuthException(super.message, {required this.statusCode});

  final int statusCode;
}

/// Прочие ошибки API (5xx, некорректный ответ сервера и т.п.).
class ApiRequestException extends ApiException {
  const ApiRequestException(super.message, {required this.statusCode});

  final int statusCode;
}
