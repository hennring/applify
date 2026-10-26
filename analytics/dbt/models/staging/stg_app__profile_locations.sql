select
    p.user_id,
    l.name,
    l.lat,
    l.lon,
    l.radius_km
from {{ source('app', 'profile_locations') }} l
join {{ source('app', 'profiles') }} p on p.id = l.profile_id
where l.lat is not null and l.lon is not null
