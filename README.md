<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://placehold.co/600x120/1a1a2e/f97316?text=Bambu+Slicer&font=source-sans-pro">
    <img alt="Bambu Slicer" src="https://placehold.co/600x120/f8fafc/1e293b?text=Bambu+Slicer&font=source-sans-pro" width="480">
  </picture>
</p>

<p align="center">
  <strong>Stop guessing filament weight. Let the actual slicer tell you.</strong>
</p>

<p align="center">
  <a href="#"><img src="https://img.shields.io/badge/python-3.8+-blue" alt="Python 3.8+"></a>
  <a href="#"><img src="https://img.shields.io/badge/license-MIT-green" alt="MIT"></a>
  <a href="#"><img src="https://img.shields.io/badge/dependencies-zero-brightgreen" alt="Zero dependencies"></a>
</p>

---

**Bambu Slicer** calls BambuStudio's CLI to slice your 3D models and extract **real** filament weight from the generated G-code — not an estimate, but what the slicing engine actually computed. Tested against Bambu Lab P1P prints with **< 5% deviation**.

## Why not geometry estimation?

| Method | Deviation | Real-world test (bunny) |
|--------|-----------|------------------------|
| Bounding box × volume × density | 40–200% | 36.8g vs 19.9g actual |
| **BambuStudio CLI slice (this tool)** | **< 5%** | **19.9g vs 19.9g actual** |

Geometry can't account for infill pattern, wall loops, support material, or layer adhesion profiles. Only the real slicer knows.

## Quickstart

### 1. Install BambuStudio

Download from [bambulab.com](https://bambulab.com/en/download/studio) (free).

### 2. Install bambu-slicer

```bash
pip install bambu-slicer
```

Or straight from GitHub:

```bash
pip install git+https://github.com/YOUR_USERNAME/bambu-slicer.git
```

### 3. Set your BambuStudio path (if not in default location)

```bash
# Windows PowerShell
$env:BAMBU_STUDIO_PATH = "D:\BambuStudio\bambu-studio.exe"
```

Or set it permanently in System Environment Variables.

### 4. Slice something

```python
from bambu_slicer import slice_model

result = slice_model("benchy.stl")
print(f"Weight: {result['weight_g']}g")   # 14.24g
```

That's it. One function call.

## Use cases

- **E-commerce platforms** — show buyers the real material cost per model
- **Print farm management** — batch-calculate filament usage across hundreds of models
- **CI/CD pipelines** — automatically compute print cost before queueing
- **Weight calculation in web apps** — replace inaccurate geometry formulas

## API

### `slice_model(file_path, infill=15, layer_height=0.20, timeout_seconds=120)`

Returns a dict (or `None` on failure):

```python
{
    "weight_g": 14.24,           # ← total filament weight (g)
    "main_weight_g": 12.10,      # weight excluding supports
    "filament_id": "GFL99",
    "infill": 15,
    "layer_height": 0.20,
    "wall_loops": 2,
    "sliced_time_ms": 2847,
    "total_triangle_count": 84252,
    "objects_count": 1,
    "original_volume_mm3": 15630.0,
    "objects": [
        {
            "name": "benchy",
            "triangle_count": 84252,
            "bbox": {"width": 60.0, "depth": 31.0, "height": 48.0}
        }
    ]
}
```

### `batch_slice_models(file_paths, infill=15, layer_height=0.20)`

Returns `dict[str, dict | None]` mapping paths to results.

### CLI

```bash
bambu-slicer model.stl --infill 20 --layer 0.16
```

## Supported formats

| Format | Support |
|--------|---------|
| `.3mf` | Native — sliced directly |
| `.stl` | Auto-wrapped via `--export-3mf` |
| `.obj` | Auto-wrapped |
| `.step` / `.stp` | Auto-wrapped |

## Default slicing config

| Parameter | Value |
|-----------|-------|
| Printer | Bambu Lab P1P (0.4mm nozzle) |
| Filament | Generic PLA (1.24 g/cm³) |
| Profile | 0.20mm Standard |
| Infill | 15% grid |
| Walls | 2 |
| Top layers | 5 |
| Bottom layers | 3 |
| Build volume | 256 × 256 × 256 mm |

Swap the `bambu_template.3mf` file to customize for your printer/filament.

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `BAMBU_STUDIO_PATH` | auto-detect | Path to `bambu-studio.exe` |
| `SLICE_INFILL` | 15 | Default infill % |
| `SLICE_LAYER_HEIGHT` | 0.20 | Default layer height (mm) |
| `SLICE_TIMEOUT` | 120 | Slice timeout (seconds) |

## How it works

```
Input model (3MF/STL/OBJ/STEP)
        │
        ▼
[Export to 3MF] ── non-3MF formats are auto-wrapped
        │
        ▼
[Merge with config template] ── P1P + Generic PLA profile
        │
        ▼
[BambuStudio --slice] ── real slicing engine
        │
        ▼
[Parse result.json] ── extract weight, bbox, metadata
        │
        ▼
Return dict with precise filament weight
```

## FAQ

**Q: BambuStudio not found?** Set `BAMBU_STUDIO_PATH` env var.

**Q: Slow slicing?** Models with >500k triangles may take 10s+. Normal: 2–4s.

**Q: weight_g vs main_weight_g?** `main_weight_g` excludes support material.

**Q: Can I use a different printer?** Replace the `bambu_template.3mf` file and adjust `_patch_project_config()`.

**Q: I don't have a Bambu printer but still need accurate weight?** BambuStudio works standalone for slicing — you don't need a Bambu printer to use this tool.

## Limitations

- Requires BambuStudio installed (Windows only)
- Slicing adds ~2–4s per model
- BambuStudio CLI output parsing is format-specific — may break with future BambuStudio updates


