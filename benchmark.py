import time
import argparse
import matplotlib.pyplot as plt
import numpy as np
from pipeline import ThreadedPipeline
from optimized_pipeline import OptimizedThreadedPipeline
from main_optimized import load_config

def benchmark_pipelines(duration=30, config_path="config.yaml"):
    """Benchmark standard vs optimized pipeline performance"""
    config = load_config(config_path)
    
    # Track metrics
    metrics = {
        "standard": {
            "fps_capture": [],
            "fps_processing": [],
            "fps_rendering": [],
            "processing_times": []
        },
        "optimized": {
            "fps_capture": [],
            "fps_processing": [],
            "fps_rendering": [],
            "processing_times": []
        }
    }
    
    # Test standard pipeline
    print("Benchmarking standard pipeline...")
    pipeline = ThreadedPipeline(config)
    pipeline.start()
    
    start_time = time.time()
    while time.time() - start_time < duration:
        metrics["standard"]["fps_capture"].append(pipeline.fps_capture)
        metrics["standard"]["fps_processing"].append(pipeline.fps_processing)
        metrics["standard"]["fps_rendering"].append(pipeline.fps_rendering)
        if hasattr(pipeline, 'processing_times') and pipeline.processing_times:
            metrics["standard"]["processing_times"].append(np.mean(pipeline.processing_times))
        time.sleep(1)
    
    pipeline.stop()
    
    # Test optimized pipeline
    print("Benchmarking optimized pipeline...")
    pipeline = OptimizedThreadedPipeline(config)
    pipeline.start()
    
    start_time = time.time()
    while time.time() - start_time < duration:
        metrics["optimized"]["fps_capture"].append(pipeline.fps_capture)
        metrics["optimized"]["fps_processing"].append(pipeline.fps_processing)
        metrics["optimized"]["fps_rendering"].append(pipeline.fps_rendering)
        if hasattr(pipeline, 'processing_times') and pipeline.processing_times:
            metrics["optimized"]["processing_times"].append(np.mean(pipeline.processing_times))
        time.sleep(1)
    
    pipeline.stop()
    
    # Generate comparison plots
    fig, axs = plt.subplots(2, 2, figsize=(12, 10))
    
    # FPS Capture
    axs[0, 0].plot(metrics["standard"]["fps_capture"], label="Standard")
    axs[0, 0].plot(metrics["optimized"]["fps_capture"], label="Optimized")
    axs[0, 0].set_title("Capture FPS")
    axs[0, 0].legend()
    
    # FPS Processing
    axs[0, 1].plot(metrics["standard"]["fps_processing"], label="Standard")
    axs[0, 1].plot(metrics["optimized"]["fps_processing"], label="Optimized")
    axs[0, 1].set_title("Processing FPS")
    axs[0, 1].legend()
    
    # FPS Rendering
    axs[1, 0].plot(metrics["standard"]["fps_rendering"], label="Standard")
    axs[1, 0].plot(metrics["optimized"]["fps_rendering"], label="Optimized")
    axs[1, 0].set_title("Rendering FPS")
    axs[1, 0].legend()
    
    # Processing Times
    axs[1, 1].plot(metrics["standard"]["processing_times"], label="Standard")
    axs[1, 1].plot(metrics["optimized"]["processing_times"], label="Optimized")
    axs[1, 1].set_title("Processing Time (ms)")
    axs[1, 1].legend()
    
    plt.tight_layout()
    plt.savefig("pipeline_benchmark.png")
    plt.show()
    
    # Print summary
    print("\nPerformance Summary:")
    print("Standard Pipeline:")
    print(f"  Avg Capture FPS: {np.mean(metrics['standard']['fps_capture']):.2f}")
    print(f"  Avg Processing FPS: {np.mean(metrics['standard']['fps_processing']):.2f}")
    print(f"  Avg Rendering FPS: {np.mean(metrics['standard']['fps_rendering']):.2f}")
    if metrics["standard"]["processing_times"]:
        print(f"  Avg Processing Time: {np.mean(metrics['standard']['processing_times'])*1000:.2f} ms")
    
    print("\nOptimized Pipeline:")
    print(f"  Avg Capture FPS: {np.mean(metrics['optimized']['fps_capture']):.2f}")
    print(f"  Avg Processing FPS: {np.mean(metrics['optimized']['fps_processing']):.2f}")
    print(f"  Avg Rendering FPS: {np.mean(metrics['optimized']['fps_rendering']):.2f}")
    if metrics["optimized"]["processing_times"]:
        print(f"  Avg Processing Time: {np.mean(metrics['optimized']['processing_times'])*1000:.2f} ms")
    
    # Calculate improvement percentages
    if metrics["standard"]["processing_times"] and metrics["optimized"]["processing_times"]:
        std_time = np.mean(metrics["standard"]["processing_times"]) * 1000
        opt_time = np.mean(metrics["optimized"]["processing_times"]) * 1000
        time_improvement = (std_time - opt_time) / std_time * 100
        print(f"\nProcessing Time Improvement: {time_improvement:.2f}%")
    
    if metrics["standard"]["fps_processing"] and metrics["optimized"]["fps_processing"]:
        std_fps = np.mean(metrics["standard"]["fps_processing"])
        opt_fps = np.mean(metrics["optimized"]["fps_processing"])
        fps_improvement = (opt_fps - std_fps) / std_fps * 100
        print(f"Processing FPS Improvement: {fps_improvement:.2f}%")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Benchmark pipeline implementations")
    parser.add_argument("--duration", type=int, default=30, help="Duration of benchmark in seconds")
    parser.add_argument("--config", type=str, default="config.yaml", help="Path to config file")
    args = parser.parse_args()
    
    benchmark_pipelines(duration=args.duration, config_path=args.config)