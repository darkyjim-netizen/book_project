/* FastAPI 연결 지점. */
(() => {
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
        : detail?.message || payload?.message || responseText;
      const error = new Error(message || `API 요청 실패 (${response.status})`);
      error.status = response.status;
      throw error;
    }
    if (response.status === 204) return null;
    return response.json();
  }

  window.BookstoreApi = Object.freeze({
    baseUrl,
    listBooks: () => request('/api/books'),
    getBook: id => request(`/api/books/${encodeURIComponent(id)}`),
    createBook: book => request('/api/books', { method: 'POST', body: JSON.stringify(book) }),
    updateBook: (id, book) => request(`/api/books/${encodeURIComponent(id)}`, { method: 'PUT', body: JSON.stringify(book) }),
    deleteBook: id => request(`/api/books/${encodeURIComponent(id)}`, { method: 'DELETE' }),
    listCategories: () => request('/api/categories'),
    me: () => request('/auth/me'),
    listProducts: () => request('/api/products?page=1&size=100'),
    getPaymentMode: () => request('/api/payments/mode'),
    createOrder: order => request('/api/orders', { method: 'POST', body: JSON.stringify(order) }),
    getPaymentReady: orderId => request(`/api/payments/toss/${encodeURIComponent(orderId)}/ready`)
  });
})();
