select skill, category from {{ ref('stg_features__skill_taxonomy') }}
