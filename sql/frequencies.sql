CREATE TABLE counts_1 AS
SELECT [skill] AS skills, count(*) AS frequency
FROM expanded GROUP BY skill;

CREATE TABLE counts_2 AS
SELECT [a.skill, b.skill] AS skills, count(*) AS frequency
FROM expanded a JOIN expanded b
  ON a.vacancy_id = b.vacancy_id AND a.skill < b.skill
GROUP BY a.skill, b.skill;

CREATE TABLE counts_3 AS
SELECT [a.skill, b.skill, c.skill] AS skills, count(*) AS frequency
FROM expanded a JOIN expanded b
  ON a.vacancy_id = b.vacancy_id AND a.skill < b.skill
JOIN expanded c ON a.vacancy_id = c.vacancy_id AND b.skill < c.skill
GROUP BY a.skill, b.skill, c.skill;
