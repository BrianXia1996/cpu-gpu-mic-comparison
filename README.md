# Server CPU and GPU Performance Trends

Publication-ready figures comparing server CPU and accelerator product families from 2007 to 2026.

| Category | Families covered |
| --- | --- |
| CPUs | AMD EPYC, Intel Xeon |
| Accelerators | AMD Instinct, NVIDIA Tesla / data center GPUs |

The sample covers major architecture transitions plus selected high-end or widely deployed products.

## Contents

- [Quick start](#quick-start)
- [Output figures](#output-figures)
- [Using the figures in LaTeX](#using-the-figures-in-latex)
- [Data files](#data-files)
- [Conventions and scope](#conventions-and-scope)
- [Metrics and terminology](#metrics-and-terminology)
- [Attribution and license](#attribution-and-license)

## Quick start

**Requirements:** Python 3.10+ and Matplotlib 3.7+ (WSL, Linux or macOS).

```sh
conda env create --name hardware-trends --file environment.yml
conda activate hardware-trends
./build.sh
```

If Matplotlib is already installed, run `./build.sh` directly. On Windows, `python plot_trends.py` is the same entry point.

### Build options

| Flag | Effect |
| --- | --- |
| `--pdf` | PDF only |
| `--png` | PNG only |
| `--eps` | EPS output |
| `--output-dir PATH` | Write to a different directory |

Format flags can be combined.

## Output figures

Results go to `build/paper/`:

- Vector PDFs (embedded STIX fonts, 7.15 in / 182 mm wide)
- 400 dpi PNGs
- `figure-data.csv` with the plotted and derived values

Panels are stacked in a single column. Model labels are ordered by launch month, left to right, with leader lines to the data points.

| PDF basename | Metric | Panels |
| --- | --- | --- |
| `peak-*` | Theoretical peak throughput: TFLOPS for FP64 and FP32, GFLOPS (dense matrix) for reduced precision | FP64 and FP32, or TF32, FP16, BF16 and FP8 |
| `flop-per-byte-*` | Peak throughput ÷ memory interface bandwidth (FLOP/byte) | Same precision panels |
| `performance-per-watt-*` | Peak throughput ÷ device design power (GFLOPS/W) | Same precision panels |
| `memory-bandwidth` | Peak memory interface bandwidth (GB/s) | CPUs and accelerators |
| `design-power` | Device design power (W) | CPUs and accelerators |

## Using the figures in LaTeX

```latex
\includegraphics[width=\linewidth]{peak-fp64-fp32.pdf}
```

For a tall four-panel figure, also constrain the height:

```latex
\includegraphics[width=\linewidth,height=0.88\textheight,keepaspectratio]{peak-low-precision.pdf}
```

## Data files

| File | Contents |
| --- | --- |
| [data/devices.csv](data/devices.csv) | Selected and archival SKUs. The `plotted` column marks records used in the precision figures. |
| [data/cache.csv](data/cache.csv) | Last-level cache bandwidth, level, capacity (when available) and measurement or specification method. |
| [data/sources.csv](data/sources.csv) | Resolves source IDs. Row notes describe configurations, estimates and rounding. |

The original Gnuplot scripts and text tables (`*.gnuplot`, `data-*.txt`) remain for historical reproduction.

## Conventions and scope

### What a row represents

- **CPUs:** a single socket.
- **GPUs:** one card or module, including both dies of a multi-die module.
- **H100 / H200:** SXM configurations.
- **B200 / B300:** individual GPUs in HGX.
- **Rubin:** NVIDIA's single-GPU specification for NVL72.
- **MI300X cache:** Infinity Cache. **MI455X cache:** aggregate global L2 across both fabric and cache dies.

### Dates

Launch dates are stored as `YYYY-MM` and placed at the start of that month. They refer to the documented launch or public introduction. For example, H200 was introduced in November 2023 and shipped in 2024.

### Missing and special values

- Empty cells mean unavailable, unverified or inapplicable.
- EPYC 9996 contributes only memory bandwidth and device design power.
- The CSV also includes archival devices, vector-only FP16/BF16 records, and numerical NVFP4 and MXFP4 records.

### Axes

- Year labels are spaced one year apart on shorter timelines and two years apart on longer ones.
- Logarithmic y-axes mark every integer multiple within each decade.
- Peak throughput and memory bandwidth share y-limits across panels within each figure. FP16 and BF16 share y-limits and ticks in the FLOP/byte figure. Other panels use their own limits.
- Limits are based on the plotted data, with padding around the extrema.
- FLOP/byte panels label the 1, 2 and 5 multiples where the range permits. Narrow ranges use automatically selected round numbers.

## Metrics and terminology

Let $P_{\mathrm{peak},p}$ be peak floating-point throughput at precision $p$, $B_\ell$ the bandwidth at memory or cache level $\ell$, and $W_{\mathrm{design}}$ the vendor-specified device design power.

$$
I^{*}_{\ell,p} = \frac{P_{\mathrm{peak},p}}{B_\ell},
\qquad
\eta_p = \frac{P_{\mathrm{peak},p}}{W_{\mathrm{design}}}.
$$

### Peak FLOPS

FLOPS means floating-point operations per second. One fused multiply-add counts as two FLOP.

- FP64 and FP32 use conventional native arithmetic.
- HGX B200/B300 datasheets report FP64 in a combined FP64/FP64 Tensor Core row. The native FP64 order of magnitude is corroborated by the linked DGEMM benchmark.
- CPU architectural estimates use the base clock. GPU values use the manufacturer's specified operating point.

### Reduced precision

- The plots use **peak dense matrix throughput** for TF32, FP16, BF16 and FP8, with FP32 accumulation where vendors offer separate accumulator options.
- **Peak vector throughput** is the throughput of general-purpose arithmetic units (CPU SIMD and packed GPU arithmetic). It is not plotted but remains in the source specifications.
- FP8 covers E4M3/E5M2-family formats, including FNUZ.
- The TF32 series uses native hardware support. See [AMD CDNA 4 architecture white paper, Table 1](https://www.amd.com/content/dam/amd/en/documents/instinct-tech-docs/white-papers/amd-cdna-4-architecture-whitepaper.pdf).

### Arithmetic intensity (FLOP per byte)

A kernel's arithmetic intensity at a given level counts FLOP per byte crossing that interface. $I^{*}_{\ell,p}$ is the intensity at which the bandwidth and compute ceilings intersect.

- **Main memory:** uses peak interface bandwidth in decimal GB/s. For Xeon X5482, the CPU-facing front-side bus sets the ceiling.
- **Cache:** uses the same peak compute throughput and a published whole-device last-level cache bandwidth. The data record whether each value is a specification or a measurement, with workload and traffic-count details where available.

### Device design power

This covers vendor TDP and the specified CPU, board or module power limit. The exact basis is listed per row. GFLOPS per W describes the hardware specification. Application power efficiency requires measuring throughput and power over the same device boundary.

## Attribution and license

Adapted from [Karl Rupp's CPU, GPU and MIC Hardware Characteristics over Time](https://www.karlrupp.net/2013/06/cpu-gpu-and-mic-hardware-characteristics-over-time/) and its [source repository](https://github.com/karlrupp/cpu-gpu-mic-comparison). Older observations draw in part on Karl Rupp's original tables.

This revision selects and updates devices, normalizes configurations, adds reduced-precision and cache data, and replaces the figure-generation workflow.

The original data is licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). See [LICENSE.txt](LICENSE.txt).
