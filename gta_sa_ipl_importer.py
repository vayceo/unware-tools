import bpy
import os
import bmesh
from mathutils import Quaternion # need to check
from .dff import dff

material_cache = {}

def parse_ipl(ipl_path):
    objs = []
    with open(ipl_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        inside = False
        for raw in lines:
            line = raw.strip()
            if line.lower() == 'inst':
                inside = True
                continue
            if line.lower() == 'end':
                inside = False
                continue
            if not inside or not line:
                continue
            if line.startswith('//') or '//' in line or line.startswith('#'):
                continue
            parts = [x.strip() for x in line.split(',')]
            if len(parts) < 10:
                continue
            obj = {
                'id': parts[0],
                'model': parts[1],
                'interior': parts[2],
                'pos': (float(parts[3]), float(parts[4]), float(parts[5])),
                'rot': (float(parts[9]), float(parts[6]), float(parts[7]), float(parts[8])),
                'lod': parts[10] if len(parts) > 10 else ''
            }
            objs.append(obj)
    return objs

def filter_triangles(verts, tris):
    return [
        tri for tri in tris
        if not (tri.a >= len(verts) or tri.b >= len(verts) or tri.c >= len(verts)
                or verts[tri.a] == verts[tri.b]
                or verts[tri.b] == verts[tri.c]
                or verts[tri.a] == verts[tri.c])
    ]

def get_or_create_material(mat_name, mat_data, dff_source, texture_dict):
    global material_cache
    cache_key = f"{mat_name}_{mat_data.color.r if mat_data.color else 0}"
    if cache_key in material_cache:
        return material_cache[cache_key]

    bpy_mat = bpy.data.materials.new(name=mat_name)
    bpy_mat.use_nodes = True
    nodes = bpy_mat.node_tree.nodes
    links = bpy_mat.node_tree.links

    for n in list(nodes):
        if n.type == 'BSDF_DIFFUSE':
            nodes.remove(n)

    principled = nodes.get("Principled BSDF") or nodes.new("ShaderNodeBsdfPrincipled")
    output = nodes.get("Material Output") or nodes.new("ShaderNodeOutputMaterial")
    links.new(principled.outputs["BSDF"], output.inputs["Surface"])

    has_texture = bool(mat_data.textures)
    if has_texture:
        tex_name = mat_data.textures[0].name.lower()
        tex_node = nodes.new("ShaderNodeTexImage")
        tex_node.name = tex_name
        existing = next((img for img in bpy.data.images if img.name.lower()==tex_name), None)
        if existing:
            tex_node.image = existing
        else:
            tex_path = texture_dict.get(tex_name) or os.path.join(dff_source, f"{tex_name}.png")
            if os.path.exists(tex_path):
                tex_node.image = bpy.data.images.load(tex_path, check_existing=True)
        links.new(tex_node.outputs["Color"], principled.inputs["Base Color"])
    elif mat_data.color:
        c = mat_data.color
        principled.inputs["Base Color"].default_value = (c.r/255, c.g/255, c.b/255, c.a/255)

    material_cache[cache_key] = bpy_mat
    return bpy_mat

def import_dff(model_name, dff_source, texture_dict=None):
    texture_dict = texture_dict or {}
    loader = dff()
    try:
        if isinstance(dff_source, str):
            path = os.path.join(dff_source, model_name + '.dff')
            if not os.path.exists(path): return None
            loader.load_file(path)
        else:
            loader.load_memory(dff_source)
    except Exception:
        return None

    if not loader.geometry_list:
        return None

    geo = loader.geometry_list[0]
    tris = geo.extensions.get('mat_split', geo.triangles)
    tris = filter_triangles(geo.vertices, tris)
    mesh = bpy.data.meshes.new(model_name)
    obj = bpy.data.objects.new(model_name, mesh)
    bm = bmesh.new()

    for v in geo.vertices:
        bm.verts.new((v.x, v.y, v.z))
    bm.verts.ensure_lookup_table()
    uv_layers = [bm.loops.layers.uv.new(f"uv{i}") for i in range(len(geo.uv_layers))]

    if geo.materials:
        for i, mat in enumerate(geo.materials):
            mat_name = (mat.textures[0].name.lower() if mat.textures else f"{model_name}_mat_{i}")
            bpy_mat = get_or_create_material(mat_name, mat, dff_source, texture_dict)
            mesh.materials.append(bpy_mat)

    for tri in tris:
        try:
            face = bm.faces.new((bm.verts[tri.a], bm.verts[tri.b], bm.verts[tri.c]))
            if geo.materials:
                face.material_index = tri.material
            for li, loop in enumerate(face.loops):
                for ui, uv in enumerate(geo.uv_layers):
                    luv = geo.uv_layers[ui][[tri.a,tri.b,tri.c][li]]
                    loop[uv_layers[ui]].uv = (luv.u, 1-luv.v)
        except ValueError:
            continue

    bm.to_mesh(mesh); bm.free()
    if uv_layers:
        mesh.uv_layers.active = mesh.uv_layers[0]; mesh.uv_layers[0].name = "uvmap"
    return obj

def place_objects(objs, dff_folder):
    global material_cache
    material_cache = {}
    bpy.context.scene.collection.hide_viewport = True
    try:
        for o in objs:
            inst = import_dff(o['model'], dff_folder)
            if not inst: continue

            # IDK MAYBE ITS NOT WORK, BUT ok :(
            # 1. convert pos: (X-gta, Y-gta, Z-gta) -> (X-blend, Y-blend, Z-blend)
            xg, yg, zg = o['pos']
            inst.location = ( xg, -zg, yg )

            # 2. quaternion from GTA (w, x, y, z)
            w, x, y, z = o['rot']
            q = Quaternion((w, x, y, z))

            # 3. replace components: 
            # from q = (w, x, y, z) -> q2 = (w,  x,  z, -y)
            q2 = Quaternion((q.w, q.x, q.z, -q.y))
            inst.rotation_mode = 'QUATERNION'
            inst.rotation_quaternion = q2

            inst['id'] = int(o['id']) if o['id'].isdigit() else -1
            inst['interior'] = int(o['interior']) if o['interior'].isdigit() else -1
            try:
                inst['lod'] = int(o['lod'])
            except:
                inst['lod'] = -1
            bpy.context.collection.objects.link(inst)
    finally:
        bpy.context.scene.collection.hide_viewport = False
        bpy.context.view_layer.update()
