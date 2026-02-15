# 🎯 Portfolio Fit

Умная платформа для анализа и оценки соответствия вашего GitHub-портфолио вакансиям.

Smart platform for analyzing and evaluating how your GitHub portfolio matches job requirements.

> **Текущая версия v3.1**: Multi-stack оценка (Python + Jupyter `.ipynb` + JS/TS + HTML/CSS + SQL signals) с stack-aware coverage и profile recalibration  
> **Планы**: Веб-приложение с анализом соответствия вакансиям, умным отбором проектов и планом доработок

## 📊 Описание / Description

Этот скрипт оценивает ваши репозитории по **17 core-критериям** + standalone full-stack сигналам и выставляет итог по **50-балльной нормализованной шкале** (Production Readiness Score v3.1).

This script evaluates your repositories across **17 core criteria** plus standalone full-stack signals and outputs a **normalized 50-point score** (Production Readiness Score v3.1).

### Критерии оценки / Evaluation Criteria

1. **CODE QUALITY & STABILITY** (15 баллов)
   - Test Coverage
   - Code Complexity
   - Type Hints

2. **SECURITY & DEPENDENCIES** (10 баллов)
   - Vulnerabilities
   - Dependency Health
   - Security Scanning

3. **MAINTENANCE & MATURITY** (10 баллов)
   - Project Activity
   - Version Stability
   - CHANGELOG

4. **ARCHITECTURE & ENGINEERING** (10 баллов)
   - Docstrings
   - Logging
   - Project Structure

5. **DOCUMENTATION & UX** (10 баллов)
   - README Quality
   - API Documentation
   - Getting Started Ease

6. **DEPLOYMENT & DEVOPS** (5 баллов)
   - Docker
   - CI/CD

### Прозрачность метрик / Metrics Transparency

- Каждый критерий имеет `status`: `known` или `unknown`
- У каждого критерия есть `method`: `measured` или `heuristic`
- У каждого критерия есть `confidence` (0..1)
- Итоговый `total_score` нормализуется по известным данным, а полнота измерения показывается в `data_coverage_percent`
- Для неприменимых проверок используется `not_applicable` (без штрафа в итоговом score)

### Поддерживаемые стеки / Supported stacks

- `python_backend`
- `python_fullstack_react`
- `python_django_templates`
- `node_frontend`
- `mixed_unknown`

CLI поддерживает `--stack-profile auto` (по умолчанию) и ручной override
для воспроизводимости.

Для Python-аналитики учитываются как `.py`, так и code-cells из `.ipynb`.

## 🚀 Быстрый старт / Quick Start

### Требования / Requirements

- Python 3.8+
- Git (для клонирования репозиториев)

### Установка / Installation

```bash
git clone https://github.com/ergon73/portfolio-fit.git
cd portfolio-fit
```

### Использование / Usage

#### 1. Оценка GitHub аккаунта / Evaluate GitHub account

```bash
python enhanced_evaluate_portfolio.py -g username
```

#### 2. Оценка всех репозиториев / Evaluate all repositories

```bash
python enhanced_evaluate_portfolio.py -g username --max-repos 0
```

#### 3. Локальная папка с репозиториями / Local folder

```bash
python enhanced_evaluate_portfolio.py --path ./repos
```

#### 3a. Принудительный stack profile / Forced stack profile

```bash
python enhanced_evaluate_portfolio.py --path ./repos --stack-profile python_backend
python enhanced_evaluate_portfolio.py --path ./repos --stack-profile node_frontend
```

#### 4. Windows (batch файл) / Windows (batch file)

Отредактируйте `evaluate_portfolio.bat` и укажите ваш GitHub username, затем запустите:

```cmd
evaluate_portfolio.bat
```

#### 5. Сравнение с предыдущим запуском / Compare with previous run

```bash
python enhanced_evaluate_portfolio.py --path ./repos --compare portfolio_evaluation_local.json
```

#### 6. Калибровка score против golden set / Calibrate score against golden set

```bash
python calibrate_scoring_model.py --labels calibration/golden_set_template.csv --results portfolio_evaluation_local.json
```

#### 7. Подготовка golden set и тюнинг весов / Prepare golden set and tune weights

```bash
python prepare_golden_set.py --results portfolio_evaluation_ergon73.json --output calibration/golden_set_ergon73_v1.csv --sample-size 36 --autofill
python tune_scoring_config.py --labels calibration/golden_set_ergon73_v1.csv --results portfolio_evaluation_ergon73.json --output calibration/scoring_config_patch_ergon73_v1.json
```

#### 8. Анализ соответствия вакансии / Job fit analysis

```bash
python job_fit_analysis.py --evaluation-json portfolio_evaluation_ergon73.json --jd-file job_description.txt --output-prefix job_fit_ergon73
```

#### 9. Benchmark по набору вакансий / Multi-JD benchmark

```bash
python run_job_fit_benchmark.py --evaluation-json portfolio_evaluation_ergon73.json --jd-dir calibration/jd_benchmark --output-prefix calibration/job_fit_benchmark_ergon73
```

#### 10. Проверка JSON-контракта / Validate JSON contract

```bash
python generate_portfolio_schema.py
python validate_evaluation_contract.py --input portfolio_evaluation_local.json
```

#### 11. Персональная перекалибровка под свое видение / Personal recalibration profile

```bash
# 1) Создать профиль и заготовку разметки
python recalibrate_profile.py --profile recruiter_view --results portfolio_evaluation_local.json --prepare-golden-set --autofill --only-prepare

# 2) Отредактировать expert_score в calibration/profiles/recruiter_view/labels/golden_set.csv

# 3) (Опционально) разделить labels по стекам
python recalibrate_profile.py --profile recruiter_view --results portfolio_evaluation_local.json --split-by-stack --include-additional-stacks --only-split

# 4) Запустить stack-aware калибровку профиля (без изменения baseline-конфига)
python recalibrate_profile.py --profile recruiter_view --results portfolio_evaluation_local.json --stack-profile python_backend

# 5) (Опционально) активировать профиль как рабочий scoring_config
python recalibrate_profile.py --profile recruiter_view --results portfolio_evaluation_local.json --stack-profile python_backend --apply-to portfolio_fit/scoring_config.json
```

### Параметры командной строки / Command Line Options

```
-g, --github USERNAME    GitHub username для оценки
-o, --output DIR         Директория для клонирования репозиториев
-p, --path DIR           Путь к локальной папке с репозиториями
-t, --token TOKEN        GitHub API token (для увеличения лимита запросов)
-m, --max-repos N        Максимум репозиториев (0 = все)
--keep-repos             Не удалять клонированные репозитории
--recursive              Рекурсивный поиск репозиториев во вложенных папках
--compare JSON_FILE      Сравнение с предыдущим JSON-результатом
--stack-profile PROFILE  Профиль стека (auto/python_backend/python_fullstack_react/python_django_templates/node_frontend/mixed_unknown)
```

## 📄 Результаты / Results

После выполнения создаются два файла:

1. **`portfolio_evaluation_{username}.json`** - JSON с данными для программной обработки
2. **`portfolio_report_{username}.txt`** - Текстовый отчет с полным отсортированным списком всех репозиториев

При использовании `--compare` дополнительно создаются:

3. **`portfolio_compare_{username}.json`** - Структурированный before/after diff по репозиториям
4. **`portfolio_compare_{username}.txt`** - Человекочитаемый compare-отчет

В JSON-результате дополнительно доступны:
- `data_coverage_percent` — доля критериев, по которым есть данные
- `criteria_meta` — `status/method/confidence/note` по каждому критерию
- `blocks_meta` — покрытие и детальная агрегация по каждому блоку
- `criteria_explainability` — структурированное объяснение “почему этот балл”
- `recommendations` — actionable рекомендации по слабым критериям
- `quick_fixes` — быстрые улучшения с оценкой impact/effort
- `data_quality_status` / `data_quality_warnings` — красные флаги по недостаточности evidence
- Формальный контракт доступен в `schemas/portfolio_evaluation.schema.json`
- Персональные профили перекалибровки хранятся в `calibration/profiles/<profile>/`
- Для profile recalibration доступны `--stack-profile`, strict mode и split labels по стекам

## 📚 Документация / Documentation

- [ENHANCED_USAGE_GUIDE.md](ENHANCED_USAGE_GUIDE.md) - Подробное руководство по использованию
- [CLONE_QUICK_START.md](CLONE_QUICK_START.md) - Быстрый старт для клонирования репозиториев
- [schemas/README.md](schemas/README.md) - JSON schema и команды проверки контракта
- [docs/adr/0001-evidence-classification.md](docs/adr/0001-evidence-classification.md) - ADR по `measured/heuristic/unknown`
- [docs/quality/definition-of-done.md](docs/quality/definition-of-done.md) - Общий DoD
- [docs/baselines/v2.3-baseline-freeze.md](docs/baselines/v2.3-baseline-freeze.md) - Freeze baseline v2.3
- [docs/migration-v2_3-to-v3_0.md](docs/migration-v2_3-to-v3_0.md) - Миграционная заметка v2.3 -> v3.0
- [docs/migration-v3_0-to-v3_1.md](docs/migration-v3_0-to-v3_1.md) - Миграционная заметка v3.0 -> v3.1
- [docs/recalibration-profiles.md](docs/recalibration-profiles.md) - Профили перекалибровки для разных пользователей
- [docs/calibration-applicability-limits.md](docs/calibration-applicability-limits.md) - Ограничения применимости калибровки
- [docs/releases/v3.0.0-release-notes.md](docs/releases/v3.0.0-release-notes.md) - Черновик release notes v3.0.0
- [docs/releases/v3.0.0-publish-checklist.md](docs/releases/v3.0.0-publish-checklist.md) - Чеклист публикации v3.0.0
- [docs/releases/v3.1.0-release-notes.md](docs/releases/v3.1.0-release-notes.md) - Черновик release notes v3.1.0
- [docs/releases/v3.1.0-publish-checklist.md](docs/releases/v3.1.0-publish-checklist.md) - Чеклист публикации v3.1.0
- [CHANGELOG.md](CHANGELOG.md) - Журнал изменений

## ✅ Проверка / Validation

```bash
ruff check .
black --check .
mypy
python -m py_compile enhanced_evaluate_portfolio.py clone_all_repos.py calibrate_scoring_model.py prepare_golden_set.py tune_scoring_config.py job_fit_analysis.py run_job_fit_benchmark.py generate_portfolio_schema.py validate_evaluation_contract.py recalibrate_profile.py portfolio_fit/scoring.py portfolio_fit/discovery.py portfolio_fit/github_fetcher.py portfolio_fit/reporting.py portfolio_fit/cli.py portfolio_fit/calibration.py portfolio_fit/tuning.py portfolio_fit/job_fit.py portfolio_fit/job_fit_benchmark.py portfolio_fit/schema_contract.py portfolio_fit/recalibration.py
python -m unittest discover -s tests -v
python validate_evaluation_contract.py --input portfolio_evaluation_local.json
python recalibrate_profile.py --profile sanity_check --results portfolio_evaluation_local.json --prepare-golden-set --autofill --only-prepare
```

## 🔧 Дополнительные скрипты / Additional Scripts

- `clone_all_repos.py` - Скрипт для клонирования Python-репозиториев пользователя
- `calibrate_scoring_model.py` - Калибровка модели на экспертно размеченном golden set
- `prepare_golden_set.py` - Формирование stratified golden set из evaluation JSON
- `tune_scoring_config.py` - Построение предложений по весам критериев из expert labels
- `job_fit_analysis.py` - Оценка соответствия портфолио конкретной вакансии (JD)
- `run_job_fit_benchmark.py` - Batch-оценка Job Fit по набору JD
- `generate_portfolio_schema.py` - Генерация формальной JSON schema результата
- `validate_evaluation_contract.py` - Проверка JSON-результата на обязательный контракт
- `recalibrate_profile.py` - Профильная перекалибровка под индивидуальную экспертную оценку
- `evaluate_portfolio.bat` - Batch-файл для Windows

## 🧱 Архитектура / Architecture

- `portfolio_fit/scoring.py` — scoring engine и критерии
- `portfolio_fit/discovery.py` — поиск репозиториев и локальная оценка
- `portfolio_fit/github_fetcher.py` — GitHub API + cloning
- `portfolio_fit/reporting.py` — JSON/TXT report rendering
- `portfolio_fit/cli.py` — CLI orchestration
- `portfolio_fit/calibration.py` — калибровка и метрики качества модели
- `portfolio_fit/tuning.py` — аналитика корреляций критериев и рекомендации по весам
- `portfolio_fit/job_fit.py` — парсинг JD, skill extraction, fit-score и roadmap
- `portfolio_fit/job_fit_benchmark.py` — benchmark-агрегация по множеству JD
- `portfolio_fit/schema_contract.py` — формальный контракт результата + runtime-валидация
- `portfolio_fit/recalibration.py` — механизм персональной перекалибровки через профили
- `portfolio_fit/scoring_config.json` — внешняя настройка порогов/весов
- `enhanced_evaluate_portfolio.py` — совместимый entrypoint (wrapper)
- `calibration/golden_set_template.csv` — шаблон экспертной разметки для Sprint 7
- `calibration/jd_benchmark/*.txt` — шаблоны JD для Sprint 8 benchmark

## 🗺️ Roadmap / Дорожная карта

- [ ] 🔍 Веб-приложение с интерфейсом для анализа
- [ ] 💼 Анализ соответствия вакансиям
- [ ] 🤖 Умный отбор релевантных проектов
- [ ] 🎯 План доработок проектов до showcase-уровня
- [ ] 📊 Анализ компетенций из GitHub и резюме
- [ ] 🔗 Рекомендации по недостающим технологиям и проектам

## 📝 Лицензия / License

[MIT](LICENSE)

## 🤝 Вклад / Contributing

Приветствуются pull requests и issues!

Pull requests and issues are welcome!

---

**Текущая версия**: v3.1 - Multi-stack CLI инструмент для оценки портфолио  
**Следующий этап**: Веб-приложение с полным функционалом анализа соответствия вакансиям
