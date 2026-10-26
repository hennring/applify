-- Technologies the LLM named that are not in skills.yaml yet (§5.8).
select distinct
    f.job_id,
    candidate
from {{ ref('stg_features__job_features') }} f
cross join unnest(f.skill_candidates) as candidate
