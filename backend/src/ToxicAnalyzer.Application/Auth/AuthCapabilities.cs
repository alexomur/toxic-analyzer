namespace ToxicAnalyzer.Application.Auth;

public static class AuthCapabilities
{
    public const string AnalysisRead = "analysis.read";
    public const string AnalysisVote = "analysis.vote";
    public const string ModelReload = "model.reload";
    public const string ModelRetrain = "model.retrain";
    public const string DatasetUpdate = "dataset.update";
    public const string AdminUsersManage = "admin.users.manage";

    public static readonly IReadOnlyList<string> All =
    [
        AnalysisRead,
        AnalysisVote,
        ModelReload,
        ModelRetrain,
        DatasetUpdate,
        AdminUsersManage
    ];
}
