{% macro days_between(a,b) %}
 {% if target.type == 'postgres' %} (cast({{ b }} as date)-cast({{ a }} as date))
 {% else %} datediff('day', {{ a }}, {{ b }}) {% endif %}
{% endmacro %}
{% macro month(col) %}cast(date_trunc('month',{{ col }}) as date){% endmacro %}
