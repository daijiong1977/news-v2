-- Add title + image_url to redesign_reading_events so the cross-device
-- "Recently read" popover on Device B can render entries that were read
-- on Device A (without these columns, the cloud-rebuilt readHistory
-- entries had IDs but no rendering metadata, and the popover silently
-- dropped them).
--
-- See docs/bugs/2026-05-03-recently-read-no-cross-device-sync.md.

ALTER TABLE redesign_reading_events
  ADD COLUMN IF NOT EXISTS title     TEXT,
  ADD COLUMN IF NOT EXISTS image_url TEXT;

-- Both RPCs change return type / signature; Postgres requires DROP +
-- CREATE rather than CREATE OR REPLACE when the OUT-parameter shape
-- changes. Idempotent via IF EXISTS so re-applies are no-ops.
DROP FUNCTION IF EXISTS public.record_reading_event(uuid, text, text, text, text, text, numeric, integer, text);
DROP FUNCTION IF EXISTS public.get_reading_history(uuid, integer);

-- Update record_reading_event RPC to accept + store the new fields.
-- Older clients that don't pass them simply write NULLs; popover then
-- falls back to the (still-empty) ARTICLES.find path. Schema-level
-- defaults keep the call shape backward-compat.
CREATE FUNCTION public.record_reading_event(
  p_client_id      uuid,
  p_story_id       text,
  p_step           text,
  p_category       text DEFAULT NULL,
  p_level          text DEFAULT NULL,
  p_language       text DEFAULT NULL,
  p_minutes_added  numeric DEFAULT 0,
  p_duration_ms    integer DEFAULT NULL,
  p_day_key        text DEFAULT to_char(now(), 'YYYY-MM-DD'),
  p_title          text DEFAULT NULL,
  p_image_url      text DEFAULT NULL
) RETURNS void
  LANGUAGE plpgsql
  SECURITY DEFINER
  SET search_path TO 'public'
AS $function$
begin
  insert into public.redesign_kid_profiles (client_id) values (p_client_id)
    on conflict (client_id) do update set last_seen_at = now();
  insert into public.redesign_reading_events
    (client_id, story_id, category, level, language, step,
     minutes_added, duration_ms, day_key, title, image_url)
  values
    (p_client_id, p_story_id, p_category, p_level, p_language, p_step,
     coalesce(p_minutes_added, 0), p_duration_ms, p_day_key,
     p_title, p_image_url);
end;
$function$;

-- Extend get_reading_history to surface title + image_url so the
-- client-side cloud merge can populate the popover's snapshot fields
-- (title is the gating field — the renderer skips entries with empty
-- title, which is why Device B's popover silently rendered 0).
CREATE FUNCTION public.get_reading_history(
  p_client_id uuid,
  p_limit     integer DEFAULT 100
) RETURNS TABLE(
  story_id    text,
  step        text,
  category    text,
  level       text,
  occurred_at timestamp with time zone,
  day_key     text,
  title       text,
  image_url   text
)
  LANGUAGE sql
  STABLE SECURITY DEFINER
  SET search_path TO 'public'
AS $function$
  select e.story_id, e.step, e.category, e.level, e.occurred_at, e.day_key,
         e.title, e.image_url
    from public.redesign_reading_events e
   where e.client_id = p_client_id
     and e.occurred_at > now() - interval '21 days'
   order by e.occurred_at desc
   limit greatest(1, least(coalesce(p_limit, 100), 500));
$function$;
