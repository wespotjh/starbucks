"""
=============================================================================
 zen_stick_final.py — 젠제네틱스 스틱포 턴테이블 최종 실행판
=============================================================================

 ★ 아무것도 고치지 않아도 됩니다. 열어서 ▶ 만 누르세요.
   칼륨 → 마그네슘 → 비타민B 순서로 턴테이블 36장씩 자동으로 렌더합니다.
   중간에 꺼져도 다시 실행하면 만든 프레임은 건너뛰고 이어서 돌아갑니다.

 실행 방법  (경로 입력 없음)
   1. 이 파일을 zen 폴더 안에 넣습니다
      zen/zen_stick_final.py, zen/textures/, zen/render/
   2. Blender 실행
   3. 상단 탭에서 스크립팅함(Scripting) 클릭
   4. 폴더 아이콘(열기)으로 zen_stick_final.py 를 직접 엽니다
      ※ 복사 붙여넣기 하면 경로를 못 찾습니다. 반드시 [열기] 로 여세요.
   5. 재생(▶) 버튼 클릭

 Blender 4.2 ~ 5.x 호환
 (머티리얼 노드 입력 이름이 버전마다 달라 방어적으로 처리했습니다)

 실측 기준값
   전체 108 x 24 mm
   좌우 크림프 씰 각 10mm, 인쇄면 88mm
   필름 전개폭 58mm = 5 + 12 + 24 + 12 + 5
   가운데 24mm가 앞면, 12mm 두 장이 뒤로 돌아 뒷면 24mm
   양끝 5mm가 합쳐져 10mm 핀 씰
   재질: 은지 + 전체 백판 → 인쇄면은 흰 무광, 은색은 단면에서만
   내용물 2.5g 고운 분말 → 중앙부 부풀음

=============================================================================
"""

import bpy
import bmesh
import math
import os
from mathutils import Vector

# =============================================================================
# CONFIG — 경로를 적을 필요가 없습니다
# =============================================================================
#
#  이 파일을 zen 폴더 안에 두세요. 폴더 구조는 이렇게 됩니다.
#
#     zen/
#       zen_stick.py      <- 이 파일
#       textures/         <- 스틱 PNG 2장을 여기에
#       render/           <- 결과가 여기 저장됩니다 (없으면 자동 생성)
#
#  경로는 스크립트가 알아서 찾습니다. 아무것도 고치지 마세요.
#  단 하나, 아래 PRODUCT 만 원하시면 바꾸시면 됩니다.

PRODUCT = "potassium"      # 실행 중 자동으로 바뀝니다. 건드리지 마세요.
PRODUCTS = ["potassium", "magnesium", "vitaminb"]   # 이 순서로 전부 렌더

SCRIPT_VERSION = "final"


def _base_dir():
    """
    이 스크립트가 있는 폴더를 찾는다.
    Blender 텍스트 에디터에 붙여넣은 경우 __file__ 이 없으므로
    열려 있는 텍스트 블록의 경로를 사용한다.
    """
    import bpy, os
    # 1) 파일로 열린 텍스트 블록에서 찾기
    for txt in bpy.data.texts:
        if txt.filepath:
            p = bpy.path.abspath(txt.filepath)
            if os.path.exists(p):
                return os.path.dirname(p)
    # 2) 저장된 .blend 파일 옆
    if bpy.data.filepath:
        return os.path.dirname(bpy.path.abspath(bpy.data.filepath))
    # 3) 그래도 못 찾으면 바탕화면의 zen 폴더를 시도
    home = os.path.expanduser("~")
    for cand in (os.path.join(home, "Desktop", "zen"),
                 os.path.join(home, "바탕화면", "zen"),
                 os.path.join(home, "zen")):
        if os.path.isdir(cand):
            return cand
    raise RuntimeError(
        "\n\n  스크립트 폴더를 찾지 못했습니다.\n"
        "  Blender 스크립팅함에서 [열기] 버튼으로 zen_stick.py 파일을\n"
        "  직접 열어서 실행해 주세요. (복사 붙여넣기 말고요)\n")


BASE_DIR = _base_dir()
TEX_DIR  = __import__("os").path.join(BASE_DIR, "textures")
OUT_DIR  = __import__("os").path.join(BASE_DIR, "render")


# --- 품질 프리셋 -------------------------------------------------------------
# 최종 실행판은 TURN(턴테이블 36장) 고정입니다.
MODE = "TURN"

# 조명 세기 배율. 1.0이 기본입니다.
# 결과가 하얗게 날아가면 0.5, 너무 어두우면 2.0 식으로 조절하세요.
LIGHT_POWER = 0.1

#
# UV_SCALE  가로세로에 똑같이 걸리는 하나의 배율입니다.
#           v4 텍스처는 도면에서 108 x 24mm 면 그대로 정확히 재단했으므로
#           1.0 으로 두면 1:1 로 정확히 입혀집니다. 건드리지 마세요.
UV_SCALE = 1.0

# AUTO_FIT  텍스처 여백이 제멋대로인 파일을 쓸 때만 켜는 자동 보정입니다.
#           잉크 영역을 재서 중앙 정렬 + PRINT_SPAN_MM 폭으로 확대합니다.
#           v4 정재단 텍스처(도면에서 직접 재단)에는 필요 없어 끕니다.
AUTO_FIT = False

# PRINT_SPAN_MM  그래픽(로고 끝~절취선)의 실물 가로 길이.
#                실물 누끼 기준: 인쇄면 88mm 를 거의 가득 채워 약 84mm.
#                렌더가 실물보다 그래픽이 작으면 이 값을 키우세요.
PRINT_SPAN_MM = 84.0

# UV_OFFSET_X_MM  자동 맞춤 후에도 미세하게 어긋나면 여기서 조정합니다.
#                 단위는 mm. +1.0 이면 그래픽이 오른쪽으로 1mm 이동합니다.
UV_OFFSET_X_MM = 0.0

PRESETS = {
    "CHECK":      {"res": 700,  "samples": 24,  "frames": 1},
    # 뒷면 글자 방향 확인용. 180도 돌려 한 장만 뽑습니다.
    "CHECK_BACK": {"res": 700,  "samples": 24,  "frames": 1},
    # 첫 시험용. EEVEE 로 돌아가며 아주 가볍습니다.
    "TURN":  {"res": 900,  "samples": 32,  "frames": 36},
    # 최종 납품용. Cycles. 시간이 오래 걸리니 마지막에만 쓰세요.
    "FINAL": {"res": 1600, "samples": 160, "frames": 60},
}

# TURN 은 EEVEE, FINAL 은 Cycles 로 돌아갑니다.
FAST_MODES = {"CHECK", "CHECK_BACK", "TURN"}


# =============================================================================
# 실측 치수 (단위 mm) — 도면에서 추출한 값. 건드리지 마세요.
# =============================================================================

LENGTH        = 108.0   # 전체 길이
WIDTH         = 24.0    # 폭 (앞면 높이)
SEAL_SIDE     = 12.0    # 좌우 크림프 씰 (도면 10mm, 실물 대비 20% 확대)
FACE_LEN      = 88.0    # 인쇄면 길이
BULGE         = 5.6     # 충전 후 최대 두께 (앞뒤 합)
FIN_HEIGHT    = 3.2     # 뒷면 핀 씰이 서 있는 높이
SEAL_THICK    = 0.18    # 필름 두께 (씰링부)
NOTCH_FROM_END = 8.0    # 이지컷 노치 위치 (우측 끝에서)

MM = 0.001


# =============================================================================
# 유틸리티
# =============================================================================

def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for block in (bpy.data.meshes, bpy.data.materials,
                  bpy.data.images, bpy.data.lights, bpy.data.cameras):
        for item in list(block):
            if item.users == 0:
                block.remove(item)
    # 남아 있는 이미지 캐시를 강제로 비웁니다.
    # 이게 없으면 텍스처 파일을 고쳐도 예전 것이 계속 렌더됩니다.
    for img in list(bpy.data.images):
        if img.name not in ("Render Result", "Viewer Node"):
            try:
                bpy.data.images.remove(img, do_unlink=True)
            except Exception:
                pass


def set_input(node, names, value):
    """
    Principled BSDF 입력 이름이 버전마다 다릅니다.
    후보 이름을 순서대로 시도하고, 없으면 조용히 넘어갑니다.
    """
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
    """
    노드를 이름으로 찾으면 언어 설정이나 버전에 따라 깨집니다.
    타입으로 찾는 것이 안전합니다.
    """
    for n in mat.node_tree.nodes:
        if n.type == "BSDF_PRINCIPLED":
            return n
    return None


def auto_smooth(obj, angle_deg):
    """
    Blender 4.1 이후 mesh.use_auto_smooth 가 사라지고
    Shade Auto Smooth 모디파이어로 바뀌었습니다. 버전별로 분기합니다.
    """
    me = obj.data
    me.shade_smooth()
    if hasattr(me, "use_auto_smooth"):          # 4.0 이하
        me.use_auto_smooth = True
        me.auto_smooth_angle = math.radians(angle_deg)
        return
    try:                                         # 4.1 이상
        prev = bpy.context.view_layer.objects.active
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        bpy.ops.object.shade_auto_smooth(angle=math.radians(angle_deg))
        obj.select_set(False)
        bpy.context.view_layer.objects.active = prev
    except Exception as e:
        print(f"  [알림] auto smooth 적용 생략: {e}")


def load_tex(filename):
    path = os.path.join(TEX_DIR, filename)
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"\n\n  텍스처를 찾을 수 없습니다:\n    {path}\n"
            f"  TEX_DIR 경로와 파일명을 확인하세요.\n"
            f"  필요한 파일: zen_{PRODUCT}_stick_front.png / _back.png\n"
        )
    img = bpy.data.images.load(path, check_existing=True)
    # 같은 세션에서 다시 실행하면 Blender 가 예전 픽셀을 캐시해 둡니다.
    # 파일을 새로 덮어써도 반영되지 않으므로 강제로 다시 읽습니다.
    try:
        img.reload()
    except Exception:
        pass
    img.colorspace_settings.name = "sRGB"
    print(f"  텍스처 로드: {filename}  ({img.size[0]} x {img.size[1]} px)")
    return img


def ink_bbox(img):
    """
    텍스처에서 잉크(흰 배경이 아닌 픽셀)의 경계 상자를 잰다.
    PNG 안에서 그래픽이 어디에 얼마나 크게 들어 있는지 알아야
    중앙 정렬과 실물 크기 맞춤을 할 수 있다.
    반환: {u0, u1, v0, v1, px_aspect}  (0~1 정규화, 실패 시 None)
    """
    try:
        import numpy as np
    except ImportError:
        print("  [알림] numpy 가 없어 자동 맞춤을 건너뜁니다")
        return None
    w, h = img.size
    if w == 0 or h == 0:
        return None
    buf = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(buf)
    px = buf.reshape(h, w, 4)
    # pixels 는 리니어 값. sRGB 0.92 백색이 리니어로 약 0.83이라 0.80 기준.
    ink = (px[..., :3].min(axis=-1) < 0.80) & (px[..., 3] > 0.5)
    cols = np.where(ink.sum(axis=0) >= 2)[0]   # 낱개 노이즈 픽셀 무시
    rows = np.where(ink.sum(axis=1) >= 2)[0]
    if cols.size == 0 or rows.size == 0:
        return None
    return {
        "u0": cols[0] / w, "u1": (cols[-1] + 1) / w,
        "v0": rows[0] / h, "v1": (rows[-1] + 1) / h,
        "px_aspect": w / h,
    }


# =============================================================================
# 머티리얼
# =============================================================================

def mat_printed(name, image):
    """
    인쇄면. 은지 위에 전체 백판이 깔려 있으므로 흰 무광 필름으로 잡습니다.
    금속 광택으로 잡으면 실물과 어긋납니다.
    """
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()

    out = nt.nodes.new("ShaderNodeOutputMaterial"); out.location = (600, 0)
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled"); bsdf.location = (250, 0)
    tex = nt.nodes.new("ShaderNodeTexImage"); tex.location = (-200, 0)
    mapping = nt.nodes.new("ShaderNodeMapping"); mapping.location = (-450, 0)
    coord = nt.nodes.new("ShaderNodeTexCoord"); coord.location = (-680, 0)

    tex.image = image
    tex.interpolation = "Cubic"      # 글자 선명도의 핵심
    tex.extension = "EXTEND"

    # --- 그래픽 자동 맞춤 ----------------------------------------------------
    # UV 는 지오메트리 기준으로 완전 대칭이므로, 쏠림도 크기 차이도 전부
    # PNG 안의 여백에서 온다. 잉크 경계 상자를 재서
    #   1) 가로·세로 중앙 정렬
    #   2) 그래픽 가로폭을 실물 기준 PRINT_SPAN_MM 로 확대
    # 를 한 번에 처리한다. 세로는 글자가 늘어나지 않도록 같은 배율을 쓴다.
    # 뒷면은 UV 를 0.5 기준으로 미러하므로 같은 보정이 그대로 통한다.
    sx = sy = 1.0
    lx = -(UV_OFFSET_X_MM / LENGTH) / UV_SCALE
    ly = 0.0
    bb = ink_bbox(image) if AUTO_FIT else None
    if AUTO_FIT and bb is None:
        print(f"  [경고] [{name}] 잉크 영역을 찾지 못해 보정 없이 진행합니다")
    if bb:
        print(f"  [{name}] 잉크 영역  가로 {bb['u0']:.1%}~{bb['u1']:.1%}"
              f"  세로 {bb['v0']:.1%}~{bb['v1']:.1%}")
        wu = bb["u1"] - bb["u0"]                    # 잉크 폭 (이미지 u 단위)
        cu = (bb["u0"] + bb["u1"]) * 0.5
        cv = (bb["v0"] + bb["v1"]) * 0.5
        # 매핑 노드는 s = uv * scale + location 으로 샘플 좌표를 만든다.
        # 면 위 x[mm] 가 이미지의 (중심 cu, 폭 wu → PRINT_SPAN_MM) 에
        # 대응하도록 배율과 위치를 역산한 값이다.
        sx = wu * LENGTH * UV_SCALE / PRINT_SPAN_MM
        sy = wu * WIDTH * UV_SCALE * bb["px_aspect"] / PRINT_SPAN_MM
        lx = cu - 0.5 * sx - UV_OFFSET_X_MM * wu / PRINT_SPAN_MM
        ly = cv - 0.5 * sy
        print(f"  [{name}] 잉크 폭 {wu * LENGTH * UV_SCALE:.1f}mm → "
              f"{PRINT_SPAN_MM:.0f}mm 로 확대, 중앙 정렬")
    mapping.inputs["Location"].default_value = (lx, ly, 0.0)
    mapping.inputs["Scale"].default_value = (sx, sy, 1.0)

    nt.links.new(coord.outputs["UV"], mapping.inputs["Vector"])
    nt.links.new(mapping.outputs["Vector"], tex.inputs["Vector"])
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])

    set_input(bsdf, "Roughness", 0.42)
    set_input(bsdf, "Metallic", 0.0)
    set_input(bsdf, ["Coat Weight", "Clearcoat"], 0.18)
    set_input(bsdf, ["Coat Roughness", "Clearcoat Roughness"], 0.30)
    set_input(bsdf, ["Specular IOR Level", "Specular"], 0.42)

    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat


def mat_silver(name):
    """씰링 단면과 노치 안쪽에서 드러나는 은지 기재."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = principled_of(mat)
    set_input(bsdf, "Base Color", (0.78, 0.79, 0.80, 1.0))
    set_input(bsdf, "Metallic", 0.85)
    set_input(bsdf, "Roughness", 0.34)
    return mat


# =============================================================================
# 지오메트리 — 핀씰 튜브
# =============================================================================

def build_stick(nx=440, ny=64):
    """
    가루가 든 스틱포를 만든다.

    단면은 납작한 타원. 좌우 끝 10mm는 크림프로 눌려 두께가 거의 0이 되고,
    가운데로 갈수록 부푼다. 뒷면 중앙에는 핀 씰이 세로로 서 있다.
    """
    L = LENGTH * MM
    W = WIDTH * MM
    half_b = BULGE * MM * 0.5
    seal = SEAL_SIDE * MM
    fin_h = FIN_HEIGHT * MM
    st = SEAL_THICK * MM

    def crimp(u):
        """u: 0~1 길이 방향. 양끝 크림프 구간에서 두께를 얇게 수렴시킨다."""
        x = u * L
        if x < seal:
            t = x / seal
        elif x > L - seal:
            t = (L - x) / seal
        else:
            return 1.0
        # 어깨가 급하게 꺾이도록. 지수가 낮을수록 각져 보입니다.
        return 0.06 + 0.94 * (t ** 0.42)

    def in_seal(u):
        """크림프 구간이면 0~1 진행도, 아니면 None."""
        x = u * L
        if x < seal:
            return x / seal
        if x > L - seal:
            return (L - x) / seal
        return None

    def flare(u):
        """
        실링 롤러가 물면서 필름이 좌우로 밀려 어깨가 벌어집니다.
        실물 누끼에서 씰링부가 몸통보다 넓게 퍼져 보이는 이유입니다.
        """
        t = in_seal(u)
        if t is None:
            return 1.0
        return 1.0 + 0.045 * (1.0 - t) ** 1.6

    def ribs(u, ang):
        """
        크림프 잔주름. 실링 롤러 이빨 자국입니다.
        씰링 구간 안에서만 나타나고, 끝으로 갈수록 뚜렷해집니다.
        간격이 넓으면 골판지처럼 보이므로 촘촘하게 잡습니다.
        """
        t = in_seal(u)
        if t is None:
            return 0.0
        x = u * L
        RIB_PITCH = 0.0010          # 주름 간격 1.0mm
        # 몸통 경계(t=1)에서 0, 바깥 끝(t=0)에서 최대
        depth = 0.00022 * (1.0 - t) ** 0.8
        return math.sin(x / RIB_PITCH * math.pi) * depth

    def wrinkle(u, ang):
        """
        본체는 매끈하게 둡니다.
        주름을 넣었더니 골판지처럼 보여서 제거했습니다.
        필름 질감은 지오메트리가 아니라 러프니스로 표현하는 편이 낫습니다.
        """
        return 0.0

    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")

    grid = []
    for i in range(nx + 1):
        u = i / nx
        c = crimp(u)
        fl = flare(u)
        row = []
        for j in range(ny + 1):
            v = j / ny
            ang = 2.0 * math.pi * v
            sgn = 1.0 if math.sin(ang) >= 0 else -1.0

            # 납작한 타원 단면 + 잔주름 + 미세 주름
            ey = (math.sin(ang) * half_b * c
                  + sgn * ribs(u, ang)
                  + sgn * wrinkle(u, ang))
            ez = math.cos(ang) * (W * 0.5) * fl

            row.append(bm.verts.new((u * L - L / 2, ey, ez)))
        grid.append(row)

    bm.verts.ensure_lookup_table()

    for i in range(nx):
        for j in range(ny):
            f = bm.faces.new([grid[i][j], grid[i + 1][j],
                              grid[i + 1][j + 1], grid[i][j + 1]])

            # 카메라는 -Y 쪽에 있습니다. y가 음수인 면이 앞면입니다.
            is_back = f.calc_center_median().y > 0
            f.material_index = 1 if is_back else 0

            for loop in f.loops:
                co = loop.vert.co
                # 나누기가 맞습니다. 곱하면 반대로 확대되어 UV 가
                # -0.05~1.05 로 텍스처 밖으로 넘칩니다 (이전 버그).
                uu = 0.5 + (co.x / L) / UV_SCALE
                vv = 0.5 + (co.z / W) / UV_SCALE
                # 뒷면은 뒤에서 볼 때 글자가 바로 읽히도록 좌우를 뒤집습니다.
                # 텍스처 파일 자체는 정방향으로 두고 여기서만 처리합니다.
                if is_back:
                    uu = 1.0 - uu
                loop[uv].uv = (uu, vv)

    # 양 끝을 막는다 (크림프라 거의 평면)
    for idx in (0, nx):
        ring = [grid[idx][j] for j in range(ny)]
        try:
            f = bm.faces.new(ring if idx == 0 else list(reversed(ring)))
            f.material_index = 2
        except Exception:
            pass

    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))

    mesh = bpy.data.meshes.new("stick")
    bm.to_mesh(mesh)
    bm.free()

    obj = bpy.data.objects.new("stick", mesh)
    bpy.context.collection.objects.link(obj)

    obj.data.materials.append(mat_printed("stick_front",
                                          load_tex(f"zen_{PRODUCT}_stick_front.png")))
    obj.data.materials.append(mat_printed("stick_back",
                                          load_tex(f"zen_{PRODUCT}_stick_back.png")))
    obj.data.materials.append(mat_silver("stick_seal"))

    auto_smooth(obj, 26)
    return obj


# =============================================================================
# 조명 · 카메라
# =============================================================================

def build_studio(subject_size):
    """
    조명 세기는 피사체 크기에 맞춰야 합니다.
    108mm짜리를 27cm 거리에서 찍는데 90W를 쏘면 완전히 타버립니다.
    거리 제곱에 반비례하므로 작은 물체일수록 약하게 잡습니다.
    """
    def area(name, loc, rot, size, energy):
        d = bpy.data.lights.new(name, type="AREA")
        d.shape = "RECTANGLE"; d.size = size[0]; d.size_y = size[1]
        d.energy = energy * LIGHT_POWER
        o = bpy.data.objects.new(name, d)
        o.location = loc; o.rotation_euler = rot
        bpy.context.collection.objects.link(o)

    s = subject_size
    area("Key",  (-0.10, -0.16, s * 1.9),
         (math.radians(48), 0, math.radians(-38)), (0.35, 0.45), 12.0)
    area("Fill", ( 0.18, -0.12, s * 0.7),
         (math.radians(76), 0, math.radians(56)), (0.45, 0.45), 3.5)
    area("Rim",  ( 0.06,  0.22, s * 1.5),
         (math.radians(122), 0, math.radians(18)), (0.28, 0.32), 8.0)

    bpy.ops.mesh.primitive_plane_add(size=1.2, location=(0, 0, -s * 0.9))
    b = bpy.context.object; b.name = "Bounce"
    m = bpy.data.materials.new("BounceWhite"); m.use_nodes = True
    bp = principled_of(m)
    set_input(bp, "Base Color", (1, 1, 1, 1))
    set_input(bp, "Roughness", 0.9)
    b.data.materials.append(m)
    b.visible_camera = False


def build_camera(subject_size):
    cd = bpy.data.cameras.new("Camera")
    cd.lens = 85
    cd.sensor_width = 36
    cam = bpy.data.objects.new("Camera", cd)
    bpy.context.collection.objects.link(cam)
    bpy.context.scene.camera = cam

    dist = subject_size * 3.0
    cam.location = (0, -dist, subject_size * 0.22)

    tgt = bpy.data.objects.new("CamTarget", None)
    bpy.context.collection.objects.link(tgt)
    tgt.location = (0, 0, 0)
    c = cam.constraints.new("TRACK_TO")
    c.target = tgt
    c.track_axis = "TRACK_NEGATIVE_Z"
    c.up_axis = "UP_Y"
    return cam


# =============================================================================
# 렌더 설정
# =============================================================================

def setup_render(res, samples, fast=False):
    sc = bpy.context.scene

    if fast:
        # 확인용은 EEVEE. 몇 초면 끝납니다.
        # 맥에서 Cycles GPU 설정이 안 되어 있으면 CPU로 떨어져 매우 느려집니다.
        sc.render.engine = "BLENDER_EEVEE_NEXT" \
            if "BLENDER_EEVEE_NEXT" in [e.identifier for e in
               bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items] \
            else "BLENDER_EEVEE"
        try:
            sc.eevee.taa_render_samples = samples
        except Exception:
            pass
    else:
        sc.render.engine = "CYCLES"
        try:
            sc.cycles.device = "GPU"
        except Exception:
            pass
        sc.cycles.samples = samples
        sc.cycles.use_denoising = True
        sc.cycles.adaptive_threshold = 0.005

    sc.render.resolution_x = res
    sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.render.filter_size = 1.1          # 기본 1.5는 글자를 흐리게 합니다
    sc.render.film_transparent = True
    sc.render.use_motion_blur = False

    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"
    sc.render.image_settings.color_depth = "16"

    # 브랜드 컬러를 그대로 내보내기 위해 Standard 고정
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.look = "None"


# =============================================================================
# 메인
# =============================================================================

def main():
    # 세 제품을 순서대로 자동 렌더합니다. 사용자가 고칠 것은 없습니다.
    # 키프레임을 쓰지 않고 프레임마다 직접 회전시켜 한 장씩 렌더합니다.
    # (Blender 4.4 의 Action 구조 변경 회피 + 중단돼도 이어서 실행 가능)
    global PRODUCT
    import time
    cfg = PRESETS[MODE]
    os.makedirs(OUT_DIR, exist_ok=True)
    n = cfg["frames"]
    total = n * len(PRODUCTS)
    t0 = time.time()
    done_total = 0
    failed = []

    for PRODUCT in PRODUCTS:
        print("=" * 66)
        print(f"  Zengenetics 스틱포 턴테이블  |  {PRODUCT}  |  {n}장  |  {SCRIPT_VERSION}")
        print(f"  출력: {os.path.join(OUT_DIR, PRODUCT + '_stick')}")
        print("=" * 66)
        try:
            clear_scene()
            setup_render(cfg["res"], cfg["samples"], fast=(MODE in FAST_MODES))
            obj = build_stick()
            size = LENGTH * MM
            build_studio(size)
            build_camera(size)
        except FileNotFoundError as e:
            print(f"  [건너뜀] {PRODUCT}: 텍스처가 없습니다. 다음 제품으로 넘어갑니다.")
            print(f"           {e}")
            failed.append(PRODUCT)
            done_total += n
            continue

        sc = bpy.context.scene
        d = os.path.join(OUT_DIR, f"{PRODUCT}_stick")
        os.makedirs(d, exist_ok=True)

        for i in range(n):
            path = os.path.join(d, f"frame_{i + 1:04d}.png")
            done_total += 1
            if os.path.exists(path):
                print(f"  [{PRODUCT} {i+1:>3}/{n}] 이미 있음, 건너뜀")
                continue
            obj.rotation_euler = (0, 0, 2.0 * math.pi * i / n)
            sc.render.filepath = path
            bpy.ops.render.render(write_still=True)
            el = time.time() - t0
            eta = el / max(done_total, 1) * (total - done_total)
            print(f"  [{PRODUCT} {i+1:>3}/{n}]  전체 {done_total}/{total}"
                  f"  경과 {el/60:.1f}분  남은시간 약 {eta/60:.1f}분")

    print("\n" + "=" * 66)
    if failed:
        print(f"  텍스처가 없어 건너뛴 제품: {', '.join(failed)}")
        print(f"  textures 폴더에 zen_제품명_stick_front.png / _back.png 를 넣고")
        print(f"  다시 실행하면 그 제품만 마저 렌더합니다.")
    else:
        print(f"  전부 완료!  render 폴더 안에 제품별로 {n}장씩 저장됐습니다.")
        print(f"  potassium_stick / magnesium_stick / vitaminb_stick")
    print("=" * 66 + "\n")


main()
