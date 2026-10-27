-- Benefits offered per job (grain: job, benefit), from the rule extraction (§5.9).
select
    f.job_id,
    b.benefit
from {{ ref('stg_features__job_features') }} f
cross join lateral unnest(f.benefits) as b(benefit)
join {{ ref('fct_job_postings') }} p using (job_id)
