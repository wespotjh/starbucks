"""
=============================================================================
 zen_powder.py — 젠제네틱스 가루 붓기 씬 v2 (연출 컷)
=============================================================================

 ★ 아무것도 고치지 않아도 됩니다. 열어서 ▶ 만 누르세요.
   확인용 3장을 렌더합니다:
     check_powder_early.png / _mid.png / _end.png

 목표 연출 (레퍼런스 이미지 기준)
   - 뜯어진 스틱포가 오른쪽 아래로 기울어 붓는 구도
   - 곱고 촘촘한 분말 줄기 (안개 낀 듯한 미세 입자 포함)
   - 원뿔형으로 쌓이는 가루 산, 표면은 입자 질감
   - 어두운 배경 + 스포트라이트

 실측 물리값 (zen_powder_motion.json)
   기울기 30→45도, 흐름 2.0초, 좁은 줄기, 낙하 60mm, 착지 산포

 구현: 물리 캐시 없이 가루알별 포물선 궤적을 시드 고정 수식으로 계산.
 Blender 4.2 ~ 5.x 호환
=============================================================================
"""

import bpy
import bmesh
import math
import os
import random

PRODUCT = "potassium"
SCRIPT_VERSION = "powder-v3"

# ---- 연출 값 ---------------------------------------------------------------
FPS = 24
CLIP_SEC = 2.0
POUR_START = 0.30
POUR_END = 1.80
ANGLE_REST = 30.0
ANGLE_POUR = 45.0
TILT_DONE = 0.55
DROP_MM = 62.0
V0_MMS = 110.0
JITTER_DEG = 2.0          # 줄기 코어 퍼짐
MIST_JITTER = 6.5         # 미세 안개 입자 퍼짐
RATE = 60000.0            # 초당 코어 입자
MIST_RATE = 9000.0        # 초당 안개 입자
GRAIN_MM = 0.24           # 고운 분말
PILE_R_MAX = 17.0         # 가루 산 바닥 반지름
PILE_H_RATIO = 0.62       # 원뿔 높이/반지름
SCATTER_EVERY = 55
SCATTER_R = 2.4
GRAV = 9810.0

MM = 0.001
LENGTH, WIDTH, BULGE, SEAL_SIDE = 108.0, 24.0, 5.6, 12.0
TORN_MM = 10.0            # 뜯겨나간 길이 (입구 쪽)


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
    set_input(bsdf, "Roughness", 0.40)
    set_input(bsdf, "Metallic", 0.0)
    set_input(bsdf, ["Specular IOR Level", "Specular"], 0.45)
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat


def mat_plain(name, color, rough=0.6, metal=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = principled_of(mat)
    set_input(bsdf, "Base Color", color)
    set_input(bsdf, "Roughness", rough)
    set_input(bsdf, "Metallic", metal)
    return mat


POWDER = (0.84, 0.83, 0.80, 1.0)


# ---- 스틱포 (뜯어진 입구, 오른쪽으로 붓는 방향) ------------------------------

def build_stick(mats):
    """입구(+x 끝)가 뜯겨 열린 스틱포. 재질: 0 앞면, 1 뒷면, 2 은지 절단면."""
    L_full = LENGTH * MM
    L = (LENGTH - TORN_MM) * MM        # 뜯긴 후 길이
    W = WIDTH * MM
    half_b = BULGE * MM * 0.5
    seal = SEAL_SIDE * MM
    nx, ny = 220, 48

    def crimp(x):
        # 왼쪽(봉합) 끝만 크림프. 오른쪽은 뜯긴 입구라 부풀어 있음.
        if x < seal:
            t = x / seal
            return 0.06 + 0.94 * (t ** 0.42)
        if x > L - 3 * MM:
            t = (L - x) / (3 * MM)
            return 0.75 + 0.25 * t      # 입구 살짝 오므라듦
        return 1.0

    rnd = random.Random(42)
    tear = [1.0 + 0.5 * rnd.uniform(-1, 1) for _ in range(ny + 1)]  # 절단면 들쭉날쭉

    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    grid = []
    for i in range(nx + 1):
        u = i / nx
        x = u * L
        if i == nx:                     # 입구 끝: 찢긴 가장자리
            pass
        c = crimp(x)
        row = []
        for j in range(ny + 1):
            ang = 2.0 * math.pi * j / ny
            xx = x
            if i == nx:
                xx = L + tear[j] * 1.5 * MM   # 지그재그 절단면
            ey = math.sin(ang) * half_b * c
            ez = math.cos(ang) * (W * 0.5)
            row.append(bm.verts.new((xx - L_full / 2, ey, ez)))
        grid.append(row)
    for i in range(nx):
        for j in range(ny):
            try:
                f = bm.faces.new([grid[i][j], grid[i + 1][j],
                                  grid[i + 1][j + 1], grid[i][j + 1]])
            except ValueError:
                continue
            if i >= nx - 2:
                f.material_index = 2            # 절단면 은색 띠
            else:
                is_back = f.calc_center_median().y > 0
                f.material_index = 1 if is_back else 0
            for loop in f.loops:
                co = loop.vert.co
                uu = 0.5 + co.x / L_full
                vv = 0.5 + co.z / W
                if f.material_index == 1:
                    uu = 1.0 - uu
                loop[uv].uv = (uu, vv)
    # 왼쪽 끝 막기
    try:
        f = bm.faces.new([grid[0][j] for j in range(ny)])
        f.material_index = 2
    except ValueError:
        pass
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    me = bpy.data.meshes.new("pour_stick")
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new("pour_stick", me)
    bpy.context.collection.objects.link(obj)
    for m in mats:
        obj.data.materials.append(m)
    try:
        me.shade_smooth()
    except Exception:
        pass
    return obj, L


# ---- 가루 시뮬레이션 (해석적) -----------------------------------------------

MOUTH = (0.0, 0.0, DROP_MM * MM)
FALL_T = math.sqrt(2 * DROP_MM / GRAV)


def tilt_angle(t):
    if t <= POUR_START * 0.6:
        return ANGLE_REST
    if t >= TILT_DONE:
        return ANGLE_POUR
    u = (t - POUR_START * 0.6) / (TILT_DONE - POUR_START * 0.6)
    u = u * u * (3 - 2 * u)
    return ANGLE_REST + (ANGLE_POUR - ANGLE_REST) * u


def pour_dir(t):
    a = math.radians(tilt_angle(t))
    return (math.cos(a), 0.0, -math.sin(a))     # 오른쪽 아래로


def landing_center():
    d = pour_dir(1.0)
    return (MOUTH[0] + d[0] * V0_MMS * FALL_T * MM, 0.0)


def grain_pos(idx, t, rate, jitter_deg, salt):
    te = POUR_START + idx / rate
    if te > POUR_END:
        return None
    age = t - te
    if age < 0:
        return None
    rnd = random.Random(idx * 7919 + salt)
    d = pour_dir(te)
    ja = math.radians(rnd.gauss(0, jitter_deg))
    jb = math.radians(rnd.gauss(0, jitter_deg))
    v = V0_MMS * rnd.uniform(0.82, 1.18)
    vx = v * (d[0] * math.cos(ja) - d[2] * math.sin(ja))
    vz = v * (d[0] * math.sin(ja) + d[2] * math.cos(ja))
    vy = v * math.sin(jb) * 0.6
    x = MOUTH[0] / MM + vx * age
    y = vy * age
    z = MOUTH[2] / MM + vz * age - 0.5 * GRAV * age * age
    if z <= 0.5:
        return None
    return (x * MM, y * MM, z * MM)


def cloud_positions(t, rate, jitter_deg, salt):
    n_win = int(rate * FALL_T * 2.0)
    first = max(0, int((t - POUR_START - FALL_T * 1.4) * rate))
    out = []
    for i in range(first, first + n_win):
        p = grain_pos(i, t, rate, jitter_deg, salt)
        if p:
            out.append(p)
    return out


def landed_count(t):
    if t <= POUR_START + FALL_T:
        return 0
    return max(0, int((min(t, POUR_END + FALL_T) - POUR_START - FALL_T) * RATE))


def total_grains():
    return int((POUR_END - POUR_START) * RATE)


def pile_radius(t):
    frac = landed_count(t) / max(total_grains(), 1)
    return PILE_R_MAX * (frac ** (1.0 / 3.0))


def scatter_positions(t):
    n = landed_count(t) // SCATTER_EVERY
    cx, cy = landing_center()
    out = []
    for k in range(n):
        rnd = random.Random(k * 104729 + 7)
        rr = max(pile_radius(POUR_START + (k * SCATTER_EVERY) / RATE + FALL_T), 2.0)
        dist = rr * (1.1 + (SCATTER_R - 1.1) * rnd.random() ** 2.4)
        az = rnd.uniform(0, 2 * math.pi)
        out.append((cx + dist * math.cos(az) * MM,
                    cy + dist * math.sin(az) * MM,
                    GRAIN_MM * MM))
    return out


def pile_surface_grains(t):
    """원뿔 표면에 뿌려진 입자들 — 가루 산의 질감."""
    r = pile_radius(t)
    if r < 1.0:
        return []
    cx, cy = landing_center()
    h = r * PILE_H_RATIO
    n = int(60 * r)
    out = []
    for k in range(n):
        rnd = random.Random(k * 65537 + 3)
        u = math.sqrt(rnd.random())
        az = rnd.uniform(0, 2 * math.pi)
        rr = r * u
        zz = h * (1 - u) + rnd.uniform(0, 0.35)
        out.append((cx + rr * math.cos(az) * MM,
                    cy + rr * math.sin(az) * MM,
                    zz * MM))
    return out


# ---- 씬 요소 ----------------------------------------------------------------

def make_grain_cloud(name, positions, grain_r, mat):
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
    return holder


def make_pile(t, mat):
    """노이즈로 표면을 흔든 원뿔 가루 산."""
    r = pile_radius(t)
    if r < 0.5:
        return None
    cx, cy = landing_center()
    h = r * PILE_H_RATIO
    bm = bmesh.new()
    seg, rings = 64, 14
    ring_verts = []
    rnd = random.Random(99)
    noise = [[rnd.uniform(-1, 1) for _ in range(seg)] for _ in range(rings + 1)]
    for ri in range(rings + 1):
        u = ri / rings                    # 0=꼭대기, 1=바닥
        rr = r * u
        zz = h * (1 - u) ** 1.15          # 살짝 볼록한 원뿔
        row = []
        for si in range(seg):
            az = 2 * math.pi * si / seg
            nz = noise[ri][si] * 0.06 * r * u
            row.append(bm.verts.new(((cx + (rr + nz) * math.cos(az) * MM),
                                     (cy + (rr + nz) * math.sin(az) * MM),
                                     max(zz + noise[ri][(si * 7) % seg] * 0.4, 0.05) * MM)))
        ring_verts.append(row)
    top = bm.verts.new((cx * 1.0, cy * 1.0, h * MM))
    for si in range(seg):
        bm.faces.new([top, ring_verts[0][si], ring_verts[0][(si + 1) % seg]])
    for ri in range(rings):
        for si in range(seg):
            bm.faces.new([ring_verts[ri][si], ring_verts[ri + 1][si],
                          ring_verts[ri + 1][(si + 1) % seg], ring_verts[ri][(si + 1) % seg]])
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    me = bpy.data.meshes.new("pile")
    bm.to_mesh(me)
    bm.free()
    pile = bpy.data.objects.new("pile", me)
    bpy.context.collection.objects.link(pile)
    pile.data.materials.append(mat)
    try:
        me.shade_smooth()
    except Exception:
        pass
    return pile


def build_studio():
    """어두운 배경 + 스포트라이트 무드."""
    w = bpy.context.scene.world or bpy.data.worlds.new("World")
    bpy.context.scene.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.015, 0.014, 0.013, 1)
        bg.inputs[1].default_value = 1.0

    def light(kind, name, loc, rot, energy, size=0.3, color=(1, 0.98, 0.95)):
        d = bpy.data.lights.new(name, type=kind)
        d.energy = energy
        d.color = color
        if kind == "AREA":
            d.size = size
        if kind == "SPOT":
            d.spot_size = math.radians(55)
            d.spot_blend = 0.6
            d.shadow_soft_size = 0.09
        o = bpy.data.objects.new(name, d)
        o.location = loc
        o.rotation_euler = rot
        bpy.context.collection.objects.link(o)

    # 키 스포트 (위 오른쪽에서 더미를 향해)
    light("SPOT", "KeySpot", (0.10, -0.14, 0.30),
          (math.radians(28), math.radians(18), math.radians(15)), 4.5)
    # 뒤 백라이트: 가루 줄기가 빛나 보이게
    light("AREA", "Back", (0.02, 0.20, 0.16),
          (math.radians(115), 0, 0), 0.9, size=0.35)
    # 약한 필
    light("AREA", "Fill", (-0.16, -0.12, 0.10),
          (math.radians(75), 0, math.radians(-45)), 0.35, size=0.4)

    # 바닥: 짙은 무광 (스포트라이트 웅덩이가 생김)
    bpy.ops.mesh.primitive_plane_add(size=5.0, location=(0, 0.6, 0))
    g = bpy.context.object
    g.name = "Ground"
    g.data.materials.append(mat_plain("GroundDark", (0.050, 0.045, 0.040, 1), 0.9))


def build_camera():
    cd = bpy.data.cameras.new("Camera")
    cd.lens = 85
    cd.sensor_width = 36
    cam = bpy.data.objects.new("Camera", cd)
    bpy.context.collection.objects.link(cam)
    bpy.context.scene.camera = cam
    cam.location = (0.012, -0.34, 0.072)
    tgt = bpy.data.objects.new("CamTarget", None)
    bpy.context.collection.objects.link(tgt)
    tgt.location = (0.012, 0, 0.052)
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
    sc.render.resolution_y = int(res * 1.25)     # 세로 구도
    sc.render.resolution_percentage = 100
    sc.render.filter_size = 1.1
    sc.render.film_transparent = False
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"
    sc.render.image_settings.color_depth = "16"
    try:
        sc.view_settings.view_transform = "Filmic"   # 하이라이트 부드럽게
    except Exception:
        sc.view_settings.view_transform = "Standard"
    sc.view_settings.look = "None"


def place_stick(obj, L_torn, t):
    """뜯긴 입구(+끝)가 MOUTH 에 오도록 기울여 배치."""
    a = math.radians(tilt_angle(t))
    obj.rotation_euler = (0, a, 0)
    mx = L_torn - LENGTH * MM / 2      # 입구 로컬 x
    ox = mx * math.cos(a)
    oz = -mx * math.sin(a)
    obj.location = (MOUTH[0] - ox, 0.0, MOUTH[2] - oz)


# ---- 프레임 구성 ------------------------------------------------------------

def build_frame_scene(t, stick, L_torn, mat_powder):
    for name in ("grains", "grains_ball", "mist", "mist_ball",
                 "scatter", "scatter_ball", "psurf", "psurf_ball", "pile"):
        o = bpy.data.objects.get(name)
        if o:
            me = o.data
            bpy.data.objects.remove(o, do_unlink=True)
            try:
                if me and me.users == 0:
                    bpy.data.meshes.remove(me)
            except Exception:
                pass

    place_stick(stick, L_torn, t)

    core = cloud_positions(t, RATE, JITTER_DEG, 13)
    if core:
        make_grain_cloud("grains", core, GRAIN_MM * MM, mat_powder)
    mist = cloud_positions(t, MIST_RATE, MIST_JITTER, 517)
    if mist:
        make_grain_cloud("mist", mist, GRAIN_MM * MM * 0.6, mat_powder)
    sc_pts = scatter_positions(t)
    if sc_pts:
        make_grain_cloud("scatter", sc_pts, GRAIN_MM * MM * 0.95, mat_powder)
    surf = pile_surface_grains(t)
    if surf:
        make_grain_cloud("psurf", surf, GRAIN_MM * MM * 1.2, mat_powder)
    make_pile(t, mat_powder)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    print("=" * 66)
    print(f"  Zengenetics 가루 붓기  |  {PRODUCT}  |  {SCRIPT_VERSION}")
    print(f"  출력 폴더: {OUT_DIR}")
    print("=" * 66)

    clear_scene()
    setup_render(900, 48)

    mats = [
        mat_printed("ps_front", load_tex(f"zen_{PRODUCT}_stick_front.png")),
        mat_printed("ps_back",  load_tex(f"zen_{PRODUCT}_stick_back.png")),
        mat_plain("ps_silver", (0.75, 0.76, 0.78, 1), 0.35, metal=0.9),
    ]
    mat_powder = mat_plain("powder", POWDER, 0.95)

    stick, L_torn = build_stick(mats)
    build_studio()
    build_camera()
    sc = bpy.context.scene

    shots = [("check_powder_early.png", 0.55),
             ("check_powder_mid.png",   1.20),
             ("check_powder_end.png",   2.00)]
    import time
    t0 = time.time()
    for name, t in shots:
        build_frame_scene(t, stick, L_torn, mat_powder)
        sc.render.filepath = os.path.join(OUT_DIR, name)
        bpy.ops.render.render(write_still=True)
        print(f"  저장됨: {name}  (t={t:.2f}s, {time.time()-t0:.0f}초 경과)")

    print("\n  3장 완료. 확인 포인트:")
    print("   - 줄기가 곱고 촘촘한지 (레퍼런스처럼)")
    print("   - 가루 산이 원뿔형 + 입자 질감인지")
    print("   - 어두운 배경/스포트라이트 무드")
    print("   - 뜯긴 입구 은색 절단면\n")


main()
