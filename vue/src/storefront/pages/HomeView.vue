<template>
<section id="shop-view">
      <section class="hero" aria-label="책장 추천 배너">
        <div class="hero-carousel">
          <article v-for="(banner,index) in banners" :key="banner.book" class="hero-slide" :class="[banner.tone,{active:index===activeBanner}]" role="button" tabindex="0" @click="openProduct(banner.book)" @keydown.enter="openProduct(banner.book)" @keydown.space.prevent="openProduct(banner.book)">
            <div class="hero-copy"><div class="eyebrow">{{ banner.label }}</div><h1>{{ banner.book }}</h1><p>{{ banner.copy }}</p><span class="banner-cta">책 자세히 보기&nbsp; →</span></div>
            <div class="hero-art" aria-hidden="true"><div class="art-orbit"></div><div class="hero-poster"><img :src="coverUrl(findBook(banner.book))" alt="" /></div></div>
          </article>
        </div>
        <div class="hero-controls" aria-label="추천 도서 배너 탐색">
          <button type="button" class="hero-arrow" @click="moveBanner(-1)" aria-label="이전 배너">‹</button>
          <span class="hero-count" aria-live="polite"><strong>{{ activeBanner + 1 }}</strong> / {{ banners.length }}</span>
          <button type="button" class="hero-arrow" @click="moveBanner(1)" aria-label="다음 배너">›</button>
        </div>
      </section>
      <div class="quick-info"><span><b>빠른 출고</b> 오후 2시 전 주문</span><span><b>구매혜택</b> 배송비 무료</span></div>
      <section class="section" id="books"><div class="section-head"><div><h3 id="home-books-title" tabindex="-1">{{ searchQuery.trim() ? '도서 검색 결과' : '국내도서 추천' }}</h3></div><div class="domestic-shelf-sort" role="group" aria-label="국내도서 추천 정렬">
        <button v-for="option in domesticSortOptions" :key="option.value" type="button"
          :aria-pressed="homeSort === option.value" @click="homeSort = option.value">{{ option.label }}</button>
      </div><button class="more" @click="navigate('domestic')">전체보기&nbsp; →</button></div><div class="categories"><button v-for="category in homeCategories" :key="category.name" class="category-tile" :class="{active:selectedHomeCategory===category.name}" :aria-pressed="selectedHomeCategory===category.name" @click="selectedHomeCategory=category.name"><span v-html="category.icon"></span>{{ category.name }}</button></div><div class="book-grid"><book-card v-for="book in homeBooks" :key="book.id" :book="book" :wished="wishlist.has(book.title)" @wish="toggleWish" @buy="addCart" @detail="openProduct"></book-card></div><p v-if="!homeBooks.length" class="empty-catalog">검색 결과가 없습니다.</p></section>
      <section class="section home-new-section" aria-labelledby="new-books-heading"><div class="section-head"><div><h2 id="new-books-heading">새로 들어온 책</h2></div><span class="catalog-count">{{ newBooks.length }}권</span></div><div class="book-grid home-new-grid"><book-card v-for="book in newBooks" :key="book.id" :book="book" :wished="wishlist.has(book.title)" @wish="toggleWish" @buy="addCart" @detail="openProduct"></book-card></div><p v-if="!newBooks.length" class="empty-catalog">새로 등록된 책이 없습니다.</p></section>
      <section class="section home-theme-section" aria-labelledby="theme-books-heading"><div class="section-head"><div><h2 id="theme-books-heading">주제별 책장</h2><p>지금의 기분과 관심사에 맞춰 골라봤어요.</p></div><button class="more" @click="navigate('curation')">추천 책장 더 보기 →</button></div><div class="theme-shelf-list"><article v-for="shelf in themeShelves" :key="shelf.title" class="theme-shelf"><div class="theme-shelf-heading"><h3>{{ shelf.title }}</h3><p>{{ shelf.note }}</p></div><div class="theme-shelf-books"><button v-for="book in shelf.books" :key="book.title" @click="openProduct(book)"><img :src="coverUrl(book)" :alt="book.cover_image ? book.title + ' 표지' : '도서 분야 안내 이미지'" @error="$event.target.onerror=null; $event.target.src='/assets/covers/category-default.png'; $event.target.alt='도서 분야 안내 이미지'" /><span><b>{{ book.title }}</b><small>{{ book.author }}</small></span><i>책 보기 →</i></button></div></article></div></section>
    </section>
</template>

<script>
import { useStorefrontContext } from '../context.js';
import BookCard from '../BookCard.vue';

export default { components: { BookCard }, setup: useStorefrontContext };
</script>
