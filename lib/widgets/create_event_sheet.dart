import 'package:flutter/material.dart';

import '../models/event.dart';
import '../theme/event_type_style.dart';

/// Модальная форма создания занятия на выбранную дату.
///
/// Возвращает созданный [Event] через `Navigator.pop` при сохранении.
/// Контроллеры полей живут в [State] этой шторки и освобождаются в
/// [dispose] — только после полного закрытия маршрута. Освобождать их
/// снаружи сразу после `await showModalBottomSheet(...)` нельзя:
/// во время анимации закрытия `TextField` ещё обращается к контроллерам.
class CreateEventSheet extends StatefulWidget {
  const CreateEventSheet({super.key, required this.date});

  /// Дата, на которую создаётся занятие.
  final DateTime date;

  @override
  State<CreateEventSheet> createState() => _CreateEventSheetState();
}

class _CreateEventSheetState extends State<CreateEventSheet> {
  final TextEditingController _titleController = TextEditingController();
  final TextEditingController _locationController = TextEditingController();

  EventType _type = EventType.lecture;
  TimeOfDay _startTime = const TimeOfDay(hour: 9, minute: 0);
  TimeOfDay _endTime = const TimeOfDay(hour: 10, minute: 35);
  String? _errorText;

  @override
  void dispose() {
    _titleController.dispose();
    _locationController.dispose();
    super.dispose();
  }

  DateTime _combine(TimeOfDay time) => DateTime(
        widget.date.year,
        widget.date.month,
        widget.date.day,
        time.hour,
        time.minute,
      );

  Future<void> _pickTime({required bool isStart}) async {
    final picked = await showTimePicker(
      context: context,
      initialTime: isStart ? _startTime : _endTime,
    );
    if (picked == null || !mounted) return;
    setState(() {
      if (isStart) {
        _startTime = picked;
      } else {
        _endTime = picked;
      }
    });
  }

  void _save() {
    final title = _titleController.text.trim();
    if (title.isEmpty) {
      setState(() => _errorText = 'Введите название занятия');
      return;
    }
    final start = _combine(_startTime);
    final end = _combine(_endTime);
    if (!end.isAfter(start)) {
      setState(() => _errorText = 'Время окончания должно быть позже начала');
      return;
    }
    final location = _locationController.text.trim();
    Navigator.of(context).pop(
      Event(
        title: title,
        eventType: _type,
        startTime: start,
        endTime: end,
        location: location.isEmpty ? null : location,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final date = widget.date;
    final dateLabel = '${date.day.toString().padLeft(2, '0')}.'
        '${date.month.toString().padLeft(2, '0')}.${date.year}';

    return SingleChildScrollView(
      child: Padding(
        padding: EdgeInsets.only(
          left: 16,
          right: 16,
          top: 16,
          bottom: MediaQuery.of(context).viewInsets.bottom + 16,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              'Новое занятие — $dateLabel',
              style: theme.textTheme.titleMedium,
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _titleController,
              autofocus: true,
              decoration: const InputDecoration(
                labelText: 'Название',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 12),
            DropdownButtonFormField<EventType>(
              initialValue: _type,
              decoration: const InputDecoration(
                labelText: 'Тип',
                border: OutlineInputBorder(),
              ),
              items: EventType.values
                  .map(
                    (type) => DropdownMenuItem(
                      value: type,
                      child: Row(
                        children: [
                          Icon(
                            Icons.circle,
                            size: 10,
                            color: eventTypeColor(type),
                          ),
                          const SizedBox(width: 8),
                          Text(eventTypeLabel(type)),
                        ],
                      ),
                    ),
                  )
                  .toList(),
              onChanged: (value) {
                if (value != null) setState(() => _type = value);
              },
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: () => _pickTime(isStart: true),
                    icon: const Icon(Icons.schedule),
                    label: Text(
                      'Начало: ${_fmtTimeOfDay(_startTime)}',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: () => _pickTime(isStart: false),
                    icon: const Icon(Icons.schedule),
                    label: Text(
                      'Конец: ${_fmtTimeOfDay(_endTime)}',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _locationController,
              decoration: const InputDecoration(
                labelText: 'Аудитория',
                border: OutlineInputBorder(),
              ),
            ),
            if (_errorText != null) ...[
              const SizedBox(height: 8),
              Text(
                _errorText!,
                style: TextStyle(color: theme.colorScheme.error),
              ),
            ],
            const SizedBox(height: 16),
            FilledButton.icon(
              onPressed: _save,
              icon: const Icon(Icons.check),
              label: const Text('Сохранить'),
            ),
          ],
        ),
      ),
    );
  }
}

String _twoDigits(int value) => value.toString().padLeft(2, '0');

String _fmtTimeOfDay(TimeOfDay time) =>
    '${_twoDigits(time.hour)}:${_twoDigits(time.minute)}';
