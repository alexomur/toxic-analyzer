using ToxicAnalyzer.Application.Abstractions;
using ToxicAnalyzer.Application.Common;

namespace ToxicAnalyzer.Application.Auth.Login;

public sealed class LoginUserHandler
{
    private readonly IAuthStore _authStore;
    private readonly IPasswordHasher _passwordHasher;
    private readonly ISessionTokenService _sessionTokenService;
    private readonly IClock _clock;
    private readonly AuthOptions _authOptions;

    public LoginUserHandler(
        IAuthStore authStore,
        IPasswordHasher passwordHasher,
        ISessionTokenService sessionTokenService,
        IClock clock,
        AuthOptions authOptions)
    {
        _authStore = authStore;
        _passwordHasher = passwordHasher;
        _sessionTokenService = sessionTokenService;
        _clock = clock;
        _authOptions = authOptions;
    }

    public async Task<BrowserSessionResult> HandleAsync(LoginUserCommand command, CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(command);

        if (string.IsNullOrWhiteSpace(command.Email) || string.IsNullOrWhiteSpace(command.Password))
        {
            throw new ValidationException(
                "Request validation failed.",
                [new ValidationError("request", "Email and password are required.")]);
        }

        var user = await _authStore.GetUserByEmailAsync(command.Email.Trim(), cancellationToken);
        if (user is null || !_passwordHasher.VerifyPassword(command.Password, user.PasswordHash))
        {
            throw new AuthenticationFailedException("Invalid email or password.");
        }

        var session = await CreateSessionAsync(user.Id, cancellationToken);
        return new BrowserSessionResult(user, session, [AuthCapabilities.AnalysisRead, AuthCapabilities.AnalysisVote]);
    }

    private async Task<SessionIssueResult> CreateSessionAsync(Guid userId, CancellationToken cancellationToken)
    {
        var sessionToken = _sessionTokenService.GenerateToken();
        var csrfToken = _sessionTokenService.GenerateToken();
        var expiresAt = _clock.UtcNow.Add(_authOptions.BrowserSessionLifetime);

        var persisted = await _authStore.CreateSessionAsync(
            userId,
            _sessionTokenService.ComputeHash(sessionToken),
            _sessionTokenService.ComputeHash(csrfToken),
            _clock.UtcNow,
            expiresAt,
            cancellationToken);

        return persisted with
        {
            SessionToken = sessionToken,
            CsrfToken = csrfToken
        };
    }
}
