select role_family, label, sort_order from {{ ref('stg_features__role_families') }}
