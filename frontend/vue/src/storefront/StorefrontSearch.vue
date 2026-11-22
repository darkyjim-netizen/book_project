<template>
  <div ref="searchArea" class="storefront-search" @keydown.esc.stop="closeAndFocus" @focusout="closeWhenLeaving">
    <form class="search" role="search" @submit.prevent="search(searchQuery)">
      <input ref="searchInput" v-model="searchQuery" type="search"
        placeholder="책 제목, 저자, 키워드로 검색" aria-label="책 제목, 저자, 키워드로 검색"
        aria-controls="store-search-panel" autocomplete="off"
        @focus="open = true" @click="open = true" />
      <button v-if="searchQuery" class="store-search-clear" type="button" aria-label="검색어 지우기" @click="clearQuery">×</button>
      <button class="store-search-submit" type="submit" aria-label="도서 검색"><span aria-hidden="true"></span></button>
    </form>
    <section v-if="open" id="store-search-panel" class="store-search-panel" aria-label="검색 안내">
      <div class="store-search-columns">
        <section>
          <header>
            <h2>최근 검색어</h2>
            <button v-if="history.length" type="button" class="search-panel-action" @click="saveHistory([])">전체 삭제</button>
          </header>
          <ul v-if="history.length" class="store-search-history">
            <li v-for="term in history" :key="term">
              <button type="button" class="search-panel-term" @click="search(term)">{{ term }}</button>
              <button type="button" class="search-panel-action" :aria-label="term + ' 검색 기록 지우기'" @click="saveHistory(history.filter(item => item !== term))">×</button>
            </li>
          </ul>
          <p v-else class="store-search-empty">최근 검색어가 없습니다.</p>
        </section>
        <section>
          <header><h2><RouterLink to="/bestsellers">지금 베스트 <span aria-hidden="true">›</span></RouterLink></h2></header>
          <ol class="store-search-best">
            <li v-for="(book, index) in bestBooks" :key="book.id">
              <button type="button" @click="showBook(book)">
                <img v-if="coverUrl(book)" :src="coverUrl(book)" alt="" />
                <strong>{{ index + 1 }}</strong>
                <span :title="book.title">{{ book.title }}</span>
              </button>
            </li>
          </ol>
        </section>
      </div>
      <section v-if="keywords.length" class="store-search-keywords">
        <h2>추천 키워드</h2>
        <div>
          <button v-for="keyword in keywords" :key="keyword" type="button" @click="search(keyword)">{{ keyword }}</button>
        </div>
      </section>
      <footer><button type="button" class="search-panel-action" @click="closeAndFocus">닫기 ×</button></footer>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import { useRoute } from 'vue-router';
import { useStorefrontContext } from './context.js';

const { searchQuery, showBookSearchResults, allBooks, domesticCategories, coverUrl, openProduct } = useStorefrontContext();
const route = useRoute();
const open = ref(false);
const searchArea = ref(null);
const searchInput = ref(null);
const history = ref([]);
const storageKey = 'bookjjeok-recent-searches';
const bestBooks = computed(() => [...allBooks.value]
  .sort((a, b) => (b.salesCount ?? 0) - (a.salesCount ?? 0)).slice(0, 5));
const keywords = computed(() => domesticCategories.value.slice(0, 8).map(category => category.name));

function saveHistory(entries) {
  history.value = entries;
  try { localStorage.setItem(storageKey, JSON.stringify(entries)); } catch { /* Search remains available. */ }
}
function search(value) {
  const term = value.trim();
  if (!term) return;
  saveHistory([term, ...history.value.filter(item => item !== term)].slice(0, 8));
  searchQuery.value = term;
  open.value = false;
  showBookSearchResults();
}
function showBook(book) {
  open.value = false;
  openProduct(book);
}
function clearQuery() {
  searchQuery.value = '';
  searchInput.value?.focus();
  open.value = true;
}
function closeAndFocus() {
  if (!open.value) return;
  searchInput.value?.focus();
  open.value = false;
}
function closeWhenLeaving(event) {
  if (event.relatedTarget && !searchArea.value?.contains(event.relatedTarget)) open.value = false;
}
function closeFromOutside(event) {
  if (!searchArea.value?.contains(event.target)) open.value = false;
}

watch(() => route.fullPath, () => { open.value = false; });
onMounted(() => {
  try {
    const entries = JSON.parse(localStorage.getItem(storageKey) || '[]');
    if (Array.isArray(entries)) history.value = entries.filter(item => typeof item === 'string').slice(0, 8);
  } catch { /* An invalid or unavailable history starts empty. */ }
  document.addEventListener('pointerdown', closeFromOutside);
});
onUnmounted(() => document.removeEventListener('pointerdown', closeFromOutside));
</script>
