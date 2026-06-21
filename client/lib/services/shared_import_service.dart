import 'package:flutter/services.dart';

class SharedImportPayload {
  final String? sourceUrl;
  final String? text;
  final String? title;
  final String? mimeType;

  const SharedImportPayload({
    this.sourceUrl,
    this.text,
    this.title,
    this.mimeType,
  });

  bool get hasContent =>
      (sourceUrl != null && sourceUrl!.isNotEmpty) ||
      (text != null && text!.isNotEmpty);

  Map<String, String> toQueryParameters() {
    return {
      if (sourceUrl != null && sourceUrl!.isNotEmpty) 'shared_url': sourceUrl!,
      if (text != null && text!.isNotEmpty) 'shared_text': text!,
      if (title != null && title!.isNotEmpty) 'shared_title': title!,
      if (mimeType != null && mimeType!.isNotEmpty) 'shared_mime': mimeType!,
    };
  }

  factory SharedImportPayload.fromPlatformMap(Map<dynamic, dynamic> value) {
    final rawText = (value['text'] as String?)?.trim() ?? '';
    final mimeType = (value['mimeType'] as String?)?.trim();
    final url = _firstUrl(rawText);
    final content =
        url == null ? rawText : rawText.replaceFirst(url, '').trim();
    final title = _titleFromUrl(url) ?? (value['title'] as String?)?.trim();

    return SharedImportPayload(
      sourceUrl: url,
      text: content.isEmpty ? null : content,
      title: title,
      mimeType: mimeType,
    );
  }

  factory SharedImportPayload.fromQueryParameters(Map<String, String> query) {
    return SharedImportPayload(
      sourceUrl: _emptyToNull(query['shared_url']),
      text: _emptyToNull(query['shared_text']),
      title: _emptyToNull(query['shared_title']),
      mimeType: _emptyToNull(query['shared_mime']),
    );
  }

  static String? _firstUrl(String text) {
    final match =
        RegExp(r'https?://[^\s]+', caseSensitive: false).firstMatch(text);
    return match?.group(0)?.replaceAll(RegExp(r'[)\].,;]+$'), '');
  }

  static String? _titleFromUrl(String? url) {
    if (url == null || url.isEmpty) return null;
    final uri = Uri.tryParse(url);
    final host = uri?.host.replaceFirst(RegExp(r'^www\.'), '');
    if (host == null || host.isEmpty) return null;
    if (host.contains('youtube.com') || host.contains('youtu.be')) {
      return 'YouTube transcript';
    }
    return '$host transcript';
  }

  static String? _emptyToNull(String? value) {
    final trimmed = value?.trim();
    return trimmed == null || trimmed.isEmpty ? null : trimmed;
  }
}

class SharedImportService {
  SharedImportService({
    MethodChannel channel =
        const MethodChannel('com.voicetextnote.app/shared_import'),
  }) : _channel = channel;

  final MethodChannel _channel;

  Future<SharedImportPayload?> consumeInitialSharedImport() async {
    return _consume('consumeInitialSharedImport');
  }

  Future<SharedImportPayload?> consumeLatestSharedImport() async {
    return _consume('consumeLatestSharedImport');
  }

  Future<SharedImportPayload?> _consume(String method) async {
    final value = await _channel.invokeMethod<Map<dynamic, dynamic>>(method);
    if (value == null || value.isEmpty) return null;

    final payload = SharedImportPayload.fromPlatformMap(value);
    return payload.hasContent ? payload : null;
  }
}
