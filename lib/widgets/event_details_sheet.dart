import 'package:flutter/material.dart';

import '../models/event.dart';
import '../theme/event_type_style.dart';
import '../utils/date_time_format.dart';

/// Открывает модальный просмотр деталей занятия.
///
/// Возвращает `true`, если пользователь нажал «Удалить занятие»
/// (удаление выполняет вызывающая сторона через `AppDatabase`).
Future<bool> showEventDetailsSheet(BuildContext context, Event event) async {
  final result = await showModalBottomSheet<bool>(
    context: context,
    showDragHandle: true,
    isScrollControlled: true,
    builder: (_) => _EventDetailsSheet(event: event),
  );
  return result ?? false;
}

class _EventDetailsSheet extends StatelessWidget {
  const _EventDetailsSheet({required this.event});

  final Event event;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final color = eventTypeColor(event.eventType);
    final duration = event.endTime.difference(event.startTime);
    final description = event.description?.trim();

    return SafeArea(
      child: SingleChildScrollView(
        padding: const EdgeInsets.fromLTRB(20, 0, 20, 20),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(
                  child: Text(
                    event.title,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: theme.textTheme.titleLarge?.copyWith(
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                Chip(
                  label: Text(
                    eventTypeLabel(event.eventType),
                    style: const TextStyle(fontSize: 12),
                  ),
                  backgroundColor: color.withValues(alpha: 0.15),
                  side: BorderSide.none,
                  visualDensity: VisualDensity.compact,
                  materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                ),
              ],
            ),
            const SizedBox(height: 16),
            _DetailRow(
              icon: Icons.schedule,
              text: '${formatTimeRange(event.startTime, event.endTime)}'
                  ' · ${formatDuration(duration)}',
            ),
            if (event.location != null)
              _DetailRow(icon: Icons.place_outlined, text: event.location!),
            if (event.teacher != null)
              _DetailRow(icon: Icons.person_outline, text: event.teacher!),
            if (description != null && description.isNotEmpty) ...[
              const SizedBox(height: 16),
              Text('Описание', style: theme.textTheme.labelLarge),
              const SizedBox(height: 4),
              Text(description, style: theme.textTheme.bodyMedium),
            ],
            const SizedBox(height: 24),
            SizedBox(
              width: double.infinity,
              child: OutlinedButton.icon(
                onPressed: () => Navigator.of(context).pop(true),
                icon: const Icon(Icons.delete_outline),
                label: const Text('Удалить занятие'),
                style: OutlinedButton.styleFrom(
                  foregroundColor: theme.colorScheme.error,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _DetailRow extends StatelessWidget {
  const _DetailRow({required this.icon, required this.text});

  final IconData icon;
  final String text;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, size: 18, color: theme.colorScheme.onSurfaceVariant),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              text,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: theme.textTheme.bodyMedium,
            ),
          ),
        ],
      ),
    );
  }
}
