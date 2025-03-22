import typer
from typing import Optional, List, Dict, Any
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import print as rprint
from rich.markdown import Markdown
from rich.text import Text
from rich.progress import BarColumn, Progress, TextColumn
from rich.console import Group
from datetime import datetime, timezone
import json
import os
import csv
from pathlib import Path

from devpost_validator.core import DevPostValidator, ValidationCategory
from devpost_validator.config_manager import HackathonConfig, ValidationThresholds

app = typer.Typer(help="DevPost Validator: A tool to validate hackathon submissions")
console = Console()


@app.command()
def setup(username: str = typer.Option(..., prompt=True, help="Your GitHub username")):
    token = typer.prompt("Enter your GitHub token", hide_input=True)

    validator = DevPostValidator()
    success = validator.set_github_token(token, username)

    if success:
        validator_with_token = DevPostValidator(token)
        token_check = validator_with_token.verify_github_token()

        if token_check.get("valid"):
            console.print(
                f"[green]GitHub token successfully stored and verified for user {token_check.get('username')}[/green]")
        else:
            console.print(f"[yellow]GitHub token stored but verification failed: {token_check.get('error')}[/yellow]")
            console.print("[yellow]You may need to use a personal access token with 'repo' scope[/yellow]")
    else:
        console.print("[red]Failed to store GitHub token[/red]")


@app.command()
def config(
        name: str = typer.Option(..., prompt=True, help="Name for this hackathon configuration"),
        start_date: str = typer.Option(..., prompt=True, help="Hackathon start date (YYYY-MM-DD)"),
        end_date: str = typer.Option(..., prompt=True, help="Hackathon end date (YYYY-MM-DD)"),
        allow_ai: bool = typer.Option(False, help="Allow AI tools for this hackathon"),
        max_team_size: Optional[int] = typer.Option(None, help="Maximum allowed team size"),
        pass_threshold: float = typer.Option(90.0, help="Score threshold for passing validation"),
        review_threshold: float = typer.Option(60.0, help="Score threshold for needing human review"),
        required_tech: Optional[List[str]] = typer.Option(None, help="Required technologies (comma-separated)"),
        disallowed_tech: Optional[List[str]] = typer.Option(None, help="Disallowed technologies (comma-separated)")
):
    try:
        start = datetime.fromisoformat(start_date).replace(tzinfo=timezone.utc)
        end = datetime.fromisoformat(end_date).replace(tzinfo=timezone.utc)

        thresholds = ValidationThresholds(
            pass_threshold=pass_threshold,
            review_threshold=review_threshold
        )

        config = HackathonConfig(
            name=name,
            start_date=start,
            end_date=end,
            allow_ai_tools=allow_ai,
            max_team_size=max_team_size,
            validation_thresholds=thresholds,
            required_technologies=required_tech or [],
            disallowed_technologies=disallowed_tech or []
        )

        validator = DevPostValidator()
        config_path = validator.config_manager.create_hackathon_config(config, name)

        console.print(f"[green]Hackathon configuration created at: {config_path}[/green]")
        console.print(f"[blue]Start date: {start.strftime('%Y-%m-%d %H:%M:%S')} UTC[/blue]")
        console.print(f"[blue]End date: {end.strftime('%Y-%m-%d %H:%M:%S')} UTC[/blue]")
        console.print(f"[blue]AI tools allowed: {allow_ai}[/blue]")
        console.print(f"[blue]Pass threshold: {pass_threshold}%[/blue]")
        console.print(f"[blue]Review threshold: {review_threshold}%[/blue]")

        if max_team_size:
            console.print(f"[blue]Maximum team size: {max_team_size}[/blue]")

        if required_tech:
            console.print(f"[blue]Required technologies: {', '.join(required_tech)}[/blue]")

        if disallowed_tech:
            console.print(f"[blue]Disallowed technologies: {', '.join(disallowed_tech)}[/blue]")

    except ValueError as e:
        console.print(f"[red]Error: {str(e)}[/red]")


@app.command()
def update_thresholds(
        config_name: str = typer.Option(..., help="Name of the hackathon configuration"),
        pass_threshold: float = typer.Option(..., help="Score threshold for passing validation"),
        review_threshold: float = typer.Option(..., help="Score threshold for needing human review")
):
    validator = DevPostValidator()
    success = validator.config_manager.update_validation_thresholds(config_name, pass_threshold, review_threshold)

    if success:
        console.print(f"[green]Updated validation thresholds for '{config_name}'[/green]")
        console.print(f"[blue]Pass threshold: {pass_threshold}%[/blue]")
        console.print(f"[blue]Review threshold: {review_threshold}%[/blue]")
    else:
        console.print(f"[red]Failed to update thresholds. Configuration '{config_name}' not found.[/red]")


@app.command()
def update_weights(
        config_name: str = typer.Option(..., help="Name of the hackathon configuration"),
        timeline: float = typer.Option(..., help="Weight for timeline score (0.0-1.0)"),
        code_authenticity: float = typer.Option(..., help="Weight for code authenticity score (0.0-1.0)"),
        rule_compliance: float = typer.Option(..., help="Weight for rule compliance score (0.0-1.0)"),
        plagiarism: float = typer.Option(..., help="Weight for plagiarism score (0.0-1.0)"),
        team_compliance: float = typer.Option(..., help="Weight for team compliance score (0.0-1.0)")
):
    weights = {
        "timeline": timeline,
        "code_authenticity": code_authenticity,
        "rule_compliance": rule_compliance,
        "plagiarism": plagiarism,
        "team_compliance": team_compliance
    }

    total = sum(weights.values())
    if abs(total - 1.0) > 0.001:
        console.print(f"[red]Weights must sum to 1.0. Current sum: {total}[/red]")
        return

    validator = DevPostValidator()
    success = validator.config_manager.update_score_weights(config_name, weights)

    if success:
        console.print(f"[green]Updated score weights for '{config_name}'[/green]")
        for category, weight in weights.items():
            console.print(f"[blue]{category}: {weight}[/blue]")
    else:
        console.print(
            f"[red]Failed to update weights. Configuration '{config_name}' not found or weights don't sum to 1.0.[/red]")


@app.command()
def check_token(username: str = typer.Option(..., prompt=True, help="Your GitHub username")):
    validator = DevPostValidator()
    token = validator.get_github_token(username)

    if not token:
        console.print("[red]No GitHub token found for this username[/red]")
        return

    validator_with_token = DevPostValidator(token)
    token_check = validator_with_token.verify_github_token()

    if token_check.get("valid"):
        console.print(f"[green]GitHub token is valid for user {token_check.get('username')}[/green]")
    else:
        console.print(f"[red]GitHub token is invalid: {token_check.get('error')}[/red]")
        console.print("[yellow]You may need to generate a new token with 'repo' scope[/yellow]")


@app.command()
def list_configs():
    validator = DevPostValidator()
    configs = validator.config_manager.list_available_configs()

    if not configs:
        console.print("[yellow]No hackathon configurations found[/yellow]")
        return

    table = Table(title="Available Hackathon Configurations")
    table.add_column("Name")

    for config_name in configs:
        table.add_row(config_name)

    console.print(table)


def _print_score_bars(scores):
    console.print("\n[bold]Detailed Scores:[/bold]")

    for category, score in scores.items():
        score_value = float(score.strip('%'))

        if score_value >= 90:
            color = "green"
        elif score_value >= 60:
            color = "yellow"
        else:
            color = "red"

        label = f"{category.replace('_', ' ').title()}: {score}"

        progress = Progress(
            TextColumn(f"{label:30}"),
            BarColumn(bar_width=50, style=color),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            expand=True
        )

        task_id = progress.add_task("", total=100, completed=score_value)
        console.print(progress)


@app.command()
def validate(
        github_url: str = typer.Argument(..., help="GitHub repository URL to validate"),
        config_name: str = typer.Option(..., help="Hackathon configuration to use"),
        username: str = typer.Option(..., help="GitHub username for authentication"),
        devpost_url: Optional[str] = typer.Option(None, help="DevPost submission URL to validate"),
        output: Optional[str] = typer.Option(None, help="Save results to JSON file"),
        verbose: bool = typer.Option(False, help="Show detailed results"),
        debug: bool = typer.Option(False, help="Show debug information")
):
    validator = DevPostValidator()

    token = validator.get_github_token(username)
    if not token:
        console.print("[red]GitHub token not found. Please run setup first.[/red]")
        return

    validator.set_github_token(token, username)

    if debug:
        token_check = validator.verify_github_token()
        if token_check.get("valid"):
            console.print(f"[green]GitHub token verified for user {token_check.get('username')}[/green]")
        else:
            console.print(f"[red]GitHub token verification failed: {token_check.get('error')}[/red]")
            console.print("[yellow]Proceeding anyway, but validation may fail[/yellow]")

    config = validator.load_hackathon_config(config_name)
    if not config:
        console.print(f"[red]Hackathon configuration '{config_name}' not found[/red]")
        return

    if debug:
        console.print(f"[blue]Using hackathon config: {config_name}[/blue]")
        console.print(f"[blue]Start date: {config.start_date.isoformat()}[/blue]")
        console.print(f"[blue]End date: {config.end_date.isoformat()}[/blue]")
        console.print(f"[blue]Pass threshold: {config.validation_thresholds.pass_threshold}%[/blue]")
        console.print(f"[blue]Review threshold: {config.validation_thresholds.review_threshold}%[/blue]")

    with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            transient=True,
    ) as progress:
        progress.add_task("Analyzing submission...", total=None)

        if not validator.is_github_url(github_url):
            console.print("[red]Invalid GitHub URL format[/red]")
            return

        result = validator.validate_project(github_url, devpost_url)

    if result.scores.category == ValidationCategory.PASSED:
        console.print(
            Panel(f"[green bold]PASSED VALIDATION ({result.scores.overall_score:.1f}%)[/green bold]", title="Result"))
    elif result.scores.category == ValidationCategory.NEEDS_REVIEW:
        console.print(Panel(f"[yellow bold]NEEDS HUMAN REVIEW ({result.scores.overall_score:.1f}%)[/yellow bold]",
                            title="Result"))
    else:
        console.print(
            Panel(f"[red bold]FAILED VALIDATION ({result.scores.overall_score:.1f}%)[/red bold]", title="Result"))

    summary = result.report.get("summary", {})
    timeline = result.report.get("timeline", {})
    scores = result.report.get("scores", {})

    console.print("\n[bold]Summary:[/bold]")
    summary_table = Table(show_header=False)
    summary_table.add_column("Property")
    summary_table.add_column("Value")

    summary_table.add_row("Overall Score", f"{result.scores.overall_score:.1f}%")
    summary_table.add_row("Validation Category", summary.get("category", "Unknown"))
    summary_table.add_row("Failures", str(summary.get("failures_count", 0)))
    summary_table.add_row("Warnings", str(summary.get("warnings_count", 0)))
    summary_table.add_row("Passes", str(summary.get("passes_count", 0)))
    summary_table.add_row("Repository Created", str(timeline.get("repository_created", "Unknown")))
    summary_table.add_row("Created During Hackathon",
                          "Yes" if timeline.get("created_during_hackathon", False) else "No")
    summary_table.add_row("Total Commits", str(timeline.get("total_commits", 0)))
    summary_table.add_row("Hackathon Commits", str(timeline.get("hackathon_commits", 0)))

    console.print(summary_table)

    _print_score_bars(scores)

    if result.failures:
        console.print("\n[bold red]Failures:[/bold red]")
        for failure in result.failures:
            console.print(f"- {failure}")

    if result.warnings:
        console.print("\n[bold yellow]Warnings:[/bold yellow]")
        for warning in result.warnings:
            console.print(f"- {warning}")

    if result.passes:
        console.print("\n[bold green]Passes:[/bold green]")
        for passed in result.passes:
            console.print(f"- {passed}")

    if debug and "error" in result.github_results:
        console.print("\n[bold red]Debug Information:[/bold red]")
        console.print(f"Error: {result.github_results.get('error')}")
        console.print(f"Status: {result.github_results.get('status')}")

    if verbose:
        if result.devpost_results:
            console.print("\n[bold]DevPost Information:[/bold]")
            devpost_table = Table(show_header=False)
            devpost_table.add_column("Property")
            devpost_table.add_column("Value")

            devpost_table.add_row("Title", result.devpost_results.get("title", ""))
            devpost_table.add_row("AI Content Probability",
                                  f"{result.devpost_results.get('ai_content_probability', 0.0) * 100:.1f}%")
            devpost_table.add_row("Team Members", ", ".join(result.devpost_results.get("team_members", [])))
            devpost_table.add_row("Technologies", ", ".join(result.devpost_results.get("technologies", [])))
            devpost_table.add_row("Duplicate Submission",
                                  "Yes" if result.devpost_results.get("duplicate_submission", False) else "No")

            console.print(devpost_table)

        if result.ai_detection_results:
            console.print("\n[bold yellow]AI Indicators:[/bold yellow]")
            ai_table = Table()
            ai_table.add_column("File")
            ai_table.add_column("Line")
            ai_table.add_column("Match")
            ai_table.add_column("Confidence")

            for indicator in result.ai_detection_results:
                ai_table.add_row(
                    indicator.get("file", "Unknown"),
                    str(indicator.get("line", 0)),
                    indicator.get("match", "Unknown"),
                    indicator.get("confidence", "medium")
                )

            console.print(ai_table)

        if result.rule_violations:
            console.print("\n[bold yellow]Rule Violations:[/bold yellow]")
            rule_table = Table()
            rule_table.add_column("File")
            rule_table.add_column("Line")
            rule_table.add_column("Rule")
            rule_table.add_column("Description")

            for violation in result.rule_violations:
                rule_table.add_row(
                    violation.get("file", "Unknown"),
                    str(violation.get("line", 0)),
                    violation.get("rule", "Unknown"),
                    violation.get("description", "")
                )

            console.print(rule_table)
    else:
        if result.ai_detection_results:
            console.print(
                f"\n[bold yellow]AI Indicators: {len(result.ai_detection_results)} found[/bold yellow] (Use --verbose to see details)")

        if result.rule_violations:
            console.print(
                f"\n[bold yellow]Rule Violations: {len(result.rule_violations)} found[/bold yellow] (Use --verbose to see details)")

    if output:
        try:
            with open(output, 'w') as f:
                json.dump(result.to_dict(), f, indent=2, default=str)
            console.print(f"\n[green]Results saved to {output}[/green]")
        except Exception as e:
            console.print(f"\n[red]Error saving results: {str(e)}[/red]")


@app.command()
def add_rule(
        name: str = typer.Option(..., prompt=True, help="Name for the rule"),
        pattern: str = typer.Option(..., prompt=True, help="Regular expression pattern"),
        description: str = typer.Option("", prompt=True, help="Description of what the rule detects")
):
    validator = DevPostValidator()

    try:
        success = validator.add_custom_rule(name=name, pattern=pattern, description=description)
        if success:
            console.print(f"[green]Rule '{name}' added successfully[/green]")
        else:
            console.print(f"[red]Failed to add rule[/red]")
    except Exception as e:
        console.print(f"[red]Error adding rule: {str(e)}[/red]")


@app.command()
def list_rules():
    validator = DevPostValidator()
    rules = validator.get_all_rules()

    if not rules:
        console.print("[yellow]No custom rules found[/yellow]")
        return

    table = Table(title="Available Rules")
    table.add_column("Name")
    table.add_column("Description")
    table.add_column("Pattern")

    for rule in rules:
        table.add_row(
            rule["name"],
            rule["description"],
            rule["pattern"][:50] + "..." if rule["pattern"] and len(rule["pattern"]) > 50 else rule["pattern"] or ""
        )

    console.print(table)


@app.command()
def load_plugin(
        plugin_path: str = typer.Argument(..., help="Path to the plugin file")
):
    validator = DevPostValidator()

    try:
        plugin_path = Path(plugin_path)
        if not plugin_path.exists():
            console.print(f"[red]Plugin file not found: {plugin_path}[/red]")
            return

        success = validator.rule_engine.load_plugin(str(plugin_path))
        if success:
            console.print(f"[green]Plugin loaded successfully[/green]")
        else:
            console.print(f"[red]Failed to load plugin[/red]")
    except Exception as e:
        console.print(f"[red]Error loading plugin: {str(e)}[/red]")


@app.command()
def batch_validate(
        file_path: str = typer.Argument(..., help="Path to a CSV or JSON file with project URLs"),
        config_name: str = typer.Option(..., help="Hackathon configuration to use"),
        username: str = typer.Option(..., help="GitHub username for authentication"),
        output_dir: str = typer.Option("./results", help="Directory to save results"),
        include_devpost: bool = typer.Option(False, help="Whether to check DevPost URLs for GitHub repos")
):
    validator = DevPostValidator()

    token = validator.get_github_token(username)
    if not token:
        console.print("[red]GitHub token not found. Please run setup first.[/red]")
        return

    validator.set_github_token(token, username)

    config = validator.load_hackathon_config(config_name)
    if not config:
        console.print(f"[red]Hackathon configuration '{config_name}' not found[/red]")
        return

    os.makedirs(output_dir, exist_ok=True)

    try:
        urls = []
        if file_path.endswith('.json'):
            with open(file_path, 'r') as f:
                data = json.load(f)
                if isinstance(data, list):
                    urls = data
                elif 'urls' in data:
                    urls = data['urls']
        elif file_path.endswith('.csv'):
            with open(file_path, 'r') as f:
                reader = csv.reader(f)
                header = next(reader, None)
                for row in reader:
                    if row and row[0].strip():
                        urls.append(row[0].strip())
        else:
            console.print("[red]Unsupported file format. Please use CSV or JSON.[/red]")
            return

        if not urls:
            console.print("[yellow]No URLs found in the file[/yellow]")
            return

        results = []
        with Progress() as progress:
            task = progress.add_task("[cyan]Validating submissions...", total=len(urls))

            for url in urls:
                github_url = None
                devpost_url = None

                if validator.is_github_url(url):
                    github_url = url
                elif validator.is_devpost_url(url) and include_devpost:
                    devpost_url = url
                    github_url = validator.extract_github_url(devpost_url)
                    if not github_url:
                        console.print(f"[yellow]Could not find GitHub URL for DevPost: {url}[/yellow]")
                        progress.update(task, advance=1)
                        continue
                else:
                    console.print(f"[yellow]Skipping invalid URL: {url}[/yellow]")
                    progress.update(task, advance=1)
                    continue

                result = validator.validate_project(github_url, devpost_url)
                results.append({
                    "url": url,
                    "github_url": github_url,
                    "devpost_url": devpost_url,
                    "category": result.scores.category,
                    "overall_score": result.scores.overall_score,
                    "result": result.to_dict()
                })

                result_filename = f"result_{len(results)}.json"
                with open(os.path.join(output_dir, result_filename), 'w') as f:
                    json.dump(results[-1], f, indent=2, default=str)

                progress.update(task, advance=1)

        passed = sum(1 for r in results if r["category"] == ValidationCategory.PASSED)
        needs_review = sum(1 for r in results if r["category"] == ValidationCategory.NEEDS_REVIEW)
        failed = sum(
            1 for r in results if r["category"] not in (ValidationCategory.PASSED, ValidationCategory.NEEDS_REVIEW))

        summary = {
            "total": len(results),
            "passed": passed,
            "needs_review": needs_review,
            "failed": failed,
            "results": [{"url": r["url"], "category": r["category"], "score": r["overall_score"]} for r in results]
        }

        with open(os.path.join(output_dir, "summary.json"), 'w') as f:
            json.dump(summary, f, indent=2, default=str)

        console.print("\n[bold]Batch Validation Summary:[/bold]")
        console.print(f"Total submissions: {summary['total']}")
        console.print(f"[green]Passed: {summary['passed']}[/green]")
        console.print(f"[yellow]Needs review: {summary['needs_review']}[/yellow]")
        console.print(f"[red]Failed: {summary['failed']}[/red]")
        console.print(f"\nDetailed results saved to: {output_dir}")

    except Exception as e:
        console.print(f"[red]Error processing file: {str(e)}[/red]")


@app.command()
def recreate_config(
        name: str = typer.Option(..., help="Name of the configuration to recreate"),
):
    validator = DevPostValidator()

    try:
        old_config = validator.load_hackathon_config(name)
        if not old_config:
            console.print(f"[red]Configuration '{name}' not found[/red]")
            return

        start_date = old_config.start_date
        end_date = old_config.end_date

        if start_date.tzinfo is None:
            start_date = start_date.replace(tzinfo=timezone.utc)
        if end_date.tzinfo is None:
            end_date = end_date.replace(tzinfo=timezone.utc)

        thresholds = old_config.validation_thresholds
        if not thresholds:
            thresholds = ValidationThresholds()

        new_config = HackathonConfig(
            name=name,
            start_date=start_date,
            end_date=end_date,
            allow_ai_tools=old_config.allow_ai_tools,
            required_technologies=old_config.required_technologies,
            disallowed_technologies=old_config.disallowed_technologies,
            max_team_size=old_config.max_team_size,
            validation_thresholds=thresholds,
            score_weights=old_config.score_weights
        )

        config_path = validator.config_manager.create_hackathon_config(new_config, name)
        console.print(f"[green]Configuration '{name}' recreated with UTC timezone at: {config_path}[/green]")

    except Exception as e:
        console.print(f"[red]Error recreating configuration: {str(e)}[/red]")


if __name__ == "__main__":
    app()