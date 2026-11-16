# Server CPU and GPU performance trends

Publication figures for selected server CPU and accelerator product families from 2007 to 2026. The CPU series are AMD EPYC and Intel Xeon. The accelerator series are AMD Instinct and NVIDIA Tesla / data center GPUs. The sample includes major architecture transitions and selected high-end or widely deployed products.

## Build the figures

In WSL, Linux or macOS, use Python 3.10 or newer with Matplotlib 3.7 or newer.

~~~sh
conda env create --name hardware-trends --file environment.yml
conda activate hardware-trends
./build.sh
~~~

With Matplotlib already installed, run `./build.sh` directly. On Windows, `python plot_trends.py` uses the same entry point. The `build/paper/` directory contains vector PDF files, 400 dpi PNG files and `figure-data.csv`. The PDFs use embedded STIX fonts and are 7.15 in (182 mm) wide. Panels are stacked in one column. Model labels are ordered by launch month from left to right, with leader lines to the data points.

Use `./build.sh --pdf` for PDF only, `--png` for PNG only, `--eps` for EPS, and `--output-dir PATH` for a different destination. Format flags can be combined.

| PDF basename | Metric | Panels |
| --- | --- | --- |
| `peak-*` | Theoretical peak throughput in TFLOPS for FP64 and FP32, and dense matrix throughput in GFLOPS for reduced precision. | FP64 and FP32, or TF32, FP16, BF16 and FP8 |
| `flop-per-byte-*` | Peak throughput divided by memory interface bandwidth, FLOP per byte | The same precision panels |
| `performance-per-watt-*` | Peak throughput divided by device design power, GFLOPS per W | The same precision panels |
| `memory-bandwidth` | Peak memory interface bandwidth, GB/s | CPUs and accelerators |
| `design-power` | Device design power, W | CPUs and accelerators |

In Overleaf, use `\includegraphics[width=\linewidth]{peak-fp64-fp32.pdf}`. For a tall four-panel figure, `\includegraphics[width=\linewidth,height=0.88\textheight,keepaspectratio]{peak-low-precision.pdf}` also constrains its height.

## Data and scope

- [devices.csv](data/devices.csv) stores the selected and archival SKUs. CPU values refer to a single socket. GPU values refer to one card or module, including both dies on a multi-die module. H100 and H200 use the SXM configurations. B200 and B300 refer to individual GPUs in HGX, and Rubin uses NVIDIA's single-GPU specification for NVL72.
- [cache.csv](data/cache.csv) stores last-level cache bandwidth, level, capacity when available, and the measurement or specification method. For the MI300X this is Infinity Cache. For the MI455X it is the aggregate global L2 across both fabric and cache dies. The derived FLOP per byte values are in `figure-data.csv`.
- [sources.csv](data/sources.csv) resolves the source IDs. See the row notes for configurations, estimates and rounding. Older observations draw in part on Karl Rupp's original tables.
- Launch dates are stored as `YYYY-MM` and positioned at the start of that month. Each subplot shows year labels spaced one year apart on shorter timelines and two years apart on longer ones. Logarithmic y-axes mark every integer multiple within each decade. Peak throughput and memory bandwidth share y-limits across panels within each figure. FP16 and BF16 share y-limits and ticks in the FLOP per byte figure. Other panels use their own y-limits. Limits are based on the plotted data with padding around the extrema. FLOP per byte panels label the 1, 2, and 5 multiples where the range permits. Narrow ranges use automatically selected round numbers on the logarithmic scale. Dates refer to the documented launch or public introduction. For example, H200 was introduced in November 2023 and shipped in 2024.
- Empty cells indicate unavailable, unverified or inapplicable values. EPYC 9996 contributes memory bandwidth and device design power. The CSV includes archival devices, vector-only FP16 and BF16 records, and numerical NVFP4 and MXFP4 records. Its `plotted` column identifies records selected for the precision figures.
- The original Gnuplot scripts and text tables are available for historical reproduction.

## Calculation and terminology

Let $P_{\mathrm{peak},p}$ denote the peak floating-point throughput at precision $p$, $B_\ell$ the bandwidth at memory or cache level $\ell$, and $W_{\mathrm{design}}$ the vendor-specified device design power.

$$
I^{*}_{\ell,p} = \frac{P_{\mathrm{peak},p}}{B_\ell},
\qquad
\eta_p = \frac{P_{\mathrm{peak},p}}{W_{\mathrm{design}}}.
$$

- **Peak FLOPS.** FLOPS means floating-point operations per second. One fused multiply-add counts as two FLOP. FP64 and FP32 use conventional native arithmetic. The HGX B200/B300 datasheets report FP64 in a combined FP64/FP64 Tensor Core row, with the native FP64 order of magnitude corroborated by the linked DGEMM benchmark. CPU architectural estimates use the base clock. GPU values use the manufacturer's specified operating point.
- **Reduced precision.** The plots use **peak dense matrix throughput** for TF32, FP16, BF16 and FP8. They use FP32 accumulation where the vendor gives separate accumulator options. **Peak vector throughput** denotes the throughput of general-purpose arithmetic units, including CPU SIMD and packed GPU arithmetic. Vector figures remain in the source specifications. FP8 covers E4M3/E5M2-family formats, including FNUZ. The TF32 series uses native hardware support. [AMD CDNA 4 architecture white paper, Table 1](https://www.amd.com/content/dam/amd/en/documents/instinct-tech-docs/white-papers/amd-cdna-4-architecture-whitepaper.pdf)
- **Arithmetic intensity.** A kernel's arithmetic intensity at a given level counts FLOP per byte crossing that interface. $I^{*}_{\ell,p}$ is the arithmetic intensity at which the bandwidth and compute ceilings intersect. The main-memory calculation uses peak interface bandwidth, in decimal GB/s. For Xeon X5482, the CPU-facing front-side bus sets the interface ceiling.
- **Cache bandwidth.** The cache calculation uses the same peak compute throughput and a published whole-device last-level cache bandwidth. The data indicate whether each bandwidth comes from a specification or a measurement, with workload and traffic-count details where available.
- **Device design power.** This term covers vendor TDP and the specified CPU, board or module power limit. The exact basis appears in each row. The resulting GFLOPS per W describes the hardware specifications. Application power efficiency is obtained by measuring throughput and power over the same device boundary.

## Attribution and license

Adapted from [Karl Rupp's CPU, GPU and MIC Hardware Characteristics over Time](https://www.karlrupp.net/2013/06/cpu-gpu-and-mic-hardware-characteristics-over-time/) and its [source repository](https://github.com/karlrupp/cpu-gpu-mic-comparison). This revision selects and updates devices, normalizes configurations, adds reduced-precision and cache data, and replaces the figure-generation workflow. The original data is licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). See [LICENSE.txt](LICENSE.txt).
