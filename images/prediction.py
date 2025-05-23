import matplotlib
matplotlib.use('Agg') # Set non-interactive backend BEFORE importing pyplot or anything that uses it

import numpy as np
from tensorflow.keras.preprocessing import image
from tensorflow.keras.models import load_model
from tensorflow.keras import backend as K
import matplotlib.pyplot as plt
import os
import torch
import cv2
import segmentation_models_pytorch as smp
from albumentations import Compose, Resize
from albumentations.pytorch import ToTensorV2
from django.conf import settings # To get BASE_DIR
from PIL import Image

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

def load_prediction_model(model_filename="DeepLabV3Plus_model.pth"):
    """Loads the PyTorch segmentation model."""
    # Construct the absolute path to the model file
    model_path = os.path.join(settings.BASE_DIR, 'ml_models', model_filename)
    if not os.path.exists(model_path):
        print(f"Error: Model file not found at {model_path}")
        # Optionally raise an exception or handle appropriately
        raise FileNotFoundError(f"Model file not found at {model_path}. Please place it in the 'ml_models' directory.")

    try:
        # Create DeepLabV3Plus model
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        model = smp.DeepLabV3Plus(classes=1, in_channels=1)
        model.load_state_dict(torch.load(model_path, map_location=device))
        model.to(device)
        model.eval()
        print(f"Successfully loaded model from {model_path}")
        return model
    except Exception as e:
        print(f"Error loading model from {model_path}: {e}")
        # Optionally re-raise or handle
        raise e # Re-raise the exception to be caught by the caller

def find_contours(mask):
    """Finds contours in a binary mask using OpenCV."""
    if isinstance(mask, torch.Tensor):
        mask = mask.squeeze().cpu().numpy()
    mask = (mask > 0.5).astype(np.uint8) * 255
    contours, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    contour_mask = np.zeros_like(mask)
    cv2.drawContours(contour_mask, contours, -1, 255, thickness=2)  # Увеличил толщину для лучшей видимости
    return contour_mask

# --- Prediction ---

def get_prediction_mask(png_image_path, model):
    """Generates a prediction mask for a given PNG image using the loaded model."""
    if not os.path.exists(png_image_path):
        print(f"Error: Input PNG file not found at {png_image_path}")
        return None

    try:
        # Load the original image to get its dimensions
        orig_img = Image.open(png_image_path)
        orig_width, orig_height = orig_img.size
        print(f"Original image dimensions: {orig_width}x{orig_height}")
        
        # Convert PIL Image to numpy array
        img_array = np.array(orig_img)
        
        # If image is RGB, convert to grayscale
        if len(img_array.shape) == 3 and img_array.shape[2] == 3:
            img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
            
        print(f"Image array shape before preprocessing: {img_array.shape}")
        
        # Define the transformations for the model input (resize to 256x256)
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        transform = Compose([
            Resize(256, 256),  # Модель ожидает 256x256
            ToTensorV2()
        ])
        
        # Apply transformations
        transformed = transform(image=img_array)
        img_tensor = transformed["image"].unsqueeze(0).float()  # Add batch dimension
        img_tensor = img_tensor.to(device)
        
        # Normalize values between 0 and 1
        if torch.max(img_tensor) > 0:
            img_tensor = img_tensor / torch.max(img_tensor)
        
        print(f"Input tensor shape: {img_tensor.shape}")
        
        # Make prediction
        with torch.no_grad():
            prediction = torch.sigmoid(model(img_tensor))
            print(f"Prediction tensor shape: {prediction.shape}")
            
            # Get contours of the prediction
            pred_mask = find_contours(prediction > 0.5)
            print(f"Contour mask shape: {pred_mask.shape}")
            
            # Resize contour mask back to original image dimensions
            pred_mask_resized = cv2.resize(pred_mask, (orig_width, orig_height), 
                                          interpolation=cv2.INTER_NEAREST)
            
            print(f"Resized contour mask shape: {pred_mask_resized.shape}")
        
        return pred_mask_resized
    except Exception as e:
        print(f"Error during prediction for {png_image_path}: {e}")
        import traceback
        traceback.print_exc()
        return None

# --- Saving Mask ---

def save_contour_mask_for_extraction(processed_png_path, prediction_mask, output_path):
    """Создает и сохраняет изображение только с контурами (без заливки) для извлечения точек."""
    if prediction_mask is None:
        print("Error: Prediction mask is None, cannot save contour mask.")
        return False
    if not os.path.exists(processed_png_path):
        print(f"Error: Processed PNG {processed_png_path} not found for saving contour mask.")
        return False

    try:
        # Load original image
        orig_img = Image.open(processed_png_path)
        orig_width, orig_height = orig_img.size
        print(f"Original image for contour mask: {orig_width}x{orig_height}")
        
        # Ensure mask has the right dimensions
        mask_height, mask_width = prediction_mask.shape
        if mask_width != orig_width or mask_height != orig_height:
            print(f"Resizing mask from {mask_width}x{mask_height} to {orig_width}x{orig_height}")
            prediction_mask = cv2.resize(prediction_mask, (orig_width, orig_height), 
                                        interpolation=cv2.INTER_NEAREST)
        
        # Create contour mask (thin lines only)
        binary_mask = (prediction_mask > 127).astype(np.uint8)
        contours, _ = cv2.findContours(binary_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Create image with only contour lines on black background
        contour_mask = np.zeros((orig_height, orig_width, 3), dtype=np.uint8)
        if contours:
            # Draw only the contour lines (no fill)
            largest_contour = max(contours, key=cv2.contourArea)
            cv2.polylines(contour_mask, [largest_contour], isClosed=True, color=(255, 0, 0), thickness=2)
        
        # Save the contour mask
        contour_image = Image.fromarray(contour_mask, 'RGB')
        contour_image.save(output_path, 'PNG')
        print(f"Contour mask for extraction saved to {output_path}")
        return True
    except Exception as e:
        print(f"Error saving contour mask to {output_path}: {e}")
        import traceback
        traceback.print_exc()
        return False

def save_prediction_mask_image(processed_png_path, prediction_mask, output_path):
    """Generates and saves an image with the prediction mask overlaid onto the processed PNG."""
    if prediction_mask is None:
        print("Error: Prediction mask is None, cannot save overlay.")
        return False
    if not os.path.exists(processed_png_path):
        print(f"Error: Processed PNG {processed_png_path} not found for saving overlay visualization.")
        return False

    try:
        # Load original image
        orig_img = Image.open(processed_png_path)
        orig_width, orig_height = orig_img.size
        print(f"Original image for overlay: {orig_width}x{orig_height}")
        
        # Ensure mask has the right dimensions by explicit resizing if needed
        mask_height, mask_width = prediction_mask.shape
        if mask_width != orig_width or mask_height != orig_height:
            print(f"Resizing mask from {mask_width}x{mask_height} to {orig_width}x{orig_height}")
            prediction_mask = cv2.resize(prediction_mask, (orig_width, orig_height), 
                                        interpolation=cv2.INTER_NEAREST)
        
        # Convert original image to numpy array
        img_array = np.array(orig_img)
        
        # Convert to RGB if grayscale
        if len(img_array.shape) == 2:
            img_array = cv2.cvtColor(img_array, cv2.COLOR_GRAY2RGB)
        elif len(img_array.shape) == 3 and img_array.shape[2] == 4:
            img_array = cv2.cvtColor(img_array, cv2.COLOR_RGBA2RGB)
        
        # Create filled contour mask
        # Find contours from the prediction mask
        binary_mask = (prediction_mask > 127).astype(np.uint8)
        contours, _ = cv2.findContours(binary_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Create filled mask
        filled_mask = np.zeros((orig_height, orig_width, 3), dtype=np.uint8)
        if contours:
            # Fill the largest contour with red color
            largest_contour = max(contours, key=cv2.contourArea)
            cv2.fillPoly(filled_mask, [largest_contour], (255, 0, 0))  # Red fill
            cv2.polylines(filled_mask, [largest_contour], isClosed=True, color=(255, 0, 0), thickness=3)  # Red border
        
        # Convert images to PIL for blending
        orig_pil = Image.fromarray(img_array.astype(np.uint8), 'RGB')
        mask_pil = Image.fromarray(filled_mask, 'RGB')
        
        # Blend images with transparency (30% mask overlay)
        result = Image.blend(orig_pil, mask_pil, alpha=0.3)
        
        # Save the result
        result.save(output_path, 'PNG')
        print(f"Overlay image with filled contour saved to {output_path}")
        return True
    except Exception as e:
        print(f"Error saving overlay image to {output_path}: {e}")
        import traceback
        traceback.print_exc()
        return False 