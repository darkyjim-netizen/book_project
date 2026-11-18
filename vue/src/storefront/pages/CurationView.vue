<template>
<section id="curation-view"><div class="curation-welcome"><div><div class="eyebrow">북적북적의 추천 책장</div><h1>처음 읽기 좋은 책</h1><p>무엇을 읽을지 망설여질 때, 편하게 시작할 수 있는 책부터 골라봤어요.</p></div></div><div class="curation-guides"><article><span>1</span><b>관심 있는 책을 골라보세요</b><small>책 소개와 추천 이유를 함께 담았어요</small></article><article><span>2</span><b>책 제목을 눌러 자세히 읽어보세요</b><small>저자와 출판 정보도 확인할 수 있어요</small></article><article><span>3</span><b>마음에 들면 장바구니에 담으세요</b><small>상세 화면에서 바로 담을 수 있어요</small></article></div><div class="section-head curation-section-head"><div><h2>추천 도서</h2><p>한 권씩 살펴보고 지금 읽고 싶은 책을 골라보세요.</p></div><span class="catalog-count">{{ curatedBooks.length }}권 추천</span></div><div class="book-grid curation-grid"><article v-for="(book,index) in curatedBooks" :key="book.title" class="curation-book" role="button" tabindex="0" @click="openBookInfo(book)" @keydown.enter="openBookInfo(book)" @keydown.space.prevent="openBookInfo(book)"><div class="curation-cover" :style="{background:book.bg}"><span>{{ String(index+1).padStart(2,'0') }}</span><img :src="coverUrl(book)" :alt="`${book.title} 표지`" loading="lazy" /></div><div class="curation-copy"><span class="category">{{ majorFor(book) }} · 입문 추천</span><h3>{{ book.title }}</h3><p class="author">{{ book.author }} · {{ book.publisher }}</p><p class="curation-reason">{{ curationNotes[book.title] || '판매 순위와 도서 정보를 바탕으로 선정한 추천 도서입니다.' }}</p><span class="curation-more">자세히 보기 →</span></div></article></div></section>
</template>

<script>
import { useStorefrontContext } from '../context.js';

export default { setup: useStorefrontContext };
</script>
