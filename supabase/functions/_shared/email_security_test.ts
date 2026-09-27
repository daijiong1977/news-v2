import { assertEquals } from "https://deno.land/std@0.224.0/assert/mod.ts";
import { magicLinkOrigin, relayAuthorized, timingSafeEqual, validServiceBearer } from "./email_security.ts";

Deno.test("magic link may return only to a production origin", () => {
  const fallback = "https://kidsnews.21mins.com";
  assertEquals(magicLinkOrigin("https://news.6ray.com", fallback), "https://news.6ray.com");
  assertEquals(magicLinkOrigin("https://evil.example", fallback), fallback);
  assertEquals(magicLinkOrigin("https://news.6ray.com.evil.example", fallback), fallback);
  assertEquals(magicLinkOrigin(null, fallback), fallback);
});

Deno.test("internal relay accepts only the configured nonempty secret", () => {
  assertEquals(timingSafeEqual("abc123", "abc123"), true);
  assertEquals(timingSafeEqual("abc123", "abc124"), false);
  assertEquals(timingSafeEqual("abc", "abc123"), false);
  assertEquals(timingSafeEqual("", ""), false);
});

Deno.test("relay supports server-to-server bearer but rejects anonymous callers", () => {
  assertEquals(relayAuthorized("internal", "", "internal", "service"), true);
  assertEquals(relayAuthorized("", "service", "internal", "service"), true);
  assertEquals(relayAuthorized("", "anon-key", "internal", "service"), false);
  assertEquals(relayAuthorized("", "", "internal", "service"), false);
});

Deno.test("other valid service-role bearer is checked against Auth admin", async () => {
  const fetcher = ((_url: string, init: RequestInit) => {
    assertEquals(new Headers(init.headers).get("Authorization"), "Bearer older-key");
    return Promise.resolve({ status: 200 } as Response);
  }) as typeof fetch;
  assertEquals(await validServiceBearer("older-key", "https://project.supabase.co", fetcher), true);
  assertEquals(await validServiceBearer("", "https://project.supabase.co", fetcher), false);
  assertEquals(await validServiceBearer("anon", "https://project.supabase.co",
    ((_url: string, _init: RequestInit) => Promise.resolve({ status: 401 } as Response)) as typeof fetch), false);
});
