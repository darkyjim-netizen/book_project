import { inject } from 'vue';

export const storefrontKey = Symbol('storefront');

export function useStorefrontContext() {
  const storefront = inject(storefrontKey);
  if (!storefront) throw new Error('Storefront layout is required.');
  return storefront;
}
