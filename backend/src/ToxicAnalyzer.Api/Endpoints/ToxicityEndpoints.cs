using ToxicAnalyzer.Api.Contracts.Toxicity;
using ToxicAnalyzer.Application.Toxicity.AnalyzeBatch;
using ToxicAnalyzer.Application.Toxicity.AnalyzeText;
using ToxicAnalyzer.Application.Toxicity.GetRandomText;
using ToxicAnalyzer.Application.Toxicity.GetTextById;
using ToxicAnalyzer.Application.Toxicity.VoteText;

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

        group.MapGet("/texts/random", GetRandomTextAsync)
            .WithName("GetRandomAnalysisText")
            .WithSummary("Get a random text for anonymous toxicity voting.")
            .Produces<GetRandomTextResponse>(StatusCodes.Status200OK)
            .ProducesProblem(StatusCodes.Status404NotFound)
            .ProducesProblem(StatusCodes.Status500InternalServerError);

        group.MapGet("/texts/{textId:guid}", GetTextByIdAsync)
            .WithName("GetAnalysisTextById")
            .WithSummary("Get stored voting information for a text by id.")
            .Produces<GetTextByIdResponse>(StatusCodes.Status200OK)
            .ProducesProblem(StatusCodes.Status404NotFound)
            .ProducesProblem(StatusCodes.Status500InternalServerError);

        group.MapPost("/texts/{textId:guid}/vote", VoteTextAsync)
            .WithName("VoteAnalysisText")
            .WithSummary("Submit an anonymous toxicity vote for a stored text.")
            .Produces(StatusCodes.Status204NoContent)
            .ProducesProblem(StatusCodes.Status400BadRequest)
            .ProducesProblem(StatusCodes.Status404NotFound)
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

    private static async Task<IResult> GetRandomTextAsync(
        GetRandomTextHandler handler,
        CancellationToken cancellationToken)
    {
        var result = await handler.HandleAsync(new GetRandomTextCommand(), cancellationToken);
        return Results.Ok(result.ToResponse());
    }

    private static async Task<IResult> GetTextByIdAsync(
        Guid textId,
        GetTextByIdHandler handler,
        CancellationToken cancellationToken)
    {
        var result = await handler.HandleAsync(new GetTextByIdCommand(textId), cancellationToken);
        return Results.Ok(result.ToResponse());
    }

    private static async Task<IResult> VoteTextAsync(
        Guid textId,
        VoteTextRequest request,
        VoteTextHandler handler,
        CancellationToken cancellationToken)
    {
        await handler.HandleAsync(new VoteTextCommand(textId, request.Vote), cancellationToken);
        return Results.NoContent();
    }
}
