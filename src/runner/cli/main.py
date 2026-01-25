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
    help="Operation mode."
)
@click.option(
    "--format", 
    "output_format", 
    type=click.Choice(["json", "text"], case_sensitive=False), 
    default="text", 
    help="Output format."
)
@click.option(
    "--report-dir",
    default=".",
    help="Directory to save reports."
)
def scan(target_path, mode, output_format, report_dir):
    """
    Scan a target directory or file.
    """
    click.echo("Initializing NSSS Scan...")
    click.echo(f"Target: {target_path}")
    click.echo(f"Mode: {mode}")
    click.echo(f"Format: {output_format}")
    click.echo(f"Loaded Configuration: HOST={settings.HOST}, DEBUG={settings.DEBUG}")
    
    # Invoking Pipeline
    from src.runner.pipeline import run_scan_pipeline, generate_reports
    import json
    
    click.echo("Running analysis pipeline...")
    results = run_scan_pipeline(target_path)
    
    # Generate reports
    generate_reports(results, report_dir)
    click.echo(f"Reports generated in {report_dir}")
    
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
                click.echo(f"  CFG: {stats.get('block_count')} blocks, {stats.get('edge_count')} edges")
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
