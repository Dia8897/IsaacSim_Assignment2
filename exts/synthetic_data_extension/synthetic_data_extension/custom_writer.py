import json
import re
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
        output_dir: str | None = None,
        backend: BaseBackend | None = None,
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
        self.enable_rgb = rgb 
        self.enable_depth = depth
        self.enable_semantic = semantic 
        self.enable_instance = instance 
        self.enable_bbox_2d = bbox_2d            

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
                        "colorize": False,
                    },
                )
            )    
        self._frame_id = 0

        self._write_metadata()

    def write(self, data:dict[str, Any]):
        frame = f"{self._frame_id:06d}"
        if "renderProducts" in data:
            for rp_name, annotators_data in data["renderProducts"].items():
                rp_prefix = self._safe_name(str(rp_name))
                self._write_annotators_for_frame(
                    annotators_data=annotators_data,
                    frame=frame,
                    render_product_prefix=rp_prefix,
                )

            self._frame_id += 1
            return

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
                 
    def _write_depth(self, entry: Any, frame: str, prefix: str):
            depth_arr, _ = self._split_data_info(entry)
            depth_arr = np.asarray(depth_arr, dtype=np.float32)

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
            },
            "files": {
                "rgb": "rgb/<frame>.png",
                "depth": "depth/<frame>.npy",
                "semantic": "semantic/<frame>.npy + semantic/<frame>_semantic_labels.json",
                "instance": "instance/<frame>.npy + instance/<frame>_instance_info.json",
                "bbox_2d": "bbox_2d/<frame>.json",
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