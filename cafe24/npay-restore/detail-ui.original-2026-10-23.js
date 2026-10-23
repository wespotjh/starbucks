/* ============================================================================
 * ds/js/detail-ui.js — 젠제네틱스 상품 상세 UI (칼륨 product_no=11 기준, 9종 공용)
 *
 * 절대 규칙
 *   - 가격을 계산하지 않는다. 화면에 쓰는 금액은 전부 `#totalPrice .total strong`
 *     (없으면 `… em`)에서 읽고 `(N개)` 꼬리만 떼어 쓴다.
 *   - 평점·리뷰수를 쓰지 않는다 (알파리뷰 위젯 담당).
 *   - `#freeShipGuide` 는 스킨 JS 가 이미 구동한다. 여기서 진행률·금액을 만들지 않는다.
 *   - `#totalProducts` 내부에 래퍼를 추가하지 않는다 (스킨 셀렉터가 7단 자손 체인이다).
 *   - 옵션 선택의 진실원장은 `tr.option_product` 행 목록이다 (select 는 `*` 로 되돌아간다).
 *
 * 로드 경로 (실측으로 확정한 사실만 적는다)
 *   이 파일은 `product/detail.html` 상단의 `@js()` 로 선언된다. 카페24는 `@css/@js` 디렉티브를
 *   모아 번들 2벌을 만든다 — **CSS 번들은 `<head>`, JS 번들은 `</body>` 근처**다.
 *   번들 안 순서 규칙: ① 콘텐츠 페이지의 직접 선언(줄 순서) → ② 레이아웃 → ③ 콘텐츠가 import 한 파일.
 *   따라서 이 파일은 **사용자 JS 번들 1번**이고, 같은 페이지의 스킨 JS 보다 먼저 실행된다.
 *   두 번들 모두 defer/async 없는 classic script 라 문서 순서대로 동기 실행된다.
 *
 * 그 순서에 기대는 것 2가지 (뒤집혀도 안전하게 실패하도록 만들어 두었다)
 *   ① 스킨 JS 가 지워 버리는 `#freeShipGuide[data-delivery]` / `.delivery_price_css` 를 먼저 붙잡는다.
 *      못 잡으면 배송비 줄이 안내 문구로 폴백한다 — 숫자를 지어내지 않는다.
 *   ② 상세 이미지 승격을 지연로더(jQuery ready)보다 먼저 한다.
 *      밀리더라도 로더는 교차 전까지 원본 속성을 남기므로 init() 의 재승격이 회수한다.
 * ==========================================================================*/

/* ── 확정 사양. 아래 두 값이 현재 동작이다.
 *    플래그는 지우지 않는다 — 전 상품 전개 후 A/B 검증 때 한 줄로 뒤집기 위해 남겨 둔다.
 *    값만 바꾸면 동작이 바뀐다. ── */
var ZG_OPT_MODE = 'multi';      /* 'multi' = 구성 카드를 눌러 여러 구성을 담을 수 있다 (현재 라이브 동작, 확정 기본값)
                                   'single' = 라디오처럼 택1. 카페24가 만든 tr.option_product 를 프로그램 삭제한다
                                              (삭제 컨트롤을 못 찾으면 'multi' 로 안전 폴백) */
var ZG_OPT_AUTOSELECT = false;  /* 확정 = false (총액 0원에서 시작, 고객이 직접 선택)
                                   true = 페이지 진입 시 2box 를 자동 선택 */

/* ── 부작용이 확인되면 즉시 되돌리기 위한 안전핀 (설계 규칙) ── */
var ZG_MOVE_TOTALPRODUCTS = true; /* true = ≤767px 에서 선택목록(#totalProducts)을 구성카드 바로 아래로 옮긴다 */

(function () {
  'use strict';

  /* ------------------------------------------------------------------ 유틸 */
  function $(sel, ctx) { try { return (ctx || document).querySelector(sel); } catch (e) { return null; } }
  function $$(sel, ctx) {
    try { return Array.prototype.slice.call((ctx || document).querySelectorAll(sel)); }
    catch (e) { return []; }
  }
  function txt(el) { return el ? (el.textContent || '') : ''; }
  function squash(s) { return String(s || '').replace(/\s+/g, ' ').trim(); }
  function keyOf(s) { return String(s || '').replace(/\s+/g, ''); }
  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }
  function on(node, ev, fn, cap) { if (node && node.addEventListener) node.addEventListener(ev, fn, !!cap); }

  /* ================================================================== *
   * [중요] · K-09 SEO 하드가드 (QA 지적 반영)
   * ------------------------------------------------------------------
   * `.zg-fold` 는 overflow:hidden 이라 `CAFE24.lazyload()` 의 IntersectionObserver 가
   * 접힌 구간의 <img> 와 **영원히 교차하지 않는다**. IO 의 교차 사각형은 조상의 클립
   * 사각형과 교집합을 취하기 때문이다. 결과: 상세 14장 중 약 12장이 1x1 placeholder
   * 로 굳어 색인에서 사라진다(개편 전엔 되던 것 → 회귀).
   * 이전 판의 `dispatchEvent(new Event('scroll'))` 완화책은 **무효**였다 —
   * IO 는 scroll 이벤트를 구독하지 않는다. 그 코드는 삭제했다.
   *
   * 대신 `ec-data-src` 를 우리가 직접 `src` 로 승격하고 속성을 지워 로더 대상에서
   * 제외한다. 성능은 네이티브 loading="lazy" 로 유지한다(네이티브 지연로딩은
   * 마크업의 src 를 지우지 않으므로 크롤러가 URL 을 본다).
   * alt 는 {$name} 이 렌더된 h1.prd-name 에서 읽는다 — 문구를 창작하지 않는다.
   * NNEditor 원본은 그대로다(런타임 속성 승격일 뿐 설계 규칙 위반 아님).
   * ================================================================== */
  function unlazyDetailImages() {
    try {
      var host = document.getElementById('prdDetail');
      if (!host) return 0;
      var h1 = document.querySelector('.prd-name');
      var nm = h1 ? (h1.textContent || '').replace(/\s+/g, ' ').trim() : '';
      var imgs = host.querySelectorAll('img[ec-data-src]');
      var n = 0;
      for (var i = 0; i < imgs.length; i++) {
        var img = imgs[i], real = img.getAttribute('ec-data-src');
        if (!real) continue;
        img.removeAttribute('ec-data-src');          /* CAFE24.lazyload() 대상에서 제외 */
        /* [근거] 첫 2장은 즉시(LCP 후보), 나머지는 지연.
         * 로드 전 높이 0 문제는 ds/css/detail.css 의 `aspect-ratio`/`min-width` 가 막는다 —
         * 자리를 차지해야 `loading="lazy"` 가 실제로 동작한다. */
        img.setAttribute('loading', n < 2 ? 'eager' : 'lazy');
        img.setAttribute('fetchpriority', n < 2 ? 'high' : 'low');
        img.setAttribute('decoding', 'async');
        if (!img.getAttribute('alt')) img.setAttribute('alt', nm + ' 상세 이미지 ' + (i + 1));
        img.src = real;
        n++;
      }
      return n;
    } catch (e) { return 0; }
  }
  /* 카페24 지연로더는 이렇게 기동한다:
   *     EC$(function(){ if (EC$('img[ec-data-src]').length > 0) CAFE24.lazyload(); });
   * 우리가 상세 이미지를 전부 승격하면 그 가드가 **0** 이 되어 로더가 아예 시작하지 않는다.
   * 로더는 IntersectionObserver 뿐 아니라 **MutationObserver 도** 걸어서 나중에 DOM 에 들어오는
   * 지연 이미지를 회수하는데, 그것까지 같이 죽는다.
   * (실측: 이 몰 상품들의 ec-data-src 는 전부 #prdDetail 안이라 지금은 피해가 없다.
   *  그러나 연관상품 등이 켜지면 조용히 깨진다 — 운이 좋은 것이지 설계가 아니다.)
   * → 승격을 끝낸 뒤 로더를 **우리가 한 번 불러** 관찰자를 되살린다. 대상이 0개여도
   *   관찰자만 설치되고 부작용이 없다. */
  function rearmLazyLoader() {
    try {
      var C = window.CAFE24;
      if (C && typeof C.lazyload === 'function' && !window.__ZG_LAZY_REARMED__) {
        window.__ZG_LAZY_REARMED__ = 1;
        C.lazyload();
      }
    } catch (e) {}
  }

  /* jQuery ready(= CAFE24.lazyload 실행 시점)보다 먼저 이겨야 하므로 파싱 시점에 즉시 실행.
   * 아직 #prdDetail 이 없으면 DOMContentLoaded 로 미룬다. init() 에서 한 번 더 돌려
   * 로더가 먼저 돌아 placeholder 를 씌운 경우도 회수한다(ec-data-src 는 교차 전까지 남는다). */
  if (document.getElementById('prdDetail')) unlazyDetailImages();
  else if (document.addEventListener) document.addEventListener('DOMContentLoaded', unlazyDetailImages, false);

  /* ------------------------------------------- 스킨 JS 보다 먼저 값을 확보 */
  /* moa/js/product/detail.js 는 초기화가 끝나면
   *   $('#freeShipGuide').removeAttr('data-delivery');  $('.delivery_price_css').remove();
   * 를 실행한다. 둘 다 사라지기 전에 문자열만 복사해 둔다(숫자를 파싱하지 않는다). */
  /* 한 번이라도 읽히면 기억한다. 로드 순서가 바뀌어도(이 파일을 @js 번들로 옮기면 바뀐다) 어느 한
   * 시점에서든 읽히면 되고, 끝내 못 읽으면 **숫자를 지어내지 않고** 안내 문구로 대체한다. */
  var CAPTURED = { delivery: '' };
  function captureDelivery() {
    if (CAPTURED.delivery) return CAPTURED.delivery;
    try {
      var g = document.getElementById('freeShipGuide');
      var a = g && g.getAttribute('data-delivery');
      if (a && squash(a)) { CAPTURED.delivery = squash(a); return CAPTURED.delivery; }
      var d = document.querySelector('.delivery_price_css');
      if (d && squash(txt(d))) { CAPTURED.delivery = squash(txt(d)); return CAPTURED.delivery; }
    } catch (e) {}
    return '';
  }
  captureDelivery();

  /* ------------------------------------------------------- 총액 (읽기 전용) */
  /* ds/js/zg-ga4.js screenTotal() 과 같은 규칙: `#totalPrice .total strong|em` 만 읽고
   * "(N개)" 꼬리를 뗀다. `#totalPrice` 전체 텍스트를 읽으면 "680001" 이 된다. */
  function totalNode() { return $('#totalPrice .total strong, #totalPrice .total em'); }
  function totalText() {
    var t = squash(txt(totalNode()));
    return t.replace(/\(\s*\d+\s*개\s*\)\s*$/, '').trim();
  }
  function totalNum() {
    var d = totalText().replace(/[^0-9]/g, '');
    return d ? parseInt(d, 10) : 0;
  }

  /* [13종 대비] "판매가가 실제로 있는 상품인가" — 계산하지 않고 스킨이 이미 써 둔 값만 읽는다.
   * 34/91/93 은 `.infoArea[data-price]` 가 "이벤트종료" · "구매 상품이 아닙니다" 같은 문구이고
   * 수량행 단가(`#totalProducts span.quantity_price`)도 비어 있다.
   * 60/61/62 는 옵션이 없어도 단가가 있으므로 여기서 true 가 되어 금액 줄을 유지한다. */
  function hasRealPrice() {
    var info = $('.infoArea[data-price]');
    if (info && /[0-9]/.test(info.getAttribute('data-price') || '')) return true;
    if (/[0-9]/.test(squash(txt($('#totalProducts span.quantity_price'))))) return true;
    return false;
  }

  /* -------------------------------------------------- 진실원장: 선택된 행 */
  function readRow(r) {
    var sp = $('p.product span', r);
    /* [9종 복제 대비] 옵션 없이 add_option 만 있는 상품은 p.product 에 <span> 이 없다.
     * 스킨의 `.product{font-size:0}` 설계 때문에 행 글자가 통째로 사라지고,
     * key 도 빈 문자열이 되어 카드 선택 표시가 붙지 않는다.
     * → <span> 이 없으면 p.product 전체 텍스트를 쓰고 행에 표식을 남겨 CSS 로 글자를 되살린다. */
    var src = sp;
    if (!sp) {
      src = $('p.product', r);
      /* p.product 가 있는데 <span> 만 없는 경우에만 표식을 남긴다.
       * (옵션 없는 상품의 정적행에는 p.product 자체가 없다 — 그 행은 스킨이 이미 그린다) */
      if (src && r.setAttribute) r.setAttribute('data-zg-nospan', '1');
    }
    var qi = $('input.quantity_opt, input[name^="quantity_opt"]', r);
    var q = 1;
    if (qi) {
      var dd = String(qi.value || '').replace(/[^0-9]/g, '');
      q = dd ? parseInt(dd, 10) : 1;
      if (q <= 0) q = 1;
    }
    return { el: r, key: keyOf(txt(src)), qty: q };
  }
  /* 카드 선택 표시의 진실원장 — 본품 구성 행만 센다 (설계 규칙) */
  function pickedRows() { return $$('tr.option_product').map(readRow); }

  /* 빈 상태 판정 = **화면에 실제로 보이는 행**의 개수.
   *
   * 클래스(`tr.option_product` / `tr.add_product`)로 세면 두 번 틀린다:
   *   ① 추가상품만 고른 고객에게 "구성을 선택해 주세요"가 뜬다 (필수옵션 상품)
   *   ② **옵션이 아예 없는 상품**에서는 그 두 클래스가 영원히 안 붙는다.
   *      실측: 필수옵션 상품은 정적행이 `<tbody class="displaynone">` 안에 숨어 있지만,
   *      옵션 없는 상품은 `<tbody class="">` 로 **노출**되고 그 행의
   *      `input[name="quantity_opt[]"]` 이 이미 value="1" 이다 (= 이미 1개가 담긴 상태).
   *      그 상품에서 클래스로 세면 영구 0 이라 금액은 뜨는데 안내문도 같이 뜬다.
   *
   * 그래서 "보이는 tbody 안의, 옵션 상세행이 아닌 tr" 을 센다. 9종 어느 형태에서도 성립한다. */
  function visibleRows() {
    var out = [];
    var tp = document.getElementById('totalProducts');
    if (!tp) return out;
    var table = null, i;
    for (i = 0; i < tp.children.length; i++) if (tp.children[i].tagName === 'TABLE') { table = tp.children[i]; break; }
    if (!table) return out;
    var hidden = /(^|\s)displaynone(\s|$)/;
    for (i = 0; i < table.children.length; i++) {
      var tb = table.children[i];
      if (tb.tagName !== 'TBODY' || hidden.test(tb.className || '')) continue;
      for (var j = 0; j < tb.children.length; j++) {
        var tr = tb.children[j];
        if (tr.tagName !== 'TR') continue;
        if (tr.id === 'totalProductsOption') continue;      /* 옵션 상세(주소·각인 등) 행 */
        if (hidden.test(tr.className || '')) continue;
        out.push(tr);
      }
    }
    return out;
  }
  function rowMatches(rowKey, cardKey) {
    if (!rowKey || !cardKey) return false;
    return rowKey.indexOf(cardKey) >= 0 || cardKey.indexOf(rowKey) >= 0;
  }
  /* R-12 배송비 금액 — **관리자 값에서 읽는다. 코드에 금액을 박지 않는다.**
   * (CLAUDE.md 배송 정책: 「3,500원 · 50,000원 이상 구매 시 무료」 하나뿐이고,
   *  카페24 스킨이 그 값을 관리자에서 읽어 `#freeShipGuide[data-delivery]` 로 내린다)
   *   0  = 무료  ·  양수 = 그 금액  ·  -1 = 못 읽었다(모른다) */
  function shipFee() {
    if (isFreeShip()) return 0;
    var d = captureDelivery();
    var m = String(d || '').match(/([0-9][0-9,]*)\s*\uC6D0/);
    if (!m) return -1;
    var v = parseInt(m[1].replace(/,/g, ''), 10);
    return isNaN(v) ? -1 : v;
  }

  function isFreeShip() {
    var f = document.getElementById('levelLineActive');
    return !!(f && f.classList && f.classList.contains('full'));
  }
  function isSoldout() {
    var s = $('.productAction .soldout');
    if (!s) return false;
    return !/(^|\s)displaynone(\s|$)/.test(s.className || '');
  }

  /* [13종] 「살 수 없는 페이지」인가 — 34(증정 이벤트 안내) · 91(네이버페이 즉시할인 안내) ·
   * 93(멤버십 혜택 안내)은 상품 상세 템플릿으로 렌더되지만 **판매 상품이 아니다.**
   * 카페24는 이 경우 인라인 「장바구니」에 `displaynone` 과 빈 `onclick` 을 준다.
   *   <div class="btnNormal sizeL displaynone" onclick="">장바구니</div>
   *   <div class="btnSubmit gFull sizeL relative displaynone" onclick="">구매하기</div>
   * 그런데 **하단 고정바의 「구매하기」에는 그 표시를 안 준다** (라이브 실측).
   * 12차 B안으로 리뷰 칩과 장바구니가 빠지면서, 지금은 화면 하단을 가득 채운
   * 커다란 버튼이 눌러도 아무 일도 안 하는 상태가 된다.
   * → 인라인 두 버튼이 **둘 다** 죽어 있으면 바 자체를 내린다. 되는 일만 보여준다.
   * ⚠ 품절(`isSoldout`)과는 다른 상태다 — 품절은 SOLD OUT 을 보여줘야 하지만
   *   여기는 애초에 팔지 않는 페이지라 살 수 있다는 신호 자체를 내린다.
   * ⚠ 카페24가 나중에 `onclick` 을 채워 주면 이 판정은 저절로 false 가 된다. */
  function isUnsellable() {
    var wrap = $('.buy-btn-wrap');
    if (!wrap) return false;
    /* [QA P2] 품절이면 절대 dead 로 보지 않는다.
     * 카페24가 품절을 **자식 두 버튼에 `displaynone`** 으로 표현하면 아래 판정이 참이 되어
     * 바가 통째로 내려가고 **SOLD OUT 이 안 보인다**(QA 가 DOM 합성으로 재현: dead=True,
     * display=none, SOLD OUT 노출=False). 라이브 13종에 품절이 0건이라 어느 쪽이 카페24의
     * 실제 출력인지는 확인할 수 없었다 → 확인될 때까지 품절을 우선한다. */
    if (isSoldout()) return false;
    var dead = function (el) {
      if (!el) return true;
      if (/(^|\s)displaynone(\s|$)/.test(el.className || '')) return true;
      var oc = el.getAttribute('onclick');
      return !oc || !oc.replace(/\s/g, '');
    };
    return dead($('#actionCart', wrap)) && dead($('.btnSubmit.gFull', wrap));
  }

  /* -------------------------------------------- 접근성: 구매 동선 키보드 도달
   * 실측 문제: 구매 동선에서 키보드로 닿는 컨트롤이 **0개**였다.
   *   인라인 장바구니만 진짜 `<button>` 이고 나머지는 전부 클릭 전용 요소다 —
   *   인라인 구매하기 `<div onclick>` · 바 장바구니 `<div onclick>` · 바 구매하기 `<span>`.
   *   게다가 12차 B안에서 시트가 닫혀 있으면 인라인 블록이 `display:none` 이라
   *   그 유일한 `<button>` 마저 포커스를 못 받는다 → 도달 가능 컨트롤 0.
   * → 마크업은 건드리지 않고(스킨 템플릿의 `onclick="{$action_*}"` 는 절대 손대지 않는다)
   *   런타임에 `role="button"` · `tabindex` 와 Enter/Space 핸들러만 얹는다.
   *   실제 동작은 기존 `onclick` 이 그대로 한다 — 우리가 구매 로직을 새로 만들지 않는다.
   * ⚠ 팔 수 없는 페이지(34·91·93)에서는 tabindex 를 떼어 **죽은 버튼에 포커스가 가지 않게** 한다.
   * ⚠ `display:none` 인 요소는 tabindex 가 있어도 포커스를 못 받는다(브라우저 규칙) —
   *   시트가 닫혀 있으면 바 「구매하기」로 들어가 시트를 열고, 그 안에서 이어서 도달한다. */
  var KB_SEL = [
    '.buy-btn-wrap .btnSubmit.gFull',
    '.mobile-fix-footer [class^="btn"].btnNormal:not(.jsGoReview)',
    '.mobile-fix-footer [class^="btn"].btnSubmit.jsLayerBtn'
  ];
  function kbTargets() {
    var out = [];
    KB_SEL.forEach(function (sel) {
      $$(sel).forEach(function (e) {
        if (!e || e.tagName === 'BUTTON' || e.tagName === 'A') return;  /* 이미 포커스 가능 */
        if (out.indexOf(e) < 0) out.push(e);
      });
    });
    return out;
  }
  function armKeyboard() {
    kbTargets().forEach(function (e) {
      if (e.getAttribute('data-zg-kb')) return;
      e.setAttribute('data-zg-kb', '1');
      if (!e.getAttribute('role')) e.setAttribute('role', 'button');
      on(e, 'keydown', function (ev) {
        var k = ev.key;
        if (k === 'Enter' || k === ' ' || k === 'Spacebar' || ev.keyCode === 13 || ev.keyCode === 32) {
          ev.preventDefault();
          try { e.click(); } catch (x) {}
        }
      });
    });
  }
  function setKeyboardReach(dead) {
    kbTargets().forEach(function (e) {
      if (dead) e.removeAttribute('tabindex');
      else e.setAttribute('tabindex', '0');
    });
  }

  /* --------------------------------------------------------------- 토스트 */
  var toastEl = null, toastTimer = null;
  function toast(msg) {
    try {
      if (!toastEl) {
        toastEl = el('div', 'zg-toast');
        toastEl.setAttribute('role', 'status');
        document.body.appendChild(toastEl);
      }
      toastEl.textContent = msg;
      toastEl.classList.add('zg-on');
      clearTimeout(toastTimer);
      toastTimer = setTimeout(function () { toastEl.classList.remove('zg-on'); }, 2400);
    } catch (e) {}
  }

  /* ------------------------------------------------------- 옵션 텍스트 가공 */
  /* 문자열 가공까지만 한다 — 숫자는 손대지 않는다 (K-04 AC3).
   *
   * 관리자 옵션명은 작명 규칙이 두 가지다. 둘 다 받아야 한다.
   *   A) `[지금 24%▼] 상품명 N box (무료배송) (+33,100원)`
   *   B) `상품명 [6+3] (45%할인 | 9주 | 무료배송) (+126,000원)`
   * 예전 규칙은 소괄호를 `(+N원)`·`(무료배송)` **두 형태만** 지워서 B 형의
   * `(45%할인 | 9주 | 무료배송)` 이 제목에 통째로 남았다. 더 나쁜 것은 B 형의 BEST 옵션에
   * 상품명 부분이 아예 없어서 **제목 자리에 괄호 문구가 오는 것**이었다(제목 소실).
   * 그 값은 `aria-label` 로도 흘러가 보조기술이 괄호 문구를 상품명처럼 읽는다.
   *
   * → 소괄호는 **전부** 걷어내고, 걷어낸 내용을 잃지 않게 칩으로 되돌린다.
   *   제목이 비면 대괄호 → 메타 → 원문 순으로 폴백한다. 어떤 작명에서도 제목이 비지 않는다.
   *   숫자·문구를 새로 만들지 않는다. 원문 조각을 옮겨 붙일 뿐이다. */
  function parseOptionText(raw) {
    var s = squash(raw);
    var tagM = s.match(/\[([^\]]+)\]/);
    var addM = s.match(/\(\s*\+\s*[\d,]+\s*원\s*\)/);
    var meta = [];

    var nm = s
      .replace(/\(\s*\+\s*[\d,]+\s*원\s*\)/g, ' ')      /* 추가금은 따로 칩으로 나간다 */
      .replace(/\(([^)]*)\)/g, function (_m, inner) {       /* 나머지 소괄호 = 메타 정보 */
        meta.push(inner);
        return ' ';
      })
      .replace(/\[[^\]]*\]/g, ' ')
      .replace(/🔥/g, ' ')
      .replace(/BEST/gi, ' ')
      .replace(/\s+/g, ' ')
      .trim();

    /* 메타를 `|` 로 쪼개 칩 후보로 만든다 */
    var parts = [];
    for (var i = 0; i < meta.length; i++) {
      var seg = meta[i].split('|');
      for (var j = 0; j < seg.length; j++) {
        var v = squash(seg[j]);
        if (v) parts.push(v);
      }
    }

    var bracket = tagM ? squash(tagM[1]) : '';
    var usedBracketAsName = false;
    if (!nm) {                                   /* B 형 BEST 옵션: 제목이 비는 경우 */
      if (bracket) { nm = bracket; usedBracketAsName = true; }
      else if (parts.length) nm = parts.join(' · ');
      else nm = s;
    }

    var tags = [];                               /* 강조 칩 */
    var notes = [];                              /* 보조 칩 */
    if (bracket && !usedBracketAsName) tags.push(bracket);
    for (var k = 0; k < parts.length; k++) {
      if (parts[k].indexOf('무료배송') >= 0) continue;   /* 전용 칩이 따로 있다 */
      if (/\d\s*%\s*할인/.test(parts[k])) tags.push(parts[k]);
      else notes.push(parts[k]);
    }

    return {
      raw: s,
      nm: nm,
      tags: tags,
      notes: notes,
      add: addM ? addM[0] : '',
      free: s.indexOf('무료배송') >= 0,
      best: /BEST/i.test(s) || s.indexOf('🔥') >= 0
    };
  }

  /* ================================================================== *
   *  초기화
   * ================================================================== */
  function ready(fn) {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', fn, false);
    else fn();
  }

  var root, optSel, cards = [], cardWrap = null;
  var pickedHead = null, pickedEmpty = null, tpNode = null, tpAnchor = null;
  var sumItemV = null, sumShipV = null, sumTotV = null;
  var sumListV = null, sumSaveV = null, sumListRow = null, sumSaveRow = null;
  var barV = null, barSum = null;
  var pendingSingle = null, pendingTimer = null, pickedTimer = null;
  var modeEffective = (ZG_OPT_MODE === 'single') ? 'single' : 'multi';

  ready(function () { try { init(); } catch (e) { /* 절대 페이지를 죽이지 않는다 */ } });

  function init() {
    /* 편집기에서 스크립트가 두 번 삽입돼도 카드가 두 벌 그려지지 않게 한다 */
    if (window.__ZG_DETAIL_UI__) return;
    window.__ZG_DETAIL_UI__ = 1;

    root = $('.zg-detail');
    if (!root) return;

    unlazyDetailImages();      /* 안전망: 로더가 먼저 돌았어도 회수한다 */
    /* 우리 DOMContentLoaded 리스너는 jQuery 것보다 뒤에 등록되므로, 이 시점이면
     * 스킨의 가드가 이미 지나갔다. 여기서 로더를 되살린다. */
    rearmLazyLoader();
    buildOptionCards();
    watchOptionSource();       /* [9종 복제 대비] 런타임에 옵션이 생기는 상품 대응 */
    buildPickedHead();
    buildSum();
    buildBar();
    armKeyboard();
    armSheetOpen();
    watchAppPay();
    watchSheet();
    bindFold();
    bindChips();
    bindAddProduct();
    watch();
    place();
    refresh();

    if (ZG_OPT_AUTOSELECT) scheduleAutoSelect();
  }

  /* ------------------------------------------------------ K-04 구성 카드 */
  function buildOptionCards() {
    var box = $('.productOption');
    if (!box) return;
    optSel = $('select[name^="option"]', box) || $('select[id^="product_option_id"]', box);
    if (!optSel) return;

    var opts = Array.prototype.filter.call(optSel.options || [], function (o) {
      return o && o.value && o.value !== '*' && o.value !== '**' && !o.disabled;
    });
    if (!opts.length) return;

    cardWrap = el('div', 'zg-opts');
    cardWrap.setAttribute('role', 'group');
    cardWrap.setAttribute('aria-label', '구성 선택');

    var title = el('div', 'zg-opts__title', '몇 박스로 하시겠어요?');

    cards = opts.map(function (o) {
      var p = parseOptionText(o.text);
      var b = el('button', 'zg-opt');
      b.type = 'button';
      /* [근거] `aria-pressed` 는 "다시 누르면 해제된다"는 토글 약속이다.
       * R-2 이후 담긴 카드를 다시 누르면 실제로 그 구성이 빠진다 — 다만 그것은
       * 카페24가 그 행에 그려 준 **자기 삭제 컨트롤**을 누르는 경로라, 컨트롤이 없는
       * 상품에서는 해제되지 않고 안내로 폴백한다(`unpick()` → false). 즉 약속이
       * **상품에 따라 지켜지기도 하고 안 지켜지기도 한다** → 고정 속성으로 걸지 않는다.
       * 상태와 "누르면 일어날 일"은 data 속성(CSS 후크) + 눈에 보이는 텍스트 +
       * `refresh()` 가 매번 다시 쓰는 aria-label 로 사실대로 알린다
       * (「선택 해제」/「이미 담김」/「장바구니에 담기」 — 아래 `refresh()` 참조).
       * <button> 의 암묵 role 이 이미 button 이라 role="button" 도 넣지 않는다. */
      b.setAttribute('data-zg-on', '');
      b.setAttribute('data-zg-value', o.value);
      b.setAttribute('data-zg-key', keyOf(o.text));

      b.appendChild(el('span', 'zg-opt__tick'));

      var body = el('span', 'zg-opt__body');
      body.appendChild(el('span', 'zg-opt__nm', p.nm));

      var mt = el('span', 'zg-opt__mt');
      p.tags.forEach(function (v) { mt.appendChild(el('em', 'zg-opt__tag', v)); });
      if (p.free) mt.appendChild(el('em', 'zg-opt__free', '무료배송'));
      p.notes.forEach(function (v) { mt.appendChild(el('em', 'zg-opt__add', v)); });
      if (p.add) mt.appendChild(el('em', 'zg-opt__add', p.add));
      var st = el('em', 'zg-opt__state', '');
      mt.appendChild(st);
      body.appendChild(mt);
      b.appendChild(body);

      if (p.best) b.appendChild(el('span', 'zg-opt__flag', '가장 많이 담아요'));

      b._zgState = st;
      b._zgBest = p.best;
      b._zgName = p.nm;

      /* 접근성 라벨은 카드에 보이는 정보를 그대로 읽힌다 — 이름만 읽고 할인율·추가금이
       * 빠지면 보조기술 사용자만 가격 정보를 못 듣는다. 금액은 계산하지 않고 원문 문자열이다. */
      var lab = [p.nm];
      p.tags.forEach(function (v) { lab.push(v); });
      if (p.free) lab.push('무료배송');
      p.notes.forEach(function (v) { lab.push(v); });
      if (p.add) lab.push('추가 ' + p.add.replace(/[()+\s]/g, ''));
      b._zgLabel = lab.filter(Boolean).join(', ');
      on(b, 'click', function () { pick(b); });
      cardWrap.appendChild(b);
      return b;
    });

    var hint = el('p', 'zg-opt-hint');
    /* `role="status"`(= `aria-live="polite"`)를 붙여 담긴 개수 안내가 낭독되게 한다.
     * 시각 결과는 0 — 원래 화면에 보이던 문장을 보조기술에도 같은 시점에 전달할 뿐이다.
     * polite 라 읽던 것을 가로채지 않는다. */
    hint.setAttribute('role', 'status');
    hint.hidden = true;

    /* (검수 설계서에 없던 UI 「옵션을 직접 선택」 버튼은 삭제했다.
     *  설계 문서 어디에도 없었고 조작점 이원화 금지 규칙과도 충돌했다.) */

    box.insertBefore(title, box.firstChild);
    box.insertBefore(cardWrap, title.nextSibling);
    box.insertBefore(hint, cardWrap.nextSibling);

    /* select 는 DOM 에 그대로 두고 시각적으로만 클립한다 (display:none 금지) */
    optSel.classList.add('zg-a11y-hide');

    cardWrap._zgHint = hint;
  }

  /* [9종 복제 대비] `buildOptionCards()` 는 DOMContentLoaded 시점의 select.options 를
   * 한 번만 읽는다. 11번은 option_type="T"(서버 렌더)라 정상이지만, option_type="F"(품목 조합)
   * 상품은 카페24 옵션 스크립트가 나중에 <option> 을 채워 넣어 **카드가 0장**이 된다.
   * → 카드를 못 만들었으면 `.productOption` 을 관찰하다가 옵션이 생기는 순간 한 번 더 짓는다. */
  function watchOptionSource() {
    if (cards.length) return;
    var box = $('.productOption');
    var MO = window.MutationObserver || window.WebKitMutationObserver;
    if (!box || !MO) return;
    var tries = 0;
    var mo = new MO(function () {
      if (cards.length || ++tries > 40) { mo.disconnect(); return; }
      buildOptionCards();
      if (cards.length) { mo.disconnect(); refresh(); }
    });
    mo.observe(box, { childList: true, subtree: true });
    setTimeout(function () { try { mo.disconnect(); } catch (e) {} }, 15000);
  }

  function pick(card) {
    if (!optSel || !card) return;
    var val = card.getAttribute('data-zg-value');
    var key = card.getAttribute('data-zg-key');
    var rows = pickedRows();
    var already = rows.some(function (r) { return rowMatches(r.key, key); });
    clearTimeout(pickedTimer);   /* 새 조작이 들어오면 직전 담기 알림 예약은 취소한다 */

    /* 담긴 카드를 다시 누르면 그 구성이 빠진다.
     * 담기/빼기가 같은 조작점이라 「담을 땐 카드, 뺄 땐 아래 목록」이라는 이원화가 사라진다.
     * 복수 담기(결정 #1 `multi`)는 그대로다 — 다른 카드는 계속 더 담을 수 있다. */
    if (already) {
      if (unpick(key)) { toast('구성을 뺐어요.'); return; }
      /* 삭제 컨트롤을 못 찾은 상품 — 예전 동작(안내)으로 안전 폴백한다. DOM 을 직접 뜯지 않는다. */
      if (modeEffective === 'multi') toast('이미 담겨 있어요. 빼시려면 아래 목록에서 지워 주세요.');
      return;
    }

    try {
      optSel.value = val;
      optSel.dispatchEvent(new Event('change', { bubbles: true }));
    } catch (e) {
      /* 구형 브라우저 */
      try {
        var ev = document.createEvent('HTMLEvents');
        ev.initEvent('change', true, false);
        optSel.value = val;
        optSel.dispatchEvent(ev);
      } catch (e2) { return; }
    }

    /* 담기 성공도 알린다. 해제(`구성을 뺐어요.`)에만 토스트가 있어 알림이 비대칭이었고,
     * 보조기술 사용자는 "빠졌다"는 알지만 "담겼다"는 알 수 없었다.
     * 토스트 노드에는 이미 `role="status"` 가 붙어 있다.
     * ⚠ 카페24가 행을 만드는 것은 비동기다 → **행이 실제로 생긴 것을 확인한 뒤에만** 알린다.
     *   (지어낸 성공을 말하지 않는다. 실패하면 아무 말도 하지 않는다.) */
    pickedTimer = setTimeout(function () {
      if (pickedRows().some(function (r) { return rowMatches(r.key, key); })) {
        toast('구성을 담았어요.');
      }
    }, 400);

    if (modeEffective === 'single') {
      pendingSingle = key;
      clearTimeout(pendingTimer);
      pendingTimer = setTimeout(function () { pendingSingle = null; }, 2500);
    }
  }

  /* 카페24가 그 행에 직접 그려 넣은 **자기 삭제 컨트롤**을 찾는다.
   * 스킨 원문(옵션 스크립트)의 위임 핸들러가 이 요소를 받는다:
   *   `EC$(document).on('click', '#totalProducts a.delete', …)` → 내부 `.option_box_del` 클릭
   *   `EC$(document).on('click', '.option_box_del', …)`          → 실제 삭제 + 데이터 정리
   * 즉 **고객이 직접 누르는 그 버튼**을 누르는 것이지, 1.9MB 옵션 스크립트의 내부 상태를
   * 우리가 뒤에서 고치는 것이 아니다.
   * ⚠ `tr.option_product`(본품)에만 쓴다. 추가상품 행은 `.option_add_box_del` 로 경로가
   *   달라 여기 걸리지 않으며, 카드는 본품 구성만 다룬다(설계 규칙). */
  function delControl(row) {
    return $('a.delete, .option_box_del, a[class*="delete"], a[class*="Del"]', row);
  }

  /* R-2 재탭 해제 — 그 구성의 행을 카페24 삭제 컨트롤로 지운다.
   * 수량이 2 이상이어도 **그 구성 전체**를 뺀다. 근거: 카드는 담기/빼기 스위치이고,
   * 수량 조절은 아래 「선택한 구성」의 스테퍼가 맡는다(조작점 이원화 금지 규칙).
   * 컨트롤을 하나도 못 찾으면 아무것도 하지 않고 false 를 돌려 호출부가 폴백하게 한다. */
  function unpick(key) {
    var hits = pickedRows().filter(function (r) { return rowMatches(r.key, key); });
    if (!hits.length) return false;
    var done = 0;
    hits.forEach(function (r) {
      var del = delControl(r.el);
      if (!del) return;
      try { del.click(); done++; } catch (e) {}
    });
    if (!done) return false;
    schedule();      /* 총액·무료배송·하단바·빈 상태 안내문을 즉시 다시 맞춘다 */
    return true;
  }

  /* 'single' 경로 — 카페24가 새 행을 만든 뒤, 남은 다른 행을 카페24 자신의
   * 삭제 컨트롤로 지운다. 삭제 컨트롤을 못 찾으면 multi 로 안전 폴백한다. */
  function pruneRows(keepKey) {
    var rows = pickedRows();
    if (rows.length <= 1) return true;
    var kept = false, failed = false;
    rows.forEach(function (r) {
      if (!kept && rowMatches(r.key, keepKey)) { kept = true; return; }
      var del = delControl(r.el);
      if (del) { try { del.click(); } catch (e) { failed = true; } }
      else failed = true;
    });
    if (failed) {
      modeEffective = 'multi';
      showHint('구성을 여러 개 담을 수 있어요. 필요 없는 구성은 아래 목록에서 지워 주세요.');
    }
    return !failed;
  }

  function showHint(msg) {
    if (!cardWrap || !cardWrap._zgHint) return;
    var h = cardWrap._zgHint;
    if (msg) { h.textContent = msg; h.hidden = false; }
    else { h.textContent = ''; h.hidden = true; }
  }

  function scheduleAutoSelect() {
    var tries = 0;
    function attempt() {
      tries++;
      if (!cards.length) return;
      if (pickedRows().length > 0) return;
      var target = null;
      for (var i = 0; i < cards.length; i++) { if (cards[i]._zgBest) { target = cards[i]; break; } }
      if (!target) target = cards[1] || cards[0];
      pick(target);
      if (tries < 3) setTimeout(function () { if (pickedRows().length === 0) attempt(); }, 700);
    }
    if (document.readyState === 'complete') setTimeout(attempt, 400);
    else on(window, 'load', function () { setTimeout(attempt, 400); });
  }

  /* --------------------------------------------- K-05 선택 목록 · 위치 이동 */
  function buildPickedHead() {
    tpNode = document.getElementById('totalProducts');
    if (!tpNode || !tpNode.parentNode) return;

    tpAnchor = document.createComment('zg-totalproducts-home');
    tpNode.parentNode.insertBefore(tpAnchor, tpNode);

    pickedHead = el('div', 'zg-picked-head');
    pickedHead.appendChild(el('div', 'zg-picked-head__t', '선택한 구성'));
    pickedEmpty = el('div', 'zg-picked-head__empty', '구성을 선택해 주세요.');
    pickedHead.appendChild(pickedEmpty);
    tpNode.parentNode.insertBefore(pickedHead, tpNode);
  }

  /* ≤767px 에서만 구성카드 바로 아래로 옮긴다. 마크업·id·module 은 건드리지 않고
   * 노드만 이동한다. 되돌리기는 ZG_MOVE_TOTALPRODUCTS = false 한 줄. */
  function place() {
    if (!tpNode || !pickedHead || !tpAnchor) return;
    try {
      var mobile = (window.innerWidth || document.documentElement.clientWidth) <= 767;
      var po = $('.productOption');
      if (ZG_MOVE_TOTALPRODUCTS && mobile && po && po.parentNode) {
        if (pickedHead.previousSibling !== po || tpNode.previousSibling !== pickedHead) {
          po.parentNode.insertBefore(pickedHead, po.nextSibling);
          po.parentNode.insertBefore(tpNode, pickedHead.nextSibling);
        }
      } else if (tpAnchor.parentNode) {
        if (tpNode.nextSibling !== tpAnchor || pickedHead.nextSibling !== tpNode) {
          tpAnchor.parentNode.insertBefore(pickedHead, tpAnchor);
          tpAnchor.parentNode.insertBefore(tpNode, tpAnchor);
        }
      }
    } catch (e) {}
  }

  /* ---------------------------------------------------------- K-08 합계 */
  function sumRow(label, cls) {
    var row = el('div', 'zg-sum__row' + (cls ? ' ' + cls : ''));
    row.appendChild(el('span', null, label));
    var v = el('span', 'zg-sum__v', '—');
    row.appendChild(v);
    return { row: row, v: v };
  }

  /* ------------------------------------------------ K-08b 정가 · 할인금액
   * 2026-09-11 개편: "정가 > 할인금액(마이너스) > 총 결제금액" 으로 보여
   * 고객이 얼마나 이득인지 느끼게 한다.
   *
   * ⚠ **추정하지 않는다.** 할인율(`지금 24%▼`)에서 역산하면 원 단위가 안 맞는다
   *    (실측: 2box 68,000 / 0.76 = 89,473 ≠ 정가 90,000 — 527원 오차).
   *    가격을 틀리게 보여주느니 안 보여주는 게 낫다.
   *
   * 정확히 맞는 경로만 쓴다 — 카페24 시중가(`#span_product_price_custom`) × 수량.
   *    실측(칼륨 11): 시중가 45,000
   *      1box 34,900  정가  45,000  할인 10,100 = 22%  ✓ 화면 표기 22%
   *      2box 68,000  정가  90,000  할인 22,000 = 24%  ✓ 24%
   *      3box 97,000  정가 135,000  할인 38,000 = 28%  ✓ 28%
   *      5box 149,000 정가 225,000  할인 76,000 = 34%  ✓ 34%
   *    네 옵션 전부 표기 할인율과 정확히 일치한다.
   *
   * 한 행이 몇 개 묶음인지는 행 이름의 `N box` 로 읽는다. 못 읽으면 1 로 본다.
   * 시중가가 없거나 할인이 0 이하이면 두 줄을 **감춘다** — 없는 할인을 만들지 않는다. */
  /* 숫자 → "12,345원". `toLocaleString` 은 구형 웹뷰에서 구분자를 안 넣는 경우가 있어 직접 넣는다. */
  function won(n) {
    var v = Math.round(Number(n) || 0);
    return String(v).replace(/\B(?=(\d{3})+(?!\d))/g, ',') + '\uC6D0';
  }

  function listUnitPrice() {
    var e = document.getElementById('span_product_price_custom');
    if (!e) return 0;
    var d = String(e.textContent || '').replace(/[^0-9]/g, '');
    return d ? parseInt(d, 10) : 0;
  }

  /* ═══════════════════════════════════════════════════════════════════════
   *  R-15 (2026-09-11) 정가 · 할인금액 — **검산에 통과한 값만 보여준다**
   *
   *  카페24가 주는 것은 이것뿐이다:
   *    · 시중가(`#span_product_price_custom`)  — **기본 구성 1개 기준**
   *    · 행 가격(`td.right .price`)            — 판매가 + 옵션 추가금
   *  옵션별 시중가는 어디에도 없다. 그래서 정가는 **추정**할 수밖에 없고,
   *  추정한 값은 **반드시 검산해서 맞을 때만** 화면에 올린다.
   *
   *  검산 기준은 **페이지가 스스로 광고하는 할인율**이다
   *  (옵션 이름 안의 「25%할인」·「22%▼」). 시중가 × N 으로 잡은 정가가
   *  그 할인율을 **그대로 재현**해야 통과다.
   *
   *  앞선 두 번의 오류가 전부 「검산 없이 추정」 때문이었다:
   *    ① 배수를 못 읽으면 조용히 1 로 가정 → 104 에서 단위가 다른 두 값을 빼
   *       가짜 할인 39,000원(정가 294,000 은 1개분, 상품금액 255,000 은 6set분).
   *    ② 배수를 행 **전체 텍스트**에서 찾아 **상품명**의 「칼륨(2box)」를 집음
   *       → 63 에서 정가 278,000(=139,000×2) · 할인 −174,000.
   *         실제는 정가 139,000 · 할인 35,000.
   *  이제 배수는 이름에서 읽지 않는다. 1..20 을 넣어 보고 **할인율이 맞는 N** 만 쓴다.
   *
   *  ⚠ 옵션 이름은 행 전체 텍스트가 아니라 `p.product span` 이다 —
   *    전체 텍스트에는 상품명이 앞에 붙어 상품명 속 숫자를 집는다(②의 원인).
   *  ⚠ 맞는 N 이 없으면 **모른다**. 두 줄을 접는다. 지어내지 않는다.
   * ═══════════════════════════════════════════════════════════════════════ */

  var LIST_N_MAX = 20;

  /* ── R-16 (2026-09-11) 옵션별 정상가 표 ──────────────────────────────────
   * 어떤 상품은 옵션 정가가 **시중가의 배수가 아니다.** 그런 상품은 위 검산으로
   * 아무 N 도 못 찾아 정가·할인을 못 보여준다. 그때만 이 표를 쓴다.
   *
   * 값의 출처는 **확정 가격표(운영 제공) + 상세페이지 안내 문구**다(둘을 대조해 일치 확인).
   * 페이지에서 읽을 수 없는 값이라 여기에 적는 수밖에 없다.
   *
   * ⚠ 이 표를 **믿고 쓰지 않는다.** 표의 `sale`(장바구니에 담기는 금액)이 라이브
   *   실제 행 가격과 **한 원이라도 다르면 그 옵션은 정가·할인을 감춘다.**
   *   가격이 바뀌었는데 표만 남아 옛 정가를 보여주는 사고를 막는다.
   *   (실제로 잡혔다 — 104 「붓기 파우더 6set」 은 안내 138,900원인데 옵션 추가금이
   *    12set 값(+162,300)으로 들어가 있어 255,000원이 담긴다. 관리자 수정 전까지 감춘다.)
   * ⚠ `list` 는 **정상가**다. 쿠폰(주문서에서 고객이 직접 적용)은 넣지 않는다 —
   *   합계의 「총 결제금액」은 지금 실제로 결제되는 금액이어야 한다.
   * ⚠ 행사 종료 시 이 블록을 지운다. 지워도 다른 상품은 영향이 없다. */
  var LIST_TABLE = {
    104: [
      { k: '\uBD93\uAE30\uD30C\uC6B0\uB3546set',        sale: 138900, list: 270000 },
      { k: '\uBD93\uAE30\uD30C\uC6B0\uB35412set',       sale: 255000, list: 540000 },
      { k: '\uB9C8\uADF8\uB124\uC2984set',               sale:  92700, list: 196000 },
      { k: '\uBE44\uD0C0\uBBFCB\uCEF4\uD50C\uB809\uC2A44set', sale: 92700, list: 196000 },
      { k: '\uBD93\uAE30\uBD80\uC2A4\uD1303set',        sale: 212400, list: 417000 },
      { k: '\uBD93\uAE30\uBD80\uC2A4\uD1305set',        sale: 324900, list: 695000 },
      { k: '\uD37C\uD3EC\uBA3C\uC2A4\uBD80\uC2A4\uD1303set', sale: 92700, list: 294000 },
      { k: '\uCE7C+\uB9C8+\uBE443set',                    sale: 212700, list: 429000 }
    ]
  };

  function productNo() {
    if (typeof window.iProductNo === 'number' && window.iProductNo > 0) return window.iProductNo;
    var m = String(location.search || '').match(/product_no=(\d+)/);
    if (m) return parseInt(m[1], 10);
    m = String(location.pathname || '').match(/\/(\d+)\/?$/);
    return m ? parseInt(m[1], 10) : 0;
  }

  /* 표에서 이 옵션을 찾는다. 못 찾으면 null, 찾았지만 가격이 다르면 'stale' */
  function tableList(optName, perPrice) {
    var t = LIST_TABLE[productNo()];
    if (!t) return null;
    var key = String(optName || '').replace(/\s+/g, '');
    for (var i = 0; i < t.length; i++) {
      if (key.indexOf(t[i].k) < 0) continue;
      return (Math.round(perPrice) === t[i].sale) ? t[i].list : 'stale';
    }
    return null;
  }


  function rateOf(name) {
    var m = String(name || '').match(/(\d{1,2})\s*%/);
    if (!m) return -1;
    var v = parseInt(m[1], 10);
    return (v >= 1 && v <= 99) ? v : -1;
  }

  function rowPrice(r) {
    var e = $('td.right strong.price', r) || $('td.right .price', r) || $('td.right', r);
    if (!e) return 0;
    var d = String(e.textContent || '').replace(/[^0-9]/g, '');
    return d ? parseInt(d, 10) : 0;
  }

  function rowQty(r) {
    var qi = $('input.quantity_opt, input[name^="quantity_opt"]', r);
    var d = qi ? String(qi.value || '').replace(/[^0-9]/g, '') : '';
    var q = d ? parseInt(d, 10) : 1;
    return q > 0 ? q : 1;
  }

  function rowListPrice(r, unit) {
    var price = rowPrice(r);
    if (!price) return 0;

    /* 추가 구성 상품은 시중가가 따로 없다 → 정가 = 판매가(할인 0)로 넣는다.
     * 그래야 추가상품을 담았다고 본품 할인 표시가 통째로 사라지지 않는다. */
    if (/(^|\s)add_product(\s|$)/.test(r.className || '')) return price;

    var sp = $('p.product span', r);
    var qty = rowQty(r);
    var per = price / qty;

    /* 표에 있는 상품이면 표가 우선한다 — 단, 가격이 어긋나면 감춘다 */
    var tl = tableList(sp ? sp.textContent : '', per);
    if (tl === 'stale') return 0;
    if (tl) return tl * qty;

    var rate = rateOf(sp ? sp.textContent : '');
    if (rate < 0 || !unit) return 0;
    var best = 0;
    for (var n = 1; n <= LIST_N_MAX; n++) {
      var list = unit * n;
      if (list <= per) continue;
      if (Math.round((1 - per / list) * 100) !== rate) continue;
      if (best) return 0;            /* 후보가 둘이면 확정 못 한다 */
      best = list;
    }
    return best ? best * qty : 0;
  }

  function listTotal() {
    var unit = listUnitPrice();
    var rows = visibleRows();
    if (!rows.length) return 0;
    var sum = 0, ok = true;
    rows.forEach(function (r) {
      var v = rowListPrice(r, unit);
      if (!v) { ok = false; return; }
      sum += v;
    });
    return ok ? sum : 0;
  }


  function buildSum() {
    var tp = document.getElementById('totalPrice');
    if (!tp || !tp.parentNode) return;
    var box = el('div', 'zg-sum');

    var L = sumRow('정가', 'zg-sum__row--list');
    var S = sumRow('할인금액', 'zg-sum__row--save');
    var a = sumRow('상품 금액');
    var b = sumRow('배송비');
    var c = sumRow('총 결제금액', 'zg-sum__row--tot');
    sumListV = L.v; sumSaveV = S.v;
    sumListRow = L.row; sumSaveRow = S.row;
    sumItemV = a.v; sumShipV = b.v; sumTotV = c.v;

    box.appendChild(L.row);
    box.appendChild(S.row);
    box.appendChild(a.row);
    box.appendChild(b.row);
    box.appendChild(c.row);
    box.appendChild(el('p', 'zg-sum__note', '최종 결제금액은 주문서에서 확인하실 수 있습니다.'));

    tp.parentNode.insertBefore(box, tp.nextSibling);
  }

  /* ------------------------------------------------------ K-12 하단 고정바 */
  function buildBar() {
    var bar = $('.mobile-fix-footer');
    if (!bar) return;
    var wrap = el('div', 'zg-bar__sum');
    wrap.appendChild(el('span', null, '총 구매 금액'));
    barV = el('strong', 'zg-bar__v zg-bar__v--hint', '구성을 선택해 주세요');
    wrap.appendChild(barV);
    barSum = wrap;
    bar.insertBefore(wrap, bar.firstChild);

    /* 품절 대체 슬롯 — 원본 「구매하기」 노드는 삭제하지 않고 CSS 로 감춘다 */
    var so = el('span', 'zg-bar__soldout', 'SOLD OUT');
    so.setAttribute('aria-disabled', 'true');
    bar.appendChild(so);
  }

  /* --------------------------------------------- K-12c 시트 열기 보정
   * 2026-09-11 개편으로 상단 인라인 구매 블록을 감췄다. 그런데 스킨의
   * `mobileLayerOn()`(moa/js/product/detail.js) 은 이렇게 생겼다:
   *
   *     if ($('.jsMobileLayer').hasClass('fixed')) { 시트를 연다 }
   *     else { $('.buy-btn-wrap').find('.btnSubmit.gFull.sizeL').trigger('click'); }
   *
   * 페이지 상단에는 `.fixed` 가 없어 **인라인 구매 버튼을 대신 누른다.**
   * 그 버튼이 이제 숨어 있으니 옵션이 안 골라진 채로 결제가 시도돼
   * 「옵션을 선택해 주세요」 만 뜨고 끝난다 — 구매 경로가 막힌다.
   *
   * → 하단바 클릭이 **스킨 핸들러에 닿기 전에**(캡처 단계) `.fixed` 를 붙여
   *   스킨이 스스로 시트 경로를 타게 한다. 스킨 코드는 건드리지 않는다. */
  function armSheetOpen() {
    var bar = $('.mobile-fix-footer');
    if (!bar) return;
    on(bar, 'click', function (e) {
      var t = e.target;
      var btn = t && t.closest ? t.closest('.jsLayerBtn') : null;
      if (!btn) return;
      /* 판매 상품이 아닌 페이지(34·91·93 등)에서는 열지 않는다 —
       * 그 페이지의 바는 `zg-bar--dead` 로 이미 내려가 있고, 시트를 열면
       * 팔지 않는 상품에 결제 UI 만 띄우게 된다. */
      if (bar.classList.contains('zg-bar--dead') ||
          (root && root.classList.contains('zg-unsellable'))) return;
      var layer = $('.mobile-layer');
      if (layer && layer.classList && !layer.classList.contains('fixed')) {
        layer.classList.add('fixed');
      }
    }, true);
  }

  /* ------------------------------------------- R-12 간편결제 앱 블록 차단
   * 카페24 「네이버페이 구매」·「카카오 톡체크아웃」 앱은 마크업이 아니라
   * **런타임 스크립트**로 버튼을 만든다 (실측, 라이브 소스):
   *     EC_CHECKOUT_TARGET_DIV.parent().append('<div id="appPaymentButtonBox" …>')
   *     $("#appPaymentButtonBox").append(<div id="kakao-checkout-button">)
   *     EC$("#NaverChk…").length == 0  →  다시 append
   * 그래서 `product/detail.html` 에서 훅을 지워도 **페이지가 뜨면 되살아난다.**
   * 2026-09-11 개편 요건(네이버페이·카카오페이·찜 제거)을 만족시키려면 여기서 막아야 한다.
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
  var APPPAY_SEL = '#appPaymentButtonBox, [id^="NaverChk"], #kakao-checkout-button';

  /* R-13 「친구 초대」·「적립금혜택 6,000원」 배지 — 외부 추천 앱이 `body` 에 붙이는
   * 떠 있는 런처다. 화면 오른쪽 아래에 뜨는데 그 자리가 하필 구매 버튼·합계 위라
   * 「할인금액」·「상품 금액」 숫자를 덮었다(실기기 확인 2026-09-11).
   * → **상세페이지에서만** 내린다. 다른 페이지에서는 그대로 뜬다.
   * ⚠ 여기서도 노드를 지우지 않는다 — 앱이 자기 노드를 다시 찾는다. */
  var OVERLAY_SEL = '#incento-launcher, #incento-widget, [class*="incento_widget__launcher"]';

  function killAppPay() {
    var box = root ? root : document;
    /* 추천 앱 런처는 `body` 직속이라 `.zg-detail` 안에서 못 찾는다 — 문서 전체에서 잡되,
     * 이 스크립트는 상세페이지에서만 도므로 다른 페이지에는 영향이 없다. */
    if (root) {
      $$(OVERLAY_SEL, document).forEach(function (n) {
        if (n.getAttribute('data-zg-off') === '1') return;
        try { n.style.setProperty('display', 'none', 'important'); } catch (e) { n.style.display = 'none'; }
        n.setAttribute('data-zg-off', '1');
      });
    }
    $$(APPPAY_SEL, box).forEach(function (n) {
      if (n.getAttribute('data-zg-off') === '1') return;
      try { n.style.setProperty('display', 'none', 'important'); } catch (e) { n.style.display = 'none'; }
      n.setAttribute('data-zg-off', '1');
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

  /* ------------------------------------------------- R-12 시트 바닥 실측
   * 열린 시트에서 합계는 `position:absolute; bottom:<구매 버튼 블록 높이>` 로 얹힌다.
   * 그 높이를 86px 로 굳혀 뒀었는데, 합계가 5줄로 늘고 앱 블록이 주입되면서 전제가 깨졌다
   * (2026-09-11 실기기 확인: 「할인금액」 줄이 버튼 패널에 잘려 있었다).
   * → 굳히지 않고 잰다. 값은 `.mobile-layer` 의 CSS 변수로 내려보낸다. */
  function fitSheet() {
    var layer = $('.mobile-layer');
    if (!layer || !layer.classList) return;
    var open = layer.classList.contains('fixed') && layer.classList.contains('on');
    if (!open) {
      layer.style.removeProperty('--zg-act-h');
      layer.style.removeProperty('--zg-tub-pb');
      return;
    }
    var act = $('.infoArea-footer .productAction', layer);
    if (!act) return;
    var ah = Math.round(act.getBoundingClientRect().height);
    if (!(ah > 0)) return;
    var sum = $('.infoArea-footer .zg-sum', layer);
    var sh = sum ? Math.round(sum.getBoundingClientRect().height) : 0;
    layer.style.setProperty('--zg-act-h', ah + 'px');
    layer.style.setProperty('--zg-tub-pb', (ah + sh + 18) + 'px');
  }

  function watchSheet() {
    var layer = $('.mobile-layer');
    if (!layer) return;
    var MO = window.MutationObserver || window.WebKitMutationObserver;
    if (MO) {
      var mo = new MO(function () { fitSheet(); });
      try { mo.observe(layer, { attributes: true, attributeFilter: ['class'] }); } catch (e) {}
    }
    on(window, 'resize', fitSheet);
    on(window, 'orientationchange', fitSheet);
    fitSheet();
  }

  /* ------------------------------------------------- K-09 상세 펼침 (접기 폐지)
   * 2026-09-11 개편: 상세페이지는 기본값으로 모두 펼친다.
   * 「상세 정보 모두 보기」 버튼은 마크업에서 제거했다. 여기서는 캐시된 예전
   * 마크업이 남아 있는 경우까지 확실히 펼치고, 남은 버튼이 있으면 치운다. */
  function bindFold() {
    var fold = $('.zg-fold');
    if (!fold) return;
    if (!fold.id) fold.id = 'zgFold';
    fold.classList.add('zg-open');

    var veil = $('.zg-veil');
    if (veil && veil.parentNode) veil.parentNode.removeChild(veil);

    /* [근거] 접힌 동안 지연 로딩이 멈춰 있던 이미지를 바로 올린다 —
     * 예전 판은 버튼 클릭이 그 시점이었다. */
    if (typeof unlazyDetailImages === 'function') {
      try { unlazyDetailImages(); } catch (e) {}
    }
  }

  /* ---------------------------------------------------- K-10 바로가기 칩 */
  function bindChips() {
    $$('[data-zg-tab]').forEach(function (chip) {
      on(chip, 'click', function () {
        var id = chip.getAttribute('data-zg-tab');
        var tab = $('.detail-tab__item[data-link="' + id + '"]');
        if (tab) { try { tab.click(); return; } catch (e) {} }
        var target = document.getElementById(id);
        if (target && target.scrollIntoView) target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
    });
  }

  /* -------------------------------------------------- K-06 세트 구성 상품
   * 추가 구성 상품(`.productSet.additional`)은 2026-09-11 로 마크업에서 제거됐다.
   * 남은 세트상품(`module="product_setproduct"`)에는 같은 표시 규칙이 필요하다. */
  function bindAddProduct() {
    on(document, 'change', function (e) {
      var t = e.target;
      if (!t || t.tagName !== 'SELECT') return;
      var li = t.closest ? t.closest('.productSet .product > li') : null;
      if (!li) return;
      var v = t.value;
      if (v && v !== '*' && v !== '**') li.setAttribute('data-zg-picked', '1');
      else li.removeAttribute('data-zg-picked');
    });
  }

  /* ------------------------------------------------------------- 관측 */
  var rafId = 0;
  function schedule() {
    if (rafId) return;
    rafId = (window.requestAnimationFrame || function (f) { return setTimeout(f, 16); })(function () {
      rafId = 0;
      try { refresh(); } catch (e) {}
    });
  }

  function watch() {
    /* K-08 AC8: 총액 갱신은 MutationObserver 로만 처리한다. setInterval 폴링 없음. */
    var MO = window.MutationObserver || window.WebKitMutationObserver;
    if (!MO) return;

    var tn = totalNode();
    var totalWrap = $('#totalPrice .total') || (tn && tn.parentNode);
    if (totalWrap) {
      new MO(schedule).observe(totalWrap, { childList: true, characterData: true, subtree: true });
    }

    if (tpNode) {
      new MO(function () {
        if (pendingSingle) {
          var k = pendingSingle;
          var has = pickedRows().some(function (r) { return rowMatches(r.key, k); });
          if (has) { pendingSingle = null; clearTimeout(pendingTimer); pruneRows(k); }
        }
        schedule();
      }).observe(tpNode, { childList: true, subtree: true });
    }

    var layer = $('.mobile-layer');
    if (layer) {
      new MO(function () {
        if (!root) return;
        root.classList.toggle('zg-sheet-open', layer.classList.contains('on'));
      }).observe(layer, { attributes: true, attributeFilter: ['class'] });
    }

    var action = $('.productAction');
    /* [QA P3] `onclick` 도 본다 — `isUnsellable()` 이 그 속성을 읽는데 관찰하지 않으면
     * 「카페24가 나중에 onclick 을 채워 주면 판정이 저절로 풀린다」는 약속이 지켜지지 않는다
     * (실측: displaynone 만 제거하면 회복되지만 onclick 만 채우면 dead 가 그대로였다). */
    if (action) new MO(schedule).observe(action, { attributes: true, subtree: true, attributeFilter: ['class', 'onclick'] });

    var ship = document.getElementById('levelLineActive');
    if (ship) new MO(schedule).observe(ship, { attributes: true, attributeFilter: ['class', 'style'] });

    var rt = null;
    on(window, 'resize', function () {
      clearTimeout(rt);
      rt = setTimeout(function () { place(); schedule(); }, 150);
    });
  }

  /* ------------------------------------------------------------- 렌더 */
  function refresh() {
    if (!root) return;
    var t = totalText();
    var num = totalNum();
    var rows = pickedRows();

    /* [근거] 추가상품 행도 "담긴 것"이다. 여기서 0 이어야만 안내문을 보여준다. */
    root.classList.toggle('zg-picked-0', visibleRows().length === 0);

    /* 추가상품 행의 「추가」 구분은 CSS 생성 콘텐츠(`tr.add_product td .product::before`)
     * 하나뿐이다. CSS 가 적용되지 않는 조건(리더 모드·고대비·스타일 차단)에서는
     * 본품과 추가상품이 완전히 같아 보이고 같이 읽힌다 — 결제 직전 목록에서 오해가 된다.
     * → 같은 뜻의 **실텍스트**를 클립 유틸로 넣어 이중화한다. 시각 결과 변화 0
     *   (칩은 계속 `::before` 가 그린다). 중복 삽입은 클래스로 막는다. */
    $$('#totalProducts tr.add_product').forEach(function (r) {
      if (r.id === 'totalProductsOption') return;
      var pd = $('td .product', r);
      if (!pd || $('.zg-add-flag', pd)) return;
      pd.insertBefore(el('span', 'zg-add-flag zg-a11y-hide', '추가 구성 상품, '), pd.firstChild);
    });
    /* K-12 AC7 문언대로 `.mobile-fix-footer` 에 `zg-bar--soldout` 을 붙인다
     * (이전 판에서는 `.zg-detail` 에 `zg-soldout` 이라 AC 문언과 어긋나 있었다). */
    var bar = $('.mobile-fix-footer');
    if (bar) bar.classList.toggle('zg-bar--soldout', isSoldout());
    /* 바만 내리면 「상품 금액 —」·「총 구매 금액 0원」·「구성을 선택해 주세요」가 남아
     * 팔지 않는 페이지에 결제 UI 만 떠 있게 된다(QA P3). 루트에도 표시를 붙여 함께 내린다. */
    var dead = isUnsellable();
    if (bar) bar.classList.toggle('zg-bar--dead', dead);
    if (root) root.classList.toggle('zg-unsellable', dead);
    armKeyboard();          /* 바가 나중에 그려지는 경우 대비 */
    setKeyboardReach(dead);

    /* 정가·할인금액 — 정확히 계산되는 경우에만 보여준다 */
    var listSum = num > 0 ? listTotal() : 0;
    var save = listSum > num ? listSum - num : 0;
    var show = save > 0;
    if (sumListRow) sumListRow.hidden = !show;
    if (sumSaveRow) sumSaveRow.hidden = !show;
    /* R-17 숨길 때 **값도 지운다.** 숨김이 어떤 이유로든 풀려도 지난 금액이
     * 남아 있으면 안 된다 — 구성을 취소했는데 정가·할인이 그대로 남아 있던 사고가
     * 바로 그것이었다(CSS 가 `[hidden]` 을 이겨 숨김 자체가 안 먹혔다). */
    if (sumListV) sumListV.textContent = show ? won(listSum) : '\u2014';
    if (sumSaveV) sumSaveV.textContent = show ? ('-' + won(save)) : '\u2014';

    if (sumItemV) sumItemV.textContent = num > 0 ? t : '—';
    /* R-12 「총 결제금액」은 **고객이 실제로 내는 돈**이어야 한다.
     * 카페24 `#totalPrice` 는 상품 금액만 담는다 — 배송비가 붙는 주문에서
     * 그 값을 그대로 쓰면 결제 직전 화면이 실제 결제액보다 적은 금액을 말하게 된다
     * (34,900원 표시 / 실제 38,400원). 배송비를 아는 경우에만 더한다. */
    var fee = shipFee();
    if (sumTotV) {
      sumTotV.textContent = (num > 0)
        ? (fee > 0 ? won(num + fee) : t)
        : '0원';
    }
    if (sumShipV) {
      var free = isFreeShip();
      var dtxt = captureDelivery();      /* 아직 못 읽었으면 이 시점에 한 번 더 시도 */
      sumShipV.textContent = free ? '무료' : (dtxt || '주문서에서 확인');
      sumShipV.classList.toggle('zg-sum__v--free', free);
    }

    if (barV) {
      if (num > 0) {
        barV.textContent = t;
        barV.classList.remove('zg-bar__v--hint');
        if (barSum) barSum.style.display = '';
      } else if (!optSel && !hasRealPrice()) {
        /* 고를 옵션도 없고 판매가도 없는 안내성 상품(34 이벤트종료 · 91/93 결제수단 안내).
         * "구성을 선택해 주세요" 는 고객이 할 수 있는 일이 없는 막다른 말이라 줄 자체를 접는다.
         * 옵션이 없어도 단가가 있는 상품(60/61/62)은 hasRealPrice() 가 true 라 여기로 오지 않는다. */
        if (barSum) barSum.style.display = 'none';
      } else {
        barV.textContent = '구성을 선택해 주세요';
        barV.classList.add('zg-bar__v--hint');
        if (barSum) barSum.style.display = '';
      }
    }

    /* 카드 상태 = tr.option_product 목록과 대조 (select.value 를 보지 않는다) */
    var picked = 0, removable = 0;
    cards.forEach(function (c) {
      var key = c.getAttribute('data-zg-key');
      var hit = null;
      for (var i = 0; i < rows.length; i++) { if (rowMatches(rows[i].key, key)) { hit = rows[i]; break; } }
      c.setAttribute('data-zg-on', hit ? '1' : '');
      /* 라벨의 마지막은 **이 버튼을 누르면 실제로 일어나는 일**이어야 한다 (R-2 로 담긴 카드의
       * 동작이 「담기」에서 「해제」로 바뀌었다). 삭제 컨트롤이 없어 해제가 안 되는 상품에서는
       * 「선택 해제」라고 말하지 않는다 — 되지 않는 일을 안내하지 않는다. */
      var canRemove = !!(hit && delControl(hit.el));
      if (canRemove) removable++;
      c.setAttribute('aria-label',
        (hit ? '선택됨, ' + hit.qty + '개. ' : '') + (c._zgLabel || c._zgName || '') +
        (hit ? (canRemove ? ', 선택 해제' : ', 이미 담김') : ', 장바구니에 담기'));
      if (c._zgState) c._zgState.textContent = hit ? ('선택됨 · ' + hit.qty + '개') : '';
      if (hit) picked++;
    });

    if (modeEffective === 'multi' && picked >= 2) {
      showHint('구성 ' + picked + '개가 담겼어요. ' + (removable === picked
        ? '카드를 다시 누르면 빠집니다.'
        : '필요 없는 구성은 아래에서 지워 주세요.'));
    } else if (modeEffective === 'multi') {
      showHint('');
    }

    /* R-12 합계 줄 수가 바뀌면(정가·할인금액 노출/은닉) 고정 합계의 높이가 달라진다 —
     * 시트 바닥 실측을 다시 돌려 버튼 블록에 깔리지 않게 한다. */
    fitSheet();
  }
})();
