"""
=============================================================================
 zen_box20.py — 젠제네틱스 정품 박스(20포) 텅스터 지기 확인 렌더
=============================================================================

 ★ 아무것도 고치지 않아도 됩니다. 열어서 ▶ 만 누르세요.
   확인용 3장을 렌더합니다:
     check_box20_closed_front.png   닫힌 상태 앞 3/4
     check_box20_closed_back.png    닫힌 상태 뒤 3/4
     check_box20_open.png           뚜껑 100도 개봉

 실행 방법
   1. 이 파일을 zen 폴더에 넣습니다 (textures 폴더 옆)
   2. Blender 실행 → Scripting 탭 → [열기] 로 이 파일 열기 → ▶
   ※ 복사 붙여넣기 하면 경로를 못 찾습니다. 반드시 [열기] 로 여세요.

 필요한 텍스처 (zen/textures/)  — box20 9장
   zen_potassium_box20_lid_top / lid_front / lid_skirt_l / lid_skirt_r
   zen_potassium_box20_front / back / side_l / side_r / bottom

 구조 실측값 (도면 벡터에서 추출 — zen_box20_panels.json)
   박스 116 x 85 x 37.5 mm, 350로얄아이보리 벨벳코팅
   텅스터 지기 1피스: 뒷벽 상단 힌지 + 뚜껑(상판 116x85)
   + 앞 텅 스커트(37.5) + 뚜껑 옆 스커트 2

 Blender 4.2 ~ 5.x 호환
=============================================================================
"""

import bpy
import bmesh
import math
import os

PRODUCT = "potassium"
SCRIPT_VERSION = "box20-check"

# ---- 치수 (mm) --------------------------------------------------------------
BOX_W = 116.0    # 가로 (x)
BOX_D = 85.0     # 깊이 (y)
BOX_H = 37.5     # 높이 (z)
CARD_T = 0.45    # 350g 판지 두께
SKIRT = 37.5     # 앞 텅 스커트 높이
LID_OPEN_DEG = 100.0

MM = 0.001
LIGHT_POWER = 0.1


def _base_dir():
    import bpy, os
    for txt in bpy.data.texts:
        if txt.filepath:
            p = bpy.path.abspath(txt.filepath)
            if os.path.exists(p):
                return os.path.dirname(p)
    if bpy.data.filepath:
        return os.path.dirname(bpy.path.abspath(bpy.data.filepath))
    home = os.path.expanduser("~")
    for cand in (os.path.join(home, "Desktop", "zen"),
                 os.path.join(home, "바탕화면", "zen"),
                 os.path.join(home, "zen")):
        if os.path.isdir(cand):
            return cand
    raise RuntimeError(
        "\n\n  스크립트 폴더를 찾지 못했습니다.\n"
        "  Blender 스크립팅함에서 [열기] 버튼으로 zen_box20.py 를\n"
        "  직접 열어서 실행해 주세요. (복사 붙여넣기 말고요)\n")


BASE_DIR = _base_dir()
TEX_DIR = os.path.join(BASE_DIR, "textures")
OUT_DIR = os.path.join(BASE_DIR, "render")


# ---- 공용 유틸 --------------------------------------------------------------

def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for block in (bpy.data.meshes, bpy.data.materials,
                  bpy.data.images, bpy.data.lights, bpy.data.cameras):
        for item in list(block):
            if item.users == 0:
                block.remove(item)
    for img in list(bpy.data.images):
        if img.name not in ("Render Result", "Viewer Node"):
            try:
                bpy.data.images.remove(img, do_unlink=True)
            except Exception:
                pass


def set_input(node, names, value):
    if isinstance(names, str):
        names = [names]
    for n in names:
        if n in node.inputs:
            try:
                node.inputs[n].default_value = value
                return True
            except Exception:
                pass
    return False


def principled_of(mat):
    for n in mat.node_tree.nodes:
        if n.type == "BSDF_PRINCIPLED":
            return n
    return None


def load_tex(filename):
    path = os.path.join(TEX_DIR, filename)
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"\n\n  텍스처를 찾을 수 없습니다:\n    {path}\n"
            f"  zen/textures 폴더에 box20 텍스처 9장이 있는지 확인하세요.\n")
    img = bpy.data.images.load(path, check_existing=True)
    try:
        img.reload()
    except Exception:
        pass
    img.colorspace_settings.name = "sRGB"
    print(f"  텍스처 로드: {filename}  ({img.size[0]} x {img.size[1]} px)")
    return img


def mat_printed(name, image):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial"); out.location = (500, 0)
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled"); bsdf.location = (200, 0)
    tex = nt.nodes.new("ShaderNodeTexImage"); tex.location = (-200, 0)
    tex.image = image
    tex.interpolation = "Cubic"
    tex.extension = "EXTEND"
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    set_input(bsdf, "Roughness", 0.55)          # 벨벳코팅
    set_input(bsdf, "Metallic", 0.0)
    set_input(bsdf, ["Coat Weight", "Clearcoat"], 0.05)
    set_input(bsdf, ["Specular IOR Level", "Specular"], 0.35)
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat


def mat_plain(name, color, rough=0.6):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = principled_of(mat)
    set_input(bsdf, "Base Color", color)
    set_input(bsdf, "Roughness", rough)
    set_input(bsdf, "Metallic", 0.0)
    return mat


# ---- 지오메트리 -------------------------------------------------------------

W = BOX_W * MM
D = BOX_D * MM
H = BOX_H * MM
T = CARD_T * MM

X_L, X_R = -W/2, W/2
Y_F, Y_B = -D/2, D/2
Z_B, Z_T = -H/2, H/2

(M_FRONT, M_BACK, M_SIDE_L, M_SIDE_R, M_BOTTOM,
 M_LID_TOP, M_LID_FRONT, M_SKIRT_L, M_SKIRT_R,
 M_IVORY, M_WHITE) = range(11)

IVORY = (0.93, 0.91, 0.85, 1.0)
WHITE = (0.96, 0.96, 0.95, 1.0)


class Builder:
    def __init__(self, name):
        self.bm = bmesh.new()
        self.uv = self.bm.loops.layers.uv.new("UVMap")
        self.name = name

    def quad(self, pts, mat, uvs=None, flip=False):
        vs = [self.bm.verts.new(p) for p in pts]
        if flip:
            vs = list(reversed(vs))
            uvs = list(reversed(uvs)) if uvs else None
        try:
            f = self.bm.faces.new(vs)
        except ValueError:
            return
        f.material_index = mat
        if uvs:
            for loop, uv in zip(f.loops, uvs):
                loop[self.uv].uv = uv

    def to_object(self, materials):
        me = bpy.data.meshes.new(self.name)
        self.bm.normal_update()
        self.bm.to_mesh(me)
        self.bm.free()
        obj = bpy.data.objects.new(self.name, me)
        bpy.context.collection.objects.link(obj)
        for m in materials:
            obj.data.materials.append(m)
        return obj


def build_tray(mats):
    """몸통: 바닥 + 앞/뒤/옆 벽 (안쪽은 백지)."""
    b = Builder("box20_tray")

    # 앞벽 (관찰자 -Y): u=(x-X_L)/W, v=(z-Z_B)/H
    b.quad([(X_L, Y_F, Z_B), (X_R, Y_F, Z_B), (X_R, Y_F, Z_T), (X_L, Y_F, Z_T)],
           M_FRONT, [(0, 0), (1, 0), (1, 1), (0, 1)], flip=True)
    b.quad([(X_L, Y_F+T, Z_B), (X_R, Y_F+T, Z_B),
            (X_R, Y_F+T, Z_T), (X_L, Y_F+T, Z_T)], M_WHITE)

    # 뒷벽 (관찰자 +Y): u=(X_R-x)/W
    b.quad([(X_R, Y_B, Z_B), (X_L, Y_B, Z_B), (X_L, Y_B, Z_T), (X_R, Y_B, Z_T)],
           M_BACK, [(0, 0), (1, 0), (1, 1), (0, 1)], flip=True)
    b.quad([(X_R, Y_B-T, Z_B), (X_L, Y_B-T, Z_B),
            (X_L, Y_B-T, Z_T), (X_R, Y_B-T, Z_T)], M_WHITE, flip=True)

    # 왼쪽 벽 (관찰자 -X). 텍스처는 세로형(37.5 x 85):
    #   이미지 u: 왼쪽=벽 위, 오른쪽=벽 아래 / 이미지 v: 아래=앞, 위=뒤
    def uv_sl(y, z):
        return ((z - Z_B) / H, (y - Y_F) / D)
    b.quad([(X_L, Y_F, Z_B), (X_L, Y_B, Z_B), (X_L, Y_B, Z_T), (X_L, Y_F, Z_T)],
           M_SIDE_L, [uv_sl(Y_F, Z_B), uv_sl(Y_B, Z_B),
                      uv_sl(Y_B, Z_T), uv_sl(Y_F, Z_T)], flip=True)
    b.quad([(X_L+T, Y_F, Z_B), (X_L+T, Y_B, Z_B),
            (X_L+T, Y_B, Z_T), (X_L+T, Y_F, Z_T)], M_WHITE)

    # 오른쪽 벽 (관찰자 +X): 이미지 u: 왼쪽=벽 아래, 오른쪽=벽 위
    def uv_sr(y, z):
        return ((Z_T - z) / H, (y - Y_F) / D)
    b.quad([(X_R, Y_B, Z_B), (X_R, Y_F, Z_B), (X_R, Y_F, Z_T), (X_R, Y_B, Z_T)],
           M_SIDE_R, [uv_sr(Y_B, Z_B), uv_sr(Y_F, Z_B),
                      uv_sr(Y_F, Z_T), uv_sr(Y_B, Z_T)], flip=True)
    b.quad([(X_R-T, Y_B, Z_B), (X_R-T, Y_F, Z_B),
            (X_R-T, Y_F, Z_T), (X_R-T, Y_B, Z_T)], M_WHITE, flip=True)

    # 바닥 (바깥면: 표시사항 인쇄) + 안쪽 백지
    b.quad([(X_L, Y_B, Z_B), (X_R, Y_B, Z_B), (X_R, Y_F, Z_B), (X_L, Y_F, Z_B)],
           M_BOTTOM, [(0, 0), (1, 0), (1, 1), (0, 1)], flip=True)
    b.quad([(X_L, Y_F, Z_B+T), (X_R, Y_F, Z_B+T),
            (X_R, Y_B, Z_B+T), (X_L, Y_B, Z_B+T)], M_WHITE, flip=True)

    return b.to_object(mats)


def build_lid(mats):
    """뚜껑: 상판 + 앞 텅 스커트 + 옆 스커트 2. 벽보다 판지 두께만큼 바깥."""
    b = Builder("box20_lid")
    o = T + 0.2 * MM          # 몸통 바깥 간격
    zt = Z_T + o              # 상판 높이
    xl, xr = X_L - o, X_R + o
    yf, yb = Y_F - o, Y_B

    # 상판. 앞에서 내려다볼 때 글이 정방향 (글자 위쪽 = 힌지/뒤).
    # 이미지 아랫변(v=0)은 앞 스커트와 공유하는 접는선 = 앞모서리.
    b.quad([(xl, yf, zt), (xr, yf, zt), (xr, yb, zt), (xl, yb, zt)],
           M_LID_TOP, [(0, 0), (1, 0), (1, 1), (0, 1)], flip=True)
    b.quad([(xl, yf, zt - T), (xr, yf, zt - T),
            (xr, yb, zt - T), (xl, yb, zt - T)], M_WHITE)

    # 앞 텅 스커트 (바깥면 인쇄)
    z0 = zt - SKIRT * MM
    b.quad([(xl, yf, z0), (xr, yf, z0), (xr, yf, zt), (xl, yf, zt)],
           M_LID_FRONT, [(0, 0), (1, 0), (1, 1), (0, 1)], flip=True)
    b.quad([(xl, yf + T, z0), (xr, yf + T, z0),
            (xr, yf + T, zt), (xl, yf + T, zt)], M_WHITE)

    # 옆 더스트플랩: 몸통 안쪽으로 접혀 들어가는 작은 무지 플랩.
    # 바깥에서는 인쇄된 옆벽이 보여야 하므로 벽 안쪽에 배치한다.
    # 도면 실측: 뚜껑 앞모서리에서 24.1~61.8mm 구간, 깊이 37.5mm.
    fy0 = Y_F + 24.1 * MM
    fy1 = Y_F + 61.8 * MM
    for sx, m in ((-1, M_SKIRT_L), (1, M_SKIRT_R)):
        x = sx * (W / 2 - T - 0.3 * MM)
        b.quad([(x, fy0, z0), (x, fy1, z0), (x, fy1, zt), (x, fy0, zt)],
               m, [(0, 0), (1, 0), (1, 1), (0, 1)],
               flip=(sx > 0))
        xi = x - sx * T
        b.quad([(xi, fy0, z0), (xi, fy1, z0), (xi, fy1, zt), (xi, fy0, zt)],
               M_WHITE, flip=(sx < 0))

    return b.to_object(mats)


def set_lid_angle(obj, base_coords, deg):
    """힌지(뒷벽 상단, x축) 기준 절대 각도."""
    a = -math.radians(deg)
    cy, cz = Y_B, Z_T
    me = obj.data
    for v, co in zip(me.vertices, base_coords):
        y, z = co[1] - cy, co[2] - cz
        v.co.x = co[0]
        v.co.y = cy + y * math.cos(a) - z * math.sin(a)
        v.co.z = cz + y * math.sin(a) + z * math.cos(a)
    me.update()


# ---- 조명 · 카메라 · 렌더 ---------------------------------------------------

def build_studio(s):
    def area(name, loc, rot, size, energy):
        d = bpy.data.lights.new(name, type="AREA")
        d.shape = "RECTANGLE"; d.size = size[0]; d.size_y = size[1]
        d.energy = energy * LIGHT_POWER
        o = bpy.data.objects.new(name, d)
        o.location = loc; o.rotation_euler = rot
        bpy.context.collection.objects.link(o)

    area("Key",  (-0.10, -0.16, s * 1.9),
         (math.radians(48), 0, math.radians(-38)), (0.35, 0.45), 12.0)
    area("Fill", (0.18, -0.12, s * 0.7),
         (math.radians(76), 0, math.radians(56)), (0.45, 0.45), 3.5)
    area("Rim",  (0.06, 0.22, s * 1.5),
         (math.radians(122), 0, math.radians(18)), (0.28, 0.32), 8.0)

    bpy.ops.mesh.primitive_plane_add(size=1.2, location=(0, 0, -s * 0.45))
    b = bpy.context.object; b.name = "Bounce"
    m = mat_plain("BounceWhite", (1, 1, 1, 1), 0.9)
    b.data.materials.append(m)
    b.visible_camera = False


def build_camera(s):
    cd = bpy.data.cameras.new("Camera")
    cd.lens = 85
    cd.sensor_width = 36
    cam = bpy.data.objects.new("Camera", cd)
    bpy.context.collection.objects.link(cam)
    bpy.context.scene.camera = cam
    tgt = bpy.data.objects.new("CamTarget", None)
    bpy.context.collection.objects.link(tgt)
    c = cam.constraints.new("TRACK_TO")
    c.target = tgt
    c.track_axis = "TRACK_NEGATIVE_Z"
    c.up_axis = "UP_Y"
    return cam, tgt


def aim_camera(cam, tgt, s, high=False):
    if high:
        cam.location = (0, -s * 2.6, s * 1.5)
        tgt.location = (0, 0, 0)
    else:
        cam.location = (0, -s * 2.9, s * 1.0)
        tgt.location = (0, 0, -s * 0.02)


def setup_render(res, samples):
    sc = bpy.context.scene
    engines = [e.identifier for e in
               bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items]
    sc.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in engines \
        else "BLENDER_EEVEE"
    try:
        sc.eevee.taa_render_samples = samples
    except Exception:
        pass
    sc.render.resolution_x = res
    sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.render.filter_size = 1.1
    sc.render.film_transparent = True
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"
    sc.render.image_settings.color_depth = "16"
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.look = "None"


# ---- 메인 -------------------------------------------------------------------

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    print("=" * 66)
    print(f"  Zengenetics 정품 박스(20포)  |  {PRODUCT}  |  {SCRIPT_VERSION}")
    print(f"  텍스처 폴더: {TEX_DIR}")
    print(f"  출력 폴더  : {OUT_DIR}")
    print("=" * 66)

    clear_scene()
    setup_render(900, 32)

    mats = [
        mat_printed("b20_front",     load_tex(f"zen_{PRODUCT}_box20_front.png")),
        mat_printed("b20_back",      load_tex(f"zen_{PRODUCT}_box20_back.png")),
        mat_printed("b20_side_l",    load_tex(f"zen_{PRODUCT}_box20_side_l.png")),
        mat_printed("b20_side_r",    load_tex(f"zen_{PRODUCT}_box20_side_r.png")),
        mat_printed("b20_bottom",    load_tex(f"zen_{PRODUCT}_box20_bottom.png")),
        mat_printed("b20_lid_top",   load_tex(f"zen_{PRODUCT}_box20_lid_top.png")),
        mat_printed("b20_lid_front", load_tex(f"zen_{PRODUCT}_box20_lid_front.png")),
        mat_printed("b20_skirt_l",   load_tex(f"zen_{PRODUCT}_box20_lid_skirt_l.png")),
        mat_printed("b20_skirt_r",   load_tex(f"zen_{PRODUCT}_box20_lid_skirt_r.png")),
        mat_plain("b20_ivory", IVORY, 0.6),
        mat_plain("b20_white", WHITE, 0.65),
    ]

    tray = build_tray(mats)
    lid = build_lid(mats)
    parts = [tray, lid]
    lid_base = [tuple(v.co) for v in lid.data.vertices]

    size = W
    build_studio(size)
    cam, tgt = build_camera(size)
    sc = bpy.context.scene

    def shot(name, rot_z_deg):
        for o in parts:
            o.rotation_euler = (0, 0, math.radians(rot_z_deg))
        sc.render.filepath = os.path.join(OUT_DIR, name)
        bpy.ops.render.render(write_still=True)
        print(f"  저장됨: {sc.render.filepath}")

    aim_camera(cam, tgt, size, high=False)
    shot("check_box20_closed_front.png", 25)
    shot("check_box20_closed_back.png", 155)

    set_lid_angle(lid, lid_base, LID_OPEN_DEG)
    aim_camera(cam, tgt, size, high=True)
    shot("check_box20_open.png", 25)

    print("\n  3장 완료. render 폴더의 check_box20_*.png 를 확인하세요.")
    print("  괜찮으면 다음 버전에서 턴테이블 + 개봉 시퀀스로 갑니다.\n")


main()
