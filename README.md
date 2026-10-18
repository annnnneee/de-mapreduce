# MapReduce

Бондаренко Анна Андреевна

**Вариант № 2: «Программист, разработчик на Python».**

[Отчёт PDF](report/main.pdf)

Из 229 388 IT-вакансий отобрано 3 892 вакансии Python-разработчиков.
MapReduce читает CSV из RustFS порциями по 1 000 строк,
считает частоты навыков, пар и троек в двух процессах.
Запросы DuckDB дают те же частоты и набор вакансий.
Повтор маппера после сбоя также сохраняет результат.

| Метод | Медиана времени, с | Максимум RSS, MiB |
|---|---:|---:|
| MapReduce | 20.616 | 369.41 |
| DuckDB | 15.814 | 1309.12 |

## Файлы

- `scripts/` — обработка, сверка, профилирование и анализ зарплат и регионов.
- `sql/` — запросы DuckDB.
- `results/mapreduce/` — частоты, идентификаторы вакансий и манифест S3.
- `results/duckdb/summary.json` — итог расчёта.
- `results/analysis/` — аналитические CSV.
- `evidence/` — профиль исходника, сверки и логи трёх запусков.
- `report/` — отчёт.
- `compose.yaml` — 4 узла RustFS.

## Запуск

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

```bash
docker compose up -d
```

```bash
python scripts/verify_upload.py
python scripts/run_mapreduce.py --upload
python scripts/run_duckdb.py
python scripts/compare_results.py
python scripts/run_mapreduce.py --inject-failure --output mapper_failure
python scripts/compare_results.py --left mapreduce --right mapper_failure
python scripts/run_duckdb.py --setup
python scripts/benchmark.py --runs 3
python scripts/analysis.py salary --size 2
python scripts/analysis.py salary --size 3
python scripts/analysis.py regions
```
