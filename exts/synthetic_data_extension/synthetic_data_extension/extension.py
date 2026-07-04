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
                    self.asset_config_field=ui.StringField() #Create a textbox and keep a reference to it because we'll need to update it later
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

    def on_shutdown(self):
        self._window=None
     


# Asset config path (with a file browser)
# Per-class instance count
# A Generate & Render button