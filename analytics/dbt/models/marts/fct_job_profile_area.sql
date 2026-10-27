-- Jobs within a radius of each user's places, for the scope filter "my places".
select user_id, job_id, distance_km
from {{ ref('int_job_profile_distance') }}
where within_radius
