import omni.ext
import omni.ui as ui
from .asset_manager import AssetManager
from pathlib import Path
from omni.kit.window.filepicker import FilePickerDialog
from .replicator_engine import generate
from .custom_writer import CustomWriter

# define the extension
class SyntheticDataExtension(omni.ext.IExt):
    # called once, when the user enables the extension
    def on_startup(self, ext_id):
        self._create_variables()
        self._window=ui.Window(
            "Synthetic Data Generation",
            width=400,
            height=500
        ) 
        self._build_ui()

    def _build_ui(self):
        with self._window.frame:
            with ui.VStack(spacing=10):
                # stacks its children vertically
                ui.Label("Synthetic Data Generation")
                with ui.HStack(spacing=5):
                    ui.Label("Asset config path")
                    self.asset_config_field=ui.StringField(model=self.asset_config_model)
                    ui.Button(
                        "Browse",
                        clicked_fn=self._browse_asset_config
                    )
                ui.Label("instance counts")
                self.instance_count_stack=ui.VStack(spacing=5)
                ui.Label("Number of frames")
                ui.IntField(model=self.num_frames_model)
                ui.Label("Randomization")
                with ui.HStack(spacing=1):
                    ui.CheckBox(model=self.randomization_models["light"])
                    ui.Label("Light")               
                with ui.HStack(spacing=1):
                    ui.CheckBox(model=self.randomization_models["material"])
                    ui.Label("Material")               
                with ui.HStack(spacing=1):
                    ui.CheckBox(model=self.randomization_models["transform"])
                    ui.Label("Transform")
                ui.Label("Output")
                with ui.HStack(spacing=1):
                    ui.CheckBox(model=self.output_models["rgb"])
                    ui.Label("RGB")
                with ui.HStack(spacing=1):
                    ui.CheckBox(model=self.output_models["depth"])
                    ui.Label("Depth")
                with ui.HStack(spacing=1):
                    ui.CheckBox(model=self.output_models["semantic"])
                    ui.Label("Semantic")
                with ui.HStack(spacing=1):
                    ui.CheckBox(model=self.output_models["instance"])
                    ui.Label("Instance")
                with ui.HStack(spacing=1):
                    ui.CheckBox(model=self.output_models["bbox_2d"])
                    ui.Label("BBox_2D")
                ui.Label("Output Directory")
                with ui.HStack(spacing=1):
                    self.output_dir_field=ui.StringField(model=self.output_dir_model)
                    ui.Button(
                        "Browse",
                        clicked_fn=self._browse_output_dir
                    )
                ui.Button(
                    "Generate and Render",
                    clicked_fn=self._generate_and_render
                )
    def _browse_asset_config(self):
        # to implement
        print("Browse asset config clicked")
        print("Current asset config: ", self.asset_config_model.get_value_as_string())
        def on_apply(filename,dirname):
            selected_path=str(Path(dirname)/filename)
            self.asset_config_model.set_value(selected_path)
            self._asset_config_picker.hide()
            try:
                project_root = Path(__file__).resolve().parents[3]
                assets = AssetManager().load_assets(selected_path, project_root)
                self._rebuild_instance_count_ui(assets)
            except Exception as error:
                print("Error while loading asset config:", error)
        def on_cancel(filename,dirname):
            self._asset_config_picker.hide()
        self._asset_config_picker=FilePickerDialog(
            "Select Asset config json",
            click_apply_handler=on_apply,
            click_cancel_handler=on_cancel
        )
        self._asset_config_picker.show()
        
        # steps:      
        #load assets and build dynamic instance count with UI 
    
    def _browse_output_dir(self):
        # to implement
        print("browse output dir clicked")
        print("Current output directory: ", self.output_dir_model.get_value_as_string())
        def on_apply(filename,dirname):
            selected_path=str(Path(dirname))
            self.output_dir_model.set_value(selected_path)
            self._output_dir_picker.hide()
        def on_cancel(filename,dirname):
            self._output_dir_picker.hide()
        self._output_dir_picker=FilePickerDialog(
            "Output directory picker",
            click_apply_handler=on_apply,
            click_cancel_handler=on_cancel
        )
        self._output_dir_picker.show()
        # steps
        # open file picker
        # let user choose output dataset dir
        # update dir model
        
    def _generate_and_render(self):
        print("generate and render clicked")
        settings={
            "asset_config_path":self.asset_config_model.get_value_as_string(),
            "output_dir":self.output_dir_model.get_value_as_string(),
            "num_frames":self.num_frames_model.get_value_as_int(),
            "randomization":{
                "light":self.randomization_models["light"].get_value_as_bool(),
                "material":self.randomization_models["material"].get_value_as_bool(),
                "transform":self.randomization_models["transform"].get_value_as_bool(),
            },
            "outputs":{
                "rgb":self.output_models["rgb"].get_value_as_bool(),
                "depth":self.output_models["depth"].get_value_as_bool(),
                "semantic":self.output_models["semantic"].get_value_as_bool(),
                "instance":self.output_models["instance"].get_value_as_bool(),
                "bbox_2d":self.output_models["bbox_2d"].get_value_as_bool(),
            }
        }
        if not settings["asset_config_path"]:
            print("Error: Asset config path is empty")
            return
        if not settings["output_dir"].strip():
            print("Error: output directory is empty")
            return
        if settings["num_frames"]<=0:
            print("Error: number of frames must be greater than 0")
            return
        if not any(settings["outputs"].values()):
            print("Error: At least one output modality must be selected")
            return
        try:
            project_root=Path(__file__).resolve().parents[3]
            assets=AssetManager().load_assets(
                settings["asset_config_path"],
                project_root
            )
            
        except Exception as error:
            print("Error while loading assets ", error)
            return
        print("Loaded assets:")
        print(assets)  
        
        settings["instance_counts"] = {}
        for asset in assets:
            label = asset["label"]
            model = self.instance_count_models.get(label)
            settings["instance_counts"][label] = (
                model.get_value_as_int() if model is not None else 1
            )
        print(settings)
        writer=CustomWriter(
            rgb=settings["outputs"]["rgb"],
            depth=settings["outputs"]["depth"],
            semantic=settings["outputs"]["semantic"],
            instance=settings["outputs"]["instance"],
            bbox_2d=settings["outputs"]["bbox_2d"],
            output_dir=settings["output_dir"],
        )
        config={
            "resolution":(1024,1024),
            "class_labels":assets,
            "instance_counts":settings["instance_counts"],
            "num_frames":settings["num_frames"],
            "writer":writer,
            "toggles":settings["randomization"]
        }
        try:
            generate(config)
        except Exception as error:
            print("Error while running replicator: ",error)
            return
 
    def _rebuild_instance_count_ui(self, assets):
        self.instance_count_models={}
        with self.instance_count_stack:
            for asset in assets:
                label=asset["label"]
                self.instance_count_models[label]= ui.SimpleIntModel(1)   
                with ui.HStack(spacing=5):
                    ui.Label(label)
                    ui.IntField(model=self.instance_count_models[label]) 
    def _create_variables(self):
        self.asset_config_path=""
        self.output_dir=""
        self.num_frames=10
        self.instance_counts={

        }
        self.randomization={
            "light":True,
            "material":True,
            "transform":True,
        }
        self.outputs={
            "rgb":True,
            "depth":True,
            "semantic":True,
            "instance":True,
            "bbox_2d":True
        }
        self.num_frames_model=ui.SimpleIntModel(self.num_frames)
        self.randomization_models={
            "light":ui.SimpleBoolModel(self.randomization["light"]),
            "material":ui.SimpleBoolModel(self.randomization["material"]),
            "transform":ui.SimpleBoolModel(self.randomization["transform"]),
        }
        self.output_models={
            "rgb":ui.SimpleBoolModel(self.outputs["rgb"]),
            "depth":ui.SimpleBoolModel(self.outputs["depth"]),
            "semantic":ui.SimpleBoolModel(self.outputs["semantic"]),
            "instance":ui.SimpleBoolModel(self.outputs["instance"]),
            "bbox_2d":ui.SimpleBoolModel(self.outputs["bbox_2d"]),
        }
        self.output_dir_model=ui.SimpleStringModel(self.output_dir)
        self.asset_config_model=ui.SimpleStringModel(self.asset_config_path)
        self.instance_count_models={}
    def on_shutdown(self):
        self._window=None
