import sys
from pathlib import Path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from datetime import datetime
from core.phase3_drift.drift_model.sampler import sample_scenarios
from core.phase3_drift.drift_model.forcing import make_synthetic_wind, make_synthetic_current

print("=== Sampler test: 5 scenarios ===")
s = sample_scenarios(72.5, 21.0, datetime(2024, 6, 15, 14, 0), n=5)
for x in s:
    print(f"  release={x['release_time']}  oil={x['oil_type']}")
print()

print("=== Forcing fallback test ===")
w = make_synthetic_wind()
c = make_synthetic_current()
print(f"  Created: {w}")
print(f"  Created: {c}")
print()

print("Session 2 OK")
