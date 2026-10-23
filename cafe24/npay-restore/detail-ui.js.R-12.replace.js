  /* ------------------------------------------- R-12 간편결제 앱 블록 — 2026-10-23 개정
   * 2026-09-11 개편 때 네이버페이·카카오페이·찜을 전부 내렸다. 2026-10-23 부터 **네이버페이만 되살린다.**
   *   - 카카오 톡체크아웃(#appPaymentButtonBox / #kakao-checkout-button) : 계속 차단
   *   - 네이버페이 : `.infoArea-footer .productAction .buy-btn-wrap` 에 주입된 컨테이너 1개만 살려
   *                 「장바구니·구매하기」 아래 전폭 한 줄로 둔다 (배치·치수는 detail.css R-12b)
   *   - 네이버 찜 : 위젯 안의 찜 버튼은 CSS 로 감춘다 (2026-09-11 "찜 제거" 요건 유지)
   *
   * 카페24 앱은 마크업이 아니라 **런타임 스크립트**로 버튼을 만든다 (실측, 라이브 소스):
   *     EC_CHECKOUT_TARGET_DIV.parent().append('<div id="appPaymentButtonBox" …>')
   *     $("#appPaymentButtonBox").append(<div id="kakao-checkout-button">)
   *     EC$("#NaverChk…").length == 0  →  다시 append
   * 이때 `[onclick^="product_submit(2"]` 가 3개(인라인·하단바·orderFixArea)라 네이버 컨테이너도 **3개** 붙고,
   * 네이버 스크립트는 getElementById 로 **첫 번째(인라인 .buy-btn-wrap)** 에만 버튼을 그린다.
   * 나머지 둘은 빈 채로 남아 flex gap 만 만든다 → 감춘다.
   *
   * ⚠ 노드를 **지우지 않는다** — 앱 스크립트가 자기 노드를 다시 찾으므로 지우면
   *   위 `length == 0` 분기가 매번 다시 돌아 무한 재생성이 된다. 인라인 스타일로 내린다.
   * ⚠ 앱이 자기 display 를 다시 쓰는 경우가 있어 `important` 로 박는다 —
   *   이건 스타일시트가 아니라 **인라인 우선순위**라 detail.css 의 "새 important 금지"
   *   설계 규칙과 무관하다.
   * ⚠ 주입 시점이 비동기라 한 번만 훑으면 놓친다 — MutationObserver 로 계속 지킨다. */
  /* ⚠ 셀렉터에 네이버 버튼 **id 전체를 리터럴로 쓰지 않는다** — 그 문자열은 A군
   *   「플러그인 훅 보존」 계약 토큰이라, 스킨 파일에 나타나면 훅 개수 검사가 오탐한다.
   *   접두사 선택자로 같은 노드를 잡는다. */
  var APPPAY_SEL = '#appPaymentButtonBox, #kakao-checkout-button';
  var NPAY_SEL = '[id^="NaverChk"]';
  var NPAY_HOME = '.infoArea-footer .productAction .buy-btn-wrap';

  /* R-13 「친구 초대」·「적립금혜택 6,000원」 배지 — 외부 추천 앱이 `body` 에 붙이는
   * 떠 있는 런처다. 화면 오른쪽 아래에 뜨는데 그 자리가 하필 구매 버튼·합계 위라
   * 「할인금액」·「상품 금액」 숫자를 덮었다(실기기 확인 2026-09-11).
   * → **상세페이지에서만** 내린다. 다른 페이지에서는 그대로 뜬다.
   * ⚠ 여기서도 노드를 지우지 않는다 — 앱이 자기 노드를 다시 찾는다. */
  var OVERLAY_SEL = '#incento-launcher, #incento-widget, [class*="incento_widget__launcher"]';

  function hideNode(n) {
    if (n.getAttribute('data-zg-off') === '1') return;
    try { n.style.setProperty('display', 'none', 'important'); } catch (e) { n.style.display = 'none'; }
    n.setAttribute('data-zg-off', '1');
  }

  function killAppPay() {
    var box = root ? root : document;
    /* 추천 앱 런처는 `body` 직속이라 `.zg-detail` 안에서 못 찾는다 — 문서 전체에서 잡되,
     * 이 스크립트는 상세페이지에서만 도므로 다른 페이지에는 영향이 없다. */
    if (root) $$(OVERLAY_SEL, document).forEach(hideNode);
    $$(APPPAY_SEL, box).forEach(hideNode);
    dressNaverPay(box);
  }

  /* 네이버페이 컨테이너 정리
   *   - 인라인 구매 블록 안의 것 1개만 살린다. 앱이 박은 인라인 `float:left; margin:20px auto 0; padding-right:10px; clear:both`
   *     은 flex 2줄 배치를 깨므로 걷는다 (스타일시트로는 인라인을 못 넘고, important 는 쓰지 않는다).
   *   - 예전 번들(2026-09-11 판)이 캐시로 남아 먼저 돌았다면 inline display:none 이 박혀 있다 — 같이 걷는다.
   *   - 그 밖의 복제본(하단바·orderFixArea)은 빈 껍데기라 내린다. */
  function dressNaverPay(box) {
    $$(NPAY_SEL, box).forEach(function (n) {
      var home = n.parentElement && n.parentElement.closest ? n.parentElement.closest(NPAY_HOME) : null;
      if (!home || n.parentElement !== home) { hideNode(n); return; }
      if (n.getAttribute('data-zg-npay') === '1') return;
      ['display', 'float', 'clear', 'margin', 'padding'].forEach(function (p) {
        try { n.style.removeProperty(p); } catch (e) {}
      });
      n.removeAttribute('data-zg-off');
      n.setAttribute('data-zg-npay', '1');
    });
  }

  function watchAppPay() {
    killAppPay();
    var MO = window.MutationObserver || window.WebKitMutationObserver;
    if (!MO) return;
    var host = $('.infoArea-footer') || root;
    if (!host) return;
    var mo = new MO(function () { killAppPay(); fitSheet(); });
    try { mo.observe(host, { childList: true, subtree: true }); } catch (e) {}
    /* 추천 앱 런처는 `body` 직속으로 늦게 붙는다 — 자식 추가만 본다(subtree 아님, 가볍게) */
    try { mo.observe(document.body, { childList: true }); } catch (e) {}
    /* 앱 스크립트는 로드가 늦다 — 초반 몇 초는 확인 사살한다(폴링 아님, 유한 회수) */
    [200, 600, 1200, 2500, 5000].forEach(function (ms) {
      setTimeout(function () { killAppPay(); fitSheet(); }, ms);
    });
  }
