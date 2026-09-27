-- Apply only after request-magic-link is deployed and the website has moved
-- off direct RPC calls. A public caller must never receive the raw token.
revoke execute on function public.issue_magic_link(text, uuid) from public;
revoke execute on function public.issue_magic_link(text, uuid) from anon;
revoke execute on function public.issue_magic_link(text, uuid) from authenticated;
grant execute on function public.issue_magic_link(text, uuid) to service_role;
