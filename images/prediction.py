import matplotlib
matplotlib.use('Agg') # Set non-interactive backend BEFORE importing pyplot or anything that uses it

import numpy as np
from tensorflow.keras.preprocessing import image
from tensorflow.keras.models import load_model
from tensorflow.keras import backend as K
import matplotlib.pyplot as plt
import os
from django.conf import settings # To get BASE_DIR

# --- Model Loading ---

def dice_coef(y_true, y_pred):
    smooth = 1e-20
    # Ensure tensors are float32
    y_true_f = K.cast(y_true, 'float32')
    y_pred_f = K.cast(y_pred, 'float32')
    intersection = K.sum(y_true_f * y_pred_f)
    return (2. * intersection + smooth) / (K.sum(y_true_f) + K.sum(y_pred_f) + smooth)

def dice_coef_loss(y_true, y_pred):
    return 1 - dice_coef(y_true, y_pred)

def load_prediction_model(model_filename="unet_r.keras"):
    """Loads the Keras segmentation model."""
    # Construct the absolute path to the model file
    model_path = os.path.join(settings.BASE_DIR, 'ml_models', model_filename)
    if not os.path.exists(model_path):
        print(f"Error: Model file not found at {model_path}")
        # Optionally raise an exception or handle appropriately
        raise FileNotFoundError(f"Model file not found at {model_path}. Please place it in the 'ml_models' directory.")
        # return None # Or return None if you prefer handling it later

    try:
        model = load_model(
            model_path,
            custom_objects={'dice_coef': dice_coef, 'dice_coef_loss': dice_coef_loss}
        )
        print(f"Successfully loaded model from {model_path}")
        return model
    except Exception as e:
        print(f"Error loading model from {model_path}: {e}")
        # Optionally re-raise or handle
        raise e # Re-raise the exception to be caught by the caller
        # return None

# --- Prediction ---

def get_prediction_mask(png_image_path, model):
    """Generates a prediction mask for a given PNG image using the loaded model."""
    if not os.path.exists(png_image_path):
        print(f"Error: Input PNG file not found at {png_image_path}")
        return None

    try:
        img = image.load_img(png_image_path, color_mode='grayscale', target_size=(512, 512))
        img_array = image.img_to_array(img)
        img_array = np.expand_dims(img_array, axis=0)

        # Original notebook had transpose: (0, 3, 1, 2) - check if model expects channels_first or channels_last
        # Keras default is channels_last (batch, height, width, channels) -> (1, 512, 512, 1)
        # If your model expects channels_first (batch, channels, height, width) -> (1, 1, 512, 512), uncomment transpose
        img_array = np.transpose(img_array, (0, 3, 1, 2)) # Uncommented: Model expects channels_first

        img_array = img_array / 255.0  # Normalize

        prediction = model.predict(img_array)
        print(f"Prediction generated for {png_image_path}")

        # Squeeze the prediction to remove batch and channel dims if necessary
        # Result shape might be (1, 512, 512, 1) -> squeeze to (512, 512)
        pred_mask = np.squeeze(prediction)

        # Normalize mask to 0-1 range if it's not already
        if pred_mask.max() > 1.0:
             pred_mask = pred_mask / pred_mask.max() # More robust normalization
        pred_mask = np.clip(pred_mask, 0, 1) # Ensure values are strictly within [0, 1]


        return pred_mask # Return the raw mask array
    except Exception as e:
        print(f"Error during prediction for {png_image_path}: {e}")
        return None

# --- Saving Mask ---

def save_prediction_mask_image(processed_png_path, prediction_mask, output_path):
    """Generates and saves an image with the prediction mask overlaid onto the processed PNG."""
    if prediction_mask is None:
        print("Error: Prediction mask is None, cannot save overlay.")
        return False
    if not os.path.exists(processed_png_path):
        print(f"Error: Processed PNG {processed_png_path} not found for saving overlay visualization.")
        return False

    try:
        # Use Matplotlib to create the overlay image
        base_img = image.load_img(processed_png_path, color_mode='grayscale') # Ensure base is loaded as grayscale
        
        # Ensure mask is in the range [0, 1] for colormap
        mask_normalized = np.clip(prediction_mask, 0, 1)

        fig, ax = plt.subplots(figsize=(base_img.width / 100, base_img.height / 100), dpi=100)
        fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
        
        ax.imshow(base_img, cmap='gray') # Draw base image explicitly in grayscale
        # Overlay the mask with Reds colormap and alpha blending
        # Set vmin/vmax to ensure consistent mapping for boolean-like masks
        ax.imshow(mask_normalized, cmap='Reds', alpha=0.4, vmin=0, vmax=1)
        ax.axis('off')
        
        # Save the figure directly
        plt.savefig(output_path, bbox_inches='tight', pad_inches=0, dpi=100)
        plt.close(fig) # Close the figure to free memory

        print(f"Overlay image saved to {output_path}")
        return True
    except Exception as e:
        print(f"Error saving overlay image to {output_path}: {e}")
        import traceback
        traceback.print_exc() # Print detailed traceback
        return False 