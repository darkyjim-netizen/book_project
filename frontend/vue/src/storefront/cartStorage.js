// Guest carts live only in this page session. Member carts are isolated by account.
export function createCartStorage(storage) {
  let guestItems = []
  const key = memberId => `bookjjeok-cart:member:${memberId}`
  storage.removeItem('bookjjeok-cart') // Discard the old shared, ownerless cart.
  return {
    load(memberId) {
      if (memberId == null) return guestItems.map(item => ({ ...item }))
      try {
        const items = JSON.parse(storage.getItem(key(memberId)) || '[]')
        return Array.isArray(items) ? items.filter(item => item && typeof item.title === 'string' && Number.isInteger(item.quantity) && item.quantity > 0) : []
      } catch { return [] }
    },
    save(memberId, items) {
      if (memberId == null) guestItems = items.map(item => ({ ...item }))
      else storage.setItem(key(memberId), JSON.stringify(items))
    },
    resetGuest() { guestItems = [] }
  }
}

let pageStorage
export function getCartStorage() {
  return pageStorage ||= createCartStorage(localStorage)
}
