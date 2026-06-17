"""
Import the appropriate pipeline implementation based on configuration.
This module provides access to both original and optimized pipeline implementations.
"""

import os
import logging

# Configure logging
logger = logging.getLogger("pipeline")

# Import the original implementation first
from original_pipeline import (
    ThreadedPipeline as OriginalThreadedPipeline,
    OptimizedFrameGrabber,
    OptimizedFrameProcessor,
    BatchProcessor
)

# Determine which pipeline implementation to use
USE_OPTIMIZED = os.environ.get("USE_OPTIMIZED_PIPELINE", "1") == "1"

# Try to import optimized version, fall back to original if not available
if USE_OPTIMIZED:
    try:
        logger.info("Using optimized pipeline implementation")
        from optimized_pipeline import OptimizedThreadedPipeline as ThreadedPipeline
    except ImportError:
        logger.warning("Optimized pipeline not available, falling back to original")
        ThreadedPipeline = OriginalThreadedPipeline
else:
    logger.info("Using original pipeline implementation by configuration")
    ThreadedPipeline = OriginalThreadedPipeline

# Export all needed classes and functions
__all__ = [
    'ThreadedPipeline', 
    'OriginalThreadedPipeline',
    'OptimizedFrameGrabber',
    'OptimizedFrameProcessor',
    'BatchProcessor'
]