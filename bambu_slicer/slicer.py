#!/usr/bin/env python3
"""
BambuStudio CLI 精确切片工具
=============================
通过调用 BambuStudio 命令行对 3D 模型进行切片，从 result.json 中提取精确耗材重量。

使用条件:
  1. 已安装 BambuStudio（Windows 版），下载地址:
     https://bambulab.com/en/download/studio
  2. BambuStudio 路径配置正确（见下方配置说明）
  3. 支持 STL/OBJ/STEP/3MF 格式输入

使用方法:
  from bambu_slicer import slice_model
  result = slice_model("model.stl")
  print(f"重量: {result['weight_g']}g")

环境变量:
  BAMBU_STUDIO_PATH  BambuStudio exe 路径（默认自动搜索常见安装位置）
  SLICE_TIMEOUT      切片超时秒数（默认 120）
  SLICE_INFILL       填充率 %（默认 15）
  SLICE_LAYER_HEIGHT 层高 mm（默认 0.20）
"""

import os
import json
import subprocess
import tempfile
import shutil
import zipfile
import re
from typing import Optional, Dict, List

# ============================================================
# 1. 配置
# ============================================================

def _find_bambu_studio() -> str:
    """自动搜索 BambuStudio 安装路径"""
    candidates = [
        os.environ.get("BAMBU_STUDIO_PATH", ""),
        # 常见安装位置
        r"C:\Program Files\BambuStudio\bambu-studio.exe",
        r"C:\Program Files\BambuStudio\BambuStudio.exe",
        r"C:\Program Files (x86)\BambuStudio\bambu-studio.exe",
        r"D:\Program Files\BambuStudio\bambu-studio.exe",
    ]
    # 也扫描常见父目录下的版本号子目录
    base_dirs = [
        r"C:\Program Files\BambuStudio",
        r"C:\Program Files (x86)\BambuStudio",
        r"D:\Program Files\BambuStudio",
        r"E:\tuoz",
    ]
    for base in base_dirs:
        if os.path.isdir(base):
            for entry in os.listdir(base):
                full = os.path.join(base, entry, "bambu-studio.exe")
                if os.path.isfile(full):
                    candidates.append(full)

    for c in candidates:
        if c and os.path.isfile(c):
            return c
    # 最后兜底
    return r"C:\Program Files\BambuStudio\bambu-studio.exe"


BAMBU_STUDIO_PATH = _find_bambu_studio()
DEFAULT_INFILL = int(os.environ.get("SLICE_INFILL", "15"))
DEFAULT_LAYER_HEIGHT = float(os.environ.get("SLICE_LAYER_HEIGHT", "0.20"))
SLICE_TIMEOUT = int(os.environ.get("SLICE_TIMEOUT", "120"))

# 源 3MF 模板路径（Skill 自带的，打包后按此路径查找）
# 模板路径：pip 安装后模板放在包同级目录（data_files 或 package_data）
_SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
# 优先：pip install 后的包同级目录
_SOURCE_CANDIDATES = [
    os.path.join(_SKILL_DIR, "..", "bambu_template.3mf"),         # pip install -e .
    os.path.join(_SKILL_DIR, "..", "..", "bambu_template.3mf"),    # repository root
    os.path.join(_SKILL_DIR, "bambu_template.3mf"),                 # same dir fallback
]
SOURCE_3MF = next((p for p in _SOURCE_CANDIDATES if os.path.exists(p)), _SOURCE_CANDIDATES[0])


# ============================================================
# 2. 辅助函数
# ============================================================

def _decode_output(result) -> str:
    """解码 subprocess 输出（自动处理 GBK/UTF-8）"""
    if result.stdout:
        try:
            return result.stdout.decode('utf-8', errors='replace')
        except Exception:
            return result.stdout.decode('gbk', errors='replace')
    return ''


def _fallback_trimesh_convert(file_path: str) -> Optional[str]:
    """兜底：用 trimesh 直接导出 3MF（不带 Bambu 配置，但至少能试试）"""
    try:
        import trimesh
        mesh = trimesh.load(file_path)
        if isinstance(mesh, trimesh.Scene):
            meshes = [g for g in mesh.geometry.values() if isinstance(g, trimesh.Trimesh)]
            if not meshes:
                return None
            mesh = trimesh.util.concatenate(meshes) if len(meshes) > 1 else meshes[0]
        if not isinstance(mesh, trimesh.Trimesh) or mesh.vertices.shape[0] == 0:
            return None
        tmp_3mf = tempfile.mktemp(suffix='.3mf', prefix='bambu_fallback_')
        mesh.export(tmp_3mf, file_type='3mf')
        return tmp_3mf
    except Exception as e:
        print(f"[BambuSlicer] trimesh 兜底失败: {e}")
        return None


# ============================================================
# 3. 模板管理
# ============================================================

def _create_blank_bambu_3mf() -> Optional[str]:
    """
    从已知可切片 3MF 创建空白模板（保留配置，去除模型数据）
    """
    src_path = SOURCE_3MF
    if not os.path.exists(src_path):
        # fallback: walk known paths
        alt_candidates = [
            os.path.normpath(os.path.join(_SKILL_DIR, "..", "assets", "bambu_template.3mf")),
            os.path.normpath(os.path.join(_SKILL_DIR, "..", "bambu_template.3mf")),
        ]
        for alt in alt_candidates:
            if os.path.exists(alt):
                src_path = alt
                break
        if not os.path.exists(src_path):
            print(f"[BambuSlicer] 模板文件不存在")
            return None

    tmp = tempfile.mktemp(suffix='.3mf', prefix='bambu_blank_')

    with zipfile.ZipFile(src_path, 'r') as src:
        with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as dst:
            for name in src.namelist():
                if name.startswith('Auxiliaries/'):
                    continue
                if name.startswith('3D/Objects/'):
                    continue
                if name == '3D/3dmodel.model':
                    xml = src.read(name).decode('utf-8')
                    xml = re.sub(r'<object[^>]*>.*?</object>', '', xml, flags=re.DOTALL)
                    xml = re.sub(r'<components>.*?</components>', '', xml, flags=re.DOTALL)
                    xml = re.sub(r'<build>.*?</build>', '<build>\n  </build>', xml, flags=re.DOTALL)
                    xml = re.sub(r'<resources>.*?</resources>', '<resources>\n  </resources>', xml, flags=re.DOTALL)
                    dst.writestr(name, xml.encode('utf-8'))
                    continue
                if name == 'Metadata/model_settings.config':
                    dst.writestr(name, b'<?xml version="1.0" encoding="UTF-8"?>\n<settings />\n')
                    continue
                if name == 'Metadata/cut_information.xml':
                    continue
                dst.writestr(name, src.read(name))
    return tmp


def _patch_project_config(config_json: str) -> str:
    """
    对 project_settings.config 应用补丁，匹配通用切片参数：
    - 打印机: Bambu Lab P1P 0.4 nozzle
    - 耗材: Generic PLA（密度 1.24 g/cm³）
    - 工艺: 0.20mm Standard, 15% 填充, 2 壁线
    """
    config = json.loads(config_json)

    # 打印机
    config['printer_model'] = 'Bambu Lab P1P'
    config['printer_settings_id'] = 'Bambu Lab P1P 0.4 nozzle'
    config['print_compatible_printers'] = ['Bambu Lab P1P 0.4 nozzle']
    config['upward_compatible_machine'] = ['Bambu Lab P1P 0.4 nozzle']
    config['printer_technology'] = 'FFF'
    config['printer_structure'] = 'corexy'

    # 耗材（数组格式！BambuStudio 期望数组字符串）
    config['filament_settings_id'] = ['Generic PLA @BBL P1P 0.4 nozzle']
    config['filament_type'] = ['PLA']
    config['filament_vendor'] = ['Generic']
    config['filament_density'] = ['1.24']
    config['filament_cost'] = ['20']
    config['filament_ids'] = ['GFL99']
    config['filament_flow_ratio'] = ['0.98']
    config['default_filament_profile'] = ['Generic PLA @BBL P1P']

    # 工艺
    config['print_settings_id'] = '0.20mm Standard @BBL P1P'
    config['default_print_profile'] = '0.20mm Standard @BBL P1P'
    config['layer_height'] = '0.2'
    config['sparse_infill_density'] = '15%'
    config['wall_loops'] = '2'
    config['bottom_shell_layers'] = '3'
    config['top_shell_layers'] = '5'
    config['seam_position'] = 'aligned'
    config['sparse_infill_pattern'] = 'grid'
    config['initial_layer_print_height'] = '0.2'
    config['initial_layer_line_width'] = '0.5'
    config['line_width'] = '0.42'

    # 机器限制 (P1P, 256mm³)
    config['printable_area'] = ['0x0', '256x0', '256x256', '0x256']
    config['printable_height'] = '256'

    return json.dumps(config, ensure_ascii=False, indent=2)


def _export_stl_as_bambu_3mf(stl_path: str, output_path: str) -> bool:
    """用 BambuStudio --export-3mf 将 STL 转为 3MF"""
    cmd = [BAMBU_STUDIO_PATH, "--export-3mf", output_path, stl_path]
    try:
        result = subprocess.run(
            cmd, capture_output=True, timeout=120,
            cwd=os.path.dirname(BAMBU_STUDIO_PATH),
        )
        if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
            return True
        return False
    except Exception as e:
        print(f"[BambuSlicer] --export-3mf 异常: {e}")
        return False


def _merge_config_into_3mf(mesh_3mf_path: str, blank_path: str) -> str:
    """合并空白模板的配置到网格 3MF"""
    output = tempfile.mktemp(suffix='.3mf', prefix='bambu_merged_')
    with zipfile.ZipFile(mesh_3mf_path, 'r') as mesh_zf:
        mesh_files = set(mesh_zf.namelist())
        with zipfile.ZipFile(blank_path, 'r') as tmpl_zf:
            tmpl_files = set(tmpl_zf.namelist())
            with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as out:
                for name in sorted(tmpl_files):
                    if name.startswith('3D/'):
                        continue
                    if name == 'Metadata/project_settings.config':
                        raw = tmpl_zf.read(name).decode('utf-8')
                        out.writestr(name, _patch_project_config(raw).encode('utf-8'))
                    else:
                        out.writestr(name, tmpl_zf.read(name))
                for name in sorted(mesh_files):
                    if name not in tmpl_files or name.startswith('3D/'):
                        out.writestr(name, mesh_zf.read(name))
    return output


def _wrap_model_for_slicing(file_path: str) -> Optional[str]:
    """
    将任意模型文件包装为可被 BambuStudio 切片的 3MF
    - 3MF 直接返回
    - STL/OBJ/STEP: --export-3mf + 合并配置
    """
    ext = os.path.splitext(file_path)[1].lower()
    if ext == '.3mf':
        return file_path

    blank = _create_blank_bambu_3mf()
    if not blank:
        print("[BambuSlicer] 无法创建空白模板，尝试 trimesh 兜底")
        return _fallback_trimesh_convert(file_path)

    try:
        if ext in ('.stl', '.obj', '.step', '.stp'):
            temp_mesh = tempfile.mktemp(suffix='.3mf', prefix='bambu_mesh_')
            if not _export_stl_as_bambu_3mf(file_path, temp_mesh):
                print("[BambuSlicer] --export-3mf 失败，尝试 trimesh 兜底")
                return _fallback_trimesh_convert(file_path)
            result = _merge_config_into_3mf(temp_mesh, blank)
            try:
                os.unlink(temp_mesh)
            except Exception:
                pass
            return result
        return _fallback_trimesh_convert(file_path)
    except Exception as e:
        print(f"[BambuSlicer] 包装失败: {e}")
        return _fallback_trimesh_convert(file_path)
    finally:
        try:
            os.unlink(blank)
        except Exception:
            pass


# ============================================================
# 4. 核心 API
# ============================================================

def slice_model(
    file_path: str,
    material: str = "pla",
    infill: int = DEFAULT_INFILL,
    layer_height: float = DEFAULT_LAYER_HEIGHT,
    timeout_seconds: int = SLICE_TIMEOUT,
) -> Optional[Dict]:
    """
    调用 BambuStudio CLI 对模型进行精确切片。

    参数:
        file_path: 模型文件路径（3MF / STL / OBJ / STEP）
        material: 材料类型（仅标注用途，切片配置固定为 Generic PLA）
        infill: 填充率 %（默认 15）
        layer_height: 层高 mm（默认 0.20）
        timeout_seconds: 切片超时秒数（默认 120）

    返回:
        {
            "weight_g": float,          # 总耗材重量 (g) ← 核心值
            "main_weight_g": float,     # 主体耗材重量 (g)
            "filament_id": str,         # 耗材 ID
            "infill": int,              # 实际填充率
            "layer_height": float,      # 实际层高
            "wall_loops": int,          # 壁线数
            "sliced_time_ms": int,      # 切片耗时 (毫秒)
            "prepare_time_ms": int,     # 准备耗时 (毫秒)
            "total_predication_ms": int,# 预估总耗时 (毫秒)
            "total_triangle_count": int,# 总三角面数
            "objects_count": int,       # 物体数量
            "original_volume_mm3": float,# 原始模型体积 (mm³)
            "objects": [                # 各物体明细
                {
                    "name": str,
                    "triangle_count": int,
                    "bbox": {"width": float, "depth": float, "height": float}
                }
            ]
        }
        失败时返回 None。
    """
    if not os.path.exists(BAMBU_STUDIO_PATH):
        print(f"[BambuSlicer] BambuStudio 未找到: {BAMBU_STUDIO_PATH}")
        print("[BambuSlicer] 请设置环境变量 BAMBU_STUDIO_PATH 指向 bambu-studio.exe")
        return None
    if not os.path.exists(file_path):
        print(f"[BambuSlicer] 模型文件不存在: {file_path}")
        return None

    # 非 3MF 格式 → 包装
    ext = os.path.splitext(file_path)[1].lower()
    source_for_slice = file_path
    need_cleanup = False

    if ext in ('.stl', '.obj', '.step', '.stp'):
        print(f"[BambuSlicer] 包装 {ext} 文件为 Bambu 3MF...")
        temp_3mf = _wrap_model_for_slicing(file_path)
        if temp_3mf:
            source_for_slice = temp_3mf
            need_cleanup = True
        else:
            print("[BambuSlicer] 包装失败，跳过")
            return None

    tmp_dir = tempfile.mkdtemp(prefix="bambu_slice_")

    try:
        # 获取模型基本信息
        info_result = _get_info(source_for_slice)

        # 构造切片命令
        cmd = [BAMBU_STUDIO_PATH, "--slice", "1", "--outputdir", tmp_dir, source_for_slice]
        print(f"[BambuSlicer] 切片中: {os.path.basename(file_path)} "
              f"(填充={infill}%, 层高={layer_height}mm)")

        subprocess.run(
            cmd, capture_output=True,
            timeout=timeout_seconds,
            cwd=os.path.dirname(BAMBU_STUDIO_PATH),
        )

        # 读取 result.json
        result_json_path = os.path.join(tmp_dir, "result.json")
        if not os.path.exists(result_json_path):
            print("[BambuSlicer] 未找到 result.json，切片可能失败")
            return None

        with open(result_json_path, "r", encoding="utf-8") as f:
            slice_data = json.load(f)

        # 提取重量
        sliced_plates = slice_data.get("sliced_plates", [])
        if not sliced_plates:
            print("[BambuSlicer] 切片结果无盘子数据")
            return None

        plate = sliced_plates[0]
        filaments = plate.get("filaments", [])
        if not filaments:
            print("[BambuSlicer] 切片结果无耗材数据")
            return None

        filament = filaments[0]
        weight_g = filament.get("total_used_g", 0)
        main_weight_g = filament.get("main_used_g", 0)
        filament_id = filament.get("filament_id", "")

        # 提取各物体 bbox
        plate_objects = plate.get("objects", [])
        objects_data = []
        for obj in plate_objects:
            entry = {"name": obj.get("name", ""), "triangle_count": obj.get("triangle_count", 0)}
            bbox = obj.get("bbox", {})
            if bbox:
                entry["bbox"] = {
                    "width": bbox.get("width", 0),
                    "depth": bbox.get("depth", 0),
                    "height": bbox.get("height", 0),
                }
            objects_data.append(entry)

        result_data = {
            "weight_g": round(weight_g, 2),
            "main_weight_g": round(main_weight_g, 2),
            "filament_id": filament_id,
            "infill": slice_data.get("sparse_infill_density", DEFAULT_INFILL),
            "layer_height": slice_data.get("layer_height", DEFAULT_LAYER_HEIGHT),
            "wall_loops": slice_data.get("wall_loops", 2),
            "sliced_time_ms": plate.get("sliced_time", 0),
            "prepare_time_ms": slice_data.get("prepare_time", 0),
            "total_predication_ms": plate.get("total_predication", 0),
            "feature_times": plate.get("feature_type_times", {}),
            "total_triangle_count": plate.get("triangle_count", 0),
            "objects_count": len(plate_objects),
            "original_volume_mm3": info_result.get("volume", 0) if info_result else 0,
            "objects": objects_data,
        }

        print(f"[BambuSlicer] ✅ 切片完成: {weight_g:.2f}g")
        return result_data

    except subprocess.TimeoutExpired:
        print(f"[BambuSlicer] ⏱ 切片超时 ({timeout_seconds}s)")
        return None
    except subprocess.CalledProcessError as e:
        print(f"[BambuSlicer] 切片失败: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"[BambuSlicer] result.json 解析失败: {e}")
        return None
    except Exception as e:
        print(f"[BambuSlicer] 未知错误: {type(e).__name__}: {e}")
        return None
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        if need_cleanup and os.path.exists(source_for_slice):
            try:
                os.remove(source_for_slice)
            except Exception:
                pass


def _get_info(file_path: str) -> Optional[Dict]:
    """调用 BambuStudio --info 获取模型基本信息"""
    try:
        result = subprocess.run(
            [BAMBU_STUDIO_PATH, "--info", file_path],
            capture_output=True, timeout=30,
            cwd=os.path.dirname(BAMBU_STUDIO_PATH),
        )
        stdout = _decode_output(result)
        info = {}
        for line in stdout.split('\n'):
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()
                try:
                    info[key] = float(value)
                except ValueError:
                    info[key] = value
        return info if info else None
    except Exception:
        return None


def batch_slice_models(
    file_paths: List[str],
    material: str = "pla",
    infill: int = DEFAULT_INFILL,
    layer_height: float = DEFAULT_LAYER_HEIGHT,
) -> Dict[str, Optional[Dict]]:
    """批量切片多个模型"""
    results = {}
    for fp in file_paths:
        results[fp] = slice_model(fp, material, infill, layer_height)
    return results


# ============================================================
# 5. CLI 入口
# ============================================================

def main():
    """命令行入口：python slicer.py <模型文件路径>"""
    import sys
    if len(sys.argv) < 2:
        print("用法: python slicer.py <模型文件> [--infill N] [--layer N]")
        print("示例: python slicer.py model.stl --infill 20 --layer 0.16")
        sys.exit(1)

    file_path = sys.argv[1]
    kwargs = {}
    if "--infill" in sys.argv:
        idx = sys.argv.index("--infill")
        kwargs["infill"] = int(sys.argv[idx + 1])
    if "--layer" in sys.argv:
        idx = sys.argv.index("--layer")
        kwargs["layer_height"] = float(sys.argv[idx + 1])

    result = slice_model(file_path, **kwargs)
    if result:
        print("\n===== 切片结果 =====")
        print(f"  耗材重量: {result['weight_g']}g")
        print(f"  填充率:   {result['infill']}%")
        print(f"  层高:     {result['layer_height']}mm")
        print(f"  切片耗时: {result['sliced_time_ms']}ms")
        print(f"  三角面数: {result['total_triangle_count']}")
        print(f"  物体数量: {result['objects_count']}")
        if result['objects']:
            print(f"  各物体:")
            for obj in result['objects']:
                bbox = obj.get('bbox', {})
                if bbox:
                    print(f"    - {obj['name']}: "
                          f"{bbox['width']:.1f}x{bbox['depth']:.1f}x{bbox['height']:.1f}mm "
                          f"({obj['triangle_count']} 三角面)")
                else:
                    print(f"    - {obj['name']} ({obj['triangle_count']} 三角面)")
        print(f"  原始体积: {result['original_volume_mm3']:.0f}mm³")
    else:
        print("切片失败")
        sys.exit(1)


if __name__ == "__main__":
    main()
