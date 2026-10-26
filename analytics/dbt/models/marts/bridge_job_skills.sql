-- Skills per job (taxonomy names only); candidates are in bridge_job_skill_candidates.
select distinct
    f.job_id,
    skill,
    coalesce(t.category, 'other') as category
from {{ ref('stg_features__job_features') }} f
cross join unnest(f.skills) as skill
left join {{ ref('stg_features__skill_taxonomy') }} t using (skill)
