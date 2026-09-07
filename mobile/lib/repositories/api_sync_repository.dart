import '../api/api_client.dart';
import '../models/event.dart';
import 'sync_repository.dart';

/// Реальная дифференциальная синхронизация: POST /api/v1/sync
class ApiSyncRepository implements SyncRepository {
  ApiSyncRepository(this._client);

  final ApiClient _client;

  @override
  Future<List<Event>> sync(DateTime lastSync, List<Event> localChanges) async {
    final payload = {
      'last_sync_timestamp': lastSync.millisecondsSinceEpoch <= 0
          ? null
          : lastSync.toUtc().toIso8601String(),
      'client_changes': localChanges.map((event) => event.toJson()).toList(),
    };
    final data = await _client.post('/api/v1/sync', payload);
    final raw = data['server_changes'];
    if (raw is! List) return const [];
    return raw
        .whereType<Map>()
        .map((item) => Event.fromJson(Map<String, dynamic>.from(item)))
        .toList();
  }
}
