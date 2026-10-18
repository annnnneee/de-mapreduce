CREATE TABLE selected AS
SELECT vacancy_id, name, role, area, salary_from, salary_to, currency, gross,
       experience, key_skills
FROM read_csv('s3://hh-lake/raw/it_vacancies_2024.csv',
              header=true, all_varchar=true, delim=',', quote='"', escape='"',
              parallel=false, max_line_size=16777216)
WHERE trim(role) = 'Программист, разработчик'
  AND regexp_matches(lower(name), '(^|[^\p{L}\p{N}_])python([^\p{L}\p{N}_]|$)');

CREATE TABLE normalized AS
SELECT vacancy_id,
       list_sort(list_distinct(list_filter(
           list_transform(string_split(coalesce(key_skills, ''), ';'),
                          x -> lower(trim(x))),
           x -> x <> ''))) AS skills
FROM selected;

CREATE TABLE expanded AS
SELECT vacancy_id, unnest(skills) AS skill FROM normalized;
