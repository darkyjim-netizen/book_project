import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/authStore'
const legacyRoutes = new Map([
  ['bestselect', 'bestsellers'], ['domestic', 'domestic'], ['curation', 'curation'],
  ['cart', 'cart'], ['checkout', 'checkout'], ['order-complete', 'orderComplete'],
  ['mypage', 'mypage'], ['admin', 'admin'], ['admin-login', 'adminLogin'],
])

function redirectStorefrontEntry(to) {
  const legacy = to.hash.slice(1)
  const match = /^(category|product|book)=(.+)$/.exec(legacy)
  if (match) {
    const [, type, value] = match
    return type === 'category'
      ? { name: 'category', params: { name: value }, query: to.query, hash: '' }
      : { name: 'productInfo', params: { title: value }, query: to.query, hash: '' }
  }
  return { name: legacyRoutes.get(legacy) ?? 'home', query: to.query, hash: '' }
}

const storefrontRoutes = [
  { path: 'main', name: 'home', component: () => import('../storefront/pages/HomeView.vue') },
  { path: 'domestic', name: 'domestic', component: () => import('../storefront/pages/DomesticView.vue') },
  { path: 'curation', name: 'curation', component: () => import('../storefront/pages/CurationView.vue') },
  { path: 'bestsellers', name: 'bestsellers', component: () => import('../storefront/pages/BestsellersView.vue') },
  { path: 'category/:name', name: 'category', component: () => import('../storefront/pages/CategoryView.vue') },
  { path: 'product/:title', alias: '/book/:title', name: 'productInfo', component: () => import('../storefront/pages/ProductView.vue') },
  { path: 'guest-order', name: 'guestOrder', component: () => import('../storefront/pages/GuestOrderView.vue') },
  { path: 'cart', name: 'cart', component: () => import('../storefront/pages/CartView.vue') },
  { path: 'checkout', name: 'checkout', component: () => import('../storefront/pages/CheckoutView.vue') },
  { path: 'order-complete', name: 'orderComplete', component: () => import('../storefront/pages/OrderCompleteView.vue') },
  { path: 'mypage', name: 'mypage', component: () => import('../storefront/pages/MyPageView.vue'), requiresAuth: true },
  { path: 'support', name: 'support', component: () => import('../storefront/pages/SupportView.vue') },
  { path: 'terms', name: 'terms', component: () => import('../storefront/pages/PolicyView.vue') },
  { path: 'privacy', name: 'privacy', component: () => import('../storefront/pages/PolicyView.vue') },
  { path: 'store-admin', name: 'admin', redirect: { name: 'adminDashboard' } },
  { path: 'store-login', name: 'adminLogin', redirect: { name: 'adminDashboard' } },
  { path: 'store-signup', name: 'adminSignup', redirect: { name: 'adminDashboard' } },
  { path: 'store-admin/dashboard', name: 'adminDashboard', component: () => import('../storefront/pages/StoreDashboardView.vue') },
].map(route => ({ ...route, meta: { storefrontView: route.name, requiresAuth: !!route.requiresAuth } }))

const routes = [
  {
    path: '/',
    component: () => import('../storefront/StorefrontLayout.vue'),
    children: [{ path: '', redirect: redirectStorefrontEntry }, ...storefrontRoutes],
  },
  { path: '/index.html', alias: '/shop.html', redirect: redirectStorefrontEntry },
  { path: '/login', name: 'login', component: () => import('../views/LoginView.vue'), meta: { guestOnly: true } },
  { path: '/register', name: 'register', component: () => import('../views/RegisterView.vue'), meta: { guestOnly: true } },
  { path: '/dashboard', name: 'dashboard', redirect: { name: 'mypage' } },
  { path: '/profile', name: 'profile', redirect: { name: 'mypage' } },
  { path: '/admin/members', name: 'admin-members', component: () => import('../views/AdminMembersView.vue'), meta: { requiresAuth: true, requiresAdmin: true } },
  { path: '/admin/members/:id', name: 'admin-member-detail', component: () => import('../views/AdminMemberDetailView.vue'), props: true, meta: { requiresAuth: true, requiresAdmin: true } },
  { path: '/:pathMatch(.*)*', redirect: { name: 'home' } }
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior(to, _from, savedPosition) {
    if (to.hash === '#home-books-title') return { el: to.hash, top: window.innerWidth <= 700 ? 210 : 156 }
    if (to.hash === '#member-recommendations') return { el: to.hash, top: window.innerWidth <= 700 ? 210 : 156 }
    return savedPosition ?? { top: 0 }
  }
})

router.beforeEach(async to => {
  // Public entry paths must not load a session or fall through to the dashboard.
  if (!to.meta.requiresAuth && !to.meta.guestOnly) return

  const auth = useAuthStore()
  if (!auth.initialized) await auth.fetchMe()

  if (to.meta.requiresAuth && !auth.isAuthenticated) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.name === 'mypage' && auth.isAdmin) {
    return { name: 'adminDashboard' }
  }
  if (to.meta.requiresAdmin && !auth.isAdmin) {
    return { name: 'dashboard' }
  }
  if (to.meta.guestOnly && auth.isAuthenticated) {
    return { name: 'dashboard' }
  }
})

export default router
