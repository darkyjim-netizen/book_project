<template>
<section id="bestseller-view">
      <div class="bestseller-layout">
      <aside class="bestseller-category-nav" aria-label="베스트셀러 분류">
        <h2>베스트셀러</h2>
        <div class="bestseller-category-group">
          <h3>종합 베스트</h3>
          <button type="button" :aria-current="!selectedCategory ? 'page' : undefined" @click="selectCategory('')">주간</button>
        </div>
        <div class="bestseller-category-group bestseller-subjects">
          <h3>분야별 베스트</h3>
          <button v-for="category in domesticCategories" :key="category.name" type="button" :aria-current="selectedCategory === category.name ? 'page' : undefined" @click="selectCategory(category.name)">{{ category.name }}</button>
        </div>
      </aside>
      <div class="bestseller-content" id="bestseller-results">
      <header class="bestseller-header">
        <h1>{{ selectedCategory ? selectedCategory + ' 베스트셀러' : '베스트셀러' }}</h1>
        <p>{{ selectedCategory ? '이 분야의 도서를 만나보세요.' : '많은 독자가 선택한 책을 만나보세요.' }}</p>
        <p v-if="!selectedCategory" class="bestseller-source">교보문고 종합 주간 베스트 · 2026.10.28–11.03 집계 <a href="https://www.fnnews.com/news/202611060800421868" target="_blank" rel="noopener noreferrer">순위 출처 보기 ↗</a></p>
      </header>
      <p v-if="selectedCategory" class="bestseller-source">북적북적 등록 도서 · 누적 판매량 순</p>
      <template v-if="!selectedCategory">
      <div class="bestseller-list" aria-label="교보문고 주간 베스트셀러">
        <article v-for="entry in bestSellerBooks" :key="entry.rank" class="bestseller-item">
          <span class="bestseller-rank">{{ String(entry.rank).padStart(2, '0') }}</span>
          <div class="bestseller-cover"><img :src="entry.book?.cover_image || `https://contents.kyobobook.co.kr/sih/fit-in/200x0/pdt/${entry.isbn}.jpg`" :alt="entry.title + ' 표지'" @error="$event.target.onerror=null; $event.target.src='/assets/covers/category-default.png'" /></div>
          <div class="bestseller-copy"><h2>{{ entry.title }}</h2><p>{{ entry.author }} · {{ entry.publisher }}</p><span v-if="entry.book" class="bestseller-available">북적북적에서 만나보세요</span><span v-else class="bestseller-unavailable">북적북적 미등록 도서</span></div>
          <div class="bestseller-actions"><button v-if="entry.book" type="button" @click="openProduct(entry.book)">책 자세히 보기 →</button><a v-else :href="'https://search.kyobobook.co.kr/search?keyword=' + encodeURIComponent(entry.title)" target="_blank" rel="noopener noreferrer">교보문고에서 찾기 ↗</a></div>
        </article>
      </div>
      <p v-if="!bestSellerBooks.length" class="empty-catalog">교보문고 순위의 검색 결과가 없습니다.</p>
      </template>
      <section v-else class="category-bestsellers" :aria-label="selectedCategory + ' 베스트셀러'">
        <div class="bestseller-list" v-if="visibleStoreBooks.length">
          <article v-for="(book, index) in visibleStoreBooks" :key="book.id" class="bestseller-item">
            <span class="bestseller-rank">{{ String(index + 1).padStart(2, '0') }}</span>
            <div class="bestseller-cover"><img :src="coverUrl(book)" :alt="book.title + ' 표지'" @error="$event.target.onerror=null; $event.target.src='/assets/covers/category-default.png'" loading="lazy" /></div>
            <div class="bestseller-copy"><h2>{{ book.title }}</h2><p>{{ book.author }} · {{ book.publisher }}</p><span class="bestseller-available">북적북적에서 만나보세요</span></div>
            <div class="bestseller-actions"><button type="button" @click="openProduct(book)">책 자세히 보기 →</button></div>
          </article>
        </div>
        <p v-else class="empty-catalog">{{ catalogLoading ? '도서 목록을 불러오고 있습니다.' : '표시할 도서가 없습니다.' }}</p>
        <button v-if="visibleStoreBooks.length < storeBooks.length" type="button" class="store-popular-more" @click="visibleCount += 20">도서 더 보기</button>
      </section>
      </div>
      </div>
    </section>
</template>

<script>
import { computed, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useStorefrontContext } from '../context.js';

export default {
  setup() {
    const context = useStorefrontContext();
    const route = useRoute(), router = useRouter();
    const selectedCategory = computed(() => typeof route.query.category === 'string' ? route.query.category : '');
    function selectCategory(category) { router.push({ name: 'bestsellers', query: category ? { category } : {} }); window.scrollTo({ top: 0, behavior: 'smooth' }); }
    const visibleCount = ref(20);
    const storeBooks = computed(() => {
      const query = context.searchQuery.value.trim().toLowerCase();
      return context.allBooks.value.filter(book => book.isDatabaseBook && context.majorFor(book) === selectedCategory.value && (!query || `${book.title} ${book.author} ${book.publisher}`.toLowerCase().includes(query)))
        .sort((a, b) => b.salesCount - a.salesCount || a.title.localeCompare(b.title, 'ko'));
    });
    const visibleStoreBooks = computed(() => storeBooks.value.slice(0, visibleCount.value));
    watch([context.searchQuery, selectedCategory], () => { visibleCount.value = 20; });
    return { ...context, selectedCategory, selectCategory, storeBooks, visibleStoreBooks, visibleCount };
  }
};
</script>
