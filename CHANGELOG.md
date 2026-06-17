# Changelog

## [2.0.0] - 2025-05-19
### Added
- Optimized pipeline implementation with better performance
- Face box stabilization for smoother tracking
- Adaptive queue management to prevent bottlenecks
- Progressive behavior analysis to save CPU resources
- Memory and performance tracking tools
- Batch processing support for GPU acceleration
- Enhanced visualization with real-time metrics

### Changed
- Default pipeline is now the optimized implementation
- Configuration file format updated with new options
- Main script supports selection between implementations

### Fixed
- Camera recovery for hardware errors
- Memory leaks in long-running sessions
- GUI update performance issues

## [1.1.0] - 2025-05-23
### Added
- Enhanced face detection with MediaPipe integration
- Improved head pose stabilization with temporal smoothing
- Added weighted temporal smoothing for behavior confidence
- Enhanced configuration validation and error handling
- Added adaptive thresholds for eye and mouth state detection

### Changed
- Adjusted detection thresholds for better accuracy
- Optimized EAR and MAR calculations
- Improved behavior classification confidence
- Updated configuration structure with new settings
- Enhanced error recovery mechanisms

### Fixed
- Reduced false positive detections for behavior recognition
- Improved stability of head pose estimation
- Fixed issues with extreme lighting conditions

## [1.0.0] - 2025-05-01
### Added
- Initial release of the EyeDTrack Driver Monitoring System
- Real-time drowsiness detection
- Distraction monitoring
- Yawning detection
- Basic driver behavior analysis