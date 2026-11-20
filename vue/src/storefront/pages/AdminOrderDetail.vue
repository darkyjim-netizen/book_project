<template>
  <section class="admin-order-page">
    <div class="admin-order-wrap">
      <RouterLink class="back-link" :to="backTo">← {{ fromRefunds ? '취소·환불 목록' : '주문·배송 목록' }}</RouterLink>
      <header class="order-header"><div><p>주문 관리</p><h1>주문 상세</h1><span v-if="order">{{ order.order_no }} · {{ date(order.ordered_at) }}</span></div><span v-if="order" class="status-badge">{{ order.status_label }}</span></header>
      <p v-if="loading" role="status">주문 정보를 불러오는 중입니다.</p><p v-if="error" class="order-error" role="alert">{{ error }} <button type="button" @click="load">다시 시도</button></p><p v-if="message" class="order-success" role="status">{{ message }}</p>
      <template v-if="order && !loading">
        <div class="order-grid"><div class="order-main">
          <section class="order-card"><h2>주문 상품</h2><article v-for="item in order.items" :key="item.order_item_id" class="order-item"><img v-if="item.cover_image" :src="item.cover_image" :alt="item.book_title + ' 표지'"><div v-else class="cover-placeholder">책</div><div><strong>{{ item.book_title }}</strong><p>{{ item.quantity }}권 · {{ money(item.unit_price) }}</p></div><b>{{ money(item.item_total) }}</b></article></section>
          <section class="order-card"><h2>주문자 및 배송 정보</h2><dl class="order-info"><div><dt>주문자</dt><dd>{{ order.orderer_name }}</dd></div><div><dt>받는 분</dt><dd>{{ order.receiver }} · {{ order.receiver_phone }}</dd></div><div><dt>배송지</dt><dd>({{ order.zipcode }}) {{ order.address1 }} {{ order.address2 }}</dd></div><div><dt>배송 요청</dt><dd>{{ order.request_memo || '없음' }}</dd></div><div><dt>택배사·운송장</dt><dd>{{ order.shipment?.carrier_name || '미등록' }}<template v-if="order.shipment?.invoice_no"> · {{ order.shipment.invoice_no }}</template></dd></div></dl></section>
        </div><aside class="order-side"><section class="order-card"><h2>결제 정보</h2><dl class="order-info"><div><dt>상품 금액</dt><dd>{{ money(order.item_amount) }}</dd></div><div><dt>할인 금액</dt><dd>− {{ money(order.discount_amount) }}</dd></div><div><dt>배송비</dt><dd>{{ money(order.ship_fee) }}</dd></div><div class="order-total"><dt>결제 금액</dt><dd>{{ money(order.total_amount) }}</dd></div></dl></section>
          <section class="order-card"><h2>{{ fromRefunds ? '취소·환불 처리' : '배송 처리' }}</h2><template v-if="!fromRefunds"><div class="order-actions"><button v-if="order.status === 'PAID'" :disabled="busy" @click="setStatus('PREPARING')">상품 준비 시작</button><button v-if="order.status === 'SHIPPING'" :disabled="busy" @click="setStatus('DELIVERED')">배송 완료</button></div><form v-if="['PAID','PREPARING'].includes(order.status)" class="invoice-form" @submit.prevent="registerInvoice"><label>택배사<select v-model="invoice.carrier_code"><option value="CJ">CJ대한통운</option><option value="HANJIN">한진택배</option><option value="LOTTE">롯데택배</option><option value="POST">우체국택배</option></select></label><label>운송장 번호<input v-model.trim="invoice.invoice_no" required maxlength="40"></label><button :disabled="busy">송장 등록·배송 시작</button></form><p v-if="!['PAID','PREPARING','SHIPPING'].includes(order.status)" class="order-hint">현재 상태에서 처리할 배송 작업이 없습니다.</p></template><template v-else><p class="order-hint">결제 환불과 주문 상태·재고 처리는 별도로 관리됩니다.</p><div class="order-actions"><button v-if="order.is_cancelable && order.status === 'PENDING'" :disabled="busy" @click="cancelOrder">주문 취소</button><button v-if="order.payment && ['PAID','PARTIAL_CANCELLED'].includes(order.payment.status)" :disabled="busy" @click="refundOrder">잔여 결제액 환불</button></div></template></section>
        </aside></div>
      </template>
    </div>
  </section>
</template>
<script setup>
import { computed, ref, watch } from 'vue';
import { useRoute } from 'vue-router';
import http from '../../api/http';
const route=useRoute(), order=ref(null), loading=ref(false), busy=ref(false), error=ref(''), message=ref('');
const invoice=ref({carrier_code:'CJ',invoice_no:''});
const fromRefunds=computed(()=>route.query.from==='refunds');
const backTo=computed(()=>({name:'adminDashboard',query:{tab:fromRefunds.value?'refunds':'orders'}}));
const money=n=>`${Number(n||0).toLocaleString('ko-KR')}원`;
const date=s=>s?new Date(s).toLocaleString('ko-KR',{timeZone:'Asia/Seoul'}):'—';
let generation=0;
async function load(){const token=++generation;loading.value=true;error.value='';try{const {data}=await http.get(`/api/v1/admin/orders/${encodeURIComponent(route.params.id)}`);if(token===generation)order.value=data}catch(e){if(token===generation){order.value=null;error.value=e.userMessage||'주문 정보를 불러오지 못했습니다.'}}finally{if(token===generation)loading.value=false}}
watch(()=>route.params.id,load,{immediate:true});
async function run(action,success){if(busy.value)return;busy.value=true;error.value='';message.value='';try{await action();message.value=success;await load()}catch(e){error.value=e.userMessage||'요청을 처리하지 못했습니다.'}finally{busy.value=false}}
function setStatus(status){if(confirm('주문 상태를 변경하시겠습니까?'))run(()=>http.put(`/api/v1/admin/orders/${order.value.order_id}/status`,{status}),'주문 상태를 변경했습니다.')}
function registerInvoice(){const names={CJ:'CJ대한통운',HANJIN:'한진택배',LOTTE:'롯데택배',POST:'우체국택배'};if(confirm('운송장을 등록하고 배송을 시작하시겠습니까?'))run(()=>http.post(`/api/v1/admin/shipments/${order.value.order_id}/invoice`,{...invoice.value,carrier_name:names[invoice.value.carrier_code]}),'운송장을 등록했습니다.')}
function cancelOrder(){const reason=prompt('주문 취소 사유를 입력해 주세요.');if(reason?.trim() && confirm('이 주문을 취소하시겠습니까?'))run(()=>http.post(`/api/v1/admin/orders/${order.value.order_id}/cancel`,{reason_text:reason.trim()}),'주문을 취소했습니다.')}
function refundOrder(){const reason=prompt('결제 환불을 진행합니다. 주문 상태와 재고는 별도로 관리해야 합니다. 환불 사유를 입력해 주세요.');if(reason?.trim() && confirm('실제 결제에 환불이 요청될 수 있습니다. 잔여 결제액 전체를 환불하시겠습니까?'))run(()=>http.post(`/api/v1/admin/orders/${order.value.order_id}/refund`,{reason:reason.trim()}),'환불을 처리했습니다.')}
</script>
<style scoped>
.order-card { box-sizing:border-box; }
.order-info > div { align-items:baseline; line-height:1.55; }
.order-info dd { min-width:0; }
.order-item { min-width:0; }
.order-item p, .order-hint { margin:8px 0 0; }
.invoice-form label { display:grid; gap:7px; line-height:1.4; }
.invoice-form input, .invoice-form select { margin-top:0; min-height:44px; }

.admin-order-page{background:#fbfafc;min-height:65vh;padding:45px 24px 80px;color:#30283a}.admin-order-wrap{max-width:1100px;margin:auto}.back-link{color:#70538b;text-decoration:none;font-size:14px}.order-header{display:flex;justify-content:space-between;align-items:end;gap:15px;margin:30px 0}.order-header p{margin:0;color:#987ead;font-size:12px;font-weight:700}.order-header h1{margin:8px 0;font-size:28px}.order-header span{color:#817788;font-size:13px}.order-header .status-badge{padding:8px 13px;background:#f0e9f8;border-radius:20px;color:#65419a;font-weight:700}.order-grid{display:grid;grid-template-columns:minmax(0,1fr) 310px;gap:20px}.order-card{margin-bottom:14px;padding:18px 24px;background:white;border:1px solid #e9e2ec;border-radius:12px}.order-card h2{margin:0 0 14px;font-size:18px}.order-item{display:flex;gap:16px;align-items:center;padding:10px 0;border-top:1px solid #f0ecf2}.order-item img,.cover-placeholder{width:58px;height:76px;object-fit:contain;border-radius:5px;background:#f5f1f8}.cover-placeholder{display:grid;place-items:center;color:#998ba3}.order-item>div:nth-child(2){flex:1;min-width:0}.order-item strong{overflow-wrap:anywhere}.order-item p,.order-hint{color:#817788;font-size:13px;line-height:1.6}.order-info{margin:0}.order-info>div{display:flex;gap:15px;justify-content:space-between;padding:6px 0;font-size:14px}.order-info dt{flex-shrink:0;color:#8a818e}.order-info dd{margin:0;text-align:right;overflow-wrap:anywhere}.order-total{margin-top:10px;padding-top:16px!important;border-top:1px solid #eee8f0;font-weight:700;color:#65419a}.order-actions,.invoice-form{display:grid;gap:10px}.invoice-form{margin-top:15px}.invoice-form label{font-size:13px;font-weight:700}.invoice-form input,.invoice-form select{box-sizing:border-box;width:100%;margin-top:7px;padding:10px;border:1px solid #ded4e6;border-radius:7px;font:inherit}.order-actions button,.invoice-form button,.order-error button{padding:11px;border:0;border-radius:7px;background:#65419a;color:white;font:inherit;cursor:pointer}.order-actions button:disabled,.invoice-form button:disabled{opacity:.5;cursor:wait}.order-error{color:#a32c2c}.order-success{color:#38744b}@media(max-width:700px){.admin-order-page{padding:30px 16px 60px}.order-grid{grid-template-columns:1fr}.order-header h1{font-size:24px}.order-card{padding:20px}}
.admin-order-page{font-size:16px;line-height:1.55}.back-link,.order-header p,.order-header span,.order-item p,.order-hint,.invoice-form label{font-size:16px}.order-card h2{font-size:21px}.order-info>div{font-size:16px}.order-actions button,.invoice-form button,.invoice-form input,.invoice-form select{font-size:16px}
</style>
