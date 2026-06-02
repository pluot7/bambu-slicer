"""
Example usage of bambu-slicer.

Prerequisites:
    1. Install BambuStudio from https://bambulab.com/en/download/studio
    2. Set BAMBU_STUDIO_PATH env var if not installed in default location

Run:
    python examples/example.py
"""
import os
import sys

# Add parent to path so we can import the local package
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bambu_slicer import slice_model, batch_slice_models, BAMBU_STUDIO_PATH


def main():
    print("=" * 60)
    print("Bambu Slicer — Example")
    print("=" * 60)
    print(f"BambuStudio path: {BAMBU_STUDIO_PATH}")
    print()

    # Replace with a path to your own 3D model
    model_path = input("Enter path to a 3MF/STL/OBJ/STEP file: ").strip()

    if not os.path.exists(model_path):
        print(f"File not found: {model_path}")
        sys.exit(1)

    # Single model slice
    print(f"\nSlicing: {os.path.basename(model_path)}")
    print("-" * 40)
    result = slice_model(model_path, infill=15, layer_height=0.20)

    if result:
        print(f"  Filament weight:     {result['weight_g']}g")
        print(f"  Main body weight:    {result['main_weight_g']}g")
        if result['main_weight_g']:
            support_pct = (result['weight_g'] - result['main_weight_g']) / result['weight_g'] * 100
            print(f"  Support weight:      ~{support_pct:.0f}%")
        print(f"  Infill:              {result['infill']}%")
        print(f"  Layer height:        {result['layer_height']}mm")
        print(f"  Slice time:          {result['sliced_time_ms']}ms")
        print(f"  Triangles:           {result['total_triangle_count']}")
        print(f"  Objects:             {result['objects_count']}")

        for obj in result.get('objects', []):
            bbox = obj.get('bbox', {})
            if bbox:
                print(f"    - {obj['name']}: {bbox['width']:.0f}x{bbox['depth']:.0f}x{bbox['height']:.0f}mm")
            else:
                print(f"    - {obj['name']}")

        print(f"\n  Volume: {result['original_volume_mm3']:.0f} mm³")
    else:
        print("  Slice failed!")

    # Batch demo (uncomment to try)
    # results = batch_slice_models([model_path, "another_model.stl"])
    # for path, res in results.items():
    #     print(f"{path}: {res['weight_g']}g" if res else f"{path}: failed")


if __name__ == "__main__":
    main()
