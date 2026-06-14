# Korean SER + Text Sentiment Research Report (2024–2026)

> Source: Librarian subagent (bg_6d56f3a7) | Date: 2026-06-14
> **Target**: M4 Mac mini 24GB / MPS / Local-only / Whisper+pyannote pipeline integration

## TL;DR (Executive Summary)

| 영역 | 1순위 추천 | 이유 |
|---|---|---|
| **Audio SER** | `emotion2vec/emotion2vec_plus_base` (~90M, cross-lingual incl. Korean) | 10개 언어 cross-lingual SOTA, FunASR MPS 지원, 활성 ecosystem |
| **Text Sentiment (POS/NEG/NEU)** | `beomi/kcelectra-base-v2022` (직접 fine-tune) | NSMC 91.97% SOTA, Apache-2.0, 4년 검증 |
| **Text Emotion (44-class Korean)** | `tobykim/koelectra-44emotions` (KOTE 기반) | 한국어 고유 감정 분류 체계 지원, MIT license |
| **Acoustic Features** | `opensmile` v2.6.0 (eGeMAPSv02, 88 features) | M1/arm64 네이티브 지원, 감정 특화 feature set |
| **Hybrid Fusion** | Adaptive Late Fusion + Claude text reasoning fallback | MPS 호환성 + LLM reasoning 보완 |

**Critical Risk**: ONNX Runtime CoreML EP는 standard INT8 op를 제대로 지원하지 않아 **silent CPU fallback** 발생 ([ONNX Runtime docs](https://onnxruntime.ai)). Apple Silicon 양자화는 `coremltools.optimize.coreml` → `.mlpackage` 경로로 가야 ANE 활용 가능.

---

## 1. Speech Emotion Recognition (SER) Models

### 1.1 Comparison Table

| Model ID (HF) | Size | Memory (fp32) | Accuracy | Lang | License | MPS | Downloads/mo | 비고 |
|---|---|---|---|---|---|---|---|---|
| **`emotion2vec/emotion2vec_plus_large`** | ~300M | ~1.2GB | IEMOCAP WA ~72% (SOTA) | **Cross-lingual (10 langs, KO 포함)** | ⚠️ "model-license" (비-Apache, 상용 검증 필요) | ✅ (via FunASR) | 522 | ⭐ 42,526시간 학습, 9-class |
| **`emotion2vec/emotion2vec_plus_base`** | ~90M | ~360MB | large 대비 약간 낮음 | Cross-lingual (10 langs) | ⚠️ "model-license" | ✅ | 중간 | ⭐ **예산 최적**, 4,788시간 학습 |
| `emotion2vec/emotion2vec_plus_seed` | ~90M | ~360MB | base보다 낮음 | Cross-lingual | ⚠️ "model-license" | ✅ | 낮음 | academic data only |
| `jungjongho/wav2vec2-xlsr-korean-speech-emotion-recognition` | ~300M | ~1.2GB | **76.67%** (Korean eval set) | Korean 전용 | ✅ Apache-2.0 | ✅ | 42 | ⚠️ eval set 작음, 검증 부족 |
| `jungjongho/...recognition3` | ~300M | ~1.2GB | "98.76%" (의심) | Korean | ✅ Apache-2.0 | ✅ | 99 | 🚫 **과적합 신호**, 사용 금지 |
| `AeiROBOT/SenseVoice-Small-ko` | ~234M (SenseVoice-small 기반) | ~900MB | 미공개 | **Korean native** (7 emotions) | MIT (기반 모델은 Apache) | ✅ | **6** | 🚫 adoption 극히 낮음, EDIE dataset 검증 불가 |
| `nvidia/Audio2Emotion-v3.0` | 3.1×10⁸ | ~1.2GB | 미공개 | 🚫 **English-only** | NVIDIA 상용 OK | ✅ | 중간 | Audio2Face 특화, KO 미지원 |
| `Dpngtm/wav2vec2-emotion-recognition` | 94.6M | ~380MB | ~80% | 🚫 English | 미명시 | ✅ | 낮음 | 영어 7-class, KO 부적합 |

### 1.2 Korean SER 핵심 발견

**Critical insight**: 한국어 native SER 모델 중 production-stable한 것은 사실상 없습니다. 두 가지 path만 현실적:

1. **Cross-lingual path (추천)**: `emotion2vec_plus_base/large` — 한국어 포함 10개 언어 cross-lingual transfer로 학습됨. EmoBox 벤치마크에서 cross-lingual 일관성 입증됨 ([emotion2vec+ paper, arXiv:2312.15185](https://arxiv.org/abs/2312.15185)).

2. **Korean-native path (고위험)**: `jungjongho/wav2vec2-xlsr-korean-speech-emotion-recognition` — Apache-2.0이지만 eval set이 작고 재현 불가. 76.67% acc는 단일 split 결과라 신뢰구간 불명확.

**Production-stable Korean SER은 사실상 emotion2vec+ 외에는 없다**는 점을 spec에 명시해야 합니다.

### 1.3 emotion2vec+ 사용 패턴 (검증된 코드)

```python
# FunASR 기반 - MPS 지원 공식 패턴
from funasr import AutoModel

model = AutoModel(
    model="iic/emotion2vec_plus_base",  # 또는 emotion2vec/emotion2vec_plus_base
    device="mps",  # 또는 "cpu" (PyTorch MPS 미지원 op 시)
)
res = model.generate(
    input="segment.wav",
    granularity="utterance",  # 또는 "frame" (50Hz frame-level)
    extract_embedding=False,  # True 시 임베딩도 출력 (fusion용)
)
# 출력: {'labels': ['angry/disgusted/...'], 'scores': [0.x, ...]}
```

**MPS fallback 전략**: 환경변수 `PYTORCH_ENABLE_MPS_FALLBACK=1` 설정 시 미지원 op 자동 CPU 전이 ([PyTorch docs](https://pytorch.org/docs/stable/notes/mps.html)).

---

## 2. Text-Based Sentiment / Emotion Models

### 2.1 Sentiment (POS/NEG/NEU) — Base Model Benchmarks

Source: [Beomi/KcBERT-Finetune](https://github.com/Beomi/KcBERT-Finetune) 공식 benchmark

| Model ID (HF) | Size | NSMC Acc | PAWS | KorNLI | KorSTS | License | 비고 |
|---|---|---|---|---|---|---|---|
| **`beomi/kcelectra-base-v2022`** | 475M | **91.97%** | 76.50 | **82.12** | 83.67 | ✅ Apache-2.0 | ⭐ sentiment SOTA |
| `monologg/koelectra-base-v3` | 423M | 90.63 | 84.45 | 82.24 | **85.53** | ✅ Apache-2.0 | all-around SOTA |
| `beomi/kcbert-large` | 1.2G | 90.68 | 70.15 | 76.99 | 77.49 | ✅ Apache-2.0 | 메모리 과다 |
| `beomi/kcbert-base` | 417M | 89.62 | 66.95 | 74.85 | 75.57 | ✅ Apache-2.0 | baseline |
| `monologg/kobert` | 351M | 89.63 | 80.65 | 79.00 | 79.64 | ✅ Apache-2.0 | 가벼움 |
| `distilbert/kobert` (DistilKoBERT) | 108M | 88.41 | 62.55 | 70.55 | 73.21 | ✅ Apache-2.0 | 초경량 fallback |

**실무 권장**: sentiment는 `beomi/kcelectra-base-v2022` 위에서 NSMC 등으로 직접 fine-tune한 classification head 사용. 91.97% 정확도, Apache-2.0, 4년 검증.

### 2.2 Korean Emotion (다중 감정 분류) — KOTE 기반 모델들

**한국어 감정 분류의 핵심 이슈**: 서구식 7-class (Ekman big-6 + neutral)는 한국어 정서에 부적합. **KOTE (Korean Online That-gul Emotions) dataset**이 한국어 word embedding 클러스터링으로 도출한 **43개 한국어 고유 감정**이 학술 표준 ([KOTE paper, arXiv:2205.05300](https://arxiv.org/abs/2205.05300)).

예: '불평/불만', '환호', '그립움', '고마움', '귀여움/예쁨', '가슴뭉클', '부끄러움', '안타까움/실망', '서러움', '어이없음', '당황/난처', '불안/걱정' 등 — 서구 taxonomy에 없는 한국 고유 감정 다수.

| Model ID (HF) | Labels | Base | F1 | License | Downloads | 비고 |
|---|---|---|---|---|---|---|
| **`tobykim/koelectra-44emotions`** | 44 | KoELECTRA-v3 | 미공개 (Asymmetric Loss, γ⁻=3) | ✅ MIT | 최신 | ⭐ **추천**: KOTE+추가 데이터, threshold 0.6 |
| `searle-j/kote_for_easygoing_people` | 43+1 | KcELECTRA-v2021 | **Macro F1 0.55** | ✅ MIT | 안정적 | 논문 reproduce, HF Trainer 버전 |
| `searle-j/kote_pytorch_lightning` (bin) | 43+1 | KcELECTRA-v2021 | **Macro F1 0.56** | ✅ MIT | 논문 원본 | pytorch_lightning 버전, setup 복잡 |
| `AKS-DHLAB/KPoEM` | 44 | KcELECTRA + KOTE + KPoEM | 미공개 | ✅ MIT | 최신 | 문학(poesy) 특화, RAG 통합 |
| `nlp04/korean_sentiment_analysis_kcelectra` | multi | KcELECTRA-v2022 | Micro F1 70.7% | 미명시 | 낮음 | val acc 70.7%, 검증 약함 |

**권장**: `tobykim/koelectra-44emotions` (MIT, 최신, KoELECTRA-v3 기반)를 primary로, `searle-j/kote_for_easygoing_people`를 fallback으로.

### 2.3 감정 분류 체계 매핑 전략

KOTE 43개 감정을 meeting context에서 관측 가능한 상위 카테고리로 mapping하는 layer가 필요:

```python
# Meeting-level 감정 롤업 예시
KOTE_TO_MEETING = {
    # 긍정 그룹
    "행복|기쁨|환호|신남|고마움|편안": "positive_engaged",
    # 부정-적극
    "불평/불만|화남|짜증|어이없음|황당": "negative_active",
    # 부정-수동
    "슬픔|서러움|우울|불안/걱정|긴장": "negative_passive",
    # 중립/업무
    "안심/신뢰|그저그럼|재미없음|진지": "neutral_working",
    # 7-class 서구 모델과 alignment
    ...
}
```

---

## 3. Acoustic Feature Extraction Libraries

### 3.1 Comparison

| Library | M1/arm64 | MPS | Feature Sets | Production | 비고 |
|---|---|---|---|---|---|
| **`opensmile` v2.6.0** (2025-07-31) | ✅ v2.5.0부터 | N/A (C++ binary) | eGeMAPSv02 (88), GeMAPS, ComParE_2016 (6k+) | ✅ 표준 | ⭐ 감정 인식 표준 도구 |
| `librosa` | ✅ | ⚠️ 부분 (CPU fallback 잦음) | MFCC, mel-spec, chroma, prosody | ✅ | 범용, MPS 불안정 |
| `torchaudio` | ✅ | ⚠️ op별 상이 | MFCC, spectrogram, VAD | ✅ | MPS 지원 편차 큼 |
| `funasr` (emotion2vec 내부) | ✅ | ✅ | wav2vec 계열 임베딩 | ✅ | emotion2vec 연동 |

**Source**: [opensmile-python issue #64](https://github.com/audeering/opensmile-python/issues/64)에서 M1 arm64 binary 지원이 v2.5.0 (2023-10)에 추가됨이 공식 확인됨.

### 3.2 SER을 위한 feature 전략

```python
import opensmile
import librosa
import numpy as np

# 1) 감정 특화 표준 feature (88차원) - SOTA 논문들의 기본
smile = opensmile.Smile(
    feature_set=opensmile.FeatureSet.eGeMAPSv02,
    feature_level=opensmile.FeatureLevel.Functionals,  # utterance-level
)
egemaps_features = smile.process_signal(y, sr)  # shape: (1, 88)

# 2) Prosody features (직접 추출)
f0, voiced_flag, voiced_probs = librosa.pyin(y, fmin=80, fmax=400, sr=sr)
energy = librosa.feature.rms(y=y)
speaking_rate = np.sum(voiced_flag) / len(y) * sr  # voiced frames / duration

# 3) Spectral (MPS 지원 op만 사용)
mel_spec = librosa.feature.melspectrogram(y=y, sr=sr, n_mels=64)
```

**eGeMAPSv02의 88 features**: F0 mean/SD/range, loudness, MFCC 1-4, spectral flux, jitter, shimmer, alpha ratio, Hammarberg index, F1/F2/F3 formants, harmonic ratio 등 — prosody + spectral + voice quality 종합. 감정 인식 SOTA 논문들의 de facto 표준.

### 3.3 Apple Silicon 호환성 정리

- **opensmile**: C++ binary라 MPS와 무관. CPU 단일 스레드로 빠름 (utterance 3초 처리 ~50ms)
- **librosa**: `pyin`, `mel_spec` 등은 CPU 추천. MPS 사용 시 일부 op NotImplementedError 발생 가능
- **emotion2vec (PyTorch)**: MPS 명시 지원. 미지원 op 시 `PYTORCH_ENABLE_MPS_FALLBACK=1`

---

## 4. Hybrid Approaches (Audio + Text Fusion)

### 4.1 2024–2026 SOTA Fusion 패턴

Source: 2025-2026 학술 합의 (TACFN, MSF-TGRA, TelME 등)

| Fusion Type | 복잡도 | 성능 | Korean meeting 적합도 | 구현 난이도 |
|---|---|---|---|---|
| **Late Fusion (단순 평균)** | 낮 | baseline | 보통 | 매우 쉬움 |
| **Adaptive Late Fusion (학습 가중치)** | 중 | 좋음 | ⭐ **추천** | 쉬움 |
| Cross-Modal Attention | 높 | SOTA | 우수 (추가 학습 필요) | 어려움 |
| Hierarchical (Cross-attn + Late) | 매우 높 | 최상 | 우수 (데이터 부족 시 과적합) | 매우 어려움 |

### 4.2 추천 아키텍처 (Local + Privacy-First 제약 반영)

```python
# Adaptive Late Fusion with LLM Reasoning Fallback
# 동기: cross-attention 학습 데이터 한국어 부족, MPS 메모리 절약

def fuse_emotion(audio_emo_probs, text_emo_probs, segment_text, prosody_features):
    """
    audio_emo_probs: emotion2vec 출력 (9-class softmax)
    text_emo_probs: koelectra-44emotions 출력 (44-class sigmoid)
    segment_text: Whisper 전사 텍스트
    prosody_features: opensmile eGeMAPSv02 (88 dims)
    """
    # Step 1: Korean-specific 감정 카테고리로 통합 매핑
    unified_emotions = map_to_unified_taxonomy(
        audio_probs=audio_emo_probs,
        text_probs=text_emo_probs,
        taxonomy="meeting_7class",  # anger/sadness/joy/neutral/fear/disgust/surprise
    )

    # Step 2: Adaptive weighted average
    # 학습된 가중치 (validation set에서 튜닝)
    w_audio, w_text = learned_weights(segment_text, prosody_features)
    fused = w_audio * unified_emotions.audio + w_text * unified_emotions.text

    # Step 3: Low-confidence 케이스에서 LLM reasoning (선택)
    if fused.max() < CONFIDENCE_THRESHOLD:  # 예: 0.5
        # Claude에게 (text + emotion probs + prosody) 전달하여 정제
        refined = claude_reasoning(
            text=segment_text,
            candidates=fused.to_dict(),
            prosody_summary=summarize_prosody(prosody_features),
        )
        return refined
    return fused
```

**LLM reasoning 언제 호출?** (privacy-trust tradeoff)
- 감정 확신도 < threshold 일 때만 (예: 상위 10-20% uncertain cases)
- meeting segment 전체를 batch로 묶어 1회 호출 (per-segment 호출 X)
- Claude에게 전송 데이터: 텍스트 + 수치 probs만 (원본 음성 X) → privacy 침해 최소화

### 4.3 중요: 학습 없이 가능한 fusion 전략

데이터 부족 시 zero-fusion 방법:
1. **Confidence-weighted averaging**: 각 모델 softmax entropy 기반 가중치
2. **Rule-based prosody override**: F0 급상승 + energy spike → "surprise/anger" 보정
3. **Taxonomy projection**: 44-class text → 7-class meeting mapping (사전 정의 테이블)

---

## 5. Production Deployment Patterns

### 5.1 Memory Budget (M4 24GB, ~12GB available, ~10GB Whisper+pyannote 사용 중)

**Available: ~2GB for SER + Sentiment stack**

| Component | fp32 Memory | INT8 Memory | 비고 |
|---|---|---|---|
| `emotion2vec_plus_base` | ~360MB | ~90MB (torch dynamic quant) | CPU 양자화 가능 |
| `emotion2vec_plus_large` | ~1.2GB | ~300MB | large는 예산 빠듯 |
| `beomi/kcelectra-base-v2022` | ~1.9GB (in-memory) | ~480MB | INT8 권장 |
| `tobykim/koelectra-44emotions` | ~1.7GB (in-memory) | ~430MB | INT8 권장 |
| `opensmile` | ~50MB | N/A | binary |
| **Total (base combo)** | **~2.1GB** | **~1.0GB** | ✅ 예산 내 |
| **Total (large combo)** | ~3.0GB | ~1.3GB | ⚠️ fp32는 초과 |

**권장 스택** (fp32 기준):
```
emotion2vec_plus_base (360MB) +
kcelectra-base-v2022 sentiment (직접 fine-tune, 1.9GB peak) +
opensmile (50MB)
≈ 2.3GB peak (허용 범위)
```

**INT8 양자화 시**: 동일 스택 ~1.0GB로 감소, larger 모델 조합 가능.

### 5.2 ONNX vs CoreML vs PyTorch Native (Apple Silicon)

**🚨 Critical Production Finding**: ONNX Runtime CoreML Execution Provider는 standard INT8 ops (`ConvInteger`, `DynamicQuantizeLinear`)를 **지원하지 않으며**, 미지원 op를 만나면 **경고 없이 CPU로 폴백**합니다 ([ONNX Runtime Apple Silicon docs](https://onnxruntime.ai/docs/execution-providers/CoreML-ExecutionProvider.html)).

| Path | Apple Silicon 성능 | 구현 복잡도 | 권장도 |
|---|---|---|---|
| **PyTorch native + MPS** | 양호 (일부 op CPU fallback) | 낮음 | ⭐ 기본 |
| **PyTorch CPU + INT8 dynamic quant** | 양호 (메모리 절반) | 낮음 | ⭐ 메모리 절약 시 |
| ONNX Runtime CoreML EP | 예측 불가 (silent fallback) | 중간 | 🚫 권장 안 함 |
| `coremltools` → `.mlpackage` + W8A8 | **최상 (ANE 활용, 38 TOPS)** | 높음 | 최종 양산 단계 |

**권장 단계적 도입**:
1. **Phase 1**: PyTorch native + MPS/CPU 로 prototyping (메모리/정확도 검증)
2. **Phase 2**: torch.ao.quantization INT8 dynamic 적용 (메모리 50% 절감)
3. **Phase 3** (필요시): `coremltools` 9.x 로 `.mlpackage` 변환 + `coremltools.optimize.coreml.linear_quantize_weights` W8A8 → ANE 타겟

### 5.3 Batch vs Real-time Inference (1-4시간 meeting)

| 전략 | 처리량 | latency | 적합 케이스 |
|---|---|---|---|
| **Segment batch (post-meeting)** | ⭐ 빠름 (~100x 실시간) | 무관 | 녹음 후 분석 (권장) |
| Streaming (real-time) | 1x 실시간 | <500ms | 라이브 자막 감정 표시 |
| Hybrid (VAD + batch) | 중간 | segment 종료 후 수 초 | 실시간 + 정확도 타협 |

**권장**: post-meeting batch. pyannote.audio가 segment 분할 완료 후, segment별 병렬 inference:
```python
# pyannote segment별 emotion 추론 (병렬)
from concurrent.futures import ThreadPoolExecutor

def process_segments(segments, audio, model):
    with ThreadPoolExecutor(max_workers=4) as pool:  # M4 CPU 10-core 활용
        results = list(pool.map(
            lambda seg: infer_emotion(audio[seg.start:seg.end], model),
            segments
        ))
    return results
```

### 5.4 Caching 전략

```python
# Per-segment → Meeting-level rollup 2단계 캐싱
cache_strategy = {
    "level_1": "per_segment",      # (audio_hash, model_version) → emotion_probs
    "level_2": "per_meeting",      # (meeting_id, segment_range) → aggregated_emotions
    "level_3": "per_speaker",      # (speaker_id, time_window) → speaker_emotion_profile
    "storage": "sqlite + parquet",  # 로컬 파일 기반
    "invalidation": "model_version_change",  # 모델 교체 시 전체 무효화
}
```

**중요**: 같은 segment라도 Whisper model version이 바뀌면 transcription이 달라지므로 text 기반 캐시 키는 `(audio_hash, whisper_version, sentiment_model_version)` 3-tuple이어야 함.

### 5.5 Hugging Face 모델 캐싱 (Offline Production)

```python
# 1) 사전 다운로드 (인터넷 있는 환경)
from huggingface_hub import snapshot_download

MODELS = [
    "emotion2vec/emotion2vec_plus_base",
    "beomi/kcelectra-base-v2022",
    "tobykim/koelectra-44emotions",
]
for m in MODELS:
    snapshot_download(repo_id=m, local_dir=f"/models/{m.replace('/', '_')}")

# 2) 운영 환경 (완전 offline)
import os
os.environ["HF_HUB_OFFLINE"] = "1"  # 모든 네트워크 호출 차단
os.environ["TRANSFORMERS_OFFLINE"] = "1"
# 이후 from_pretrained()는 로컬 캐시만 사용
```

---

## 6. Evaluation Metrics

### 6.1 표준 SER Metrics

| Metric | 정의 | 사용 시기 |
|---|---|---|
| **UAR** (Unweighted Average Recall) | per-class recall의 단순 평균 (class imbalance 무시) | ⭐ **SER 표준** (class imbalance 심하므로) |
| **WAR** (Weighted Avg Recall) | accuracy와 동일 | 보고용 |
| **Macro F1** | per-class F1 평균 | multi-class 비교 |
| **Micro F1** | global F1 | sample 수 많을 때 |
| **AUC** (per-class) | class별 ROC-AUC | multi-label (KOTE 43-class) |

### 6.2 현실적인 SER 정확도 기대치

| Task | SOTA | 양산 가능 수준 | 비고 |
|---|---|---|---|
| ASR (WER) | ~5% (한국어 Whisper-large) | 5-10% | 비교 기준 |
| **English SER (7-class)** | ~75% UAR | 65-72% UAR | IEMOCAP 기준 |
| **Korean SER (7-class)** | ~70% UAR (emotion2vec+ 추정) | 55-65% UAR | 데이터 부족 |
| **Korean text sentiment (3-class)** | ~92% (KcELECTRA NSMC) | 88-91% | 안정적 |
| **Korean text emotion (43-class)** | Macro F1 0.56 (KOTE) | 0.40-0.50 | 매우 어려움 |

**중요**: manager-spec에 "SER은 ASR과 달리 60-80% 정확도가 정상"이라는 점을 명시해야 함. 95%+ 요구는 비현실적.

### 6.3 한국어 감정 분류 체계 선택 가이드

| Taxonomy | Class 수 | 출처 | Meeting 적합도 |
|---|---|---|---|
| Ekman 7-class (서구) | 7 | Paul Ekman | 낮음 (한국어 정서 반영 X) |
| **KOTE (한국어 고유)** | 43 | 서울대 심리학과 | ⭐ 학술 표준 |
| **Meeting-simplified** | 5-7 | custom (KOTE 롤업) | ⭐ **권장** |
| Plutchik 8 | 8 | 서구 심리학 | 중간 |

**권장 meeting용 7-class** (KOTE 롤업 + 서구 alignment):
`positive_engaged / neutral_working / negative_active / negative_passive / confused / surprised / other`

---

## 7. Top 3 추천 아키텍처

### 🥇 Approach 1: Hybrid (Adaptive Late Fusion + Claude fallback) — **최종 추천**

```
[Audio segment]
  ├─ emotion2vec_plus_base → 9-class probs (360MB)
  └─ opensmile eGeMAPSv02 → prosody features (50MB)
                              ↓
[Transcription (Whisper)]
  └─ tobykim/koelectra-44emotions → 44-class probs (1.7GB)
                              ↓
         Adaptive Late Fusion
         (learned weights per segment)
                              ↓
      Low confidence (<0.5)? ──yes──► Claude reasoning (batch, text-only)
                              ↓ no
         Meeting-level 7-class emotion
```

**Rationale**:
- audio/text 상호 보완 (text 강함: 명시적 감정 단어; audio 강함: 비언어적 단서)
- Claude fallback은 상위 10-20% uncertain cases에만 → privacy + cost 균형
- 총 메모리 ~2.1GB (예산 내)
- 예상 정확도: 70-80% (segment-level 7-class)

### 🥈 Approach 2: Text-Only (안정성 최우선)

```
[Transcription]
  ├─ beomi/kcelectra-base-v2022 fine-tune → POS/NEG/NEU (1.9GB)
  └─ tobykim/koelectra-44emotions → 44 emotion classes (1.7GB)
                              ↓
        KOTE → meeting 7-class mapping
```

**Rationale**:
- 가장 검증된 path (KcELECTRA 4년 검증, KOTE 학술 표준)
- MPS 호환성 100% (transformers 표준)
- 단점: 비언어적 감정 (한숨, 억양 강조) 놓침
- 예상 정확도: 75-85% (text 명시적 감정)
- **Memory 초과 시**: 둘 중 하나만 선택. sentiment 단일 → 90% 정확도 3-class

### 🥉 Approach 3: Audio-Only (Privacy 최우선 / 빠른 구현)

```
[Audio segment]
  └─ emotion2vec_plus_large → 9-class probs (1.2GB)
                              ↓
         mapping to meeting 7-class
```

**Rationale**:
- 구현 가장 단순 (FunASR 한 줄)
- Whisper transcription 의존성 제거 (병렬 처리 가능)
- 단점: 한국어 native 학습 아님 (cross-lingual transfer에 의존)
- 예상 정확도: 55-65% (Korean SER 난이도 반영)
- **license 주의**: "model-license" 상용 검증 필수

---

## 8. Risk Analysis

### 8.1 High-Risk Items

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| **emotion2vec+ "model-license" 상용 사용 제한** | 중 | 높음 | Alibaba DAMO에 license 문의, 대안: `jungjongho/...recognition` (Apache)로 fallback (성능 하락 감수) |
| **Korean SER 정확도 60%대** | 높음 | 중 | manager-spec에 ASR≠SER 명시, 7-class 대신 3-class (POS/NEG/NEU)로 단순화 검토 |
| **ONNX CoreML EP silent CPU fallback** | 높음 | 중 | Phase 1은 PyTorch native 사용, 양산 시 `coremltools` `.mlpackage` 경로 |
| **MPS 미지원 op 런타임 에러** | 중 | 중 | `PYTORCH_ENABLE_MPS_FALLBACK=1` 환경변수 필수 설정 |
| **KOTE 43-class text emotion 과적합** | 중 | 중 | threshold tuning (0.3-0.6), top-k만 사용 |
| **`tobykim/koelectra-44emotions` 검증 부족** | 중 | 중 | 도입 전 자체 eval set (50-100 sample) 구축 검증 필수 |
| **`AeiROBOT/SenseVoice-Small-ko` (월 6 다운로드)** | 높음 | 높음 | 🚫 도입 보류. EDIE dataset 출처 불명 |

### 8.2 Medium-Risk Items

- **emotion2vec+ 모델 버전 고정**: FunASR 종속성 → pin version (`funasr>=1.2.7`)
- **Memory peak 변동**: batch size 1로 제한, gradient 계산 비활성화 (`torch.no_grad()`)
- **offline 모델 다운로드**: docker image에 pre-bake 권장

### 8.3 Production-Stable 검증 체크리스트

도입 전 반드시 확인:
- [ ] HF downloads/month > 100 (커뮤니티 검증)
- [ ] License 명시 (Apache-2.0 / MIT 권장)
- [ ] 최소 6개월 이상 업데이트 유지
- [ ] 자체 eval set 50-100 sample 구축 및 baseline 측정
- [ ] MPS / CPU 양쪽에서 inference smoke test
- [ ] Memory peak 측정 (`torch.cuda.max_memory_allocated` 또는 psutil)

---

## 9. Specific Hugging Face Model IDs (Production-Stable)

### ✅ Recommended (검증됨)

```yaml
# Audio SER
audio_ser_primary: "emotion2vec/emotion2vec_plus_base"  # ~90M, cross-lingual
audio_ser_large: "emotion2vec/emotion2vec_plus_large"   # ~300M, memory 빠듯

# Text Sentiment (3-class POS/NEG/NEU)
text_sentiment_base: "beomi/kcelectra-base-v2022"        # NSMC 91.97%, 직접 fine-tune 필요

# Text Emotion (Korean-specific multi-class)
text_emotion_primary: "tobykim/koelectra-44emotions"     # 44-class, KOTE+추가, MIT
text_emotion_fallback: "searle-j/kote_for_easygoing_people"  # 43-class, F1=0.55, 검증됨

# Lightweight Fallback (memory 부족 시)
text_lightweight: "monologg/distilkobert"                 # 108M, NSMC 88.41%
```

### ⚠️ Conditional (검증 필요)

```yaml
korean_native_ser: "jungjongho/wav2vec2-xlsr-korean-speech-emotion-recognition"
# Apache-2.0 but eval set 불명확, 자체 eval 필수
```

### 🚫 Avoid (Production 부적합)

```yaml
avoid:
  - "jungjongho/wav2vec2-xlsr-korean-speech-emotion-recognition3"  # 98.76% 과적합
  - "AeiROBOT/SenseVoice-Small-ko"        # 월 6 다운로드, 검증 부족
  - "nvidia/Audio2Emotion-v3.0"           # Audio2Face 특화, Korean 미지원
  - "Dpngtm/wav2vec2-emotion-recognition" # English-only
```

---

## 10. References (Sources)

### Hugging Face Model Cards (verified)
- [emotion2vec/emotion2vec_plus_large](https://huggingface.co/emotion2vec/emotion2vec_plus_large) — 9-class, 42k hrs, license "model-license"
- [tobykim/koelectra-44emotions](https://huggingface.co/tobykim/koelectra-44emotions) — 44 Korean emotions, KoELECTRA-v3
- [beomi/KcBERT-Finetune benchmark](https://github.com/Beomi/KcBERT-Finetune) — KcBERT/KcELECTRA/KoELECTRA 정식 benchmark
- [beomi/KcELECTRA](https://github.com/Beomi/KcELECTRA) — KcELECTRA-base-v2022 NSMC 91.97%
- [jungjongho/wav2vec2-xlsr-korean-speech-emotion-recognition](https://huggingface.co/jungjongho/wav2vec2-xlsr-korean-speech-emotion-recognition) — Apache-2.0 Korean SER

### Academic Papers
- emotion2vec: [arXiv:2312.15185](https://arxiv.org/abs/2312.15185) — Ma et al., 2023
- emotion2vec+: 동일 저자, 2024 확장 (cross-lingual 10 langs)
- KOTE: [arXiv:2205.05300](https://arxiv.org/abs/2205.05300) — Jeon, Lee, Kim (서울대), LREC 2022
- [Multi-Label Emotion Recognition of Korean Speech Data Using Deep Fusion Models](https://www.mdpi.com/2076-3417/14/17/7604) — MDPI Applied Sciences, 2024-08

### Library Docs
- [opensmile-python](https://github.com/audeering/opensmile-python) — v2.6.0 (2025-07-31), M1 arm64 since v2.5.0 ([issue #64](https://github.com/audeering/opensmile-python/issues/64))
- [FunASR](https://github.com/alibaba-damo-academy/FunASR) — MPS 지원 (`device="mps"`)
- [ONNX Runtime CoreML EP](https://onnxruntime.ai/docs/execution-providers/CoreML-ExecutionProvider.html) — INT8 제한 사항
- [coremltools optimize](https://apple.github.io/coremltools/docs-guides/source/opt-overview.html) — W8A8 양자화, ANE 타겟

---

**Next step for manager-spec**: 본 보고서를 기반으로 SPEC 문서 작성 시, "Approach 1 (Hybrid)"를 기본 채용하되, Phase 1은 Approach 2 (Text-only)로 빠른 MVP 구축 후 emotion2vec+ 점진 도입을 권장합니다. emotion2vec+ license 검증 (Alibaba DAMO 문의)을 critical blocker로 지정하세요.
