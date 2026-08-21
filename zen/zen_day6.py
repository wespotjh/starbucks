"""
=============================================================================
 zen_day6.py — 젠제네틱스 데이팩(6포) 플립톱 박스 확인 렌더
=============================================================================

 ★ 아무것도 고치지 않아도 됩니다. 열어서 ▶ 만 누르세요.
   확인용 3장을 렌더합니다:
     check_day6_closed_front.png   닫힌 상태 앞 3/4
     check_day6_closed_back.png    닫힌 상태 뒤 3/4
     check_day6_open140.png        뚜껑 140도 개봉 + 이너프레임

 실행 방법
   1. 이 파일을 zen 폴더에 넣습니다 (textures 폴더 옆)
   2. Blender 실행 → Scripting 탭 → [열기] 로 이 파일 열기 → ▶
   ※ 복사 붙여넣기 하면 경로를 못 찾습니다. 반드시 [열기] 로 여세요.

 필요한 텍스처 (zen/textures/)
   zen_potassium_day6_front.png / _back.png / _left.png / _right.png
   zen_potassium_day6_lid_top.png
   (bottom / inner 는 무지라 텍스처 없이 재질로 처리)

 구조 실측값 (도면 벡터에서 추출 — zen_day6_panels.json)
   박스 50 x 20 x 116 mm, 300로얄아이보리 벨벳코팅
   플립톱: 앞 절취선 상단 23.3mm / 뒤 힌지 상단 13.1mm / 옆은 대각 연결
   이너프레임: 폭 49, 높이 96.9, 곡선 노치, 몸통 위 돌출 9mm(추정)
   개봉 최대 각도 140도 (실물 영상 실측)

 Blender 4.2 ~ 5.x 호환
=============================================================================
"""

import bpy
import bmesh
import math
import os

PRODUCT = "potassium"
SCRIPT_VERSION = "day6-check"

# ---- 치수 (mm) --------------------------------------------------------------
BOX_W = 50.0     # 가로 (x)
BOX_D = 20.0     # 깊이 (y)
BOX_H = 116.0    # 높이 (z)
TEAR_FRONT = 23.3    # 앞면 절취선: 상단에서
HINGE_BACK = 13.1    # 뒷면 힌지: 상단에서
CARD_T = 0.4         # 판지 두께
INNER_W = 49.0
INNER_H = 96.9
INNER_PROUD = 9.0    # 이너프레임이 몸통 절취선 위로 올라온 높이 (실물 미확정, 통상치)
NOTCH_W = 24.0       # 이너프레임 곡선 노치 폭
NOTCH_D = 6.0        # 노치 깊이
LID_OPEN_DEG = 140.0

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
        "  Blender 스크립팅함에서 [열기] 버튼으로 zen_day6.py 를\n"
        "  직접 열어서 실행해 주세요. (복사 붙여넣기 말고요)\n")


BASE_DIR = _base_dir()
TEX_DIR = os.path.join(BASE_DIR, "textures")
OUT_DIR = os.path.join(BASE_DIR, "render")


# ---- 공용 유틸 (zen_stick 과 동일) ------------------------------------------

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
            f"  zen/textures 폴더에 데이팩 텍스처 8장이 있는지 확인하세요.\n")
    img = bpy.data.images.load(path, check_existing=True)
    try:
        img.reload()
    except Exception:
        pass
    img.colorspace_settings.name = "sRGB"
    print(f"  텍스처 로드: {filename}  ({img.size[0]} x {img.size[1]} px)")
    return img


def mat_printed(name, image):
    """인쇄면: 아이보리 판지 + 벨벳코팅 → 매트하고 부드러운 반사."""
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

Z_TOP = H / 2
Z_BOT = -H / 2
Y_F = -D / 2          # 앞면
Y_B = D / 2           # 뒷면
X_L = -W / 2
X_R = W / 2
Z_TEAR_F = Z_TOP - TEAR_FRONT * MM   # 앞 절취선 높이
Z_HINGE = Z_TOP - HINGE_BACK * MM    # 뒤 힌지 높이

# 머티리얼 인덱스
M_FRONT, M_BACK, M_LEFT, M_RIGHT, M_TOP, M_IVORY, M_WHITE = range(7)

IVORY = (0.93, 0.91, 0.85, 1.0)   # 300 로얄아이보리 단면/내면
WHITE = (0.96, 0.96, 0.95, 1.0)


def z_side_tear(y):
    """옆면 절취선 높이: 앞(23.3mm)에서 뒤 힌지(13.1mm)로 대각선."""
    t = (y - Y_F) / D
    return Z_TEAR_F + t * (Z_HINGE - Z_TEAR_F)


class Builder:
    def __init__(self, name):
        self.bm = bmesh.new()
        self.uv = self.bm.loops.layers.uv.new("UVMap")
        self.name = name

    def quad(self, pts, mat, uvs=None, flip=False):
        """pts: 4개 (x,y,z) 튜플. uvs: 대응하는 4개 (u,v). flip: 법선 뒤집기."""
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

    def poly(self, pts, mat, flip=False):
        vs = [self.bm.verts.new(p) for p in pts]
        if flip:
            vs = list(reversed(vs))
        try:
            f = self.bm.faces.new(vs)
            f.material_index = mat
        except ValueError:
            pass

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


def uv_front(z0, z1):
    """앞/뒤 텍스처는 패널 전체(116mm)라 z 위치를 v 로 환산."""
    v0 = (z0 - Z_BOT) / H
    v1 = (z1 - Z_BOT) / H
    return v0, v1


def build_body(mats):
    b = Builder("day6_body")

    # 앞면 몸통 (절취선 아래). 관찰자(-Y)에게 x- 가 왼쪽 → u=(x-X_L)/W
    v0, v1 = uv_front(Z_BOT, Z_TEAR_F)
    b.quad([(X_L, Y_F, Z_BOT), (X_R, Y_F, Z_BOT),
            (X_R, Y_F, Z_TEAR_F), (X_L, Y_F, Z_TEAR_F)],
           M_FRONT, [(0, v0), (1, v0), (1, v1), (0, v1)], flip=True)
    # 앞면 안쪽 (백지)
    b.quad([(X_L, Y_F + T, Z_BOT), (X_R, Y_F + T, Z_BOT),
            (X_R, Y_F + T, Z_TEAR_F), (X_L, Y_F + T, Z_TEAR_F)],
           M_WHITE)

    # 뒷면 몸통 (힌지 아래). 뒤(+Y)에서 보면 x+ 가 왼쪽 → u=(X_R-x)/W
    v0, v1 = uv_front(Z_BOT, Z_HINGE)
    b.quad([(X_R, Y_B, Z_BOT), (X_L, Y_B, Z_BOT),
            (X_L, Y_B, Z_HINGE), (X_R, Y_B, Z_HINGE)],
           M_BACK, [(0, v0), (1, v0), (1, v1), (0, v1)], flip=True)
    b.quad([(X_R, Y_B - T, Z_BOT), (X_L, Y_B - T, Z_BOT),
            (X_L, Y_B - T, Z_HINGE), (X_R, Y_B - T, Z_HINGE)],
           M_WHITE, flip=True)

    # 왼쪽 몸통 (x=X_L), 절취선 대각. 관찰자(-X)에게 앞(y-)이 오른쪽 → u=(Y_B-y)/D
    zf, zb = z_side_tear(Y_F), z_side_tear(Y_B)
    b.quad([(X_L, Y_F, Z_BOT), (X_L, Y_B, Z_BOT),
            (X_L, Y_B, zb), (X_L, Y_F, zf)],
           M_LEFT,
           [((Y_B - Y_F) / D, (Z_BOT - Z_BOT) / H), (0, 0),
            (0, (zb - Z_BOT) / H), (1, (zf - Z_BOT) / H)], flip=True)
    b.quad([(X_L + T, Y_F, Z_BOT), (X_L + T, Y_B, Z_BOT),
            (X_L + T, Y_B, zb), (X_L + T, Y_F, zf)],
           M_WHITE)

    # 오른쪽 몸통 (x=X_R). 관찰자(+X)에게 앞(y-)이 왼쪽 → u=(y-Y_F)/D
    b.quad([(X_R, Y_B, Z_BOT), (X_R, Y_F, Z_BOT),
            (X_R, Y_F, zf), (X_R, Y_B, zb)],
           M_RIGHT,
           [(1, 0), (0, 0), (0, (zf - Z_BOT) / H), (1, (zb - Z_BOT) / H)],
           flip=True)
    b.quad([(X_R - T, Y_B, Z_BOT), (X_R - T, Y_F, Z_BOT),
            (X_R - T, Y_F, zf), (X_R - T, Y_B, zb)],
           M_WHITE, flip=True)

    # 바닥
    b.quad([(X_L, Y_F, Z_BOT), (X_R, Y_F, Z_BOT),
            (X_R, Y_B, Z_BOT), (X_L, Y_B, Z_BOT)], M_IVORY)

    return b.to_object(mats)


def build_lid(mats):
    b = Builder("day6_lid")
    zf, zb = z_side_tear(Y_F), z_side_tear(Y_B)

    # 앞면 뚜껑 (절취선 위)
    v0, v1 = uv_front(Z_TEAR_F, Z_TOP)
    b.quad([(X_L, Y_F, Z_TEAR_F), (X_R, Y_F, Z_TEAR_F),
            (X_R, Y_F, Z_TOP), (X_L, Y_F, Z_TOP)],
           M_FRONT, [(0, v0), (1, v0), (1, v1), (0, v1)], flip=True)
    b.quad([(X_L, Y_F + T, Z_TEAR_F), (X_R, Y_F + T, Z_TEAR_F),
            (X_R, Y_F + T, Z_TOP), (X_L, Y_F + T, Z_TOP)],
           M_WHITE)

    # 뒷면 뚜껑 (힌지 위)
    v0, v1 = uv_front(Z_HINGE, Z_TOP)
    b.quad([(X_R, Y_B, Z_HINGE), (X_L, Y_B, Z_HINGE),
            (X_L, Y_B, Z_TOP), (X_R, Y_B, Z_TOP)],
           M_BACK, [(0, v0), (1, v0), (1, v1), (0, v1)], flip=True)
    b.quad([(X_R, Y_B - T, Z_HINGE), (X_L, Y_B - T, Z_HINGE),
            (X_L, Y_B - T, Z_TOP), (X_R, Y_B - T, Z_TOP)],
           M_WHITE, flip=True)

    # 옆면 뚜껑 (대각 아랫변)
    b.quad([(X_L, Y_F, zf), (X_L, Y_B, zb),
            (X_L, Y_B, Z_TOP), (X_L, Y_F, Z_TOP)],
           M_LEFT,
           [(1, (zf - Z_BOT) / H), (0, (zb - Z_BOT) / H), (0, 1), (1, 1)],
           flip=True)
    b.quad([(X_L + T, Y_F, zf), (X_L + T, Y_B, zb),
            (X_L + T, Y_B, Z_TOP), (X_L + T, Y_F, Z_TOP)],
           M_WHITE)
    b.quad([(X_R, Y_B, zb), (X_R, Y_F, zf),
            (X_R, Y_F, Z_TOP), (X_R, Y_B, Z_TOP)],
           M_RIGHT,
           [(1, (zb - Z_BOT) / H), (0, (zf - Z_BOT) / H), (0, 1), (1, 1)],
           flip=True)
    b.quad([(X_R - T, Y_B, zb), (X_R - T, Y_F, zf),
            (X_R - T, Y_F, Z_TOP), (X_R - T, Y_B, Z_TOP)],
           M_WHITE, flip=True)

    # 상판 (주황 플랩). 앞에서 봤을 때 글자가 바로 읽히는 방향.
    b.quad([(X_L, Y_F, Z_TOP), (X_R, Y_F, Z_TOP),
            (X_R, Y_B, Z_TOP), (X_L, Y_B, Z_TOP)],
           M_TOP, [(0, 0), (1, 0), (1, 1), (0, 1)], flip=True)
    b.quad([(X_L, Y_F, Z_TOP - T), (X_R, Y_F, Z_TOP - T),
            (X_R, Y_B, Z_TOP - T), (X_L, Y_B, Z_TOP - T)],
           M_WHITE)

    obj = b.to_object(mats)
    return obj


def build_inner(mats):
    """이너프레임: 앞판(곡선 노치) + 좌우 날개. 무인쇄 백색."""
    b = Builder("day6_inner")
    yi = Y_F + T + 0.2 * MM              # 앞판 바로 안쪽
    top = Z_TEAR_F + INNER_PROUD * MM    # 몸통 절취선 위로 돌출
    bot = top - INNER_H * MM
    xw = INNER_W * MM / 2

    # 앞판: 상단 가운데 코사인 노치
    seg = 40
    top_edge = []
    for i in range(seg + 1):
        x = -xw + (2 * xw) * i / seg
        dip = 0.0
        if abs(x) < NOTCH_W * MM / 2:
            dip = NOTCH_D * MM * 0.5 * (1 + math.cos(2 * math.pi * x / (NOTCH_W * MM)))
        top_edge.append((x, yi, top - dip))
    pts = [(-xw, yi, bot), (xw, yi, bot)] + list(reversed(top_edge))
    b.poly(pts, M_WHITE, flip=True)
    # 뒷면(안쪽에서 보이는 면)
    pts2 = [(p[0], yi + T, p[2]) for p in pts]
    b.poly(pts2, M_WHITE)

    # 좌우 날개 (안쪽 벽에 붙어 뒤로)
    for sx, depth in ((-1, 16.0), (1, 13.5)):
        x = sx * (W / 2 - T - 0.2 * MM)
        y1 = yi + depth * MM
        b.quad([(x, yi, bot), (x, y1, bot),
                (x, y1, top - 5 * MM), (x, yi, top)],
               M_WHITE)
        b.quad([(x - sx * T, yi, bot), (x - sx * T, y1, bot),
                (x - sx * T, y1, top - 5 * MM), (x - sx * T, yi, top)],
               M_WHITE, flip=True)

    return b.to_object(mats)


def open_lid(obj, deg):
    """힌지(뒤 상단 모서리, x축)를 중심으로 뚜껑을 뒤로 젖힌다."""
    a = -math.radians(deg)
    cy, cz = Y_B, Z_HINGE
    me = obj.data
    for v in me.vertices:
        y, z = v.co.y - cy, v.co.z - cz
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

    bpy.ops.mesh.primitive_plane_add(size=1.2, location=(0, 0, -s * 0.75))
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
    cam.location = (0, -s * 3.2, s * 0.35)
    tgt = bpy.data.objects.new("CamTarget", None)
    bpy.context.collection.objects.link(tgt)
    tgt.location = (0, 0, 0)
    c = cam.constraints.new("TRACK_TO")
    c.target = tgt
    c.track_axis = "TRACK_NEGATIVE_Z"
    c.up_axis = "UP_Y"
    return cam


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
    print(f"  Zengenetics 데이팩(6포)  |  {PRODUCT}  |  {SCRIPT_VERSION}")
    print(f"  텍스처 폴더: {TEX_DIR}")
    print(f"  출력 폴더  : {OUT_DIR}")
    print("=" * 66)

    clear_scene()
    setup_render(900, 32)

    mats = [
        mat_printed("day6_front",  load_tex(f"zen_{PRODUCT}_day6_front.png")),
        mat_printed("day6_back",   load_tex(f"zen_{PRODUCT}_day6_back.png")),
        mat_printed("day6_left",   load_tex(f"zen_{PRODUCT}_day6_left.png")),
        mat_printed("day6_right",  load_tex(f"zen_{PRODUCT}_day6_right.png")),
        mat_printed("day6_top",    load_tex(f"zen_{PRODUCT}_day6_lid_top.png")),
        mat_plain("day6_ivory", IVORY, 0.6),
        mat_plain("day6_white", WHITE, 0.65),
    ]

    body = build_body(mats)
    lid = build_lid(mats)
    inner = build_inner(mats)
    parts = [body, lid, inner]

    size = H
    build_studio(size)
    build_camera(size)
    sc = bpy.context.scene

    def shot(name, rot_z_deg):
        for o in parts:
            o.rotation_euler = (0, 0, math.radians(rot_z_deg))
        sc.render.filepath = os.path.join(OUT_DIR, name)
        bpy.ops.render.render(write_still=True)
        print(f"  저장됨: {sc.render.filepath}")

    # 1) 닫힌 앞 3/4     2) 닫힌 뒤 3/4
    shot("check_day6_closed_front.png", 25)
    shot("check_day6_closed_back.png", 155)

    # 3) 뚜껑 140도 개봉
    open_lid(lid, LID_OPEN_DEG)
    shot("check_day6_open140.png", 25)

    print("\n  3장 완료. render 폴더의 check_day6_*.png 를 확인하세요.")
    print("  괜찮으면 다음 버전에서 턴테이블 시퀀스로 갑니다.\n")


main()
