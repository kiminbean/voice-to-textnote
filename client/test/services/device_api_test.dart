import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:voice_to_textnote/services/device_api.dart';

class MockDio extends Mock implements Dio {}

void main() {
  late MockDio mockDio;
  late DeviceApi deviceApi;

  setUp(() {
    mockDio = MockDio();
    deviceApi = DeviceApi(mockDio, platform: 'ios');
  });

  group('DeviceApi', () {
    test('registerDeviceToken sends POST to /devices/register with correct body', () async {
      // Arrange
      when(() => mockDio.post(
            any(),
            data: any(named: 'data'),
          )).thenAnswer((_) async => Response(
            data: {'status': 'success'},
            statusCode: 200,
            requestOptions: RequestOptions(path: ''),
          ));

      // Act
      await deviceApi.registerDeviceToken('test_token_123');

      // Assert
      verify(() => mockDio.post(
            '/devices/register',
            data: {
              'fcm_token': 'test_token_123',
              'platform': 'ios',
            },
          )).called(1);
    });
  });
}
