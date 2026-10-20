import 'package:flutter/material.dart';
import 'services/api_service.dart';
import 'screens/login_screen.dart';
import 'screens/subjects_screen.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const TeacherAttendanceApp());
}

class TeacherAttendanceApp extends StatelessWidget {
  const TeacherAttendanceApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'بوابة الأستاذ - نظام الحضور',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF1E3A8A),
          primary: const Color(0xFF1E3A8A),
        ),
        useMaterial3: true,
      ),
      home: const _AuthGate(),
    );
  }
}

class _AuthGate extends StatefulWidget {
  const _AuthGate();

  @override
  State<_AuthGate> createState() => _AuthGateState();
}

class _AuthGateState extends State<_AuthGate> {
  Map<String, dynamic>? _savedTeacher;
  bool _checking = true;

  @override
  void initState() {
    super.initState();
    _checkSession();
  }

  Future<void> _checkSession() async {
    final teacher = await ApiService.getSavedTeacher();
    if (!mounted) return;
    setState(() {
      _savedTeacher = teacher;
      _checking = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    if (_checking) {
      return const Scaffold(
        body: Center(child: CircularProgressIndicator()),
      );
    }
    if (_savedTeacher != null) {
      return SubjectsScreen(teacher: _savedTeacher!);
    }
    return const LoginScreen();
  }
}
