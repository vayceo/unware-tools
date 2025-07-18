# unware tools

a blender add-on for importing gta sa maps, exporting models, and cleaning dff files for use in unity or other engines.

install it like any normal blender addon — no setup required.

---

## features

### 🗺️ map importer
- scans folders for `.ipl` map files
- auto-finds the related `.dff` models
- places all objects into the scene, ready to go
- optional: keeps original world positions/rotations

### 📦 export system
- exports selected objects and all used textures to a `.zip`
- supports `.fbx` and `.dff` formats
- textures auto-converted to `.png`
- simple one-click export

### 🧹 dff cleaner
- removes:
  - collision meshes (`colmesh`, `colsphere`)
  - LODs
  - dummy empties
  - unused wheels
- regenerates wheels from placeholders (e.g. `wheel_rf` → real mesh)
- keeps scale/rotation/position clean

---

## how to use

1. open blender and go to `preferences > addons`
2. install this script or drop it into your `scripts/addons` folder
3. enable `unware tools`
4. open the "unware" tab in the right sidebar (N-panel)
5. set a root folder with `.ipl`, `.dff`, and textures
6. import, clean, export — done

---

## 📦 asset rules

- `.dff` models must be in a folder under your root path
- all textures **must be placed next to the corresponding `.dff`** (same folder)
- texture format: `*.png`, `*.bmp`, `*.jpg` — whatever blender can load
- texture names should match the ones used in the `.dff`

example:
root/
├─ map.ipl
├─ objects/
│ ├─ wall.dff
│ ├─ wall.png
│ ├─ road.dff
│ ├─ road.png
│ └─ ...

---

## compatibility

- tested on blender 4.4+
- works with gta sa mod assets
- exports clean meshes for unity/unreal

---

## license

no license yet, use at your own risk.