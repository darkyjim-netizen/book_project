/*
 * FastAPI 연결 지점.
 * [백엔드 연동 수정] 원래는 /api/books, /api/orders 같은 옛 경로를 불렀지만, 새 백엔드는 모두 /api/v1 아래에 있고
 * 응답 모양도 달라서, 이 파일에서 백엔드 응답을 쇼핑몰 화면(shop.js)이 쓰던 모양으로 바꿔 줍니다.
 * - 도서: book_id → id, authors(배열) → author, sale_price → price
 * - 내 정보: name 을 display_name 으로도 내려 줌(shop.js 가 display_name 을 읽음)
 * - 주문: POST /orders 후 POST /orders/{id}/pay (백엔드가 모의 결제 모드면 바로 승인)
 * 알려진 한계: 쇼핑몰 화면의 책 목록은 아직 코드 안의 예시 데이터라 DB와 제목이 같은 3권만 주문됩니다.
 */
(() => {
  const baseUrl = window.BOOKSTORE_API_BASE_URL || '/api/v1';

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
      // 백엔드 오류 형식: { success: false, error: { code, message, detail } }
      const message = payload?.error?.message
        || (typeof payload?.detail === 'string' ? payload.detail : '')
        || responseText;
      const error = new Error(message || `API 요청 실패 (${response.status})`);
      error.status = response.status;
      throw error;
    }
    if (response.status === 204) return null;
    return response.json();
  }

  // 백엔드 도서 -> 화면용 도서
  const toProduct = book => ({
    id: book.book_id,
    title: book.title,
    author: (book.authors || []).join(', '),
    publisher: book.publisher,
    price: Number(book.sale_price ?? book.list_price ?? 0),
    list_price: Number(book.list_price ?? 0),
    discount: Number(book.discount_rate ?? 0),
    stock: book.stock_qty,
    cover: book.cover_image,
    category: book.category_name
  });

  // 한 번에 최대 100권까지만 받을 수 있어서, 전체 페이지를 모아서 돌려준다.
  async function listProducts() {
    const first = await request('/books?page=1&size=100');
    const pages = first.meta?.total_pages || 1;
    const rest = await Promise.all(
      Array.from({ length: pages - 1 }, (_, i) => request(`/books?page=${i + 2}&size=100`))
    );
    const items = [first, ...rest].flatMap(page => page.items || []);
    return { ...first, items: items.map(toProduct) };
  }

  const unsupported = name => async () => {
    throw new Error(`${name}은(는) 아직 새 백엔드(/api/v1)와 연결되지 않았습니다.`);
  };

  // 주문 생성(POST /orders) 후 결제 요청(POST /orders/{id}/pay)까지 한 번에 처리한다.
  // 백엔드가 모의 결제(PG_MOCK_MODE)이면 결제가 바로 승인된다.
  async function createOrder(order) {
    const member = await request('/auth/me');
    const created = await request('/orders', {
      method: 'POST',
      body: JSON.stringify({
        items: (order.items || []).map(item => ({ book_id: item.product_id, quantity: item.quantity })),
        orderer_name: member.name,
        orderer_phone: member.phone || order.receiver_phone,
        orderer_email: member.email,
        receiver: order.receiver_name,
        receiver_phone: order.receiver_phone,
        zipcode: order.postal_code,
        address1: order.address,
        payment_method: 'CARD'
      })
    });
    const payment = await request(`/orders/${created.order_id}/pay`, {
      method: 'POST',
      body: JSON.stringify({})
    });
    // shop.js 가 읽는 이름(id, order_number, total)으로 맞춰서 돌려준다.
    return {
      id: created.order_id,
      order_number: created.order_no,
      total: created.total_amount,
      status: payment.status,
      payment
    };
  }

  window.BookstoreApi = Object.freeze({
    baseUrl,
    listBooks: listProducts,
    getBook: async id => toProduct(await request(`/books/${encodeURIComponent(id)}`)),
    listCategories: () => request('/books/categories'),
    // 쇼핑몰 화면은 display_name 을 읽으므로 name 을 같이 넣어 준다.
    me: async () => {
      const member = await request('/auth/me');
      return { ...member, display_name: member.name, username: member.email };
    },
    listProducts,
    getPaymentMode: async () => ({ mode: 'mock' }),
    // 관리자 도서 등록·수정·삭제와 토스 결제창은 아직 연결하지 않았다(모의 결제만 사용).
    createBook: unsupported('도서 등록'),
    updateBook: unsupported('도서 수정'),
    deleteBook: unsupported('도서 삭제'),
    createOrder,
    getPaymentReady: unsupported('결제 준비')
  });
})();