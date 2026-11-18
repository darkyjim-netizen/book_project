<template>
<section class="account-support member-mypage">
  <header><p>MY PAGE</p><h1>{{ profile.name || '회원' }}님의 마이페이지</h1><p>회원정보와 주문, 쿠폰 및 배송지를 관리하세요.</p></header>
  <div class="member-overview" aria-label="계정 요약">
    <article><span>회원 <i aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="8" r="3.2"/><path d="M5.5 19c.4-3.1 2.7-5 6.5-5s6.1 1.9 6.5 5"/></svg></i></span><strong>{{ profile.nickname || profile.name || '회원' }}</strong><small>{{ profile.email }}</small></article>
    <article><span>회원 유형 <i aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3.5 19 6v5.2c0 4.3-2.6 7.3-7 9.3-4.4-2-7-5-7-9.3V6l7-2.5Z"/><path d="m9 11.8 2 2 4-4"/></svg></i></span><strong>{{ auth.isAdmin ? '관리자' : '일반 회원' }}</strong><small>북적북적 회원</small></article>
    <article><span>계정 상태 <i aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="8"/><path d="m8.5 12 2.3 2.4 4.8-5"/></svg></i></span><strong>{{ auth.user?.status === 'ACTIVE' ? '정상 이용 중' : '확인 필요' }}</strong><small>내 계정</small></article>
    <article><span>보유 쿠폰 <i aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M4 8.5a2 2 0 0 0 2-2h12a2 2 0 0 0 2 2v2a1.8 1.8 0 0 0 0 3.6v2a2 2 0 0 0-2 2H6a2 2 0 0 0-2-2v-2a1.8 1.8 0 0 0 0-3.6v-2Z"/><path d="M12 8.5v7" stroke-dasharray="1.3 2"/></svg></i></span><strong>{{ coupons.length }}장</strong><small>쿠폰 탭에서 확인</small></article>
  </div>
  <section id="member-recommendations" class="as-card member-recommendations" aria-labelledby="member-rec-title">
    <h2 id="member-rec-title">{{ recAlgorithm && recAlgorithm !== 'POPULAR' ? '회원님을 위한 추천 도서' : '지금 많이 찾는 인기 도서' }}</h2>
    <p v-if="recLoading">추천 도서를 불러오는 중입니다.</p><p v-else-if="recError">{{ recError }}</p><p v-else-if="!recs.length">추천할 도서가 아직 없습니다.</p>
    <div v-else class="member-recommendation-grid"><RouterLink v-for="book in recs" :key="book.book_id" :to="{name:'productInfo',params:{title:book.title},query:{from:'mypage'}}" class="member-recommendation"><img v-if="book.cover_image" :src="book.cover_image" :alt="book.title + ' 표지'"><span v-else class="member-no-cover">표지 없음</span><strong>{{ book.title }}</strong><small>{{ (book.authors || []).join(', ') }}</small><span>{{ money(book.sale_price) }}</span></RouterLink></div>
  </section>
  <nav class="member-tabs" aria-label="마이페이지 메뉴"><button v-for="item in tabs" :key="item.id" type="button" :aria-current="activeTab === item.id ? 'page' : null" @click="activeTab = item.id">{{ item.label }}</button></nav>
  <p v-if="error" class="as-error" role="alert">{{ error }}</p><p v-if="message" class="as-success" role="status">{{ message }}</p>
  <div class="as-grid">
    <section v-show="activeTab === 'profile'" class="as-card as-wide"><h2>회원정보</h2><p>{{ profile.email }}</p><form @submit.prevent="saveProfile"><label>이름<input v-model.trim="profile.name" required maxlength="60"></label><label>별명<input v-model.trim="profile.nickname" maxlength="60"></label><label>연락처<input v-model.trim="profile.phone" maxlength="20" autocomplete="tel"></label><button :disabled="busy">정보 저장</button></form></section>
    <section v-show="activeTab === 'coupons'" class="as-card as-wide"><h2>쿠폰 등록</h2><form class="as-inline" @submit.prevent="registerCoupon"><label>쿠폰 코드<input v-model.trim="code" required></label><button :disabled="busy">등록</button></form><h3>보유 쿠폰</h3><p v-if="!coupons.length">보유한 쿠폰이 없습니다.</p><ul class="as-list"><li v-for="coupon in coupons" :key="coupon.member_coupon_id"><b>{{ coupon.name }}</b><span>최소 {{ money(coupon.min_order_amount) }} · {{ date(coupon.expires_at) }}까지</span></li></ul></section>
    <section v-show="activeTab === 'orders'" class="as-card as-wide"><h2>주문내역</h2><p v-if="!orders.length">주문내역이 없습니다.</p><ul class="as-list"><li v-for="order in orders" :key="order.order_id"><b>{{ order.order_no }} · {{ order.status_label }}</b><span>{{ order.summary_title }} · {{ money(order.total_amount) }} · {{ date(order.ordered_at) }}</span></li></ul><div class="as-pagination"><button v-if="orderPage > 1" @click="loadOrders(orderPage - 1)">이전</button><span>{{ orderPage }} / {{ orderPages }}</span><button v-if="orderPage < orderPages" @click="loadOrders(orderPage + 1)">다음</button></div></section>
    <section v-show="activeTab === 'addresses'" class="as-card as-wide"><h2>배송지 관리</h2><p v-if="!addresses.length">등록된 배송지가 없습니다.</p><ul class="as-list"><li v-for="address in addresses" :key="address.address_id"><b>{{ address.alias }} <small v-if="address.is_default">기본 배송지</small></b><span>{{ address.receiver }} · {{ address.phone }} · ({{ address.zipcode }}) {{ address.address1 }} {{ address.address2 }}</span><div><button type="button" class="as-secondary" @click="editAddress(address)">수정</button> <button type="button" class="as-secondary" @click="deleteAddress(address)">삭제</button></div></li></ul><h3>{{ addressId ? '배송지 수정' : '배송지 추가' }}</h3><form class="as-fields" @submit.prevent="saveAddress"><label>배송지 이름<input v-model.trim="addressForm.alias" required maxlength="50"></label><label>받는 분<input v-model.trim="addressForm.receiver" required maxlength="60"></label><label>연락처<input v-model.trim="addressForm.phone" required maxlength="20"></label><label>우편번호<input v-model.trim="addressForm.zipcode" required maxlength="10"></label><label>기본 주소<input v-model.trim="addressForm.address1" required maxlength="255"></label><label>상세 주소<input v-model.trim="addressForm.address2" maxlength="255"></label><label>배송 요청사항<input v-model.trim="addressForm.request_memo" maxlength="255"></label><label class="as-check"><input v-model="addressForm.is_default" type="checkbox"> 기본 배송지로 설정</label><div><button :disabled="busy">{{ addressId ? '수정 저장' : '배송지 등록' }}</button> <button v-if="addressId" type="button" class="as-secondary" @click="resetAddress">취소</button></div></form></section>
    <section v-show="activeTab === 'profile'" class="as-card as-wide"><h2>회원탈퇴</h2><p>탈퇴 후에는 계정을 사용할 수 없습니다.</p><form @submit.prevent="withdraw"><label>탈퇴 사유 (선택)<textarea v-model.trim="reason" maxlength="500"></textarea></label><button class="as-danger" :disabled="busy">회원탈퇴</button></form></section>
  </div>
</section>
</template>
<script setup>
import { onMounted, reactive, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import http from '../../api/http';
import { useAuthStore } from '../../stores/authStore';
import { memberApi } from '../../api/memberApi';
const router=useRouter(), route=useRoute(), auth=useAuthStore();
const tabs=[{id:'profile',label:'회원정보'},{id:'coupons',label:'쿠폰'},{id:'orders',label:'주문내역'},{id:'addresses',label:'배송지 관리'}];
const selectedTab=()=>tabs.some(item=>item.id===route.query.tab)?route.query.tab:'profile';
const activeTab=ref(selectedTab());
watch(()=>route.query.tab,()=>{activeTab.value=selectedTab()});
const recs=ref([]),recAlgorithm=ref(''),recLoading=ref(true),recError=ref('');
async function loadRecommendations(){try{const data=await memberApi.recommendations(5);recs.value=data.items || [];recAlgorithm.value=data.algorithm || ''}catch(e){recError.value=e.userMessage || '추천 도서를 불러오지 못했습니다.'}finally{recLoading.value=false}}
const profile=reactive({name:'',nickname:'',phone:'',email:''}), coupons=ref([]), orders=ref([]), addresses=ref([]), code=ref(''), reason=ref(''), error=ref(''), message=ref(''), busy=ref(false), orderPage=ref(1), orderPages=ref(1), addressId=ref(null);
const blankAddress=()=>({alias:'',receiver:'',phone:'',zipcode:'',address1:'',address2:'',request_memo:'',is_default:false});
const addressForm=reactive(blankAddress());
const money=n=>`${Number(n || 0).toLocaleString('ko-KR')}원`, date=s=>s ? new Date(s).toLocaleDateString('ko-KR',{timeZone:'Asia/Seoul'}) : '';
function failure(e){ error.value=e.userMessage || '요청을 처리하지 못했습니다.'; }
async function run(fn, success=''){ if(busy.value)return; error.value=''; message.value=''; busy.value=true; try { await fn(); message.value=success; } catch(e){failure(e)} finally {busy.value=false} }
async function loadOrders(page=1){ try {const {data}=await http.get('/api/v1/orders',{params:{page,size:10}}); orders.value=data.items; orderPage.value=page; orderPages.value=data.meta.total_pages || 1;}catch(e){failure(e)} }
async function loadCoupons(){coupons.value=(await http.get('/api/v1/members/me/coupons')).data}
async function loadAddresses(){addresses.value=(await http.get('/api/v1/members/me/addresses')).data}
onMounted(async()=>{const results=await Promise.allSettled([http.get('/api/v1/members/me').then(r=>Object.assign(profile,r.data)),loadCoupons(),loadAddresses(),loadOrders(),loadRecommendations()]); const failed=results.find(r=>r.status==='rejected'); if(failed) failure(failed.reason);});
function saveProfile(){run(async()=>{const {data}=await http.put('/api/v1/members/me',{name:profile.name,nickname:profile.nickname || null,phone:profile.phone || null}); Object.assign(profile,data); await auth.fetchMe();},'회원정보를 저장했습니다.');}
function registerCoupon(){run(async()=>{await http.post('/api/v1/members/me/coupons',{code:code.value}); code.value=''; await loadCoupons();},'쿠폰을 등록했습니다.');}
function resetAddress(){addressId.value=null; Object.assign(addressForm,blankAddress())}
function editAddress(a){addressId.value=a.address_id; Object.assign(addressForm,blankAddress(),a)}
function saveAddress(){run(async()=>{const body={...addressForm}; delete body.address_id; if(addressId.value) await http.put(`/api/v1/members/me/addresses/${addressId.value}`,body); else await http.post('/api/v1/members/me/addresses',body); resetAddress(); await loadAddresses();},'배송지를 저장했습니다.');}
function deleteAddress(a){if(!window.confirm(`'${a.alias}' 배송지를 삭제하시겠습니까?`))return; run(async()=>{await http.delete(`/api/v1/members/me/addresses/${a.address_id}`); if(addressId.value===a.address_id) resetAddress(); await loadAddresses();},'배송지를 삭제했습니다.');}
function withdraw(){if(!window.confirm('정말 회원탈퇴하시겠습니까? 탈퇴 후 계정을 사용할 수 없습니다.'))return; run(async()=>{await http.post('/api/v1/auth/withdraw',{reason_code:'ETC',reason_text:reason.value || null}); auth.setUser(null); await router.push('/main');});}
</script>
