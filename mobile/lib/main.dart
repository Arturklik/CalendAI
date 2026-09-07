import 'package:flutter/material.dart';

import 'api/api_client.dart';
import 'repositories/api_sync_repository.dart';
import 'screens/calendar_screen.dart';
import 'screens/login_screen.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final client = ApiClient();
  await client.loadToken();
  runApp(CalendAIApp(client: client));
}

class CalendAIApp extends StatelessWidget {
  const CalendAIApp({super.key, required this.client});

  final ApiClient client;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'CalendAI',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: Colors.blue),
        useMaterial3: true,
      ),
      home: client.hasToken
          ? CalendarScreen(syncRepository: ApiSyncRepository(client))
          : LoginScreen(client: client),
    );
  }
}
