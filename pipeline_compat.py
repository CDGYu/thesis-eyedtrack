"""
Compatibility layer for existing code to use the optimized pipeline.
"""

from optimized_pipeline import OptimizedThreadedPipeline
from pipeline import ThreadedPipeline as OriginalThreadedPipeline

class CompatiblePipeline(OptimizedThreadedPipeline):
    """
    A compatibility wrapper around OptimizedThreadedPipeline that provides
    the same interface as the original ThreadedPipeline.
    """
    
    def __init__(self, config):
        """Initialize with original or enhanced config."""
        # Make sure all required config options exist
        self._ensure_config_compatibility(config)
        super().__init__(config)
    
    def _ensure_config_compatibility(self, config):
        """Ensure all required config options exist for the optimized pipeline."""
        # Add performance section if missing
        if "performance" not in config:
            config["performance"] = {}
        
        # Set defaults for new performance options
        perf_defaults = {
            "skip_frames": 1,
            "max_queue_size": 5,
            "resize_factor": 1.0,
            "use_threading": True,
            "max_workers": 4,
            "enable_gpu": False,
            "use_opencv_dnn": True,
            "camera_buffer_size": 1,
            "batch_size": 1,
            "profile_performance": False,
            "track_memory": False,
            "memory_log_interval": 100
        }
        
        for key, value in perf_defaults.items():
            if key not in config["performance"]:
                config["performance"][key] = value
        
        # Add display section if missing
        if "display" not in config:
            config["display"] = {}
        
        # Set defaults for new display options
        display_defaults = {
            "show_status_panel": True,
            "only_show_status_on_risk": True,
            "alert_duration": 3.0
        }
        
        for key, value in display_defaults.items():
            if key not in config["display"]:
                config["display"][key] = value
        
        return config
    
    # Add any methods from the original pipeline that might be missing in the optimized version
    # For example:
    
    def get_metrics(self):
        """Backward compatibility for get_metrics method."""
        if hasattr(self, 'get_performance_metrics'):
            return self.get_performance_metrics()
        return {
            "fps_capture": self.fps_capture,
            "fps_processing": self.fps_processing,
            "fps_rendering": self.fps_rendering,
        }