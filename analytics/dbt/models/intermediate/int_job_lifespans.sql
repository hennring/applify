-- When each job was seen first and last, over all its source postings. Sightings are
-- mapped to the job via job_sources, so merges made after the sighting are respected.
with sightings as (
    select
        s.job_id,
        min(r.seen_at) as first_seen_at,
        max(r.seen_at) as last_seen_at,
        count(distinct r.run_id) as runs_seen
    from {{ ref('stg_raw__job_sightings') }} r
    join {{ ref('stg_app__job_sources') }} s using (source, external_id)
    group by s.job_id
)

select
    j.job_id,
    least(j.first_seen_at, s.first_seen_at) as first_seen_at,
    coalesce(s.last_seen_at, j.first_seen_at) as last_seen_at,
    coalesce(s.runs_seen, 0) as runs_seen
from {{ ref('stg_app__jobs') }} j
left join sightings s using (job_id)
