# Model Workspace

`model/` — активная рабочая зона текущего этапа Toxic Analyzer.
Её цель — разработать и воспроизвести baseline-модель для бинарной классификации токсичности.
Каталог должен быть самодостаточным для Python-tooling и удобным как отдельный рабочий `cwd`.

## Быстрый старт: полный pipeline запуска

Ниже — краткий сквозной сценарий от подготовки окружения до обучения baseline и включения интерактивного режима.
Сначала показан путь через Docker, затем ручной путь через уже существующий PostgreSQL.

### Вариант 1: через Docker

Этот вариант удобен, если нужен изолированный локальный PostgreSQL для model-пайплайна.
Все команды ниже предполагают, что текущий каталог — `model/`.

1. Установить Python-зависимости:

```bash
python -m pip install -e .[dev]
```

2. Поднять локальный PostgreSQL в Docker:

```bash
docker volume create toxic-analyzer-postgres-e2e-data
docker run -d \
  --name toxic-analyzer-postgres-e2e \
  -e POSTGRES_DB=toxic_analyzer_e2e \
  -e POSTGRES_USER=toxic_model \
  -e POSTGRES_PASSWORD=toxic_model_pw \
  -p 127.0.0.1:55432:5432 \
  --health-cmd "pg_isready -U toxic_model -d toxic_analyzer_e2e" \
  --health-interval 5s \
  --health-timeout 3s \
  --health-retries 20 \
  -v toxic-analyzer-postgres-e2e-data:/var/lib/postgresql/data \
  postgres:17
```

3. Создать schema training store и, если нужно, импортировать legacy dataset:

```bash
apply-training-store-schema --postgres-dsn "postgresql://toxic_model:toxic_model_pw@127.0.0.1:55432/toxic_analyzer_e2e"
import-mixed-dataset-to-postgres --postgres-dsn "postgresql://toxic_model:toxic_model_pw@127.0.0.1:55432/toxic_analyzer_e2e"
```

4. Настроить DSN для последующих команд:

```powershell
$env:TOXIC_ANALYZER_POSTGRES_DSN="postgresql://toxic_model:toxic_model_pw@127.0.0.1:55432/toxic_analyzer_e2e"
```

5. Обучить baseline от PostgreSQL:

```bash
train-baseline --data-source postgres
```

6. Проверить одиночный inference:

```bash
predict-baseline --text "ты ведешь себя как идиот"
```

7. Включить интерактивный режим:

```bash
ask-baseline
```

После этого можно вводить фразы по одной. Выход — пустая строка или `exit`.

### Вариант 2: ручной путь через уже существующий PostgreSQL

Этот вариант подходит для "сухого" старта, когда репозиторий только что получен, а PostgreSQL уже развернут и хранит данные.
Все команды ниже тоже предполагают работу из `model/`.

1. Установить Python-зависимости:

```bash
python -m pip install -e .[dev]
```

2. Указать подключение к уже существующей БД:

```powershell
$env:TOXIC_ANALYZER_POSTGRES_DSN="postgresql://user:pass@host:5432/toxic_analyzer"
```

3. Если schema training store ещё не применялась, создать её один раз:

```bash
apply-training-store-schema --postgres-dsn "postgresql://user:pass@host:5432/toxic_analyzer"
```

4. Если данные уже лежат в PostgreSQL в ожидаемой схеме, сразу обучить baseline:

```bash
train-baseline --data-source postgres
```

5. Проверить одиночный inference:

```bash
predict-baseline --text "ты ведешь себя как идиот"
```

6. Включить интерактивный режим:

```bash
ask-baseline
```

По умолчанию обучение сохраняет модель в `artifacts/baseline_model_v3_3.pkl`, а интерактивный режим читает именно локальный `.pkl`-артефакт, а не PostgreSQL.

## Роли каталогов

- `notebooks/` — исследования и эксперименты
- `src/` — production-oriented Python-код
- `tests/` — автоматические тесты для Python-модулей
- `configs/` — конфигурации для будущей model-разработки
- `data/` — локальные датасеты и промежуточные данные, которые не должны коммититься
- `artifacts/` — артефакты, чекпоинты и результаты запусков, которые не должны коммититься

Минимальная структура намеренно остаётся компактной.
Пустые каталоги без очевидной пользы лучше не добавлять заранее.

## Правило для ноутбуков

Jupyter Notebook используется как лаборатория: для проверки гипотез, анализа данных и прототипирования идей.
Ноутбуки не являются источником production-кода.

Если решение подтверждено экспериментом, его нужно переносить в обычные Python-модули внутри `src/`.
Ноутбуки должны оставаться местом для исследований, а не финальной реализации.

Ручная проверка качества будущей модели может начинаться в ноутбуках, но повторяемая логика должна постепенно выноситься в Python-код и тесты.

## Python Tooling

`model/` оформлен как самостоятельный Python-подпроект.
Конфигурация форматирования, линтинга и тестов находится в `model/pyproject.toml`.

Это позволяет:

- запускать Python-tooling прямо из `model/`
- держать `src/` как будущий импортируемый пакет
- готовить код к использованию из внешнего слоя, например будущего FastAPI, не смешивая модельный код с API

## Текущие границы

Сейчас каталог используется для baseline-разработки модели.
На этом этапе допускаются training pipeline, evaluation flow, сохранение артефактов обучения и минимальный inference-интерфейс внутри `model/`.
`backend/` и `frontend/` по-прежнему не реализуются и не должны определять форму модельного кода.

## Целевая постановка

Текущая задача — бинарная классификация токсичности по одному входу:

- вход: только текст комментария;
- выход: `label` и `toxic_probability`;
- `label`: `1` для токсичного комментария и `0` для нетоксичного;
- `toxic_probability`: число от `0` до `1`, означающее вероятность токсичности комментария.

Итоговый `label` получается порогованием `toxic_probability`.

## Целевой домен и основной датасет

Целевой домен модели — смешанный русскоязычный UGC, а не отдельный источник вроде `Habr`.
Для baseline-разработки используется общий размеченный набор, но с этого этапа `PostgreSQL` считается
основным хранилищем текстовых данных для `train/retrain`.
Локальный `data/processed/mixed_toxic_comments.sqlite3` остаётся legacy-источником для совместимости,
первичного импорта и fallback-сценария, а не единственным рабочим хранилищем.

Этот датасет объединяет несколько источников:

- `habr`
- `ok`
- `dvach`

`Habr` остаётся полезным источником данных, но не рассматривается как главный или единственный домен, на который ориентируется модель.
Поэтому итоговые метрики baseline следует анализировать:

- по всему смешанному датасету;
- отдельно по каждому источнику.

### PostgreSQL training store

По умолчанию используется отдельная схема `toxic_analyzer_model`.
SQL/schema файлы лежат в `sql/postgres/`:

- `001_create_training_store.sql`
- `002_create_training_dataset_view.sql`

Внутри схемы намеренно разделены разные типы данных:

- `canonical_training_texts` — canonical labeled texts для baseline training;
- `feedback_events` — пользовательские feedback-события, которые не идут в обучение напрямую;
- `training_candidates` — промежуточный curated layer между feedback и canonical set;
- `model_registry` — метаданные обученных моделей и путь к локальному артефакту;
- `retrain_jobs` — состояние будущих `train/retrain` запусков.

В обучение из PostgreSQL идут только:

- записи из `canonical_training_texts` со статусом `labeled`;
- записи из `training_candidates` со статусом `approved`.

`feedback_events` не смешиваются с canonical training set напрямую.
Веса модели не сохраняются в PostgreSQL: `model_registry.artifact_path` указывает на локальный файл в
`model/artifacts/`, а само обучение и retrain по-прежнему живут в Python-коде внутри `model/`.

## Baseline pipeline

Текущий baseline строится на обучающей выборке, которую `train-baseline` получает через repository/data-source layer.
По умолчанию CLI работает в режиме `--data-source auto`:

- если настроен PostgreSQL DSN или env-конфигурация, основной источник — view `training_examples_for_training`;
- если PostgreSQL не настроен, используется локальный `data/processed/mixed_toxic_comments.sqlite3`.

После загрузки данных применяются следующие правила:

- используются только строки с бинарной меткой;
- строки с одинаковым нормализованным текстом и противоречащими метками исключаются из обучения;
- точные дубликаты текста с одинаковой меткой схлопываются до одной записи;
- split строится как `70/15/15` со стратификацией по комбинации `source + label`;
- если в PostgreSQL появляются редкие curated source strata, sparse rows распределяются отдельно, не ломая основной stratified split для крупных источников.

Для первого baseline в кодовой базе используется линейная модель на `TF-IDF` признаках:

- word n-grams;
- char n-grams;
- `LogisticRegression`;
- калибровка `toxic_probability` через validation split.

Подробная история эволюции baseline, различия между V1, V2 и V3, реальные трудности модели и инженерные выводы
вынесены в отдельный документ [MODEL_EVOLUTION.md](C:/Users/Alexomur/Desktop/projects/toxic-analyzer/model/MODEL_EVOLUTION.md).

### Запуск обучения baseline

Из каталога `model/`:

```bash
python -m pip install -e .[dev]
train-baseline
```

По умолчанию команда:

- работает в режиме `--data-source auto`;
- сначала пытается читать данные из PostgreSQL, если настроены `TOXIC_ANALYZER_POSTGRES_DSN` или совместимый набор env vars;
- при отсутствии PostgreSQL-конфигурации читает `data/processed/mixed_toxic_comments.sqlite3`;
- сохраняет модель в `artifacts/baseline_model_v3_3.pkl`;
- сохраняет отчёт с метриками в `artifacts/baseline_training_report_v3_3.json`;
- использует `configs/baseline_seed_examples_v3.jsonl` и `configs/baseline_hard_cases_v3.jsonl`.

Полезные режимы запуска:

```bash
train-baseline --data-source sqlite --dataset-db data/processed/mixed_toxic_comments.sqlite3
train-baseline --data-source postgres --postgres-dsn "postgresql://user:pass@db.example.com:5432/toxic_analyzer"
```

Поддерживаются два способа настройки PostgreSQL:

- единый DSN через `TOXIC_ANALYZER_POSTGRES_DSN` или `--postgres-dsn`;
- набор env vars: `TOXIC_ANALYZER_POSTGRES_HOST`, `TOXIC_ANALYZER_POSTGRES_PORT`,
  `TOXIC_ANALYZER_POSTGRES_DB`, `TOXIC_ANALYZER_POSTGRES_USER`,
  `TOXIC_ANALYZER_POSTGRES_PASSWORD`, `TOXIC_ANALYZER_POSTGRES_SSLMODE`,
  `TOXIC_ANALYZER_POSTGRES_SCHEMA`.

`localhost` не захардкожен: можно указывать адрес отдельной машины, Docker hostname, WSL-host или любой другой
доступный PostgreSQL endpoint.

### Подготовка PostgreSQL schema и импорт legacy SQLite

Рекомендуемый путь миграции:

```bash
python -m pip install -e .[dev]
apply-training-store-schema --postgres-dsn "postgresql://user:pass@db.example.com:5432/toxic_analyzer"
import-mixed-dataset-to-postgres --postgres-dsn "postgresql://user:pass@db.example.com:5432/toxic_analyzer" --apply-schema
```

`import-mixed-dataset-to-postgres`:

- читает legacy `mixed_toxic_comments.sqlite3`, включая старую сокращённую SQLite-схему;
- делает batched upsert в `canonical_training_texts`;
- валидирует итоговые количества строк и breakdown по `source` / `label_status`;
- безопасно перезапускается повторно за счёт upsert по `(origin_system, source, source_record_id)`.

Если в окружении уже есть PostgreSQL deployment, используйте отдельную БД или отдельную schema.
Эти команды не удаляют существующие инстансы, не требуют destructive Docker-операций и не переносят веса модели в БД.

### Локальный PostgreSQL через Docker

Для локальной разработки безопаснее поднимать отдельный контейнер с уникальным именем, отдельным volume и отдельным host port,
а не переиспользовать уже существующие PostgreSQL-инстансы.

Проверенный локальный профиль:

- container name: `toxic-analyzer-postgres-e2e`
- image: `postgres:17`
- host port: `127.0.0.1:55432`
- db: `toxic_analyzer_e2e`
- user: `toxic_model`
- schema: `toxic_analyzer_model`

Пример запуска:

```bash
docker volume create toxic-analyzer-postgres-e2e-data
docker run -d \
  --name toxic-analyzer-postgres-e2e \
  -e POSTGRES_DB=toxic_analyzer_e2e \
  -e POSTGRES_USER=toxic_model \
  -e POSTGRES_PASSWORD=toxic_model_pw \
  -p 127.0.0.1:55432:5432 \
  --health-cmd "pg_isready -U toxic_model -d toxic_analyzer_e2e" \
  --health-interval 5s \
  --health-timeout 3s \
  --health-retries 20 \
  -v toxic-analyzer-postgres-e2e-data:/var/lib/postgresql/data \
  postgres:17
```

После этого можно применить schema и импортировать legacy dataset:

```bash
apply-training-store-schema --postgres-dsn "postgresql://toxic_model:toxic_model_pw@127.0.0.1:55432/toxic_analyzer_e2e"
import-mixed-dataset-to-postgres --postgres-dsn "postgresql://toxic_model:toxic_model_pw@127.0.0.1:55432/toxic_analyzer_e2e"
```

Остановить и удалить именно этот контейнер:

```bash
docker stop toxic-analyzer-postgres-e2e
docker rm -f toxic-analyzer-postgres-e2e
docker volume rm toxic-analyzer-postgres-e2e-data
```

Важно:

- системный PostgreSQL на `5432` можно оставить нетронутым;
- отдельный Docker PostgreSQL должен жить на своём порту, например `55432`;
- не использовать destructive Docker-команды против чужих контейнеров и volume.

### Проверенный e2e сценарий

На текущем этапе уже был реально прогнан локальный e2e сценарий на Docker PostgreSQL:

1. поднят отдельный контейнер `postgres:17` на `127.0.0.1:55432`;
2. применена schema `toxic_analyzer_model`;
3. импортирован `data/processed/mixed_toxic_comments.sqlite3`;
4. проверено, что в `canonical_training_texts` и `training_examples_for_training` доступно `164770` строк;
5. выполнен `train-baseline --data-source postgres`;
6. выполнены `predict-baseline` и `ask-baseline` от нового локального `.pkl` артефакта.

Пример обучающего запуска:

```bash
train-baseline \
  --data-source postgres \
  --postgres-dsn "postgresql://toxic_model:toxic_model_pw@127.0.0.1:55432/toxic_analyzer_e2e" \
  --model-output artifacts/baseline_model_postgres_docker_e2e.pkl \
  --report-output artifacts/baseline_training_report_postgres_docker_e2e.json
```

В этом сценарии training report фиксировал `dataset_source.kind = "postgres"`, а inference оставался независимым от БД и работал только через локальный артефакт модели.

### Запуск инференса baseline

```bash
predict-baseline --text "ты ведёшь себя как идиот"
```

Команда печатает JSON с `label` и `toxic_probability`.
По умолчанию используется `artifacts/baseline_model_v3_3.pkl`.
Для inference PostgreSQL не нужен: команда читает только локальный артефакт модели.

### Программный слой инференса

Для интеграции модели во внешний сервисный слой не нужно вызывать CLI-команды из Python-кода.
Внутри пакета есть отдельный service-layer:

- `toxic_analyzer.model_runtime` — разрешение пути к артефакту модели и её загрузка;
- `toxic_analyzer.inference_service.ToxicityInferenceService` — программный интерфейс для single и batch inference.

CLI-инструменты и внутренний FastAPI используют тот же service-layer. PostgreSQL нужен для
train/retrain и data management, а не для загрузки весов. Отдельный runtime/admin контракт
описан в [FASTAPI.md](C:/Users/Alexomur/Desktop/projects/toxic-analyzer/model/FASTAPI.md).

### Отдельный пользовательский скрипт

Если нужен более простой запуск без JSON-обвязки, используйте:

```bash
ask-baseline "ты ведёшь себя как идиот"
```

Если запустить `ask-baseline` без параметров, команда перейдёт в интерактивный режим и будет читать фразы из консоли до пустой строки или `exit`.
По умолчанию используется `artifacts/baseline_model_v3_3.pkl`.

## Подготовка комментариев Habr

Для первичной подготовки датасета используется публичный датасет Hugging Face `IlyaGusev/habr`.
В проекте добавлен минимальный пайплайн, который:

- скачивает parquet-shard'ы датасета;
- разворачивает вложенные `comments` в плоскую таблицу "один комментарий = одна запись";
- оставляет только комментарии из русскоязычных статей;
- дополнительно фильтрует комментарии на уровне самого текста;
- сохраняет `raw_text`, `clean_text` и служебные флаги пригодности для аннотации.

Пайплайн запускается модулем `toxic_analyzer.prepare_habr_comments`.

### Что делает очистка

- берёт `message_markdown`, а при его отсутствии извлекает текст из `message_html`;
- нормализует Unicode и пробелы;
- маскирует `URL`, email и крупные code block'и специальными токенами;
- не вырезает всю латиницу из русских комментариев;
- отсеивает комментарии, которые:
  - не проходят проверку на русский язык;
  - состоят в основном из кода;
  - не содержат достаточно осмысленного текста;
  - являются точными дубликатами по `clean_text`.

Латиница сохраняется намеренно: для Habr она часто несёт смысл как часть обычного технического текста
(`Python`, `Docker`, `PostgreSQL`, названия API, команд и продуктов). Полное удаление латиницы ухудшило бы
качество данных и повредило бы контекст комментария.

### Выходные файлы

- `data/processed/habr_comments_russian_annotation_pool.jsonl` — очищенные русские комментарии, пригодные для разметки;
- `artifacts/habr_comments_preparation_report.json` — сводка по количеству статей, комментариев и причин отбраковки.

### Компактная база для разметки только по тексту комментария

Если нужен минимальный SQLite-слой без контекста статьи, времён публикации и прочих source-level полей,
можно собрать отдельную компактную базу напрямую из очищенного `jsonl`:

```bash
python -m pip install -e .
build-habr-annotation-compact-db --rebuild
```

По умолчанию скрипт читает `data/processed/habr_comments_russian_annotation_pool.jsonl` и создаёт
`data/processed/habr_comments_annotation_compact.sqlite3` со схемой:

- `id`
- `comment_id`
- `habr_score`
- `raw_text`
- `toxic_label`
- `label_status`

При такой миграции `toxic_label` намеренно сбрасывается в `NULL`, а статусы сводятся к минимальной схеме:
записи с `is_annotation_ready = true` получают `pending`, остальные `excluded`.

### Запуск

Рекомендуемое окружение для этого пайплайна — Python `3.12`.
На Windows можно просто запустить файл [run_prepare_habr_comments.bat](C:/Users/Alexomur/Desktop/projects/toxic-analyzer/model/run_prepare_habr_comments.bat).
Он установит зависимости в локальное окружение и начнёт полную выгрузку и очистку датасета.

Если в окружении задан `HF_TOKEN`, Hugging Face будет использовать авторизованные запросы. Это полезно при
долгой загрузке или повторных обрывах.

Альтернативно из `model/` можно запустить:

```bash
python -m pip install -e .
prepare-habr-comments --config configs/habr_comments.toml
```

### Продолжение после обрыва

Пайплайн поддерживает `resume`-режим:

- после каждого завершённого shard'а он пишет `artifacts/habr_comments_preparation_progress.json`;
- при `--resume` он восстанавливает dedup-состояние из уже записанного `jsonl`;
- при наличии progress-файла продолжает со следующего shard'а;
- при необходимости можно явно указать `--start-shard`.

Примеры:

```bash
prepare-habr-comments --config configs/habr_comments.toml --resume
prepare-habr-comments --config configs/habr_comments.toml --resume --start-shard 8
```

Для Windows-скрипта это тоже работает:

```bat
run_prepare_habr_comments.bat --resume
run_prepare_habr_comments.bat --resume --start-shard 8
```

## Рабочее определение токсичности

Для текущего этапа токсичным считается комментарий, который направленно оскорбляет, унижает, агрессивно атакует,
провоцирует враждебность или желает вред человеку либо группе.

Формулировка "текст вызывает негативные эмоции" сама по себе не используется как основное правило.
Она слишком широкая и даёт шумную разметку: негативные эмоции могут вызывать новости, жалобы, резкая критика
или описание неприятных событий без токсичной атаки на адресата.

Базовый принцип: токсичность определяется не по общему негативному тону текста, а по наличию направленной
словесной агрессии в адрес человека, группы или собеседника.

## Целевая схема ответа модели

Интерфейс baseline-модели должен быть максимально простым:

- `label`: `0` / `1`
- `toxic_probability`: число от `0` до `1`, означающее вероятность токсичности

Где:

- `1` означает токсичный комментарий;
- `0` означает нетоксичный комментарий.

Итоговый `label` получается порогованием `toxic_probability`.

## Правила разметки

Ставить `Да`, если комментарий:

- содержит прямые оскорбления, унижение или словесную атаку на человека;
- использует мат или грубую лексику как нападение на адресата, а не как фоновую эмоцию;
- выражает угрозу, пожелание вреда или одобрение вреда;
- направлен на травлю, высмеивание или дегуманизацию человека либо группы;
- содержит враждебные обобщения по отношению к социальной, этнической, гендерной, религиозной или иной группе;
- использует явную агрессию, где цель высказывания — задеть, унизить или спровоцировать враждебность.

Ставить `Нет`, если комментарий:

- выражает несогласие или критику без оскорблений и унижения;
- негативно оценивает событие, продукт, идею или ситуацию, но не атакует человека или группу;
- описывает грустные, тяжёлые или шокирующие события без агрессии к адресату;
- содержит нейтральную цитату токсичного текста без поддержки этой позиции;
- использует эмоциональную или грубую лексику как реакцию на ситуацию, а не как атаку на кого-то;
- остаётся неоднозначным, но в нём нет достаточно явного признака направленной словесной агрессии.

## Пограничные случаи

- Жёсткая критика без оскорблений: `Нет`.
- Сарказм или пассивная агрессия: `Да`, если унижение или враждебность выражены достаточно ясно.
- Мат без адресата: чаще `Нет`; мат как обращение к человеку или группе: `Да`.
- Цитирование чужой токсичности в учебных, аналитических или новостных целях: `Нет`, если автор не поддерживает атаку.
- Описание насилия, трагедии или преступления: `Нет`, если текст не атакует адресата.
- Оскорбление неопределённой группы людей: `Да`, если это враждебное обобщение, даже без конкретного имени.

Если текст пограничный, приоритет у более консервативной разметки: без явной направленной агрессии ставится `Нет`.
В таких случаях `toxic_probability` может оставаться ближе к порогу из-за неопределённости.

## FastAPI runtime

Внутренний FastAPI слой можно поднять прямо из `model/`:

```bash
python -m pip install -e .[dev]
serve-model-api --host 127.0.0.1 --port 8000
```

По умолчанию runtime загружает `artifacts/baseline_model_v3_3.pkl`. Если локальный артефакт отсутствует, `GET /health/live` отвечает успешно, а `GET /health/ready` возвращает `503`.

Доступные ручки:

- `GET /health/live`
- `GET /health/ready`
- `GET /v1/model/info`
- `POST /v1/predict`
- `POST /v1/predict/batch`
- `POST /v1/admin/reload`
- `POST /v1/admin/retrain`
- `GET /v1/admin/jobs/{job_key}`
- `GET /v1/admin/jobs`

Для `retrain` и job-status должен быть настроен PostgreSQL training store через `TOXIC_ANALYZER_POSTGRES_DSN` или совместимый набор env vars. Runtime inference по-прежнему читает только локальный артефакт модели.

### Docker runtime

Контейнер для внутреннего FastAPI runtime можно собрать прямо из корня репозитория:

```bash
docker build -t toxic-analyzer-model:local ./model
```

Запуск контейнера:

```bash
docker run --rm -p 8000:8000 --name toxic-analyzer-model toxic-analyzer-model:local
```

Что важно:

- образ ожидает локальный артефакт в `model/artifacts/`, обычно `baseline_model_v3_3.pkl`;
- Docker healthcheck внутри образа смотрит в `GET /health/ready`;
- для `retrain` и job-status можно пробросить PostgreSQL через `-e TOXIC_ANALYZER_POSTGRES_DSN=...` или совместимый набор env vars.

## Короткий guide для ручной разметки

Перед выставлением метки полезно проверить три вопроса:

1. Есть ли в тексте цель атаки: человек, собеседник или группа?
2. Есть ли в тексте унижение, оскорбление, угроза или явная враждебность?
3. Хочет ли автор именно задеть адресата, а не просто выразить негативное мнение о ситуации?

Если ответы на первый и второй вопросы скорее "да", метка обычно должна быть `Да`.
Если негатив есть, но целевой словесной агрессии нет, метка должна быть `Нет`.

## Примеры

- "Ты идиот, с тобой невозможно говорить" -> `Да`
- "Надеюсь, тебя уволят и больше никуда не возьмут" -> `Да`
- "Все такие люди отвратительны" -> `Да`
- "Заткнись уже, надоел" -> `Да`
- "Автор статьи плохо разобрался в теме" -> `Нет`
- "Мне очень не нравится эта идея, она сырая" -> `Нет`
- "Это ужасная новость, очень тяжело такое читать" -> `Нет`
- "Чёрт, опять всё сломалось" -> `Нет`
- "Он сказал: 'ты ничтожество', и после этого его забанили" -> `Нет`
- "Ну да, конечно, ты у нас самый умный" -> `Да`, если по контексту это явное унижение
- "Ваше решение выглядит слабым, потому что в нём нет данных" -> `Нет`
- "Таких людей надо изолировать от общества" -> `Да`
