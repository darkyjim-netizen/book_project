<template>
<section id="category-view">
      <div class="catalog-head"><h1>{{ selectedMajor }}</h1><p>{{ selectedMajor }} 분야의 책을 살펴보세요.</p></div>
      <div v-if="availableSubcategories.length" class="subcategory-bar"><button class="subcategory-chip" :class="{active:!selectedSub}" @click="selectedSub=''">전체</button><button v-for="sub in availableSubcategories" :key="sub" class="subcategory-chip" :class="{active:selectedSub===sub}" @click="selectedSub=sub">{{ sub }}</button></div>
      <div class="section-head catalog-section-head"><h2 v-if="selectedSub">{{ selectedSub }}</h2><span class="catalog-count">{{ categoryBooks.length }}권</span><label class="book-sort"><span>정렬</span><select v-model="categorySort" aria-label="도서 정렬"><option value="default">기본순</option><option value="newest">최신 출간순</option><option value="price-low">낮은 가격순</option><option value="price-high">높은 가격순</option></select></label></div>
      <div class="book-grid catalog-grid"><book-card v-for="book in categoryBooks" :key="book.id" :book="book" :wished="wishlist.has(String(book.id))" @wish="toggleWish" @buy="addCart" @detail="openProduct"></book-card></div>
      <div v-if="!categoryBooks.length" class="category-empty"><strong>{{ selectedSub||selectedMajor }} 도서를 준비하고 있어요.</strong><p>다른 세부 분야를 선택하거나 검색어를 바꿔보세요.</p></div>
    </section>
</template>

<script>
import { useStorefrontContext } from '../context.js';
import BookCard from '../BookCard.vue';

export default { components: { BookCard }, setup: useStorefrontContext };
</script>
