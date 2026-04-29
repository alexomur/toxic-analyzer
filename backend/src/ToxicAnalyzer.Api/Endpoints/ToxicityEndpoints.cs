using ToxicAnalyzer.Api.Contracts.Toxicity;
using ToxicAnalyzer.Application.Toxicity.AnalyzeBatch;
using ToxicAnalyzer.Application.Toxicity.AnalyzeText;

namespace ToxicAnalyzer.Api.Endpoints;

public static class ToxicityEndpoints
{
    public static IEndpointRouteBuilder MapToxicityEndpoints(this IEndpointRouteBuilder endpoints)
    {
        var group = endpoints
            .MapGroup("/api/v1/toxicity")
            .WithTags("Toxicity");

        group.MapPost("/analyze", AnalyzeAsync)
            .WithName("AnalyzeText")
            .WithSummary("Analyze a single text for toxicity.")
            .Produces<AnalyzeTextResponse>(StatusCodes.Status200OK)
            .ProducesProblem(StatusCodes.Status400BadRequest)
            .ProducesProblem(StatusCodes.Status503ServiceUnavailable)
            .ProducesProblem(StatusCodes.Status504GatewayTimeout)
            .ProducesProblem(StatusCodes.Status500InternalServerError);

        group.MapPost("/analyze-batch", AnalyzeBatchAsync)
            .WithName("AnalyzeTextBatch")
            .WithSummary("Analyze a batch of texts for toxicity.")
            .Produces<AnalyzeBatchResponse>(StatusCodes.Status200OK)
            .ProducesProblem(StatusCodes.Status400BadRequest)
            .ProducesProblem(StatusCodes.Status503ServiceUnavailable)
            .ProducesProblem(StatusCodes.Status504GatewayTimeout)
            .ProducesProblem(StatusCodes.Status500InternalServerError);

        return endpoints;
    }

    private static async Task<IResult> AnalyzeAsync(
        AnalyzeTextRequest request,
        AnalyzeTextHandler handler,
        CancellationToken cancellationToken)
    {
        var result = await handler.HandleAsync(
            new AnalyzeTextCommand(request.Text, request.ReportLevel),
            cancellationToken);
        return Results.Ok(result.ToResponse());
    }

    private static async Task<IResult> AnalyzeBatchAsync(
        AnalyzeBatchRequest request,
        AnalyzeBatchHandler handler,
        CancellationToken cancellationToken)
    {
        var command = new AnalyzeBatchCommand(
            request.Items.Select(item => new AnalyzeBatchItem(item.Text, item.ClientItemId)).ToArray());

        var result = await handler.HandleAsync(command, cancellationToken);
        return Results.Ok(result.ToResponse());
    }
}
