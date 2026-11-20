<template>
<section class="account-support member-mypage">
  <div class="mypage-layout">
  <aside class="mypage-sidebar"><p class="mypage-kicker">나의 북적북적</p><h1>마이페이지</h1><p class="mypage-sidebar-label">나의 쇼핑</p><nav aria-label="마이페이지 메뉴"><button v-for="item in tabs" :key="item.id" type="button" :aria-current="activeTab === item.id ? 'page' : null" @click="activeTab = item.id">{{ item.label }} <span aria-hidden="true">›</span></button></nav><div class="mypage-sidebar-note">책과 함께하는<br>나만의 공간</div></aside>
  <div class="mypage-main">
  <section class="mypage-profile" aria-label="계정 요약"><div class="mypage-profile-person"><div class="mypage-avatar" aria-hidden="true"><svg class="mypage-book-icon" viewBox="0 0 48 48" fill="none"><path d="M24 14c-5-4-12-5-19-3v25c7-2 14-1 19 3 5-4 12-5 19-3V11c-7-2-14-1-19 3Z" fill="#fff" stroke="currentColor" stroke-width="2.2" stroke-linejoin="round"/><path d="M24 14v25M10 18c3-.4 6 .1 9 1.5M10 24c3-.4 6 .1 9 1.5M29 26c3-1.4 6-1.9 9-1.5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/><path d="M32 10v11l3-2 3 2V9.5" fill="#c9b0e6" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/></svg></div><div><span class="mypage-profile-tag">북적북적 회원</span><h2>{{ profile.nickname || profile.name || '회원' }}님, 반가워요</h2><p>{{ profile.email }}</p><button type="button" class="mypage-profile-edit" @click="activeTab = 'profile'">회원정보 수정 <span aria-hidden="true">↗</span></button></div></div><div class="mypage-profile-stats"><button type="button" @click="activeTab = 'coupons'"><span>보유 쿠폰</span><strong>{{ couponsLoaded ? coupons.length : '—' }}<small v-if="couponsLoaded">장</small></strong></button><button type="button" @click="activeTab = 'orders'"><span>전체 주문</span><strong>{{ orderStats ? orderStats.total : '—' }}<small v-if="orderStats">건</small></strong></button><div><span>계정 상태</span><strong class="mypage-status">{{ auth.user?.status === 'ACTIVE' ? '이용 중' : '확인 필요' }}</strong></div></div></section>
  <div v-if="activeTab === 'overview'" class="mypage-dashboard">
  <div class="mypage-section-heading"><div><span>나의 쇼핑</span><h2>주문 · 배송 현황</h2></div><button type="button" class="mypage-more" @click="activeTab = 'orders'">주문내역 보기 <span aria-hidden="true">→</span></button></div>
  <div class="mypage-order-status"><div v-for="step in orderSteps" :key="step.key"><strong>{{ orderStats ? orderStats[step.key] : '—' }}</strong><span>{{ step.label }}</span></div></div><p v-if="orderStatsError" class="mypage-stats-error" role="alert">주문 현황을 불러오지 못했습니다. <button type="button" class="as-secondary" @click="loadOrderStats">다시 시도</button></p>
  <section v-if="!auth.isAdmin" class="as-card member-recommendations" aria-labelledby="member-wishlist-title">
    <h2 id="member-wishlist-title">찜한 책</h2>
    <p v-if="wishLoading" role="status">찜한 책을 불러오는 중입니다.</p>
    <p v-else-if="wishError" role="alert">{{ wishError }} <button type="button" class="as-secondary" @click="loadWishlist(wishPage)">다시 시도</button></p>
    <p v-else-if="!wishedBooks.length">아직 찜한 책이 없습니다. 마음에 드는 책의 하트를 눌러 보세요.</p>
    <div v-else class="member-recommendation-grid"><RouterLink v-for="book in wishedBooks" :key="book.book_id" :to="{name:'productInfo',params:{title:book.title},query:{from:'mypage'}}" class="member-recommendation"><img v-if="book.cover_image" :src="book.cover_image" :alt="book.title + ' 표지'"><span v-else class="member-no-cover">표지 없음</span><strong>{{ book.title }}</strong><small>{{ (book.authors || []).join(', ') }}</small><span>{{ money(book.sale_price) }}</span></RouterLink></div>
    <nav v-if="!wishLoading && !wishError && wishPages > 1" class="as-pagination" aria-label="찜한 책 페이지"><button type="button" :disabled="wishPage <= 1" @click="loadWishlist(wishPage - 1)">이전</button><span>{{ wishPage }} / {{ wishPages }}</span><button type="button" :disabled="wishPage >= wishPages" @click="loadWishlist(wishPage + 1)">다음</button></nav>
  </section>
  <section id="member-recommendations" class="as-card member-recommendations" aria-labelledby="member-rec-title">
    <h2 id="member-rec-title">{{ recAlgorithm && recAlgorithm !== 'POPULAR' ? '회원님을 위한 추천 도서' : '지금 많이 찾는 인기 도서' }}</h2>
    <p v-if="recLoading">추천 도서를 불러오는 중입니다.</p><p v-else-if="recError">{{ recError }}</p><p v-else-if="!recs.length">추천할 도서가 아직 없습니다.</p>
    <div v-else class="member-recommendation-grid"><RouterLink v-for="book in recs" :key="book.book_id" :to="{name:'productInfo',params:{title:book.title},query:{from:'mypage'}}" class="member-recommendation"><img v-if="book.cover_image" :src="book.cover_image" :alt="book.title + ' 표지'"><span v-else class="member-no-cover">표지 없음</span><strong>{{ book.title }}</strong><small>{{ (book.authors || []).join(', ') }}</small><span>{{ money(book.sale_price) }}</span></RouterLink></div>
  </section>
  </div>
  <p v-if="error" class="as-error" role="alert">{{ error }}</p><p v-if="message" class="as-success" role="status">{{ message }}</p>
  <div v-if="activeTab !== 'overview'" class="as-grid">
    <section v-show="activeTab === 'profile'" class="as-card as-wide"><h2>회원정보</h2><p>{{ profile.email }}</p><form @submit.prevent="saveProfile"><label>이름<input v-model.trim="profile.name" required maxlength="60"></label><label>별명<input v-model.trim="profile.nickname" maxlength="60"></label><label>연락처<input v-model.trim="profile.phone" maxlength="20" autocomplete="tel"></label><button :disabled="busy">정보 저장</button></form></section>
    <section v-show="activeTab === 'coupons'" class="as-card as-wide"><h2>쿠폰 등록</h2><form class="as-inline" @submit.prevent="registerCoupon"><label>쿠폰 코드<input v-model.trim="code" required></label><button :disabled="busy">등록</button></form><h3>보유 쿠폰</h3><p v-if="couponsLoading" role="status">쿠폰을 불러오는 중입니다.</p><p v-else-if="couponsError" role="alert">쿠폰을 불러오지 못했습니다. <button type="button" class="as-secondary" @click="loadCoupons">다시 시도</button></p><p v-else-if="!coupons.length">보유한 쿠폰이 없습니다.</p><ul v-if="!couponsLoading && !couponsError" class="as-list"><li v-for="coupon in coupons" :key="coupon.member_coupon_id"><b>{{ coupon.name }}</b><span>최소 {{ money(coupon.min_order_amount) }} · {{ date(coupon.expires_at) }}까지</span></li></ul></section>
    <section v-show="activeTab === 'orders'" class="as-card as-wide"><h2>주문내역</h2><p v-if="ordersLoading" role="status">주문내역을 불러오는 중입니다.</p><p v-else-if="ordersError" role="alert">주문내역을 불러오지 못했습니다. <button type="button" class="as-secondary" @click="loadOrders(orderPage)">다시 시도</button></p><p v-else-if="!orders.length">주문내역이 없습니다.</p><ul v-if="!ordersLoading && !ordersError" class="as-list"><li v-for="order in orders" :key="order.order_id"><b>{{ order.order_no }} · {{ order.status_label }}</b><span>{{ order.summary_title }} · {{ money(order.total_amount) }} · {{ date(order.ordered_at) }}</span></li></ul><div v-if="!ordersLoading && !ordersError && orderPages > 1" class="as-pagination"><button v-if="orderPage > 1" @click="loadOrders(orderPage - 1)">이전</button><span>{{ orderPage }} / {{ orderPages }}</span><button v-if="orderPage < orderPages" @click="loadOrders(orderPage + 1)">다음</button></div></section>
    <section v-show="activeTab === 'addresses'" class="as-card as-wide"><h2>배송지 관리</h2><p v-if="addressesLoading" role="status">배송지를 불러오는 중입니다.</p><p v-else-if="addressesError" role="alert">배송지를 불러오지 못했습니다. <button type="button" class="as-secondary" @click="loadAddresses">다시 시도</button></p><p v-else-if="!addresses.length">등록된 배송지가 없습니다.</p><ul v-if="!addressesLoading && !addressesError" class="as-list"><li v-for="address in addresses" :key="address.address_id"><b>{{ address.alias }} <small v-if="address.is_default">기본 배송지</small></b><span>{{ address.receiver }} · {{ address.phone }} · ({{ address.zipcode }}) {{ address.address1 }} {{ address.address2 }}</span><div><button type="button" class="as-secondary" @click="editAddress(address)">수정</button> <button type="button" class="as-secondary" @click="deleteAddress(address)">삭제</button></div></li></ul><h3>{{ addressId ? '배송지 수정' : '배송지 추가' }}</h3><form class="as-fields" @submit.prevent="saveAddress"><label>배송지 이름<input v-model.trim="addressForm.alias" required maxlength="50"></label><label>받는 분<input v-model.trim="addressForm.receiver" required maxlength="60"></label><label>연락처<input v-model.trim="addressForm.phone" required maxlength="20"></label><label>우편번호<input v-model.trim="addressForm.zipcode" required maxlength="10"></label><label>기본 주소<input v-model.trim="addressForm.address1" required maxlength="255"></label><label>상세 주소<input v-model.trim="addressForm.address2" maxlength="255"></label><label>배송 요청사항<input v-model.trim="addressForm.request_memo" maxlength="255"></label><label class="as-check"><input v-model="addressForm.is_default" type="checkbox"> 기본 배송지로 설정</label><div><button :disabled="busy">{{ addressId ? '수정 저장' : '배송지 등록' }}</button> <button v-if="addressId" type="button" class="as-secondary" @click="resetAddress">취소</button></div></form></section>
    <section v-show="activeTab === 'profile'" class="as-card as-wide"><h2>회원탈퇴</h2><p>탈퇴 후에는 계정을 사용할 수 없습니다.</p><form @submit.prevent="withdraw"><label>탈퇴 사유 (선택)<textarea v-model.trim="reason" maxlength="500"></textarea></label><button class="as-danger" :disabled="busy">회원탈퇴</button></form></section>
  </div>
  </div></div>
</section>
</template>
<script setup>
import { onMounted, reactive, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import http from '../../api/http';
import { useAuthStore } from '../../stores/authStore';
import { memberApi } from '../../api/memberApi';
import { storefrontApi } from '../api.js';
const router=useRouter(), route=useRoute(), auth=useAuthStore();
const tabs=[{id:'overview',label:'마이홈'},{id:'orders',label:'주문내역'},{id:'coupons',label:'쿠폰'},{id:'addresses',label:'배송지 관리'},{id:'profile',label:'회원정보 수정'}];
const selectedTab=()=>tabs.some(item=>item.id===route.query.tab)?route.query.tab:'overview';
const activeTab=ref(selectedTab());
watch(()=>route.query.tab,()=>{activeTab.value=selectedTab()});
watch(activeTab,tab=>{if(tab!==selectedTab())router.replace({query:{...route.query,tab}});error.value='';message.value=''});
const recs=ref([]),recAlgorithm=ref(''),recLoading=ref(true),recError=ref('');
const orderStats=ref(null), orderStatsError=ref(false);
const orderSteps=[{key:'preparing',label:'상품 준비'},{key:'shipping',label:'배송 중'},{key:'delivered',label:'배송 완료'},{key:'cancelled',label:'주문 취소'}];
async function loadOrderStats(){orderStatsError.value=false;try{orderStats.value=(await http.get('/api/v1/orders/stats')).data}catch{orderStatsError.value=true}}
const wishedBooks=ref([]), wishLoading=ref(true), wishError=ref(''), wishPage=ref(1), wishPages=ref(1);
async function loadWishlist(page=1){wishLoading.value=true;wishError.value='';try{const data=await storefrontApi.wishlist(page);wishedBooks.value=data.items || [];wishPage.value=data.meta.page;wishPages.value=Math.max(1,data.meta.total_pages || 1)}catch(e){wishError.value='찜한 책을 불러오지 못했습니다.'}finally{wishLoading.value=false}}
async function loadRecommendations(){try{const data=await memberApi.recommendations(5);recs.value=data.items || [];recAlgorithm.value=data.algorithm || ''}catch(e){recError.value=e.userMessage || '추천 도서를 불러오지 못했습니다.'}finally{recLoading.value=false}}
const profile=reactive({name:'',nickname:'',phone:'',email:''}), coupons=ref([]), orders=ref([]), addresses=ref([]), code=ref(''), reason=ref(''), error=ref(''), message=ref(''), busy=ref(false), orderPage=ref(1), orderPages=ref(1), addressId=ref(null);
const couponsLoading=ref(true),couponsLoaded=ref(false),couponsError=ref(false),ordersLoading=ref(true),ordersError=ref(false),addressesLoading=ref(true),addressesError=ref(false);
const blankAddress=()=>({alias:'',receiver:'',phone:'',zipcode:'',address1:'',address2:'',request_memo:'',is_default:false});
const addressForm=reactive(blankAddress());
const money=n=>`${Number(n || 0).toLocaleString('ko-KR')}원`, date=s=>s ? new Date(s).toLocaleDateString('ko-KR',{timeZone:'Asia/Seoul'}) : '';
function failure(e){ error.value=e.userMessage || '요청을 처리하지 못했습니다.'; }
async function run(fn, success=''){ if(busy.value)return; error.value=''; message.value=''; busy.value=true; try { await fn(); message.value=success; } catch(e){failure(e)} finally {busy.value=false} }
async function loadOrders(page=1){ordersLoading.value=true;ordersError.value=false;try{const {data}=await http.get('/api/v1/orders',{params:{page,size:10}});orders.value=data.items;orderPage.value=page;orderPages.value=data.meta.total_pages || 1}catch{ordersError.value=true}finally{ordersLoading.value=false}}
async function loadCoupons(){couponsLoading.value=true;couponsError.value=false;try{coupons.value=(await http.get('/api/v1/members/me/coupons')).data;couponsLoaded.value=true}catch{couponsError.value=true;couponsLoaded.value=false}finally{couponsLoading.value=false}}
async function loadAddresses(){addressesLoading.value=true;addressesError.value=false;try{addresses.value=(await http.get('/api/v1/members/me/addresses')).data}catch{addressesError.value=true}finally{addressesLoading.value=false}}
onMounted(async()=>{const results=await Promise.allSettled([http.get('/api/v1/members/me').then(r=>Object.assign(profile,r.data)),loadCoupons(),loadAddresses(),loadOrders(),loadOrderStats(),loadRecommendations(),...(auth.isAdmin ? [] : [loadWishlist()])]); const failed=results.find(r=>r.status==='rejected'); if(failed) failure(failed.reason);});
function saveProfile(){run(async()=>{const {data}=await http.put('/api/v1/members/me',{name:profile.name,nickname:profile.nickname || null,phone:profile.phone || null}); Object.assign(profile,data); await auth.fetchMe();},'회원정보를 저장했습니다.');}
function registerCoupon(){run(async()=>{await http.post('/api/v1/members/me/coupons',{code:code.value}); code.value=''; await loadCoupons();},'쿠폰을 등록했습니다.');}
function resetAddress(){addressId.value=null; Object.assign(addressForm,blankAddress())}
function editAddress(a){addressId.value=a.address_id; Object.assign(addressForm,blankAddress(),a)}
function saveAddress(){run(async()=>{const body={...addressForm}; delete body.address_id; if(addressId.value) await http.put(`/api/v1/members/me/addresses/${addressId.value}`,body); else await http.post('/api/v1/members/me/addresses',body); resetAddress(); await loadAddresses();},'배송지를 저장했습니다.');}
function deleteAddress(a){if(!window.confirm(`'${a.alias}' 배송지를 삭제하시겠습니까?`))return; run(async()=>{await http.delete(`/api/v1/members/me/addresses/${a.address_id}`); if(addressId.value===a.address_id) resetAddress(); await loadAddresses();},'배송지를 삭제했습니다.');}
function withdraw(){if(!window.confirm('정말 회원탈퇴하시겠습니까? 탈퇴 후 계정을 사용할 수 없습니다.'))return; run(async()=>{await http.post('/api/v1/auth/withdraw',{reason_code:'ETC',reason_text:reason.value || null}); auth.setUser(null); await router.push('/main');});}
</script>

<style scoped>
.mypage-book-icon{width:42px;height:42px;display:block;filter:drop-shadow(0 2px 2px #7952a218)}
@media(max-width:600px){.mypage-book-icon{width:34px;height:34px}}
</style>
