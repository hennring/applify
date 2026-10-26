-- Skills named together in the same posting (each pair once, alphabetically).
select
    a.skill as skill_a,
    b.skill as skill_b,
    count(*) as jobs
from {{ ref('bridge_job_skills') }} a
join {{ ref('bridge_job_skills') }} b on a.job_id = b.job_id and a.skill < b.skill
group by a.skill, b.skill
having count(*) >= 3
