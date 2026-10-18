with jobs as (
    select experience,
           list_transform(string_split(coalesce(key_skills, ''), ';'), x -> lower(trim(x))) as skills
    from read_csv('results/duckdb/selected.csv', all_varchar=true)
    where currency='RUR' and gross='false'
      and (salary_from is not null or salary_to is not null)
), cohorts(name, skills) as (
    values ('git', ['git']), ('git + html', ['git', 'html']),
           ('bottle + python', ['bottle', 'python']),
           ('python + zeromq', ['python', 'zeromq'])
)
select c.name as skills, j.experience, count(*) as vacancies
from jobs j cross join cohorts c
where list_has_all(j.skills, c.skills)
group by c.name, j.experience
order by c.name, j.experience;
