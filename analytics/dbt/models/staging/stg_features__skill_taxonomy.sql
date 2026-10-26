select skill, category from {{ source('features', 'skill_taxonomy') }}
