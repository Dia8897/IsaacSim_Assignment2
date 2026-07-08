import random
#from isaacsim.core.utils.semantics import add_labels
import omni.replicator.core as rep

def create_camera_and_render_product(resolution):
    camera = rep.create.camera(position=(0, -18, 10), look_at=(0, 3, 0))
    render_product = rep.create.render_product(camera, resolution)

    return camera, render_product

def build_ground_and_lighting():
    # Create a ground plane
    ground = rep.create.plane(scale=(3000, 3000, 1), position=(0, 0, 0))
    
    # Create a directional light
    light = rep.create.light(rotation=(315,0,0), intensity=8000, light_type="distant")
    light2 = rep.create.light(
    position=(0, -5, 10),
    intensity=5000,
    light_type="sphere"
)

    return ground, light



def instantiate_assets(class_labels, instance_counts):
    result = {}

    manual_positions = {
        "Dolly": (-6, 0, 0),
        "Forklift": (0, 0, 0),
        "Rack": (6, 0, 0),
        "Stillage": (-6, 6, 0),
        "Str": (0, 6, 0),
    }

    print("instantiate_assets called")
    print("class_labels:", class_labels)
    print("instance_counts:", instance_counts)

    for asset in class_labels:
        class_label = asset["label"]
        path = asset["path"]
        count = instance_counts.get(class_label, 0)

        print(f"Creating {count} instance(s) of {class_label} from {path}")

        result[class_label] = []

        base_x, base_y, base_z = manual_positions.get(class_label, (0, 0, 0))

        for i in range(count):
            position = (base_x + i * 3, base_y, base_z)

            print(f"Creating {class_label} at {position}")

            handle = rep.create.from_usd(path)

            with handle:
                rep.modify.pose(
                    position=position,
                    rotation=(0, 0, 0),
                    scale=(1, 1, 1),
                )
                rep.modify.semantics([("class", class_label)])

            result[class_label].append(handle)

    return result

def _randomize_transform(list_of_prims):
    for prim in list_of_prims:
        with prim:
            rep.modify.pose(
                position=rep.distribution.uniform(
                    (-250, -250, 0.1),
                    (250, 250, 0.1)),                                                    
                rotation=rep.distribution.uniform(
                    (0, 0, 0),
                    (0, 0, 360)
                ),
                scale=rep.distribution.uniform(
                    (0.85, 0.85, 0.85),
                    (1.25, 1.25, 1.25)
                ),
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

    materials = []

    for i in range(count):
        color = (random.uniform(0, 1), random.uniform(0, 1), random.uniform(0, 1))
        material = rep.create.material_omnipbr(diffuse=color) 
        materials.append(material)

    return materials        

def _randomize_material(list_of_prims, material_pool):
    for prim in list_of_prims:
        with prim:
            rep.randomizer.materials(material_pool)



async def run(num_frames: int, render_product, writer, toggles: dict):
    if writer is not None:
        print("Attaching writer to render product...")
        writer.attach([render_product])

    print("Starting manual Replicator stepping...")

    for frame in range(num_frames):
        print(f"Rendering frame {frame + 1}/{num_frames}")

        if toggles.get("transform", False):
            rep.randomizer.randomize_transform()

        if toggles.get("light", False):
            rep.randomizer.randomize_light()

        if toggles.get("material", False):
            rep.randomizer.randomize_material()

        await rep.orchestrator.step_async()

    print("Replicator finished.")

    if writer is not None:
        try:
            writer.backend.wait_until_done()
        except Exception as e:
            print("backend wait_until_done failed:", e)
        writer.detach()
        print("Writer detached.")

async def generate(config):
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

        await run(config["num_frames"], render_product, config["writer"], config["toggles"])
        