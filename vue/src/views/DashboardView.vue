<template>
  <section class="dashboard-page">
    <div class="dashboard-content">
      <div class="page-heading">
        <div><p class="eyebrow">MY BOOKSHELF</p><h1>{{ auth.isAdmin ? '시스템 관리자 대시보드' : '나의 책장' }}</h1><p>계정과 북적북적 서비스를 한곳에서 관리합니다.</p></div>
        <a class="date-button" href="/shop.html">책 둘러보기 <span aria-hidden="true">→</span></a>
      </div>
      <section class="metric-grid" aria-label="계정 정보">
        <article class="dashboard-card metric-card"><div class="metric-top"><span>로그인 사용자</span><span class="metric-icon mint">♙</span></div><strong class="metric-value">{{ auth.user?.display_name }}</strong><div class="metric-bottom"><span class="positive">@{{ auth.user?.username }}</span><span>내 계정</span></div></article>
        <article class="dashboard-card metric-card"><div class="metric-top"><span>사용자 유형</span><span class="metric-icon lavender">◇</span></div><strong class="metric-value">{{ auth.isAdmin ? '관리자' : '일반 회원' }}</strong><div class="metric-bottom"><span class="positive">{{ auth.user?.role }}</span><span>현재 권한</span></div></article>
        <article class="dashboard-card metric-card"><div class="metric-top"><span>계정 상태</span><span class="metric-icon blue">✓</span></div><strong class="metric-value">{{ auth.user?.is_active ? '활성' : '비활성' }}</strong><div class="metric-bottom"><span class="positive">세션 인증</span><span>서버 확인 완료</span></div></article>
        <article class="dashboard-card metric-card"><div class="metric-top"><span>책장 바로가기</span><span class="metric-icon peach">▤</span></div><strong class="metric-value">북스토어</strong><div class="metric-bottom"><a class="positive" href="/shop.html">오늘의 책 보기 →</a><span>도서 둘러보기</span></div></article>
      </section>
      <section class="admin-profile dashboard-card" aria-labelledby="profile-title">
        <div class="profile-heading"><div class="profile-symbol">{{ auth.isAdmin ? '♙' : '♡' }}</div><div><p class="eyebrow">ACCOUNT OVERVIEW</p><h2 id="profile-title">{{ auth.isAdmin ? '시스템 관리자' : '내 계정' }}</h2><p>계정 정보와 서비스 이용 메뉴를 확인하세요.</p></div><span class="importance-badge">{{ auth.user?.is_active ? '정상 이용 중' : '이용 제한' }}</span></div>
        <dl class="profile-grid">
          <div class="profile-item"><dt>아이디</dt><dd>{{ auth.user?.username }}</dd></div>
          <div class="profile-item"><dt>이메일</dt><dd>{{ auth.user?.email }}</dd></div>
          <div class="profile-item"><dt>권한</dt><dd>{{ auth.isAdmin ? '시스템 관리자' : '일반 회원' }}</dd></div>
          <div class="profile-item"><dt>사용자명</dt><dd>{{ auth.user?.display_name }}</dd></div>
          <div class="profile-item"><dt>서비스</dt><dd>북적북적 도서 쇼핑몰</dd></div>
          <div class="profile-item"><dt>세션 상태</dt><dd>FastAPI 서버 인증 완료</dd></div>
        </dl>
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
import { useAuthStore } from '../stores/authStore'
const auth = useAuthStore()
</script>
