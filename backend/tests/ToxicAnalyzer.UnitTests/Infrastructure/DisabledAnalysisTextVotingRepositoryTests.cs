using ToxicAnalyzer.Application.Abstractions;
using ToxicAnalyzer.Application.Common;
using ToxicAnalyzer.Infrastructure.AnalysisCapture;

namespace ToxicAnalyzer.UnitTests.Infrastructure;

public sealed class DisabledAnalysisTextVotingRepositoryTests
{
    private static readonly CurrentActor TestActor = CurrentActor.Anonymous("anonymous-test-actor");

    [Fact]
    public async Task GetRandomAsync_ThrowsFeatureDisabledException()
    {
        var repository = new DisabledAnalysisTextVotingRepository();

        var exception = await Assert.ThrowsAsync<FeatureDisabledException>(() =>
            repository.GetRandomAsync(CancellationToken.None));

        Assert.Equal("Analysis text voting is unavailable because AnalysisCapture is disabled.", exception.Message);
    }

    [Fact]
    public async Task GetByIdAsync_ThrowsFeatureDisabledException()
    {
        var repository = new DisabledAnalysisTextVotingRepository();

        var exception = await Assert.ThrowsAsync<FeatureDisabledException>(() =>
            repository.GetByIdAsync(Guid.NewGuid(), CancellationToken.None));

        Assert.Equal("Analysis text voting is unavailable because AnalysisCapture is disabled.", exception.Message);
    }

    [Fact]
    public async Task RegisterVoteAsync_ThrowsFeatureDisabledException()
    {
        var repository = new DisabledAnalysisTextVotingRepository();

        var exception = await Assert.ThrowsAsync<FeatureDisabledException>(() =>
            repository.RegisterVoteAsync(Guid.NewGuid(), AnalysisTextVoteKind.Toxic, TestActor, CancellationToken.None));

        Assert.Equal("Analysis text voting is unavailable because AnalysisCapture is disabled.", exception.Message);
    }
}
