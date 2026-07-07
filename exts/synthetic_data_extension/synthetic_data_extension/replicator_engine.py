import omni.replicator.core as rep

def create_camera_and_render_product(resolution):
    camera = rep.create.camera(position=(0, 0, 1.5), look_at=(0, 0, 0))
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
            add_labels(handle, labels=[class_label])
            result[class_label].append(handle)

    return result   