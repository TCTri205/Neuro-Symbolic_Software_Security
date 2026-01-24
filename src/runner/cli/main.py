import click
import sys
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
def scan(target_path, mode, output_format):
    """
    Scan a target directory or file.
    """
    click.echo(f"Initializing NSSS Scan...")
    click.echo(f"Target: {target_path}")
    click.echo(f"Mode: {mode}")
    click.echo(f"Format: {output_format}")
    click.echo(f"Loaded Configuration: HOST={settings.HOST}, DEBUG={settings.DEBUG}")
    
    # Placeholder for actual scan logic invocation
    # from src.runner.pipeline import run_scan
    # run_scan(target_path, mode, output_format)
    
    click.echo("Scan complete (Simulation).")

if __name__ == "__main__":
    cli()
