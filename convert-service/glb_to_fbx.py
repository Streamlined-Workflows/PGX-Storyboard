"""Run inside Blender: turn one GLB file into one binary FBX file in the studio's conventions.

    blender --background --factory-startup --python-exit-code 1 --python glb_to_fbx.py -- in.glb out.fbx

The FBX is written +Y up, +Z forward, right-handed, one unit = one centimetre, with the sizes worked into the
points so nothing downstream has to scale. A GLB is in metres, so a one-metre cube comes out 100 units across.
Only meshes, empties and armatures are written: no cameras, lights or animation, and no picture files.
"""
import sys

import bpy

src, dst = sys.argv[sys.argv.index("--") + 1:][:2]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)
if not any(o.type == "MESH" for o in bpy.data.objects):
    raise SystemExit("The GLB file has no mesh in it.")
scene = bpy.context.scene
scene.unit_settings.system = "METRIC"
scene.unit_settings.scale_length = 0.01                     # one Blender unit is now one centimetre
for o in bpy.data.objects:                                  # so everything is made 100 times larger, and that is baked in
    if o.parent is None:
        o.scale = [s * 100 for s in o.scale]
        o.location = [v * 100 for v in o.location]
bpy.ops.object.select_all(action="SELECT")
bpy.context.view_layer.objects.active = next(o for o in bpy.data.objects if o.type == "MESH")
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
bpy.ops.export_scene.fbx(filepath=dst, use_selection=False, object_types={"MESH", "EMPTY", "ARMATURE"}, axis_forward="-Z", axis_up="Y",
                         global_scale=1.0, apply_unit_scale=True, apply_scale_options="FBX_SCALE_NONE", bake_space_transform=True,
                         bake_anim=False, add_leaf_bones=False, path_mode="STRIP", embed_textures=False, mesh_smooth_type="FACE")
