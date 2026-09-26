import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../services/app_logger.dart';

/// Displays the in-memory diagnostics and lets the user copy them.
Future<void> showAppErrorLogDialog(BuildContext context) async {
  final copied = await showDialog<bool>(
    context: context,
    builder: (_) => const _AppErrorLogDialog(),
  );
  if (copied == true && context.mounted) {
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Логи скопированы в буфер обмена')),
    );
  }
}

class _AppErrorLogDialog extends StatelessWidget {
  const _AppErrorLogDialog();

  @override
  Widget build(BuildContext context) {
    final logger = AppLogger.instance;
    final maxHeight = MediaQuery.sizeOf(context).height * 0.6;

    return AlertDialog(
      title: const Text('Журнал ошибок'),
      content: SizedBox(
        width: double.maxFinite,
        height: maxHeight,
        child: AnimatedBuilder(
          animation: logger,
          builder: (context, _) => SingleChildScrollView(
            child: SelectableText(
              logger.export(),
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(false),
          child: const Text('Закрыть'),
        ),
        FilledButton.icon(
          onPressed: () async {
            await Clipboard.setData(ClipboardData(text: logger.export()));
            if (context.mounted) Navigator.of(context).pop(true);
          },
          icon: const Icon(Icons.copy),
          label: const Text('Скопировать логи'),
        ),
      ],
    );
  }
}
