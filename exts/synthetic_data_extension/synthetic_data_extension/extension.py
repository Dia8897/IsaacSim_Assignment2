import omni.ext
import omni.ui as ui

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
                ui.Label("Number of frames")
                ui.IntField(model=self.num_frames_model)
                ui.Label("Randomization")
                with ui.HStack(spacing=5):
                    ui.CheckBox(model=self.randomization_models["light"])
                    ui.Label("Light")               
                with ui.HStack(spacing=5):
                    ui.CheckBox(model=self.randomization_models["material"])
                    ui.Label("Material")               
                with ui.HStack(spacing=5):
                    ui.CheckBox(model=self.randomization_models["transform"])
                    ui.Label("Transform")
                ui.Label("Output")
                with ui.HStack(spacing=5):
                    ui.CheckBox(model=self.output_models["rgb"])
                    ui.Label("RGB")
                with ui.HStack(spacing=5):
                    ui.CheckBox(model=self.output_models["depth"])
                    ui.Label("Depth")
                with ui.HStack(spacing=5):
                    ui.CheckBox(model=self.output_models["semantic"])
                    ui.Label("Semantic")
                with ui.HStack(spacing=5):
                    ui.CheckBox(model=self.output_models["instance"])
                    ui.Label("Instance")
                with ui.HStack(spacing=5):
                    ui.CheckBox(model=self.output_models["bbox_2d"])
                    ui.Label("bbox_2d")
                ui.Label("Output Directory")
                with ui.HStack(spacing=5):
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
    def _browse_output_dir(self):
        # to implement
        print("browse output dir clicked")
        
    def _generate_and_render(self):
        # to implement
        print("generate and render clicked")
            
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
    def on_shutdown(self):
        self._window=None
     


# Asset config path (with a file browser)
# Per-class instance count
# A Generate & Render button