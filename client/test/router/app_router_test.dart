import 'package:flutter_test/flutter_test.dart';
import 'package:voice_to_textnote/router/app_router.dart';

void main() {
  group('externalDeepLinkRedirect', () {
    test('maps voicetextnote result host links to result route', () {
      expect(
        externalDeepLinkRedirect(
          Uri.parse('voicetextnote://result/meeting-123'),
        ),
        '/result/meeting-123',
      );
    });

    test('maps voicetextnote summary host links to result route', () {
      expect(
        externalDeepLinkRedirect(
          Uri.parse('voicetextnote://summary/summary-456'),
        ),
        '/result/summary-456',
      );
    });

    test('maps path-style voicetextnote links to result route', () {
      expect(
        externalDeepLinkRedirect(
          Uri.parse('voicetextnote:///result/meeting-789'),
        ),
        '/result/meeting-789',
      );
    });

    test('ignores normal app routes', () {
      expect(externalDeepLinkRedirect(Uri.parse('/result/local')), isNull);
    });
  });
}
