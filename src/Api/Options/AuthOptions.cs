using System.ComponentModel.DataAnnotations;

namespace Api.Options;

/// <summary>JWT bearer settings. Values come from configuration (environment or user-secrets), never from source.</summary>
public sealed class AuthOptions
{
    public const string SectionName = "Auth";

    /// <summary>OIDC issuer URL, for example https://idp.example.com/realms/{{REALM}}.</summary>
    [Required]
    public string Authority { get; init; } = "";

    /// <summary>Expected token audience.</summary>
    [Required]
    public string Audience { get; init; } = "";
}
