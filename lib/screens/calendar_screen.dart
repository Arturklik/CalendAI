import 'package:flutter/material.dart';

import '../database/app_database.dart';
import '../models/event.dart';
import '../repositories/http_sync_repository.dart';
import '../repositories/sync_repository.dart';
import '../services/api_exceptions.dart';
import '../services/auth_storage.dart';
import '../theme/event_type_style.dart';
import '../utils/day_events.dart';
import '../widgets/auth_dialog.dart';
import '../widgets/create_event_sheet.dart';
import '../widgets/event_card.dart';
import '../widgets/event_details_sheet.dart';

const List<String> _monthNames = [
  'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
  'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь',
];

/// Родительный падеж для заголовка дня («20 сентября»).
const List<String> _monthNamesGenitive = [
  'января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
  'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря',
];

const List<String> _weekdayNames = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];

const List<String> _weekdayFullNames = [
  'понедельник', 'вторник', 'среда', 'четверг',
  'пятница', 'суббота', 'воскресенье',
];



/// Базовый экран календаря: месячная сетка + список занятий на выбранный день.
///
/// [syncRepository] и [authStorage] опциональны: по умолчанию используется
/// реальная синхронизация с бэкендом ([HttpSyncRepository]) и JWT-хранилище.
class CalendarScreen extends StatefulWidget {
  const CalendarScreen({super.key, this.syncRepository, this.authStorage});

  final SyncRepository? syncRepository;
  final AuthStorage? authStorage;

  @override
  State<CalendarScreen> createState() => _CalendarScreenState();
}

class _CalendarScreenState extends State<CalendarScreen> {
  final AppDatabase _db = AppDatabase.instance;

  late final AuthStorage _authStorage =
      widget.authStorage ?? AuthStorage();
  late final SyncRepository _syncRepository = widget.syncRepository ??
      HttpSyncRepository(authStorage: _authStorage);

  late DateTime _focusedMonth;
  late DateTime _selectedDate;
  List<Event> _monthEvents = [];
  bool _syncing = false;
  bool _isAuthenticated = false;
  String? _userEmail;
  DateTime _lastSync = DateTime.fromMillisecondsSinceEpoch(0, isUtc: true);

  @override
  void initState() {
    super.initState();
    final now = DateTime.now();
    _focusedMonth = DateTime(now.year, now.month);
    _selectedDate = DateTime(now.year, now.month, now.day);
    _refreshAuthState();
    _loadMonthEvents();
  }

  /// Обновляет состояние авторизации для AppBar (профиль / «Войти»).
  Future<void> _refreshAuthState() async {
    final authenticated = await _authStorage.isAuthenticated;
    final email = authenticated ? await _authStorage.userEmail : null;
    if (!mounted) return;
    setState(() {
      _isAuthenticated = authenticated;
      _userEmail = email;
    });
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

  /// День месяца -> цвет точки-индикатора (тип первого занятия дня).
  Map<int, Color> get _dayIndicatorColors {
    final colors = <int, Color>{};
    for (final event in _monthEvents) {
      final local = event.startTime.toLocal();
      if (local.year == _focusedMonth.year &&
          local.month == _focusedMonth.month) {
        colors.putIfAbsent(local.day, () => eventTypeColor(event.eventType));
      }
    }
    return colors;
  }

  /// События выбранного дня (сравнение в локальной таймзоне).
  List<Event> get _selectedDayEvents =>
      eventsOnDay(_monthEvents, _selectedDate);

  /// Синхронизация с бэкендом.
  ///
  /// Без сохранённого JWT сначала показывает диалог входа/регистрации.
  /// Ошибки API/сети показываются в SnackBar, не роняя приложение.
  Future<void> _sync() async {
    if (_syncing) return;

    if (!await _authStorage.isAuthenticated) {
      if (!mounted) return;
      final authenticated = await AuthDialog.show(context, _authStorage);
      if (!authenticated) return;
      await _refreshAuthState();
    }

    setState(() => _syncing = true);
    try {
      final localChanges = await _db.getPendingChanges(_lastSync);
      final remoteEvents =
          await _syncRepository.sync(_lastSync, localChanges);
      for (final event in remoteEvents) {
        // Сохраняем серверный updated_at без перезаписи клиентским временем,
        // иначе скачанные события снова попадут в local_changes.
        await _db.applyRemoteEvent(event);
      }
      _lastSync = DateTime.now().toUtc();
      await _loadMonthEvents();
      if (!mounted) return;
      _showSnackBar(
        'Синхронизация завершена: получено — ${remoteEvents.length}, '
        'отправлено — ${localChanges.length}',
      );
    } on ApiException catch (exception) {
      if (!mounted) return;
      _showSnackBar(exception.message, isError: true);
    } finally {
      if (mounted) setState(() => _syncing = false);
    }
  }

  void _showSnackBar(String message, {bool isError = false}) {
    final colors = Theme.of(context).colorScheme;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: isError ? colors.error : null,
      ),
    );
  }

  /// Открывает диалог входа/регистрации и обновляет состояние AppBar.
  Future<void> _openAuthDialog() async {
    final authenticated = await AuthDialog.show(context, _authStorage);
    if (authenticated) await _refreshAuthState();
  }

  /// Выход из аккаунта с подтверждением.
  ///
  /// Очищает JWT, локальную БД (события не должны перемешиваться между
  /// аккаунтами) и сбрасывает метку синхронизации.
  Future<void> _logout() async {
    final email = _userEmail;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Выход из аккаунта'),
        content: Text(
          email == null || email.isEmpty
              ? 'Выйти из аккаунта?'
              : 'Выйти из аккаунта $email?',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(false),
            child: const Text('Отмена'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(dialogContext).pop(true),
            child: const Text('Выйти'),
          ),
        ],
      ),
    );
    if (confirmed != true) return;

    await _authStorage.clear();
    await _db.clearAll();
    _lastSync = DateTime.fromMillisecondsSinceEpoch(0, isUtc: true);
    await _loadMonthEvents();
    if (!mounted) return;
    setState(() {
      _isAuthenticated = false;
      _userEmail = null;
    });
    _showSnackBar('Вы вышли из аккаунта');
  }

  /// Модальный просмотр деталей занятия; удаление — по кнопке в шторке.
  Future<void> _showEventDetails(Event event) async {
    final shouldDelete = await showEventDetailsSheet(context, event);
    if (!mounted || !shouldDelete) return;
    await _db.softDeleteEvent(event.id);
    await _loadMonthEvents();
    if (!mounted) return;
    _showSnackBar('Занятие удалено');
  }

  Future<void> _showCreateEventForm() async {
    final created = await showModalBottomSheet<Event>(
      context: context,
      isScrollControlled: true,
      builder: (_) => CreateEventSheet(date: _selectedDate),
    );

    if (created != null) {
      await _db.upsertEvent(created);
      await _loadMonthEvents();
    }
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
          _buildAccountButton(),
        ],
      ),
      body: Column(
        children: [
          _buildMonthHeader(),
          _buildWeekdayRow(),
          _buildMonthGrid(),
          const Divider(height: 1),
          _buildDayHeader(),
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

  /// Кнопка аккаунта: вход для гостя, меню профиля для авторизованного.
  Widget _buildAccountButton() {
    if (!_isAuthenticated) {
      return IconButton(
        icon: const Icon(Icons.login),
        tooltip: 'Войти',
        onPressed: _openAuthDialog,
      );
    }
    return PopupMenuButton<String>(
      icon: const Icon(Icons.account_circle_outlined),
      tooltip: 'Аккаунт',
      onSelected: (value) {
        if (value == 'logout') _logout();
      },
      itemBuilder: (context) => [
        PopupMenuItem<String>(
          enabled: false,
          child: ListTile(
            contentPadding: EdgeInsets.zero,
            leading: const Icon(Icons.person_outline),
            title: Text(_userEmail ?? 'Аккаунт'),
            subtitle: const Text('Вы вошли в аккаунт'),
          ),
        ),
        const PopupMenuDivider(),
        const PopupMenuItem<String>(
          value: 'logout',
          child: ListTile(
            contentPadding: EdgeInsets.zero,
            leading: Icon(Icons.logout),
            title: Text('Выйти из аккаунта'),
          ),
        ),
      ],
    );
  }

  /// Заголовок выбранного дня над списком занятий.
  Widget _buildDayHeader() {
    final selected = _selectedDate;
    final now = DateTime.now();
    final isToday = selected.year == now.year &&
        selected.month == now.month &&
        selected.day == now.day;
    final dateLabel =
        '${selected.day} ${_monthNamesGenitive[selected.month - 1]}';
    final title = isToday
        ? 'Сегодня, $dateLabel'
        : 'Расписание на $dateLabel, ${_weekdayFullNames[selected.weekday - 1]}';

    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
      child: Align(
        alignment: Alignment.centerLeft,
        child: Text(
          title,
          style: Theme.of(context).textTheme.titleSmall,
        ),
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
    final dayIndicatorColors = _dayIndicatorColors;
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
        final indicatorColor = dayIndicatorColors[day];
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
                      fontWeight: isSelected ? FontWeight.w600 : null,
                      color: isSelected ? colorScheme.onPrimary : null,
                    ),
                  ),
                  if (indicatorColor != null)
                    Icon(
                      Icons.circle,
                      size: 5,
                      // На активном фоне точка — контрастная (onPrimary),
                      // в остальных днях — цвет типа занятия.
                      color: isSelected
                          ? colorScheme.onPrimary
                          : indicatorColor,
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
      return _buildEmptyDayState();
    }
    return ListView.builder(
      padding: const EdgeInsets.fromLTRB(12, 4, 12, 88),
      itemCount: events.length,
      itemBuilder: (context, index) {
        final event = events[index];
        return EventCard(
          event: event,
          onTap: () => _showEventDetails(event),
        );
      },
    );
  }

  /// Дружелюбная заглушка, когда на выбранный день занятий нет.
  Widget _buildEmptyDayState() {
    final theme = Theme.of(context);
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            Icons.event_busy_outlined,
            size: 48,
            color: theme.colorScheme.outline,
          ),
          const SizedBox(height: 12),
          Text('На этот день занятий нет', style: theme.textTheme.bodyMedium),
        ],
      ),
    );
  }
}
