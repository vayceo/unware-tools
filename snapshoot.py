import bpy
import os
import math
from mathutils import Vector

from .material_helpers import apply_car_colors

def clear_scene(keep_cam_and_lights=False):
    objs = list(bpy.data.objects)
    for o in objs:
        if keep_cam_and_lights and o.type in ('CAMERA', 'LIGHT'):
            continue
        try:
            bpy.data.objects.remove(o, do_unlink=True)
        except:
            pass

    if keep_cam_and_lights:
        data_iters = (bpy.data.meshes, bpy.data.materials, bpy.data.armatures)
    else:
        data_iters = (bpy.data.meshes, bpy.data.materials, bpy.data.armatures, bpy.data.cameras, bpy.data.lights)

    for data_iter in data_iters:
        for d in list(data_iter):
            try:
                data_iter.remove(d)
            except:
                pass

    for col in list(bpy.data.collections):
        try:
            if keep_cam_and_lights:
                if any(o.type in ('CAMERA','LIGHT') for o in col.objects):
                    continue
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
    any_mesh = False
    for o in bpy.context.scene.objects:
        if o.type == 'MESH' and o.visible_get():
            any_mesh = True
            for corner in o.bound_box:
                w = o.matrix_world @ Vector(corner)
                min_v.x = min(min_v.x, w.x)
                min_v.y = min(min_v.y, w.y)
                min_v.z = min(min_v.z, w.z)
                max_v.x = max(max_v.x, w.x)
                max_v.y = max(max_v.y, w.y)
                max_v.z = max(max_v.z, w.z)
    if not any_mesh:
        raise RuntimeError("no visible mesh for bbox")
    return min_v, max_v

def position_cam_pretty(cam, light, min_v, max_v):
    center = (min_v + max_v) * 0.5
    ext = max_v - min_v
    hx, hy = ext.x, ext.y
    if hx > hy * 5:
        dir_vec = Vector((0, 1, 0))
    elif hy > hx * 5:
        dir_vec = Vector((1, 0, 0))
    else:
        denom = (hx + hy) if (hx + hy) else 1.0
        w1 = hx / denom
        w2 = hy / denom
        dir_vec = Vector((w1, w2, 0.3))
        if dir_vec.length == 0:
            dir_vec = Vector((0, 1, 0.3))
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

def snapshoot(dff_folder: str, render_folder: str = None, report=None, mode: str = 'OBJECT', fov: float = None,
             primary_color=None, secondary_color=None, emission_strength: float = 5.0):
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

    rpt('INFO', f"found {total} dff files, starting rendering to {render_folder} (mode={mode})")

    for i, f in enumerate(files):
        rpt('INFO', f"processing {i+1}/{total}: {f}")
        try:
            if mode == 'CAR':
                clear_scene(keep_cam_and_lights=True)
            else:
                clear_scene(keep_cam_and_lights=False)

            try:
                bpy.ops.import_scene.dff(filepath=os.path.join(dff_folder, f), read_mat_split=True)
            except Exception as e:
                err = f"import error {f}: {e}"
                rpt('ERROR', err)
                errors.append(err)
                continue

            move_objs_to_scene()

            if mode == 'CAR':
                try:
                    bpy.ops.car.clean_model() # car cleaner
                    rpt('INFO', f"car cleaned: {f}")
                    # apply colors
                    try:
                        apply_car_colors(primary_color=primary_color, secondary_color=secondary_color, emission_strength=emission_strength)
                        rpt('INFO', f"applied car colors for {f}")
                    except Exception as e:
                        rpt('ERROR', f"apply_car_colors failed: {e}")
                except Exception as e:
                    rpt('ERROR', f"car cleaner failed: {e}")

            try:
                min_v, max_v = get_bbox()
            except Exception as e:
                err = f"bbox error {f}: {e}"
                rpt('ERROR', err)
                errors.append(err)
                continue

            center = (min_v + max_v) * 0.5
            ext = (max_v - min_v)
            diameter = ext.length
            dist = max(3.0, diameter * 2.5)

            cam = None
            light = None
            cam_created = False
            light_created = False

            if mode == 'CAR':
                # cam pos
                FRONT_FACTOR = 1.0
                SIDE_FACTOR = 0.35
                HEIGHT_FACTOR = 1.25

                center += Vector((-0.2, 0.0, 0.0)) # center offset
                forward = Vector((0, 1, 0))
                side = Vector((1, 0, 0))

                cam = create_camera()
                if fov:
                    try:
                        cam.data.angle = math.radians(float(fov))
                    except Exception:
                        pass
                cam_created = True

                light = create_sun()
                light_created = True

                cam.location = center + forward * (dist * FRONT_FACTOR) + side * (dist * SIDE_FACTOR)
                cam.location.z = center.z + max(0.5, ext.z * HEIGHT_FACTOR)
                look_at(cam, center)

                try:
                    light.location = cam.location + (cam.matrix_world.to_quaternion() @ Vector((0, -1, 0))) * (diameter * 0.2 + 1.0)
                except:
                    light.location = cam.location + Vector((0, -1, 0)) * (diameter * 0.2 + 1.0)
                look_at(light, center)

            else:
                cam = create_camera()
                if fov:
                    try:
                        cam.data.angle = math.radians(float(fov))
                    except Exception:
                        pass
                cam_created = True

                light = create_sun()
                light_created = True
                try:
                    position_cam_pretty(cam, light, min_v, max_v)
                except Exception as e:
                    rpt('ERROR', f"camera pretty positioning failed: {e}")

            out = os.path.join(render_folder, f + ".png")
            try:
                render_model(out)
            except Exception as e:
                err = f"render error {f}: {e}"
                rpt('ERROR', err)
                errors.append(err)
                try:
                    if cam_created and cam and cam.name in bpy.data.objects:
                        bpy.data.objects.remove(cam, do_unlink=True)
                    if light_created and light and light.name in bpy.data.objects:
                        bpy.data.objects.remove(light, do_unlink=True)
                except:
                    pass
                continue

            try:
                if cam_created and cam and cam.name in bpy.data.objects:
                    bpy.data.objects.remove(cam, do_unlink=True)
                if light_created and light and light.name in bpy.data.objects:
                    bpy.data.objects.remove(light, do_unlink=True)
            except Exception as e:
                rpt('ERROR', f"failed to cleanup cam/light: {e}")

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
