"""Fresh read-only Supabase source/history snapshot; no DB or source-config writes."""
from datetime import date, datetime, timedelta, timezone
import argparse
import json
from pathlib import Path

from .agent_shadow import write


def snapshot(sb, day):
    date.fromisoformat(day)
    start = (date.fromisoformat(day) - timedelta(days=7)).isoformat()
    fields = 'id,name,category,rss_url,priority,enabled,is_backup,state,active_weekdays,cadence_days,last_used_at,next_pickup_at,feed_kind,feed_config,max_to_vet,min_body_words,flow'
    # Page both reads; never treat the API row limit as the complete configuration.
    def pages(table, fields, configure, order):
        rows = []
        for offset in range(0, 10000, 500):
            result = configure(sb.table(table).select(fields)).order(order).range(offset, offset+499).execute()
            batch = result.data
            if not isinstance(batch, list):
                raise ValueError('Connector returned no row list')
            rows.extend(batch)
            if len(batch) < 500:
                return rows
        raise ValueError('Snapshot pagination budget exceeded')
    sources = pages('redesign_source_configs', fields, lambda q: q.eq('enabled', True), 'id')
    history = pages('redesign_stories', 'id,category,published_date,source_title,source_url,source_name,payload_story_id,archived',
        lambda q: q.gte('published_date', start).lt('published_date', day).eq('archived', False), 'id')
    if not sources or not history:
        raise ValueError('Source/history snapshot empty; check connector, never assume clearance')
    return {'date': day, 'fetched_at': datetime.now(timezone.utc).isoformat(),
            'sources': sources, 'history': history, 'authority': 'Supabase read-only'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--date', required=True)
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--env-file', type=Path)
    args = p.parse_args()
    try:
        if args.output.exists():
            raise ValueError('Snapshot already frozen; choose a new output path')
        from dotenv import load_dotenv
        load_dotenv(args.env_file)
        import os
        from supabase import create_client, ClientOptions
        sb = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_ANON_KEY'],
            options=ClientOptions(headers={'Authorization': 'Bearer ' + os.environ['SUPABASE_READ_TOKEN']}))
        value = snapshot(sb, args.date)
        write(args.output, value)
        print(json.dumps({'ok': True, 'sources': len(value['sources']), 'history': len(value['history']), 'path': str(args.output)}))
        return 0
    except Exception as exc:
        print(json.dumps({'ok': False, 'error': str(exc) if isinstance(exc, ValueError) else type(exc).__name__}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
