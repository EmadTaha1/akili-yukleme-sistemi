import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

class ApiService {
  static const String _prefTokenKey = 'auth_token';
  static const String _prefTeacherNameKey = 'teacher_name';
  static const String _prefTeacherEmailKey = 'teacher_email';
  static const String _prefTeacherIdKey = 'teacher_id';
  static const String _prefBaseUrlKey = 'api_base_url';

  static String _defaultBaseUrl() {
    if (kIsWeb) {
      final host = Uri.base.host;
      if (host.isNotEmpty) {
        return 'http://$host:5000';
      }
    }
    return 'http://192.168.1.171:5000';
  }

  static Future<String> getBaseUrl() async {
    final prefs = await SharedPreferences.getInstance();
    final saved = prefs.getString(_prefBaseUrlKey);
    if (saved != null && saved.trim().isNotEmpty) {
      return saved.trim();
    }
    return _defaultBaseUrl();
  }

  static Future<void> setBaseUrl(String url) async {
    final prefs = await SharedPreferences.getInstance();
    var cleaned = url.trim();
    if (cleaned.endsWith('/')) {
      cleaned = cleaned.substring(0, cleaned.length - 1);
    }
    await prefs.setString(_prefBaseUrlKey, cleaned);
  }

  static Future<String?> getToken() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(_prefTokenKey);
  }

  static Future<Map<String, dynamic>?> getSavedTeacher() async {
    final prefs = await SharedPreferences.getInstance();
    final token = prefs.getString(_prefTokenKey);
    if (token == null || token.isEmpty) return null;
    return {
      'id': prefs.getInt(_prefTeacherIdKey) ?? 0,
      'name': prefs.getString(_prefTeacherNameKey) ?? '',
      'email': prefs.getString(_prefTeacherEmailKey) ?? '',
    };
  }

  static Future<Map<String, String>> _headers() async {
    final token = await getToken();
    return {
      'Content-Type': 'application/json',
      if (token != null && token.isNotEmpty) 'Authorization': 'Bearer $token',
    };
  }

  /// Login teacher and store token + profile locally
  static Future<Map<String, dynamic>> login(
    String email,
    String password,
  ) async {
    final baseUrl = await getBaseUrl();
    final uri = Uri.parse('$baseUrl/api/login');

    try {
      final response = await http
          .post(
            uri,
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode({
              'email': email.trim(),
              'password': password.trim(),
            }),
          )
          .timeout(const Duration(seconds: 10));

      final data = jsonDecode(utf8.decode(response.bodyBytes));

      if (response.statusCode == 200 && data['status'] == 'ok') {
        final prefs = await SharedPreferences.getInstance();
        final teacher = data['teacher'] as Map<String, dynamic>;
        await prefs.setString(_prefTokenKey, data['token'] as String);
        await prefs.setInt(_prefTeacherIdKey, teacher['id'] as int);
        await prefs.setString(_prefTeacherNameKey, teacher['name'] as String);
        await prefs.setString(_prefTeacherEmailKey, teacher['email'] as String);
        return {'success': true, 'teacher': teacher};
      } else {
        return {
          'success': false,
          'message': data['message'] ?? 'بيانات الدخول غير صحيحة',
        };
      }
    } catch (e) {
      return {
        'success': false,
        'message':
            'تعذر الاتصال بالسيرفر ($baseUrl). تأكد من تشغيل السيرفر واتصالك بنفس الشبكة.',
      };
    }
  }

  /// Logout and clear session
  static Future<void> logout() async {
    try {
      final baseUrl = await getBaseUrl();
      final headers = await _headers();
      await http
          .post(Uri.parse('$baseUrl/api/logout'), headers: headers)
          .timeout(const Duration(seconds: 4));
    } catch (_) {}
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_prefTokenKey);
    await prefs.remove(_prefTeacherNameKey);
    await prefs.remove(_prefTeacherEmailKey);
    await prefs.remove(_prefTeacherIdKey);
  }

  /// Fetch subjects assigned to the logged-in teacher
  static Future<Map<String, dynamic>> getSubjects() async {
    final baseUrl = await getBaseUrl();
    final headers = await _headers();

    try {
      final response = await http
          .get(Uri.parse('$baseUrl/api/subjects'), headers: headers)
          .timeout(const Duration(seconds: 10));

      if (response.statusCode == 401) {
        await logout();
        return {'success': false, 'unauthorized': true};
      }

      final data = jsonDecode(utf8.decode(response.bodyBytes));
      if (response.statusCode == 200 && data['status'] == 'ok') {
        return {
          'success': true,
          'subjects': data['subjects'] as List<dynamic>,
        };
      }
      return {
        'success': false,
        'message': data['message'] ?? 'حدث خطأ أثناء جلب المواد',
      };
    } catch (e) {
      return {
        'success': false,
        'message': 'تعذر الاتصال بالسيرفر لجلب المواد المقررة.',
      };
    }
  }

  /// Fetch quick dashboard stats for the logged-in teacher
  static Future<Map<String, dynamic>?> getDashboardStats() async {
    final baseUrl = await getBaseUrl();
    final headers = await _headers();

    try {
      final response = await http
          .get(Uri.parse('$baseUrl/api/dashboard/stats'), headers: headers)
          .timeout(const Duration(seconds: 8));

      if (response.statusCode == 200) {
        final data = jsonDecode(utf8.decode(response.bodyBytes));
        if (data['status'] == 'ok') {
          return data['stats'] as Map<String, dynamic>;
        }
      }
    } catch (_) {}
    return null;
  }

  /// Fetch enrolled students for a specific subject
  static Future<List<dynamic>> getSubjectStudents(int subjectId) async {
    final baseUrl = await getBaseUrl();
    final headers = await _headers();

    final response = await http
        .get(
          Uri.parse('$baseUrl/api/subjects/$subjectId/students'),
          headers: headers,
        )
        .timeout(const Duration(seconds: 10));

    if (response.statusCode == 200) {
      final data = jsonDecode(utf8.decode(response.bodyBytes));
      if (data['status'] == 'ok') {
        return data['students'] as List<dynamic>;
      }
    }
    return [];
  }
}
