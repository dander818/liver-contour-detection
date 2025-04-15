import pydicom
import numpy as np
from PIL import Image
import os

# png_path - куда записать png изображение
def dcm_to_png(dcm_path, png_path=None):
    """Converts a DICOM image to PNG format."""
    try:
        ds = pydicom.dcmread(dcm_path)
        
        # Check if pixel data exists
        if not hasattr(ds, 'PixelData'):
            print(f"Warning: No pixel data found in DICOM file: {dcm_path}")
            return None
        
        pixel_array = ds.pixel_array.astype(float)

        # Normalize pixel values
        if pixel_array.max() > 0:
            scaled_image = (np.maximum(pixel_array, 0) / pixel_array.max()) * 255.0
        else:
            scaled_image = np.zeros(pixel_array.shape) # Handle black images
            
        scaled_image = np.uint8(scaled_image)

        img = Image.fromarray(scaled_image)
        
        if png_path is None:
            png_path = os.path.splitext(dcm_path)[0] + ".png"
        
        img.save(png_path)
        print(f"Successfully converted {dcm_path} to {png_path}")
        return png_path
    except Exception as e:
        print(f"Error converting DICOM file {dcm_path}: {e}")
        return None 