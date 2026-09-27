import { assertEquals } from "https://deno.land/std@0.224.0/assert/mod.ts";
import { magicLinkOrigin, relayAuthorized, timingSafeEqual } from "./email_security.ts";

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
