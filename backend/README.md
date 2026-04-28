# Backend

`backend/` содержит продуктовый backend для Toxic Analyzer.

## Текущий статус

- Технологический стек: ASP.NET Core Web API на `net10.0`
- Solution: `ToxicAnalyzer.sln`
- Основной проект: `ToxicAnalyzer.Api`
- Сейчас в проекте находится стартовый каркас API без доменной логики
- MVP API-обязательства backend: `backend/API_CONTRACTS.md`

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

## MVP API notes

- Текущий backend MVP работает без пользовательской auth.
- Для production-доступа со стороны Discord bot и других внешних клиентов стоит добавить простой API key слой на уровне `backend`.
- OpenAPI-описание для локальной разработки доступно в development environment по пути `/openapi/v1.json`.
