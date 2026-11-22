<template>
<section class="cart-page">
      <div class="cart-heading"><button class="cart-back" @click="navigate('home')">← 쇼핑 계속하기</button><h1>장바구니</h1><p>담아 둔 도서를 확인해 주세요.</p></div>
      <div class="cart-layout">
        <div class="cart-items">
          <div v-if="cartBooks.length" class="cart-list"><div class="cart-bulk"><label><input type="checkbox" :checked="selectedCart.size===cartBooks.length" @change="selectedCart=$event.target.checked?new Set(cartBooks.map(book=>book.cartIndex)):new Set()" /> 전체 선택</label><div class="cart-bulk-actions"><button type="button" @click="removeAllCart">전체 삭제</button></div></div>
            <article v-for="book in cartBooks" :key="book.cartKey" class="cart-item">
              <img :src="coverUrl(book)" :alt="book.title + ' 표지'" />
              <div class="cart-item-info"><span>{{ majorFor(book) }}</span><h2>{{ book.title }}</h2><p>{{ book.author }} · {{ book.publisher }}</p></div>
              <input class="cart-select" type="checkbox" :checked="selectedCart.has(book.cartIndex)" @change="toggleCartItem(book.cartIndex)" aria-label="주문 도서 선택" /><div class="quantity-control"><button @click="updateCartQuantity(book.cartIndex,book.quantity-1)" :disabled="book.quantity<=1" aria-label="수량 줄이기">−</button><span>{{ book.quantity }}</span><button @click="updateCartQuantity(book.cartIndex,book.quantity+1)" aria-label="수량 늘리기">＋</button></div><strong>{{ won(book.price * (1 - book.discount / 100) * book.quantity) }}</strong><button type="button" class="cart-remove" @click="removeCart(book.cartIndex)" :aria-label="`${book.title} 삭제`">×</button>
            </article>
          </div>
          <div v-else class="cart-empty"><span>🛒</span><h2>장바구니가 비어 있어요</h2><p>마음에 드는 책을 담아보세요.</p><button @click="navigate('home')">책 둘러보기</button></div>
        </div>
        <aside class="cart-summary"><h2>주문 금액</h2><div><span>선택 상품</span><b>{{ selectedCartBooks.length }}종</b></div><div><span>상품금액</span><b>{{ won(cartSubtotal) }}</b></div><div><span>상품할인 금액</span><b class="cart-discount">− {{ won(cartDiscount) }}</b></div><div class="cart-total"><span>결제예정금액</span><strong>{{ won(cartTotal) }}</strong></div><button :disabled="!selectedCartBooks.length" @click="openPayment">주문서 작성</button></aside>
      </div>
    </section>
</template>

<script>
import { useStorefrontContext } from '../context.js';

export default { setup: useStorefrontContext };
</script>
