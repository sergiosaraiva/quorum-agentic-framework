using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace Infrastructure.Migrations
{
    /// <summary>
    /// VS-005 (OD-004, TQ-003): order statuses open/paid/cancelled become the BC-001 states
    /// draft/placed/paid/shipped/closed. Mapping (TQ-010): open -> draft, paid -> paid. The code vocabulary has no `cancelled`
    /// state yet (OD-013, BQ-009), so the migration refuses to run while any cancelled row exists rather than
    /// invent a state or lose the information. The code never wrote 'cancelled', so none is expected.
    /// Down is lossy by necessity: the old vocabulary has fewer states (placed -> open, shipped and closed -> paid).
    /// </summary>
    public partial class AlignOrderStatusesToBc001 : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            // The old constraint rejects the new values and the new one rejects the old, so: drop, map, add.
            migrationBuilder.DropCheckConstraint(
                name: "ck_order_status",
                table: "order");

            migrationBuilder.Sql("""
                DO $$
                BEGIN
                    IF EXISTS (SELECT 1 FROM "order" WHERE status = 'cancelled') THEN
                        RAISE EXCEPTION 'VS-005: % order row(s) have status cancelled, which the code vocabulary has no state for yet (OD-013, BQ-009). Resolve them before migrating.',
                            (SELECT count(*) FROM "order" WHERE status = 'cancelled');
                    END IF;
                END
                $$;
                """);

            migrationBuilder.Sql("""UPDATE "order" SET status = 'draft' WHERE status = 'open';""");

            migrationBuilder.AddCheckConstraint(
                name: "ck_order_status",
                table: "order",
                sql: "status in ('draft','placed','paid','shipped','closed')");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropCheckConstraint(
                name: "ck_order_status",
                table: "order");

            migrationBuilder.Sql("""UPDATE "order" SET status = 'open' WHERE status IN ('draft','placed');""");
            migrationBuilder.Sql("""UPDATE "order" SET status = 'paid' WHERE status IN ('shipped','closed');""");

            migrationBuilder.AddCheckConstraint(
                name: "ck_order_status",
                table: "order",
                sql: "status in ('open','paid','cancelled')");
        }
    }
}
