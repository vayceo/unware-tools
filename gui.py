import bpy
import os
import zipfile
import tempfile
import re
from .gta_sa_ipl_importer import parse_ipl, place_objects
from . import snapshoot as snapshoot_module

def scan_ipl_files(root):
    files = []
    for dp, _, names in os.walk(root):
        for f in names:
            if f.lower().endswith('.ipl'):
                files.append((os.path.join(dp, f), f))
    return files

def find_dff_folder(root):
    for dp, _, names in os.walk(root):
        for f in names:
            if f.lower().endswith('.dff'):
                return dp
    return ''

def safe_name(n):
    return re.sub(r'[^a-z0-9_\\-]', '_', n.lower())

# ---------- IPL import ----------
class autoscan_ipl_item(bpy.types.PropertyGroup):
    path: bpy.props.StringProperty()
    name: bpy.props.StringProperty()

class autoscan_props(bpy.types.PropertyGroup):
    root_path: bpy.props.StringProperty(
        name="root",
        subtype='DIR_PATH',
        update=lambda self, ctx: self.update_list()
    )
    dff_path: bpy.props.StringProperty(
        name="dff folders",
        subtype='DIR_PATH'
    )
    ipl_items: bpy.props.CollectionProperty(type=autoscan_ipl_item)
    ipl_enum: bpy.props.EnumProperty(
        name="ipl",
        items=lambda self, ctx: [(it.path, it.name, "") for it in self.ipl_items] if self.ipl_items else []
    )
    preserve_transforms: bpy.props.BoolProperty(
        name="preserve transforms",
        description="keep world position and rotation during export",
        default=False
    )
    export_format: bpy.props.EnumProperty(
        name="format",
        items=[('FBX','fbx',''),('DFF','dff','')],
        default='FBX'
    )
    optimize: bpy.props.BoolProperty(
        name="optimize",
        description="clear scene before import (recommended)",
        default=True
    )
    snap_mode: bpy.props.EnumProperty(
        name="snap mode",
        items=[('OBJECT', 'OBJECT', 'auto camera'), ('CAR', 'CAR', 'static car camera')],
        default='OBJECT'
    )
    snap_fov: bpy.props.FloatProperty(
        name="snap FOV",
        description="field of view in degrees for snapshot camera",
        default=15.0,
        min=1.0,
        max=179.0
    )
    def update_list(self):
        self.ipl_items.clear()
        if os.path.isdir(self.root_path):
            for p, n in scan_ipl_files(self.root_path):
                it = self.ipl_items.add()
                it.path, it.name = p, n
            if self.ipl_items:
                self.ipl_enum = self.ipl_items[0].path
            else:
                self.ipl_enum = ''

class import_autoscan_ipl_operator(bpy.types.Operator):
    bl_idname = "import.autoscan_ipl"
    bl_label = "import ipl"
    def execute(self, context):
        props = context.scene.autoscan_props
        if props.optimize:
            bpy.ops.object.select_all(action='SELECT')
            bpy.ops.object.delete()

        ipl_path = props.ipl_enum
        if not os.path.exists(ipl_path):
            self.report({'ERROR'}, "ipl file not found")
            return {'CANCELLED'}
        dff_folder = find_dff_folder(props.root_path)
        if not dff_folder:
            self.report({'ERROR'}, "dff folder not found")
            return {'CANCELLED'}
        objs = parse_ipl(ipl_path)
        place_objects(objs, dff_folder)
        for area in context.window.screen.areas:
            if area.type == 'VIEW_3D':
                for space in area.spaces:
                    if space.type == 'VIEW_3D':
                        space.shading.type = 'SOLID'
                        space.shading.color_type = 'TEXTURE'
                        space.shading.show_specular_highlight = False
                        space.shading.show_object_outline = False
        self.report({'INFO'}, f"imported {len(objs)} objects")
        return {'FINISHED'}

class export_zip_operator(bpy.types.Operator):
    bl_idname = "export.textures_and_model_zip"
    bl_label = "export zip"
    filepath: bpy.props.StringProperty(subtype="FILE_PATH")

    def execute(self, context):
        props = context.scene.autoscan_props
        sel = context.selected_objects
        if not sel:
            self.report({'ERROR'}, "no selected objects")
            return {'CANCELLED'}

        tmp = tempfile.mkdtemp()
        files = []

        for obj in sel:
            if not obj.material_slots:
                continue
            for slot in obj.material_slots:
                mat = slot.material
                if not mat or not mat.node_tree:
                    continue
                for node in mat.node_tree.nodes:
                    if node.type == 'TEX_IMAGE' and node.image:
                        if node.image.packed_file:
                            node.image.unpack(method='USE_ORIGINAL')
                        name = safe_name(os.path.splitext(node.image.name)[0])
                        path = os.path.join(tmp, f"{name}.png")
                        try:
                            node.image.save_render(path)
                        except:
                            node.image.filepath_raw = path
                            node.image.file_format = 'PNG'
                            node.image.save()
                        files.append(path)

        fmt = props.export_format.lower()
        name = safe_name(sel[0].name)
        model_path = os.path.join(tmp, f"{name}.{fmt}")

        if fmt == 'fbx':
            bpy.ops.export_scene.fbx(
                filepath=model_path,
                use_selection=True,
                apply_unit_scale=False,
                bake_space_transform=not props.preserve_transforms,
                use_space_transform=not props.preserve_transforms,
                global_scale=1.0
            )
        else:
            bpy.ops.export_dff.scene(
                filepath=model_path,
                only_selected=True,
                preserve_positions=props.preserve_transforms,
                preserve_rotations=props.preserve_transforms
            )
        files.append(model_path)

        out = self.filepath or os.path.join(os.path.expanduser("~"), "Desktop", f"{name}.zip")
        if not out.lower().endswith('.zip'):
            out += '.zip'

        with zipfile.ZipFile(out, 'w') as z:
            for f in files:
                z.write(f, os.path.basename(f))

        self.report({'INFO'}, f"exported to {out}")
        return {'FINISHED'}

    def invoke(self, context, event):
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        name = safe_name(context.selected_objects[0].name) if context.selected_objects else "export"
        self.filepath = os.path.join(desktop, f"{name}.zip")
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

# ---------- snapshoot operator ----------
class SNAP_OT_snapshoot(bpy.types.Operator):
    bl_idname = "snapshoot.make_snapshoot"
    bl_label = "snapshoot"
    filepath: bpy.props.StringProperty(subtype='FILE_PATH')

    def execute(self, context):
        props = context.scene.autoscan_props

        dff_folder = props.dff_path if props.dff_path and os.path.isdir(props.dff_path) else find_dff_folder(props.root_path)
        if not dff_folder or not os.path.isdir(dff_folder):
            self.report({'ERROR'}, "dff folder not found")
            return {'CANCELLED'}

        sel = (self.filepath or "").strip()
        if not sel:
            out = os.path.join(os.path.expanduser("~"), "Desktop")
        else:
            sel = os.path.expanduser(sel)
            if os.path.isdir(sel):
                out = sel
            else:
                out = os.path.dirname(sel) or os.path.join(os.path.expanduser("~"), "Desktop")

        try:
            os.makedirs(out, exist_ok=True)
        except Exception as e:
            self.report({'ERROR'}, f"cant create out folder: {e}")
            return {'CANCELLED'}

        files = [f for f in os.listdir(dff_folder) if f.lower().endswith('.dff')]
        total = len(files)
        if total == 0:
            msg = f"no dff files in {dff_folder}"
            self.report({'ERROR'}, msg)
            return {'CANCELLED'}

        wm = context.window_manager
        try:
            wm.progress_begin(0, total)
        except:
            pass

        def report_cb(level, msg):
            self.report({level}, msg)

        report_cb('INFO', f"start snapshoot: dff_folder={dff_folder}, out={out}, count={total}")

        try:
            summary = snapshoot_module.snapshoot(dff_folder, out, report=report_cb, mode=props.snap_mode, fov=props.snap_fov)
        except Exception as e:
            report_cb('ERROR', f"snapshoot crashed: {e}")
            try:
                wm.progress_end()
            except:
                pass
            return {'CANCELLED'}

        processed = summary.get('processed', 0)
        errors = summary.get('errors', [])
        outs = summary.get('outs', [])

        missing = []
        for p in outs:
            if not os.path.exists(p):
                missing.append(p)
                msg = f"file not found after render: {p}"
                report_cb('ERROR', msg)

        try:
            for i in range(processed):
                wm.progress_update(i+1)
        except:
            pass
        try:
            wm.progress_end()
        except:
            pass

        report_cb('INFO', f"done. processed={processed}, errors={len(errors)}, missing_files={len(missing)}")
        if errors:
            for e in errors:
                report_cb('ERROR', e)
        if missing:
            report_cb('ERROR', "some renders reported saved but files missing. check antivirus or permissions")

        return {'FINISHED'}

    def invoke(self, context, event):
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        self.filepath = desktop
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

# ---------- car cleaner ----------
class CAR_OT_clean_model(bpy.types.Operator):
    bl_idname = "car.clean_model"
    bl_label = "clean car"
    bl_description = "delete cols, lods, dummies and more"
    def execute(self, context):
        logs = []
        objs = list(bpy.data.objects)
        world_matrices = {o.name: o.matrix_world.copy() for o in objs}
        empty_names = [o.name for o in objs if o.type == 'EMPTY']
        # remove cols and LODs
        for o in objs:
            name = o.name
            lname = name.lower()
            if any(tag in lname for tag in ("colmesh","colsphere")) or lname.endswith("vlo"):
                bpy.data.objects.remove(o, do_unlink=True)
                logs.append(f"removed {name}")
        # remove wheels
        mesh_data = None
        for o in list(bpy.data.objects):
            if o.name.startswith("wheel") and "_" not in o.name and o.type=='MESH':
                mesh_data = o.data
                name = o.name
                bpy.data.objects.remove(o, do_unlink=True)
                logs.append(f"removed wheel {name}")
        # duplicate wheels
        if mesh_data:
            for name in empty_names:
                if name.startswith("wheel_"):
                    dummy = bpy.data.objects.get(name)
                    if not dummy: continue
                    new = bpy.data.objects.new(f"wheel_{name}", mesh_data)
                    new.matrix_world = dummy.matrix_world.copy()
                    if name.startswith("wheel_l"):
                        sx, sy, sz = new.scale
                        new.scale = (-sx, sy, sz)
                    context.collection.objects.link(new)
                    logs.append(f"duplicated wheel at {name}")
        # cleanup dummies
        for name in empty_names:
            empty = bpy.data.objects.get(name)
            if not empty: continue
            for child in list(empty.children):
                child.parent = None
            bpy.data.objects.remove(empty, do_unlink=True)
            logs.append(f"removed dummy {name}")
        # restore matrices
        for name, mat in world_matrices.items():
            o = bpy.data.objects.get(name)
            if o: o.matrix_world = mat
        for msg in logs:
            self.report({'INFO'}, msg)
        return {'FINISHED'}

# ---------- UI ----------
class unware_tools_panel(bpy.types.Panel):
    bl_label = "unware"
    bl_idname = "unware_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "unware"
    def draw(self, context):
        layout = self.layout
        props = context.scene.autoscan_props

        box = layout.box()
        box.label(text="map import", icon='IMPORT')
        box.prop(props, "root_path")
        if props.ipl_enum:
            box.prop(props, "ipl_enum", text="ipl")
            box.prop(props, "optimize", text="optimize")
            box.operator("import.autoscan_ipl")
        else:
            box.label(text="no ipl files found")

        box = layout.box()
        box.label(text="export", icon='EXPORT')
        box.prop(props, "preserve_transforms", text="preserve transforms")
        box.prop(props, "export_format", text="format")
        box.operator("export.textures_and_model_zip")

        box = layout.box()
        box.label(text="car cleaner", icon='MODIFIER')
        box.operator("car.clean_model", text="clean car")

        box = layout.box()
        box.label(text="snapshoot", icon='RENDER_STILL')
        box.prop(props, "dff_path", text="dff")
        box.prop(props, "snap_mode", text="mode")
        box.prop(props, "snap_fov", text="FOV")
        box.operator("snapshoot.make_snapshoot", text="snapshoot")

classes = [
    autoscan_ipl_item,
    autoscan_props,
    import_autoscan_ipl_operator,
    export_zip_operator,
    SNAP_OT_snapshoot,
    CAR_OT_clean_model,
    unware_tools_panel,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.autoscan_props = bpy.props.PointerProperty(type=autoscan_props)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.autoscan_props

if __name__ == "__main__":
    register()
