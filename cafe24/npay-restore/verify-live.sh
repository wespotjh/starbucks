#!/usr/bin/env bash
# 라이브(zengenetics.co.kr) 상품 상세에 네이버페이 복원 패치가 실제로 올라가 있는지 확인한다.
# 사용: bash verify-live.sh      (카페24 저장 뒤, 그리고 24시간 뒤에 한 번 더)
set -u
URL="https://zengenetics.co.kr/product/detail.html?product_no=11"
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128 Safari/537.36"
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
curl -sSL -A "$UA" "$URL" -o "$tmp/page.html" || { echo "페이지를 못 받았습니다"; exit 2; }
css=$(grep -o 'href="/ind-script/optimizer_user[^"]*type=css[^"]*"' "$tmp/page.html" | head -1 | sed 's/href="//;s/"$//;s/&amp;/\&/g')
js=$(grep -o 'src="/ind-script/optimizer_user[^"]*type=js[^"]*"'  "$tmp/page.html" | head -1 | sed 's/src="//;s/"$//;s/&amp;/\&/g')
curl -sS -A "$UA" "https://zengenetics.co.kr$css" -o "$tmp/user.css"
curl -sS -A "$UA" "https://zengenetics.co.kr$js"  -o "$tmp/user.js"
ok=0
if grep -q "R-12b 네이버페이 복원" "$tmp/user.css"; then echo "[OK] detail.css  : R-12b 블록 있음"; else echo "[--] detail.css  : R-12b 블록 없음 (아직 미적용이거나 되돌아감)"; ok=1; fi
if grep -q "function dressNaverPay" "$tmp/user.js"; then echo "[OK] detail-ui.js: dressNaverPay() 있음"; else echo "[--] detail-ui.js: dressNaverPay() 없음 (아직 미적용이거나 되돌아감)"; ok=1; fi
if grep -q "APPPAY_SEL = '#appPaymentButtonBox, #kakao-checkout-button'" "$tmp/user.js"; then echo "[OK] detail-ui.js: 차단 셀렉터에서 네이버 제외됨"; else echo "[--] detail-ui.js: 예전 차단 셀렉터(네이버 포함) 그대로"; ok=1; fi
echo "CSS 번들 $(echo "$css" | grep -o 't=[0-9]*')  JS 번들 $(echo "$js" | grep -o 't=[0-9]*')"
[ $ok -eq 0 ] && echo "==> 패치가 라이브에 살아 있습니다." || echo "==> 패치가 라이브에 (아직) 없습니다."
exit $ok
