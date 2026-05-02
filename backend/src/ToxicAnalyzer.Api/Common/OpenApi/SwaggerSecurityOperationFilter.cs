using Microsoft.AspNetCore.Authorization;
using Microsoft.OpenApi;
using Swashbuckle.AspNetCore.SwaggerGen;
using ToxicAnalyzer.Api.Common.Auth;

namespace ToxicAnalyzer.Api.Common.OpenApi;

public sealed class SwaggerSecurityOperationFilter : IOperationFilter
{
    public void Apply(OpenApiOperation operation, OperationFilterContext context)
    {
        var hasAllowAnonymous = context.ApiDescription.ActionDescriptor.EndpointMetadata.OfType<AllowAnonymousAttribute>().Any();
        var hasAuthorize = context.ApiDescription.ActionDescriptor.EndpointMetadata.OfType<AuthorizeAttribute>().Any();

        var isMutatingMethod =
            string.Equals(context.ApiDescription.HttpMethod, "POST", StringComparison.OrdinalIgnoreCase) ||
            string.Equals(context.ApiDescription.HttpMethod, "PUT", StringComparison.OrdinalIgnoreCase) ||
            string.Equals(context.ApiDescription.HttpMethod, "PATCH", StringComparison.OrdinalIgnoreCase) ||
            string.Equals(context.ApiDescription.HttpMethod, "DELETE", StringComparison.OrdinalIgnoreCase);

        if (!hasAllowAnonymous && hasAuthorize)
        {
            operation.Security ??= [];

            operation.Security.Add(new OpenApiSecurityRequirement
            {
                [
                    new OpenApiSecuritySchemeReference("Bearer", null, null)
                ] = []
            });

            operation.Security.Add(new OpenApiSecurityRequirement
            {
                [
                    new OpenApiSecuritySchemeReference("SessionCookie", null, null)
                ] = []
            });
        }

        if (!isMutatingMethod)
        {
            return;
        }

        operation.Parameters ??= [];

        if (operation.Parameters.All(parameter => !string.Equals(parameter.Name, AuthConstants.CsrfHeaderName, StringComparison.OrdinalIgnoreCase)))
        {
            operation.Parameters.Add(new OpenApiParameter
            {
                Name = AuthConstants.CsrfHeaderName,
                In = ParameterLocation.Header,
                Required = false,
                Description = "Required for browser session requests that change server state.",
                Schema = new OpenApiSchema
                {
                    Type = JsonSchemaType.String
                }
            });
        }
    }
}
