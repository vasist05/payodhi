"""
scripts/run_phase1_e2e_demo.py

End-to-end execution of Phase 1 (Detection) and handoff to Phase 2 (Verification)
using real Sentinel-1 SAR satellite images from the dataset.
"""

import json
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "backend"))

from core.phase1_sar import SARSpillDetector
from core.phase2_false_positive.inference import SpillFilter


if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

def run_demo():
    print("=" * 70)
    print(">> PAYODHI: PHASE 1 END-TO-END DETECTION DEMO")
    print("=" * 70)

    # 1. Initialize Phase 1 Detector
    print("\n[1/4] Loading Phase 1 SAR U-Net Detection Model...")
    detector = SARSpillDetector(
        checkpoint_path="base_model_kaggle_iou7441.pth",
        tile_size=256,
        stride=192,
    )
    print("      ✓ Model loaded with ResNet-34 encoder and trained weights.")

    # 2. Select real SAR test image
    test_image_path = "data/fp_filter/csiro_patches/oil/0_0_0_img_0bBRglmdLdC6cFxF_JAV_cls_1.jpg"
    if not Path(test_image_path).exists():
        print(f"Error: Test image not found at {test_image_path}")
        return

    print(f"\n[2/4] Input Satellite Scene: {test_image_path}")

    # Reference coordinates: Mumbai High offshore zone
    bbox_wgs84 = (71.30, 19.20, 71.55, 19.45)  # min_lon, min_lat, max_lon, max_lat
    scene_id = "SCENE-S1-2018-07-28-IND-001"
    output_dir = "data/phase1_crops"

    # 3. Execute Phase 1 Detection
    print("\n[3/4] Running Phase 1 Detection Pipeline...")
    print("      - Sliding-window tiling (256x256, 192px stride)")
    print("      - PyTorch U-Net inference on SAR backscatter")
    print("      - Seamless cosine overlap blending")
    print("      - Morphological cleaning & contour extraction")
    print("      - Coordinate projection to WGS84 (EPSG:4326)")
    print("      - Candidate crop extraction with 32px padding")

    results = detector.detect(
        image_input=test_image_path,
        threshold=0.50,
        min_pixels=30,
        bbox_wgs84=bbox_wgs84,
        scene_id=scene_id,
        output_crops_dir=output_dir,
    )

    spill_count = results["spill_count"]
    print(f"\n      [+] RESULT: Detected {spill_count} oil spill slick(s) in scene.")

    if spill_count == 0:
        print("      No spills detected above threshold.")
        return

    for idx, det in enumerate(results["detections"]):
        cand = results["candidates"][idx]
        print(f"\n      --- Spill #{idx + 1} Metadata ---")
        print(f"      * Candidate ID:        {cand.id}")
        print(f"      * Mean Confidence:     {det['confidence'] * 100:.2f}%")
        print(f"      * Spill Area:          {det['area_sq_km']:.4f} km2 ({det['pixel_area']} pixels)")
        print(f"      * Centroid (Lat, Lon): {det['centroid'][0]:.4f} N, {det['centroid'][1]:.4f} E")
        print(f"      * GeoJSON Geometry:    {det['geometry']['type']}")
        print(f"      * Sample Coordinates:  {det['geometry']['coordinates'][0][0][:3]}...")
        print(f"      * Exported Crop:       {cand.patch_path}")

    # 4. Phase 1 -> Phase 2 Seamless Handoff
    print("\n[4/4] Passing Phase 1 Candidate to Phase 2 (SAR-UV False-Positive Filter)...")
    filter_model = SpillFilter(mode="sar_uv")
    
    first_candidate = results["candidates"][0]
    p2_result = filter_model.verify_single(
        patch_path=first_candidate.patch_path,
        wind_u10=3.5,   # Typical coastal wind context
        wind_v10=-2.1,
    )

    is_oil = p2_result["is_oil"]
    p2_conf = p2_result["confidence"]
    verdict = "CONFIRMED OIL SPILL" if is_oil else "REJECTED LOOKALIKE"

    print(f"      * Phase 2 Filter Verdict: {verdict}")
    print(f"      * Phase 2 Confidence:     {p2_conf * 100:.2f}%")
    print(f"      * Features Extracted:     {len(p2_result.get('features', []))} physical radar/damping features")

    # 5. Save Output Evidence JSON
    evidence_output_path = "data/demo_cache/phase1_e2e_result.json"
    Path(evidence_output_path).parent.mkdir(parents=True, exist_ok=True)

    summary = {
        "scene_id": scene_id,
        "input_image": test_image_path,
        "phase1_detections": [
            {
                "id": c.id,
                "confidence": d["confidence"],
                "area_sq_km": d["area_sq_km"],
                "centroid": d["centroid"],
                "patch_path": c.patch_path,
                "geometry": d["geometry"],
            }
            for d, c in zip(results["detections"], results["candidates"])
        ],
        "phase2_verification": {
            "verdict": verdict,
            "is_oil": is_oil,
            "confidence": p2_conf,
        },
    }

    with open(evidence_output_path, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\n[OK] Evidence JSON successfully saved to: {evidence_output_path}")
    print("=" * 70)
    print("[SUCCESS] END-TO-END DEMO COMPLETED SUCCESSFULLY!")
    print("=" * 70)


if __name__ == "__main__":
    run_demo()
