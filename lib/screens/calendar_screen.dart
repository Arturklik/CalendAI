import 'package:flutter/material.dart';

import '../database/app_database.dart';
import '../models/event.dart';
import '../repositories/mock_sync_repository.dart';
import '../repositories/sync_repository.dart';

/// Цветовая дифференциация типов занятий.
Color eventTypeColor(EventType type) => switch (type) {
      EventType.lecture => Colors.blue,
      EventType.lab => Colors.orange,
      EventType.practice => Colors.green,
      EventType.exam => Colors.red,
      EventType.other => Colors.grey,
    };

const Map<EventType, String> eventTypeLabels = {
  EventType.lecture: 'Лекция',
  EventType.practice: 'Практика',
  EventType.lab: 'Лабораторная',
  EventType.exam: 'Экзамен',
  EventType.other: 'Другое',
};

const List<String> _monthNames = [
  'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
  'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь',
];

const List<String> _weekdayNames = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];

String _twoDigits(int value) => value.toString().padLeft(2, '0');

String _fmtTime(DateTime dt) {
  final local = dt.toLocal();
  return '${_twoDigits(local.hour)}:${_twoDigits(local.minute)}';
}

String _fmtTimeOfDay(TimeOfDay time) =>
    '${_twoDigits(time.hour)}:${_twoDigits(time.minute)}';

/// Базовый экран календаря: месячная сетка + список занятий на выбранный день.
class CalendarScreen extends StatefulWidget {
  const CalendarScreen({super.key, SyncRepository? syncRepository})
      : _syncRepository = syncRepository ?? const MockSyncRepository();

  final SyncRepository _syncRepository;

  @override
  State<CalendarScreen> createState() => _CalendarScreenState();
}

class _CalendarScreenState extends State<CalendarScreen> {
  final AppDatabase _db = AppDatabase.instance;

  late DateTime _focusedMonth;
  late DateTime _selectedDate;
  List<Event> _monthEvents = [];
  bool _syncing = false;
  DateTime _lastSync = DateTime.fromMillisecondsSinceEpoch(0, isUtc: true);

  @override
  void initState() {
    super.initState();
    final now = DateTime.now();
    _focusedMonth = DateTime(now.year, now.month);
    _selectedDate = DateTime(now.year, now.month, now.day);
    _loadMonthEvents();
  }

  Future<void> _loadMonthEvents() async {
    final start = DateTime(_focusedMonth.year, _focusedMonth.month);
    final end = DateTime(_focusedMonth.year, _focusedMonth.month + 1);
    final events = await _db.getEventsInRange(start, end);
    if (mounted) setState(() => _monthEvents = events);
  }

  void _shiftMonth(int delta) {
    setState(() {
      _focusedMonth = DateTime(_focusedMonth.year, _focusedMonth.month + delta);
      _selectedDate = _focusedMonth;
    });
    _loadMonthEvents();
  }

  /// День месяца -> есть ли события (для точек-индикаторов в сетке).
  Set<int> get _daysWithEvents {
    final days = <int>{};
    for (final e in _monthEvents) {
      final local = e.startTime.toLocal();
      if (local.year == _focusedMonth.year &&
          local.month == _focusedMonth.month) {
        days.add(local.day);
      }
    }
    return days;
  }

  List<Event> get _selectedDayEvents {
    final dayStart =
        DateTime(_selectedDate.year, _selectedDate.month, _selectedDate.day);
    final dayEnd = dayStart.add(const Duration(days: 1));
    final list = _monthEvents.where((e) {
      return e.startTime.toLocal().isBefore(dayEnd) &&
          e.endTime.toLocal().isAfter(dayStart);
    }).toList();
    list.sort((a, b) => a.startTime.compareTo(b.startTime));
    return list;
  }

  Future<void> _sync() async {
    if (_syncing) return;
    setState(() => _syncing = true);
    try {
      final localChanges = await _db.getPendingChanges(_lastSync);
      final remoteEvents =
          await widget._syncRepository.sync(_lastSync, localChanges);
      for (final event in remoteEvents) {
        await _db.upsertEvent(event);
      }
      _lastSync = DateTime.now().toUtc();
      await _loadMonthEvents();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              'Синхронизация завершена: получено событий — ${remoteEvents.length}',
            ),
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _syncing = false);
    }
  }

  Future<void> _showCreateEventForm() async {
    final titleController = TextEditingController();
    final locationController = TextEditingController();
    EventType type = EventType.lecture;
    TimeOfDay startTime = const TimeOfDay(hour: 9, minute: 0);
    TimeOfDay endTime = const TimeOfDay(hour: 10, minute: 35);

    final created = await showModalBottomSheet<Event>(
      context: context,
      isScrollControlled: true,
      builder: (sheetContext) {
        String? errorText;
        return StatefulBuilder(
          builder: (sheetContext, setSheetState) {
            DateTime combine(TimeOfDay time) => DateTime(
                  _selectedDate.year,
                  _selectedDate.month,
                  _selectedDate.day,
                  time.hour,
                  time.minute,
                );

            Future<void> pickTime(bool isStart) async {
              final picked = await showTimePicker(
                context: sheetContext,
                initialTime: isStart ? startTime : endTime,
              );
              if (picked != null) {
                setSheetState(() {
                  if (isStart) {
                    startTime = picked;
                  } else {
                    endTime = picked;
                  }
                });
              }
            }

            void save() {
              final title = titleController.text.trim();
              if (title.isEmpty) {
                setSheetState(() => errorText = 'Введите название занятия');
                return;
              }
              final start = combine(startTime);
              final end = combine(endTime);
              if (!end.isAfter(start)) {
                setSheetState(() =>
                    errorText = 'Время окончания должно быть позже начала');
                return;
              }
              final location = locationController.text.trim();
              Navigator.of(sheetContext).pop(
                Event(
                  title: title,
                  eventType: type,
                  startTime: start,
                  endTime: end,
                  location: location.isEmpty ? null : location,
                ),
              );
            }

            final dateLabel =
                '${_selectedDate.day.toString().padLeft(2, '0')}.'
                '${_selectedDate.month.toString().padLeft(2, '0')}.'
                '${_selectedDate.year}';

            return Padding(
              padding: EdgeInsets.only(
                left: 16,
                right: 16,
                top: 16,
                bottom: MediaQuery.of(sheetContext).viewInsets.bottom + 16,
              ),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Text(
                    'Новое занятие — $dateLabel',
                    style: Theme.of(sheetContext).textTheme.titleMedium,
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: titleController,
                    autofocus: true,
                    decoration: const InputDecoration(
                      labelText: 'Название',
                      border: OutlineInputBorder(),
                    ),
                  ),
                  const SizedBox(height: 12),
                  DropdownButtonFormField<EventType>(
                    initialValue: type,
                    decoration: const InputDecoration(
                      labelText: 'Тип',
                      border: OutlineInputBorder(),
                    ),
                    items: EventType.values
                        .map(
                          (t) => DropdownMenuItem(
                            value: t,
                            child: Row(
                              children: [
                                Icon(Icons.circle,
                                    size: 10, color: eventTypeColor(t)),
                                const SizedBox(width: 8),
                                Text(eventTypeLabels[t] ?? t.name),
                              ],
                            ),
                          ),
                        )
                        .toList(),
                    onChanged: (value) {
                      if (value != null) setSheetState(() => type = value);
                    },
                  ),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Expanded(
                        child: OutlinedButton.icon(
                          onPressed: () => pickTime(true),
                          icon: const Icon(Icons.schedule),
                          label: Text('Начало: ${_fmtTimeOfDay(startTime)}'),
                        ),
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: OutlinedButton.icon(
                          onPressed: () => pickTime(false),
                          icon: const Icon(Icons.schedule),
                          label: Text('Конец: ${_fmtTimeOfDay(endTime)}'),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: locationController,
                    decoration: const InputDecoration(
                      labelText: 'Аудитория',
                      border: OutlineInputBorder(),
                    ),
                  ),
                  if (errorText != null) ...[
                    const SizedBox(height: 8),
                    Text(
                      errorText!,
                      style: TextStyle(
                        color: Theme.of(sheetContext).colorScheme.error,
                      ),
                    ),
                  ],
                  const SizedBox(height: 16),
                  FilledButton.icon(
                    onPressed: save,
                    icon: const Icon(Icons.check),
                    label: const Text('Сохранить'),
                  ),
                ],
              ),
            );
          },
        );
      },
    );

    if (created != null) {
      await _db.upsertEvent(created);
      await _loadMonthEvents();
    }
    titleController.dispose();
    locationController.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('CalendAI'),
        actions: [
          if (_syncing)
            const Padding(
              padding: EdgeInsets.all(14),
              child: SizedBox(
                width: 20,
                height: 20,
                child: CircularProgressIndicator(strokeWidth: 2),
              ),
            )
          else
            IconButton(
              icon: const Icon(Icons.sync),
              tooltip: 'Синхронизировать',
              onPressed: _sync,
            ),
        ],
      ),
      body: Column(
        children: [
          _buildMonthHeader(),
          _buildWeekdayRow(),
          _buildMonthGrid(),
          const Divider(height: 1),
          Expanded(child: _buildEventList()),
        ],
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: _showCreateEventForm,
        tooltip: 'Добавить занятие',
        child: const Icon(Icons.add),
      ),
    );
  }

  Widget _buildMonthHeader() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          IconButton(
            icon: const Icon(Icons.chevron_left),
            onPressed: () => _shiftMonth(-1),
          ),
          Text(
            '${_monthNames[_focusedMonth.month - 1]} ${_focusedMonth.year}',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          IconButton(
            icon: const Icon(Icons.chevron_right),
            onPressed: () => _shiftMonth(1),
          ),
        ],
      ),
    );
  }

  Widget _buildWeekdayRow() {
    return Row(
      children: _weekdayNames
          .map(
            (name) => Expanded(
              child: Center(
                child: Text(
                  name,
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ),
            ),
          )
          .toList(),
    );
  }

  Widget _buildMonthGrid() {
    final firstOfMonth = DateTime(_focusedMonth.year, _focusedMonth.month);
    final daysInMonth =
        DateTime(_focusedMonth.year, _focusedMonth.month + 1, 0).day;
    // Понедельник — первый день недели: weekday 1..7 -> сдвиг 0..6.
    final leadingEmpty = firstOfMonth.weekday - 1;
    final cellCount = ((leadingEmpty + daysInMonth + 6) ~/ 7) * 7;
    final daysWithEvents = _daysWithEvents;
    final now = DateTime.now();

    return GridView.builder(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: 7,
        childAspectRatio: 1.2,
      ),
      itemCount: cellCount,
      itemBuilder: (context, index) {
        if (index < leadingEmpty || index >= leadingEmpty + daysInMonth) {
          return const SizedBox.shrink();
        }
        final day = index - leadingEmpty + 1;
        final date = DateTime(_focusedMonth.year, _focusedMonth.month, day);
        final isSelected = date == _selectedDate;
        final isToday =
            date.year == now.year && date.month == now.month && date.day == now.day;
        final hasEvents = daysWithEvents.contains(day);
        final colorScheme = Theme.of(context).colorScheme;

        return GestureDetector(
          onTap: () => setState(() => _selectedDate = date),
          child: Center(
            child: Container(
              width: 36,
              height: 36,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: isSelected ? colorScheme.primary : null,
                border: isToday && !isSelected
                    ? Border.all(color: colorScheme.primary)
                    : null,
              ),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Text(
                    '$day',
                    style: TextStyle(
                      fontSize: 13,
                      color: isSelected ? colorScheme.onPrimary : null,
                    ),
                  ),
                  if (hasEvents)
                    Icon(
                      Icons.circle,
                      size: 4,
                      color: isSelected
                          ? colorScheme.onPrimary
                          : colorScheme.primary,
                    ),
                ],
              ),
            ),
          ),
        );
      },
    );
  }

  Widget _buildEventList() {
    final events = _selectedDayEvents;
    if (events.isEmpty) {
      return const Center(child: Text('Нет занятий на этот день'));
    }
    return ListView.builder(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      itemCount: events.length,
      itemBuilder: (context, index) {
        final event = events[index];
        final color = eventTypeColor(event.eventType);
        final subtitleParts = [
          '${_fmtTime(event.startTime)} – ${_fmtTime(event.endTime)}',
          if (event.location != null) event.location!,
          if (event.teacher != null) event.teacher!,
        ];
        return Card(
          child: IntrinsicHeight(
            child: Row(
              children: [
                Container(
                  width: 5,
                  decoration: BoxDecoration(
                    color: color,
                    borderRadius: const BorderRadius.only(
                      topLeft: Radius.circular(12),
                      bottomLeft: Radius.circular(12),
                    ),
                  ),
                ),
                Expanded(
                  child: ListTile(
                    title: Text(event.title),
                    subtitle: Text(subtitleParts.join(' · ')),
                    trailing: Chip(
                      label: Text(
                        eventTypeLabels[event.eventType] ??
                            event.eventType.name,
                        style: const TextStyle(fontSize: 11),
                      ),
                      backgroundColor: color.withValues(alpha: 0.15),
                      side: BorderSide.none,
                      visualDensity: VisualDensity.compact,
                    ),
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}
