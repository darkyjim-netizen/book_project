<template>
  <section class="dashboard-page">
    <!-- [백엔드 연동 수정] 회원 필드를 백엔드 응답 이름에 맞춤: display_name → name, username → nickname(없으면 email),
         is_active → status === 'ACTIVE', role 은 'ADMIN' / 'USER' -->
    <div class="dashboard-content">
      <div class="page-heading">
        <div><p class="eyebrow">MY BOOKSHELF</p><h1>{{ auth.isAdmin ? '시스템 관리자 대시보드' : '나의 책장' }}</h1><p>계정과 북적북적 서비스를 한곳에서 관리합니다.</p></div>
        <a class="date-button" href="/shop.html">책 둘러보기 <span aria-hidden="true">→</span></a>
      </div>
      <section class="metric-grid" aria-label="계정 정보">
        <article class="dashboard-card metric-card"><div class="metric-top"><span>로그인 사용자</span><span class="metric-icon mint">♙</span></div><strong class="metric-value">{{ auth.user?.name }}</strong><div class="metric-bottom"><span class="positive">{{ auth.user?.nickname || auth.user?.email }}</span><span>내 계정</span></div></article>
        <article class="dashboard-card metric-card"><div class="metric-top"><span>사용자 유형</span><span class="metric-icon lavender">◇</span></div><strong class="metric-value">{{ auth.isAdmin ? '관리자' : '일반 회원' }}</strong><div class="metric-bottom"><span class="positive">{{ auth.user?.role }}</span><span>현재 권한</span></div></article>
        <article class="dashboard-card metric-card"><div class="metric-top"><span>계정 상태</span><span class="metric-icon blue">✓</span></div><strong class="metric-value">{{ auth.user?.status === 'ACTIVE' ? '활성' : '비활성' }}</strong><div class="metric-bottom"><span class="positive">세션 인증</span><span>서버 확인 완료</span></div></article>
        <article class="dashboard-card metric-card"><div class="metric-top"><span>책장 바로가기</span><span class="metric-icon peach">▤</span></div><strong class="metric-value">북스토어</strong><div class="metric-bottom"><a class="positive" href="/shop.html">오늘의 책 보기 →</a><span>도서 둘러보기</span></div></article>
      </section>
      <section class="admin-profile dashboard-card" aria-labelledby="profile-title">
        <div class="profile-heading"><div class="profile-symbol">{{ auth.isAdmin ? '♙' : '♡' }}</div><div><p class="eyebrow">ACCOUNT OVERVIEW</p><h2 id="profile-title">{{ auth.isAdmin ? '시스템 관리자' : '내 계정' }}</h2><p>계정 정보와 서비스 이용 메뉴를 확인하세요.</p></div><span class="importance-badge">{{ auth.user?.status === 'ACTIVE' ? '정상 이용 중' : '이용 제한' }}</span></div>
        <dl class="profile-grid">
          <div class="profile-item"><dt>닉네임</dt><dd>{{ auth.user?.nickname || '-' }}</dd></div>
          <div class="profile-item"><dt>이메일</dt><dd>{{ auth.user?.email }}</dd></div>
          <div class="profile-item"><dt>권한</dt><dd>{{ auth.isAdmin ? '시스템 관리자' : '일반 회원' }}</dd></div>
          <div class="profile-item"><dt>사용자명</dt><dd>{{ auth.user?.name }}</dd></div>
          <div class="profile-item"><dt>서비스</dt><dd>북적북적 도서 쇼핑몰</dd></div>
          <div class="profile-item"><dt>세션 상태</dt><dd>FastAPI 서버 인증 완료</dd></div>
        </dl>
      </section>
      <!-- [추가] 맞춤 추천 섹션. GET /ai/recommendations 결과를 보여 줍니다.
           구매 이력이 있는 회원은 SASRec 추천(SASREC), 신규 회원·비회원은 인기 도서(POPULAR)입니다. -->
      <section class="dashboard-card" aria-labelledby="rec-title" style="padding:24px;margin:24px 0">
        <p class="eyebrow">FOR YOU</p>
        <h2 id="rec-title">{{ recTitle }}</h2>
        <p v-if="recError" style="color:#b91c1c">{{ recError }}</p>
        <div v-else-if="recLoading">추천 도서를 불러오는 중...</div>
        <div v-else-if="!recs.length">추천할 도서가 아직 없습니다.</div>
        <div v-else style="display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:16px;margin-top:16px">
          <article v-for="b in recs" :key="b.book_id" style="display:flex;flex-direction:column;gap:6px">
            <img v-if="b.cover_image" :src="b.cover_image" :alt="b.title" style="width:100%;aspect-ratio:3/4;object-fit:cover;border-radius:8px" />
            <div v-else style="width:100%;aspect-ratio:3/4;border-radius:8px;background:#eef2f7;display:flex;align-items:center;justify-content:center;color:#94a3b8;font-size:13px">표지 없음</div>
            <strong style="font-size:14px;line-height:1.3">{{ b.title }}</strong>
            <small>{{ (b.authors || []).join(', ') }}</small>
            <span>{{ price(b.sale_price) }}</span>
            <small style="color:#64748b">{{ b.reason }}</small>
          </article>
        </div>
      </section>
      <section class="dashboard-lower">
        <RouterLink to="/profile" class="dashboard-card action-card"><span class="action-symbol">♙</span><div><h2>마이페이지</h2><p>이메일과 표시 이름을 확인하거나 수정합니다.</p></div><span class="action-arrow">→</span></RouterLink>
        <RouterLink v-if="auth.isAdmin" to="/admin/members" class="dashboard-card action-card"><span class="action-symbol lavender">⌘</span><div><h2>회원 관리</h2><p>회원 목록과 계정 권한을 관리합니다.</p></div><span class="action-arrow">→</span></RouterLink>
        <a v-if="auth.isAdmin" href="/shop.html#admin" class="dashboard-card action-card"><span class="action-symbol lavender">▤</span><div><h2>도서 데이터 관리</h2><p>도서 목록과 재고 관리 화면을 엽니다.</p></div><span class="action-arrow">→</span></a>
        <a href="/shop.html" class="dashboard-card action-card"><span class="action-symbol blue">▤</span><div><h2>책 쇼핑</h2><p>추천 도서와 책장 큐레이션을 둘러봅니다.</p></div><span class="action-arrow">→</span></a>
      </section>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { memberApi } from '../api/memberApi'
import { useAuthStore } from '../stores/authStore'
import { apiError } from '../utils/format'

const auth = useAuthStore()
// [추가] 맞춤 추천 데이터 (memberApi.recommendations → GET /ai/recommendations)
const recs = ref([])
const recAlgorithm = ref('')
const recLoading = ref(true)
const recError = ref('')
// SASREC: 구매 흐름 기반 추천, POPULAR: 인기 도서(구매 이력이 없는 신규 회원)
const recTitle = computed(() => recAlgorithm.value === 'SASREC' ? '회원님의 구매 흐름을 분석한 맞춤 추천' : '지금 많이 찾는 인기 도서')
const price = v => (v == null ? '' : `${Number(v).toLocaleString('ko-KR')}원`)

onMounted(async () => {
  try {
    const data = await memberApi.recommendations(5)
    recs.value = data.items || []
    recAlgorithm.value = data.algorithm || ''
  } catch (e) { recError.value = apiError(e) }
  finally { recLoading.value = false }
})
</script>
