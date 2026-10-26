select role_family, label, sort_order from {{ source('features', 'role_families') }}
