bl_info = {
    "name": "unware tool",
    "blender": (2, 80, 0),
    "category": "Import-Export",
    "author": "psychobye",
    "version": (2, 4, 0),
    "location": "View3D > N-Panel > unware",
    "description": "brfuck tool.",
}

from .gui import register, unregister

if "bpy" in locals():
    import importlib
    importlib.reload(gui)
