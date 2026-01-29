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
    "--baseline",
    "baseline_generate",
    is_flag=True,
    default=False,
    help="Generate baseline file from current findings.",
)
@click.option(
    "--baseline-only",
    is_flag=True,
    default=False,
    help="Suppress existing findings using baseline.",
)
@click.option(
    "--baseline-reset",
    is_flag=True,
    default=False,
    help="Regenerate baseline file (overwrite existing).",
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
    type=click.Choice(["markdown", "sarif", "ir", "graph"], case_sensitive=False),
    help="Report types to generate (repeatable).",
)
@click.option(
    "--emit-ir",
    is_flag=True,
    default=False,
    help="Include parsed IR in output JSON.",
)
@click.option(
    "--strip-docstrings",
    is_flag=True,
    default=False,
    help="Strip docstrings from IR.",
)
@click.option("--report-dir", default=".", help="Directory to save reports.")
def scan(
    target_path,
    mode,
    baseline_generate,
    baseline_only,
    baseline_reset,
    output_format,
    report_types,
    emit_ir,
    strip_docstrings,
    report_dir,
):
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
    from src.core.scan.baseline import BaselineEngine
    from src.report import ReportManager
    from src.report.graph import GraphTraceExporter
    import os
    import json

    click.echo("Running analysis pipeline...")
    baseline_enabled = baseline_only
    generate_baseline = (
        baseline_generate or baseline_reset or mode.lower() == "baseline"
    )
    baseline_engine = BaselineEngine() if generate_baseline else None

    if baseline_reset and baseline_engine:
        if os.path.exists(baseline_engine.storage_path):
            os.remove(baseline_engine.storage_path)

    orchestrator = AnalysisOrchestrator(
        enable_ir=emit_ir,
        enable_docstring_stripping=strip_docstrings,
        baseline_mode=baseline_enabled,
    )
    results = {}
    baseline_entries = []

    if os.path.isfile(target_path):
        res = orchestrator.analyze_file(target_path)
        results[target_path] = res.to_dict()
        if baseline_engine and res.cfg:
            with open(target_path, "r", encoding="utf-8") as f:
                source_lines = f.read().splitlines()
            findings = []
            for block in res.cfg._blocks.values():
                findings.extend(block.security_findings)

            if res.secrets:
                for s in res.secrets:
                    findings.append(
                        {
                            "check_id": f"secret.{s.type.replace(' ', '_').lower()}",
                            "message": f"Found {s.type}",
                            "line": s.line,
                            "column": 1,
                            "severity": "CRITICAL",
                        }
                    )

            baseline_entries.extend(
                baseline_engine.build_entries(findings, target_path, source_lines)
            )
    elif os.path.isdir(target_path):
        for root, dirs, files in os.walk(target_path):
            for file in files:
                if file.endswith(".py"):
                    full_path = os.path.join(root, file)
                    res = orchestrator.analyze_file(full_path)
                    results[full_path] = res.to_dict()
                    if baseline_engine and res.cfg:
                        with open(full_path, "r", encoding="utf-8") as f:
                            source_lines = f.read().splitlines()
                        findings = []
                        for block in res.cfg._blocks.values():
                            findings.extend(block.security_findings)

                        if res.secrets:
                            for s in res.secrets:
                                findings.append(
                                    {
                                        "check_id": f"secret.{s.type.replace(' ', '_').lower()}",
                                        "message": f"Found {s.type}",
                                        "line": s.line,
                                        "column": 1,
                                        "severity": "CRITICAL",
                                    }
                                )

                        baseline_entries.extend(
                            baseline_engine.build_entries(
                                findings, full_path, source_lines
                            )
                        )

    if baseline_engine:
        baseline_engine.save(baseline_entries)
        click.echo(f"Baseline saved: {baseline_engine.storage_path}")

    # Prepare metadata for reports
    metadata = {}
    debug_payload = {}
    if baseline_enabled:
        baseline_summary = orchestrator.baseline_summary()
        if baseline_summary:
            metadata["baseline"] = baseline_summary
            debug_payload["baseline"] = baseline_summary

    report_types_list = [report_type.lower() for report_type in report_types]
    include_graph = not report_types_list or "graph" in report_types_list
    if include_graph:
        debug_payload["graph"] = GraphTraceExporter.build_payload(results)

    if debug_payload:
        debug_path = os.path.join(report_dir, "nsss_debug.json")
        if not os.path.exists(report_dir):
            os.makedirs(report_dir)
        with open(debug_path, "w", encoding="utf-8") as f:
            json.dump(debug_payload, f, indent=2)
        click.echo(f"Debug output: {debug_path}")

    # Generate reports
    click.echo(f"Generating reports in {report_dir}...")

    report_manager = ReportManager(report_dir, report_types=report_types_list or None)
    generated_reports = report_manager.generate_all(results, metadata=metadata)

    for report_path in generated_reports:
        click.echo(f"  - {report_path}")

    click.echo("Reports generated.")

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
