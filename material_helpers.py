import bpy

def _parse_color(col):
    if not col:
        return None
    if isinstance(col, str):
        c = col.lstrip('#')
        if len(c) == 6:
            return tuple(int(c[i:i+2], 16)/255.0 for i in (0,2,4))
        return None
    if isinstance(col, (list, tuple)) and len(col) >= 3:
        return (float(col[0]), float(col[1]), float(col[2]))
    return None

def _remove_image_nodes_by_substring(mat, needle_lower):
    if not mat or not mat.node_tree:
        return 0
    nodes = mat.node_tree.nodes
    removed = 0
    for n in list(nodes):
        try:
            if n.type == 'TEX_IMAGE' and n.image and needle_lower in (n.image.name or '').lower():
                for link in list(n.outputs[0].links):
                    try:
                        mat.node_tree.links.remove(link)
                    except:
                        pass
                nodes.remove(n)
                removed += 1
        except Exception:
            try:
                if n.type == 'TEX_IMAGE':
                    n.image = None
                    removed += 1
            except:
                pass
    return removed

def _ensure_principled(mat):
    if not mat:
        return None
    if not mat.use_nodes:
        mat.use_nodes = True
    nodes = mat.node_tree.nodes
    bsdf = next((n for n in nodes if n.type == 'BSDF_PRINCIPLED'), None)
    output = next((n for n in nodes if n.type == 'OUTPUT_MATERIAL'), None)
    if not bsdf:
        bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
        bsdf.location = (0, 0)
        if output:
            try:
                mat.node_tree.links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])
            except:
                pass
    return bsdf

def _set_principled_color(mat, color, alpha=1.0):
    if not mat:
        return False
    bsdf = _ensure_principled(mat)
    if not bsdf:
        return False
    r,g,b = color
    try:
        bsdf.inputs['Base Color'].default_value = (r, g, b, 1.0)
    except:
        pass
    try:
        bsdf.inputs['Alpha'].default_value = alpha
    except:
        pass
    try:
        if alpha < 1.0:
            mat.blend_method = 'BLEND'
            mat.shadow_method = 'NONE'
        else:
            mat.blend_method = 'OPAQUE'
            mat.shadow_method = 'OPAQUE'
    except:
        pass
    return True

def _add_emission(mat, color, strength=5.0):
    if not mat or not mat.node_tree:
        return False
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    output = next((n for n in nodes if n.type == 'OUTPUT_MATERIAL'), None)
    bsdf = next((n for n in nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if not output:
        output = nodes.new(type='ShaderNodeOutputMaterial')
        output.location = (400, 0)
    if not bsdf:
        bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
        bsdf.location = (0, 0)

    emi = nodes.new(type='ShaderNodeEmission')
    emi.location = (0, -200)
    r,g,b = color
    try:
        emi.inputs['Color'].default_value = (r, g, b, 1.0)
        try:
            emi.inputs['Strength'].default_value = strength
        except:
            # fallback: multiply color by strength
            emi.inputs['Color'].default_value = (r * strength, g * strength, b * strength, 1.0)
    except:
        pass

    add = nodes.new(type='ShaderNodeAddShader')
    add.location = (200, 0)

    for link in list(output.inputs['Surface'].links):
        try:
            links.remove(link)
        except:
            pass

    try:
        links.new(bsdf.outputs['BSDF'], add.inputs[0])
    except:
        pass
    try:
        links.new(emi.outputs['Emission'], add.inputs[1])
    except:
        pass
    try:
        links.new(add.outputs['Shader'], output.inputs['Surface'])
    except:
        pass

    mat.use_nodes = True
    return True

def apply_car_colors(primary_color=None, secondary_color=None, emission_strength=5.0):
    prim = _parse_color(primary_color)
    sec = _parse_color(secondary_color)
    remap_name = "remapvehicles.png"
    lights_name = "vehiclelights128.png"
    vt_left = "v_t_left.png"
    vt_right = "v_t_right.png"
    orange = (1.0, 0.55, 0.0)
    white = (1.0, 1.0, 1.0)
    black = (0.0, 0.0, 0.0)

    for mat in list(bpy.data.materials):
        if not mat or not mat.name:
            continue
        lname = mat.name.lower()

        removed_lights = _remove_image_nodes_by_substring(mat, lights_name)
        if removed_lights:
            if 'glass' not in lname:
                _set_principled_color(mat, white, alpha=1.0)
                _add_emission(mat, white, strength=emission_strength)

        removed_vt_l = _remove_image_nodes_by_substring(mat, vt_left)
        removed_vt_r = _remove_image_nodes_by_substring(mat, vt_right)
        if removed_vt_l or removed_vt_r:
            _set_principled_color(mat, orange, alpha=1.0)
            _add_emission(mat, orange, strength=1.5)

        if 'primary' in lname and prim:
            _remove_image_nodes_by_substring(mat, remap_name)
            _set_principled_color(mat, prim, alpha=1.0)
        elif 'secondary' in lname and sec:
            _remove_image_nodes_by_substring(mat, remap_name)
            _set_principled_color(mat, sec, alpha=1.0)

        if 'glass' in lname:
            _remove_image_nodes_by_substring(mat, lights_name)
            _set_principled_color(mat, black, alpha=0.2)
            try:
                mat.use_backface_culling = False
            except:
                pass
