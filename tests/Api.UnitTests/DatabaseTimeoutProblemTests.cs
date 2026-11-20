using Api.Common;
using Microsoft.AspNetCore.Http;
using Microsoft.EntityFrameworkCore;
using Npgsql;

namespace Api.UnitTests;

/// <summary>TQ-015 (OD-025): only a database timeout maps to 503; every other exception keeps its status.</summary>
public class DatabaseTimeoutProblemTests
{
    [Fact]
    public void IsTimeout_TimeoutException_IsTrue() =>
        Assert.True(DatabaseTimeoutProblem.IsTimeout(new TimeoutException()));

    [Fact]
    public void IsTimeout_NpgsqlExceptionWithTimeoutCause_IsTrue() =>
        Assert.True(DatabaseTimeoutProblem.IsTimeout(new NpgsqlException("read failed", new TimeoutException())));

    [Fact]
    public void IsTimeout_TimeoutWrappedByEfUpdateException_IsTrue() =>
        Assert.True(DatabaseTimeoutProblem.IsTimeout(
            new DbUpdateException("save failed", new NpgsqlException("x", new TimeoutException()))));

    [Fact]
    public void IsTimeout_NpgsqlExceptionWithoutTimeoutCause_IsFalse() =>
        Assert.False(DatabaseTimeoutProblem.IsTimeout(new NpgsqlException("connection refused", new InvalidOperationException())));

    [Theory]
    [MemberData(nameof(NonTimeouts))]
    public void IsTimeout_OtherExceptions_AreFalse(Exception exception) =>
        Assert.False(DatabaseTimeoutProblem.IsTimeout(exception));

    public static TheoryData<Exception> NonTimeouts() => new()
    {
        new InvalidOperationException("boom"),
        new OperationCanceledException(),
        new DbUpdateException("conflict", new InvalidOperationException()),
        new BadHttpRequestException("bad"),
    };

    [Fact]
    public void IsTimeout_Null_IsFalse() =>
        Assert.False(DatabaseTimeoutProblem.IsTimeout(null));

    [Fact]
    public void IsTimeout_TimeoutBeyondChainBound_IsFalse()
    {
        Exception chain = new TimeoutException();
        for (var i = 0; i < 20; i++)
        {
            chain = new InvalidOperationException("wrapper", chain);
        }

        Assert.False(DatabaseTimeoutProblem.IsTimeout(chain));
    }

    [Fact]
    public void SelectStatusCode_Timeout_Is503() =>
        Assert.Equal(503, DatabaseTimeoutProblem.SelectStatusCode(new NpgsqlException("x", new TimeoutException())));

    [Fact]
    public void SelectStatusCode_BadHttpRequest_KeepsItsOwnStatus()
    {
        Assert.Equal(400, DatabaseTimeoutProblem.SelectStatusCode(new BadHttpRequestException("x")));
        Assert.Equal(413, DatabaseTimeoutProblem.SelectStatusCode(new BadHttpRequestException("x", 413)));
    }

    [Fact]
    public void SelectStatusCode_AnythingElse_Is500() =>
        Assert.Equal(500, DatabaseTimeoutProblem.SelectStatusCode(new InvalidOperationException()));
}
