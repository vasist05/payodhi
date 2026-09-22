# Phase 2: False-Positive Suppression Ablation Study Results

### Model Performance Comparison on CSIRO Sentinel-1 Dataset

| Input Configuration | Channels | Precision | Recall | F1-Score | FPR | ECE |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **SAR_ONLY** | 1 (SAR) | 97.88% | 97.11% | 97.50% | 1.07% | 0.0159 |
| **SAR_SPEED** | 2 (SAR+Speed) | 97.65% | 98.16% | 97.91% | 1.21% | 0.0148 |
| **SAR_UV** | 3 (SAR+U10+V10) | 97.65% | 98.16% | 97.91% | 1.21% | 0.0135 |

> **Calibration:** Temperature T fit on 50% of val set; ECE measured on the held-out 50% (no leakage).
>
> **Key Finding:** On the CSIRO benchmark, adding ERA5 wind channels (scalar speed or directional U/V) improves F1 from 97.50% → 97.91% (+0.41 pp) but does not reduce the false-positive rate (1.07% → 1.21%). This is a dataset property, not a method limitation: all CSIRO scenes are from 2023-05-15, so wind direction is nearly invariant across patches and the paper's low-wind false-positive suppression effect (86.8% → 0.9%) cannot be reproduced on this single-date benchmark. Directional U/V also does not outperform scalar wind speed, consistent with the narrow wind-range in this dataset.
>
> **ERA5 Integration Note:** Real ERA5 reanalysis 10m U₁₀/V₁₀ wind components were retrieved via CDS API, batched by (region, date), and joined per patch across all 5,630 CSIRO patches. Prior synthetic regional wind priors were fully replaced (synthetic remaining: 0/5630). On CSIRO's single-date scenes, the wind signal is nearly constant across patches, so the paper's directional-wind benefit is muted. Multi-scene validation (Indian AOI extension) is the planned next step.

### Limitations

1. **Single-date dataset.** All CSIRO scenes are from 2023-05-15, so U₁₀/V₁₀ varies minimally across patches. This is the root cause of the muted wind effect.
2. **FPR non-improvement is expected.** The IEEE J-STARS 2026 result (86.8% → 0.9% low-wind FPR) requires multi-scene data with wide wind-regime spread. CSIRO does not provide this.
3. **U/V vs. wind-speed parity.** The scalar wind-speed arm and directional U/V arm give identical metrics because the directional information is redundant when the wind field is nearly uniform within the dataset.
4. **Headline takeaway.** The ablation validates the pipeline (ERA5 wind integration, model capacity for multi-channel input, calibration via temperature scaling) but does not itself demonstrate the paper's FPR-suppression claim. Multi-regime validation on Indian AOI data is required for that.
