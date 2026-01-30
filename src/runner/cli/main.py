import click
import datetime
import os
import shutil

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
    type=click.Choice(
        ["markdown", "sarif", "ir", "graph", "debug"], case_sensitive=False
    ),
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
@click.option(
    "--diff",
    is_flag=True,
    default=False,
    help="Run incrementally on changed files and dependencies only.",
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
    diff,
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
    from src.core.scan.diff import DiffScanner
    from src.report import ReportManager
    from src.report.graph import GraphTraceExporter
    import os
    import json

    impacted_files = None
    if diff:
        click.echo("Running in Diff Mode...")
        # Assume project root is current working directory for now
        project_root = os.getcwd()
        diff_scanner = DiffScanner(project_root=project_root)
        changed = diff_scanner.get_changed_files()
        impacted_files = diff_scanner.compute_impacted_files(changed)
        click.echo(
            f"Diff Analysis: {len(changed)} changed, {len(impacted_files)} impacted."
        )
        if not impacted_files:
            click.echo("No files impacted. Exiting.")
            return

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
        abs_target = os.path.abspath(target_path)
        if impacted_files is not None and abs_target not in impacted_files:
            click.echo(f"Skipping {target_path} (not in impacted set)")
        else:
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
                    abs_path = os.path.abspath(full_path)

                    if impacted_files is not None and abs_path not in impacted_files:
                        continue

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


@cli.group()
def ops() -> None:
    """Operational maintenance utilities."""
    pass


@ops.command("clear-cache")
@click.option(
    "--llm-cache/--no-llm-cache",
    default=True,
    help="Clear the LLM response cache.",
)
@click.option(
    "--graph-cache/--no-graph-cache",
    default=True,
    help="Clear the IR graph cache for the project.",
)
@click.option(
    "--project-root",
    default=".",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    help="Project root used for graph cache lookup.",
)
def clear_cache(llm_cache: bool, graph_cache: bool, project_root: str) -> None:
    """Clear persistence caches for LLM and IR graphs."""
    if not llm_cache and not graph_cache:
        click.echo("No cache targets selected.")
        return

    if llm_cache:
        from src.core.ai.cache_store import LLMCacheStore

        store = LLMCacheStore.get_instance()
        store.clear()
        click.echo(f"Cleared LLM cache: {os.path.abspath(store.storage_path)}")

    if graph_cache:
        from src.core.persistence.graph_serializer import build_cache_dir

        root = os.path.abspath(project_root)
        graph_cache_dir = build_cache_dir(root)
        if os.path.exists(graph_cache_dir):
            shutil.rmtree(graph_cache_dir)
            click.echo(f"Removed graph cache directory: {graph_cache_dir}")
        else:
            click.echo(f"Graph cache not found: {graph_cache_dir}")


@ops.command("graph-export")
@click.option(
    "--project-root",
    default=None,
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    help="Project root used for graph cache lookup.",
)
@click.option(
    "--output",
    default="graph_export.jsonl",
    type=click.Path(dir_okay=False),
    help="Output path for exported graph cache.",
)
def graph_export(project_root: str, output: str) -> None:
    """Export the persisted IR graph cache to a file."""
    from src.core.persistence.graph_serializer import JsonlGraphSerializer
    from src.core.persistence import get_graph_persistence_service

    root = os.path.abspath(project_root or os.getcwd())
    persistence = get_graph_persistence_service(root)
    loaded = persistence.load_project_graph(root, strict=True)
    if not loaded:
        raise click.ClickException("Graph cache not found or stale")

    graph, meta = loaded
    serializer = JsonlGraphSerializer()
    output_path = os.path.abspath(output)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    serializer.save(graph, output_path, metadata=meta)
    click.echo(f"Exported graph cache to: {output_path}")


@ops.command("graph-import")
@click.option(
    "--project-root",
    default=None,
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    help="Project root used for graph cache lookup.",
)
@click.option(
    "--input",
    "input_path",
    required=True,
    type=click.Path(exists=True, dir_okay=False),
    help="Input graph cache file to import.",
)
def graph_import(project_root: str, input_path: str) -> None:
    """Import a persisted IR graph cache file into this project."""
    from src.core.persistence.graph_serializer import (
        JsonlGraphSerializer,
        build_cache_dir,
    )
    from src.core.persistence import get_graph_persistence_service

    root = os.path.abspath(project_root or os.getcwd())
    cache_dir = build_cache_dir(root)
    if os.path.exists(cache_dir):
        shutil.rmtree(cache_dir)
    serializer = JsonlGraphSerializer()
    graph, _meta = serializer.load(os.path.abspath(input_path))

    persistence = get_graph_persistence_service(root)
    saved_count = persistence.save_project_graph(graph, project_root=root)
    click.echo(f"Imported graph cache entries: {saved_count}")


@ops.command("health")
@click.option(
    "--project-root",
    default=".",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    help="Project root used for graph cache lookup.",
)
def health(project_root: str) -> None:
    """Run a basic health check of local NSSS state."""
    from src.core.ai.cache_store import LLMCacheStore
    from src.core.persistence.graph_serializer import build_manifest_path

    click.echo("NSSS Ops Health Check")
    root = os.path.abspath(project_root)
    click.echo(f"Project root: {root}")

    llm_store = LLMCacheStore.get_instance()
    llm_status = _describe_path(llm_store.storage_path)
    click.echo(f"LLM cache: {llm_status}")

    graph_manifest_path = build_manifest_path(root)
    graph_status = _describe_path(graph_manifest_path)
    click.echo(f"Graph cache: {graph_status}")

    baseline_path = os.path.abspath(os.path.join(root, ".nsss", "baseline.json"))
    baseline_status = _describe_path(baseline_path)
    click.echo(f"Baseline file: {baseline_status}")

    feedback_path = os.path.abspath(os.path.join(root, ".nsss", "feedback.json"))
    feedback_status = _describe_path(feedback_path)
    click.echo(f"Feedback store: {feedback_status}")


@ops.command("rotate-logs")
@click.option(
    "--log-file",
    default=os.path.join(".nsss", "logs", "nsss.log"),
    type=click.Path(dir_okay=False),
    help="Log file to rotate.",
)
@click.option(
    "--keep",
    default=5,
    show_default=True,
    type=int,
    help="Number of rotated logs to keep.",
)
def rotate_logs(log_file: str, keep: int) -> None:
    """Rotate a local NSSS log file."""
    log_path = os.path.abspath(log_file)
    if not os.path.exists(log_path):
        click.echo(f"Log file not found: {log_path}")
        return

    timestamp = datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S")
    rotated_path = f"{log_path}.{timestamp}"
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    shutil.move(log_path, rotated_path)
    with open(log_path, "w", encoding="utf-8") as handle:
        handle.write("")

    click.echo(f"Rotated log file: {rotated_path}")
    _prune_rotated_logs(log_path, keep)


def _describe_path(path: str) -> str:
    abs_path = os.path.abspath(path)
    exists = os.path.exists(abs_path)
    size = os.path.getsize(abs_path) if exists else 0
    readable = os.access(abs_path, os.R_OK) if exists else False
    writable = (
        os.access(abs_path, os.W_OK)
        if exists
        else os.access(os.path.dirname(abs_path), os.W_OK)
    )
    timestamp = "n/a"
    if exists:
        timestamp = datetime.datetime.fromtimestamp(
            os.path.getmtime(abs_path)
        ).isoformat()
    size_label = _format_bytes(size)
    return (
        f"{abs_path} (exists={exists}, size={size_label}, "
        f"readable={readable}, writable={writable}, modified={timestamp})"
    )


def _format_bytes(size: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    idx = 0
    value = float(size)
    while value >= 1024 and idx < len(units) - 1:
        value /= 1024
        idx += 1
    if idx == 0:
        return f"{int(value)} {units[idx]}"
    return f"{value:.1f} {units[idx]}"


def _prune_rotated_logs(log_path: str, keep: int) -> None:
    if keep < 0:
        return
    directory = os.path.dirname(log_path)
    basename = os.path.basename(log_path)
    rotated = []
    if os.path.isdir(directory):
        for entry in os.listdir(directory):
            if entry.startswith(basename + "."):
                rotated.append(os.path.join(directory, entry))
    rotated.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    for path in rotated[keep:]:
        try:
            os.remove(path)
        except OSError:
            pass


@ops.command("backup")
@click.option(
    "--target",
    type=click.Choice(
        ["baseline", "graph", "llm-cache", "feedback", "all"], case_sensitive=False
    ),
    default="all",
    help="Target to backup.",
)
@click.option(
    "--project-root",
    default=".",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    help="Project root directory.",
)
@click.option(
    "--keep",
    default=10,
    show_default=True,
    type=int,
    help="Number of backups to keep (older ones pruned).",
)
def backup(target: str, project_root: str, keep: int) -> None:
    """Create backups of NSSS state files."""
    root = os.path.abspath(project_root)
    nsss_dir = os.path.join(root, ".nsss")

    if not os.path.exists(nsss_dir):
        click.echo(f"NSSS directory not found: {nsss_dir}")
        return

    targets = (
        ["baseline", "graph", "llm-cache", "feedback"] if target == "all" else [target]
    )
    backup_count = 0

    for tgt in targets:
        backup_path = _create_backup(root, tgt)
        if backup_path:
            click.echo(f"Created backup: {backup_path}")
            backup_count += 1
            # Prune old backups
            _prune_backups(root, tgt, keep)

    click.echo(f"Backup complete. Created {backup_count} backup(s).")


@ops.command("rollback")
@click.option(
    "--target",
    type=click.Choice(
        ["baseline", "graph", "llm-cache", "feedback", "all"], case_sensitive=False
    ),
    help="Target to rollback (required unless --list).",
)
@click.option(
    "--backup-file",
    type=click.Path(exists=True, dir_okay=False),
    help="Specific backup file to restore from.",
)
@click.option(
    "--project-root",
    default=".",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    help="Project root directory.",
)
@click.option(
    "--list",
    "list_backups",
    is_flag=True,
    help="List available backups.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be restored without making changes.",
)
@click.option(
    "--yes",
    is_flag=True,
    help="Skip confirmation prompt.",
)
@click.option(
    "--prune",
    is_flag=True,
    help="Prune old backups instead of restoring.",
)
@click.option(
    "--keep",
    default=10,
    show_default=True,
    type=int,
    help="Number of backups to keep when pruning.",
)
def rollback(
    target: str,
    backup_file: str,
    project_root: str,
    list_backups: bool,
    dry_run: bool,
    yes: bool,
    prune: bool,
    keep: int,
) -> None:
    """Rollback NSSS state files to a previous backup."""
    root = os.path.abspath(project_root)
    nsss_dir = os.path.join(root, ".nsss")

    if not os.path.exists(nsss_dir):
        click.echo(f"NSSS directory not found: {nsss_dir}")
        return

    # List backups mode
    if list_backups:
        _list_all_backups(root)
        return

    # Prune mode
    if prune:
        if not target:
            click.echo("Error: --target is required for pruning.")
            return
        targets = (
            ["baseline", "graph", "llm-cache", "feedback"]
            if target == "all"
            else [target]
        )
        for tgt in targets:
            _prune_backups(root, tgt, keep)
            click.echo(f"Pruned old backups for {tgt}, keeping {keep} most recent.")
        return

    # Rollback mode
    if not target:
        click.echo("Error: --target is required for rollback.")
        return

    if target == "all" and backup_file:
        click.echo("Error: Cannot specify --backup-file with --target=all.")
        return

    if not yes and not dry_run:
        if not click.confirm(f"This will restore {target} from backup. Continue?"):
            click.echo("Rollback cancelled.")
            return

    targets = (
        ["baseline", "graph", "llm-cache", "feedback"] if target == "all" else [target]
    )

    for tgt in targets:
        if backup_file and tgt != target:
            continue

        restore_from = backup_file if backup_file else _find_latest_backup(root, tgt)

        if not restore_from:
            click.echo(f"No backup found for {tgt}.")
            continue

        if dry_run:
            click.echo(f"[DRY RUN] Would restore {tgt} from: {restore_from}")
        else:
            _restore_from_backup(root, tgt, restore_from)
            click.echo(f"Rolled back {tgt} from: {restore_from}")


def _create_backup(project_root: str, target: str) -> str:
    """Create a backup of a target file."""
    timestamp = datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S")
    nsss_dir = os.path.join(project_root, ".nsss")

    if target == "baseline":
        source = os.path.join(nsss_dir, "baseline.json")
    elif target == "graph":
        from src.core.persistence.graph_serializer import build_cache_dir

        source = build_cache_dir(project_root)
    elif target == "llm-cache":
        source = os.path.join(nsss_dir, "cache", "llm_cache.json")
    elif target == "feedback":
        source = os.path.join(nsss_dir, "feedback.json")
    else:
        return ""

    if not os.path.exists(source):
        return ""

    backup_path = f"{source}.backup.{timestamp}"
    if os.path.isdir(source):
        shutil.copytree(source, backup_path)
    else:
        shutil.copy2(source, backup_path)
    return backup_path


def _find_latest_backup(project_root: str, target: str) -> str:
    """Find the most recent backup for a target."""
    nsss_dir = os.path.join(project_root, ".nsss")

    if target == "baseline":
        pattern = os.path.join(nsss_dir, "baseline.json.backup.*")
    elif target == "graph":
        from src.core.persistence.graph_serializer import build_cache_dir

        base_path = build_cache_dir(project_root)
        pattern = f"{base_path}.backup.*"
    elif target == "llm-cache":
        pattern = os.path.join(nsss_dir, "cache", "llm_cache.json.backup.*")
    elif target == "feedback":
        pattern = os.path.join(nsss_dir, "feedback.json.backup.*")
    else:
        return ""

    import glob

    backups = glob.glob(pattern)
    if not backups:
        return ""

    backups.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return backups[0]


def _restore_from_backup(project_root: str, target: str, backup_path: str) -> None:
    """Restore a target from a backup file."""
    nsss_dir = os.path.join(project_root, ".nsss")

    if target == "baseline":
        dest = os.path.join(nsss_dir, "baseline.json")
    elif target == "graph":
        from src.core.persistence.graph_serializer import build_cache_dir

        dest = build_cache_dir(project_root)
    elif target == "llm-cache":
        dest = os.path.join(nsss_dir, "cache", "llm_cache.json")
    elif target == "feedback":
        dest = os.path.join(nsss_dir, "feedback.json")
    else:
        return

    if os.path.isdir(backup_path):
        if os.path.exists(dest):
            shutil.rmtree(dest)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copytree(backup_path, dest)
    else:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copy2(backup_path, dest)


def _prune_backups(project_root: str, target: str, keep: int) -> None:
    """Prune old backups, keeping only the N most recent."""
    if keep < 0:
        return

    nsss_dir = os.path.join(project_root, ".nsss")

    if target == "baseline":
        pattern = os.path.join(nsss_dir, "baseline.json.backup.*")
    elif target == "graph":
        from src.core.persistence.graph_serializer import build_cache_dir

        base_path = build_cache_dir(project_root)
        pattern = f"{base_path}.backup.*"
    elif target == "llm-cache":
        pattern = os.path.join(nsss_dir, "cache", "llm_cache.json.backup.*")
    elif target == "feedback":
        pattern = os.path.join(nsss_dir, "feedback.json.backup.*")
    else:
        return

    import glob

    backups = glob.glob(pattern)
    backups.sort(key=lambda p: os.path.getmtime(p), reverse=True)

    for backup_path in backups[keep:]:
        try:
            if os.path.isdir(backup_path):
                shutil.rmtree(backup_path)
            else:
                os.remove(backup_path)
        except OSError:
            pass


def _list_all_backups(project_root: str) -> None:
    """List all available backups."""
    nsss_dir = os.path.join(project_root, ".nsss")
    click.echo("Available backups:\n")

    targets = ["baseline", "graph", "llm-cache", "feedback"]
    found_any = False

    for target in targets:
        if target == "baseline":
            pattern = os.path.join(nsss_dir, "baseline.json.backup.*")
        elif target == "graph":
            from src.core.persistence.graph_serializer import build_cache_dir

            base_path = build_cache_dir(project_root)
            pattern = f"{base_path}.backup.*"
        elif target == "llm-cache":
            pattern = os.path.join(nsss_dir, "cache", "llm_cache.json.backup.*")
        elif target == "feedback":
            pattern = os.path.join(nsss_dir, "feedback.json.backup.*")
        else:
            continue

        import glob

        backups = glob.glob(pattern)
        if backups:
            found_any = True
            click.echo(f"{target.upper()}:")
            backups.sort(key=lambda p: os.path.getmtime(p), reverse=True)
            for backup_path in backups:
                size = os.path.getsize(backup_path)
                mtime = datetime.datetime.fromtimestamp(os.path.getmtime(backup_path))
                click.echo(f"  - {backup_path}")
                click.echo(
                    f"    Size: {_format_bytes(size)}, Modified: {mtime.isoformat()}"
                )
            click.echo()

    if not found_any:
        click.echo("No backups found.")


if __name__ == "__main__":
    cli()
