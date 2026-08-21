"""
=============================================================================
 zen_webp.py — 렌더 프레임 일괄 WebP 변환기
=============================================================================

 ★ 아무것도 고치지 않아도 됩니다. Blender 에서 열어서 ▶ 만 누르세요.
   (Blender 에 내장된 파이썬으로 변환하므로 다른 프로그램 설치가 필요 없습니다)

 하는 일
   zen/render/ 안의 모든 시퀀스 폴더(frame_0001.png ...)를 찾아
   zen/webp/<같은 폴더 이름>/frame_0001.webp ... 로 변환합니다.
   - 품질 82 (웹용으로 충분히 선명하면서 용량 대폭 절감)
   - 이미 변환된 파일은 건너뜀 (이어하기 가능)
   - check_*.png 같은 낱장 확인 파일은 건너뜀

 실행 방법
   1. 이 파일을 zen 폴더에 넣습니다
   2. Blender → Scripting → [열기] → zen_webp.py → ▶
=============================================================================
"""

import bpy
import os

QUALITY = 82


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
    raise RuntimeError("\n\n  [열기] 버튼으로 zen_webp.py 를 직접 열어 실행하세요.\n")


BASE_DIR = _base_dir()
RENDER_DIR = os.path.join(BASE_DIR, "render")
WEBP_DIR = os.path.join(BASE_DIR, "webp")


def main():
    if not os.path.isdir(RENDER_DIR):
        print("  render 폴더가 없습니다:", RENDER_DIR)
        return

    # WebP 저장 설정
    sc = bpy.context.scene
    sc.render.image_settings.file_format = "WEBP"
    sc.render.image_settings.quality = QUALITY
    sc.render.image_settings.color_mode = "RGBA"

    seq_dirs = [d for d in sorted(os.listdir(RENDER_DIR))
                if os.path.isdir(os.path.join(RENDER_DIR, d))]
    if not seq_dirs:
        print("  변환할 시퀀스 폴더가 없습니다.")
        return

    print("=" * 66)
    print(f"  WebP 변환  |  품질 {QUALITY}  |  대상 {len(seq_dirs)}개 폴더")
    print("=" * 66)

    total_done = total_skip = 0
    for d in seq_dirs:
        src = os.path.join(RENDER_DIR, d)
        dst = os.path.join(WEBP_DIR, d)
        pngs = sorted(f for f in os.listdir(src) if f.lower().endswith(".png"))
        if not pngs:
            continue
        os.makedirs(dst, exist_ok=True)
        done = skip = 0
        for f in pngs:
            out = os.path.join(dst, os.path.splitext(f)[0] + ".webp")
            if os.path.exists(out):
                skip += 1
                continue
            img = bpy.data.images.load(os.path.join(src, f))
            img.save_render(out)
            bpy.data.images.remove(img)
            done += 1
        total_done += done
        total_skip += skip
        print(f"  {d}: 변환 {done}장, 건너뜀 {skip}장")

    print("=" * 66)
    print(f"  완료! 총 변환 {total_done}장 (기존 {total_skip}장 유지)")
    print(f"  결과 폴더: {WEBP_DIR}")
    print("  이제 zen_scroll.html 을 브라우저로 열면 스크롤 페이지가 동작합니다.")
    print("=" * 66)


main()
