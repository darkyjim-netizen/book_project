<template>
<p v-if="toastMessage" class="toast show" role="status">{{ toastMessage }}</p>
<div v-if="cartDeleteComplete" class="cart-added-backdrop" @click.self="closeCartDeleteComplete()" @keydown.esc.stop="closeCartDeleteComplete()" @keydown.tab="trapCartDialogFocus">
    <section ref="cartDialog" class="cart-added-dialog" role="dialog" aria-modal="true" aria-labelledby="cart-deleted-title" aria-describedby="cart-deleted-description">
      <span class="cart-added-icon cart-deleted-icon" aria-hidden="true">×</span>
      <h2 id="cart-deleted-title">삭제되었습니다</h2>
      <p id="cart-deleted-description">장바구니에서 상품을 삭제했어요.</p>
      <div class="cart-added-actions"><button type="button" class="cart-added-go" @click="closeCartDeleteComplete()">확인</button></div>
    </section>
  </div>
<div v-if="cartDeleteTargets" class="cart-added-backdrop" @click.self="closeCartDelete()" @keydown.esc.stop="closeCartDelete()" @keydown.tab="trapCartDialogFocus">
    <section ref="cartDialog" class="cart-added-dialog" role="dialog" aria-modal="true" aria-labelledby="cart-delete-title" aria-describedby="cart-delete-description">
      <button class="cart-added-close" type="button" aria-label="닫기" @click="closeCartDelete()">×</button>
      <h2 id="cart-delete-title">{{ cartDeleteMode === 'all' ? '전체 상품을 삭제하시겠습니까?' : cartDeleteMode === 'single' ? '상품을 삭제하시겠습니까?' : '선택한 상품을 삭제하시겠습니까?' }}</h2>
      <p id="cart-delete-description">{{ cartDeleteMode === 'all' ? '장바구니의 모든 상품' : cartDeleteMode === 'single' ? '해당 상품' : '선택한 ' + cartDeleteTargets.length + '개 상품' }}을 장바구니에서 삭제합니다.</p>
      <div class="cart-added-actions"><button type="button" class="cart-added-continue" @click="closeCartDelete()">취소</button><button type="button" class="cart-added-go" @click="confirmCartDelete()">삭제하기</button></div>
    </section>
  </div>
<div v-if="addedCartTitle" class="cart-added-backdrop" @click.self="closeCartDialog()" @keydown.esc.stop="closeCartDialog()" @keydown.tab="trapCartDialogFocus">
    <section ref="cartDialog" class="cart-added-dialog" role="dialog" aria-modal="true" aria-labelledby="cart-added-title">
      <button class="cart-added-close" type="button" aria-label="닫기" @click="closeCartDialog()">×</button>
      <span class="cart-added-icon cart-success-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none"><path d="M4 5h2l1.5 9h9.8l1.7-6.5H7"/><path d="M9 18.5h.01M16 18.5h.01"/><path d="m10 10.5 1.5 1.5 3-3"/></svg></span>
      <h2 id="cart-added-title">장바구니에 담겼습니다</h2>
      <div class="cart-added-actions"><button type="button" class="cart-added-continue" @click="closeCartDialog()">쇼핑 계속하기</button><button type="button" class="cart-added-go" @click="closeCartDialog(true)">장바구니로 이동</button></div>
    </section>
  </div>
<div v-if="showBookForm" class="modal-backdrop" @click.self="showBookForm=false"><form class="modal" @submit.prevent="createBook"><div class="modal-top"><h2>{{ editingBookId ? '도서 수정' : '새 도서 등록' }}</h2><button type="button" class="close" @click="showBookForm=false">×</button></div><div class="field"><label>도서명 *</label><input v-model.trim="bookForm.title" required placeholder="도서명" /></div><div class="field"><label>저자 *</label><input v-model.trim="bookForm.author" required placeholder="저자 이름" /></div><div class="field"><label>분야</label><select v-model="bookForm.major" @change="bookForm.subcategory=formSubcategories[0]"><option v-for="group in categoryGroups" :key="group.name">{{ group.name }}</option></select></div><div class="field"><label>세부 분야</label><select v-model="bookForm.subcategory"><option v-for="sub in formSubcategories" :key="sub">{{ sub }}</option></select></div><div class="field"><label>판매가 *</label><input v-model.number="bookForm.price" type="number" min="0" required placeholder="18000" /></div><div class="field"><label>재고 수량</label><input v-model.number="bookForm.stock" type="number" min="0" /></div><div class="field"><label>출판사</label><input v-model.trim="bookForm.publisher" placeholder="출판사명" /></div><div class="modal-foot"><button type="button" class="secondary" @click="showBookForm=false">취소</button><button class="primary" type="submit">{{ editingBookId ? '수정 완료' : '도서 등록' }}</button></div></form></div>
</template>

<script>
import { useStorefrontContext } from './context.js';
export default { setup: useStorefrontContext };
</script>
