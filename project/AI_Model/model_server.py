import json
import os
import pickle
import sys
import librosa
import numpy as np


def find_latest_model(model_dir):
    """Find the latest .pkl or .pckl model file."""
    candidates = []
    for filename in os.listdir(model_dir):
        if filename.endswith((".pkl", ".pckl")):
            full_path = os.path.join(model_dir, filename)
            # Skip scaler files
            if "scaler" not in filename.lower():
                candidates.append((os.path.getmtime(full_path), full_path))
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][1]


def load_model(model_path):
    """Load model from pickle file."""
    with open(model_path, "rb") as handle:
        return pickle.load(handle)


def load_scaler(model_dir):
    """Load the scaler if it exists."""
    scaler_path = os.path.join(model_dir, "scaler.pkl")
    if os.path.exists(scaler_path):
        try:
            with open(scaler_path, "rb") as f:
                return pickle.load(f)
        except Exception as e:
            print(json.dumps({"type": "error", "message": f"Failed to load scaler: {e}"}), file=sys.stderr)
            return None
    return None


def extract_audio_features(audio_path, sr=22050):
    """
    Load audio file and extract 114 features (MFCCs + spectral data).
    - Resample to 22,050 Hz
    - Extract 13 MFCC coefficients (including energy) * 8 aggregations = 104 features
    - Extract spectral centroid, rolloff, zero crossing rate = 10 features
    Total: ~114 features
    """
    try:
        # Load audio at specified sample rate (resamples if needed)
        y, sr = librosa.load(audio_path, sr=sr, mono=True)
        
        # Extract MFCCs (13 coefficients by default)
        mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
        
        # Compute statistics across time for each coefficient
        mfcc_features = []
        for mfcc in mfccs:
            mfcc_features.extend([
                np.mean(mfcc), np.std(mfcc),
                np.min(mfcc), np.max(mfcc),
                np.median(mfcc), np.percentile(mfcc, 25),
                np.percentile(mfcc, 75), np.var(mfcc)
            ])
        
        # Extract additional spectral features
        spectral_centroid = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
        spectral_rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr)[0]
        zcr = librosa.feature.zero_crossing_rate(y)[0]
        
        spectral_features = [
            np.mean(spectral_centroid), np.std(spectral_centroid),
            np.mean(spectral_rolloff), np.std(spectral_rolloff),
            np.mean(zcr), np.std(zcr),
            np.mean(np.abs(y)), np.std(np.abs(y)),
            np.max(np.abs(y)), np.min(np.abs(y))
        ]
        
        # Combine all features into a single vector
        all_features = np.array(mfcc_features + spectral_features, dtype=np.float32)
        
        return all_features.reshape(1, -1)
    except Exception as exc:
        raise Exception(f"Failed to extract audio features: {exc}")


def format_response(result):
    """Format model output as JSON-serializable string."""
    if isinstance(result, (str, int, float)):
        return str(result)
    if isinstance(result, np.ndarray):
        return str(result.tolist())
    if isinstance(result, np.generic):
        return str(result.item())
    return json.dumps(result, ensure_ascii=True, default=str)


def main():
    model_dir = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()

    # Load the model
    model_path = find_latest_model(model_dir)
    if not model_path:
        print(json.dumps({"type": "error", "message": "No .pkl or .pckl model found."}))
        sys.stdout.flush()
        return

    try:
        loaded_data = load_model(model_path)
        
        # Extract actual model and scaler from dict wrapper if needed
        if isinstance(loaded_data, dict) and "model" in loaded_data:
            model = loaded_data["model"]
            scaler = loaded_data.get("scaler", None)
            model_info = f"{loaded_data.get('model_name', os.path.basename(model_path))}"
        else:
            model = loaded_data
            scaler = load_scaler(model_dir)
            model_info = os.path.basename(model_path)
        
        print(json.dumps({"type": "ready", "message": f"Loaded model: {model_info}"}))
        sys.stdout.flush()
    except Exception as exc:
        print(json.dumps({"type": "error", "message": f"Failed to load model: {exc}"}))
        sys.stdout.flush()
        return

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            payload = json.loads(line)
            request_id = payload.get("id")
            audio_path = payload.get("audioPath", "")

            # Load audio to check volume level
            y, sr = librosa.load(audio_path, sr=22050, mono=True)
            
            # Calculate RMS (root mean square) energy
            rms_energy = np.sqrt(np.mean(y**2))
            max_amplitude = np.max(np.abs(y))
            
            # High volume requirement - need loud/clear audio to trigger alerts
            # Anything quieter than these thresholds = forced to prediction 0 with high confidence
            LOW_VOLUME_THRESHOLD = 0.02  # RMS threshold (need significant energy)
            LOW_AMPLITUDE_THRESHOLD = 0.1  # Max amplitude threshold (need clear audio)
            
            is_low_volume = rms_energy < LOW_VOLUME_THRESHOLD or max_amplitude < LOW_AMPLITUDE_THRESHOLD
            
            # Extract features from the audio file
            features = extract_audio_features(audio_path)

            # Scale features if scaler is available
            if scaler:
                features = scaler.transform(features)

            # Run inference on the extracted features
            try:
                if hasattr(model, "predict"):
                    prediction = model.predict(features)[0]
                    
                    # Try to get probabilities/confidence scores
                    confidence = None
                    probabilities = None
                    if hasattr(model, "predict_proba"):
                        proba = model.predict_proba(features)[0]
                        confidence = float(np.max(proba))
                        probabilities = [round(float(p), 6) for p in proba]
                    
                    # Get class labels if available
                    classes = None
                    if hasattr(model, "classes_"):
                        classes = [int(c) if isinstance(c, (int, np.integer)) else str(c) for c in model.classes_]
                    
                    # HARDCODED OVERRIDE: Force prediction to 0 when volume is too low
                    original_prediction = prediction
                    if is_low_volume:
                        prediction = 0
                        confidence = 1.0  # High confidence that low volume = no alert
                        probabilities = [1.0, 0.0] if len(probabilities or []) == 2 else None
                        print(f"[OVERRIDE] Low volume detected (RMS: {rms_energy:.6f}, Max: {max_amplitude:.6f}) - forcing prediction to 0", file=sys.stderr)
                    
                    result = {
                        "prediction": int(prediction) if isinstance(prediction, (int, np.integer)) else str(prediction),
                        "confidence": round(confidence, 4) if confidence else None,
                        "probabilities": probabilities,
                        "classes": classes,
                        "num_features": features.shape[1],
                        "rms_energy": round(float(rms_energy), 6),
                        "max_amplitude": round(float(max_amplitude), 6),
                        "was_overridden": is_low_volume,
                        "original_prediction": int(original_prediction) if is_low_volume else None
                    }
                    
                    # Log raw values to stderr for debugging
                    print(f"[MODEL RAW] Prediction: {prediction} | RMS: {rms_energy:.6f} | Max: {max_amplitude:.6f} | Probabilities: {probabilities} | Classes: {classes} | Features: {features.shape[1]}", file=sys.stderr)
                    
                    response_text = format_response(result)
                else:
                    response_text = f"Model has no predict method"
            except Exception as pred_err:
                response_text = f"Prediction error: {pred_err}"

            print(json.dumps({"type": "response", "id": request_id, "message": response_text}, ensure_ascii=True, default=str))
            sys.stdout.flush()
        except Exception as exc:
            print(json.dumps({"type": "error", "message": f"Inference error: {exc}"}, ensure_ascii=True, default=str))
            sys.stdout.flush()


if __name__ == "__main__":
    main()
