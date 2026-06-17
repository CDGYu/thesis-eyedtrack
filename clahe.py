'''
clahe.py

CLAHE (Contrast Limited Adaptive Histogram Equalization) Module

This module provides functions and classes for enhancing image contrast using CLAHE,
with optional gamma correction and homomorphic filtering, and supports batch
processing (including parallel execution).

Example Usage:
--------------
1. Basic CLAHE on a single image:

```python
import cv2
from clahe import apply_clahe

img = cv2.imread('dark_image.jpg')
enhanced = apply_clahe(img)
cv2.imwrite('enhanced.jpg', enhanced)
```

2. Advanced enhancement with CLAHEEnhancer:

```python
from clahe import CLAHEEnhancer

enhancer = CLAHEEnhancer(base_clip_limit=2.5, do_gamma=True, do_homomorphic=True)
enhanced = enhancer.apply(img)
```

3. Batch processing with parallel execution:

```python
import numpy as np
from clahe import apply_clahe_batch, CLAHEEnhancer

frames = np.stack([frame1, frame2, frame3])  # shape: (N, H, W, 3)
enhancer = CLAHEEnhancer()
enhanced_frames = apply_clahe_batch(frames, enhancer, parallel=True, max_workers=4)
```
'''

import cv2
import numpy as np
import logging
from functools import lru_cache
from typing import List, Dict, Any, Optional, Union, Tuple
import multiprocessing
from concurrent.futures import ProcessPoolExecutor

# Configure module-level logger for status and debugging messages
glogger = logging.getLogger(__name__)
glogger.setLevel(logging.INFO)


def apply_clahe(
    frame: np.ndarray,
    preserve_color: bool = True,
    clip_limit: float = 2.0,
    tile_grid_size: Tuple[int, int] = (8, 8),
    apply_to_video: bool = False
) -> Union[np.ndarray, list]:
    """
    Enhance contrast of a single image or a batch of frames using CLAHE.

    Args:
        frame: BGR image (H x W x 3) or 4D array of frames (N x H x W x 3).
        preserve_color: If True, applies CLAHE on the L-channel in LAB space to retain color balance.
        clip_limit: Contrast threshold for adaptive equalization; values >0 recommended.
        tile_grid_size: Grid size for dividing the image into tiles; smaller tiles = more localized contrast enhancement.
        apply_to_video: If True, treats `frame` as a batch of frames and returns a list of enhanced frames.

    Returns:
        Enhanced BGR image or list of enhanced BGR images for video batches.

    Raises:
        ValueError: For invalid inputs or parameter values.
    """
    # Validate input types and parameter ranges
    if not isinstance(frame, np.ndarray):
        raise ValueError("Input frame must be a numpy.ndarray.")
    if clip_limit <= 0:
        raise ValueError("clip_limit must be positive.")
    if (
        not isinstance(tile_grid_size, tuple)
        or len(tile_grid_size) != 2
        or tile_grid_size[0] <= 0
        or tile_grid_size[1] <= 0
    ):
        raise ValueError("tile_grid_size must be a tuple of two positive ints.")

    # If processing a video batch, ensure frame is 4D
    if apply_to_video:
        if frame.ndim == 4:
            # Process each frame individually
            return [apply_clahe_single_image(f, preserve_color, clip_limit, tile_grid_size) for f in frame]
        else:
            raise ValueError("For video, input must be a 4D array of frames.")

    # Single image path
    return apply_clahe_single_image(frame, preserve_color, clip_limit, tile_grid_size)


def apply_clahe_single_image(
    frame: np.ndarray,
    preserve_color: bool,
    clip_limit: float,
    tile_grid_size: Tuple[int, int]
) -> np.ndarray:
    """
    Internal helper: Applies CLAHE to one image, supporting color preservation or grayscale.
    """
    if not preserve_color:
        # Convert to grayscale and apply CLAHE directly
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid_size)
        return clahe.apply(gray)

    # Preserve color: transform to LAB, enhance L channel, and merge back
    lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid_size)
    l_enhanced = clahe.apply(l)
    lab_enhanced = cv2.merge((l_enhanced, a, b))
    return cv2.cvtColor(lab_enhanced, cv2.COLOR_LAB2BGR)


@lru_cache(maxsize=8)
def _get_clahe(clip_limit: float, tile_grid_size: Tuple[int, int]) -> cv2.CLAHE:
    """Return a cached CLAHE object for reuse with identical parameters."""
    return cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid_size)


@lru_cache(maxsize=8)
def _get_gamma_lut(gamma: float) -> np.ndarray:
    """Compute and cache a lookup table for fast gamma correction."""
    inv = 1.0 / gamma
    # Build mapping: input intensity -> gamma-corrected output
    table = np.array([(i / 255.0) ** inv * 255 for i in range(256)], dtype=np.uint8)
    return table


def _apply_gamma(image: np.ndarray, gamma: float) -> np.ndarray:
    """
    Apply gamma correction to an image using a precomputed LUT.

    Raises:
        ValueError: If gamma is not positive.
    """
    if gamma <= 0:
        raise ValueError("Gamma must be positive.")
    lut = _get_gamma_lut(gamma)
    return cv2.LUT(image, lut)


def _homomorphic_filter(
    channel: np.ndarray,
    sigma: float,
    low_gain: float,
    high_gain: float
) -> np.ndarray:
    """
    Perform homomorphic filtering on a single-channel image to correct lighting.

    Steps:
    1. Log-transform pixel values.
    2. Low-pass filter via Gaussian blur.
    3. Amplify high-frequency details, suppress low-frequency illumination.
    4. Exponentiate and normalize back to [0,255].
    """
    # Normalize to [0,1] and apply log transform
    img = channel.astype(np.float32) / 255.0
    log = np.log1p(img)
    # Smooth illumination variations
    blur = cv2.GaussianBlur(log, (0, 0), sigmaX=sigma, sigmaY=sigma)
    # Combine low and high frequency components
    corrected = high_gain * (log - blur) + low_gain * blur
    exp = np.expm1(corrected)
    # Scale back to 8-bit
    norm = cv2.normalize(exp, None, 0, 255, cv2.NORM_MINMAX)
    return norm.astype(np.uint8)


class CLAHEEnhancer:
    def __init__(self, base_clip_limit=2.0, base_tile_grid_size=(8, 8), 
                 do_gamma=False, gamma_value=1.5,
                 do_homomorphic=False, homomorphic_sigma=1.0,
                 homomorphic_low_gain=0.5, homomorphic_high_gain=1.5):
        self.clahe = cv2.createCLAHE(clipLimit=base_clip_limit, tileGridSize=base_tile_grid_size)
        self.do_gamma = do_gamma
        self.gamma_value = gamma_value
        self.do_homomorphic = do_homomorphic
        self.homomorphic_sigma = homomorphic_sigma
        self.homomorphic_low_gain = homomorphic_low_gain
        self.homomorphic_high_gain = homomorphic_high_gain
        
        # Cache for homomorphic filter
        self._homomorphic_filter_cache = {}
        
    def _apply_gamma_correction(self, img):
        """Apply gamma correction to an image"""
        # Normalize to 0-1 range
        normalized = img / 255.0
        # Apply gamma correction
        corrected = np.power(normalized, 1.0/self.gamma_value)
        # Scale back to 0-255 range
        return np.uint8(corrected * 255)
    
    def _get_homomorphic_filter(self, shape):
        """Get or create homomorphic filter for the given shape"""
        # Check if we have a cached filter for this shape
        if shape in self._homomorphic_filter_cache:
            return self._homomorphic_filter_cache[shape]
            
        # Create filter
        rows, cols = shape
        crow, ccol = rows // 2, cols // 2
        
        # Create meshgrid for filter
        u = np.arange(rows)
        v = np.arange(cols)
        u, v = np.meshgrid(u, v, indexing='ij')
        
        # Compute squared distance from center
        d_squared = (u - crow) ** 2 + (v - ccol) ** 2
        
        # Create homomorphic filter
        h = np.exp(-d_squared / (2 * self.homomorphic_sigma ** 2))
        h = self.homomorphic_low_gain + (self.homomorphic_high_gain - self.homomorphic_low_gain) * (1 - h)
        
        # Cache the filter
        self._homomorphic_filter_cache[shape] = h
        
        return h
    
    def _apply_homomorphic_filtering(self, img):
        """Apply homomorphic filtering to enhance contrast"""
        # Convert to float and add small value to avoid log(0)
        img_float = img.astype(np.float32) + 1.0
        
        # Take log transform
        img_log = np.log(img_float)
        
        # Apply FFT
        img_fft = np.fft.fft2(img_log)
        img_fft_shifted = np.fft.fftshift(img_fft)
        
        # Get filter for this image shape
        h = self._get_homomorphic_filter(img_log.shape)
        
        # Apply filter in frequency domain
        img_filtered = h * img_fft_shifted
        
        # Apply inverse FFT
        img_filtered_shifted = np.fft.ifftshift(img_filtered)
        img_filtered_log = np.real(np.fft.ifft2(img_filtered_shifted))
        
        # Apply exponential to reverse log transform
        img_filtered = np.exp(img_filtered_log) - 1.0
        
        # Normalize to 0-255 range
        img_min = np.min(img_filtered)
        img_max = np.max(img_filtered)
        img_normalized = 255 * (img_filtered - img_min) / (img_max - img_min)
        
        return np.uint8(img_normalized)
    
    def apply(self, image, preserve_color=True):
        """Apply CLAHE enhancement to an image"""
        # Make a copy to avoid modifying the original
        result = image.copy()
        
        if preserve_color and len(image.shape) == 3:
            # Convert to LAB color space
            lab = cv2.cvtColor(result, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            
            # Apply CLAHE to L channel
            l = self.clahe.apply(l)
            
            # Apply gamma correction if enabled
            if self.do_gamma:
                l = self._apply_gamma_correction(l)
                
            # Apply homomorphic filtering if enabled
            if self.do_homomorphic:
                l = self._apply_homomorphic_filtering(l)
                
            # Merge channels and convert back to BGR
            lab = cv2.merge((l, a, b))
            result = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
        else:
            # Grayscale image or color preservation not requested
            if len(image.shape) == 3:
                # Convert to grayscale
                gray = cv2.cvtColor(result, cv2.COLOR_BGR2GRAY)
            else:
                gray = result.copy()
                
            # Apply CLAHE
            gray = self.clahe.apply(gray)
            
            # Apply gamma correction if enabled
            if self.do_gamma:
                gray = self._apply_gamma_correction(gray)
                
            # Apply homomorphic filtering if enabled
            if self.do_homomorphic:
                gray = self._apply_homomorphic_filtering(gray)
                
            result = gray
            
        return result


def _process_single_frame(args):
    """Helper for parallel batch processing: unpack args and apply enhancer."""
    frame, enhancer = args
    return enhancer.apply(frame)


def apply_clahe_batch(
    frames: np.ndarray,
    enhancer: CLAHEEnhancer,
    parallel: bool = False,
    max_workers: Optional[int] = None
) -> np.ndarray:
    """
    Apply CLAHEEnhancer to a batch of frames (N x H x W x 3) either sequentially or in parallel.

    Args:
        frames: 4D numpy array of input frames.
        enhancer: Initialized CLAHEEnhancer instance.
        parallel: If True, use multiprocessing for speed-up.
        max_workers: Number of parallel workers; defaults to CPU count.

    Returns:
        4D numpy array of enhanced frames.

    Raises:
        ValueError: For invalid inputs or worker settings.
    """
    if not isinstance(frames, np.ndarray) or frames.ndim != 4:
        raise ValueError("Frames batch must be a 4D numpy array.")

    if parallel:
        # Determine number of processes
        workers = max_workers or multiprocessing.cpu_count()
        if workers <= 0:
            raise ValueError("max_workers must be positive.")
        glogger.info(f"Processing {len(frames)} frames in parallel with {workers} workers")
        args = [(f, enhancer) for f in frames]
        with ProcessPoolExecutor(max_workers=workers) as exe:
            enhanced = list(exe.map(_process_single_frame, args))
        return np.stack(enhanced, axis=0)

    # Fallback to sequential processing for fewer frames or debugging
    return np.stack([enhancer.apply(f) for f in frames], axis=0)