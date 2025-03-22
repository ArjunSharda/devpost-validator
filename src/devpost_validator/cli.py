import typer
from typing import Optional, List, Dict, Any, Tuple
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich import print as rprint
from rich.markdown import Markdown
from rich.text import Text
from rich.progress import Progress
from rich.console import Group
from rich.rule import Rule
from rich.box import ROUNDED, SIMPLE
from rich.columns import Columns
from rich.tree import Tree
from rich.syntax import Syntax
from rich.style import Style
from rich.prompt import Prompt, Confirm
from datetime import datetime, timezone, timedelta
import json
import os
import csv
import asyncio
import sys
from pathlib import Path
import platform
import webbrowser
import time
import re
import traceback

from devpost_validator.core import DevPostValidator, ValidationCategory, ValidationPriority
from devpost_validator.config_manager import (
    HackathonConfig, ValidationThresholds, ValidationFeatures,
    ReportSettings, GlobalSettings, BatchValidationSettings
)

app = typer.Typer(
    help="DevPost Validator: A tool to validate hackathon submissions",
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]}
)

console = Console()
error_console = Console(stderr=True)

config_app = typer.Typer(help="Manage hackathon configurations")
app.add_typer(config_app, name="config")

report_app = typer.Typer(help="Generate and manage reports")
app.add_typer(report_app, name="report")

batch_app = typer.Typer(help="Batch validation tools")
app.add_typer(batch_app, name="batch")

plugin_app = typer.Typer(help="Manage validator plugins")
app.add_typer(plugin_app, name="plugin")

VERSION = "2.0.0"


def sanitize_sensitive_data(text):
    if not isinstance(text, str):
        return text

    token_pattern = r'token\s*[=:]\s*[\'"]?([^\s\'"]+)[\'"]?'
    ghp_pattern = r'ghp_\w{36}'
    password_pattern = r'password[=:]\s*[\'"]([^\'"]+)[\'"]'

    sanitized = re.sub(token_pattern, 'token=***REDACTED***', text)
    sanitized = re.sub(ghp_pattern, '***REDACTED***', sanitized)
    sanitized = re.sub(password_pattern, 'password=***REDACTED***', sanitized)

    return sanitized


def print_version(value: bool):
    if value:
        console.print(f"DevPost Validator v{VERSION}")
        raise typer.Exit()


@app.callback()
def main(
        version: bool = typer.Option(False, "--version", "-v", help="Show version and exit", callback=print_version,
                                     is_eager=True),
):
    pass


@app.command("setup", help="Set up GitHub authentication")
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


@config_app.command("create", help="Create a new hackathon configuration")
def create_config(
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

        features = ValidationFeatures()
        report_settings = ReportSettings()

        config = HackathonConfig(
            name=name,
            start_date=start,
            end_date=end,
            allow_ai_tools=allow_ai,
            max_team_size=max_team_size,
            validation_thresholds=thresholds,
            validation_features=features,
            report_settings=report_settings,
            required_technologies=required_tech or [],
            disallowed_technologies=disallowed_tech or []
        )

        validator = DevPostValidator()
        config_path = validator.config_manager.create_hackathon_config(config, name)

        console.print(f"[green]Hackathon configuration created at: {config_path}[/green]")

        hackathon_panel = Panel(
            Group(
                Text(f"Name: {name}", style="bold"),
                Text(f"Start date: {start.strftime('%Y-%m-%d %H:%M:%S')} UTC"),
                Text(f"End date: {end.strftime('%Y-%m-%d %H:%M:%S')} UTC"),
                Text(f"Duration: {(end - start).days} days"),
                Text(f"AI tools allowed: {allow_ai}"),
                Text(f"Pass threshold: {pass_threshold}%"),
                Text(f"Review threshold: {review_threshold}%"),
                Text(f"Max team size: {max_team_size if max_team_size else 'Not limited'}"),
                Text(f"Required technologies: {', '.join(required_tech) if required_tech else 'None'}"),
                Text(f"Disallowed technologies: {', '.join(disallowed_tech) if disallowed_tech else 'None'}")
            ),
            title=f"[bold cyan]Hackathon Configuration: {name}[/bold cyan]",
            border_style="cyan",
            padding=(1, 2),
            box=ROUNDED
        )

        console.print(hackathon_panel)

    except ValueError as e:
        error_console.print(f"[red]Error: {str(e)}[/red]")


@config_app.command("list", help="List available hackathon configurations")
def list_configs():
    validator = DevPostValidator()
    configs = validator.config_manager.list_available_configs()

    if not configs:
        console.print("[yellow]No hackathon configurations found[/yellow]")
        return

    table = Table(title="Available Hackathon Configurations", box=ROUNDED, border_style="blue")
    table.add_column("Name", style="cyan")
    table.add_column("Start Date", style="green")
    table.add_column("End Date", style="green")
    table.add_column("AI Allowed", style="yellow")
    table.add_column("Required Technologies", style="magenta")

    for config_name in configs:
        config = validator.config_manager.load_hackathon_config(config_name)
        if config:
            table.add_row(
                config_name,
                config.start_date.strftime("%Y-%m-%d"),
                config.end_date.strftime("%Y-%m-%d"),
                "Yes" if config.allow_ai_tools else "No",
                ", ".join(config.required_technologies) if config.required_technologies else "None"
            )

    console.print(table)


@config_app.command("show", help="Show details of a hackathon configuration")
def show_config(name: str = typer.Argument(..., help="Name of the configuration to show")):
    validator = DevPostValidator()
    config = validator.config_manager.load_hackathon_config(name)

    if not config:
        error_console.print(f"[red]Configuration '{name}' not found[/red]")
        return

    console.print(Rule(f"[bold cyan]Hackathon Configuration: {name}[/bold cyan]", style="cyan"))

    basic_info = Table(show_header=False, box=SIMPLE, padding=(0, 2))
    basic_info.add_column("Property", style="blue")
    basic_info.add_column("Value")

    basic_info.add_row("Name", config.name)
    basic_info.add_row("Start Date", config.start_date.strftime("%Y-%m-%d %H:%M:%S %Z"))
    basic_info.add_row("End Date", config.end_date.strftime("%Y-%m-%d %H:%M:%S %Z"))
    basic_info.add_row("Duration", f"{(config.end_date - config.start_date).days} days")
    basic_info.add_row("AI Tools Allowed", "Yes" if config.allow_ai_tools else "No")
    basic_info.add_row("Maximum Team Size", str(config.max_team_size) if config.max_team_size else "Not limited")

    thresholds = Table(title="Validation Thresholds", box=SIMPLE)
    thresholds.add_column("Threshold", style="blue")
    thresholds.add_column("Value")

    thresholds.add_row("Pass Threshold", f"{config.validation_thresholds.pass_threshold}%")
    thresholds.add_row("Review Threshold", f"{config.validation_thresholds.review_threshold}%")

    weights = Table(title="Score Weights", box=SIMPLE)
    weights.add_column("Category", style="blue")
    weights.add_column("Weight")

    for category, weight in config.score_weights.items():
        weights.add_row(category.replace("_", " ").title(), f"{weight * 100:.1f}%")

    technologies = Table(title="Technology Requirements", box=SIMPLE)
    technologies.add_column("Category", style="blue")
    technologies.add_column("Technologies")

    technologies.add_row(
        "Required",
        ", ".join(config.required_technologies) if config.required_technologies else "None"
    )
    technologies.add_row(
        "Disallowed",
        ", ".join(config.disallowed_technologies) if config.disallowed_technologies else "None"
    )

    features_table = Table(title="Validation Features", box=SIMPLE)
    features_table.add_column("Feature", style="blue")
    features_table.add_column("Enabled")

    features_dict = config.validation_features.model_dump()
    for feature, enabled in features_dict.items():
        features_table.add_row(
            feature.replace("_", " ").title(),
            "[green]Enabled[/green]" if enabled else "[gray]Disabled[/gray]"
        )

    report_settings_table = Table(title="Report Settings", box=SIMPLE)
    report_settings_table.add_column("Setting", style="blue")
    report_settings_table.add_column("Value")

    report_settings_dict = config.report_settings.model_dump()
    for setting, value in report_settings_dict.items():
        if isinstance(value, bool):
            display_value = "[green]Yes[/green]" if value else "[gray]No[/gray]"
        else:
            display_value = str(value)

        report_settings_table.add_row(
            setting.replace("_", " ").title(),
            display_value
        )

    console.print(basic_info)
    console.print()
    console.print(Columns([thresholds, weights]))
    console.print()
    console.print(technologies)
    console.print()
    console.print(features_table)
    console.print()
    console.print(report_settings_table)


@config_app.command("features", help="Update validation features for a configuration")
def update_features(
        config_name: str = typer.Argument(..., help="Name of the configuration to update"),
        analyze_code_complexity: bool = typer.Option(None, help="Analyze code complexity metrics"),
        analyze_commit_patterns: bool = typer.Option(None, help="Analyze commit patterns and distribution"),
        analyze_technology_stack: bool = typer.Option(None, help="Analyze used technologies"),
        analyze_team_composition: bool = typer.Option(None, help="Analyze team composition and contributions"),
        check_plagiarism: bool = typer.Option(None, help="Check for plagiarism in submissions"),
        check_ai_content: bool = typer.Option(None, help="Check for AI-generated content"),
        export_detailed_report: bool = typer.Option(None, help="Export detailed validation reports"),
        enable_batch_processing: bool = typer.Option(None, help="Enable batch processing of submissions"),
        strict_timeline_validation: bool = typer.Option(None, help="Strict validation of submission timeline"),
        track_external_dependencies: bool = typer.Option(None, help="Track external dependencies and services"),
        detect_abandoned_branches: bool = typer.Option(None, help="Detect abandoned branches"),
        analyze_code_quality: bool = typer.Option(None, help="Analyze code quality metrics"),
        analyze_documentation: bool = typer.Option(None, help="Analyze project documentation"),
        detect_security_issues: bool = typer.Option(None, help="Detect security issues"),
        generate_recommendations: bool = typer.Option(None, help="Generate improvement recommendations"),
):
    validator = DevPostValidator()
    config = validator.config_manager.load_hackathon_config(config_name)

    if not config:
        error_console.print(f"[red]Configuration '{config_name}' not found[/red]")
        return

    features = config.validation_features

    if analyze_code_complexity is not None:
        features.analyze_code_complexity = analyze_code_complexity
    if analyze_commit_patterns is not None:
        features.analyze_commit_patterns = analyze_commit_patterns
    if analyze_technology_stack is not None:
        features.analyze_technology_stack = analyze_technology_stack
    if analyze_team_composition is not None:
        features.analyze_team_composition = analyze_team_composition
    if check_plagiarism is not None:
        features.check_plagiarism = check_plagiarism
    if check_ai_content is not None:
        features.check_ai_content = check_ai_content
    if export_detailed_report is not None:
        features.export_detailed_report = export_detailed_report
    if enable_batch_processing is not None:
        features.enable_batch_processing = enable_batch_processing
    if strict_timeline_validation is not None:
        features.strict_timeline_validation = strict_timeline_validation
    if track_external_dependencies is not None:
        features.track_external_dependencies = track_external_dependencies
    if detect_abandoned_branches is not None:
        features.detect_abandoned_branches = detect_abandoned_branches
    if analyze_code_quality is not None:
        features.analyze_code_quality = analyze_code_quality
    if analyze_documentation is not None:
        features.analyze_documentation = analyze_documentation
    if detect_security_issues is not None:
        features.detect_security_issues = detect_security_issues
    if generate_recommendations is not None:
        features.generate_recommendations = generate_recommendations

    success = validator.config_manager.update_validation_features(config_name, features)

    if success:
        console.print(f"[green]Updated validation features for '{config_name}'[/green]")

        features_dict = features.model_dump()

        table = Table(title="Updated Validation Features", box=ROUNDED)
        table.add_column("Feature")
        table.add_column("Status")

        for feature, enabled in features_dict.items():
            table.add_row(
                feature.replace("_", " ").title(),
                "[green]Enabled[/green]" if enabled else "[gray]Disabled[/gray]"
            )

        console.print(table)
    else:
        error_console.print(f"[red]Failed to update features for '{config_name}'[/red]")


@config_app.command("thresholds", help="Update validation thresholds for a configuration")
def update_thresholds(
        config_name: str = typer.Argument(..., help="Name of the hackathon configuration"),
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
        error_console.print(f"[red]Failed to update thresholds. Configuration '{config_name}' not found.[/red]")


@config_app.command("weights", help="Update score weights for a configuration")
def update_weights(
        config_name: str = typer.Argument(..., help="Name of the hackathon configuration"),
        timeline: float = typer.Option(..., help="Weight for timeline score (0.0-1.0)"),
        code_authenticity: float = typer.Option(..., help="Weight for code authenticity score (0.0-1.0)"),
        rule_compliance: float = typer.Option(..., help="Weight for rule compliance score (0.0-1.0)"),
        plagiarism: float = typer.Option(..., help="Weight for plagiarism score (0.0-1.0)"),
        team_compliance: float = typer.Option(..., help="Weight for team compliance score (0.0-1.0)"),
        complexity: float = typer.Option(..., help="Weight for code complexity score (0.0-1.0)"),
        technology: float = typer.Option(..., help="Weight for technology stack score (0.0-1.0)"),
        commit_quality: float = typer.Option(..., help="Weight for commit quality score (0.0-1.0)")
):
    weights = {
        "timeline": timeline,
        "code_authenticity": code_authenticity,
        "rule_compliance": rule_compliance,
        "plagiarism": plagiarism,
        "team_compliance": team_compliance,
        "complexity": complexity,
        "technology": technology,
        "commit_quality": commit_quality
    }

    total = sum(weights.values())
    if abs(total - 1.0) > 0.001:
        error_console.print(f"[red]Weights must sum to 1.0. Current sum: {total}[/red]")
        return

    validator = DevPostValidator()
    success = validator.config_manager.update_score_weights(config_name, weights)

    if success:
        console.print(f"[green]Updated score weights for '{config_name}'[/green]")

        table = Table(title="Updated Score Weights", box=ROUNDED)
        table.add_column("Category")
        table.add_column("Weight")

        for category, weight in weights.items():
            table.add_row(
                category.replace("_", " ").title(),
                f"{weight * 100:.1f}%"
            )

        console.print(table)
    else:
        error_console.print(
            f"[red]Failed to update weights. Configuration '{config_name}' not found or weights don't sum to 1.0.[/red]")


@app.command("check-token", help="Check if the GitHub token is valid")
def check_token(username: str = typer.Option(..., prompt=True, help="Your GitHub username")):
    validator = DevPostValidator()
    token = validator.get_github_token(username)

    if not token:
        error_console.print("[red]No GitHub token found for this username[/red]")
        return

    validator_with_token = DevPostValidator(token)
    token_check = validator_with_token.verify_github_token()

    if token_check.get("valid"):
        console.print(f"[green]GitHub token is valid for user {token_check.get('username')}[/green]")
    else:
        error_console.print(f"[red]GitHub token is invalid: {token_check.get('error')}[/red]")
        console.print("[yellow]You may need to generate a new token with 'repo' scope[/yellow]")


def _print_score_bars(scores, width=50):
    result = []

    categories = {
        "Timeline": scores.timeline_score,
        "Code Authenticity": scores.code_authenticity_score,
        "Rule Compliance": scores.rule_compliance_score,
        "Plagiarism": scores.plagiarism_score,
        "Team Compliance": scores.team_compliance_score,
        "Complexity": scores.complexity_score,
        "Technology": scores.technology_score,
        "Commit Quality": scores.commit_quality_score
    }

    table = Table(box=None, padding=(0, 1), expand=True)
    table.add_column("Category", style="blue")
    table.add_column("Score")
    table.add_column("Progress", ratio=width)

    for name, score in categories.items():
        score_text = f"{score:.1f}%"

        if score >= 90:
            color = "green"
        elif score >= 60:
            color = "yellow"
        else:
            color = "red"

        progress = Progress(
            BarColumn(bar_width=width, style=color, complete_style=f"bright_{color}"),
            TaskProgressColumn(markup=False),
            expand=True
        )
        progress_task = progress.add_task("", total=100, completed=score)

        table.add_row(name, score_text, progress)

    return table


@app.command("validate", help="Validate a GitHub repository")
def validate(
        github_url: str = typer.Argument(..., help="GitHub repository URL to validate"),
        config_name: str = typer.Option(..., help="Hackathon configuration to use"),
        username: str = typer.Option(..., help="GitHub username for authentication"),
        devpost_url: Optional[str] = typer.Option(None, help="DevPost submission URL to validate"),
        output: Optional[str] = typer.Option(None, help="Save results to JSON or HTML file"),
        report_format: str = typer.Option("html", help="Report format (html, json, markdown)"),
        verbose: bool = typer.Option(False, help="Show detailed results"),
        quiet: bool = typer.Option(False, help="Minimal output"),
        open_report: bool = typer.Option(False, help="Open report in browser when validation completes"),
        secrets: bool = typer.Option(False, help="Analyze repository for secrets and sensitive data"),
        debug: bool = typer.Option(False, help="Show debug information")
):
    try:
        validator = DevPostValidator()

        token = validator.get_github_token(username)
        if not token:
            error_console.print("[red]GitHub token not found. Please run setup first.[/red]")
            return

        validator.set_github_token(token, username)

        if debug:
            token_check = validator.verify_github_token()
            if token_check.get("valid"):
                console.print(f"[green]GitHub token verified for user {token_check.get('username')}[/green]")
            else:
                error_console.print(f"[red]GitHub token verification failed: {token_check.get('error')}[/red]")
                console.print("[yellow]Proceeding anyway, but validation may fail[/yellow]")

        config = validator.load_hackathon_config(config_name)
        if not config:
            error_console.print(f"[red]Hackathon configuration '{config_name}' not found[/red]")
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
                transient=not debug,
        ) as progress:
            task = progress.add_task("Analyzing submission...", total=None)

            if not validator.is_github_url(github_url):
                error_console.print("[red]Invalid GitHub URL format[/red]")
                return

            result = validator.validate_project(github_url, devpost_url, analyze_secrets=secrets)
            progress.update(task, completed=100, description="Analysis complete!")

        if quiet:
            print(f"{result.scores.category}: {result.scores.overall_score:.1f}%")
            return

        if result.scores.category == ValidationCategory.PASSED:
            category_style = "green bold"
        elif result.scores.category == ValidationCategory.NEEDS_REVIEW:
            category_style = "yellow bold"
        else:
            category_style = "red bold"

        console.print(Panel(
            Text(f"{result.scores.category}: {result.scores.overall_score:.1f}%", style=category_style),
            title="Validation Result",
            border_style=category_style.split()[0],
            expand=False
        ))

        summary = result.report.get("summary", {})
        timeline = result.report.get("timeline", {})

        metrics_table = Table(title="Validation Metrics", box=ROUNDED)
        metrics_table.add_column("Metric", style="blue")
        metrics_table.add_column("Value")

        metrics_table.add_row("Overall Score", f"{result.scores.overall_score:.1f}%")
        metrics_table.add_row("Validation Category", summary.get("category", "Unknown"))
        metrics_table.add_row("Failures", str(summary.get("failures_count", 0)))
        metrics_table.add_row("Warnings", str(summary.get("warnings_count", 0)))
        metrics_table.add_row("Passes", str(summary.get("passes_count", 0)))
        metrics_table.add_row("Repository Created", str(timeline.get("repository_created", "Unknown")))
        metrics_table.add_row("Created During Hackathon",
                              "Yes" if timeline.get("created_during_hackathon", False) else "No")
        metrics_table.add_row("Total Commits", str(timeline.get("total_commits", 0)))
        metrics_table.add_row("Hackathon Commits", str(timeline.get("hackathon_commits", 0)))
        metrics_table.add_row("Validation Duration", f"{summary.get('validation_duration_seconds', 0):.2f} seconds")

        console.print(metrics_table)

        console.print("\n[bold]Detailed Scores:[/bold]")
        scores_table = _print_score_bars(result.scores)
        console.print(scores_table)

        if result.failures:
            console.print("\n[bold red]Failures:[/bold red]")
            for failure in result.failures:
                priority_color = "red"
                if failure.priority == ValidationPriority.CRITICAL:
                    priority_color = "bright_red"
                elif failure.priority == ValidationPriority.HIGH:
                    priority_color = "red"
                elif failure.priority == ValidationPriority.MEDIUM:
                    priority_color = "yellow"

                console.print(f"- [{priority_color}]{failure.priority}[/{priority_color}]: {failure.message}")

        if result.warnings:
            console.print("\n[bold yellow]Warnings:[/bold yellow]")
            for warning in result.warnings:
                priority_color = "yellow"
                if warning.priority == ValidationPriority.HIGH:
                    priority_color = "bright_yellow"

                console.print(f"- [{priority_color}]{warning.priority}[/{priority_color}]: {warning.message}")

        if result.passes:
            console.print("\n[bold green]Passes:[/bold green]")
            for passed in result.passes:
                console.print(f"- [green]{passed.priority}[/green]: {passed.message}")

        if debug and hasattr(result, "github_results") and "error" in result.github_results:
            console.print("\n[bold red]Debug Information:[/bold red]")
            console.print(f"Error: {result.github_results.get('error')}")
            console.print(f"Status: {result.github_results.get('status')}")

        if verbose:
            if hasattr(result, "technology_analysis_results") and result.technology_analysis_results:
                console.print("\n[bold blue]Technology Stack Analysis:[/bold blue]")
                tech_results = result.technology_analysis_results

                tech_table = Table(box=SIMPLE)
                tech_table.add_column("Category")
                tech_table.add_column("Technologies")

                detected = tech_results.get("detected_technologies", [])
                languages = tech_results.get("primary_languages", [])
                frameworks = tech_results.get("frameworks", [])
                databases = tech_results.get("database_technologies", [])
                cloud = tech_results.get("cloud_services", [])

                tech_table.add_row("Detected Technologies", ", ".join(detected) if detected else "None")
                tech_table.add_row("Languages", ", ".join(languages) if languages else "None")
                tech_table.add_row("Frameworks", ", ".join(frameworks) if frameworks else "None")
                tech_table.add_row("Databases", ", ".join(databases) if databases else "None")
                tech_table.add_row("Cloud Services", ", ".join(cloud) if cloud else "None")

                console.print(tech_table)

            if hasattr(result, "devpost_results") and result.devpost_results:
                console.print("\n[bold cyan]DevPost Submission Analysis:[/bold cyan]")
                devpost_table = Table(box=SIMPLE)
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

            if hasattr(result, "ai_detection_results") and result.ai_detection_results:
                console.print("\n[bold yellow]AI Code Detection Results:[/bold yellow]")
                ai_table = Table(box=SIMPLE)
                ai_table.add_column("File")
                ai_table.add_column("Line")
                ai_table.add_column("Pattern")
                ai_table.add_column("Confidence")

                for indicator in result.ai_detection_results[:10]:
                    ai_table.add_row(
                        indicator.get("file", "Unknown"),
                        str(indicator.get("line", 0)),
                        indicator.get("match", "Unknown"),
                        indicator.get("confidence", "medium")
                    )

                console.print(ai_table)

                if len(result.ai_detection_results) > 10:
                    console.print(f"[yellow]... and {len(result.ai_detection_results) - 10} more indicators[/yellow]")

            if hasattr(result, "rule_violations") and result.rule_violations:
                console.print("\n[bold yellow]Rule Violations:[/bold yellow]")
                rule_table = Table(box=SIMPLE)
                rule_table.add_column("File")
                rule_table.add_column("Line")
                rule_table.add_column("Rule")
                rule_table.add_column("Description")

                for violation in result.rule_violations[:10]:
                    rule_table.add_row(
                        violation.get("file", "Unknown"),
                        str(violation.get("line", 0)),
                        violation.get("rule", "Unknown"),
                        violation.get("description", "")
                    )

                console.print(rule_table)

                if len(result.rule_violations) > 10:
                    console.print(f"[yellow]... and {len(result.rule_violations) - 10} more violations[/yellow]")

            if hasattr(result, "code_complexity_results") and result.code_complexity_results:
                console.print("\n[bold magenta]Code Complexity Analysis:[/bold magenta]")
                complexity = result.code_complexity_results

                complexity_table = Table(box=SIMPLE)
                complexity_table.add_column("Metric")
                complexity_table.add_column("Value")

                complexity_table.add_row("Average Complexity", f"{complexity.get('average_complexity', 0):.2f}")

                if "most_complex_files" in complexity:
                    complex_files = complexity["most_complex_files"]
                    if complex_files:
                        complexity_table.add_row("Most Complex File", complex_files[0].get("path", "Unknown"))
                        complexity_table.add_row("", f"Complexity: {complex_files[0].get('complexity', 0):.2f}")

                console.print(complexity_table)

 
            if secrets and hasattr(result, "secret_analysis_results") and result.secret_analysis_results:
                console.print("\n[bold red]Security Analysis Results:[/bold red]")
                
                secret_results = result.secret_analysis_results
                secret_table = Table(box=SIMPLE)
                secret_table.add_column("Metric", style="blue")
                secret_table.add_column("Value", style="red")
                
                secret_table.add_row("Total Secrets Found", str(secret_results.get("total_secrets", 0)))
                secret_table.add_row("Critical Severity", str(secret_results.get("critical_secrets", 0)))
                secret_table.add_row("High Severity", str(secret_results.get("high_risk_secrets", 0)))
                secret_table.add_row("Medium Severity", str(secret_results.get("medium_risk_secrets", 0)))
                secret_table.add_row("Security Score", f"{result.scores.secret_security_score * 100:.1f}%")
                secret_table.add_row("Files Scanned", str(secret_results.get("files_scanned", 0)))
                
                console.print(secret_table)
                
                if result.secret_analysis_results.get("findings"):
                    findings_table = Table(title="Secret Findings", box=SIMPLE)
                    findings_table.add_column("File", style="blue")
                    findings_table.add_column("Line", style="blue")
                    findings_table.add_column("Type", style="yellow")
                    findings_table.add_column("Risk", style="red")
                    
 
                    for finding in result.secret_analysis_results.get("findings", [])[:10]:
                        findings_table.add_row(
                            finding.get("file", ""),
                            str(finding.get("line", "")),
                            finding.get("type", ""),
                            finding.get("risk", "")
                        )
                    
                    console.print(findings_table)
                    
                    if len(result.secret_analysis_results.get("findings", [])) > 10:
                        console.print(f"[yellow]... and {len(result.secret_analysis_results.get('findings', [])) - 10} more secret findings[/yellow]")
        else:
            if hasattr(result, "ai_detection_results") and result.ai_detection_results:
                console.print(
                    f"\n[yellow]AI Indicators: {len(result.ai_detection_results)} found[/yellow] (Use --verbose to see details)")

            if hasattr(result, "rule_violations") and result.rule_violations:
                console.print(
                    f"\n[yellow]Rule Violations: {len(result.rule_violations)} found[/yellow] (Use --verbose to see details)")

 
            if secrets and hasattr(result, "secret_analysis_results") and result.secret_analysis_results.get("total_secrets", 0) > 0:
                console.print(f"\n[red]Security Issues: {result.secret_analysis_results.get('total_secrets', 0)} potential secrets found[/red] (Use --verbose to see details)")

        if output:
            output_path = Path(output)
            report_dir = output_path.parent
            report_dir.mkdir(exist_ok=True, parents=True)

            console.print(f"\n[blue]Generating {report_format} report...[/blue]")

            success = False
            if report_format.lower() == "html":
                success = validator.export_report_html(result, str(output_path))
            elif report_format.lower() == "json":
                success = result.save_to_file(str(output_path))
            elif report_format.lower() == "markdown":
                success = validator.report_generator.generate_markdown_report(result, str(output_path))

            if success:
                console.print(f"[green]Report saved to {output_path}[/green]")

                if open_report and report_format.lower() == "html":
                    try:
                        console.print("[blue]Opening report in your browser...[/blue]")
                        webbrowser.open(f"file://{output_path.absolute()}")
                    except Exception as e:
                        console.print(f"[yellow]Couldn't open browser: {str(e)}[/yellow]")
            else:
                error_console.print(f"[red]Error saving report to {output_path}[/red]")
    except Exception as e:
        error_msg = sanitize_sensitive_data(str(e))
        error_console.print(f"[red]Error: {error_msg}[/red]")
        if debug:
            error_console.print("[red]Debug traceback:[/red]")
            type_obj, value, tb = sys.exc_info()
            sanitized_traceback = sanitize_sensitive_data("".join(traceback.format_exception(type_obj, value, tb)))
            error_console.print(sanitized_traceback)


@app.command("add-rule", help="Add a custom validation rule")
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
            error_console.print(f"[red]Failed to add rule[/red]")
    except Exception as e:
        error_console.print(f"[red]Error adding rule: {str(e)}[/red]")


@app.command("list-rules", help="List all available validation rules")
def list_rules():
    validator = DevPostValidator()
    rules = validator.get_all_rules()

    if not rules:
        console.print("[yellow]No custom rules found[/yellow]")
        return

    table = Table(title="Available Rules", box=ROUNDED)
    table.add_column("Name", style="blue")
    table.add_column("Description", style="green")
    table.add_column("Pattern", style="yellow")

    for rule in rules:
        pattern = rule["pattern"]
        if len(pattern) > 50:
            pattern = pattern[:47] + "..."

        table.add_row(
            rule["name"],
            rule["description"],
            pattern
        )

    console.print(table)


@plugin_app.command("load", help="Load a validator plugin")
def load_plugin(
        plugin_path: str = typer.Argument(..., help="Path to the plugin file")
):
    validator = DevPostValidator()

    try:
        plugin_path = Path(plugin_path)
        if not plugin_path.exists():
            error_console.print(f"[red]Plugin file not found: {plugin_path}[/red]")
            return

        success = validator.rule_engine.load_plugin(str(plugin_path))
        if success:
            console.print(f"[green]Plugin loaded successfully[/green]")
        else:
            error_console.print(f"[red]Failed to load plugin[/red]")
    except Exception as e:
        error_console.print(f"[red]Error loading plugin: {str(e)}[/red]")

@plugin_app.command("list", help="List all loaded plugins")
def list_plugins():
    validator = DevPostValidator()
    plugins = validator.rule_engine.get_loaded_plugins()
    
    if not plugins:
        console.print("[yellow]No plugins currently loaded[/yellow]")
        return
    
    table = Table(title="Loaded Plugins")
    table.add_column("Name", style="cyan")
    table.add_column("Type", style="green")
    table.add_column("Rules Provided", style="blue")
    
    for plugin in plugins:
        if hasattr(plugin, "name"):
            name = plugin.name
            type_name = "Class-based"
            rules_count = len(plugin.register_rules()) if hasattr(plugin, "register_rules") else 0
        else:
            name = plugin.__name__ if hasattr(plugin, "__name__") else "Unknown"
            type_name = "Function-based"
            rules_count = len(plugin.register_rules()) if hasattr(plugin, "register_rules") else 0
        
        table.add_row(name, type_name, str(rules_count))
    
    console.print(table)

@plugin_app.command("unload", help="Unload a specific plugin")
def unload_plugin(
        plugin_name: str = typer.Argument(..., help="Name of the plugin to unload")
):
    validator = DevPostValidator()
    success = validator.rule_engine.unload_plugin(plugin_name)
    
    if success:
        console.print(f"[green]Plugin '{plugin_name}' successfully unloaded[/green]")
    else:
        error_console.print(f"[red]Failed to unload plugin '{plugin_name}'. Plugin not found or error occurred.[/red]")

@plugin_app.command("unload-all", help="Unload all plugins")
def unload_all_plugins():
    validator = DevPostValidator()
    validator.rule_engine.unload_all_plugins()
    console.print("[green]All plugins have been unloaded[/green]")

@plugin_app.command("create", help="Create a new plugin template")
def create_plugin(
        output_path: str = typer.Argument(..., help="Path to save the new plugin"),
        plugin_name: str = typer.Option("CustomPlugin", "--name", "-n", help="Name for the plugin class"),
        plugin_type: str = typer.Option("class", "--type", "-t", help="Plugin type: 'class' or 'function'")
):
    from devpost_validator.plugin_utils import create_plugin_template
    
    try:
        output_file = Path(output_path)
        if output_file.exists():
            overwrite = typer.confirm(f"File {output_file} already exists. Overwrite?")
            if not overwrite:
                console.print("[yellow]Plugin creation aborted[/yellow]")
                return
        
        if plugin_type.lower() not in ["class", "function"]:
            error_console.print("[red]Invalid plugin type. Must be 'class' or 'function'[/red]")
            return
            
        success = create_plugin_template(
            output_path=output_path,
            plugin_name=plugin_name,
            plugin_type=plugin_type.lower()
        )
        
        if success:
            console.print(f"[green]Plugin template created at: {output_file}[/green]")
            console.print("Edit the template to add your custom validation logic")
        else:
            error_console.print("[red]Failed to create plugin template[/red]")
    except Exception as e:
        error_console.print(f"[red]Error creating plugin template: {str(e)}[/red]")


@batch_app.command("validate", help="Batch validate multiple projects")
def batch_validate(
        file_path: str = typer.Argument(..., help="Path to a CSV or JSON file with project URLs"),
        config_name: str = typer.Option(..., help="Hackathon configuration to use"),
        username: str = typer.Option(..., help="GitHub username for authentication"),
        output_dir: str = typer.Option("./results", help="Directory to save results"),
        include_devpost: bool = typer.Option(False, help="Extract GitHub URLs from DevPost URLs"),
        report_format: str = typer.Option("html", help="Report format (html, json, markdown)"),
        concurrency: int = typer.Option(1, help="Number of concurrent validations"),
        summary_only: bool = typer.Option(False, help="Only generate summary report, not individual reports"),
        open_summary: bool = typer.Option(False, help="Open summary report when validation completes")
):
    try:
        validator = DevPostValidator()

        token = validator.get_github_token(username)
        if not token:
            error_console.print("[red]GitHub token not found. Please run setup first.[/red]")
            return

        validator.set_github_token(token, username)

        config = validator.config_manager.load_hackathon_config(config_name)
        if not config:
            error_console.print(f"[red]Hackathon configuration '{config_name}' not found[/red]")
            return

        output_dir_path = Path(output_dir)
        output_dir_path.mkdir(exist_ok=True, parents=True)

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

                has_devpost_col = False
                github_col = 0
                devpost_col = 1

                if header:
                    for i, col in enumerate(header):
                        if col.lower() in ["github", "github_url", "github url", "repo", "repository"]:
                            github_col = i
                        elif col.lower() in ["devpost", "devpost_url", "devpost url", "submission"]:
                            devpost_col = i
                            has_devpost_col = True

                for row in reader:
                    if not row:
                        continue

                    if github_col < len(row) and row[github_col].strip():
                        github_url = row[github_col].strip()
                        devpost_url = None

                        if has_devpost_col and devpost_col < len(row) and row[devpost_col].strip():
                            devpost_url = row[devpost_col].strip()

                        urls.append({
                            "github": github_url,
                            "devpost": devpost_url
                        })
                    elif has_devpost_col and devpost_col < len(row) and row[devpost_col].strip():
                        urls.append({
                            "devpost": row[devpost_col].strip(),
                            "github": None
                        })
        else:
            error_console.print("[red]Unsupported file format. Please use CSV or JSON.[/red]")
            return

        if not urls:
            error_console.print("[yellow]No URLs found in the file[/yellow]")
            return

        normalized_urls = []
        for url_item in urls:
            if isinstance(url_item, dict):
                normalized_urls.append(url_item)
            elif isinstance(url_item, str):
                if validator.is_github_url(url_item):
                    normalized_urls.append({"github": url_item, "devpost": None})
                elif validator.is_devpost_url(url_item):
                    normalized_urls.append({"devpost": url_item, "github": None})
                else:
                    console.print(f"[yellow]Skipping invalid URL: {url_item}[/yellow]")

        results = []
        console.print(
            f"[blue]Validating {len(normalized_urls)} submissions with {concurrency} concurrent workers[/blue]")

        with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TextColumn("({task.completed}/{task.total})"),
        ) as progress:
            task = progress.add_task("Validating submissions...", total=len(normalized_urls))

            for idx, url_data in enumerate(normalized_urls):
                github_url = url_data.get("github")
                devpost_url = url_data.get("devpost")

                if not github_url and devpost_url and include_devpost:
                    progress.update(task,
                                    description=f"Extracting GitHub URL from DevPost {idx + 1}/{len(normalized_urls)}")
                    github_url = validator.extract_github_url(devpost_url)

                if not github_url:
                    console.print(f"[yellow]No GitHub URL for entry {idx + 1}, skipping[/yellow]")
                    progress.update(task, advance=1)
                    continue

                progress.update(task, description=f"Validating {github_url}")

                result = validator.validate_project(github_url, devpost_url)

                short_name = github_url.split("/")[-1].split(".")[0]

                result_data = {
                    "id": result.id,
                    "github_url": github_url,
                    "devpost_url": devpost_url,
                    "category": result.scores.category,
                    "overall_score": result.scores.overall_score,
                }

                if not summary_only:
                    report_path = output_dir_path / f"{short_name}_{result.id}.{report_format}"

                    if report_format.lower() == "html":
                        validator.export_report_html(result, str(report_path))
                    elif report_format.lower() == "json":
                        result.save_to_file(str(report_path))
                    elif report_format.lower() == "markdown":
                        validator.report_generator.generate_markdown_report(result, str(report_path))

                    result_data["report_path"] = str(report_path)

                results.append(result_data)
                progress.update(task, advance=1)

        passed = sum(1 for r in results if r["category"] == ValidationCategory.PASSED)
        needs_review = sum(1 for r in results if r["category"] == ValidationCategory.NEEDS_REVIEW)
        failed = sum(
            1 for r in results if r["category"] not in (ValidationCategory.PASSED, ValidationCategory.NEEDS_REVIEW))

        summary = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total": len(results),
            "passed": passed,
            "needs_review": needs_review,
            "failed": failed,
            "config_name": config_name,
            "results": sorted(results, key=lambda x: x["overall_score"], reverse=True)
        }

        summary_path = output_dir_path / "summary.json"
        with open(summary_path, 'w') as f:
            json.dump(summary, f, indent=2, default=str)

        summary_table = Table(title="Batch Validation Summary", box=ROUNDED)
        summary_table.add_column("Category", style="blue")
        summary_table.add_column("Count", style="cyan")
        summary_table.add_column("Percentage", style="green")

        total = len(results)
        if total > 0:
            summary_table.add_row("Total Submissions", str(total), "100.0%")
            summary_table.add_row("Passed", str(passed), f"{passed / total * 100:.1f}%")
            summary_table.add_row("Needs Review", str(needs_review), f"{needs_review / total * 100:.1f}%")
            summary_table.add_row("Failed", str(failed), f"{failed / total * 100:.1f}%")
        else:
            summary_table.add_row("Total Submissions", "0", "0.0%")

        console.print(summary_table)
        console.print(f"\n[green]Summary saved to: {summary_path}[/green]")

        results_table = Table(title="Individual Results", box=ROUNDED)
        results_table.add_column("GitHub Repository", style="blue")
        results_table.add_column("Score", style="cyan")
        results_table.add_column("Category", style="green")

        for result in sorted(results, key=lambda x: x["overall_score"], reverse=True)[:10]:
            url = result["github_url"]
            short_url = "/".join(url.split("/")[-2:])

            category = result["category"]
            category_style = "green" if category == ValidationCategory.PASSED else "yellow" if category == ValidationCategory.NEEDS_REVIEW else "red"

            results_table.add_row(
                short_url,
                f"{result['overall_score']:.1f}%",
                f"[{category_style}]{category}[/{category_style}]"
            )

        if results:
            console.print(results_table)

            if len(results) > 10:
                console.print(f"[blue]... and {len(results) - 10} more results[/blue]")

        if open_summary and report_format.lower() == "html":
            summary_html = output_dir_path / "summary.html"

            percentage_passed = passed / total * 100 if total > 0 else 0
            percentage_review = needs_review / total * 100 if total > 0 else 0
            percentage_failed = failed / total * 100 if total > 0 else 0

            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Batch Validation Summary</title>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }}
                    h1 {{ color: #333; }}
                    .summary {{ background: white; padding: 20px; border-radius: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }}
                    table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
                    th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }}
                    th {{ background-color: #f2f2f2; }}
                    tr:hover {{ background-color: #f9f9f9; }}
                    .passed {{ color: green; }}
                    .needs-review {{ color: orange; }}
                    .failed {{ color: red; }}
                </style>
            </head>
            <body>
                <div class="summary">
                    <h1>Batch Validation Summary</h1>
                    <p>Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
                    <p>Config: {config_name}</p>

                    <h2>Summary</h2>
                    <table>
                        <tr>
                            <th>Category</th>
                            <th>Count</th>
                            <th>Percentage</th>
                        </tr>
                        <tr>
                            <td>Total Submissions</td>
                            <td>{total}</td>
                            <td>100.0%</td>
                        </tr>
                        <tr>
                            <td>Passed</td>
                            <td>{passed}</td>
                            <td>{percentage_passed:.1f}%</td>
                        </tr>
                        <tr>
                            <td>Needs Review</td>
                            <td>{needs_review}</td>
                            <td>{percentage_review:.1f}%</td>
                        </tr>
                        <tr>
                            <td>Failed</td>
                            <td>{failed}</td>
                            <td>{percentage_failed:.1f}%</td>
                        </tr>
                    </table>

                    <h2>Results</h2>
                    <table>
                        <tr>
                            <th>Repository</th>
                            <th>Score</th>
                            <th>Category</th>
                            <th>Report</th>
                        </tr>
            """

            for result in sorted(results, key=lambda x: x["overall_score"], reverse=True):
                url = result["github_url"]
                short_url = "/".join(url.split("/")[-2:])

                category = result["category"]
                category_class = "passed" if category == ValidationCategory.PASSED else "needs-review" if category == ValidationCategory.NEEDS_REVIEW else "failed"

                report_link = ""
                if "report_path" in result:
                    report_filename = Path(result["report_path"]).name
                    report_link = f"<a href='{report_filename}' target='_blank'>View Report</a>"

                html_content += f"""
                <tr>
                    <td><a href="{url}" target="_blank">{short_url}</a></td>
                    <td>{result['overall_score']:.1f}%</td>
                    <td class="{category_class.lower()}">{category}</td>
                    <td>{report_link}</td>
                </tr>
                """

            html_content += """
                    </table>
                </div>
            </body>
            </html>
            """

            with open(summary_html, 'w') as f:
                f.write(html_content)

            console.print(f"[green]HTML summary saved to: {summary_html}[/green]")

            if open_summary:
                try:
                    console.print("[blue]Opening summary in your browser...[/blue]")
                    webbrowser.open(f"file://{summary_html.absolute()}")
                except Exception as e:
                    console.print(f"[yellow]Couldn't open browser: {str(e)}[/yellow]")

    except Exception as e:
        error_msg = sanitize_sensitive_data(str(e))
        error_console.print(f"[red]Error processing batch validation: {error_msg}[/red]")


@report_app.command("generate", help="Generate a validation report for a previous validation")
def generate_report(
        github_url: str = typer.Argument(..., help="GitHub repository URL"),
        output: str = typer.Argument(..., help="Output file path"),
        format: str = typer.Option("html", help="Report format (html, json, markdown)"),
        config_name: str = typer.Option(..., help="Hackathon configuration to use"),
        username: str = typer.Option(..., help="GitHub username for authentication"),
        devpost_url: Optional[str] = typer.Option(None, help="DevPost submission URL"),
        open_report: bool = typer.Option(False, help="Open report when generated")
):
    try:
        validator = DevPostValidator()

        token = validator.get_github_token(username)
        if not token:
            error_console.print("[red]GitHub token not found. Please run setup first.[/red]")
            return

        validator.set_github_token(token, username)

        config = validator.load_hackathon_config(config_name)
        if not config:
            error_console.print(f"[red]Hackathon configuration '{config_name}' not found[/red]")
            return

        with Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]{task.description}"),
                transient=True,
        ) as progress:
            task = progress.add_task("Validating project...", total=None)
            result = validator.validate_project(github_url, devpost_url)
            progress.update(task, completed=100, description="Validation complete!")

        console.print(f"[blue]Generating {format} report to {output}...[/blue]")

        output_path = Path(output)
        output_path.parent.mkdir(exist_ok=True, parents=True)

        success = False
        if format.lower() == "html":
            success = validator.export_report_html(result, str(output_path))
        elif format.lower() == "json":
            success = result.save_to_file(str(output_path))
        elif format.lower() == "markdown":
            success = validator.report_generator.generate_markdown_report(result, str(output_path))

        if success:
            console.print(f"[green]Report saved to {output_path}[/green]")

            if open_report and format.lower() == "html":
                try:
                    console.print("[blue]Opening report in your browser...[/blue]")
                    webbrowser.open(f"file://{output_path.absolute()}")
                except Exception as e:
                    console.print(f"[yellow]Couldn't open browser: {str(e)}[/yellow]")
        else:
            error_console.print(f"[red]Error generating report to {output_path}[/red]")
    except Exception as e:
        error_msg = sanitize_sensitive_data(str(e))
        error_console.print(f"[red]Error generating report: {error_msg}[/red]")


@app.command("recreate-config", help="Recreate a configuration with updated schema")
def recreate_config(
        name: str = typer.Option(..., help="Name of the configuration to recreate"),
):
    validator = DevPostValidator()

    try:
        old_config = validator.load_hackathon_config(name)
        if not old_config:
            error_console.print(f"[red]Configuration '{name}' not found[/red]")
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

        features = old_config.validation_features
        if not features:
            features = ValidationFeatures()

        report_settings = old_config.report_settings
        if not report_settings:
            report_settings = ReportSettings()

        new_config = HackathonConfig(
            name=old_config.name,
            start_date=start_date,
            end_date=end_date,
            allow_ai_tools=old_config.allow_ai_tools,
            required_technologies=old_config.required_technologies,
            disallowed_technologies=old_config.disallowed_technologies,
            max_team_size=old_config.max_team_size,
            validation_thresholds=thresholds,
            validation_features=features,
            report_settings=report_settings,
            score_weights=old_config.score_weights
        )

        config_path = validator.config_manager.create_hackathon_config(new_config, name)
        console.print(f"[green]Configuration '{name}' recreated with updated schema at: {config_path}[/green]")

    except Exception as e:
        error_console.print(f"[red]Error recreating configuration: {str(e)}[/red]")


@config_app.command("wipe", help="Wipe configuration data")
def wipe_config(
    username: Optional[str] = typer.Option(None, "--username", "-u", help="GitHub username to wipe token for"),
    configs: bool = typer.Option(False, "--configs", "-c", help="Wipe all hackathon configurations"),
    config_name: Optional[str] = typer.Option(None, "--config", help="Wipe a specific configuration"),
    cache: bool = typer.Option(False, "--cache", help="Wipe cached data"),
    all_data: bool = typer.Option(False, "--all", help="Wipe all data (configs, cache, and GitHub token if username provided)"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation prompts")
):
    validator = DevPostValidator()
    
 
    if not any([username, configs, config_name, cache, all_data]):
        error_console.print("[red]Error: You must specify what to wipe (--username, --configs, --config, --cache, or --all)[/red]")
        return
    
    if config_name and configs:
        error_console.print("[red]Error: You can't use both --config and --configs together[/red]")
        return
    
 
    if not force:
        operations = []
        if username:
            operations.append(f"GitHub token for user '{username}'")
        if configs:
            operations.append("all hackathon configurations")
        if config_name:
            operations.append(f"configuration '{config_name}'")
        if cache:
            operations.append("all cached data")
        if all_data:
            operations.append("ALL DATA (configurations, cache, and GitHub token if username provided)")
        
        operations_str = ", ".join(operations)
        confirm = typer.confirm(f"Are you sure you want to wipe {operations_str}?")
        if not confirm:
            console.print("[yellow]Operation cancelled[/yellow]")
            return
    
 
    results = {
        "token_wiped": False,
        "configs_wiped": 0,
        "specific_config_wiped": False,
        "cache_files_wiped": 0
    }
    
    if username:
        results["token_wiped"] = validator.config_manager.wipe_github_token(username)
        if results["token_wiped"]:
            console.print(f"[green]Successfully wiped GitHub token for user '{username}'[/green]")
        else:
            console.print(f"[yellow]No GitHub token found for user '{username}'[/yellow]")
    
    if configs:
        count, names = validator.config_manager.wipe_all_configs()
        results["configs_wiped"] = count
        if count > 0:
            console.print(f"[green]Successfully wiped {count} hackathon configurations: {', '.join(names)}[/green]")
        else:
            console.print("[yellow]No hackathon configurations found to wipe[/yellow]")
    
    if config_name:
        results["specific_config_wiped"] = validator.config_manager.wipe_hackathon_config(config_name)
        if results["specific_config_wiped"]:
            console.print(f"[green]Successfully wiped configuration '{config_name}'[/green]")
        else:
            console.print(f"[yellow]Configuration '{config_name}' not found[/yellow]")
    
    if cache:
        count, dirs = validator.config_manager.wipe_cache()
        results["cache_files_wiped"] = count
        if count > 0:
            console.print(f"[green]Successfully wiped {count} cached files from {len(dirs)} directories[/green]")
        else:
            console.print("[yellow]No cache found to wipe[/yellow]")
    
    if all_data:
        results = validator.config_manager.wipe_all_data(username)
        console.print("[green]Successfully wiped all data:[/green]")
        console.print(f"- {results['configs_deleted']} configurations wiped")
        console.print(f"- {results['cache_files_deleted']} cached files deleted")
        if username:
            if results["token_deleted"]:
                console.print(f"- GitHub token for '{username}' deleted")
            else:
                console.print(f"- No GitHub token found for '{username}'")
        console.print("[green]All DevPost Validator data has been reset[/green]")

if __name__ == "__main__":
    app()