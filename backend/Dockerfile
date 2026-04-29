FROM mcr.microsoft.com/dotnet/sdk:10.0 AS build
WORKDIR /src

COPY ["src/ToxicAnalyzer.Api/ToxicAnalyzer.Api.csproj", "src/ToxicAnalyzer.Api/"]
COPY ["src/ToxicAnalyzer.Application/ToxicAnalyzer.Application.csproj", "src/ToxicAnalyzer.Application/"]
COPY ["src/ToxicAnalyzer.Domain/ToxicAnalyzer.Domain.csproj", "src/ToxicAnalyzer.Domain/"]
COPY ["src/ToxicAnalyzer.Infrastructure/ToxicAnalyzer.Infrastructure.csproj", "src/ToxicAnalyzer.Infrastructure/"]

RUN dotnet restore "src/ToxicAnalyzer.Api/ToxicAnalyzer.Api.csproj"

COPY src ./src

RUN dotnet publish "src/ToxicAnalyzer.Api/ToxicAnalyzer.Api.csproj" \
    -c Release \
    -o /app/publish \
    /p:UseAppHost=false

FROM mcr.microsoft.com/dotnet/aspnet:10.0 AS final
WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

ENV ASPNETCORE_URLS=http://+:8080

EXPOSE 8080

COPY --from=build /app/publish .

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=6 CMD ["curl", "--fail", "http://127.0.0.1:8080/health/ready"]

ENTRYPOINT ["dotnet", "ToxicAnalyzer.Api.dll"]
