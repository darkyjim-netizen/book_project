<template>
<section id="shop-view">
      <section v-if="banners.length" class="hero" aria-label="책장 추천 배너">
        <div class="hero-carousel">
          <article v-for="(banner,index) in banners" :key="banner.book" class="hero-slide" :class="[banner.tone,{active:index===activeBanner}]" role="button" tabindex="0" @click="openProduct(banner.book)" @keydown.enter="openProduct(banner.book)" @keydown.space.prevent="openProduct(banner.book)">
            <div class="hero-copy"><div class="eyebrow">{{ banner.label }}</div><h1>{{ banner.book }}</h1><p>{{ banner.copy }}</p><p v-if="bannerDescriptions[banner.book]" class="hero-book-description">{{ bannerDescriptions[banner.book] }}</p><span class="banner-cta">책 자세히 보기&nbsp; →</span></div>
            <div class="hero-art" aria-hidden="true"><div class="art-orbit"></div><div class="hero-poster"><img :src="coverUrl(findBook(banner.book))" alt="" /></div></div>
          </article>
        </div>
        <div v-if="banners.length > 1" class="hero-dots" role="group" aria-label="배너 선택"><button v-for="(banner,index) in banners" :key="banner.book" type="button" :aria-label="`${index+1}번 배너: ${banner.book}`" :aria-pressed="activeBanner===index" @click="activeBanner=index"><span></span></button></div>
        <div v-if="banners.length > 1" class="hero-controls" aria-label="추천 도서 배너 탐색">
          <button type="button" class="hero-arrow" @click="moveBanner(-1)" aria-label="이전 배너">‹</button>
          <span class="hero-count" aria-live="polite"><strong>{{ activeBanner + 1 }}</strong> / {{ banners.length }}</span>
          <button type="button" class="hero-arrow" @click="moveBanner(1)" aria-label="다음 배너">›</button>
        </div>
      </section>
      <p v-else-if="catalogLoading" class="empty-catalog" role="status">도서 목록을 불러오고 있습니다.</p>
      <p v-else-if="catalogError" class="empty-catalog" role="alert">{{ catalogError }}</p>
      <section class="section" id="books"><div class="section-head"><div><h3 id="home-books-title" tabindex="-1">{{ searchQuery.trim() ? '도서 검색 결과' : '국내도서 추천' }}</h3></div><div class="domestic-shelf-sort" role="group" aria-label="국내도서 추천 정렬">
        <button v-for="option in domesticSortOptions" :key="option.value" type="button"
          :aria-pressed="homeSort === option.value" @click="homeSort = option.value">{{ option.label }}</button>
      </div><button class="more" @click="navigate('domestic')">전체보기&nbsp; →</button></div><div class="categories"><button v-for="category in homeCategories" :key="category.name" class="category-tile" :class="{active:selectedHomeCategory===category.name}" :aria-pressed="selectedHomeCategory===category.name" @click="selectedHomeCategory=category.name"><span v-html="category.icon"></span>{{ category.name }}</button></div><div class="book-grid"><book-card v-for="book in homeBooks" :key="book.id" :book="book" :wished="wishlist.has(String(book.id))" @wish="toggleWish" @buy="addCart" @detail="openProduct"></book-card></div><p v-if="!homeBooks.length" class="empty-catalog">{{ catalogLoading ? '도서 목록을 불러오고 있습니다.' : searchQuery.trim() ? '검색 결과가 없습니다.' : '표시할 도서가 없습니다.' }}</p></section>
      <section class="section home-new-section" aria-labelledby="new-books-heading"><div class="section-head"><div><h2 id="new-books-heading">새로 입고된 책</h2></div><span class="catalog-count">{{ newBooks.length }}권</span></div><div class="book-grid home-new-grid"><book-card v-for="book in newBooks" :key="book.id" :book="book" :wished="wishlist.has(String(book.id))" @wish="toggleWish" @buy="addCart" @detail="openProduct"></book-card></div><p v-if="!newBooks.length" class="empty-catalog">{{ catalogLoading ? '도서 목록을 불러오고 있습니다.' : '새로 등록된 책이 없습니다.' }}</p></section>
      <section class="section home-theme-section" aria-labelledby="theme-books-heading">
        <div class="section-head"><div><h2 id="theme-books-heading">주제별 책장</h2><p>관심 있는 분야에서 새로운 책을 발견해 보세요.</p></div><button class="more" @click="navigate('curation')">추천 책장 더 보기 →</button></div>
        <div v-if="themeShelves.length" class="theme-shelf-list">
          <article v-for="(shelf, index) in themeShelves" :key="shelf.title" class="theme-shelf">
            <div class="theme-shelf-heading"><span class="theme-number">{{ String(index + 1).padStart(2, '0') }}</span><h3>{{ shelf.title }}</h3><p>{{ shelf.title }} 분야에서 골라본 책</p></div>
            <div class="theme-shelf-books"><button v-for="book in shelf.books" :key="book.title" type="button" @click="openProduct(book)"><img :src="coverUrl(book)" :alt="book.cover_image ? book.title + ' 표지' : '도서 분야 안내 이미지'" @error="$event.target.onerror=null; $event.target.src='/assets/covers/category-default.png'; $event.target.alt='도서 분야 안내 이미지'" /><span><b>{{ book.title }}</b><small>{{ book.author || '저자 정보 없음' }}</small><i>자세히 보기 →</i></span></button></div>
          </article>
        </div><p v-else class="empty-catalog">{{ catalogLoading ? '도서 목록을 불러오고 있습니다.' : '표시할 도서가 없습니다.' }}</p>
      </section>
    </section>
</template>

<script>
import { ref, watch } from 'vue';
import { storefrontApi } from '../api.js';
import { useStorefrontContext } from '../context.js';
import BookCard from '../BookCard.vue';
import { useAuthStore } from '../../stores/authStore.js';

export default {
  components: { BookCard },
  setup() {
    const context = useStorefrontContext();
    const bannerDescriptions = ref({});
    watch(() => context.banners.value.map(banner => context.findBook(banner.book)?.id).join(','), async (_, previous, onCleanup) => {
      let current = true;
      onCleanup(() => { current = false; });
      const entries = await Promise.all(context.banners.value.map(async banner => {
        const book = context.findBook(banner.book);
        if (!book?.id) return [banner.book, ''];
        try {
          const detail = await storefrontApi.getBook(book.id);
          const raw = detail.summary || detail.description || '';
          const text = String(raw).replace(/<[^>]*>/g, ' ').replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&').replace(/\s+/g, ' ').trim();
          const sentences = text.match(/^.*?[.!?。](?:\s|$)/)?.[0]?.trim() || text;
          return [banner.book, sentences.length > 115 ? sentences.slice(0, 112) + '…' : sentences];
        } catch { return [banner.book, '']; }
      }));
      if (current) bannerDescriptions.value = Object.fromEntries(entries);
    }, { immediate: true });
    return { ...context, auth: useAuthStore(), bannerDescriptions };
  }
};
</script>

<style scoped>
#shop-view .hero-copy .hero-book-description{display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:2;overflow:hidden;max-width:480px;margin:14px 0 0;color:#efe7f9;font-size:16px;line-height:1.65;word-break:keep-all}
@media(max-width:600px){#shop-view .hero-copy .hero-book-description{font-size:14px;max-width:100%;margin-top:10px}}
</style>
