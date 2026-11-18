<template>
<section v-if="productBook" class="product-page">
      <button class="product-back" @click="backToBooks">← 이전 목록</button>
      <div class="product-main">
        <div class="product-cover-panel" :style="{background:productBook.bg}"><img :src="coverUrl(productBook)" :alt="productBook.title + ' 표지'" /></div>
        <div class="product-summary">
          <p class="product-category">{{ majorFor(productBook) }} <span>도서</span></p>
          <h1>{{ productBook.title }}</h1>
          <p class="product-author">{{ productBook.author }} 지음 <span>·</span> {{ productBook.publisher }}</p>
          <div class="product-rating" v-if="productBook.rate">★ {{ productBook.rate }} <span>독자 평점</span></div>
          <div class="product-price-block"><del v-if="productBook.discount">{{ won(productBook.price) }}</del><strong>{{ won(productBook.price*(1-productBook.discount/100)) }}</strong><span v-if="productBook.discount">{{ productBook.discount }}% 할인</span></div>
          <div class="product-actions"><button @click="addCart(productBook.title)">장바구니 담기</button><button class="product-wish" @click="toggleWish(productBook)">{{ wishlist.has(productBook.title) ? '♥ 찜한 책' : '♡ 찜하기' }}</button></div>
          <p class="product-shipping">재고 {{ productBook.stock > 0 ? '있음' : '문의 필요' }} <span>·</span> 주문 후 배송 안내</p>
        </div>
      </div>
      <nav class="product-section-nav" aria-label="도서 상세 메뉴">
        <button type="button" :aria-pressed="productPanel==='intro'" @click="productPanel='intro'">책 소개</button>
        <button type="button" :aria-pressed="productPanel==='contents'" @click="productPanel='contents'">목차</button>
        <button type="button" :aria-pressed="productPanel==='reviews'" @click="productPanel='reviews'">리뷰 <span v-if="reviewCount != null">{{ reviewCount }}</span></button>
      </nav>
      <div v-if="productPanel!=='reviews'" class="product-description-grid">
        <section v-if="productPanel==='intro'" class="product-description product-editorial">
          <h2>줄거리 및 책 소개</h2>
          <p v-if="productDetailStatus==='loading'" role="status">책 소개를 불러오는 중입니다.</p>
          <p v-else-if="productDetailStatus==='error'" role="status">책 소개를 불러오지 못했습니다.</p>
          <template v-else>
            <p v-if="productDetail?.subtitle" class="product-intro-subtitle">{{ productDetail.subtitle }}</p>
            <div v-if="productIntroduction.intro.length" class="product-intro-body">
              <p v-for="(text, index) in productIntroduction.intro" :key="index" class="product-reading-text">{{ text }}</p>
            </div>
            <p v-else class="product-reading-text product-empty-text">{{ !productBook.isDatabaseBook ? detailsFor(productBook).intro : '등록된 책 소개가 없습니다.' }}</p>
            <section v-if="productIntroduction.review" class="product-publisher-review">
              <h3>출판사 서평</h3>
              <p class="product-reading-text">{{ productIntroduction.review }}</p>
            </section>
          </template>
        </section>
        <section v-else class="product-description product-editorial">
          <h2>목차</h2>
          <p v-if="productDetail?.table_of_contents?.trim()" class="product-reading-text product-contents">{{ productDetail.table_of_contents.trim() }}</p>
          <template v-else-if="productDetailStatus==='loading'">
            <p role="status">목차를 불러오는 중입니다.</p>
          </template>
          <template v-else-if="publishedContents">
            <p class="product-empty-text">공개 목차를 바탕으로 정리한 책의 구성입니다.</p>
            <ol class="product-contents-entries">
              <li v-for="([title, page], index) in publishedContents.entries" :key="index">
                <span>{{ title }}</span>
                <span v-if="page">{{ page }}쪽</span>
              </li>
            </ol>
            <a class="product-contents-source" :href="publishedContents.url" target="_blank" rel="noopener noreferrer">출처에서 원문 목차 보기 ↗</a>
          </template>
          <ul v-else-if="!productBook.isDatabaseBook" class="product-contents-list">
            <li v-for="item in detailsFor(productBook).contents" :key="item">{{ item }}</li>
          </ul>
          <template v-else>
            <p class="product-empty-text">{{ productDetailStatus==='error' ? '목차를 불러오지 못했습니다.' : '등록된 목차가 없습니다.' }}</p>
            <a v-if="productBook.isbn13" class="product-contents-source" :href="'https://search.kyobobook.co.kr/search?keyword=' + encodeURIComponent(productBook.isbn13)" target="_blank" rel="noopener noreferrer">ISBN으로 도서 정보 찾아보기 ↗</a>
          </template>
        </section>
        <aside class="product-facts">
          <h2>도서 정보</h2>
          <dl>
            <div><dt>저자</dt><dd>{{ productBook.author }}</dd></div>
            <div><dt>출판사</dt><dd>{{ productBook.publisher }}</dd></div>
            <div><dt>분야</dt><dd>{{ majorFor(productBook) }}</dd></div>
            <div v-if="productBook.published_date"><dt>출간일</dt><dd>{{ productBook.published_date }}</dd></div>
            <div v-if="productBook.isbn13"><dt>ISBN</dt><dd>{{ productBook.isbn13 }}</dd></div>
            <div v-if="productDetail?.page_count"><dt>쪽수</dt><dd>{{ productDetail.page_count }}쪽</dd></div>
            <div v-if="productDetail?.translator"><dt>번역</dt><dd>{{ productDetail.translator }}</dd></div>
            <div v-if="productDetail?.binding"><dt>제본</dt><dd>{{ productDetail.binding }}</dd></div>
            <div v-if="productDetail?.size_mm"><dt>크기</dt><dd>{{ productDetail.size_mm }}</dd></div>
          </dl>
        </aside>
      </div>
      <section v-else class="product-reviews" aria-labelledby="product-reviews-title">
        <h2 id="product-reviews-title">독자 리뷰</h2>
        <div v-if="ratingCount" class="product-review-overview">
          <div class="product-average-rating">
            <span>평균 평점</span>
            <strong>{{ Number(reviewStats.rating_avg).toFixed(1) }} <small>/ 5</small></strong>
            <span>{{ ratingCount }}개의 평가</span>
          </div>
          <ul class="product-rating-breakdown" aria-label="별점별 리뷰 수">
            <li v-for="score in [5, 4, 3, 2, 1]" :key="score">
              <span>{{ score }}점</span>
              <meter :aria-label="score+'점 리뷰 비율'" :value="reviewStats.rating_distribution[score] / ratingCount"></meter>
              <span>{{ reviewStats.rating_distribution[score] }}건</span>
            </li>
          </ul>
        </div>
        <form v-if="productBook.isDatabaseBook" class="product-review-form" @submit.prevent="submitProductReview">
          <h3>리뷰 작성</h3>
          <fieldset :disabled="reviewSubmitting">
            <legend>별점</legend>
            <div class="product-stars">
              <label v-for="score in 5" :key="score" :class="{selected:score<=reviewDraft.rating}">
                <input type="radio" name="product-rating" :value="score" v-model="reviewDraft.rating" :aria-label="score+'점'" required />
                <span aria-hidden="true">★</span>
              </label>
            </div>
          </fieldset>
          <label for="product-review-content">리뷰 내용</label>
          <textarea id="product-review-content" v-model="reviewDraft.content" rows="3" minlength="10" maxlength="5000" placeholder="책을 읽은 소감을 10자 이상 남겨주세요." required></textarea>
          <div class="product-review-submit">
            <small>{{ reviewDraft.content.length }} / 5000자</small>
            <button type="submit" :disabled="reviewSubmitting || reviewsStatus==='loading' || !reviewDraft.rating || reviewDraft.content.trim().length<10">{{ reviewSubmitting ? '등록 중…' : '리뷰 등록' }}</button>
          </div>
          <p v-if="reviewMessage" role="status">{{ reviewMessage }}</p>
        </form>
        <div v-if="productBook.isDatabaseBook" class="product-review-controls">
          <label>별점
            <select v-model="reviewRating" :disabled="reviewsStatus==='loading' || reviewSubmitting" @change="loadProductReviews(productBook, 1)">
              <option value="">전체 별점</option>
              <option v-for="score in [5, 4, 3, 2, 1]" :key="score" :value="score">{{ score }}점</option>
            </select>
          </label>
          <label>정렬
            <select v-model="reviewSort" :disabled="reviewsStatus==='loading' || reviewSubmitting" @change="loadProductReviews(productBook, 1)">
              <option value="recent">최신순</option>
              <option value="rating_desc">높은 별점순</option>
              <option value="rating_asc">낮은 별점순</option>
            </select>
          </label>
        </div>
        <p v-if="reviewsStatus==='loading'" role="status">리뷰를 불러오는 중입니다.</p>
        <p v-else-if="reviewsStatus==='error'" role="status">리뷰를 불러오지 못했습니다. <button type="button" @click="loadProductReviews(productBook, reviewPage)">다시 시도</button></p>
        <p v-else-if="!productReviews?.items.length" class="product-review-empty">{{ reviewRating ? '선택한 별점의 리뷰가 없습니다.' : '등록된 리뷰가 없습니다.' }}</p>
        <div v-else class="product-review-list">
          <article v-for="review in productReviews.items" :key="review.review_id">
            <header><strong>{{ review.member_name }}</strong><time :datetime="review.created_at">{{ review.created_at.slice(0,10) }}</time></header>
            <div class="product-review-rating"><span aria-hidden="true">{{ '★'.repeat(review.rating) }}<span class="product-empty-stars">{{ '★'.repeat(5 - review.rating) }}</span></span> <span>{{ review.rating }} / 5</span></div>
            <h3 v-if="review.title">{{ review.title }}</h3>
            <p class="product-reading-text">{{ review.content }}</p>
          </article>
        </div>
        <nav v-if="!reviewsStatus && productReviews?.meta.total_pages > 1" class="domestic-pagination" aria-label="리뷰 페이지">
          <button type="button" :disabled="reviewPage===1 || reviewsStatus==='loading'" @click="loadProductReviews(productBook, reviewPage-1)">이전</button>
          <span>{{ reviewPage }} / {{ productReviews.meta.total_pages }}</span>
          <button type="button" :disabled="reviewPage>=productReviews.meta.total_pages || reviewsStatus==='loading'" @click="loadProductReviews(productBook, reviewPage+1)">다음</button>
        </nav>
      </section>
    </section>
<section v-else class="product-page"><p role="status">{{ catalogLoading ? '도서 정보를 불러오는 중입니다.' : '도서를 찾을 수 없습니다.' }}</p><button class="product-back" @click="backToBooks">← 이전 목록</button></section>
</template>

<script>
import { useStorefrontContext } from '../context.js';

export default { setup: useStorefrontContext };
</script>
