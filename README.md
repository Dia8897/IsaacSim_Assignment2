# Synthetic Data Generation Extension - Report

Extension:  `exts/synthetic_data_extension`  Modules:  `extension.py`  (UI),  `asset_manager.py`  (JSON loading/validation),  `replicator_engine.py`  (scene + randomizers + run loop),  `custom_writer.py`  (the graded  `Writer`  subclass).

## 1. What a Replicator Writer does - the annotator  `write()`  flow
A writer doesn't render anything itself; The replicator calls it once per frame with whatever it asked for. The flow in this project is:
1. **Construction:** (`CustomWriter.__init__`) the writer declares which annotators it needs by calling `AnnotatorRegistry.get_annotator(name, init_params=...)` for each enabled modality (`rgb`, `distance_to_image_plane`, `semantic_segmentation`, `instance_segmentation`, `bounding_box_2d_tight`) and stores them in `self.annotators`. Annotators that weren't toggled on in the UI are never requested.
2. **Attach:** (`replicator_engine.run`); `writer.attach([render_product])` binds those annotators to a specific render product/camera. The replicator now knows to compute those buffers whenever a render product is rendered.
3. **Step:** Each `rep.orchestrator.step_async()`  call renders one frame and evaluates every attached annotator against it.
4. **Write:** `write(data)`: Replicator invokes this with a dict for that frame, keyed by annotator name. Each modality's value is either the raw array or a `{"data": ..., "info": ...}` pair, with segmentation and bbox annotators always carrying the second element, since a mask array of integers is meaningless without the id.
5. **Dispatch:** `_write_annotators_for_frame`  looks at which keys are present and calls the matching  `_write_rgb`  /  `_write_depth`  /  `_write_segmentation`  /  `_write_bbox_2d`  helper, which is where the actual file serialization happens.
## 2. Why a  `CustomWriter`  over  `BasicWriter`
`BasicWriter` would have taken a config dict and quietly done all of the following for you. Writing it ourselves forced us to actually understand:
1. **The data isn't just an array:** Every annotator we used except RGB and depth returns  `{"data": <buffer>, "info": <mapping dict>}`. The first time we ignored  `info`  we had segmentation masks that were technically correct but useless (just integers with no way to know which integer meant  `"Forklift"`).  `_split_data_info`  and  `_extract_id_to_color`  /  `_label_from_semantic_id`  exist specifically because we had to go read what  `idToLabels`,  `idToColors`, and  `colorToLabels`  actually contain and reverse them into usable label maps.
2. **Depth is not one thing:** we used `distance_to_image_plane` because it provides the depth value for each rendered pixel. This depth is needed to save depth maps and to reconstruct the labeled 3D point cloud. Each pixel’s depth is back-projected with the camera intrinsics to obtain XYZ coordinates, while RGB and semantic labels are taken from the same pixel.
3. **Raw ground truth and human-viewable ground truth are different deliverables.** A  `.npy`  id mask is what a dataloader wants; a human reviewing the dataset wants a colorized PNG.  `BasicWriter`  would have hidden that this is a deliberate choice hence why we write both (`_write_segmentation`  saves the raw mask, a JSON label map,  _and_  a colorized PNG for inspection).
4. **Bounding boxes come back as a structured NumPy array, not a list of dicts;** `bounding_box_2d_tight`  gives you a record array with named fields (`semanticId`,  `x_min`,  `y_min`, ...).  `_bbox_array_to_list`  exists because we had to inspect  `dtype.names`  to even know the field names existed.
5. **The writer owns dataset layout, not just pixels.** Deciding on  `modality/<frame>.ext`  folders, zero-padded frame ids, and a top-level  `metadata.json`  describing what was written and in what units was our decision to make. `BasicWriter`  would have made it for us and we'd never have had to think about what a consumer of the dataset actually needs (`_write_metadata`,  `metadata.json`'s  `depth_units: "meters"`  field).
## 3. Randomizers applied, ranges chosen, and why they matter
Implemented in  `replicator_engine.py`, each gated independently by its UI toggle (`toggles["transform"|"light"|"material"]`) and registered via  `rep.randomizer.register(...)`  so it only runs when enabled:

-   **Transform**  (`_randomize_transform`): per instance, per frame:
    
    -   Position:  `uniform((-250, -250, 0.1), (250, 250, 0.1))`
    -   Rotation:  `uniform((0, 0, 0), (0, 0, 360))`  (full yaw spin)
    -   Scale:  `uniform((0.85, 0.85, 0.85), (1.25, 1.25, 1.25))`
    
    Position/rotation variation is what teaches a detector/segmenter that an object's class doesn't depend on where it sits or which way it faces; without it every frame is a near-duplicate of the manual layout in  `instantiate_assets`. The ±15%/+25% scale jitter adds mild size variance without asset instances becoming unrecognizably tiny or clipping through the ground plane.
    
-   **Light**  (`_randomize_light`) : rotation  `uniform((300,0,0),(360,0,360))`  and intensity  `uniform(1000, 5000)`  on the directional light. Varying incidence angle and brightness changes shadow direction/length and exposure from frame to frame, which is what prevents a model from learning "this class always has a shadow on the left" as a shortcut feature instead of learning actual shape/texture cues.
    
-   **Material**  (`_randomize_material`): a pool of 5  `OmniPBR`  materials with random RGB diffuse color (`create_material_pool`) is built once per run and assigned to instances via  `rep.randomizer.materials(material_pool)`. This decorrelates class label from surface color/albedo, so the network can't cheat by memorizing "yellow object = Forklift."
## 4. Limitations and how this would scale to a real dataset
-   **Single fixed camera, no viewpoint diversity.** A real dataset needs multiple viewpoints/elevations per scene (or a randomized camera rig) so the model isn't overfit to one vantage point.
-   **No occlusion/collision awareness.**  Transforms are sampled independently per instance with no interpenetration or overlap check, so instances can clip through each other or the ground.  `rep.randomizer`  supports scatter/collision-check utilities that weren't wired in here.
-   **Small, fixed asset pool.**  Five classes, one mesh per class, manually seeded base positions (`instantiate_assets`'s  `manual_positions`). No distractor objects, no background/floor texture randomization beyond flat material color, no HDRI/environment randomization.
 -   **Synchronous, single-process writing.**  `CustomWriter`  writes to local disk through  `BackendDispatch`  and blocks on  `wait_until_done()`  at the end of the run. For a real dataset (tens of thousands of frames) this I/O path would bottleneck the render loop; scaling it means batching/async writes, and pointing  `BackendDispatch`  at a distributed store instead of a local folder.
 -  **Debug  `print()`s instead of logging**, and no retry/error-isolation per frame; one bad frame currently has no defined recovery path.
 -    **Scaling strategy overall:**  run headless across multiple GPU workers each driving its own stage/asset subset, widen the asset library and add environment/background randomization, add camera-pose randomization or a multi-camera rig, replace the local  `BackendDispatch`  with a distributed storage backend and make writes asynchronous, and add an automated per-class/per-modality statistics check before a generated batch is accepted into the dataset.
## 5. Point clouds

Enabled via  `pointcloud=True`  on  `CustomWriter`, which generates one labeled 3D point cloud per rendered frame using annotators it already has:  `rgb`  for color,  `distance_to_image_plane`  for depth,  `semantic_segmentation`  for labels, and optionally  `instance_segmentation`  for per-point instance ids.

**Method: pinhole back-projection**, not Replicator's point-cloud annotator. Each valid pixel  `(u, v)`  becomes a 3D point:

```
X = (u - cx) * Z / fx
Y = (v - cy) * Z / fy
Z = depth

```

where  `Z`  comes from  `distance_to_image_plane`,  `fx, fy`  are the focal lengths and  `cx, cy`  the image center. Color and labels are read from the same pixel:  `RGB = rgb[v, u]`,  `semantic_label = semantic_mask[v, u]`, and  `instance_label = instance_mask[v, u]`  when instance output is enabled.

**Coordinate frame:**  camera space; only the intrinsic (pinhole) projection is undone; the camera's world position/orientation is never applied.

**Output:**  one ASCII  `.ply`  per frame at  `pointcloud/<frame>.ply`  (e.g.  `pointcloud/000000.ply`), each point carrying  `x y z red green blue semantic_label`, plus  `instance_label`  when instance output is enabled.

**Caveat:**  `fx`/`fy`  are derived from a constructor default (`camera_fov_degrees=60.0`) rather than the FOV actually set on the camera in  `replicator_engine.py`, so geometry is only metrically correct if that default matches the real camera.