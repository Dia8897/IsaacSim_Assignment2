import random
#from isaacsim.core.utils.semantics import add_labels
import omni.replicator.core as rep

def create_camera_and_render_product(resolution):
    camera = rep.create.camera(position=(0, -10, 5), look_at=(0, 0, 0))
    render_product = rep.create.render_product(camera, resolution)

    return camera, render_product

def build_ground_and_lighting():
    # Create a ground plane
    ground = rep.create.plane(scale=(10, 10, 1), position=(0, 0, 0))
    
    # Create a directional light
    light = rep.create.light(rotation=(315,0,0), intensity=3000, light_type="distant")

    return ground, light

def instantiate_assets(class_labels, instance_counts):
    result = {}
    for asset in class_labels:
        class_label = asset["label"]
        path = asset["path"]
        count = instance_counts[class_label]
        result[class_label] = []

        for i in range(count):
            handle = rep.create.from_usd(path)
            with handle:
                rep.modify.semantics([("class",class_label)])
            result[class_label].append(handle)    

    return result

def _randomize_transform(list_of_prims):
    #need to verify if it should take a list of prims or needs the group wrapper
    for prim in list_of_prims:
        with prim:
            rep.modify.pose(  
               position = rep.distribution.uniform((-8, -8, 0.1), (8, 8, 0.1)),
               rotation = rep.distribution.uniform((0, 0, 0), (360, 360, 360)),
               scale = rep.distribution.uniform((0.75, 0.75, 0.75), (1.25, 1.25, 1.25)),
    )

def _randomize_light(light):
    with light:
        rep.modify.pose(
            rotation=rep.distribution.uniform((300, 0, 0), (360, 0, 360)),
        )

        rep.modify.attribute(
            "intensity",
            rep.distribution.uniform(1000, 5000),
        )

    
def create_material_pool(count):
    #dropped .functional because unsure if compatible with older isaacsim versions (rep.functional.create.material(...))
    #if rep.modify.material fails, try rep.randomizer.materials
    materials = []

    for i in range(count):
        color = (random.uniform(0, 1), random.uniform(0, 1), random.uniform(0, 1))
        material = rep.create.material_omnipbr(
            diffuse=color,
            
        )
        materials.append(material)

    return materials        

def _randomize_material(list_of_prims, material_pool):
    for prim in list_of_prims:
        with prim:
            rep.randomizer.materials(material_pool)


def run(num_frames:int, render_product, writer, toggles:dict):
    # num_frames: how many frames to generate
    # render_product: camera output
    # writer: saves data
    
    if writer is not None:
        writer.attach([render_product])
    # decide what should happen for each frame
    with rep.trigger.on_frame(num_frames=num_frames):
        if toggles.get("transform",False):
            rep.randomizer.randomize_transform()
        if toggles.get("light",False):
            rep.randomizer.randomize_light()
        if toggles.get("material",False):
            rep.randomizer.randomize_material()
    # execute everything just defined
    rep.orchestrator.run()
    if writer is not None:
        writer.detach()

def generate(config):
    with rep.new_layer():
        camera, render_product = create_camera_and_render_product(config["resolution"])
        ground, light = build_ground_and_lighting()
        material_pool = create_material_pool(count=5)
        prim_dict = instantiate_assets(config["class_labels"], config["instance_counts"])

        all_prims = []
        for prim_list in prim_dict.values():
            for prim in prim_list:
                all_prims.append(prim)

        def randomize_transform():
            _randomize_transform(all_prims)

        def randomize_light():
            _randomize_light(light)

        def randomize_material():
            _randomize_material(all_prims, material_pool)

        rep.randomizer.register(randomize_transform)
        rep.randomizer.register(randomize_light)
        rep.randomizer.register(randomize_material)

        run(config["num_frames"], render_product, config["writer"], config["toggles"])
        