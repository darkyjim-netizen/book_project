<template>
  <section class="guest-order-page" aria-labelledby="guest-order-title">
    <div class="guest-order-heading"><h1 id="guest-order-title">비회원 주문조회</h1><p>주문번호와 주문 시 사용한 이메일로 상품과 배송 상태를 확인하세요.</p></div>
    <div class="guest-order-layout">
      <form class="guest-order-panel guest-order-form" @submit.prevent="lookup">
        <h2>주문 정보 확인</h2>
        <label for="guest-order-number">주문번호</label>
        <input id="guest-order-number" v-model.trim="orderNumber" maxlength="30" required autocomplete="off" placeholder="주문번호를 입력해 주세요" />
        <label for="guest-order-email">주문자 이메일</label>
        <input id="guest-order-email" v-model.trim="email" type="email" required autocomplete="email" placeholder="주문 시 입력한 이메일" />
        <button type="submit" :disabled="loading">{{ loading ? '조회 중...' : '주문 조회하기' }}</button>
        <p v-if="error" role="alert" class="guest-order-error">{{ error }}</p>
        <p class="guest-order-help">비회원 주문만 조회할 수 있습니다. 회원 주문은 로그인 후 확인해 주세요.</p>
        <a href="/login">회원 로그인 →</a>
      </form>
      <section class="guest-order-panel guest-order-result" aria-live="polite" aria-label="조회 결과">
        <template v-if="order">
          <div class="guest-order-result-head"><div><span>주문번호 {{ order.order_no }}</span><h2>{{ order.status_label }}</h2></div><time :datetime="order.ordered_at">{{ formatDate(order.ordered_at) }}</time></div>
          <h3>주문 상품</h3>
          <article v-for="item in order.items" :key="item.order_item_id" class="guest-order-item">
            <img v-if="item.cover_image" :src="item.cover_image" :alt="item.book_title + ' 표지'" />
            <div><b>{{ item.book_title }}</b><span>{{ item.quantity }}권 · {{ won(item.unit_price) }}</span></div><strong>{{ won(item.item_total) }}</strong>
          </article>
          <dl class="guest-order-details"><div><dt>상품 금액</dt><dd>{{ won(order.item_amount) }}</dd></div><div><dt>배송비</dt><dd>{{ won(order.ship_fee) }}</dd></div><div><dt>결제 금액</dt><dd><strong>{{ won(order.total_amount) }}</strong></dd></div><div><dt>받는 분</dt><dd>{{ order.receiver }}</dd></div><div><dt>배송 상태</dt><dd>{{ shipmentStatus }}</dd></div></dl>
          <div v-if="order.is_cancelable" class="guest-cancel-box">
            <h3>주문 취소</h3>
            <p>배송이 시작되기 전까지 취소할 수 있어요. 결제 금액은 결제하신 수단으로 환불됩니다.</p>
            <div class="guest-cancel-fields">
              <select v-model="cancelReason" aria-label="취소 사유">
                <option value="CHANGE_MIND">단순 변심</option>
                <option value="WRONG_ORDER">주문 실수</option>
                <option value="DELAY">배송 지연</option>
                <option value="ETC">기타</option>
              </select>
              <input v-model.trim="cancelReasonText" maxlength="200" placeholder="상세 사유 (선택)" aria-label="상세 사유" />
            </div>
            <button type="button" class="guest-cancel-btn" :disabled="cancelling" @click="cancelOrder">{{ cancelling ? '취소 처리 중…' : '주문 취소하기' }}</button>
          </div>
          <p v-else-if="order.status === 'CANCELLED'" class="guest-cancel-done">취소된 주문입니다.</p>
          <p v-else class="guest-cancel-note">배송이 시작된 주문은 취소할 수 없어요. 반품은 고객센터로 문의해 주세요.</p>
          <p v-if="cancelMessage" role="status" class="guest-cancel-msg">{{ cancelMessage }}</p>
        </template>
        <div v-else class="guest-order-empty"><b>주문 내역을 확인해 보세요</b><p>주문 정보가 일치하면 이곳에서 상품과 배송 상태를 볼 수 있습니다.</p></div>
      </section>
    </div>
  </section>
</template>
<script setup>
import { computed, ref } from 'vue';
import { storefrontApi } from '../api.js';
const orderNumber = ref(''), email = ref(''), order = ref(null), error = ref(''), loading = ref(false);
const shipmentLabels = { READY:'배송 준비', PICKED:'상품 수거', IN_TRANSIT:'배송 중', OUT_FOR_DELIVERY:'배달 출발', DELIVERED:'배송 완료', FAILED:'배송 실패', RETURNING:'반송 중' };
const shipmentStatus = computed(() => order.value?.shipment ? (shipmentLabels[order.value.shipment.status] || order.value.shipment.status) : '배송 정보 없음');
const won = value => `${Number(value || 0).toLocaleString('ko-KR')}원`;
const formatDate = value => value ? new Intl.DateTimeFormat('ko-KR', { dateStyle:'long', timeZone:'Asia/Seoul' }).format(new Date(value)) : '';
// ---- 비회원 주문 취소 ----
// 조회에 성공하면 서버가 이 주문 전용 토큰(2시간 유효)을 준다. 취소할 때 이 토큰으로 본인 확인을 한다.
const guestToken = ref(''), cancelReason = ref('CHANGE_MIND'), cancelReasonText = ref(''), cancelling = ref(false), cancelMessage = ref('');
async function cancelOrder() {
  const o = order.value;
  if (!o || cancelling.value) return;
  if (!confirm(`주문 ${o.order_no}을(를) 취소할까요?\n결제된 금액은 환불됩니다.`)) return;
  cancelling.value = true; cancelMessage.value = '';
  try {
    order.value = await storefrontApi.cancelGuestOrder(o.order_id, { reason_code: cancelReason.value, reason_text: cancelReasonText.value || null }, guestToken.value);
    cancelMessage.value = '주문이 취소되었습니다.';
  } catch (err) {
    // 토큰이 만료(2시간)됐으면 다시 조회하면 새 토큰을 받는다.
    cancelMessage.value = err.status === 401 || err.status === 403
      ? '인증 시간이 지났어요. 주문을 다시 조회한 뒤 취소해 주세요.'
      : (err.message || '주문을 취소하지 못했습니다.');
  } finally { cancelling.value = false; }
}

async function lookup() {
  if (loading.value) return;
  error.value = ''; order.value = null; loading.value = true;
  guestToken.value = ''; cancelMessage.value = ''; cancelReason.value = 'CHANGE_MIND'; cancelReasonText.value = '';
  try {
    const result = await storefrontApi.lookupGuestOrder(orderNumber.value, email.value);
    guestToken.value = result.guest_order_token || '';
    order.value = result;
  }
  catch (err) { error.value = err.status === 404 ? '일치하는 비회원 주문을 찾을 수 없습니다. 주문번호와 이메일을 확인해 주세요.' : (err.message || '조회에 실패했습니다. 잠시 후 다시 시도해 주세요.'); }
  finally { loading.value = false; }
}
</script>

<style scoped>
.guest-order-page{box-sizing:border-box;padding-top:20px;min-width:0}
.guest-order-heading{margin-bottom:26px}.guest-order-heading h1{margin:0 0 12px;font-size:32px;font-weight:700;letter-spacing:-.035em;line-height:1.35}.guest-order-heading p{margin:0;font-size:16px;line-height:1.7;color:#766580}
.guest-order-layout{gap:24px}.guest-order-panel{padding:28px;border-color:#e7ddef;box-shadow:0 4px 20px #44265e04}.guest-order-panel h2{font-size:22px;font-weight:600}
.guest-order-form input{font-size:16px;min-height:50px;border-radius:10px}.guest-order-form label{font-size:15px}.guest-order-form button{min-height:50px;font-size:16px;border-radius:10px}.guest-order-help{margin:18px 0 10px;font-size:14px;line-height:1.8}.guest-order-form>a{display:inline-flex;align-items:center;min-height:36px;font-size:14px}.guest-order-notice{margin-top:16px;font-size:13px;color:#8a7a94}
.guest-order-empty{padding:54px 16px}.guest-order-empty b{display:block;margin-bottom:10px;font-size:19px;font-weight:600;color:#5c4270}.guest-order-empty p{max-width:34em;margin:0 auto;font-size:15px;line-height:1.8;color:#8a7994}
.guest-cancel-box{margin-top:24px;padding:20px;border:1px solid #f0dbe0;border-radius:12px;background:#fffafb}
.guest-cancel-box h3{margin:0 0 6px;font-size:17px;color:#a43b52}
.guest-cancel-box p{margin:0 0 14px;font-size:14px;line-height:1.6;color:#8a7a94;word-break:keep-all}
.guest-cancel-fields{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px}
.guest-cancel-fields select,.guest-cancel-fields input{min-height:44px;padding:0 12px;border:1px solid #e2d6ea;border-radius:10px;font:inherit;font-size:15px;background:#fff}
.guest-cancel-fields input{flex:1;min-width:180px}
.guest-cancel-btn{min-height:44px;padding:0 20px;border:0;border-radius:10px;background:#d05a6e;color:#fff;font:inherit;font-size:15px;font-weight:700;cursor:pointer}
.guest-cancel-btn:disabled{opacity:.6;cursor:default}
.guest-cancel-note,.guest-cancel-done{margin-top:20px;font-size:14px;color:#8a7a94;word-break:keep-all}
.guest-cancel-msg{margin-top:12px;font-size:15px;font-weight:600;color:#6841a4}
@media(max-width:700px){.guest-order-page{padding-top:12px}.guest-order-heading h1{font-size:28px}.guest-order-panel{padding:22px 20px}.guest-order-empty{padding:30px 8px}}
</style>
