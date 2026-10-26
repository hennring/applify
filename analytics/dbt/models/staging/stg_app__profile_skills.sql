select
    p.user_id,
    s.skill,
    s.canonical,
    s.category,
    s.weight
from {{ source('app', 'profile_skills') }} s
join {{ source('app', 'profiles') }} p on p.id = s.profile_id
