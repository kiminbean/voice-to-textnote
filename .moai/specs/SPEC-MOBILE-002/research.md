# Research: SPEC-MOBILE-002 Offline STT

## 1. Current STT Architecture

### 1.1 Backend STT Pipeline (`/Users/ibkim/Projects/voice-to-textnote/backend/ml/stt_engine.py`)

**Current Implementation:**
- **Platform-Adaptive Engine**: Uses mlx-whisper for macOS (Apple Silicon) and faster-whisper/openai-whisper for Linux
- **Default Models**: 
  - macOS: `mlx-community/whisper-small-mlx`
  - Linux: `small` (faster-whisper with CTranslate2 int8 for 4-6x speedup)
- **Loading Strategy**: Singleton pattern with lazy loading + server warm-up
- **Memory Management**: 19.2GB threshold monitoring (24GB * 80%)
- **Language Support**: Korean ("ko") as default, with initial_prompt vocabulary support

**Key Technical Details:**
```python
# Platform-specific backend selection
def _try_load_mlx(self) -> bool:  # macOS Apple Silicon
def _try_load_faster_whisper(self) -> bool:  # CPU int8/CUDA
def _try_load_whisper(self) -> bool:  # openai-whisper fallback

# STT Processing Pipeline
def transcribe(self, audio_path, language="ko", initial_prompt=None) -> dict
# Returns: {text, segments, language} with word_timestamps support
```

### 1.2 API Endpoints (`/Users/ibkim/Projects/voice-to-textnote/backend/app/api/v1/`)

**STT Endpoints:**
- `POST /api/v1/transcriptions` - Upload + STT task creation
- `GET /api/v1/transcriptions/{task_id}/status` - SSE polling fallback
- `GET /api/v1/transcriptions/{task_id}` - Result retrieval
- `POST /api/v1/transcriptions/batch` - Multi-file batch processing

**Processing Flow:**
1. Audio upload with format validation (WAV, MP3, M4A, OGG)
2. File size/duration checks (500MB max, 4 hours max)
3. Audio normalization to 16kHz mono WAV
4. Celery task enqueue for STT processing
5. Parallel diarization task auto-start
6. Redis caching + file system persistence

### 1.3 Celery Worker (`/Users/ibkim/Projects/voice-to-textnote/backend/workers/tasks/transcription_task.py`)

**Task Configuration:**
- Soft time limit: 60 minutes
- Hard time limit: 65 minutes  
- Max retries: 3 with exponential backoff
- Chunk processing for >30 minute audio
- Memory-optimized temporary file handling

**Processing Steps:**
1. Audio preprocessing (16kHz mono WAV conversion)
2. Whisper model loading (lazy + platform-specific)
3. STT inference with chunking for long audio
4. Result caching in Redis (24h TTL)
5. File system persistence for fallback

## 2. Flutter Client Audio Flow

### 2.1 Recording Architecture (`/Users/ibkim/Projects/voice-to-textnote/client/lib/`)

**Current Recording Pipeline:**
- **Recording Service**: BackgroundRecordingService for persistent recording
- **Audio Format**: M4A files stored in documents directory
- **State Management**: Riverpod RecordingProvider with RecordingStatus enum
- **Permissions**: Microphone permission handling with dialog fallbacks

**Recording Flow:**
```dart
// Current flow in recording_screen.dart
1. Permission check → PermissionDialog if needed
2. BackgroundRecordingService.startRecording()
3. Timer for elapsed seconds tracking
4. Recording stop → Meeting creation → Pipeline navigation
```

### 2.2 Audio API Integration (`/Users/ibkim/Projects/voice-to-textnote/client/lib/services/audio_api.dart`)

**Current Implementation:**
- Dio-based HTTP client
- Audio file streaming URL generation
- HEAD request for file availability checks
- No local audio processing capabilities

### 2.3 Pipeline Processing (`/Users/ibkim/Projects/voice-to-textnote/client/lib/providers/pipeline_provider.dart`)

**Current Pipeline Flow:**
1. Upload → STT → Diarization → Minutes → Summary
2. **SSE First, Polling Fallback**: Real-time updates with 3s polling fallback
3. **Parallel Processing**: STT and diarization run concurrently
4. **Progress Interpolation**: Step-based progress (0.0 → 1.0)
5. **Error Handling**: User-friendly Korean error messages

**Connectivity Patterns:**
- ConnectivityService with real-time monitoring
- OfflineBanner widget for offline status display
- Automatic SSE → polling fallback on network issues

## 3. Platform-Specific Considerations

### 3.1 iOS Support
**Current State:**
- Basic Flutter iOS app structure exists
- No platform-specific STT integration
- Standard microphone recording via record plugin
- No Swift ML frameworks detected

**Opportunities:**
- Apple ML Kit Speech-to-Text (iOS 13+)
- Core ML whisper.cpp models
- Background audio processing with AVAudioEngine

### 3.2 macOS Support  
**Current State:**
- macOS Flutter app with basic structure
- Whisper mlx already optimized for Apple Silicon
- No platform-specific audio processing
- Foreground service recording capability

**Advantages:**
- Already using mlx-whisper (MPS acceleration)
- Native Core Audio integration possible
- Apple Speech Framework available

### 3.3 Android Support
**Current State:**
- Android foreground recording service (RecordingService.kt)
- No ML inference integration
- Standard audio recording via record plugin
- No offline STT capabilities

**Android Capabilities:**
- TensorFlow Lite integration available
- Android Speech Recognition API
- MediaKit for audio processing
- Background service execution

## 4. On-Device Inference Options

### 4.1 whisper.cpp Integration
**Feasibility:**
- **Backend**: No whisper.cpp references detected in current codebase
- **Models**: Whisper small/medium models suitable for mobile (75MB-150MB)
- **Performance**: Real-time on modern devices (M2, Snapdragon 8 Gen 2)

**Mobile Integration Options:**
1. **Flutter Plugin**: whisper.cpp Dart wrapper (community)
2. **Platform Channels**: Native iOS/Android whisper.cpp integration
3. **Binary Distribution**: Precompiled libraries per platform

### 4.2 TensorFlow Lite
**Current State:**
- No TFLite references in Flutter pubspec.yaml
- No ML model files in project
- No TensorFlow dependencies

**Model Options:**
- Whisper TFLite variants (experimental)
- DistilWhisper quantized models
- Custom TFLite STT models

### 4.3 Platform-Specific Solutions

**iOS:**
- Apple ML Kit Speech (no model download required)
- Core ML whisper models (~100MB)
- AVAudioEngine for real-time processing

**Android:**
- Android Speech Recognition API (offline available)
- TensorFlow Lite Whisper models
- MediaPipe Speech-to-Text

**macOS:**
- mlx-whisper already in use (extend to client)
- Core ML whisper integration
- Native macOS speech framework

## 5. Existing Patterns & Reference Implementations

### 5.1 Async Processing Patterns
**Current Implementation:**
- **SSE First**: Real-time server-sent events
- **Polling Fallback**: 3-second interval polling on SSE failure
- **Task Cancellation**: Manual cancellation via _cancelled flag
- **Error Recovery**: Automatic retry with exponential backoff

**Reusable Patterns:**
```dart
// SSE + Polling fallback pattern
await _waitForCompletion(taskId, () => api.getStatus(taskId));
// Progress interpolation by step
final adjustedProgress = currentBase + (serverProgress * stepRange);
// Cancellation handling
if (_cancelled) throw Exception('Pipeline cancelled');
```

### 5.2 State Management Patterns
**Riverpod Implementation:**
- AsyncValue for loading/error states
- StateNotifier for complex state transitions
- Provider-scoped service lifecycle management

### 5.3 Audio Handling Patterns
**Current Approach:**
- Background recording with file persistence
- Format normalization in backend only
- No local audio processing on client

## 6. Risks & Constraints

### 6.1 Technical Risks

**Model Size Issues:**
- Whisper small: 75MB (download time on mobile)
- Whisper medium: 150MB (storage constraints)
- Apple ML Kit: 2GB+ download (not practical for offline)

**Performance Concerns:**
- Real-time processing requirements
- Battery impact of background inference
- Thermal throttling on mobile devices
- Memory limitations on mobile (2-4GB typical)

**Platform Limitations:**
- iOS app size limits (200MB App Store, 4GB Enterprise)
- Android background execution restrictions
- ML model format per-platform requirements

### 6.2 Integration Complexity

**Backend-Client Coordination:**
- Current architecture assumes server-based processing
- Need for hybrid offline/online synchronization
- Model versioning and updates across platforms

**Network Transition Handling:**
- Online → offline → online state management
- Partial processing recovery
- Data consistency across interruptions

### 6.3 User Experience Risks

**Battery Impact:**
- Local STT processing power consumption
- Background processing visibility
- Thermal management user feedback

**Storage Management:**
- Model download/cleanup lifecycle
- Temporary audio file handling
- User storage quota management

## 7. Recommendations

### 7.1 Phased Implementation Approach

**Phase 1: Foundation (2-3 weeks)**
1. **Offline Detection Enhancement**: 
   - Implement robust connectivity monitoring
   - Create offline-first state management
   - Add local task queue persistence

2. **Platform Audio Preprocessing**:
   - Implement local audio normalization (16kHz mono)
   - Add format validation on client before upload
   - Create local audio trimming capabilities

**Phase 2: iOS STT Integration (3-4 weeks)**
1. **iOS Whisper.cpp Integration**:
   - Create Swift whisper.cpp wrapper
   - Implement Core ML model loading
   - Add background task processing with Task API

2. **iOS Hybrid Processing**:
   - Local STT for short recordings (<5 min)
   - Fallback to server for long recordings
   - Background processing with power optimization

**Phase 3: Android STT Integration (3-4 weeks)**
1. **Android TensorFlow Lite**:
   - Implement TFLite Whisper integration
   - Optimize model for mobile performance
   - Add background service execution

2. **Android Speech API Fallback**:
   - Use Android Speech Recognition for quick results
   - Fallback to TFLite for offline accuracy
   - Battery optimization with smart scheduling

**Phase 4: macOS Integration (2-3 weeks)**
1. **Leverage Existing mlx-whisper**:
   - Extract mlx functionality for client use
   - Implement local processing for privacy
   - Add background transcription support

### 7.2 Technical Architecture Recommendations

**Hybrid Processing Strategy:**
- **Short Recordings (<5 min)**: Local STT processing
- **Long Recordings (>5 min)**: Server processing with offline caching
- **Network Unavailable**: Local processing with sync on restore

**Model Distribution:**
- **iOS**: Core ML format (Apple-optimized)
- **Android**: TensorFlow Lite quantized format
- **macOS**: Native mlx-whisper integration

**State Management:**
- Create unified offline/online pipeline state
- Implement task queue persistence with SQLite
- Add conflict resolution for partial results

**Error Handling:**
- Local processing fallback patterns
- Graceful degradation on resource constraints
- User-friendly offline/online transition messaging

### 7.3 Performance Optimization

**Mobile-Specific Optimizations:**
- Model quantization for reduced size/faster inference
- Background processing power limits
- Thermal monitoring and throttling
- Memory usage monitoring and cleanup

**Network Efficiency:**
- Progressive model download with compression
- Differential audio transmission (changed segments only)
- Smart retry strategies for interrupted uploads

### 7.4 User Experience Guidelines

**Offline Experience:**
- Clear offline status indicators
- Processing time estimation for local STT
- Background task progress notifications
- Power impact visibility

**Data Consistency:**
- Automatic sync on restore
- Conflict resolution for partial results
- Processing history across offline/online states

**Storage Management:**
- Automatic model cleanup with usage tracking
- User storage visibility and controls
- Temporary audio file lifecycle management

This comprehensive analysis provides the foundation for implementing offline STT processing while maintaining the existing server-first architecture and ensuring a smooth user experience across all platforms.
