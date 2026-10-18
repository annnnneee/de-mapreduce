# Технология MapReduce

Бондаренко Анна Андреевна

**Вариант № 2: «Программист, разработчик на Python».**

[Отчёт PDF](report/main.pdf) · [Исходник LaTeX](report/main.tex)

Из 229 388 IT-вакансий отобрано 3 892 вакансии Python-разработчиков.
Собственный MapReduce читает CSV из RustFS порциями по 1 000 строк,
считает частоты навыков, пар и троек в двух процессах.
Независимые запросы DuckDB дают те же частоты и набор вакансий.
Повтор маппера после искусственного сбоя также сохраняет результат.

| Метод | Медиана времени, с | Максимум RSS, MiB |
|---|---:|---:|
| MapReduce | 20.616 | 369.41 |
| DuckDB | 15.814 | 1309.12 |

Три запуска каждого метода. Замер включает чтение S3 и локальную запись,
загрузка результатов в S3 и сверка выполняются вне замера.
RSS — максимум суммы памяти родителя и потомков, шаг 50 мс.
Подробности и реальные скриншоты запусков находятся в отчёте.

## Файлы

- `scripts/` — обработка, сверка, профилирование и анализ зарплат и регионов.
- `sql/` — запросы DuckDB.
- `results/mapreduce/` — частоты, идентификаторы вакансий и манифест S3.
- `results/duckdb/summary.json` — итог независимого расчёта.
- `results/analysis/` — аналитические CSV.
- `evidence/` — профиль исходника, сверки и логи трёх запусков.
- `report/` — LaTeX, PDF и 12 скриншотов.
- `compose.yaml` — четыре узла RustFS.

## Запуск

Python 3.11. Команды выполняются из корня проекта.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

В `.env` укажи ключи своего RustFS. Адрес S3: `http://127.0.0.1:19000`,
консоль: `http://127.0.0.1:19001`. Для нового развёртывания:

```bash
docker compose up -d
```

В консоли создай бакет `hh-lake` и загрузи исходный
`it_vacancies_2024.csv` в `raw/`. Готовое хранилище можно использовать повторно.
Исходный CSV размером 808.4 MiB в репозиторий не включён.
Его SHA-256 и число строк записаны в `evidence/source_profile.json`.
Для локального профилирования положи CSV в `data/` либо задай `source`
в личном `config.local.json`.

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

Полные частоты DuckDB и выборка для анализа создаются при запуске.
В Git хранится один полный комплект частот — MapReduce.
Зарплаты сравниваются в рублях на руки, для вилки используется середина.
В зарплатных группах не менее 10 наблюдений; разница медиан показывает
связь в выборке, а не причинное влияние навыка.

Для сборки отчёта: `cd report` и `tectonic main.tex`.
Нужны шрифты PT Serif, PT Sans и Menlo.
