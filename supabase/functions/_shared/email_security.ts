export const SITE_ORIGINS = new Set([
  "https://kidsnews.21mins.com",
  "https://news.6ray.com",
]);

export function magicLinkOrigin(requestOrigin: string | null, fallback: string): string {
  return requestOrigin && SITE_ORIGINS.has(requestOrigin) ? requestOrigin : fallback;
}

export function timingSafeEqual(a: string, b: string): boolean {
  if (!a || a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

export function relayAuthorized(internalHeader: string, bearer: string,
                                internalSecret: string, serviceRoleKey: string): boolean {
  return timingSafeEqual(internalHeader, internalSecret) || timingSafeEqual(bearer, serviceRoleKey);
}

export async function validServiceBearer(
  bearer: string, supabaseUrl: string, fetcher: typeof fetch = fetch,
): Promise<boolean> {
  if (!bearer || !supabaseUrl) return false;
  try {
    const response = await fetcher(`${supabaseUrl}/auth/v1/admin/users?per_page=1`, {
      headers: { apikey: bearer, Authorization: `Bearer ${bearer}` },
      signal: AbortSignal.timeout(3000),
    });
    return response.status === 200;
  } catch {
    return false;
  }
}
