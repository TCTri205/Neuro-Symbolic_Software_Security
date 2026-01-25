import click
from src.core.config import settings


@click.group()
def cli():
    """NSSS - Neuro-Symbolic Software Security CLI"""
    pass


@cli.command()
@click.argument("target_path", type=click.Path(exists=True))
@click.option(
    "--mode",
    type=click.Choice(["ci", "audit", "baseline"], case_sensitive=False),
    default="audit",
    help="Operation mode.",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "text"], case_sensitive=False),
    default="text",
    help="Output format.",
)
@click.option(
    "--report-type",
    "report_types",
    multiple=True,
    type=click.Choice(["markdown", "sarif", "ir"], case_sensitive=False),
    help="Report types to generate (repeatable).",
)
@click.option(
    "--emit-ir",
    is_flag=True,
    default=False,
    help="Include parsed IR in output JSON.",
)
@click.option("--report-dir", default=".", help="Directory to save reports.")
def scan(target_path, mode, output_format, report_types, emit_ir, report_dir):
    """
    Scan a target directory or file.
    """
    click.echo("Initializing NSSS Scan...")
    click.echo(f"Target: {target_path}")
    click.echo(f"Mode: {mode}")
    click.echo(f"Format: {output_format}")
    click.echo(f"Loaded Configuration: HOST={settings.HOST}, DEBUG={settings.DEBUG}")

    # Invoking Pipeline
    from src.core.pipeline.orchestrator import AnalysisOrchestrator
    from src.report import ReportManager
    import os
    import json

    click.echo("Running analysis pipeline...")
    orchestrator = AnalysisOrchestrator(enable_ir=emit_ir)
    results = {}

    if os.path.isfile(target_path):
        res = orchestrator.analyze_file(target_path)
        results[target_path] = res.to_dict()
    elif os.path.isdir(target_path):
        for root, dirs, files in os.walk(target_path):
            for file in files:
                if file.endswith(".py"):
                    full_path = os.path.join(root, file)
                    res = orchestrator.analyze_file(full_path)
                    results[full_path] = res.to_dict()

    # Generate reports
    click.echo(f"Generating reports in {report_dir}...")

    report_types_list = [report_type.lower() for report_type in report_types]
    report_manager = ReportManager(report_dir, report_types=report_types_list or None)
    generated_reports = report_manager.generate_all(results)

    for report_path in generated_reports:
        click.echo(f"  - {report_path}")

    click.echo(f"Reports generated.")

    if output_format == "json":
        click.echo(json.dumps(results, indent=2))
    else:
        # Text summary
        for file, res in results.items():
            click.echo(f"\nFile: {file}")
            if "error" in res:
                click.echo(f"  Error: {res['error']}")
            else:
                stats = res.get("stats", {})
                click.echo(
                    f"  CFG: {stats.get('block_count')} blocks, {stats.get('edge_count')} edges"
                )
                click.echo(f"  Vars: {stats.get('var_count')} variables tracked")

                # Show first few phis as example
                has_phis = False
                for b in res["structure"]["blocks"]:
                    if b["phis"]:
                        click.echo(f"  Block {b['id']} Phis: {b['phis']}")
                        has_phis = True
                if not has_phis:
                    click.echo("  No Phi nodes found.")

    click.echo("\nScan complete.")


if __name__ == "__main__":
    cli()
