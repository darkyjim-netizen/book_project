/* FastAPI 연결 지점. */

const baseUrl = window.BOOKSTORE_API_BASE_URL || '';

async function request(path, options = {}) {
  const { headers, ...requestOptions } = options;
  const response = await fetch(`${baseUrl}${path}`, {
    ...requestOptions,
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...headers }
  });
  if (!response.ok) {
    const responseText = await response.text();
    let payload;
    try { payload = JSON.parse(responseText); } catch { payload = null; }
    const detail = payload?.detail;
    const message = typeof detail === 'string'
      ? detail
      : detail?.message || payload?.error?.message || payload?.message || responseText;
    const error = new Error(message || 'API 요청에 실패했습니다.');
    error.status = response.status;
    throw error;
  }
  if (response.status === 204) return null;
  return response.json();
}

async function listBooks(sort = 'sales') {
  const query = new URLSearchParams({ is_domestic: 'true', sort, page: '1', size: '100' });
  const firstPage = await request(`/api/v1/books?${query}`);
  const totalPages = firstPage.meta?.total_pages || 1;
  const laterPages = await Promise.all(
    Array.from({ length: totalPages - 1 }, (_, index) =>
      request(`/api/v1/books?${new URLSearchParams({ is_domestic: 'true', sort, page: String(index + 2), size: '100' })}`)
    )
  );

  return {
    ...firstPage,
    items: [firstPage, ...laterPages].flatMap(page => page.items || [])
  };
}

export const storefrontApi = Object.freeze({
  baseUrl,
  wishlist: (page = 1) => request(`/api/v1/wishlist?${new URLSearchParams({ page, size: 100 })}`),
  toggleWishlist: id => request(`/api/v1/wishlist/${encodeURIComponent(id)}`, { method: 'POST' }),
  adminOverview: () => request('/api/v1/admin/dashboard/overview'),
  adminLogin: (email, password) => request('/api/v1/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }),
  adminLogout: () => request('/api/v1/auth/logout', { method: 'POST' }),
  adminBooks: (page = 1, keyword = '') => request(`/api/v1/admin/books?${new URLSearchParams({ page, size: 20, keyword })}`),
  saveAdminBook: (id, data) => request(id ? `/api/v1/admin/books/${id}` : '/api/v1/admin/books', { method: id ? 'PUT' : 'POST', body: JSON.stringify(data) }),
  deleteAdminBook: id => request(`/api/v1/admin/books/${id}`, { method: 'DELETE' }),
  adminMembers: (page = 1, keyword = '') => request(`/api/v1/admin/members?${new URLSearchParams({ page, size: 20, keyword })}`),
  adminMember: id => request(`/api/v1/admin/members/${id}`),
  setMemberStatus: (id, status) => request(`/api/v1/admin/members/${id}/status`, { method: 'PUT', body: JSON.stringify({ status }) }),
  searchAddresses: (keyword, page) => request(`/api/v1/postal/search?${new URLSearchParams({ keyword, page })}`),
  listBooks,
  lookupGuestOrder: (order_no, email) => request('/api/v1/orders/lookup', { method: 'POST', body: JSON.stringify({ order_no, email }) }),
  getBook: id => request(`/api/v1/books/${encodeURIComponent(id)}`),
  listBookReviews: (id, page = 1, sort = 'recent', rating = '') => {
    const query = new URLSearchParams({ page, size: 6, sort });
    if (rating) query.set('rating', rating);
    return request(`/api/v1/books/${encodeURIComponent(id)}/reviews?${query}`);
  },
  getBookReviewStats: id => request(`/api/v1/books/${encodeURIComponent(id)}/review-stats`),
  createReview: review => request('/api/v1/reviews', { method: 'POST', body: JSON.stringify(review) }),
  listCategories: () => request('/api/v1/books/categories'),
  me: () => request('/api/v1/auth/me'),
  listProducts: async () => {
    const result = await listBooks();
    return {
      ...result,
      items: result.items.map(book => ({
        ...book,
        id: book.book_id,
        price: book.sale_price
      }))
    };
  },
  getPaymentMode: () => request('/api/v1/orders/payment-mode'),
  createOrder: order => request('/api/v1/orders', { method: 'POST', body: JSON.stringify(order) }),
  // 비회원 주문은 주문 생성 응답의 guest_order_token을 X-Guest-Order-Token 헤더로 보내야 한다.
  getPaymentReady: (orderId, guestToken) => request(`/api/v1/orders/${encodeURIComponent(orderId)}/payment-ready`, {
    headers: guestToken ? { 'X-Guest-Order-Token': guestToken } : {}
  }),
  payOrder: (orderId, body = {}, guestToken) => request(`/api/v1/orders/${encodeURIComponent(orderId)}/pay`, {
    method: 'POST', body: JSON.stringify(body), headers: guestToken ? { 'X-Guest-Order-Token': guestToken } : {}
  })
});
