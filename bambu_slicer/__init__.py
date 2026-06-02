"""
Bambu Slicer — CLI-based 3D model slicing via BambuStudio.

Provides precise filament weight extraction by running the actual
BambuStudio slicing engine, not geometry estimation.

Typical usage:
    from bambu_slicer import slice_model, batch_slice_models

    result = slice_model("model.stl")
    if result:
        print(f"Filament weight: {result['weight_g']}g")
"""

from .slicer import slice_model, batch_slice_models, BAMBU_STUDIO_PATH

__all__ = ["slice_model", "batch_slice_models", "BAMBU_STUDIO_PATH"]
__version__ = "1.0.0"
