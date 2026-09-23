"""
scripts/smoke_phase1.py

Quick smoke test for Phase 1 detector.
"""
import os
import sys
from pathlib import Path

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

import numpy as np

def main():
    print("Initializing SARSpillDetector...")
    from core.phase1_sar import SARSpillDetector
    detector = SARSpillDetector(checkpoint_path="base_model_kaggle_iou7441.pth")
    print("Model initialized successfully.")

    # Create dummy 512x512 SAR scene with a dark patch simulating an oil slick
    dummy = np.random.uniform(0.2, 0.5, (512, 512)).astype(np.float32)
    dummy[200:270, 200:270] = 0.05  # dark slick region

    print("Running detection on dummy SAR scene (512x512)...")
    res = detector.detect(dummy, threshold=0.50, min_pixels=20)
    print(f"Detections count: {res['spill_count']}")
    print(f"Candidates generated: {len(res['candidates'])}")
    if res['candidates']:
        cand = res['candidates'][0]
        print(f"Sample candidate: id={cand.id}, confidence={cand.detection_confidence}, area_km2={cand.metadata.get('area_sq_km')}")
    print("Phase 1 smoke test PASSED!")

if __name__ == "__main__":
    main()
