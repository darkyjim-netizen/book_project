<template>
<section class="admin-dashboard db-dashboard">
  <div class="dashboard-content">
    <form v-if="!member && !checking" class="dashboard-card admin-auth" @submit.prevent="login"><h1>관리자 로그인</h1><p>관리자 계정으로 로그인해 주세요.</p><label>이메일<input v-model.trim="email" type="email" required autocomplete="username" /></label><label>비밀번호<input v-model="password" type="password" required autocomplete="current-password" /></label><button class="primary" type="submit">로그인</button><p v-if="error" role="alert" class="admin-error">{{ error }}</p></form>
    <p v-else-if="checking">관리자 권한 확인 중...</p>
    <template v-else>
      <div class="admin-workspace">
      <aside class="admin-side"><p class="admin-side-kicker">북적북적 관리자</p><h1>운영 관리</h1><p class="admin-side-label">AI 분석</p><nav aria-label="AI 분석"><button v-for="item in analysisTabs" :key="item.id" type="button" :aria-current="tab === item.id ? 'page' : null" @click="changeTab(item.id)">{{ item.label }} <span aria-hidden="true">›</span></button></nav><p class="admin-side-label admin-side-group">관리 메뉴</p><nav aria-label="관리 메뉴"><button v-for="item in tabs" :key="item.id" type="button" :aria-current="tab === item.id ? 'page' : null" @click="changeTab(item.id)">{{ item.label }} <span aria-hidden="true">›</span></button></nav><p class="admin-side-note">북적북적의 오늘을<br />한눈에 살펴보세요.</p></aside>
      <div class="admin-workspace-main">
      <div class="admin-welcome"><div class="admin-welcome-person"><div class="admin-welcome-icon" aria-hidden="true">✳</div><div><h2>{{ member.nickname || member.name || '관리자' }}님, 안녕하세요</h2><p>매장의 현황을 한곳에서 확인하고 관리하세요.</p></div></div><button v-if="!extraTabs.includes(tab) && !analysisTabs.some(item => item.id === tab)" type="button" class="admin-refresh" :disabled="loading" @click="tab === 'overview' ? loadOverview() : loadList(page)">↻ 새로고침</button></div>
      <div class="admin-section-heading"><div><span>{{ analysisTabs.some(item => item.id === tab) ? 'AI 분석' : '운영 현황' }}</span><h2>{{ [...analysisTabs, ...tabs].find(item => item.id === tab)?.label }}</h2><p>{{ tab === 'overview' ? '매출과 주문, 재고 현황을 확인하세요.' : '운영 정보를 확인하고 관리하세요.' }}</p></div></div>
      <p v-if="error" role="alert" class="admin-error">{{ error }}</p><p v-if="loading">데이터를 불러오는 중입니다...</p>
      <AdminOperations v-if="extraTabs.includes(tab)" :section="tab" />
      <AdminAnalysis v-if="analysisTabs.some(item => item.id === tab)" :section="tab" @show-reviews="changeTab('reviews')" />
      <template v-if="tab === 'overview' && overview && !loading">
        <section class="metric-grid"><article v-for="metric in metrics" :key="metric.label" class="dashboard-card metric-card"><div class="metric-top">{{ metric.label }}</div><strong class="metric-value">{{ metric.value }}</strong><div class="metric-bottom">{{ metric.note }}</div></article></section>
        <section class="admin-operations" aria-labelledby="admin-operations-title">
          <div class="admin-operations-heading"><div><h2 id="admin-operations-title">운영 현황</h2><p>처리가 필요한 주문과 재고를 확인하세요.</p></div><button type="button" @click="changeTab('books')">도서 상품 관리 →</button></div>
          <div class="admin-operations-grid"><article><span>결제 완료 주문</span><strong>{{ Number(overview.paid_orders).toLocaleString() }}건</strong><small>결제 후 상품 준비 전</small></article><article><span>재고 부족 도서</span><strong>{{ Number(overview.low_stock_books).toLocaleString() }}종</strong><small>판매 중 · 안전 재고 이하</small></article><article><span>재고 없는 도서</span><strong>{{ Number(overview.out_of_stock_books).toLocaleString() }}종</strong><small>판매 중 또는 품절 · 재고 0 이하</small></article></div>
        </section>
        <section class="dashboard-lower analytics-grid" aria-label="주문 통계">
          <article v-for="chart in charts" :key="chart.title" class="dashboard-card admin-chart">
            <div class="card-heading"><div><h2>{{ chart.title }}</h2><p>{{ chart.note }}</p></div></div>
            <template v-if="chartTotal(chart.rows) > 0">
              <div class="admin-donut" :style="{background: chartGradient(chart.rows)}" aria-hidden="true"><div><small>총 주문</small><strong>{{ chartTotal(chart.rows).toLocaleString() }}건</strong></div></div>
              <ul class="admin-chart-legend"><li v-for="(row, index) in chart.rows" :key="row.label"><span class="legend-label"><i :style="{background: chartColor(index)}" aria-hidden="true"></i>{{ row.label }}</span><b>{{ Number(row.count).toLocaleString() }}건 <small>({{ chartPercent(row.count, chart.rows) }}%)</small></b></li></ul>
            </template><p v-else class="admin-empty">집계된 주문이 없습니다.</p>
          </article>
        </section>
        <p class="data-note">매출은 결제 완료 금액에서 부분 취소액을 차감한 값입니다. 구매 패턴은 결제 완료 후 진행 중인 주문의 건수이며, 연령은 주문 당시 생년월일 기준, 지역은 배송지 첫 항목 기준입니다.</p>
      </template>
      <template v-if="tab === 'books'"><div class="admin-toolbar"><h2>도서 상품 관리</h2><form @submit.prevent="searchList"><input v-model.trim="keyword" placeholder="도서명 검색" /><button>검색</button></form><button @click="newBook">＋ 도서 등록</button></div>
        <form v-if="editing" class="dashboard-card admin-editor" @submit.prevent="saveBook"><h3>{{ editingId ? '도서 수정' : '도서 등록' }}</h3><div class="admin-fields"><label v-if="!editingId">국제 표준 도서번호 13자리<input v-model="bookForm.isbn13" required pattern="[0-9]{13}" /></label><label>도서명<input v-model.trim="bookForm.title" required /></label><label v-if="!editingId">카테고리 번호<input v-model.number="bookForm.category_id" type="number" min="1" required /></label><label v-if="!editingId">출판사 번호<input v-model.number="bookForm.publisher_id" type="number" min="1" required /></label><label v-if="!editingId">저자 번호 (쉼표 구분, 선택)<input v-model="authorIds" placeholder="예: 1, 2" /></label><label>정가<input v-model.number="bookForm.list_price" type="number" min="0" required /></label><label>판매가<input v-model.number="bookForm.sale_price" type="number" min="0" required /></label><label>재고<input v-model.number="bookForm.stock_qty" type="number" min="0" required /></label></div><div class="admin-actions"><button type="submit">저장</button><button type="button" @click="editing = false">취소</button></div></form>
        <div class="dashboard-card table-wrap"><table><thead><tr><th>도서명</th><th>저자</th><th>판매가</th><th>재고</th><th>관리</th></tr></thead><tbody><tr v-for="book in items" :key="book.book_id"><td>{{ book.title }}</td><td>{{ book.authors.join(', ') || '미등록' }}</td><td>{{ Number(book.sale_price).toLocaleString() }}원</td><td>{{ book.stock_qty }}</td><td class="row-actions"><button @click="editBook(book)">수정</button><button @click="deleteBook(book)">삭제</button></td></tr><tr v-if="!items.length && !loading"><td colspan="5">도서가 없습니다.</td></tr></tbody></table></div></template>
      <template v-if="tab === 'members'"><div class="admin-toolbar"><h2>회원 관리</h2><form @submit.prevent="searchList"><input v-model.trim="keyword" placeholder="회원 검색" /><button>검색</button></form></div><div class="dashboard-card table-wrap"><table><thead><tr><th>이름</th><th>이메일</th><th>권한</th><th>상태</th><th>관리</th></tr></thead><tbody><tr v-for="person in items" :key="person.member_id"><td>{{ person.name }}</td><td>{{ person.email }}</td><td>{{ roleLabel(person.role) }}</td><td>{{ statusLabel(person.status) }}</td><td><button @click="showMember(person.member_id)">상세</button></td></tr><tr v-if="!items.length && !loading"><td colspan="5">회원이 없습니다.</td></tr></tbody></table></div><section v-if="selectedMember" class="dashboard-card admin-editor"><h3>회원 상세</h3><p>{{ selectedMember.member.name }} · {{ selectedMember.member.email }}</p><p>연락처: {{ selectedMember.member.phone || '미등록' }}</p><div v-if="member.role === 'ADMIN'" class="admin-actions"><button v-if="selectedMember.member.status === 'ACTIVE'" @click="setStatus('SUSPENDED')">이용 정지</button><button v-if="selectedMember.member.status === 'SUSPENDED'" @click="setStatus('ACTIVE')">이용 재개</button></div></section></template>
      <nav v-if="['books','members'].includes(tab) && pages > 1" class="domestic-pagination" aria-label="목록 페이지"><button :disabled="page <= 1" @click="changePage(page - 1)">이전</button><span>{{ page }} / {{ pages }}</span><button :disabled="page >= pages" @click="changePage(page + 1)">다음</button></nav>
      </div></div>
    </template>
  </div>
</section>
</template>
<script setup>
import { computed, onMounted, ref } from 'vue';
import { storefrontApi as api } from '../api.js';
import { useAuthStore } from '../../stores/authStore.js';
import { useRoute } from 'vue-router';
import AdminOperations from './AdminOperations.vue';
import AdminAnalysis from './AdminAnalysis.vue';
const auth = useAuthStore();
const member=ref(null), checking=ref(true), loading=ref(false), error=ref(''), email=ref(''), password=ref(''), tab=ref('overview'), overview=ref(null), items=ref([]), page=ref(1), pages=ref(1), keyword=ref(''), selectedMember=ref(null), editing=ref(false), editingId=ref(null), bookForm=ref({}), authorIds=ref('');
const extraTabs=['orders','refunds','qna','reviews','notices','coupons'];
const analysisTabs=[{id:'sentiment',label:'리뷰 감성 분석'},{id:'sales',label:'인기 도서 분야'},{id:'customers',label:'고객 구매 분석'},{id:'churn',label:'이탈 가능성 분석'}];
const tabs=[{id:'overview',label:'대시보드'},{id:'books',label:'도서 상품 관리'},{id:'members',label:'회원 관리'},{id:'orders',label:'주문·배송 관리'},{id:'refunds',label:'취소·환불 관리'},{id:'qna',label:'고객 문의 관리'},{id:'reviews',label:'리뷰 관리'},{id:'notices',label:'공지사항 관리'},{id:'coupons',label:'쿠폰 관리'}];
const route = useRoute();
if (['orders', 'refunds'].includes(route.query.tab)) tab.value = route.query.tab;
const roleLabel = role => ({USER:'일반 회원', SELLER:'판매자', STAFF:'직원', ADMIN:'관리자'}[role] || '확인 필요');
const statusLabel = status => ({ACTIVE:'정상', DORMANT:'휴면', SUSPENDED:'이용 정지', WITHDRAWN:'탈퇴'}[status] || '확인 필요');
const metrics=computed(()=>[{label:'총 매출',value:`${Number(overview.value.total_sales).toLocaleString()}원`,note:'결제 완료 기준'}, {label:'누적 회원 수',value:`${Number(overview.value.member_count).toLocaleString()}명`,note:'전체 회원'}, {label:'오늘 주문 건수',value:`${dailyRows.value.at(-1).count.toLocaleString()}건`,note:'한국 시간 기준'}, {label:'전체 주문 건수',value:`${Number(overview.value.order_count).toLocaleString()}건`,note:'모든 주문 상태 포함'}]);
const dailyRows=computed(()=>{const today=new Date(new Date().toLocaleString('en-US',{timeZone:'Asia/Seoul'}));const counts=Object.fromEntries((overview.value?.daily_orders || []).map(x=>[x.day,x.count]));return Array.from({length:7},(_,i)=>{const d=new Date(Date.UTC(today.getFullYear(),today.getMonth(),today.getDate()-6+i));const key=d.toISOString().slice(0,10);return {label:key.slice(5),count:counts[key] || 0};});});
const charts=computed(()=>[{title:'일별 주문 건수',note:'최근 7일 · 모든 주문 상태',rows:dailyRows.value},{title:'연령대별 주문 분포',note:'결제 완료 후 진행 중인 주문 · 생년월일 미입력 및 비회원은 미상',rows:overview.value?.age_groups || []},{title:'지역별 주문 분포',note:'결제 완료 후 진행 중인 주문 · 배송지 기준',rows:overview.value?.regions || []}]);
const chartColors=['#65419a','#a487d0','#d6b5e8','#8676c5','#c77da3','#739bb5','#78a895','#d3a66a','#7993cd','#b58dba'];
const chartColor=index=>chartColors[index % chartColors.length];
const chartTotal=rows=>rows.reduce((sum,row)=>sum+Math.max(0,Number(row.count)||0),0);
const chartPercent=(count,rows)=>(100*(Number(count)||0)/chartTotal(rows)).toFixed(1);
function chartGradient(rows){const total=chartTotal(rows);let position=0;const stops=rows.map((row,index)=>{const start=position;position+=Math.max(0,Number(row.count)||0)/total*100;return `${chartColor(index)} ${start}% ${position}%`});return `conic-gradient(${stops.join(',')})`;}
async function authenticate(){try{const result=await api.me(); if (!['ADMIN','STAFF'].includes(result.role)) throw new Error('관리자 권한이 필요합니다.'); member.value=result; await auth.fetchMe(); await loadOverview();}catch(e){member.value=null; if(e.status !== 401) error.value=e.message;}finally{checking.value=false;}}
async function login(){error.value='';try{await api.adminLogin(email.value,password.value); password.value=''; await authenticate();}catch(e){error.value=e.message;}}
async function loadOverview(){loading.value=true;error.value='';try{overview.value=await api.adminOverview();}catch(e){error.value=e.message;}finally{loading.value=false;}}
async function changeTab(id){tab.value=id;keyword.value='';items.value=[];editing.value=false;selectedMember.value=null;if(id==='overview') await loadOverview();else if(['books','members'].includes(id)) await loadList(1);}
async function loadList(n){loading.value=true;error.value='';try{const result=await (tab.value==='books'?api.adminBooks(n,keyword.value):api.adminMembers(n,keyword.value));items.value=result.items;page.value=result.meta.page;pages.value=Math.max(1,result.meta.total_pages);}catch(e){error.value=e.message;}finally{loading.value=false;}}
async function changePage(nextPage){ await loadList(nextPage); if (page.value === nextPage) window.scrollTo({ top: 0, behavior: 'smooth' }); }
function searchList(){loadList(1);}
function newBook(){editingId.value=null;bookForm.value={isbn13:'',title:'',category_id:null,publisher_id:null,list_price:0,sale_price:0,stock_qty:0};authorIds.value='';editing.value=true;}
function editBook(book){editingId.value=book.book_id;bookForm.value={title:book.title,list_price:book.list_price,sale_price:book.sale_price,stock_qty:book.stock_qty};editing.value=true;}
async function saveBook(){try{error.value='';const payload={...bookForm.value};if(!editingId.value){const raw=authorIds.value.trim();if(raw && !/^\d+(\s*,\s*\d+)*$/.test(raw)) throw new Error('저자 번호는 숫자를 쉼표로 구분해 입력해 주세요.');payload.author_ids=raw?raw.split(',').map(Number):[];}await api.saveAdminBook(editingId.value,payload);editing.value=false;await loadList(page.value);}catch(e){error.value=e.message;}}
async function deleteBook(book){if(!confirm(`“${book.title}” 도서를 삭제하시겠습니까?`)) return;try{await api.deleteAdminBook(book.book_id);await loadList(page.value);}catch(e){error.value=e.message;}}
async function showMember(id){try{error.value='';selectedMember.value=await api.adminMember(id);}catch(e){error.value=e.message;}}
async function setStatus(status){if(!confirm(`회원 상태를 ${status === 'ACTIVE' ? '이용 재개' : '이용 정지'}로 변경하시겠습니까?`)) return;try{await api.setMemberStatus(selectedMember.value.member.member_id,status);await showMember(selectedMember.value.member.member_id);await loadList(page.value);}catch(e){error.value=e.message;}}
onMounted(authenticate);
</script>

