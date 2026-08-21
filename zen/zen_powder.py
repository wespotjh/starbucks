"""
=============================================================================
 zen_powder.py — 젠제네틱스 가루 붓기 씬 확인 렌더
=============================================================================

 ★ 아무것도 고치지 않아도 됩니다. 열어서 ▶ 만 누르세요.
   확인용 3장을 렌더합니다:
     check_powder_early.png   붓기 시작 (기울기 30도 직후)
     check_powder_mid.png     본류 (43도, 줄기 + 더미 성장)
     check_powder_end.png     붓기 끝 (더미 완성 + 착지 산포)

 실행 방법
   1. 이 파일을 zen 폴더에 넣습니다 (textures 폴더 옆)
   2. Blender 실행 → Scripting 탭 → [열기] 로 이 파일 열기 → ▶
   ※ 반드시 [열기] 로 여세요. 복사 붙여넣기 금지.

 필요한 텍스처: zen_potassium_stick_front.png / _back.png (이미 있음)

 실측 기준값 (zen_powder_motion.json)
   임계 각도 30도 시작 / 43도 본류, 흐름 2.0초
   줄기는 좁고 단단, 공중 확산 거의 없음
   낙하 거리 60mm, 흩어짐은 착지 시 (더미 지름의 2~3배)
   더미는 낮은 돔, 가루는 흰색 고운 분말 (3종 공통)

 구현: 물리 캐시를 쓰지 않고 가루알마다 포물선 궤적을 수식으로 계산.
       시드 고정이라 어느 프레임이든 결정적으로 재현됩니다.

 Blender 4.2 ~ 5.x 호환
=============================================================================
"""

import bpy
import bmesh
import math
import os
import random

PRODUCT = "potassium"
SCRIPT_VERSION = "powder-check"

# ---- 연출 값 (실측 기반) ----------------------------------------------------
FPS = 24
CLIP_SEC = 2.0            # 전체 길이
POUR_START = 0.30         # 가루가 나오기 시작하는 시각 (임계각 도달)
POUR_END = 1.80           # 붓기 끝
ANGLE_REST = 30.0         # 시작 기울기 (수평 기준)
ANGLE_POUR = 43.0         # 본류 기울기
TILT_DONE = 0.55          # 이 시각까지 30→43도 도달
DROP_MM = 60.0            # 포 입구 → 바닥 낙하 거리
V0_MMS = 110.0            # 입구에서 가루 초기 속도 (포 축 방향)
JITTER_DEG = 2.2          # 줄기 퍼짐 (작을수록 단단)
RATE = 22000.0            # 초당 가루알 수 (시각용 밀도)
GRAIN_MM = 0.42           # 가루알 반지름
PILE_R_MAX = 15.0         # 더미 최대 반지름
PILE_H_RATIO = 0.34       # 더미 높이/반지름 (낮은 돔)
SCATTER_EVERY = 36        # 착지 n알마다 1알이 주변으로 튐
SCATTER_R = 2.6           # 산포 반경 = 더미 반지름의 배수
GRAV = 9810.0             # mm/s^2

MM = 0.001
LIGHT_POWER = 0.1

# 스틱포 치수 (zen_stick 과 동일)
LENGTH, WIDTH, BULGE, SEAL_SIDE = 108.0, 24.0, 5.6, 12.0


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
    raise RuntimeError("\n\n  [열기] 버튼으로 zen_powder.py 를 직접 열어 실행하세요.\n")


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
        raise FileNotFoundError(f"\n\n  텍스처가 없습니다: {path}\n")
    img = bpy.data.images.load(path, check_existing=True)
    try:
        img.reload()
    except Exception:
        pass
    img.colorspace_settings.name = "sRGB"
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
    set_input(bsdf, "Roughness", 0.42)
    set_input(bsdf, "Metallic", 0.0)
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


POWDER = (0.94, 0.93, 0.90, 1.0)     # 흰 고운 분말 (아주 살짝 웜톤)


# ---- 스틱포 (zen_stick 단순판: 주름 없음) -----------------------------------

def build_stick(mats):
    L, W = LENGTH * MM, WIDTH * MM
    half_b = BULGE * MM * 0.5
    seal = SEAL_SIDE * MM
    nx, ny = 220, 48

    def crimp(u):
        x = u * L
        if x < seal:
            t = x / seal
        elif x > L - seal:
            t = (L - x) / seal
        else:
            return 1.0
        return 0.06 + 0.94 * (t ** 0.42)

    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    grid = []
    for i in range(nx + 1):
        u = i / nx
        c = crimp(u)
        row = []
        for j in range(ny + 1):
            ang = 2.0 * math.pi * j / ny
            ey = math.sin(ang) * half_b * c
            ez = math.cos(ang) * (W * 0.5)
            row.append(bm.verts.new((u * L - L / 2, ey, ez)))
        grid.append(row)
    for i in range(nx):
        for j in range(ny):
            try:
                f = bm.faces.new([grid[i][j], grid[i + 1][j],
                                  grid[i + 1][j + 1], grid[i][j + 1]])
            except ValueError:
                continue
            is_back = f.calc_center_median().y > 0
            f.material_index = 1 if is_back else 0
            for loop in f.loops:
                co = loop.vert.co
                uu = 0.5 + co.x / L
                vv = 0.5 + co.z / W
                if is_back:
                    uu = 1.0 - uu
                loop[uv].uv = (uu, vv)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    me = bpy.data.meshes.new("pour_stick")
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new("pour_stick", me)
    bpy.context.collection.objects.link(obj)
    for m in mats:
        obj.data.materials.append(m)
    obj.data.shade_smooth() if hasattr(obj.data, "shade_smooth") else None
    return obj


# ---- 가루 시뮬레이션 (해석적) -----------------------------------------------

def tilt_angle(t):
    """포 기울기 (도). 30도에서 43도로 부드럽게."""
    if t <= POUR_START * 0.6:
        return ANGLE_REST
    if t >= TILT_DONE:
        return ANGLE_POUR
    u = (t - POUR_START * 0.6) / (TILT_DONE - POUR_START * 0.6)
    u = u * u * (3 - 2 * u)
    return ANGLE_REST + (ANGLE_POUR - ANGLE_REST) * u


MOUTH = (0.0, 0.0, DROP_MM * MM)      # 포 입구 월드 위치 (고정)
FALL_T = math.sqrt(2 * DROP_MM / GRAV)   # 자유낙하 시간 근사


def pour_dir(t):
    a = math.radians(tilt_angle(t))
    return (-math.cos(a), 0.0, -math.sin(a))


def landing_center():
    d = pour_dir(1.0)
    vx = V0_MMS * d[0]
    return (MOUTH[0] + vx * FALL_T * MM, 0.0)


def grain_state(idx, t):
    """가루알 idx 의 시각 t 위치. None=아직/착지."""
    te = POUR_START + idx / RATE
    if te > POUR_END:
        return None
    age = t - te
    if age < 0:
        return None
    rnd = random.Random(idx * 7919 + 13)
    d = pour_dir(te)
    ja = math.radians(rnd.gauss(0, JITTER_DEG))
    jb = math.radians(rnd.gauss(0, JITTER_DEG))
    v = V0_MMS * rnd.uniform(0.85, 1.15)
    vx = v * (d[0] * math.cos(ja) - d[2] * math.sin(ja))
    vz = v * (d[0] * math.sin(ja) + d[2] * math.cos(ja))
    vy = v * math.sin(jb) * 0.6
    x = MOUTH[0] / MM + vx * age
    y = vy * age
    z = MOUTH[2] / MM + vz * age - 0.5 * GRAV * age * age
    if z <= 0.5:
        return None                    # 착지 → 더미로 흡수
    return (x * MM, y * MM, z * MM)


def landed_count(t):
    if t <= POUR_START:
        return 0
    n = int((min(t, POUR_END) - POUR_START - FALL_T) * RATE)
    return max(0, n)


def total_grains():
    return int((POUR_END - POUR_START) * RATE)


def pile_radius(t):
    frac = landed_count(t) / max(total_grains(), 1)
    return PILE_R_MAX * (frac ** (1.0 / 3.0))


def scatter_positions(t):
    """착지 시 튄 알갱이들 (누적, 결정적)."""
    n = landed_count(t) // SCATTER_EVERY
    cx, cy = landing_center()
    out = []
    for k in range(n):
        rnd = random.Random(k * 104729 + 7)
        rr = pile_radius(POUR_START + (k * SCATTER_EVERY) / RATE + FALL_T)
        rr = max(rr, 2.0)
        dist = rr * (1.15 + (SCATTER_R - 1.15) * rnd.random() ** 2.2)
        az = rnd.uniform(0, 2 * math.pi)
        out.append((cx + dist * math.cos(az) * MM,
                    cy + dist * math.sin(az) * MM,
                    GRAIN_MM * MM))
    return out


# ---- 씬 요소 ----------------------------------------------------------------

def make_grain_cloud(name, positions, grain_r, mat):
    """점 메시 + 버텍스 인스턴스로 가루알 무리를 만든다."""
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(p) for p in positions], [], [])
    holder = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(holder)

    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=grain_r)
    ball = bpy.context.object
    ball.name = name + "_ball"
    ball.data.materials.append(mat)
    ball.parent = holder
    holder.instance_type = 'VERTS'
    ball.hide_render = False
    return holder


def make_pile(radius_mm, mat):
    cx, cy = landing_center()
    bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, radius=1.0)
    pile = bpy.context.object
    pile.name = "pile"
    r = max(radius_mm, 0.001) * MM
    pile.scale = (r, r, r * PILE_H_RATIO)
    pile.location = (cx, cy, 0.0)
    pile.data.materials.append(mat)
    try:
        bpy.ops.object.shade_smooth()
    except Exception:
        pass
    return pile


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

    # 바닥: 밝은 무광 화이트 (보이는 표면)
    bpy.ops.mesh.primitive_plane_add(size=1.0, location=(0, 0, 0))
    g = bpy.context.object; g.name = "Ground"
    g.data.materials.append(mat_plain("GroundWhite", (0.97, 0.97, 0.96, 1), 0.8))


def build_camera(s):
    cd = bpy.data.cameras.new("Camera")
    cd.lens = 85
    cd.sensor_width = 36
    cam = bpy.data.objects.new("Camera", cd)
    bpy.context.collection.objects.link(cam)
    bpy.context.scene.camera = cam
    cam.location = (0.02, -s * 2.6, s * 0.75)
    tgt = bpy.data.objects.new("CamTarget", None)
    bpy.context.collection.objects.link(tgt)
    tgt.location = (-0.01, 0, s * 0.35)
    c = cam.constraints.new("TRACK_TO")
    c.target = tgt
    c.track_axis = "TRACK_NEGATIVE_Z"
    c.up_axis = "UP_Y"


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
    sc.render.film_transparent = False      # 바닥이 보이는 씬
    sc.render.use_motion_blur = False
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"
    sc.render.image_settings.color_depth = "16"
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.look = "None"


def place_stick(obj, t):
    """포 입구(-x 끝)가 MOUTH 에 고정되도록 기울여 배치."""
    a = math.radians(tilt_angle(t))
    obj.rotation_euler = (0, -a, 0)
    mx = -LENGTH * MM / 2
    # 회전 후 입구 로컬(-L/2,0,0) 의 월드 오프셋
    ox = mx * math.cos(a)
    oz = mx * math.sin(a)
    obj.location = (MOUTH[0] - ox, 0.0, MOUTH[2] - oz)


# ---- 프레임 구성 ------------------------------------------------------------

def build_frame_scene(t, mats_stick, mat_powder):
    """시각 t 의 장면을 조립한다 (가루/더미는 매번 새로)."""
    for name in ("grains", "grains_ball", "scatter", "scatter_ball", "pile"):
        o = bpy.data.objects.get(name)
        if o:
            bpy.data.objects.remove(o, do_unlink=True)

    stick = bpy.data.objects.get("pour_stick") or build_stick(mats_stick)
    place_stick(stick, t)

    n_air = int(RATE * FALL_T * 1.4)
    first = max(0, int((t - POUR_START - FALL_T * 1.3) * RATE))
    positions = []
    for i in range(first, first + n_air * 2):
        p = grain_state(i, t)
        if p:
            positions.append(p)
    if positions:
        make_grain_cloud("grains", positions, GRAIN_MM * MM, mat_powder)

    sc = scatter_positions(t)
    if sc:
        make_grain_cloud("scatter", sc, GRAIN_MM * MM * 1.15, mat_powder)

    r = pile_radius(t)
    if r > 0.3:
        make_pile(r, mat_powder)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    print("=" * 66)
    print(f"  Zengenetics 가루 붓기  |  {PRODUCT}  |  {SCRIPT_VERSION}")
    print(f"  출력 폴더: {OUT_DIR}")
    print("=" * 66)

    clear_scene()
    setup_render(900, 32)

    mats_stick = [
        mat_printed("ps_front", load_tex(f"zen_{PRODUCT}_stick_front.png")),
        mat_printed("ps_back",  load_tex(f"zen_{PRODUCT}_stick_back.png")),
    ]
    mat_powder = mat_plain("powder", POWDER, 0.92)

    build_studio(0.12)
    build_camera(0.12)
    sc = bpy.context.scene

    shots = [("check_powder_early.png", 0.55),
             ("check_powder_mid.png",   1.20),
             ("check_powder_end.png",   2.00)]
    for name, t in shots:
        build_frame_scene(t, mats_stick, mat_powder)
        sc.render.filepath = os.path.join(OUT_DIR, name)
        bpy.ops.render.render(write_still=True)
        print(f"  저장됨: {sc.render.filepath}  (t={t:.2f}s, 기울기 {tilt_angle(t):.0f}도)")

    print("\n  3장 완료. render 폴더의 check_powder_*.png 를 확인하세요.")
    print("  확인 포인트: 줄기 굵기/직진성, 더미 크기와 낮은 돔 모양, 착지 산포.")
    print("  괜찮으면 다음 버전에서 48프레임 시퀀스로 갑니다.\n")


main()
