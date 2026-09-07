import 'package:path/path.dart' as p;
import 'package:sqflite/sqflite.dart';

import '../models/event.dart';

/// Локальное офлайн-хранилище CalendAI (SQLite через sqflite).
///
/// Все метки времени (start_time, end_time, updated_at) хранятся
/// в UTC в формате ISO 8601 — это гарантирует корректное лексикографическое
/// сравнение строк в диапазонных запросах независимо от исходной таймзоны.
class AppDatabase {
  AppDatabase._();

  static final AppDatabase instance = AppDatabase._();

  static const String _dbName = 'calendai.db';
  static const int _dbVersion = 1;
  static const String tableEvents = 'events';

  Database? _db;

  Future<Database> get database async => _db ??= await _open();

  Future<Database> _open() async {
    final path = p.join(await getDatabasesPath(), _dbName);
    return openDatabase(
      path,
      version: _dbVersion,
      onCreate: (db, version) async {
        await db.execute('''
          CREATE TABLE $tableEvents (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            event_type TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            location TEXT,
            teacher TEXT,
            description TEXT,
            recurrence_rule TEXT,
            updated_at TEXT NOT NULL,
            is_deleted INTEGER NOT NULL DEFAULT 0
          )
        ''');
        await db.execute(
          'CREATE INDEX idx_events_start_time ON $tableEvents(start_time)',
        );
      },
    );
  }

  /// Для тестов/сброса.
  Future<void> close() async {
    await _db?.close();
    _db = null;
  }

  /// События, пересекающиеся с диапазоном [start, end) (не удалённые),
  /// отсортированные по времени начала.
  Future<List<Event>> getEventsInRange(DateTime start, DateTime end) async {
    final db = await database;
    final rows = await db.query(
      tableEvents,
      where: 'is_deleted = 0 AND start_time < ? AND end_time > ?',
      whereArgs: [
        end.toUtc().toIso8601String(),
        start.toUtc().toIso8601String(),
      ],
      orderBy: 'start_time ASC',
    );
    return rows.map(Event.fromJson).toList();
  }

  /// Локальные изменения (включая soft-deleted) с момента [lastSync] —
  /// используется как `localChanges` для SyncRepository.
  Future<List<Event>> getPendingChanges(DateTime lastSync) async {
    final db = await database;
    final rows = await db.query(
      tableEvents,
      where: 'updated_at > ?',
      whereArgs: [lastSync.toUtc().toIso8601String()],
    );
    return rows.map(Event.fromJson).toList();
  }

  /// Вставка или обновление события по id.
  /// [touchTimestamp] = false при применении server_changes, иначе LWW сломается.
  Future<void> upsertEvent(Event event, {bool touchTimestamp = true}) async {
    final db = await database;
    final stamped = touchTimestamp
        ? event.copyWith(updatedAt: DateTime.now().toUtc())
        : event;
    await db.insert(
      tableEvents,
      _toRow(stamped),
      conflictAlgorithm: ConflictAlgorithm.replace,
    );
  }

  /// Мягкое удаление: запись остаётся для последующей синхронизации.
  Future<void> softDeleteEvent(String id) async {
    final db = await database;
    await db.update(
      tableEvents,
      {
        'is_deleted': 1,
        'updated_at': DateTime.now().toUtc().toIso8601String(),
      },
      where: 'id = ?',
      whereArgs: [id],
    );
  }

  Map<String, Object?> _toRow(Event event) {
    final json = event.toJson();
    json['start_time'] = event.startTime.toUtc().toIso8601String();
    json['end_time'] = event.endTime.toUtc().toIso8601String();
    json['is_deleted'] = event.isDeleted ? 1 : 0;
    return json;
  }
}
