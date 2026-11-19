<template>
    <article class="book-card" role="link" tabindex="0" @click="$emit('detail',book)" @keydown.enter.self="$emit('detail',book)" @keydown.space.prevent.self="$emit('detail',book)">
      <div class="book-art" :style="{background:book.bg}">
        <span v-if="rank != null" class="rank">{{ String(rank).padStart(2,'0') }}</span>
        <button v-if="auth.initialized && !auth.isAdmin" class="wish" :class="{on:wished}" @click.stop="$emit('wish',book)" :aria-label="wished?'찜 해제':'찜하기'">{{ wished?'♥':'♡' }}</button>
        <img v-if="bookCoverUrl(book)" class="book-cover-img" :src="bookCoverUrl(book)" :alt="book.isDatabaseBook && !book.cover_image ? '도서 분야 안내 이미지' : book.title + ' 표지'" @error="$event.target.onerror=null; $event.target.src='/assets/covers/category-default.png'; $event.target.alt='도서 분야 안내 이미지'" loading="lazy" />
        <span v-if="book.isDatabaseBook && !book.cover_image" class="cover-category-label">{{ book.major || book.cat }}</span>
        <div v-if="!bookCoverUrl(book)" class="book-cover" :style="{background:book.color}"><strong>{{ book.title }}</strong><small>{{ book.author }} 지음</small></div>
      </div>
      <div class="book-meta"><div class="category">{{ book.major||book.cat }}</div><h3>{{ book.title }}</h3><div class="author">{{ book.author }} · {{ book.publisher }}</div>
        <div class="price-line"><span class="discount">{{ book.discount?book.discount+'%':'' }}</span><span class="price">{{ Number(book.price*(1-book.discount/100)).toLocaleString('ko-KR') }}원</span></div>
        <div v-if="book.rate" class="rating">★ {{ book.rate }}<span>독자 평점</span></div><div v-else class="rating new-book-label">새로 추가된 책</div><div class="buy-row"><button @click.stop="$emit('detail',book)">상세</button><button @click.stop="$emit('buy',book)">담기</button></div>
      </div>
    </article>
</template>

<script setup>
import { bookCoverUrl } from './useStorefront.js';
import { useAuthStore } from '../stores/authStore.js';
const auth = useAuthStore();
defineProps({ book: { type: Object, required: true }, rank: Number, wished: Boolean });
defineEmits(['wish', 'buy', 'detail']);
</script>
