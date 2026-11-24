"""Renders `previews/<name>.png` for every item in `pack.json`: the garment
alone, from the front, with its colour texture, on a transparent background.

    blender --background --factory-startup --python tools/render_previews.py [-- <size>]

Run it after `build_pack.py`. Needs Blender 4.2 or later.
"""

import json
import math
import pathlib
import sys

import bpy
from mathutils import Vector

ROOT = pathlib.Path(__file__).resolve().parent.parent
SIZE = int(sys.argv[sys.argv.index("--") + 1]) if "--" in sys.argv else 512
# The share of the picture left empty round the garment.
MARGIN = 0.08


def show_colour(material):
    """Workbench draws a material's active image: make it the base colour's."""
    if not material or not material.node_tree:
        return
    for node in material.node_tree.nodes:
        if node.type != "BSDF_PRINCIPLED":
            continue
        for link in node.inputs["Base Color"].links:
            if link.from_node.type == "TEX_IMAGE":
                material.node_tree.nodes.active = link.from_node


def render(model, picture):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(model))
    scene = bpy.context.scene
    low, high = Vector((math.inf,) * 3), Vector((-math.inf,) * 3)
    for thing in scene.objects:
        # The importer also adds a small mesh of its own (the bones' shape).
        if thing.type != "MESH" or not thing.material_slots:
            thing.hide_render = True
            continue
        for slot in thing.material_slots:
            show_colour(slot.material)
        for corner in thing.bound_box:
            point = thing.matrix_world @ Vector(corner)
            low = Vector(map(min, low, point))
            high = Vector(map(max, high, point))
    middle = (low + high) / 2
    # glTF's +Z (the garment's front) is Blender's -Y.
    camera = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
    scene.collection.objects.link(camera)
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = max(high.x - low.x, high.z - low.z) / (1 - 2 * MARGIN)
    camera.location = (middle.x, low.y - 5, middle.z)
    camera.rotation_euler = (math.radians(90), 0, 0)
    camera.data.clip_end = 100
    scene.camera = camera
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "TEXTURE"
    scene.display.shading.show_specular_highlight = False
    scene.display.render_aa = "16"
    scene.view_settings.view_transform = "Standard"
    scene.render.film_transparent = True
    scene.render.resolution_x = scene.render.resolution_y = SIZE
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.filepath = str(picture)
    bpy.ops.render.render(write_still=True)


def main():
    pack = json.loads((ROOT / "pack.json").read_text())
    (ROOT / "previews").mkdir(exist_ok=True)
    for item in pack["items"]:
        model = next(f["path"] for f in item["files"] if f["path"].endswith(".glb"))
        render(ROOT / model, ROOT / item["preview"])
        print("rendered", item["preview"])


main()
