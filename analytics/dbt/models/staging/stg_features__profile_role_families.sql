select user_id, role, role_family from {{ source('features', 'profile_role_families') }}
