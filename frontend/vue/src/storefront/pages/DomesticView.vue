<template>
<section id="domestic-view">
      <div class="domestic-catalog-layout">
      <aside class="domestic-category-nav" aria-label="국내도서 분야">
        <h2>국내도서</h2>
        <div class="domestic-category-group"><button type="button" class="domestic-bestsellers" @click="openBestSellers">베스트셀러</button></div>
        <div class="domestic-category-group domestic-subjects"><h3>분야별 도서</h3>
        <button v-for="category in domesticCategories" :key="category.name" type="button"
          :aria-current="activeDomesticCategory === category.name ? 'page' : undefined"
          @click="selectHeaderCategory(category.name)">{{ category.name }}</button>
        </div>
      </aside>
      <section class="domestic-shelf" aria-labelledby="domestic-results-title">
        <header class="domestic-shelf-head">
          <h1 id="domestic-results-title">{{ activeDomesticCategory || '도서 목록' }}</h1>
          <div v-if="activeDomesticCategory" class="domestic-shelf-sort" role="group" aria-label="국내도서 정렬">
            <button v-for="option in domesticSortOptions" :key="option.value" type="button"
              :aria-pressed="domesticSort === option.value" @click="domesticSortByCategory.set(activeDomesticCategory, option.value)">
              {{ option.label }}
            </button>
          </div>
        </header>
        <div v-if="domesticBooks.length" class="book-grid catalog-grid">
          <book-card v-for="book in pagedBooks" :key="book.id" :book="book" :wished="wishlist.has(String(book.id))" @wish="toggleWish" @buy="addCart" @detail="openProduct"></book-card>
        </div>
        <p v-else class="empty-catalog">해당 분야의 검색 결과가 없습니다.</p>
        <nav v-if="totalPages > 1" class="domestic-pagination" aria-label="국내도서 페이지">
          <button type="button" :disabled="page === 1" @click="goToPage(page - 1)">이전</button>
          <button v-for="number in visiblePages" :key="number" type="button"
            :aria-current="page === number ? 'page' : undefined" @click="goToPage(number)">{{ number }}</button>
          <button type="button" :disabled="page === totalPages" @click="goToPage(page + 1)">다음</button>
        </nav>
      </section>
      </div>
    </section>
</template>

<script>
import { computed, ref, watch } from 'vue';
import { useStorefrontContext } from '../context.js';
import BookCard from '../BookCard.vue';

export default {
  components: { BookCard },
  setup() {
    const context = useStorefrontContext();
    const page = ref(1);
    const pageSize = 20;
    const totalPages = computed(() => Math.max(1, Math.ceil(context.domesticBooks.value.length / pageSize)));
    const pagedBooks = computed(() => context.domesticBooks.value.slice((page.value - 1) * pageSize, page.value * pageSize));
    const visiblePages = computed(() => {
      const start = Math.max(1, Math.min(page.value - 2, totalPages.value - 4));
      return Array.from({ length: Math.min(5, totalPages.value) }, (_, index) => start + index);
    });
    watch([context.activeDomesticCategory, context.domesticSort, context.searchQuery], () => { page.value = 1; });
    watch(totalPages, total => { if (page.value > total) page.value = total; });
    function goToPage(number) {
      page.value = number;
      document.getElementById('domestic-results-title')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
    return { ...context, page, totalPages, pagedBooks, visiblePages, goToPage };
  },
};
</script>
