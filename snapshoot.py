import bpy
import os
import math
from mathutils import Vector

def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    for data_iter in (bpy.data.meshes, bpy.data.materials, bpy.data.armatures, bpy.data.cameras, bpy.data.lights):
        for d in list(data_iter):
            try:
                data_iter.remove(d)
            except:
                pass
    for col in list(bpy.data.collections):
        try:
            bpy.data.collections.remove(col)
        except:
            pass

def setup_render():
    scene = bpy.context.scene
    scene.render.resolution_x = 512
    scene.render.resolution_y = 512
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'
    scene.render.film_transparent = True
    scene.render.engine = 'BLENDER_EEVEE_NEXT'

def create_camera():
    bpy.ops.object.camera_add()
    cam = bpy.context.active_object
    cam.data.lens = 80
    cam.data.clip_start = 0.1
    cam.data.clip_end = 2000
    bpy.context.scene.camera = cam
    return cam

def create_sun():
    bpy.ops.object.light_add(type='SUN')
    sun = bpy.context.active_object
    sun.data.energy = 5.0
    sun.data.angle = math.radians(180)
    return sun

def look_at(obj, target):
    direction = target - obj.location
    obj.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()

def move_objs_to_scene():
    scene_col = bpy.context.scene.collection
    objs = [o for c in bpy.data.collections for o in c.objects]
    for o in objs:
        for c in list(o.users_collection):
            try:
                c.objects.unlink(o)
            except:
                pass
        try:
            scene_col.objects.link(o)
        except:
            pass
    for c in list(bpy.data.collections):
        if not c.objects:
            try:
                bpy.data.collections.remove(c)
            except:
                pass

def get_bbox():
    min_v = Vector((float('inf'),)*3)
    max_v = Vector((float('-inf'),)*3)
    bpy.context.view_layer.update()
    for o in bpy.context.scene.objects:
        if o.type == 'MESH' and o.visible_get():
            for corner in o.bound_box:
                w = o.matrix_world @ Vector(corner)
                min_v = Vector(map(min, min_v, w))
                max_v = Vector(map(max, max_v, w))
    return min_v, max_v

# TODO: add more options
def position_cam_pretty(cam, light, min_v, max_v):
    center = (min_v + max_v) * 0.5
    ext = max_v - min_v
    hx, hy = ext.x, ext.y
    if hx > hy * 5:
        dir_vec = Vector((0, 1, 0))
    elif hy > hx * 5:
        dir_vec = Vector((1, 0, 0))
    else:
        w1 = hx / (hx + hy) if hx+hy else 0.5
        w2 = hy / (hx + hy) if hx+hy else 0.5
        dir_vec = Vector((w1, w2, 0.3))
        dir_vec.normalize()
    diameter = ext.length
    dist = max(3.0, diameter * 2.5)
    cam.location = center + dir_vec * dist
    look_at(cam, center)
    light.location = cam.location + dir_vec * (diameter * 0.2 + 1.0)
    look_at(light, center)
    bpy.context.view_layer.update()

def render_model(path):
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)

# TODO: type of models like a ped/car/obj
def snapshoot(dff_folder: str, render_folder: str = None, report=None):
    def rpt(level, msg):
        if callable(report):
            try:
                report(level, msg)
            except:
                pass
        print(f"[{level}] {msg}")

    if not os.path.isdir(dff_folder):
        rpt('ERROR', f"dff_folder not found: {dff_folder}")
        return {'total':0, 'processed':0, 'errors':[f"dff_folder not found: {dff_folder}"], 'outs':[]}

    if render_folder:
        render_folder = os.path.expanduser(render_folder)
        try:
            os.makedirs(render_folder, exist_ok=True)
        except Exception as e:
            rpt('ERROR', f"cant create render folder {render_folder}: {e}")
            return {'total':0, 'processed':0, 'errors':[f"cant create render folder {render_folder}: {e}"], 'outs':[]}
    else:
        render_folder = os.path.join(dff_folder, "renders")
        os.makedirs(render_folder, exist_ok=True)

    setup_render()
    files = [f for f in os.listdir(dff_folder) if f.lower().endswith('.dff')]
    total = len(files)
    if total == 0:
        rpt('ERROR', f"no .dff files found in {dff_folder}")
        return {'total':0, 'processed':0, 'errors':[f"no .dff files found in {dff_folder}"], 'outs':[]}

    processed = 0
    errors = []
    outs = []

    rpt('INFO', f"found {total} dff files, starting rendering to {render_folder}")

    for i, f in enumerate(files):
        rpt('INFO', f"processing {i+1}/{total}: {f}")
        try:
            clear_scene()
            cam = create_camera()
            light = create_sun()
            try:
                bpy.ops.import_scene.dff(filepath=os.path.join(dff_folder, f), read_mat_split=True)
            except Exception as e:
                err = f"import error {f}: {e}"
                rpt('ERROR', err)
                errors.append(err)
                continue
            move_objs_to_scene()
            try:
                min_v, max_v = get_bbox()
            except Exception as e:
                err = f"bbox error {f}: {e}"
                rpt('ERROR', err)
                errors.append(err)
                continue
            try:
                position_cam_pretty(cam, light, min_v, max_v)
            except Exception as e:
                rpt('ERROR', f"camera positioning error {f}: {e}")
            out = os.path.join(render_folder, f + ".png")
            try:
                render_model(out)
            except Exception as e:
                err = f"render error {f}: {e}"
                rpt('ERROR', err)
                errors.append(err)
                continue
            processed += 1
            outs.append(out)
            rpt('INFO', f"render done: {f} -> {out}")
        except Exception as e:
            err = f"unexpected error {f}: {e}"
            rpt('ERROR', err)
            errors.append(err)
            continue

    rpt('INFO', "all files processed")
    return {'total': total, 'processed': processed, 'errors': errors, 'outs': outs}
