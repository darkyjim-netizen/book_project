<template>
<section class="account-page receipt-page"><div class="receipt-card"><span class="receipt-check">✓</span><p class="eyebrow">주문 완료</p><h1>주문이 완료되었습니다</h1><p>주문과 결제가 완료되었습니다. 주문 내역을 확인해 주세요.</p><div v-if="lastOrder" class="receipt-details"><div><span>주문 번호</span><b>{{ lastOrder.id }}</b></div><div><span>주문 상태</span><b>{{ lastOrder.status }}</b></div><div><span>주문 상품</span><b>{{ lastOrder.books.length }}종 · {{ lastOrder.books.reduce((sum,book)=>sum+book.quantity,0) }}권</b></div><div><span>결제 금액</span><b>{{ won(lastOrder.total) }}</b></div><div><span>받는 분 · 연락처</span><b>{{ lastOrder.profile.name }} · {{ lastOrder.profile.phone }}</b></div><div><span>우편번호</span><b>{{ lastOrder.profile.postalCode }}</b></div><div><span>주소</span><b>{{ [lastOrder.profile.address, lastOrder.profile.addressDetail].filter(Boolean).join(' ') }}</b></div></div><div v-if="lastOrder" class="receipt-books"><article v-for="book in lastOrder.books" :key="book.cartKey"><img :src="coverUrl(book)" :alt="book.title" /><span><b>{{ book.title }}</b><small>{{ book.author }} · {{ book.quantity }}권</small></span><strong>{{ won(book.price*book.quantity) }}</strong></article></div><div class="receipt-actions"><button @click="navigate('mypage')">주문 내역 보기</button><button class="secondary" @click="navigate('home')">쇼핑 계속하기</button></div></div></section>
</template>

<script>
import { useStorefrontContext } from '../context.js';

export default { setup: useStorefrontContext };
</script>
