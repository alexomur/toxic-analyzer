namespace ToxicAnalyzer.Application.Abstractions;

public sealed record CurrentActor(
    bool IsAuthenticated,
    ActorType ActorType,
    string SubjectId,
    string? ClientId,
    string? TenantId,
    string? SessionId,
    string AuthenticationScheme,
    IReadOnlyList<string>? Roles = null,
    IReadOnlyList<string>? Scopes = null,
    IReadOnlyList<string>? Capabilities = null)
{
    public string SourceKind => ActorType switch
    {
        ActorType.Anonymous => "anonymous",
        ActorType.User => "user",
        ActorType.Admin => "admin",
        ActorType.Service => "service",
        _ => "unknown"
    };

    public string ActorKey => $"{ActorType.ToString().ToLowerInvariant()}:{SubjectId}";

    public bool HasCapability(string capability)
    {
        return Capabilities?.Contains(capability, StringComparer.Ordinal) == true;
    }

    public static CurrentActor Anonymous(string subjectId, string? tenantId = null)
    {
        return new CurrentActor(
            false,
            ActorType.Anonymous,
            subjectId,
            null,
            tenantId,
            null,
            "anonymous",
            [],
            []);
    }
}
