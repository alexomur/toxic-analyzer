using ToxicAnalyzer.Application.Abstractions;
using ToxicAnalyzer.Application.Common;

namespace ToxicAnalyzer.Application.Auth.Register;

public sealed class RegisterUserHandler
{
    private readonly IAuthStore _authStore;
    private readonly IPasswordHasher _passwordHasher;
    private readonly ISessionTokenService _sessionTokenService;
    private readonly IClock _clock;
    private readonly AuthOptions _authOptions;

    public RegisterUserHandler(
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

    public async Task<BrowserSessionResult> HandleAsync(RegisterUserCommand command, CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(command);

        var email = command.Email.Trim();
        var username = string.IsNullOrWhiteSpace(command.Username) ? null : command.Username.Trim();

        var errors = new List<ValidationError>();
        if (string.IsNullOrWhiteSpace(email))
        {
            errors.Add(new ValidationError("email", "Email is required."));
        }

        if (string.IsNullOrWhiteSpace(command.Password) || command.Password.Length < 8)
        {
            errors.Add(new ValidationError("password", "Password must contain at least 8 characters."));
        }

        if (errors.Count > 0)
        {
            throw new ValidationException("Request validation failed.", errors);
        }

        var existingUser = await _authStore.GetUserByEmailAsync(email, cancellationToken);
        if (existingUser is not null)
        {
            throw new ConflictException("A user with the same email already exists.");
        }

        var user = await _authStore.CreateUserAsync(
            email,
            username,
            _passwordHasher.HashPassword(command.Password),
            role: "member",
            cancellationToken);

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
