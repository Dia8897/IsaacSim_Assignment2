import json
import re
import hashlib
from pathlib import Path
from typing import Any

import numpy as np
import omni.replicator.core as rep
from omni.replicator.core import AnnotatorRegistry, BackendDispatch, Writer
from omni.replicator.core import functional as F
from omni.replicator.core.scripts.backends import BaseBackend

class CustomWriter(Writer):
    def __init__(
        self,
        rgb: bool = True,
        depth: bool = True,
        semantic: bool = True,
        instance: bool = True,
        bbox_2d: bool = True,
        pointcloud:bool= False,
        output_dir: str | None = None,
        backend: BaseBackend | None = None,
        camera_fov_degrees: float = 60.0,
        **kwargs,

    ):
        self.version ="0.0.1"
        self.data_structure = "renderProduct"

        if output_dir is None or not str(output_dir).strip():
            raise ValueError("CustomWriter requires a valid output_dir.")

        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        if backend is not None and not isinstance(backend, BaseBackend):
            raise TypeError(
                "`backend` must inherit from "
                "`omni.replicator.core.scripts.backends.BaseBackend`."
            )
        if backend is not None:
            self.backend = backend
        else:
            
            try:
                self.backend = BackendDispatch(output_dir=str(self.output_dir))
            except TypeError:
                self.backend = BackendDispatch(
                    {"paths": {"out_dir": str(self.output_dir)}}
                )
        if pointcloud:
            rgb =True
            semantic = True
            depth = True        
        self.enable_rgb = rgb 
        self.enable_depth = depth
        self.enable_semantic = semantic 
        self.enable_instance = instance 
        self.enable_bbox_2d = bbox_2d
        self.enable_pointcloud = pointcloud
        self.camera_fov_degrees = float(camera_fov_degrees)

        self.annotators = []  
        if rgb:
            self.annotators.append(AnnotatorRegistry.get_annotator("rgb"))
        """We used the distance_to_image_plane annotator for the depth. It represents per-pixel z-depth values in meters, which is more useful for many applications than the normalized depth values that the default depth annotator provides."""    

        if depth:
            self.annotators.append(AnnotatorRegistry.get_annotator("distance_to_image_plane"))   
        if semantic:
            self.annotators.append(
                AnnotatorRegistry.get_annotator(
                    "semantic_segmentation",
                    init_params={
                        "semanticTypes": ["class"],
                        "colorize": False,
                    },
                )
            )    

        if instance:
            self.annotators.append(
                AnnotatorRegistry.get_annotator(
                    "instance_segmentation",
                    init_params={
                        "semanticTypes": ["class"],
                        "colorize": False,
                    },
                )
            )
        if bbox_2d:
            self.annotators.append(
                AnnotatorRegistry.get_annotator(
                    "bounding_box_2d_tight",
                    init_params={
                        "semanticTypes": ["class"],
                        #"colorize": False,
                    },
                )
            )    
        


        self._frame_id = 0

        self._write_metadata()

    def write(self, data: dict[str, Any]):
        print("CUSTOM WRITER WRITE CALLED")
        frame = f"{self._frame_id:06d}"

        print(f"[{frame}] write() top-level keys: {list(data.keys())}")

        annotator_keys = {
            "rgb",
            "distance_to_image_plane",
            "semantic_segmentation",
            "instance_segmentation",
            "bounding_box_2d_tight",
        }

        # Case 1: data is grouped under "renderProducts"
        if "renderProducts" in data:
            for rp_name, annotators_data in data["renderProducts"].items():
                rp_prefix = self._safe_name(str(rp_name))
                self._write_annotators_for_frame(
                    annotators_data=annotators_data,
                    frame=frame,
                    render_product_prefix=rp_prefix,
                )

        # Case 2: data itself contains annotators directly
        elif annotator_keys.intersection(data.keys()):
            self._write_annotators_for_frame(
                annotators_data=data,
                frame=frame,
                render_product_prefix="",
            )

        # Case 3: data is grouped by render product name directly
        else:
            wrote_any = False

            for key, value in data.items():
                if not isinstance(value, dict):
                    continue

                if not annotator_keys.intersection(value.keys()):
                    continue

                rp_prefix = self._safe_name(str(key))
                self._write_annotators_for_frame(
                    annotators_data=value,
                    frame=frame,
                    render_product_prefix=rp_prefix,
                )
                wrote_any = True

            if not wrote_any:
                print(f"[{frame}] No known annotator keys found. Nothing written.")

        self._frame_id += 1

    def on_final_frame(self):
        self._frame_id = 0
    def _write_annotators_for_frame(
            self,
            annotators_data: dict,
            frame: str,
            render_product_prefix: str = "",

    ):
        prefix = f"{render_product_prefix}/" if render_product_prefix else ""

        if self.enable_rgb and "rgb" in annotators_data:
            self._write_rgb(annotators_data["rgb"], frame, prefix)

        if self.enable_depth and "distance_to_image_plane" in annotators_data:
            self._write_depth(
                annotators_data["distance_to_image_plane"],
                frame,
                prefix,
            )

        if self.enable_semantic and "semantic_segmentation" in annotators_data:
            self._write_segmentation(
                entry=annotators_data["semantic_segmentation"],
                frame=frame,
                prefix=prefix,
                folder="semantic",
                mask_name="semantic",
                info_name="semantic_labels",
            )

        if self.enable_instance and "instance_segmentation" in annotators_data:
            self._write_segmentation(
                entry=annotators_data["instance_segmentation"],
                frame=frame,
                prefix=prefix,
                folder="instance",
                mask_name="instance",
                info_name="instance_info",
            )

        if self.enable_bbox_2d and "bounding_box_2d_tight" in annotators_data:
            self._write_bbox_2d(
                annotators_data["bounding_box_2d_tight"],
                frame,
                prefix,
            )
        if (self.enable_pointcloud and 
            "rgb" in annotators_data and 
            "distance_to_image_plane" in annotators_data and
              "semantic_segmentation" in annotators_data
              ):
            self._write_labeled_pointcloud(
                frame=frame,
                prefix=prefix,
                rgb_entry=annotators_data["rgb"],
                depth_entry=annotators_data["distance_to_image_plane"],
                semantic_entry=annotators_data["semantic_segmentation"],
                

                
            )    




    def _write_rgb(self, entry: Any, frame:str, prefix:str):
            """The entry is the rgb data coming from the replicator 
            the entry could be directly the image array or a dictionary
            containing data and metadata so to deal with both data types
            we split the data info"""
           
            rgb_arr, _ = self._split_data_info(entry)
            rgb_arr = np.asarray(rgb_arr)

            # Replicator RGB is often RGBA the a the channel that corresponds to transparency, so we should only save the rgb channel
            if rgb_arr.ndim == 3 and rgb_arr.shape[-1] >= 3:
               rgb_arr = rgb_arr[:, :, :3]

            path = f"{prefix}rgb/{frame}.png"
            print(f"[{frame}] Writing {path}")
            self.backend.schedule(F.write_image, path=path, data=rgb_arr)
    def _write_segmentation(
        self,
        entry: Any,
        frame: str,
        prefix: str,
        folder: str,
        mask_name: str,
        info_name: str,
        ):
        mask_arr, info = self._split_data_info(entry)
        mask_arr = np.asarray(mask_arr)

        out_folder = self.output_dir / prefix / folder
        out_folder.mkdir(parents=True, exist_ok=True)


        mask_path = out_folder / f"{frame}.npy"
        print(f"[{frame}] Writing {mask_path}")
        np.save(mask_path, mask_arr)


        info_path = out_folder / f"{frame}_{info_name}.json"
        print(f"[{frame}] Writing {info_path}")

        self._write_json(
            info_path,
        {
            "frame": frame,
            "modality": folder,
            "mask_file": f"{frame}.npy",
            "mask_name": mask_name,
            "mask_shape": list(mask_arr.shape),
            "mask_dtype": str(mask_arr.dtype),
            "info": self._json_safe(info),
        },
    )

        # raw mask_arr holds label/instance ids, not viewable as-is, so also
        # save a colorized png purely for visual inspection
        colorized = self._colorize_mask(mask_arr, info)
        vis_path = f"{prefix}{folder}/{frame}_colorized.png"
        print(f"[{frame}] Writing {vis_path}")
        self.backend.schedule(F.write_image, path=vis_path, data=colorized)


    def _colorize_mask(self, mask_arr: np.ndarray, info: dict | None = None) -> np.ndarray:
        """Build a viewable RGB preview for segmentation masks.

        Replicator may return either raw id masks or already-colorized masks
        depending on annotator settings/version. Raw id masks should be colored
        from the annotator metadata when that metadata contains an id/color map.
        """
        info = info or {}

        if mask_arr.ndim == 3 and mask_arr.shape[-1] >= 3:
            return self._normalize_rgb_image(mask_arr[:, :, :3])

        ids = mask_arr[:, :, 0] if mask_arr.ndim == 3 and mask_arr.shape[-1] == 1 else mask_arr
        colorized = np.zeros((*ids.shape, 3), dtype=np.uint8)
        id_to_color = self._extract_id_to_color(info)

        for id_value in np.unique(ids):
            if id_value == 0:
                continue
            id_key = self._normalize_id_key(id_value)
            color = id_to_color.get(id_key)
            if color is None:
                color = self._fallback_color(id_value)
            colorized[ids == id_value] = color

        return colorized

    def _normalize_rgb_image(self, image: np.ndarray) -> np.ndarray:
        image = np.asarray(image)

        if image.dtype == np.uint8:
            return image

        if np.issubdtype(image.dtype, np.floating):
            max_value = float(np.nanmax(image)) if image.size else 0.0
            if max_value <= 1.0:
                return np.clip(image * 255.0, 0, 255).astype(np.uint8)

        return np.clip(image, 0, 255).astype(np.uint8)
    def _squeeze_single_channel(self, arr: np.ndarray) -> np.ndarray:
        arr = np.asarray(arr)

        if arr.ndim == 3 and arr.shape[-1] == 1:
            return arr[:, :, 0]

        return arr

    def _extract_id_to_color(self, info: dict) -> dict[str, np.ndarray]:
        id_to_color = {}

        for key in ("idToColors", "idToColor", "idToRGBA", "idToRgb", "idToRGB"):
            value = info.get(key)
            if isinstance(value, dict):
                id_to_color.update(self._parse_id_color_dict(value))

        color_to_labels = info.get("colorToLabels")
        if isinstance(color_to_labels, dict):
            id_to_labels = info.get("idToLabels", {})
            label_to_id = self._label_to_id_map(id_to_labels)

            for color_key, label_entry in color_to_labels.items():
                color = self._parse_color_value(color_key)
                if color is None:
                    continue

                label = self._label_from_entry(label_entry)
                id_value = label_to_id.get(label)
                if id_value is not None:
                    id_to_color[id_value] = color

        return id_to_color

    def _parse_id_color_dict(self, value: dict) -> dict[str, np.ndarray]:
        result = {}

        for id_value, color_value in value.items():
            color = self._parse_color_value(color_value)
            if color is not None:
                result[self._normalize_id_key(id_value)] = color

        return result

    def _label_to_id_map(self, id_to_labels: dict) -> dict[Any, str]:
        result = {}

        if not isinstance(id_to_labels, dict):
            return result

        for id_value, label_entry in id_to_labels.items():
            label = self._label_from_entry(label_entry)
            if label is not None:
                result[label] = self._normalize_id_key(id_value)

        return result

    def _label_from_entry(self, label_entry: Any) -> Any:
        if isinstance(label_entry, dict):
            class_label = label_entry.get("class")
            if isinstance(class_label, list) and class_label:
                return class_label[0]
            return class_label

        return label_entry

    def _parse_color_value(self, value: Any) -> np.ndarray | None:
        if isinstance(value, str):
            numbers = re.findall(r"\d+(?:\.\d+)?", value)
            if len(numbers) < 3:
                return None
            value = [float(number) for number in numbers[:3]]

        if isinstance(value, dict):
            keys = ("r", "g", "b")
            if not all(key in value for key in keys):
                return None
            value = [value[key] for key in keys]

        if isinstance(value, np.ndarray):
            value = value.tolist()

        if not isinstance(value, (list, tuple)) or len(value) < 3:
            return None

        color = np.asarray(value[:3], dtype=np.float32)
        max_value = float(np.max(color)) if color.size else 0.0
        if max_value <= 1.0:
            color = color * 255.0

        return np.clip(color, 0, 255).astype(np.uint8)

    def _normalize_id_key(self, id_value: Any) -> str:
        try:
            return str(int(id_value))
        except Exception:
            return str(id_value)

    def _fallback_color(self, id_value: Any) -> np.ndarray:
        colors = {
            "1": np.array([255, 0, 0], dtype=np.uint8),      # red
            "2": np.array([0, 255, 0], dtype=np.uint8),      # green
            "3": np.array([0, 0, 255], dtype=np.uint8),      # blue
            "4": np.array([255, 255, 0], dtype=np.uint8),    # yellow
            "5": np.array([255, 0, 255], dtype=np.uint8),    # magenta
            "6": np.array([0, 255, 255], dtype=np.uint8),    # cyan
            "7": np.array([255, 128, 0], dtype=np.uint8),    # orange
            "8": np.array([128, 0, 255], dtype=np.uint8),    # purple
        }

        key = self._normalize_id_key(id_value)
        return colors.get(key, np.array([255, 255, 255], dtype=np.uint8))

    def _write_depth(self, entry: Any, frame: str, prefix: str):
            depth_arr, _ = self._split_data_info(entry)
            depth_arr = np.asarray(depth_arr, dtype=np.float32)
            depth_arr = self._squeeze_single_channel(depth_arr)

            folder = self.output_dir / prefix / "depth"
            
            folder.mkdir(parents=True, exist_ok=True)

            path = folder / f"{frame}.npy"
            print(f"[{frame}] Writing {path}")
            np.save(path, depth_arr)    
    def _write_bbox_2d(self, entry: Any, frame: str, prefix: str):
        bbox_data, info = self._split_data_info(entry)
        boxes = self._bbox_array_to_list(bbox_data, info)

        out_folder = self.output_dir / prefix / "bbox_2d"
        out_folder.mkdir(parents=True, exist_ok=True)

        path = out_folder / f"{frame}.json"

        print(f"[{frame}] Writing {path}")
        self._write_json(
            path,
            {
                "frame": frame,
                "type": "bounding_box_2d_tight",
                "boxes": boxes,
                "info": self._json_safe(info),
            },
        )    

    def _split_data_info(self, entry: Any) -> tuple[Any, dict]:
        

        if isinstance(entry, dict):
            data = entry.get("data", entry)
            info = entry.get("info", {})
            return data, info

        return entry, {}
 
    def _bbox_array_to_list(self, bbox_data: Any, info: dict) -> list[dict]:
        bbox_arr = np.asarray(bbox_data)
        boxes = []

        if bbox_arr.size == 0:
            return boxes

        for row in bbox_arr:
            box = {}

            # structured arrays
            if hasattr(row, "dtype") and row.dtype.names:
                for field in row.dtype.names:
                    value = row[field]
                    box[field] = self._json_safe(value)

            # normal numeric array.
            else:
                values = np.asarray(row).tolist()
                box["raw"] = self._json_safe(values)

                if len(values) >= 5:
                    box.update(
                        {
                            "semanticId": values[0],
                            "x_min": values[1],
                            "y_min": values[2],
                            "x_max": values[3],
                            "y_max": values[4],
                        }
                    )

            semantic_id = box.get("semanticId", box.get("semantic_id"))
            label = self._label_from_semantic_id(semantic_id, info)
            if label is not None:
                box["label"] = label

            boxes.append(box)

        return boxes

    def _label_from_semantic_id(self, semantic_id: Any, info: dict) -> Any:
        if semantic_id is None:
            return None

        try:
            semantic_id_str = str(int(semantic_id))
        except Exception:
            semantic_id_str = str(semantic_id)

        id_to_labels = info.get("idToLabels", {})

        if semantic_id_str not in id_to_labels:
            return None

        label_entry = id_to_labels[semantic_id_str]

        
        if isinstance(label_entry, dict):
            class_label = label_entry.get("class")
            if isinstance(class_label, list) and class_label:
                return class_label[0]
            return class_label

        return label_entry 
    def _write_labeled_pointcloud(
        self,
        frame: str,
        prefix: str,
        rgb_entry: Any,
        depth_entry: Any,
        semantic_entry: Any,
        instance_entry: Any | None = None,
    ):
        rgb_arr, _ = self._split_data_info(rgb_entry)
        depth_arr, _ = self._split_data_info(depth_entry)
        semantic_arr, _ = self._split_data_info(semantic_entry)

        rgb_arr = np.asarray(rgb_arr)
        depth_arr = np.asarray(depth_arr, dtype=np.float32)
        semantic_arr = np.asarray(semantic_arr)

        rgb_arr = self._normalize_rgb_image(rgb_arr)

        if rgb_arr.ndim == 3 and rgb_arr.shape[-1] >= 3:
            rgb_arr = rgb_arr[:, :, :3]

        depth_arr = self._squeeze_single_channel(depth_arr)
        semantic_arr = self._squeeze_single_channel(semantic_arr)

        instance_arr = None

        if instance_entry is not None:
            instance_arr, _ = self._split_data_info(instance_entry)
            instance_arr = np.asarray(instance_arr)
            instance_arr = self._squeeze_single_channel(instance_arr)

        if depth_arr.ndim != 2:
            print(f"[{frame}] Point cloud skipped: invalid depth shape {depth_arr.shape}")
            return

        h, w = depth_arr.shape

        if rgb_arr.shape[0] != h or rgb_arr.shape[1] != w:
            print(f"[{frame}] Point cloud skipped: RGB and depth size mismatch.")
            return

        if semantic_arr.shape[0] != h or semantic_arr.shape[1] != w:
            print(f"[{frame}] Point cloud skipped: semantic and depth size mismatch.")
            return

        if instance_arr is not None:
            if instance_arr.shape[0] != h or instance_arr.shape[1] != w:
                print(f"[{frame}] Instance labels ignored: instance and depth size mismatch.")
                instance_arr = None

        points, colors, semantic_labels, instance_labels = self._depth_to_labeled_points(
            rgb=rgb_arr,
            depth=depth_arr,
            semantic=semantic_arr,
            instance=instance_arr,
        )

        out_folder = self.output_dir / prefix / "pointcloud"
        out_folder.mkdir(parents=True, exist_ok=True)

        ply_path = out_folder / f"{frame}.ply"
        print(f"[{frame}] Writing {ply_path}")

        self._write_ply_ascii(
            ply_path=ply_path,
            points=points,
            colors=colors,
            semantic_labels=semantic_labels,
            instance_labels=instance_labels,
        )


    def _depth_to_labeled_points(
        self,
        rgb: np.ndarray,
        depth: np.ndarray,
        semantic: np.ndarray,
        instance: np.ndarray | None = None,
    ):
        h, w = depth.shape

        fov_rad = np.deg2rad(self.camera_fov_degrees)

        fx = w / (2.0 * np.tan(fov_rad / 2.0))
        fy = fx

        cx = w / 2.0
        cy = h / 2.0

        u, v = np.meshgrid(np.arange(w), np.arange(h))

        z = depth.astype(np.float32)

        valid = np.isfinite(z) & (z > 0.0)

        x = (u.astype(np.float32) - cx) * z / fx
        y = (v.astype(np.float32) - cy) * z / fy

        points = np.stack([x, y, z], axis=-1)

        points = points[valid]
        colors = rgb[valid]
        semantic_labels = semantic[valid]

        if instance is not None:
            instance_labels = instance[valid]
        else:
            instance_labels = None

        colors = self._normalize_rgb_image(colors)

        return points, colors, semantic_labels, instance_labels


    def _write_ply_ascii(
        self,
        ply_path: Path,
        points: np.ndarray,
        colors: np.ndarray,
        semantic_labels: np.ndarray,
        instance_labels: np.ndarray | None = None,
    ):
        ply_path.parent.mkdir(parents=True, exist_ok=True)

        has_instance = instance_labels is not None

        with ply_path.open("w", encoding="utf-8") as f:
            f.write("ply\n")
            f.write("format ascii 1.0\n")
            f.write(f"element vertex {len(points)}\n")
            f.write("property float x\n")
            f.write("property float y\n")
            f.write("property float z\n")
            f.write("property uchar red\n")
            f.write("property uchar green\n")
            f.write("property uchar blue\n")
            f.write("property uint semantic_label\n")

            if has_instance:
                f.write("property uint instance_label\n")

            f.write("end_header\n")

            for i in range(len(points)):
                x, y, z = points[i]
                r, g, b = colors[i][:3]
                sem = int(semantic_labels[i])

                if has_instance:
                    inst = int(instance_labels[i])
                    f.write(
                        f"{float(x)} {float(y)} {float(z)} "
                        f"{int(r)} {int(g)} {int(b)} {sem} {inst}\n"
                    )
                else:
                    f.write(
                        f"{float(x)} {float(y)} {float(z)} "
                        f"{int(r)} {int(g)} {int(b)} {sem}\n"
                    )

    def _write_metadata(self):
        metadata_path = self.output_dir / "metadata.json"

        metadata = {
            "writer": "CustomWriter",
            "version": self.version,
            "uses_basic_writer": False,
            "data_structure": self.data_structure,
            "depth_annotator": "distance_to_image_plane",
            "depth_units": "meters",
            "enabled_modalities": {
                "rgb": self.enable_rgb,
                "depth": self.enable_depth,
                "semantic": self.enable_semantic,
                "instance": self.enable_instance,
                "bbox_2d": self.enable_bbox_2d,
                "pointcloud": self.enable_pointcloud,
            },
            "files": {
                "rgb": "rgb/<frame>.png",
                "depth": "depth/<frame>.npy",
                "semantic": "semantic/<frame>.npy + semantic/<frame>_semantic_labels.json + semantic/<frame>_colorized.png",
                "instance": "instance/<frame>.npy + instance/<frame>_instance_info.json + instance/<frame>_colorized.png",
                "bbox_2d": "bbox_2d/<frame>.json",
                "pointcloud": "pointcloud/<frame>.ply",

            },
        }

        self._write_json(metadata_path, metadata)

    def _write_json(self, path: Path, data: dict):
        path.parent.mkdir(parents=True, exist_ok=True)

        with path.open("w", encoding="utf-8") as f:
            json.dump(self._json_safe(data), f, indent=2)

    def _json_safe(self, value: Any) -> Any:

        if isinstance(value, dict):
            return {str(k): self._json_safe(v) for k, v in value.items()}

        if isinstance(value, (list, tuple)):
            return [self._json_safe(v) for v in value]

        if isinstance(value, np.ndarray):
            return value.tolist()

        if isinstance(value, np.generic):
            return value.item()

        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")

        return value

    def _safe_name(self, name: str) -> str:
        

        name = name.strip().replace("\\", "/")
        name = name.split("/")[-1] if "/" in name else name
        name = re.sub(r"[^a-zA-Z0-9_.-]+", "_", name)
        return name or "render_product"



        
try:
    rep.writers.register_writer(CustomWriter)
except Exception:
    rep.WriterRegistry.register(CustomWriter)
