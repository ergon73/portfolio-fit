# 🔍 Enhanced Portfolio Evaluation Script

Расширенный скрипт для оценки качества портфолио GitHub-репозиториев на Python.

Enhanced script for evaluating quality of GitHub portfolio repositories in Python.

## 📊 Описание / Description

Этот скрипт оценивает ваши Python-репозитории по **18 критериям** и выставляет оценку по **50-балльной шкале** (Production Readiness Score v2.2).

This script evaluates your Python repositories against **18 criteria** and scores them on a **50-point scale** (Production Readiness Score v2.2).

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

## 🚀 Быстрый старт / Quick Start

### Требования / Requirements

- Python 3.7+
- Git (для клонирования репозиториев)

### Установка / Installation

```bash
git clone <repository-url>
cd <repository-name>
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

#### 4. Windows (batch файл) / Windows (batch file)

Отредактируйте `evaluate_portfolio.bat` и укажите ваш GitHub username, затем запустите:

```cmd
evaluate_portfolio.bat
```

### Параметры командной строки / Command Line Options

```
-g, --github USERNAME    GitHub username для оценки
-o, --output DIR         Директория для клонирования репозиториев
-p, --path DIR           Путь к локальной папке с репозиториями
-t, --token TOKEN        GitHub API token (для увеличения лимита запросов)
-m, --max-repos N        Максимум репозиториев (0 = все)
--keep-repos             Не удалять клонированные репозитории
```

## 📄 Результаты / Results

После выполнения создаются два файла:

1. **`portfolio_evaluation_{username}.json`** - JSON с данными для программной обработки
2. **`portfolio_report_{username}.txt`** - Текстовый отчет с полным отсортированным списком всех репозиториев

## 📚 Документация / Documentation

- [ENHANCED_USAGE_GUIDE.md](ENHANCED_USAGE_GUIDE.md) - Подробное руководство по использованию
- [CLONE_QUICK_START.md](CLONE_QUICK_START.md) - Быстрый старт для клонирования репозиториев

## 🔧 Дополнительные скрипты / Additional Scripts

- `clone_all_repos.py` - Скрипт для клонирования всех репозиториев пользователя
- `evaluate_portfolio.bat` - Batch-файл для Windows

## 📝 Лицензия / License

[Укажите вашу лицензию / Specify your license]

## 🤝 Вклад / Contributing

Приветствуются pull requests и issues!

Pull requests and issues are welcome!
