"""
Visualization utilities for driver behavior analysis system.
Provides functions for creating informative visual displays.
"""

import cv2
import numpy as np
import matplotlib.pyplot as plt
from typing import Dict, List, Tuple, Optional, Union, Any
import time
import logging
from dataclasses import dataclass
from enum import Enum
import os

# Configure module-level logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Constants for visualization
COLORS = {
    "safe": (0, 255, 0),      # Green
    "warning": (0, 165, 255),  # Orange
    "danger": (0, 0, 255),     # Red
    "info": (255, 255, 0),     # Cyan
    "text": (255, 255, 255),   # White
    "background": (0, 0, 0),   # Black
    "highlight": (255, 255, 0), # Yellow
    "attention": (255, 0, 255), # Magenta
    "neutral": (128, 128, 128)  # Gray
}

# Alert levels for consistent styling
class AlertLevel(Enum):
    SAFE = "safe"
    WARNING = "warning"
    DANGER = "danger"
    INFO = "info"

@dataclass
class VisualizationConfig:
    """Configuration for visualization components"""
    dashboard_width: int = 300
    font_face: int = cv2.FONT_HERSHEY_SIMPLEX
    title_font_scale: float = 0.7
    text_font_scale: float = 0.5
    value_font_scale: float = 0.5
    plot_height: int = 80
    plot_margin: int = 30
    show_timestamp: bool = True
    show_fps: bool = True
    background_opacity: float = 0.8  # For semi-transparent overlays
    theme: str = "dark"  # 'dark' or 'light'

# Default configuration
DEFAULT_CONFIG = VisualizationConfig()

def create_dashboard(
    frame: np.ndarray,
    metrics: Dict[str, Union[float, str, bool]],
    history: Optional[Dict[str, List[float]]] = None,
    max_history: int = 100,
    config: VisualizationConfig = DEFAULT_CONFIG
) -> np.ndarray:
    """
    Create a dashboard visualization with metrics and optional history plots.
    
    Args:
        frame: Input frame to display alongside dashboard
        metrics: Dictionary of metrics to display (name -> value)
        history: Optional dictionary of metric histories for plotting
        max_history: Maximum number of history points to display
        config: Visualization configuration
        
    Returns:
        Dashboard image with frame and visualizations
    """
    h, w = frame.shape[:2]
    dashboard_width = config.dashboard_width
    
    # Create dashboard canvas
    dashboard = np.zeros((h, dashboard_width, 3), dtype=np.uint8)
    dashboard[:] = COLORS["background"]
    
    # Add title
    cv2.putText(dashboard, "Driver Monitoring", (10, 30),
                config.font_face, config.title_font_scale, COLORS["text"], 2)
    
    # Add timestamp
    y_pos = 60
    if config.show_timestamp:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(dashboard, timestamp, (10, y_pos),
                    config.font_face, config.text_font_scale, COLORS["info"], 1)
        y_pos += 30
    
    # Add FPS if provided in metrics
    if config.show_fps and "fps" in metrics:
        fps = metrics.pop("fps")  # Remove from metrics to avoid duplicate display
        fps_str = f"FPS: {fps:.1f}" if isinstance(fps, (int, float)) else f"FPS: {fps}"
        cv2.putText(dashboard, fps_str, (10, y_pos),
                    config.font_face, config.text_font_scale, COLORS["info"], 1)
        y_pos += 30
    
    # Add metrics
    for name, value in metrics.items():
        # Format value based on type
        if isinstance(value, float):
            value_str = f"{value:.2f}"
        elif isinstance(value, bool):
            value_str = "YES" if value else "NO"
            color = COLORS["danger"] if value else COLORS["safe"]
        else:
            value_str = str(value)
            
        # Determine color based on metric name and value
        if "risk" in name.lower():
            if isinstance(value, str):
                if "high" in value.lower():
                    color = COLORS["danger"]
                elif "moderate" in value.lower():
                    color = COLORS["warning"]
                else:
                    color = COLORS["safe"]
            else:
                # Numeric risk threshold
                if isinstance(value, (int, float)):
                    if value > 0.7:
                        color = COLORS["danger"]
                    elif value > 0.3:
                        color = COLORS["warning"]
                    else:
                        color = COLORS["safe"]
                else:
                    color = COLORS["text"]
        elif "alert" in name.lower() or "warning" in name.lower():
            color = COLORS["warning"]
        elif "drowsy" in name.lower() or "distracted" in name.lower():
            color = COLORS["danger"]
        else:
            color = COLORS["text"]
            
        # Draw metric name and value
        cv2.putText(dashboard, f"{name}:", (10, y_pos),
                    config.font_face, config.text_font_scale, COLORS["text"], 1)
        cv2.putText(dashboard, value_str, (150, y_pos),
                    config.font_face, config.value_font_scale, color, 1)
        y_pos += 30
    
    # Add history plots if provided
    if history:
        plot_y = y_pos + 20
        
        for name, values in history.items():
            if not values:
                continue
                
            # Draw plot title
            cv2.putText(dashboard, name, (10, plot_y - 5),
                        config.font_face, config.text_font_scale, COLORS["text"], 1)
            
            # Draw plot background
            cv2.rectangle(dashboard, (10, plot_y), (dashboard_width - 10, plot_y + config.plot_height),
                         (50, 50, 50), -1)
            
            # Draw plot data
            if len(values) > 1:
                # Normalize values to plot height
                min_val = min(values)
                max_val = max(values)
                range_val = max(max_val - min_val, 0.001)  # Avoid division by zero
                
                # Draw points and lines
                points = []
                for i, val in enumerate(values[-max_history:]):
                    x = 10 + int((dashboard_width - 20) * i / min(max_history, len(values)))
                    y = plot_y + config.plot_height - int((val - min_val) / range_val * (config.plot_height - 10))
                    points.append((x, y))
                
                # Draw lines between points
                if len(points) > 1:
                    for i in range(len(points) - 1):
                        cv2.line(dashboard, points[i], points[i+1], COLORS["info"], 1)
                
                # Draw min/max labels
                cv2.putText(dashboard, f"{min_val:.2f}", (dashboard_width - 50, plot_y + config.plot_height - 5),
                            config.font_face, 0.4, COLORS["text"], 1)
                cv2.putText(dashboard, f"{max_val:.2f}", (dashboard_width - 50, plot_y + 10),
                            config.font_face, 0.4, COLORS["text"], 1)
            
            plot_y += config.plot_height + config.plot_margin
    
    # Combine frame and dashboard
    combined = np.zeros((h, w + dashboard_width, 3), dtype=np.uint8)
    combined[:, :w] = frame
    combined[:, w:] = dashboard
    
    return combined

def draw_alert(
    frame: np.ndarray,
    message: str,
    level: Union[str, AlertLevel] = AlertLevel.INFO,
    position: Optional[Tuple[int, int]] = None,
    duration_ms: int = 1000,
    font_scale: float = 1.0,
    thickness: int = 2,
    flash: bool = True
) -> np.ndarray:
    """
    Draw an alert message on the frame.
    
    Args:
        frame: Input frame
        message: Alert message
        level: Alert level ("info", "warning", "danger") or AlertLevel enum
        position: Optional position, defaults to center
        duration_ms: Flash duration in milliseconds
        font_scale: Font scale for the alert text
        thickness: Line thickness
        flash: Whether to flash the alert
        
    Returns:
        Frame with alert drawn
    """
    h, w = frame.shape[:2]
    result = frame.copy()
    
    # Convert AlertLevel enum to string if needed
    if isinstance(level, AlertLevel):
        level = level.value
    
    # Determine color based on level
    color = COLORS.get(level, COLORS["info"])
    
    # Determine position
    if position is None:
        position = (w // 2, h // 2)
    
    # Create flashing effect based on time
    should_draw = True
    if flash and duration_ms > 0:
        ms = int(time.time() * 1000) % (duration_ms * 2)
        should_draw = ms > duration_ms
    
    if should_draw:
        # Draw background box
        text_size = cv2.getTextSize(message, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)[0]
        box_coords = (
            position[0] - text_size[0] // 2 - 10,
            position[1] - text_size[1] // 2 - 10,
            position[0] + text_size[0] // 2 + 10,
            position[1] + text_size[1] // 2 + 10
        )
        cv2.rectangle(result, (box_coords[0], box_coords[1]), (box_coords[2], box_coords[3]),
                     (0, 0, 0), -1)
        cv2.rectangle(result, (box_coords[0], box_coords[1]), (box_coords[2], box_coords[3]),
                     color, thickness)
        
        # Draw text
        cv2.putText(result, message, 
                   (position[0] - text_size[0] // 2, position[1] + text_size[1] // 2),
                   cv2.FONT_HERSHEY_SIMPLEX, font_scale, color, thickness)
    
    return result

# Replace the existing draw_overlay_text function in visualization.py with this updated version:

def draw_overlay_text(
    frame: np.ndarray,
    text: Union[str, Dict[str, str]],
    position: Tuple[int, int],
    font_scale: float = 0.5,
    color: Tuple[int, int, int] = COLORS["text"],
    thickness: int = 1,
    background: bool = True,
    bg_color: Tuple[int, int, int] = (0, 0, 0),
    bg_opacity: float = 0.7,
    padding: int = 5
) -> np.ndarray:
    """
    Draw text with optional semi-transparent background.
    Can handle both text strings and dictionaries of key-value pairs.
    
    Args:
        frame: Input image to draw on
        text: Text to display (string or dictionary)
        position: (x, y) position for text
        font_scale: Font scale
        color: Text color (BGR)
        thickness: Text thickness
        background: Whether to draw background
        bg_color: Background color
        bg_opacity: Background opacity (0-1)
        padding: Padding around text
        
    Returns:
        Frame with text overlay
    """
    result = frame.copy()
    
    # Handle dictionary input
    if isinstance(text, dict):
        text_lines = [f"{k}: {v}" for k, v in text.items()]
        text = "\n".join(text_lines)
    
    # Split text into lines
    lines = text.split('\n')
    
    # Get text size
    max_width = 0
    text_heights = []
    
    for line in lines:
        (text_width, text_height), baseline = cv2.getTextSize(
            line, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness
        )
        max_width = max(max_width, text_width)
        text_heights.append((text_height, baseline))
    
    if background:
        # Calculate background dimensions
        line_height = max([h + b for h, b in text_heights]) + padding
        total_height = line_height * len(lines) + padding
        
        # Create background rectangle
        bg_x1 = position[0] - padding
        bg_y1 = position[1] - padding
        bg_x2 = position[0] + max_width + padding * 2
        bg_y2 = position[1] + total_height
        
        # Create semi-transparent overlay
        overlay = result.copy()
        cv2.rectangle(overlay, (bg_x1, bg_y1), (bg_x2, bg_y2), bg_color, -1)
        
        # Blend with original frame
        cv2.addWeighted(overlay, bg_opacity, result, 1 - bg_opacity, 0, result)
    
    # Draw text for each line
    for i, line in enumerate(lines):
        line_height = text_heights[i][0] + text_heights[i][1] + padding
        y_pos = position[1] + i * line_height + text_heights[i][0]
        
        cv2.putText(
            result, line, (position[0], y_pos), 
            cv2.FONT_HERSHEY_SIMPLEX, font_scale, color, thickness
        )
    
    return result

def draw_metric_bar(
    frame: np.ndarray,
    value: float,
    position: Tuple[int, int],
    width: int = 150,
    height: int = 20,
    min_value: float = 0.0,
    max_value: float = 1.0,
    color_ranges: Optional[List[Tuple[float, Tuple[int, int, int]]]] = None,
    label: Optional[str] = None,
    show_value: bool = True
) -> np.ndarray:
    """
    Draw a metric bar visualization.
    
    Args:
        frame: Input frame
        value: Current value to display
        position: (x, y) position for the bar
        width: Bar width in pixels
        height: Bar height in pixels
        min_value: Minimum value (left end of bar)
        max_value: Maximum value (right end of bar)
        color_ranges: List of (threshold, color) tuples for coloring
        label: Optional label to display
        show_value: Whether to show numeric value
        
    Returns:
        Frame with metric bar
    """
    result = frame.copy()
    x, y = position
    
    # Default color ranges if not provided
    if color_ranges is None:
        color_ranges = [
            (0.3, COLORS["safe"]),
            (0.7, COLORS["warning"]),
            (1.0, COLORS["danger"])
        ]
    
    # Normalize value to 0-1 range
    norm_value = (value - min_value) / (max_value - min_value)
    norm_value = max(0.0, min(1.0, norm_value))  # Clamp to 0-1
    
    # Draw background
    cv2.rectangle(result, (x, y), (x + width, y + height), (50, 50, 50), -1)
    cv2.rectangle(result, (x, y), (x + width, y + height), (100, 100, 100), 1)
    
    # Draw filled portion
    filled_width = int(width * norm_value)
    if filled_width > 0:
        # Determine color based on value
        bar_color = color_ranges[-1][1]  # Default to last color
        for threshold, color in color_ranges:
            if norm_value <= threshold:
                bar_color = color
                break
        
        cv2.rectangle(result, (x, y), (x + filled_width, y + height), bar_color, -1)
    
    # Draw label
    if label:
        cv2.putText(result, label, (x, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, COLORS["text"], 1)
    
    # Draw value
    if show_value:
        value_str = f"{value:.2f}"
        cv2.putText(result, value_str, (x + width + 5, y + height - 5), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, COLORS["text"], 1)
    
    return result

def create_multi_view(
    frames: List[np.ndarray],
    titles: Optional[List[str]] = None,
    layout: Optional[Tuple[int, int]] = None,
    size: Optional[Tuple[int, int]] = None
) -> np.ndarray:
    """
    Create a multi-view display of multiple frames.
    
    Args:
        frames: List of frames to display
        titles: Optional list of titles for each frame
        layout: Optional (rows, cols) layout, auto-determined if not provided
        size: Optional (width, height) for each frame
        
    Returns:
        Combined multi-view image
    """
    if not frames:
        return np.zeros((100, 100, 3), dtype=np.uint8)
    
    n_frames = len(frames)
    
    # Determine layout if not provided
    if layout is None:
        cols = min(3, n_frames)
        rows = (n_frames + cols - 1) // cols
        layout = (rows, cols)
    else:
        rows, cols = layout
    
    # Ensure all frames have the same size
    if size is None:
        # Use the size of the first frame
        h, w = frames[0].shape[:2]
        size = (w, h)
    else:
        w, h = size
    
    # Resize all frames to the target size
    resized_frames = []
    for frame in frames:
        if frame.shape[:2] != (h, w):
            resized = cv2.resize(frame, (w, h))
        else:
            resized = frame
        resized_frames.append(resized)
    
    # Create empty canvas
    canvas = np.zeros((h * rows, w * cols, 3), dtype=np.uint8)
    
    # Place frames on canvas
    for i, frame in enumerate(resized_frames):
        if i >= rows * cols:
            break
            
        row = i // cols
        col = i % cols
        
        y1 = row * h
        y2 = y1 + h
        x1 = col * w
        x2 = x1 + w
        
        canvas[y1:y2, x1:x2] = frame
        
        # Add title if provided
        if titles and i < len(titles):
            title = titles[i]
            cv2.putText(canvas, title, (x1 + 10, y1 + 30), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, COLORS["text"], 2)
    
    return canvas

def save_visualization(
    frame: np.ndarray,
    filename: Optional[str] = None,
    directory: str = "visualizations",
    prefix: str = "viz",
    format: str = "jpg",
    timestamp: bool = True
) -> str:
    """
    Save visualization frame to disk.
    
    Args:
        frame: Frame to save
        filename: Optional specific filename
        directory: Directory to save in
        prefix: Prefix for auto-generated filenames
        format: Image format (jpg, png)
        timestamp: Whether to include timestamp in filename
        
    Returns:
        Path to saved file
    """
    # Create directory if it doesn't exist
    os.makedirs(directory, exist_ok=True)
    
    # Generate filename if not provided
    if filename is None:
        if timestamp:
            time_str = time.strftime("%Y%m%d_%H%M%S")
            filename = f"{prefix}_{time_str}.{format}"
        else:
            filename = f"{prefix}.{format}"
    
    # Ensure filename has correct extension
    if not filename.lower().endswith(f".{format}"):
        filename = f"{filename}.{format}"
    
    # Full path
    filepath = os.path.join(directory, filename)
    
    # Save image
    cv2.imwrite(filepath, frame)
    logger.info(f"Saved visualization to {filepath}")
    
    return filepath

def create_behavior_summary(
    frame: np.ndarray,
    behavior_data: Dict[str, Any],
    position: Tuple[int, int] = (20, 20),
    width: int = 300,
    padding: int = 10,
    opacity: float = 0.8
) -> np.ndarray:
    """
    Create a behavior summary overlay with key information.
    
    Args:
        frame: Input frame
        behavior_data: Dictionary with behavior analysis data
        position: (x, y) position for the summary box
        width: Width of the summary box
        padding: Padding inside the box
        opacity: Background opacity
        
    Returns:
        Frame with behavior summary overlay
    """
    result = frame.copy()
    x, y = position
    
    # Extract key information
    behavior = behavior_data.get("behavior", "Unknown")
    confidence = behavior_data.get("confidence", 0.0)
    is_risky = behavior_data.get("is_risky", False)
    description = behavior_data.get("description", "")
    
    # Determine color based on risk
    if is_risky:
        if confidence > 0.7:
            color = COLORS["danger"]
            risk_level = "HIGH RISK"
        else:
            color = COLORS["warning"]
            risk_level = "MODERATE RISK"
    else:
        color = COLORS["safe"]
        risk_level = "SAFE"
    
    # Calculate box height based on content
    line_height = 30
    n_lines = 4  # Title, behavior, confidence, description
    box_height = n_lines * line_height + 2 * padding
    
    # Create semi-transparent overlay
    overlay = result.copy()
    cv2.rectangle(overlay, (x, y), (x + width, y + box_height), (0, 0, 0), -1)
    cv2.addWeighted(overlay, opacity, result, 1 - opacity, 0, result)
    
    # Draw border with risk color
    cv2.rectangle(result, (x, y), (x + width, y + box_height), color, 2)
    
    # Draw title
    title_y = y + padding + 20
    cv2.putText(result, risk_level, (x + padding, title_y), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
    
    # Draw behavior
    behavior_y = title_y + line_height
    cv2.putText(result, f"Behavior: {behavior}", (x + padding, behavior_y), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, COLORS["text"], 1)
    
    # Draw confidence
    conf_y = behavior_y + line_height
    conf_str = f"Confidence: {confidence:.1%}"
    cv2.putText(result, conf_str, (x + padding, conf_y), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, COLORS["text"], 1)
    
    # Draw description
    desc_y = conf_y + line_height
    cv2.putText(result, description, (x + padding, desc_y), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, COLORS["text"], 1)
    
    return result

def highlight_region(
    frame: np.ndarray,
    region: Tuple[int, int, int, int],
    color: Tuple[int, int, int] = COLORS["highlight"],
    thickness: int = 2,
    label: Optional[str] = None,
    label_position: str = "top"
) -> np.ndarray:
    """
    Highlight a region of interest in the frame.
    
    Args:
        frame: Input frame
        region: (x, y, width, height) region to highlight
        color: Border color
        thickness: Border thickness
        label: Optional label to display
        label_position: Position for label ("top", "bottom")
        
    Returns:
        Frame with highlighted region
    """
    result = frame.copy()
    x, y, w, h = region
    
    # Draw rectangle
    cv2.rectangle(result, (x, y), (x + w, y + h), color, thickness)
    
    # Add label if provided
    if label:
        if label_position == "top":
            label_y = max(0, y - 10)
        else:  # bottom
            label_y = min(frame.shape[0], y + h + 20)
            
        cv2.putText(result, label, (x, label_y), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, thickness)
    
    return result

def create_attention_map(
    frame: np.ndarray,
    attention_data: np.ndarray,
    alpha: float = 0.4,
    colormap: int = cv2.COLORMAP_JET
) -> np.ndarray:
    """
    Create an attention heatmap overlay.
    
    Args:
        frame: Input frame
        attention_data: 2D array with attention values (0-1)
        alpha: Opacity of the overlay
        colormap: OpenCV colormap to use
        
    Returns:
        Frame with attention map overlay
    """
    h, w = frame.shape[:2]
    
    # Ensure attention data is the right shape
    if attention_data.shape != (h, w):
        attention_data = cv2.resize(attention_data, (w, h))
    
    # Normalize to 0-255
    attention_norm = np.clip(attention_data * 255, 0, 255).astype(np.uint8)
    
    # Apply colormap
    heatmap = cv2.applyColorMap(attention_norm, colormap)
    
    # Create overlay
    result = cv2.addWeighted(frame, 1.0, heatmap, alpha, 0)
    
    return result