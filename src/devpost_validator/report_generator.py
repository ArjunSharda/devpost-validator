import json
from typing import Dict, List, Any, Optional
from datetime import datetime
import statistics
from pathlib import Path
import base64
import os


class ReportGenerator:
    def __init__(self):
        self.html_template = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DevPost Validator Report</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif;
            line-height: 1.6;
            color: #333;
            margin: 0;
            padding: 20px;
            background-color: #f8f9fa;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background-color: #fff;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
        }
        header {
            text-align: center;
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 1px solid #eee;
        }
        h1 {
            color: #2c3e50;
            margin-bottom: 10px;
        }
        .status {
            display: inline-block;
            padding: 8px 16px;
            border-radius: 30px;
            font-weight: bold;
            font-size: 1.2em;
            margin-top: 10px;
        }
        .status.passed {
            background-color: #d4edda;
            color: #155724;
        }
        .status.needs-review {
            background-color: #fff3cd;
            color: #856404;
        }
        .status.failed {
            background-color: #f8d7da;
            color: #721c24;
        }
        .score-section {
            margin-bottom: 30px;
        }
        .overall-score {
            font-size: 2.5em;
            font-weight: bold;
            margin: 10px 0;
            color: #2c3e50;
        }
        .score-bar-container {
            height: 25px;
            background-color: #e9ecef;
            border-radius: 5px;
            margin-top: 8px;
            overflow: hidden;
        }
        .score-bar {
            height: 100%;
            border-radius: 5px;
            transition: width 1s ease-in-out;
        }
        .score-bar.high {
            background-color: #28a745;
        }
        .score-bar.medium {
            background-color: #ffc107;
        }
        .score-bar.low {
            background-color: #dc3545;
        }
        .score-details {
            display: flex;
            flex-wrap: wrap;
            margin: 30px 0;
        }
        .score-category {
            flex: 1;
            min-width: 200px;
            margin: 10px;
            padding: 15px;
            background-color: #f8f9fa;
            border-radius: 5px;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
        }
        .score-category h3 {
            margin-top: 0;
            color: #495057;
            font-size: 1.1em;
        }
        .score-value {
            font-size: 1.5em;
            font-weight: bold;
            margin: 10px 0;
        }
        .validation-items {
            margin: 20px 0;
        }
        .validation-items h2 {
            color: #495057;
            border-bottom: 1px solid #eee;
            padding-bottom: 10px;
        }
        .validation-item {
            padding: 12px 15px;
            margin-bottom: 10px;
            border-radius: 5px;
            position: relative;
        }
        .validation-item.pass {
            background-color: #d4edda;
            border-left: 4px solid #28a745;
        }
        .validation-item.warning {
            background-color: #fff3cd;
            border-left: 4px solid #ffc107;
        }
        .validation-item.failure {
            background-color: #f8d7da;
            border-left: 4px solid #dc3545;
        }
        .validation-item .priority {
            position: absolute;
            top: 12px;
            right: 15px;
            padding: 3px 8px;
            border-radius: 3px;
            font-size: 0.8em;
        }
        .priority.critical {
            background-color: #dc3545;
            color: white;
        }
        .priority.high {
            background-color: #fd7e14;
            color: white;
        }
        .priority.medium {
            background-color: #ffc107;
            color: #212529;
        }
        .priority.low {
            background-color: #6c757d;
            color: white;
        }
        .priority.info {
            background-color: #17a2b8;
            color: white;
        }
        .section {
            margin-bottom: 30px;
        }
        .section h2 {
            color: #495057;
            border-bottom: 1px solid #eee;
            padding-bottom: 10px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 20px;
        }
        table th, table td {
            padding: 10px;
            text-align: left;
            border-bottom: 1px solid #eee;
        }
        table th {
            background-color: #f8f9fa;
            font-weight: 600;
        }
        table tr:hover {
            background-color: #f8f9fa;
        }
        .badge {
            display: inline-block;
            padding: 3px 8px;
            border-radius: 3px;
            font-size: 0.8em;
            margin-right: 5px;
            margin-bottom: 5px;
        }
        .badge.tech {
            background-color: #e9ecef;
            color: #495057;
        }
        .badge.language {
            background-color: #cfe2ff;
            color: #084298;
        }
        .badge.framework {
            background-color: #d1e7dd;
            color: #0f5132;
        }
        .badge.database {
            background-color: #f8d7da;
            color: #842029;
        }
        .badge.cloud {
            background-color: #fff3cd;
            color: #664d03;
        }
        .timeline {
            margin-top: 20px;
            position: relative;
        }
        .timeline::before {
            content: '';
            position: absolute;
            top: 0;
            left: 15px;
            height: 100%;
            width: 2px;
            background-color: #eee;
        }
        .timeline-item {
            position: relative;
            padding-left: 40px;
            margin-bottom: 15px;
        }
        .timeline-item::before {
            content: '';
            position: absolute;
            left: 10px;
            top: 15px;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            background-color: #007bff;
        }
        .timeline-item.hackathon {
            font-weight: bold;
        }
        .timeline-item.hackathon::before {
            background-color: #28a745;
        }
        .timeline-item:not(.hackathon)::before {
            background-color: #6c757d;
        }
        .timeline-date {
            color: #6c757d;
            font-size: 0.9em;
            margin-bottom: 5px;
        }
        .metrics {
            background-color: #f8f9fa;
            padding: 15px;
            border-radius: 5px;
            margin-top: 20px;
        }
        .metrics h3 {
            margin-top: 0;
            color: #495057;
        }
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 10px;
        }
        .metric-item {
            background-color: white;
            padding: 10px;
            border-radius: 5px;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
        }
        .metric-name {
            font-size: 0.9em;
            color: #6c757d;
        }
        .metric-value {
            font-size: 1.3em;
            font-weight: bold;
            color: #495057;
            margin-top: 5px;
        }
        footer {
            text-align: center;
            color: #6c757d;
            margin-top: 50px;
            font-size: 0.9em;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>DevPost Validator Report</h1>
            <p>Repository: {{repo_name}}</p>
            <p>Generated on: {{generation_time}}</p>
            <div class="status {{status_class}}">{{status}}</div>
        </header>

        <div class="score-section">
            <h2>Overall Score</h2>
            <div class="overall-score">{{overall_score}}</div>
            <div class="score-bar-container">
                <div class="score-bar {{score_class}}" style="width: {{overall_score_numeric}}%;"></div>
            </div>
        </div>

        <div class="score-details">
            {{score_categories}}
        </div>

        <div class="validation-items">
            <h2>Validation Results</h2>

            {{failures_section}}

            {{warnings_section}}

            {{passes_section}}
        </div>

        <div class="section">
            <h2>GitHub Repository Analysis</h2>

            <table>
                <tr>
                    <th>Property</th>
                    <th>Value</th>
                </tr>
                <tr>
                    <td>Created</td>
                    <td>{{repo_created}}</td>
                </tr>
                <tr>
                    <td>Last Updated</td>
                    <td>{{repo_updated}}</td>
                </tr>
                <tr>
                    <td>Created During Hackathon</td>
                    <td>{{created_during_hackathon}}</td>
                </tr>
                <tr>
                    <td>Total Commits</td>
                    <td>{{total_commits}}</td>
                </tr>
                <tr>
                    <td>Hackathon Commits</td>
                    <td>{{hackathon_commits}}</td>
                </tr>
            </table>

            <h3>Commit Timeline</h3>
            <div class="timeline">
                {{commit_timeline}}
            </div>
        </div>

        {{technologies_section}}

        {{devpost_section}}

        {{ai_detection_section}}

        <div class="metrics">
            <h3>Validation Metrics</h3>
            <div class="metrics-grid">
                {{metrics}}
            </div>
        </div>

        <footer>
            <p>Powered by DevPost Validator</p>
            <p>© 2025 DevPost Validator</p>
        </footer>
    </div>
</body>
</html>
        '''

    def generate_html_report(self, result, output_path: str) -> bool:
        try:
            if not result:
                return False

            repo_name = result.github_results.get("name", "Unknown Repository")
            generation_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")

            category = result.scores.category
            status_class = ""
            if category == "PASSED":
                status_class = "passed"
            elif category == "NEEDS REVIEW":
                status_class = "needs-review"
            else:
                status_class = "failed"

            overall_score = f"{result.scores.overall_score:.1f}%"
            overall_score_numeric = result.scores.overall_score

            score_class = ""
            if result.scores.overall_score >= 90:
                score_class = "high"
            elif result.scores.overall_score >= 60:
                score_class = "medium"
            else:
                score_class = "low"

            score_categories_html = self._generate_score_categories_html(result.scores)

            failures_section = self._generate_validation_items_html(result.failures, "Failures", "failure")
            warnings_section = self._generate_validation_items_html(result.warnings, "Warnings", "warning")
            passes_section = self._generate_validation_items_html(result.passes, "Passes", "pass")

            timeline = result.github_results
            repo_created = str(timeline.get("created_at", "Unknown"))
            repo_updated = str(timeline.get("last_updated", "Unknown"))
            created_during_hackathon = "Yes" if timeline.get("created_during_hackathon", False) else "No"
            total_commits = str(timeline.get("total_commits", 0))
            hackathon_commits = str(timeline.get("hackathon_commits", 0))

            commit_timeline_html = self._generate_commit_timeline_html(result.github_results.get("commit_timeline", []))

            technologies_section = self._generate_technologies_section_html(result.technology_analysis_results)

            devpost_section = self._generate_devpost_section_html(result.devpost_results)

            ai_detection_section = self._generate_ai_detection_section_html(result.ai_detection_results)

            metrics_html = self._generate_metrics_html(result.metrics)

            report_html = self.html_template
            report_html = report_html.replace("{{repo_name}}", repo_name)
            report_html = report_html.replace("{{generation_time}}", generation_time)
            report_html = report_html.replace("{{status}}", category)
            report_html = report_html.replace("{{status_class}}", status_class)
            report_html = report_html.replace("{{overall_score}}", overall_score)
            report_html = report_html.replace("{{overall_score_numeric}}", str(overall_score_numeric))
            report_html = report_html.replace("{{score_class}}", score_class)
            report_html = report_html.replace("{{score_categories}}", score_categories_html)
            report_html = report_html.replace("{{failures_section}}", failures_section)
            report_html = report_html.replace("{{warnings_section}}", warnings_section)
            report_html = report_html.replace("{{passes_section}}", passes_section)
            report_html = report_html.replace("{{repo_created}}", repo_created)
            report_html = report_html.replace("{{repo_updated}}", repo_updated)
            report_html = report_html.replace("{{created_during_hackathon}}", created_during_hackathon)
            report_html = report_html.replace("{{total_commits}}", total_commits)
            report_html = report_html.replace("{{hackathon_commits}}", hackathon_commits)
            report_html = report_html.replace("{{commit_timeline}}", commit_timeline_html)
            report_html = report_html.replace("{{technologies_section}}", technologies_section)
            report_html = report_html.replace("{{devpost_section}}", devpost_section)
            report_html = report_html.replace("{{ai_detection_section}}", ai_detection_section)
            report_html = report_html.replace("{{metrics}}", metrics_html)

            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(report_html)

            return True
        except Exception as e:
            print(f"Error generating HTML report: {str(e)}")
            return False

    def _generate_score_categories_html(self, scores) -> str:
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

        html = ""
        for name, score in categories.items():
            score_class = "high" if score >= 90 else "medium" if score >= 60 else "low"

            html += f'''
            <div class="score-category">
                <h3>{name}</h3>
                <div class="score-value">{score:.1f}%</div>
                <div class="score-bar-container">
                    <div class="score-bar {score_class}" style="width: {score}%;"></div>
                </div>
            </div>
            '''

        return html

    def _generate_validation_items_html(self, items, title, item_class) -> str:
        if not items:
            return ""

        html = f"<h3>{title} ({len(items)})</h3>"

        for item in items:
            priority = item.priority.lower()

            html += f'''
            <div class="validation-item {item_class}">
                <div class="priority {priority}">{priority}</div>
                <p>{item.message}</p>
            </div>
            '''

        return html

    def _generate_commit_timeline_html(self, timeline) -> str:
        if not timeline:
            return "<p>No commit data available</p>"

        html = ""
        for commit in timeline:
            date = commit.get("date", "").split("T")[0]
            time = commit.get("date", "").split("T")[1].split(".")[0] if "T" in commit.get("date", "") else ""
            during_hackathon = "hackathon" if commit.get("during_hackathon", False) else ""
            message = commit.get("message", "").split("\n")[0]
            author = commit.get("author", "")

            html += f'''
            <div class="timeline-item {during_hackathon}">
                <div class="timeline-date">{date} {time} - {author}</div>
                <div class="timeline-content">
                    <p>{message}</p>
                </div>
            </div>
            '''

        return html

    def _generate_technologies_section_html(self, tech_results) -> str:
        if not tech_results:
            return ""

        detected_techs = tech_results.get("detected_technologies", [])
        if not detected_techs:
            return ""

        primary_languages = tech_results.get("primary_languages", [])
        frameworks = tech_results.get("frameworks", [])
        database_techs = tech_results.get("database_technologies", [])
        cloud_services = tech_results.get("cloud_services", [])

        html = '''
        <div class="section">
            <h2>Technology Stack</h2>

            <div>
        '''

        for tech in detected_techs:
            badge_class = "tech"
            if tech in primary_languages:
                badge_class = "language"
            elif tech in frameworks:
                badge_class = "framework"
            elif tech in database_techs:
                badge_class = "database"
            elif tech in cloud_services:
                badge_class = "cloud"

            html += f'<span class="badge {badge_class}">{tech}</span>'

        html += '''
            </div>

            <table style="margin-top: 20px;">
                <tr>
                    <th>Category</th>
                    <th>Technologies</th>
                </tr>
        '''

        if primary_languages:
            html += f'''
            <tr>
                <td>Languages</td>
                <td>{"".join([f'<span class="badge language">{tech}</span>' for tech in primary_languages])}</td>
            </tr>
            '''

        if frameworks:
            html += f'''
            <tr>
                <td>Frameworks</td>
                <td>{"".join([f'<span class="badge framework">{tech}</span>' for tech in frameworks])}</td>
            </tr>
            '''

        if database_techs:
            html += f'''
            <tr>
                <td>Databases</td>
                <td>{"".join([f'<span class="badge database">{tech}</span>' for tech in database_techs])}</td>
            </tr>
            '''

        if cloud_services:
            html += f'''
            <tr>
                <td>Cloud Services</td>
                <td>{"".join([f'<span class="badge cloud">{tech}</span>' for tech in cloud_services])}</td>
            </tr>
            '''

        missing_required = tech_results.get("missing_required", [])
        if missing_required:
            html += f'''
            <tr>
                <td>Missing Required Technologies</td>
                <td>{"".join([f'<span class="badge tech">{tech}</span>' for tech in missing_required])}</td>
            </tr>
            '''

        forbidden_used = tech_results.get("forbidden_used", [])
        if forbidden_used:
            html += f'''
            <tr>
                <td>Disallowed Technologies Used</td>
                <td>{"".join([f'<span class="badge tech">{tech}</span>' for tech in forbidden_used])}</td>
            </tr>
            '''

        html += '''
            </table>
        </div>
        '''

        return html

    def _generate_devpost_section_html(self, devpost_results) -> str:
        if not devpost_results:
            return ""

        title = devpost_results.get("title", "Unknown Project")
        team_members = devpost_results.get("team_members", [])
        technologies = devpost_results.get("technologies", [])
        ai_content_probability = devpost_results.get("ai_content_probability", 0.0) * 100
        duplicate_submission = "Yes" if devpost_results.get("duplicate_submission", False) else "No"

        ai_class = "high" if ai_content_probability < 30 else "medium" if ai_content_probability < 70 else "low"

        html = f'''
        <div class="section">
            <h2>DevPost Submission</h2>

            <table>
                <tr>
                    <th>Property</th>
                    <th>Value</th>
                </tr>
                <tr>
                    <td>Title</td>
                    <td>{title}</td>
                </tr>
                <tr>
                    <td>Team Members</td>
                    <td>{", ".join(team_members)}</td>
                </tr>
                <tr>
                    <td>Technologies</td>
                    <td>{"".join([f'<span class="badge tech">{tech}</span>' for tech in technologies])}</td>
                </tr>
                <tr>
                    <td>AI Content Probability</td>
                    <td>
                        <div style="display: flex; align-items: center;">
                            <span style="margin-right: 10px;">{ai_content_probability:.1f}%</span>
                            <div class="score-bar-container" style="width: 150px; margin: 0;">
                                <div class="score-bar {ai_class}" style="width: {min(100, ai_content_probability)}%;"></div>
                            </div>
                        </div>
                    </td>
                </tr>
                <tr>
                    <td>Duplicate Submission</td>
                    <td>{duplicate_submission}</td>
                </tr>
            </table>
        </div>
        '''

        return html

    def _generate_ai_detection_section_html(self, ai_results) -> str:
        if not ai_results:
            return ""

        html = '''
        <div class="section">
            <h2>AI Detection Results</h2>

            <table>
                <tr>
                    <th>File</th>
                    <th>Line</th>
                    <th>Pattern</th>
                    <th>Confidence</th>
                </tr>
        '''

        for result in ai_results[:10]:
            file = result.get("file", "Unknown")
            line = result.get("line", 0)
            match = result.get("match", "Unknown")
            confidence = result.get("confidence", "medium").lower()

            confidence_class = "high" if confidence == "high" else "medium" if confidence == "medium" else "low"

            html += f'''
            <tr>
                <td>{file}</td>
                <td>{line}</td>
                <td><code>{match}</code></td>
                <td><span class="badge priority {confidence_class}">{confidence}</span></td>
            </tr>
            '''

        html += '''
            </table>
        </div>
        '''

        return html

    def _generate_metrics_html(self, metrics) -> str:
        if not metrics:
            return ""

        html = ""

        for name, value in metrics.items():
            display_name = name.replace("_", " ").title()
            display_value = str(value)

            if isinstance(value, float):
                display_value = f"{value:.2f}"

            html += f'''
            <div class="metric-item">
                <div class="metric-name">{display_name}</div>
                <div class="metric-value">{display_value}</div>
            </div>
            '''

        return html

    def generate_markdown_report(self, result, output_path: str) -> bool:
        try:
            if not result:
                return False

            repo_name = result.github_results.get("name", "Unknown Repository")
            generation_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")

            markdown = f"# DevPost Validator Report\n\n"
            markdown += f"Repository: {repo_name}  \n"
            markdown += f"Generated on: {generation_time}  \n"
            markdown += f"Overall Score: **{result.scores.overall_score:.1f}%**  \n"
            markdown += f"Status: **{result.scores.category}**\n\n"

            markdown += "## Score Breakdown\n\n"
            markdown += f"- Timeline: {result.scores.timeline_score:.1f}%\n"
            markdown += f"- Code Authenticity: {result.scores.code_authenticity_score:.1f}%\n"
            markdown += f"- Rule Compliance: {result.scores.rule_compliance_score:.1f}%\n"
            markdown += f"- Plagiarism: {result.scores.plagiarism_score:.1f}%\n"
            markdown += f"- Team Compliance: {result.scores.team_compliance_score:.1f}%\n"
            markdown += f"- Complexity: {result.scores.complexity_score:.1f}%\n"
            markdown += f"- Technology: {result.scores.technology_score:.1f}%\n"
            markdown += f"- Commit Quality: {result.scores.commit_quality_score:.1f}%\n\n"

            markdown += "## Validation Results\n\n"

            if result.failures:
                markdown += "### Failures\n\n"
                for item in result.failures:
                    markdown += f"- 🚫 **{item.priority}**: {item.message}\n"
                markdown += "\n"

            if result.warnings:
                markdown += "### Warnings\n\n"
                for item in result.warnings:
                    markdown += f"- ⚠️ **{item.priority}**: {item.message}\n"
                markdown += "\n"

            if result.passes:
                markdown += "### Passes\n\n"
                for item in result.passes:
                    markdown += f"- ✅ **{item.priority}**: {item.message}\n"
                markdown += "\n"

            markdown += "## Repository Analysis\n\n"
            markdown += f"- Created: {result.github_results.get('created_at', 'Unknown')}\n"
            markdown += f"- Last Updated: {result.github_results.get('last_updated', 'Unknown')}\n"
            markdown += f"- Created During Hackathon: {'Yes' if result.github_results.get('created_during_hackathon', False) else 'No'}\n"
            markdown += f"- Total Commits: {result.github_results.get('total_commits', 0)}\n"
            markdown += f"- Hackathon Commits: {result.github_results.get('commits_during_hackathon', 0)}\n\n"

            if result.technology_analysis_results:
                markdown += "## Technology Stack\n\n"
                detected_techs = result.technology_analysis_results.get("detected_technologies", [])
                if detected_techs:
                    markdown += ", ".join([f"`{tech}`" for tech in detected_techs]) + "\n\n"

                primary_languages = result.technology_analysis_results.get("primary_languages", [])
                if primary_languages:
                    markdown += f"**Languages**: {', '.join(primary_languages)}\n"

                frameworks = result.technology_analysis_results.get("frameworks", [])
                if frameworks:
                    markdown += f"**Frameworks**: {', '.join(frameworks)}\n"

                database_techs = result.technology_analysis_results.get("database_technologies", [])
                if database_techs:
                    markdown += f"**Databases**: {', '.join(database_techs)}\n"

                missing_required = result.technology_analysis_results.get("missing_required", [])
                if missing_required:
                    markdown += f"**Missing Required Technologies**: {', '.join(missing_required)}\n"

                forbidden_used = result.technology_analysis_results.get("forbidden_used", [])
                if forbidden_used:
                    markdown += f"**Disallowed Technologies Used**: {', '.join(forbidden_used)}\n\n"

            if result.devpost_results:
                markdown += "## DevPost Submission\n\n"
                markdown += f"**Title**: {result.devpost_results.get('title', 'Unknown Project')}\n"
                markdown += f"**Team Members**: {', '.join(result.devpost_results.get('team_members', []))}\n"
                markdown += f"**Technologies**: {', '.join(result.devpost_results.get('technologies', []))}\n"
                markdown += f"**AI Content Probability**: {result.devpost_results.get('ai_content_probability', 0.0) * 100:.1f}%\n"
                markdown += f"**Duplicate Submission**: {'Yes' if result.devpost_results.get('duplicate_submission', False) else 'No'}\n\n"

            if result.ai_detection_results:
                markdown += "## AI Detection Results\n\n"
                markdown += "| File | Line | Pattern | Confidence |\n"
                markdown += "| --- | --- | --- | --- |\n"

                for detection in result.ai_detection_results[:10]:
                    file = detection.get("file", "Unknown")
                    line = detection.get("line", 0)
                    match = detection.get("match", "Unknown").replace("|", "\\|")
                    confidence = detection.get("confidence", "medium")

                    markdown += f"| {file} | {line} | `{match}` | {confidence} |\n"

                markdown += "\n"

            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(markdown)

            return True
        except Exception as e:
            print(f"Error generating markdown report: {str(e)}")
            return False