import '../models/event.dart';

/// Интерфейс синхронизации с бэкендом (AGENTS.md: дифференциальная
/// синхронизация, без преждевременной привязки к сетевому коду).
///
/// Отправляет локальные изменения [localChanges], накопленные с момента
/// [lastSync], и возвращает события, изменённые на сервере после [lastSync]
/// (включая soft-deleted), которые клиент применяет через upsert.
abstract class SyncRepository {
  Future<List<Event>> sync(DateTime lastSync, List<Event> localChanges);
}
