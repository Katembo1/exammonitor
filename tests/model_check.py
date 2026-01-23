import tensorflow as tf
from tensorflow.keras.models import load_model
import os

MODEL_PATH = 'trained_model.keras'

if not os.path.exists(MODEL_PATH):
    print(f"ERROR: Model file not found at {MODEL_PATH}")
else:
    print(f"Loading model from {MODEL_PATH}...")
    try:
        model = load_model(MODEL_PATH, compile=False)
        
        print("\n" + "="*60)
        print("MODEL INSPECTION")
        print("="*60)
        
        print(f"\nModel Input Shape: {model.input_shape}")
        print(f"Model Output Shape: {model.output_shape}")
        
        print("\n--- First Few Layers ---")
        for i, layer in enumerate(model.layers[:5]):
            print(f"Layer {i}: {layer.name}")
            print(f"  Input Shape: {layer.input_shape}")
            print(f"  Output Shape: {layer.output_shape}")
        
        print("\n--- Model Summary ---")
        model.summary()
        
    except Exception as e:
        print(f"ERROR loading model: {e}")
        print("\nThis suggests the model file is corrupted or was saved incorrectly.")
        print("Recommendation: Delete the .keras files and retrain.")