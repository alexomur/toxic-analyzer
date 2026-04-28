# Backend

`backend/` содержит продуктовый backend для Toxic Analyzer.

## Текущий статус

- Технологический стек: ASP.NET Core Web API на `net8.0`
- Solution: `ToxicAnalyzer.sln`
- Основной проект: `ToxicAnalyzer.Api`
- Сейчас в проекте находится стартовый каркас API без доменной логики

## Зона ответственности

- внешний HTTP API для будущего `frontend`
- оркестрация вызовов внутреннего `model`-сервиса
- авторизация, продуктовая логика и хранение продуктовых данных
- изоляция `frontend` от внутреннего устройства `model`

`backend` не должен дублировать обучение модели или хранение весов модели.

## Как запускать локально

Из каталога `backend/`:

```powershell
dotnet restore .\ToxicAnalyzer.sln
dotnet run --project .\ToxicAnalyzer.Api\ToxicAnalyzer.Api.csproj
```

По умолчанию Swagger доступен в development-окружении.

## Ближайший вектор работ

- заменить шаблонные endpoint'ы на доменные API-контракты
- подключить конфигурацию для вызовов `model`
- ввести явные application и infrastructure слои по мере появления реальных сценариев
