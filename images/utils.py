import pydicom
import numpy as np
from PIL import Image
import os
import nibabel as nib

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
        print(f"DICOM image shape: {pixel_array.shape}")

        # Normalize pixel values
        if pixel_array.max() > 0:
            scaled_image = (np.maximum(pixel_array, 0) / pixel_array.max()) * 255.0
        else:
            scaled_image = np.zeros(pixel_array.shape) # Handle black images
            
        scaled_image = np.uint8(scaled_image)

        img = Image.fromarray(scaled_image)
        print(f"Converted DICOM to PIL Image with size: {img.size}")
        
        if png_path is None:
            png_path = os.path.splitext(dcm_path)[0] + ".png"
        
        img.save(png_path)
        print(f"Successfully converted {dcm_path} to {png_path}")
        return png_path
    except Exception as e:
        print(f"Error converting DICOM file {dcm_path}: {e}")
        import traceback
        traceback.print_exc()
        return None

def nii_to_png(nii_path, png_path=None, slice_idx=None):
    """Converts a NIfTI image to PNG format, extracting a specific slice."""
    try:
        # Load the NIfTI file
        print(f"Loading NIfTI file: {nii_path}")
        nii = nib.load(nii_path)
        
        # Get the data as a numpy array
        data = nii.get_fdata()
        print(f"Original NIfTI data shape: {data.shape}")
        
        # Transpose to correct orientation (same as in DeepLab.ipynb)
        data = data.transpose(2, 1, 0)
        print(f"After transpose, shape: {data.shape}")
        
        # If slice index not specified, use the middle slice
        if slice_idx is None:
            slice_idx = data.shape[0] // 2
        
        print(f"Using slice: {slice_idx} of {data.shape[0]}")
            
        # Extract the specified slice
        slice_data = data[slice_idx].astype(float)
        print(f"Slice shape: {slice_data.shape}")
        
        # Ensure slice_data is 2D
        if len(slice_data.shape) > 2:
            print(f"Warning: Slice has more than 2 dimensions: {slice_data.shape}. Using first channel.")
            slice_data = slice_data[:, :, 0]
        
        # Normalize pixel values
        if slice_data.max() > 0:
            min_val = slice_data.min()
            max_val = slice_data.max()
            print(f"Normalizing values from range [{min_val}, {max_val}] to [0, 255]")
            scaled_image = (np.maximum(slice_data, 0) / max_val) * 255.0
        else:
            print("Warning: Image has no positive values, creating black image")
            scaled_image = np.zeros(slice_data.shape) # Handle black images
            
        scaled_image = np.uint8(scaled_image)
        print(f"Scaled image shape: {scaled_image.shape}, dtype: {scaled_image.dtype}")
        
        # Convert to PIL Image
        try:
            img = Image.fromarray(scaled_image)
            print(f"Converted to PIL Image with size: {img.size}")
        except Exception as e:
            print(f"Error converting array to PIL Image: {e}")
            # Try to reshape or add dummy dimension if needed
            if len(scaled_image.shape) == 2:
                img = Image.fromarray(scaled_image, mode='L')
                print(f"Converted using explicit L mode (grayscale): {img.size}")
        
        # Create default png path if not provided
        if png_path is None:
            png_path = os.path.splitext(nii_path)[0] + ".png"
        
        # Save as PNG
        img.save(png_path)
        print(f"Successfully converted {nii_path} (slice {slice_idx}) to {png_path}")
        return png_path
    except Exception as e:
        print(f"Error converting NIfTI file {nii_path}: {e}")
        import traceback
        traceback.print_exc()
        return None 