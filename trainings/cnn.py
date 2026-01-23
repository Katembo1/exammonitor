import tensorflow as tf
import os
import sys

# --- Configuration (Update these if your environment changes) ---

# Base directory where your data folders (train, valid, test) and label_map.pbtxt reside
BASE_DIR = os.getcwd()
# The pattern to find your TFRecord files
TRAIN_TFRECORD_PATTERN = os.path.join(BASE_DIR, 'train', '*.tfrecord')
VALID_TFRECORD_PATTERN = os.path.join(BASE_DIR, 'valid', '*.tfrecord')
LABEL_MAP_PATH = os.path.join(BASE_DIR,'train', 'Cheating_label_map.pbtxt')

# Model and Training Parameters
NUM_CLASSES = 3 
IMAGE_SIZE = 224  # CRITICAL: Must match inference script (224x224)
BATCH_SIZE = 32
EPOCHS = 20 

# Save paths
SAVE_PATH = 'trained_model.keras' 
CHECKPOINT_PATH = 'best_model_checkpoint.keras'

# Steps per epoch
STEPS_PER_EPOCH = 65 
VALIDATION_STEPS = 14

# --- 1. Label Map Parsing ---
def load_label_map(label_map_path):
    """Checks if the label map exists and confirms class configuration."""
    if not os.path.exists(label_map_path):
        print(f"ERROR: Label map not found at {label_map_path}")
        sys.exit(1)
        
    print(f"Label map PBTXT found at: {label_map_path}")
    print(f"Assuming {NUM_CLASSES} classes: 'normal', 'cheating', 'good'.")
    return True

# --- 2. TFRecord Parsing Function ---
def parse_tf_example(serialized_example):
    """
    Parses a single tf.Example record using the Object Detection API keys.
    ENSURES: Output is (224, 224, 3) RGB images
    """
    feature_description = {
        'image/encoded': tf.io.FixedLenFeature([], tf.string),
        'image/object/class/label': tf.io.VarLenFeature(tf.int64),
        'image/object/bbox/xmin': tf.io.VarLenFeature(tf.float32),
        'image/object/bbox/xmax': tf.io.VarLenFeature(tf.float32),
        'image/object/bbox/ymin': tf.io.VarLenFeature(tf.float32),
        'image/object/bbox/ymax': tf.io.VarLenFeature(tf.float32),
        'image/format': tf.io.FixedLenFeature([], tf.string, default_value='jpeg'),
    }
    
    example = tf.io.parse_single_example(serialized_example, feature_description)
    
    # CRITICAL: Decode as RGB (3 channels) - matches inference script
    image = tf.image.decode_jpeg(example['image/encoded'], channels=3)
    
    # CRITICAL: Resize to exactly 224x224 - matches inference script
    image = tf.image.resize(image, (IMAGE_SIZE, IMAGE_SIZE))
    
    # Normalize to [0, 1] - matches inference script
    image = tf.cast(image, tf.float32) / 255.0
    
    # Verify shape
    image = tf.ensure_shape(image, [IMAGE_SIZE, IMAGE_SIZE, 3])
    
    # Parse label
    label_sparse = example['image/object/class/label']
    
    if tf.size(label_sparse.values) > 0:
        # Assuming 1-indexed labels in TFRecords, convert to 0-indexed
        label_id = tf.cast(label_sparse.values[0] - 1, tf.int32)
        label_id = tf.clip_by_value(label_id, 0, NUM_CLASSES - 1)
    else:
        label_id = tf.constant(0, dtype=tf.int32) 
    
    label = tf.one_hot(label_id, NUM_CLASSES)
    
    return image, label


# --- 3. Dataset Pipeline Creation ---
def create_dataset(tfrecord_pattern, is_training=False):
    """Loads, shuffles, and batches data from TFRecord files."""
    
    file_list = tf.io.gfile.glob(tfrecord_pattern)
    if not file_list:
        print(f"ERROR: No TFRecord files found at: {tfrecord_pattern}")
        sys.exit(1)
        
    print(f"Found {len(file_list)} TFRecord files at {tfrecord_pattern}")
    
    dataset = tf.data.Dataset.from_tensor_slices(file_list)
    dataset = dataset.interleave(
        lambda x: tf.data.TFRecordDataset(x),
        cycle_length=tf.data.AUTOTUNE,
        num_parallel_calls=tf.data.AUTOTUNE
    )
    
    if is_training:
        dataset = dataset.shuffle(buffer_size=10000)
        dataset = dataset.repeat() 
    
    dataset = dataset.map(parse_tf_example, num_parallel_calls=tf.data.AUTOTUNE)
    dataset = dataset.batch(BATCH_SIZE).prefetch(tf.data.AUTOTUNE)
    
    return dataset


# --- 4. Model Definition (EfficientNetB0 for Transfer Learning) ---
def create_transfer_model():
    """
    Defines a model using MobileNetV2 pre-trained backbone.
    ENSURES: Input shape is (224, 224, 3)
    """
    print("\nSetting up MobileNetV2 base model...")
    print(f"Input shape: ({IMAGE_SIZE}, {IMAGE_SIZE}, 3)")
    
    # CRITICAL: Explicitly define input layer with correct shape
    inputs = tf.keras.Input(shape=(IMAGE_SIZE, IMAGE_SIZE, 3), name='input_layer')

    # Load pre-trained MobileNetV2 without top layer
    base_model = tf.keras.applications.MobileNetV2(
        input_shape=(IMAGE_SIZE, IMAGE_SIZE, 3),
        include_top=False,
        weights='imagenet'
    )
    
    # Freeze base model for transfer learning
    base_model.trainable = False
    
    # Pass inputs through base model
    x = base_model(inputs, training=False)
    
    # Add classification head
    x = tf.keras.layers.GlobalAveragePooling2D(name='global_avg_pool')(x)
    x = tf.keras.layers.Dense(128, activation='relu', name='dense_128')(x)
    x = tf.keras.layers.Dropout(0.4, name='dropout')(x)
    
    # Output layer: 3 classes (normal, cheating, good)
    outputs = tf.keras.layers.Dense(NUM_CLASSES, activation='softmax', name='output_layer')(x)
    
    # Create model
    model = tf.keras.Model(inputs=inputs, outputs=outputs, name='exam_monitor_model')
    
    # Verify input shape
    print(f"Model created. Input shape: {model.input_shape}")
    assert model.input_shape == (None, IMAGE_SIZE, IMAGE_SIZE, 3), "Model input shape mismatch!"
    
    return model


# --- 5. Main Training Function ---
def main():
    """Execute the data loading, model compilation, and training."""
    
    print("\n" + "="*70)
    print("EXAM MONITORING MODEL TRAINING PIPELINE")
    print("="*70)
    print(f"Image size: {IMAGE_SIZE}x{IMAGE_SIZE}x3 (RGB)")
    print(f"Number of classes: {NUM_CLASSES}")
    print(f"Batch size: {BATCH_SIZE}")
    print(f"Epochs: {EPOCHS}")
    print(f"Training steps per epoch: {STEPS_PER_EPOCH}")
    print(f"Validation steps: {VALIDATION_STEPS}")
    print("="*70 + "\n")

    # 1. Check Data and Load Datasets
    load_label_map(LABEL_MAP_PATH)
    
    try:
        train_dataset = create_dataset(TRAIN_TFRECORD_PATTERN, is_training=True)
        valid_dataset = create_dataset(VALID_TFRECORD_PATTERN)
        
        # Verify a sample batch
        print("\nVerifying dataset shape...")
        for images, labels in train_dataset.take(1):
            print(f"Sample batch - Images shape: {images.shape}, Labels shape: {labels.shape}")
            assert images.shape[1:] == (IMAGE_SIZE, IMAGE_SIZE, 3), "Dataset image shape mismatch!"
            print("✓ Dataset verification passed!\n")
            
    except Exception as e:
        print(f"\nFATAL ERROR during dataset creation: {e}")
        return

    # 2. Define Model
    model = create_transfer_model()
    
    print("\n" + "="*70)
    print("MODEL ARCHITECTURE")
    print("="*70)
    model.summary()
    print("="*70 + "\n")

    # 3. Compile Model
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=1e-3),
        loss='categorical_crossentropy',
        metrics=['accuracy']
    )

    # 4. Define Callbacks
    callbacks = [
        tf.keras.callbacks.ModelCheckpoint(
            filepath=CHECKPOINT_PATH, 
            monitor='val_loss', 
            save_best_only=True,
            save_weights_only=False, 
            verbose=1
        ),
        tf.keras.callbacks.EarlyStopping(
            monitor='val_loss', 
            patience=5, 
            restore_best_weights=True,
            verbose=1
        ),
        tf.keras.callbacks.ReduceLROnPlateau(
            monitor='val_loss',
            factor=0.5,
            patience=3,
            verbose=1,
            min_lr=1e-7
        )
    ]

    # 5. Train Model
    print(f"\nStarting Training for {EPOCHS} epochs...")
    print("="*70 + "\n")
    
    try:
        history = model.fit(
            train_dataset,
            epochs=EPOCHS,
            steps_per_epoch=STEPS_PER_EPOCH,
            validation_data=valid_dataset,
            validation_steps=VALIDATION_STEPS,
            callbacks=callbacks,
            verbose=1
        )
    except KeyboardInterrupt:
        print("\n\nTraining interrupted by user.")
        print("Saving current model state...")
        model.save(SAVE_PATH)
        print(f"Model saved to: {SAVE_PATH}")
        return
    except Exception as e:
        print(f"\nTraining failed with error: {e}")
        return

    # 6. Save Final Model
    print("\n" + "="*70)
    print("SAVING FINAL MODEL")
    print("="*70)
    
    model.save(SAVE_PATH)
    print(f"✓ Final model saved to: {SAVE_PATH}")
    
    # Verify saved model
    print("\nVerifying saved model...")
    loaded_model = tf.keras.models.load_model(SAVE_PATH, compile=False)
    print(f"✓ Saved model input shape: {loaded_model.input_shape}")
    assert loaded_model.input_shape == (None, IMAGE_SIZE, IMAGE_SIZE, 3), "Saved model shape mismatch!"
    
    print("\n" + "="*70)
    print("TRAINING COMPLETE!")
    print("="*70)
    print(f"Model files created:")
    print(f"  - {SAVE_PATH} (final model)")
    print(f"  - {CHECKPOINT_PATH} (best checkpoint)")
    print(f"\nYou can now run your inference script (app2.py)")
    print("="*70 + "\n")

if __name__ == '__main__':
    main()