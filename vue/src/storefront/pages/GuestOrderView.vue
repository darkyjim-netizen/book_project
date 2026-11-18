<template>
  <section class="guest-order-page" aria-labelledby="guest-order-title">
    <div class="guest-order-heading"><p>ORDER LOOKUP</p><h1 id="guest-order-title">비회원 주문조회</h1><p>주문할 때 입력한 주문번호와 이메일을 입력해 주세요.</p></div>
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
        </template>
        <div v-else class="guest-order-empty"><b>주문 내역을 확인해 보세요</b><p>주문 정보가 일치하면 이곳에서 상품과 배송 상태를 볼 수 있습니다.</p></div>
      </section>
    </div>
    <p class="guest-order-notice">비회원은 쿠폰을 등록하거나 사용할 수 없습니다.</p>
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
async function lookup() {
  if (loading.value) return;
  error.value = ''; order.value = null; loading.value = true;
  try { order.value = await storefrontApi.lookupGuestOrder(orderNumber.value, email.value); }
  catch (err) { error.value = err.status === 404 ? '일치하는 비회원 주문을 찾을 수 없습니다. 주문번호와 이메일을 확인해 주세요.' : (err.message || '조회에 실패했습니다. 잠시 후 다시 시도해 주세요.'); }
  finally { loading.value = false; }
}
</script>
