import json
import traceback
import re
from datetime import datetime
from typing import Dict, List, Optional, Any

from src.trmeric_api.logging.AppLogger import appLogger
from src.trmeric_services.journal.Vectors.VectorEndpoints import get_vector_counts_by_category, get_vector_category_summary
from src.trmeric_services.journal.ActivityEndpoints import get_recent_activity_summaries, summarize_user_activity


class VectorVisualization:
    """Generates comprehensive markdown reports for vector analysis using VectorEndpoints"""
    
    def __init__(self, tenant_id: int):
        self.tenant_id = tenant_id
        
    def generate_time_period_report(self, days: float = 7.0, user_id: Optional[int] = None) -> str:
        """
        Generate a comprehensive markdown report of vector analysis for a time period
        
        Args:
            days: Number of days to analyze (default: 7)
            user_id: Optional user ID filter
            
        Returns:
            Markdown formatted report as string
        """
        try:
            appLogger.info({
                "event": "vector_visualization_start",
                "tenant_id": self.tenant_id,
                "user_id": user_id,
                "days": days
            })
            
            # Get vector counts using VectorEndpoints
            vector_data = get_vector_counts_by_category(
                days=days,
                tenant_id=self.tenant_id,
                user_id=user_id
            )
            
            # DEBUG: Print the raw vector data from API
            print(f"DEBUG - Raw vector data from API: {vector_data}")
            
            if not vector_data.get("success"):
                return self._generate_error_report(vector_data.get("error", "Unknown error"))
            
            # Check if we have any vector activity
            total_entries = vector_data["summary"]["total_vector_entries"]
            if total_entries == 0:
                return self._generate_empty_report(days)
            
            # Generate comprehensive report
            report = self._build_markdown_report(vector_data, days, user_id)
            
            # Save report to file
            report_path = self._save_report_to_file(f"period_{days}d", report, vector_data, days, user_id)
            
            appLogger.info({
                "event": "vector_visualization_complete",
                "report_path": report_path,
                "total_entries": total_entries
            })
            
            return report
            
        except Exception as e:
            appLogger.error({
                "event": "vector_visualization_error",
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            return f"# Vector Analysis Report - Error\n\nError generating report: {str(e)}"
    
    def _generate_ascii_chart(self, vector_data: Dict) -> str:
        """Generate ASCII bar chart for vector distribution"""
        # Get vector counts
        vectors = []
        for vector_name, data in vector_data.items():
            if data["count"] > 0:
                vectors.append((vector_name.replace('_', ' ').title(), data["count"]))
        
        if not vectors:
            return "No vector data to display"
        
        # Sort by count
        vectors.sort(key=lambda x: x[1], reverse=True)
        
        # Calculate bar lengths (max 40 chars)
        max_count = max(count for _, count in vectors)
        max_bar_length = 40
        
        chart_lines = ["```", "Vector Distribution Chart:", ""]
        
        for vector_name, count in vectors:
            bar_length = int((count / max_count) * max_bar_length)
            bar = "█" * bar_length
            padding = " " * (25 - len(vector_name))
            chart_lines.append(f"{vector_name}{padding} │{bar} {count}")
        
        chart_lines.extend(["", "```"])
        return "\n".join(chart_lines)
    
    def _generate_pie_chart_text(self, vector_data: Dict) -> str:
        """Generate text-based pie chart representation"""
        # Get vector counts
        total_count = sum(data["count"] for data in vector_data.values() if data["count"] > 0)
        
        if total_count == 0:
            return "No data for pie chart"
        
        lines = ["```", "Vector Distribution (Pie Chart):", ""]
        
        # Unicode pie chart characters
        pie_chars = ["●", "○", "◆", "◇", "▲", "△"]
        
        for i, (vector_name, data) in enumerate(vector_data.items()):
            if data["count"] > 0:
                percentage = (data["count"] / total_count) * 100
                char = pie_chars[i % len(pie_chars)]
                vector_display = vector_name.replace('_', ' ').title()
                lines.append(f"{char} {vector_display}: {data['count']} ({percentage:.1f}%)")
        
        lines.extend(["", "```"])
        return "\n".join(lines)
    
    def _build_markdown_report(self, vector_data: Dict, days: float, user_id: Optional[int] = None) -> str:
        """Build the comprehensive markdown report"""
        summary = vector_data["summary"]
        period_info = vector_data["period"]
        date_range = vector_data["date_range"]
        filters = vector_data.get("filters", {})
        
        # Header
        report_lines = [
            "# Vector Analysis Report",
            "",
            f"**Period:** {period_info}",
            f"**Date Range:** {date_range['from']} to {date_range.get('to', 'now')}",
            f"**Tenant ID:** {self.tenant_id}",
        ]
        
        if filters.get("user_id"):
            report_lines.append(f"**User ID:** {filters['user_id']}")
        
        report_lines.extend([
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "---",
            ""
        ])
        
        # Executive Summary with metrics
        report_lines.extend(self._generate_executive_summary(summary, vector_data["vector_data"]))
        
        # Visual Charts
        report_lines.extend(self._generate_visual_charts(vector_data["vector_data"]))
        
        # Detailed Vector Analysis
        report_lines.extend(self._generate_detailed_analysis(vector_data["vector_data"]))
        
        # AI Insights for each active vector
        report_lines.extend(self._generate_ai_insights_section(vector_data["vector_data"], days))
        
        # Activity Summary Section
        if user_id:
            report_lines.extend(self._generate_activity_summary_section(user_id, days))
        
        # Footer
        report_lines.extend([
            "",
            "---",
            "",
            f"*Report generated by Trmeric Vector Analysis System on {datetime.now().strftime('%Y-%m-%d at %H:%M:%S')}*"
        ])
        
        return "\n".join(report_lines)
    
    def _generate_executive_summary(self, summary: Dict, vector_data: Dict) -> List[str]:
        """Generate executive summary section"""
        active_vectors = sum(1 for data in vector_data.values() if data["count"] > 0)
        
        lines = [
            "## Executive Summary",
            "",
            f"- **Total Vector Entries:** {summary['total_vector_entries']}",
            f"- **Total Activities:** {summary['total_activities']}",
            f"- **Active Vectors:** {active_vectors} out of 6",
            f"- **Vectors with Activity:** {summary['vectors_with_activity']}",
            ""
        ]
        
        # Top performing vectors
        top_vectors = sorted(
            [(name, data["count"]) for name, data in vector_data.items() if data["count"] > 0],
            key=lambda x: x[1], reverse=True
        )[:3]
        
        if top_vectors:
            lines.extend([
                "**Top Performing Vectors:**",
                ""
            ])
            for i, (vector_name, count) in enumerate(top_vectors, 1):
                vector_display = vector_name.replace('_', ' ').title()
                lines.append(f"{i}. **{vector_display}** - {count} entries")
            lines.append("")
        
        return lines
    
    def _generate_visual_charts(self, vector_data: Dict) -> List[str]:
        """Generate visual chart sections"""
        lines = [
            "## Vector Distribution Visualizations",
            "",
            "### Bar Chart",
            "",
            self._generate_ascii_chart(vector_data),
            "",
            "### Distribution Breakdown",
            "",
            self._generate_pie_chart_text(vector_data),
            ""
        ]
        return lines
    
    def _generate_detailed_analysis(self, vector_data: Dict) -> List[str]:
        """Generate detailed analysis for each vector"""
        lines = [
            "## Detailed Vector Analysis",
            ""
        ]
        
        # Vector definitions from VectorEndpoints
        vector_definitions = {
            "value_vector": "Business Impact & Value Creation",
            "strategy_planning_vector": "Strategic Planning & Vision",
            "execution_vector": "Project Execution & Implementation",
            "portfolio_management_vector": "Portfolio Oversight & Management",
            "governance_vector": "Governance & Risk Management",
            "learning_vector": "Knowledge & Learning Management"
        }
        
        # Sort by count (highest first)
        sorted_vectors = sorted(
            vector_data.items(),
            key=lambda x: x[1]["count"],
            reverse=True
        )
        
        for vector_name, data in sorted_vectors:
            vector_display = vector_name.replace('_', ' ').title()
            vector_def = vector_definitions.get(vector_name, "Vector definition not available")
            
            lines.extend([
                f"### 🔹 {vector_display}",
                "",
                f"**Definition:** {vector_def}",
                f"**Total Entries:** {data['count']}",
                f"**Activities Tracked:** {len(data['activity_ids'])}",
                ""
            ])
            
            if data["count"] > 0:
                # Show recent entries
                recent_entries = data["entries"][:3]  # Show latest 3
                lines.append("**Recent Activity:**")
                lines.append("")
                
                for entry in recent_entries:
                    created_date = entry["created_date"]
                    if isinstance(created_date, str):
                        date_display = created_date.split('T')[0]  # Just the date part
                    else:
                        date_display = created_date.strftime('%Y-%m-%d')
                    
                    lines.append(f"- 📅 {date_display} - Entry `{entry['entry_id']}` ({entry['activity_count']} activities)")
                
                if data["count"] > 3:
                    lines.append(f"- ... and {data['count'] - 3} more entries")
                
                lines.append("")
            else:
                lines.extend([
                    "*No activity recorded for this vector in the selected time period.*",
                    ""
                ])
        
        return lines
    
    def _generate_ai_insights_section(self, vector_data: Dict, days: float) -> List[str]:
        """Generate AI insights for vectors with activity"""
        lines = [
            "## AI-Generated Vector Insights",
            ""
        ]
        
        active_vectors = [(name, data) for name, data in vector_data.items() if data["count"] > 0]
        
        if not active_vectors:
            lines.extend([
                "*No vector activity found for AI analysis.*",
                ""
            ])
            return lines
        
        # Generate summary for each active vector
        for vector_name, data in active_vectors:
            if data["count"] > 0:
                vector_display = vector_name.replace('_', ' ').title()
                
                lines.extend([
                    f"### 🔸 {vector_display} Insights",
                    ""
                ])
                
                try:
                    # Get AI summary for this vector
                    summary_result = get_vector_category_summary(
                        vector_name=vector_name,
                        days=days,
                        tenant_id=self.tenant_id
                    )
                    
                    if summary_result.get("success"):
                        ai_summary = summary_result.get("ai_summary", "No summary available")
                        # Format the AI summary nicely
                        formatted_summary = ai_summary.replace("### ", "**").replace("##", "**")
                        lines.extend([
                            formatted_summary,
                            ""
                        ])
                    else:
                        lines.extend([
                            f"*Unable to generate insights: {summary_result.get('error', 'Unknown error')}*",
                            ""
                        ])
                
                except Exception as e:
                    lines.extend([
                        f"*Error generating insights for {vector_display}: {str(e)}*",
                        ""
                    ])
        
        return lines
    
    def _generate_activity_summary_section(self, user_id: int, days: float) -> List[str]:
        """Generate activity summary section using ActivityEndpoints"""
        lines = [
            "## Recent Activity Summary",
            ""
        ]
        
        try:
            # Get recent activity summaries using the new endpoint
            activity_result = get_recent_activity_summaries(
                user_id=user_id,
                limit=5,
                tenant_id=self.tenant_id,
                days=days
            )
            
            if not activity_result.get("success"):
                lines.extend([
                    "*Unable to retrieve activity summaries.*",
                    ""
                ])
                return lines
            
            summaries = activity_result.get("summaries", [])
            if not summaries:
                lines.extend([
                    f"*No activity summaries found for the past {days} days.*",
                    ""
                ])
                return lines

            # Add summary count info
            count = activity_result.get("count", 0)
            lines.extend([
                f"**Recent Sessions:** {count} session summaries found",
                ""
            ])

            # Add individual summaries using the known format from ActivityEndpoints
            for i, summary_data in enumerate(summaries, 1):
                # Get summary text - we know this field exists
                summary_text = summary_data.get("summary", "No summary available")
                
                # Get formatted date - should now be properly formatted with the DAO fix
                date_formatted = summary_data.get("date_formatted", "Recent Activity")
                
                # Extract just the date part if it includes time
                if " " in date_formatted and date_formatted != "Recent Activity":
                    date_display = date_formatted.split(" ")[0]  # Just the date part
                else:
                    date_display = date_formatted

                lines.extend([
                    f"### Session {i} - {date_display}",
                    "",
                    summary_text,
                    ""
                ])
            
            # Try to get synthesized summary using the existing function
            try:
                synthesized_summary, _ = summarize_user_activity(user_id, limit=count)
                if synthesized_summary and synthesized_summary != "You don't have any recent activities with Tango. Time to get started!":
                    lines.extend([
                        "### Activity Synthesis",
                        "",
                        "**Overall Journey Analysis:**",
                        "",
                        synthesized_summary,
                        ""
                    ])
            except Exception as synth_error:
                appLogger.warning({
                    "event": "activity_synthesis_error",
                    "user_id": user_id,
                    "error": str(synth_error)
                })
                # Continue without synthesis - not critical
            
        except Exception as e:
            appLogger.error({
                "event": "generate_activity_summary_error",
                "user_id": user_id,
                "days": days,
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            lines.extend([
                f"*Error retrieving activity summaries: {str(e)}*",
                ""
            ])
        
        return lines
    
    def _generate_empty_report(self, days: float) -> str:
        """Generate report for periods with no vector activity"""
        return f"""# Vector Analysis Report

    **Period:** Past {days} days
    **Tenant ID:** {self.tenant_id}
    **Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

    ## Summary

    No vector activity was found for the selected time period. This could indicate:

    - No transformation activities occurred
    - Activities haven't been processed through vector analysis yet
    - Filters are too restrictive

    Try expanding the time period or checking different filter criteria.

    ---

    *Report generated by Trmeric Vector Analysis System*
    """
    
    def _generate_error_report(self, error_message: str) -> str:
        """Generate report for error cases"""
        return f"""# Vector Analysis Report - Error

    **Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

    ## Error

    Unable to generate vector analysis report.

    **Error Details:** {error_message}

    Please check system logs for more information.

    ---

    *Report generated by Trmeric Vector Analysis System*
    """
    
    def _save_report_to_file(self, report_id: str, report: str, vector_data: Dict = None, days: float = None, user_id: int = None) -> str:
        """Save the report to both markdown and HTML files"""
        try:
            import os
            
            # Create reports directory if it doesn't exist
            reports_dir = "/tmp/vector_reports"
            os.makedirs(reports_dir, exist_ok=True)
            
            # Generate filename with timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            base_filename = f"vector_analysis_{report_id}_{timestamp}"
            
            # Save markdown file
            md_file_path = os.path.join(reports_dir, f"{base_filename}.md")
            with open(md_file_path, 'w', encoding='utf-8') as f:
                f.write(report)
            
            # Generate and save HTML file with enhanced styling  
            if vector_data and vector_data.get('success') and days is not None:
                html_content = self._generate_html_report(vector_data, days, user_id)
            else:
                # Fallback to basic HTML for cases without vector data
                html_content = f"<html><body><h1>Vector Report</h1><pre>{report}</pre></body></html>"
            html_file_path = os.path.join(reports_dir, f"{base_filename}.html")
            with open(html_file_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            appLogger.info({
                "event": "vector_report_saved",
                "report_id": report_id,
                "md_file_path": md_file_path,
                "html_file_path": html_file_path
            })
            
            return f"Reports saved:\n- Markdown: {md_file_path}\n- HTML: {html_file_path}"
            
        except Exception as e:
            appLogger.error({
                "event": "vector_report_save_error",
                "report_id": report_id,
                "error": str(e)
            })
            return f"Error saving report: {str(e)}"

    def _generate_html_report(self, vector_data: Dict, days: float, user_id: int = None) -> str:
        """Generate interactive dashboard HTML with orange theme and radar chart using API data directly"""
        
        # Extract vector counts directly from API data
        vector_counts = {}
        all_vectors = ['Strategy Planning', 'Portfolio Management', 'Value Creation', 'Execution', 'Governance', 'Learning']
        
        # Map API vector names to display names
        vector_name_mapping = {
            'strategy_planning_vector': 'Strategy Planning',
            'portfolio_management_vector': 'Portfolio Management',
            'value_vector': 'Value Creation', 
            'execution_vector': 'Execution',
            'governance_vector': 'Governance',
            'learning_vector': 'Learning'
        }
        
        # Initialize all vectors to 0
        for vector in all_vectors:
            vector_counts[vector] = 0
            
        # Extract actual counts from API data
        if 'vector_data' in vector_data:
            for api_name, data in vector_data['vector_data'].items():
                display_name = vector_name_mapping.get(api_name, api_name)
                if display_name in vector_counts:
                    vector_counts[display_name] = data.get('count', 0)
        
        # Generate sessions data from activity summaries
        sessions = []
        if user_id:
            try:
                from src.trmeric_services.journal.ActivityEndpoints import get_recent_activity_summaries
                session_data = get_recent_activity_summaries(user_id, limit=5, days=days)
                
                if session_data.get('success') and session_data.get('summaries'):
                    for i, session_summary in enumerate(session_data['summaries']):
                        sessions.append({
                            'title': f"Session {i+1} - {session_summary.get('date_formatted', 'Unknown Date')}",
                            'content': session_summary.get('summary', 'No summary available'),
                            'session_id': session_summary.get('socket_id', ''),
                            'created_date': session_summary.get('created_date', ''),
                            'vectors': []  # Will be populated based on session analysis
                        })
            except Exception as e:
                appLogger.warning(f"Could not load session data: {e}")
                sessions = []
        
        # Map sessions to vectors based on the vector entries
        for session in sessions:
            session_vectors = []
            session_id = session['session_id']
            
            # DEBUG: Print session ID being checked
            print(f"DEBUG - Checking session ID: {session_id}")
            
            # Check which vectors this session is associated with
            if 'vector_data' in vector_data:
                for api_vector_name, vector_info in vector_data['vector_data'].items():
                    display_name = vector_name_mapping.get(api_vector_name, api_vector_name)
                    
                    # Check if this session appears in this vector's entries
                    for entry in vector_info.get('entries', []):
                        entry_session_id = entry.get('session_id')
                        print(f"DEBUG - Comparing with vector entry session ID: {entry_session_id}")
                        if entry_session_id == session_id:
                            if display_name not in session_vectors:
                                session_vectors.append(display_name)
                            break
            
            # Fallback: if no session_id match, use content-based mapping
            if not session_vectors:
                print(f"DEBUG - No session ID match found, using content-based mapping for session: {session['title']}")
                content_lower = session['content'].lower()
                
                # Simple keyword matching for vector assignment
                if any(word in content_lower for word in ['strategy', 'strategic', 'planning', 'vision']):
                    if vector_counts.get('Strategy Planning', 0) > 0:
                        session_vectors.append('Strategy Planning')
                if any(word in content_lower for word in ['portfolio', 'management', 'project']):
                    if vector_counts.get('Portfolio Management', 0) > 0:
                        session_vectors.append('Portfolio Management')
                if any(word in content_lower for word in ['value', 'impact', 'outcome', 'analytics', 'data']):
                    if vector_counts.get('Value Creation', 0) > 0:
                        session_vectors.append('Value Creation')
                if any(word in content_lower for word in ['execution', 'implement', 'deploy', 'deliver']):
                    if vector_counts.get('Execution', 0) > 0:
                        session_vectors.append('Execution')
                if any(word in content_lower for word in ['governance', 'risk', 'compliance', 'govern']):
                    if vector_counts.get('Governance', 0) > 0:
                        session_vectors.append('Governance')
                if any(word in content_lower for word in ['learning', 'knowledge', 'training', 'education']):
                    if vector_counts.get('Learning', 0) > 0:
                        session_vectors.append('Learning')
            
            session['vectors'] = session_vectors
            print(f"DEBUG - Session '{session['title']}' mapped to vectors: {session_vectors}")
        
        # Calculate summary stats
        active_vectors = sum(1 for count in vector_counts.values() if count > 0)
        total_entries = sum(vector_counts.values())
        vector_insights = {}  # Empty for now, can be populated later
        
        # DEBUG: Print the data being used
        print(f"DEBUG - Vector counts for HTML: {vector_counts}")
        print(f"DEBUG - Sessions for HTML: {len(sessions)}")
        print(f"DEBUG - Session details: {[{'title': s['title'], 'vectors': s['vectors'], 'content_preview': s['content'][:100]} for s in sessions]}")
        print(f"DEBUG - Active vectors: {active_vectors}, Total entries: {total_entries}")
        
        html_content = f"""<!DOCTYPE html>
<html lang='en'>
<head>
    <meta charset='UTF-8'>
    <meta name='viewport' content='width=device-width, initial-scale=1.0'>
    <title>trmeric Vector Analysis Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        
        body {{
            font-family: 'Inter', 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #f8f9fa;
            color: #2c1810;
            height: 100vh;
            overflow: hidden;
        }}
        
        .banner {{
            background: linear-gradient(135deg, #ff6b35 0%, #f7931e 100%);
            color: white;
            padding: 16px 24px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            position: relative;
            z-index: 100;
            border-bottom: 1px solid rgba(255,255,255,0.2);
        }}
        
        .banner h1 {{
            font-size: 24px;
            font-weight: 600;
            letter-spacing: 1px;
            margin: 0;
        }}
        
        .banner .subtitle {{
            font-size: 14px;
            opacity: 0.9;
            margin-top: 4px;
            font-weight: 400;
        }}
        
        .dashboard {{
            display: flex;
            height: calc(100vh - 80px);
            background: white;
            margin: 0;
            overflow: hidden;
        }}
        
        .left-panel {{
            width: 35%;
            background: #fafafa;
            border-right: 1px solid #e5e5e5;
            display: flex;
            flex-direction: column;
        }}
        
        .sessions-header {{
            background: white;
            color: #333;
            padding: 20px 24px;
            border-bottom: 1px solid #e5e5e5;
            font-weight: 600;
            font-size: 16px;
        }}
        
        .sessions-container {{
            flex: 1;
            overflow-y: auto;
            padding: 16px;
        }}
        
        .session-card {{
            background: white;
            border: 1px solid #e5e5e5;
            border-radius: 8px;
            margin: 0 0 12px 0;
            padding: 16px;
            cursor: pointer;
            transition: all 0.2s ease;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}
        
        .session-card:hover {{
            border-color: #ff6b35;
            box-shadow: 0 2px 8px rgba(255,107,53,0.15);
        }}
        
        .session-card.highlighted {{
            border-color: #ff6b35;
            background: #fff8f5;
            box-shadow: 0 2px 12px rgba(255,107,53,0.2);
        }}
        
        .session-title {{
            font-weight: 600;
            color: #333;
            margin-bottom: 8px;
            font-size: 14px;
        }}
        
        .session-content {{
            font-size: 13px;
            line-height: 1.5;
            color: #666;
            max-height: 80px;
            overflow: hidden;
            text-overflow: ellipsis;
        }}
        
        .vector-tags {{
            margin-top: 12px;
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
        }}
        
        .vector-tag {{
            background: #ff6b35;
            color: white;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 500;
        }}
        
        .right-panel {{
            flex: 1;
            background: white;
            display: flex;
            flex-direction: column;
        }}
        
        .chart-header {{
            background: white;
            color: #333;
            padding: 20px 24px;
            border-bottom: 1px solid #e5e5e5;
            font-weight: 600;
            font-size: 16px;
        }}
        
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 16px;
            margin: 20px 24px;
        }}
        
        .stat-card {{
            background: linear-gradient(135deg, #ff6b35 0%, #f7931e 100%);
            color: white;
            padding: 16px;
            border-radius: 8px;
            text-align: center;
            box-shadow: 0 2px 4px rgba(255,107,53,0.2);
        }}
        
        .stat-number {{
            font-size: 24px;
            font-weight: 700;
            margin-bottom: 4px;
        }}
        
        .stat-label {{
            font-size: 12px;
            opacity: 0.9;
            font-weight: 500;
        }}
        
        .chart-container {{
            padding: 24px;
            display: flex;
            align-items: center;
            justify-content: center;
            background: #fafafa;
            border-bottom: 1px solid #e5e5e5;
            min-height: 340px; /* reduced to give more space for insights */
        }}
        
        .chart-wrapper {{
            position: relative;
            width: 320px;
            height: 320px;
        }}
        
        .vector-details {{
            flex: 1;
            padding: 24px;
            overflow-y: auto;
            background: white;
        }}
        
        .vector-details h3 {{
            color: #333;
            margin-bottom: 16px;
            font-size: 18px;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        
        .vector-icon {{
            width: 12px;
            height: 12px;
            border-radius: 50%;
            background: #ff6b35;
        }}
        
        .vector-details p {{
            color: #666;
            font-size: 14px;
            line-height: 1.6;
            margin-bottom: 12px;
        }}
        
        .insight-content {{
            background: #f8f9fa;
            border-left: 4px solid #ff6b35;
            padding: 16px;
            border-radius: 0 4px 4px 0;
            margin-top: 16px;
            transition: all 0.3s ease;
            cursor: pointer;
        }}
        
        .insight-content:hover {{
            background: #f0f2f5;
            transform: translateX(2px);
            box-shadow: 0 2px 8px rgba(255,107,53,0.1);
        }}
        
        .animated-number {{
            display: inline-block;
            transition: all 0.5s ease;
        }}
        
        .pulse-animation {{
            animation: pulse 2s infinite;
        }}
        
        @keyframes pulse {{
            0% {{ transform: scale(1); }}
            50% {{ transform: scale(1.05); }}
            100% {{ transform: scale(1); }}
        }}
        
        .chart-controls {{
            display: flex;
            gap: 8px;
            margin: 16px 24px 0 24px;
            flex-wrap: wrap;
        }}
        
        .control-button {{
            background: #ffffff;
            border: 2px solid #ff6b35;
            color: #ff6b35;
            padding: 8px 16px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 12px;
            font-weight: 600;
            transition: all 0.2s ease;
            user-select: none;
        }}
        
        .control-button:hover {{
            background: #ff6b35;
            color: white;
            transform: translateY(-1px);
            box-shadow: 0 2px 8px rgba(255,107,53,0.3);
        }}
        
        .control-button.active {{
            background: #ff6b35;
            color: white;
        }}
        
        .vector-comparison-bar {{
            width: 100%;
            height: 8px;
            background: #e9ecef;
            border-radius: 4px;
            margin: 8px 0;
            overflow: hidden;
        }}
        
        .comparison-fill {{
            height: 100%;
            background: linear-gradient(90deg, #ff6b35, #f7931e);
            border-radius: 4px;
            transition: width 0.8s ease;
        }}
        
        .session-card.fade-in {{
            animation: fadeIn 0.5s ease;
        }}
        
        @keyframes fadeIn {{
            from {{ opacity: 0; transform: translateY(10px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}
        
        .tooltip {{
            position: absolute;
            background: rgba(51,51,51,0.95);
            color: white;
            padding: 8px 12px;
            border-radius: 4px;
            font-size: 12px;
            pointer-events: none;
            z-index: 1000;
            opacity: 0;
            transition: opacity 0.2s ease;
        }}
        
        .tooltip.show {{
            opacity: 1;
        }}
        
        .vector-details.expanded {{
            background: linear-gradient(135deg, #fff8f5 0%, #ffffff 100%);
            border-left: 4px solid #ff6b35;
        }}
        
        .session-search {{
            padding: 12px;
            border: 1px solid #e5e5e5;
            border-radius: 6px;
            margin: 16px;
            font-size: 14px;
            transition: border-color 0.2s ease;
        }}
        
        .session-search:focus {{
            outline: none;
            border-color: #ff6b35;
            box-shadow: 0 0 0 2px rgba(255,107,53,0.1);
        }}
        
        .sessions-counter {{
            background: #ff6b35;
            color: white;
            padding: 4px 8px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 600;
            margin-left: auto;
        }}
        
        .sessions-container::-webkit-scrollbar {{
            width: 6px;
        }}
        
        .sessions-container::-webkit-scrollbar-track {{
            background: #f1f1f1;
        }}
        
        .sessions-container::-webkit-scrollbar-thumb {{
            background: #ff6b35;
            border-radius: 3px;
        }}
        
        .vector-details::-webkit-scrollbar {{
            width: 6px;
        }}
        
        .vector-details::-webkit-scrollbar-track {{
            background: #f1f1f1;
        }}
        
        .vector-details::-webkit-scrollbar-thumb {{
            background: #ff6b35;
            border-radius: 3px;
        }}
        
        .empty-state {{
            text-align: center;
            color: #999;
            font-style: italic;
            padding: 32px;
        }}
    </style>
</head>
<body>
    <div class="banner">
        <h1>trmeric</h1>
        <div class="subtitle">Vector Analysis Dashboard</div>
    </div>
    
    <div class="dashboard">
        <div class="left-panel">
            <div class="sessions-header">
                Activity Sessions
                <span class="sessions-counter" id="sessionsCounter">0</span>
            </div>
            <input type="text" class="session-search" id="sessionSearch" placeholder="Search sessions...">
            <div class="sessions-container" id="sessionsContainer">
                <!-- Sessions will be populated by JavaScript -->
            </div>
        </div>
        
        <div class="right-panel">
            <div class="chart-header">
                Vector Usage Comparison
            </div>
            
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-number">{active_vectors}</div>
                    <div class="stat-label">Active Vectors</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{total_entries}</div>
                    <div class="stat-label">Total Entries</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{len(sessions)}</div>
                    <div class="stat-label">Sessions</div>
                </div>
            </div>
            
            <div class="chart-container">
                <div class="chart-wrapper">
                    <canvas id="vectorChart"></canvas>
                </div>
            </div>
            
            <div class="vector-details" id="vectorDetails">
                <h3 id="vectorTitle">
                    <div class="vector-icon" id="vectorIcon"></div>
                    Select a vector to see details
                </h3>
                <p id="vectorDescription">Click on any axis of the radar chart to see detailed insights and which sessions contributed to that vector.</p>
                <div id="vectorInsightContent"></div>
            </div>
        </div>
    </div>

    <!-- Tooltip for enhanced interactions -->
    <div class="tooltip" id="tooltip"></div>

    <!-- Modal for full session content -->
    <div id="sessionModal" style="display:none; position:fixed; top:0; left:0; right:0; bottom:0; background:rgba(0,0,0,0.5); z-index:2000; align-items:center; justify-content:center;">
        <div style="background:white; max-width:800px; width:90%; max-height:80%; overflow:auto; border-radius:8px; padding:24px; position:relative; box-shadow:0 8px 24px rgba(0,0,0,0.3);">
            <button id="modalClose" style="position:absolute; right:16px; top:16px; border:none; background:#ff6b35; color:white; padding:8px 12px; border-radius:4px; cursor:pointer; font-weight:600;">✕</button>
            <h3 id="modalTitle" style="color:#333; margin-bottom:16px; padding-right:40px;">Session Details</h3>
            <div id="modalContent" style="color:#666; line-height:1.6; font-size:14px;"></div>
        </div>
    </div>

    <script>
        // Data from backend
        const vectorData = {json.dumps(vector_counts)};
        const sessions = {json.dumps(sessions)};
        const vectorInsights = {json.dumps(vector_insights)};
        
        // DEBUG: Print data received in frontend
        console.log('DEBUG - Frontend vectorData:', vectorData);
        console.log('DEBUG - Frontend sessions:', sessions);
        console.log('DEBUG - Frontend vectorInsights:', vectorInsights);
        
        const vectorDescriptions = {{
            'Strategy Planning': 'Strategic Planning & Vision - Long-term planning and strategic decision making',
            'Portfolio Management': 'Portfolio Oversight & Management - Managing and optimizing project portfolios',
            'Value Creation': 'Business Impact & Value Creation - Driving business value and measurable outcomes',
            'Execution': 'Project Execution & Implementation - Executing projects and delivering results',
            'Governance': 'Governance & Risk Management - Ensuring compliance and managing risks',
            'Learning': 'Knowledge & Learning Management - Capturing and sharing organizational knowledge'
        }};
        
        // Average CIO usage patterns for comparison
        const avgCioData = {{
            'Strategy Planning': 85,
            'Portfolio Management': 75,
            'Value Creation': 60,
            'Execution': 70,
            'Governance': 80,
            'Learning': 45
        }};
        
        const orangeColors = [
            '#ff6b35', '#f7931e', '#ffab00', '#ffc107', '#ffcc02', '#ffd54f'
        ];
        
        let currentHighlightedVector = null;
        let chart = null;
        let currentView = 'comparison';
        let filteredSessions = [...sessions];
        
        // Initialize the page
        document.addEventListener('DOMContentLoaded', function() {{
            renderSessions();
            renderChart();
            setupInteractivity();
            
            // Set default selected vector (first active one)
            const activeVectors = Object.keys(vectorData).filter(v => vectorData[v] > 0);
            if (activeVectors.length > 0) {{
                setTimeout(() => highlightVector(activeVectors[0]), 500);
            }}
        }});
        
        function setupInteractivity() {{
            // Session search
            const searchInput = document.getElementById('sessionSearch');
            searchInput.addEventListener('input', handleSessionSearch);
            
            // Stat cards hover effects
            document.querySelectorAll('.stat-card').forEach(card => {{
                card.addEventListener('mouseenter', () => {{
                    card.classList.add('pulse-animation');
                }});
                card.addEventListener('mouseleave', () => {{
                    card.classList.remove('pulse-animation');
                }});
            }});
            
            // Add tooltips to session cards
            addSessionTooltips();
        }}
        
        function handleSessionSearch(event) {{
            const searchTerm = event.target.value.toLowerCase();
            
            filteredSessions = sessions.filter(session => 
                session.title.toLowerCase().includes(searchTerm) ||
                session.content.toLowerCase().includes(searchTerm) ||
                session.vectors.some(v => v.toLowerCase().includes(searchTerm))
            );
            
            renderSessions();
            updateSessionsCounter();
        }}
        
        function updateSessionsCounter() {{
            const counter = document.getElementById('sessionsCounter');
            counter.textContent = filteredSessions.length;
            counter.classList.add('pulse-animation');
            setTimeout(() => counter.classList.remove('pulse-animation'), 1000);
        }}
        
        function addSessionTooltips() {{
            document.querySelectorAll('.session-card').forEach(card => {{
                card.addEventListener('mouseenter', showTooltip);
                card.addEventListener('mouseleave', hideTooltip);
                card.addEventListener('mousemove', moveTooltip);
            }});
        }}
        
        function showTooltip(event) {{
            const sessionIndex = event.target.closest('.session-card').dataset.sessionIndex;
            const session = filteredSessions[sessionIndex];
            if (!session) return;
            
            const tooltip = document.getElementById('tooltip');
            const vectorList = session.vectors.join(', ');
            tooltip.innerHTML = `
                <strong>${{session.title}}</strong><br>
                <em>Vectors: ${{vectorList}}</em><br>
                Click to view full content
            `;
            tooltip.classList.add('show');
        }}
        
        function hideTooltip() {{
            document.getElementById('tooltip').classList.remove('show');
        }}
        
        function moveTooltip(event) {{
            const tooltip = document.getElementById('tooltip');
            tooltip.style.left = event.pageX + 10 + 'px';
            tooltip.style.top = event.pageY - 10 + 'px';
        }}
        
        function renderSessions() {{
            const container = document.getElementById('sessionsContainer');
            container.innerHTML = '';
            
            if (filteredSessions.length === 0) {{
                container.innerHTML = '<div class="empty-state">No sessions match your search</div>';
                return;
            }}
            
            filteredSessions.forEach((session, index) => {{
                const sessionDiv = document.createElement('div');
                sessionDiv.className = 'session-card fade-in';
                sessionDiv.setAttribute('data-session-index', index);
                
                const vectorTags = session.vectors.map(v => 
                    `<span class="vector-tag">${{v}}</span>`
                ).join('');
                
                sessionDiv.innerHTML = `
                    <div class="session-title">${{session.title}}</div>
                    <div class="session-content">${{session.content.substring(0, 180)}}...</div>
                    <div class="vector-tags">${{vectorTags}}</div>
                `;
                
                // Add click handler to open full session modal
                sessionDiv.addEventListener('click', () => openSessionModal(session));
                
                container.appendChild(sessionDiv);
                
                // Stagger animation
                setTimeout(() => {{
                    sessionDiv.style.opacity = '1';
                }}, index * 50);
            }});
            
            // Re-add tooltips
            addSessionTooltips();
            updateSessionsCounter();
        }}
        
        function expandSession(sessionElement, session) {{
            const content = sessionElement.querySelector('.session-content');
            const isExpanded = sessionElement.classList.contains('expanded');
            
            if (isExpanded) {{
                content.innerHTML = `${{session.content.substring(0, 180)}}...`;
                sessionElement.classList.remove('expanded');
            }} else {{
                content.innerHTML = session.content;
                sessionElement.classList.add('expanded');
                
                // Smooth scroll to show full content
                setTimeout(() => {{
                    sessionElement.scrollIntoView({{ behavior: 'smooth', block: 'nearest' }});
                }}, 100);
            }}
        }}
        
        function openSessionModal(session) {{
            const modal = document.getElementById('sessionModal');
            const modalTitle = document.getElementById('modalTitle');
            const modalContent = document.getElementById('modalContent');
            
            modalTitle.textContent = session.title || 'Session Details';
            modalContent.innerHTML = (session.content || '').replace(/\\n/g, '<br>');
            
            modal.style.display = 'flex';
            
            // Close button handler
            const closeBtn = document.getElementById('modalClose');
            closeBtn.onclick = () => {{
                modal.style.display = 'none';
            }};
            
            // Close when clicking backdrop
            modal.onclick = (e) => {{
                if (e.target === modal) {{
                    modal.style.display = 'none';
                }}
            }};
            
            // Close on Escape key
            const escapeHandler = (e) => {{
                if (e.key === 'Escape') {{
                    modal.style.display = 'none';
                    document.removeEventListener('keydown', escapeHandler);
                }}
            }};
            document.addEventListener('keydown', escapeHandler);
        }}
        
        function renderChart() {{
            const ctx = document.getElementById('vectorChart').getContext('2d');
            
            const labels = Object.keys(vectorData);
            const userData = Object.values(vectorData);
            
            // Normalize user data to 0-100 scale for better visualization
            const maxUserValue = Math.max(...userData);
            const normalizedUserData = userData.map(val => maxUserValue > 0 ? (val / maxUserValue) * 100 : 0);
            
            // Fake average CIO usage patterns (normalized to 0-100 scale)
            const avgCioDataLocal = {{
                'Strategy Planning': 85,
                'Portfolio Management': 75,
                'Value Creation': 60,
                'Execution': 70,
                'Governance': 80,
                'Learning': 45
            }};
            
            const cioDataValues = labels.map(label => avgCioDataLocal[label] || 50);
            
            chart = new Chart(ctx, {{
                type: 'radar',
                data: {{
                    labels: labels,
                    datasets: [
                        {{
                            label: 'Average CIO Usage',
                            data: cioDataValues,
                            backgroundColor: 'rgba(200, 200, 200, 0.2)',
                            borderColor: 'rgba(150, 150, 150, 0.8)',
                            borderWidth: 2,
                            pointBackgroundColor: 'rgba(150, 150, 150, 0.8)',
                            pointBorderColor: '#fff',
                            pointBorderWidth: 2,
                            pointRadius: 4,
                            pointHoverRadius: 6,
                            pointHoverBackgroundColor: 'rgba(150, 150, 150, 1)',
                            fill: true
                        }},
                        {{
                            label: 'Your Usage',
                            data: normalizedUserData,
                            backgroundColor: 'rgba(255, 107, 53, 0.3)',
                            borderColor: '#ff6b35',
                            borderWidth: 3,
                            pointBackgroundColor: '#ff6b35',
                            pointBorderColor: '#fff',
                            pointBorderWidth: 3,
                            pointRadius: 6,
                            pointHoverRadius: 8,
                            pointHoverBackgroundColor: '#f7931e',
                            fill: true
                        }}
                    ]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: true,
                    plugins: {{
                        legend: {{
                            position: 'bottom',
                            labels: {{
                                color: '#333',
                                font: {{
                                    size: 12,
                                    weight: '500'
                                }},
                                usePointStyle: true,
                                pointStyle: 'circle',
                                padding: 20
                            }}
                        }},
                        tooltip: {{
                            backgroundColor: 'rgba(51,51,51,0.9)',
                            titleColor: 'white',
                            bodyColor: 'white',
                            borderColor: '#ff6b35',
                            borderWidth: 1,
                            cornerRadius: 4,
                            callbacks: {{
                                label: function(context) {{
                                    const datasetLabel = context.dataset.label;
                                    const value = context.parsed.r;
                                    const vectorName = context.label;
                                    
                                    if (datasetLabel === 'Your Usage') {{
                                        const actualValue = vectorData[vectorName] || 0;
                                        return `${{datasetLabel}}: ${{actualValue}} entries (${{value.toFixed(1)}}% normalized)`;
                                    }} else {{
                                        return `${{datasetLabel}}: ${{value.toFixed(1)}}%`;
                                    }}
                                }}
                            }}
                        }}
                    }},
                    scales: {{
                        r: {{
                            beginAtZero: true,
                            max: 100,
                            ticks: {{
                                stepSize: 20,
                                color: '#666',
                                font: {{
                                    size: 10
                                }}
                            }},
                            grid: {{
                                color: 'rgba(200, 200, 200, 0.3)'
                            }},
                            angleLines: {{
                                color: 'rgba(200, 200, 200, 0.3)'
                            }},
                            pointLabels: {{
                                color: '#333',
                                font: {{
                                    size: 11,
                                    weight: '600'
                                }}
                            }}
                        }}
                    }},
                    onClick: (event, elements) => {{
                        if (elements.length > 0) {{
                            const elementIndex = elements[0].index;
                            const vectorName = labels[elementIndex];
                            highlightVector(vectorName);
                        }}
                    }},
                    onHover: (event, elements) => {{
                        event.native.target.style.cursor = elements.length > 0 ? 'pointer' : 'default';
                        
                        // Add glow effect on hover
                        if (elements.length > 0) {{
                            const canvas = event.chart.canvas;
                            canvas.style.filter = 'drop-shadow(0 0 10px rgba(255,107,53,0.3))';
                        }} else {{
                            const canvas = event.chart.canvas;
                            canvas.style.filter = 'none';
                        }}
                    }}
                }}
            }});
        }}
        
        function highlightVector(vectorName) {{
            // Clear previous highlights with animation
            document.querySelectorAll('.session-card').forEach(card => {{
                card.classList.remove('highlighted');
                card.style.transition = 'all 0.3s ease';
            }});
            
            // Highlight sessions related to this vector with staggered animation
            let delay = 0;
            filteredSessions.forEach((session, index) => {{
                if (session.vectors.includes(vectorName)) {{
                    const sessionCard = document.querySelector(`[data-session-index="${{index}}"]`);
                    if (sessionCard) {{
                        setTimeout(() => {{
                            sessionCard.classList.add('highlighted');
                        }}, delay);
                        delay += 50;
                    }}
                }}
            }});
            
            // Update vector details with enhanced animations
            const vectorTitle = document.getElementById('vectorTitle');
            const vectorDescription = document.getElementById('vectorDescription');
            const vectorInsightContent = document.getElementById('vectorInsightContent');
            const vectorIcon = document.getElementById('vectorIcon');
            const vectorDetails = document.getElementById('vectorDetails');
            
            // Add expansion effect
            vectorDetails.classList.add('expanded');
            
            // Set icon color based on vector
            const vectorIndex = Object.keys(vectorData).indexOf(vectorName);
            vectorIcon.style.background = orangeColors[vectorIndex] || '#ff6b35';
            
            vectorTitle.innerHTML = `
                <div class="vector-icon" style="background: ${{orangeColors[vectorIndex] || '#ff6b35'}}"></div>
                ${{vectorName}}
            `;
            
            vectorDescription.textContent = vectorDescriptions[vectorName] || 'No description available';
            
            // Enhanced insights with comparison bars
            const insight = vectorInsights[vectorName];
            const userValue = vectorData[vectorName] || 0;
            const cioValue = avgCioData[vectorName] || 50;
            const comparison = userValue > 0 ? ((userValue / Math.max(...Object.values(vectorData))) * 100).toFixed(1) : 0;
            const difference = comparison - cioValue;
            const comparisonText = difference > 10 ? 'significantly above' : 
                                 difference > 0 ? 'above' : 
                                 difference > -10 ? 'near' : 'below';
            
            let insightHtml = `
                <div class="insight-content">
                    <strong>Usage Comparison:</strong><br>
                    Your usage: <span class="animated-number">${{userValue}}</span> entries (<span class="animated-number">${{comparison}}</span>% normalized)<br>
                    Average CIO: <span class="animated-number">${{cioValue}}</span>%<br>
                    <div class="vector-comparison-bar">
                        <div class="comparison-fill" style="width: ${{Math.min(comparison, 100)}}%"></div>
                    </div>
                    <span style="color: ${{difference > 0 ? '#28a745' : difference < -10 ? '#dc3545' : '#6c757d'}}">
                        You are <strong>${{comparisonText}}</strong> average CIO usage
                        ${{Math.abs(difference) > 5 ? ` by ${{Math.abs(difference).toFixed(1)}} points` : ''}}
                    </span>
                </div>
            `;
            
            if (insight) {{
                insightHtml += `
                    <div class="insight-content" style="margin-top: 12px;" onclick="toggleInsightExpansion(this)">
                        <strong>AI Insights:</strong><br>
                        <div class="insight-text">${{insight.substring(0, 300)}}${{insight.length > 300 ? '... <em style="color: #ff6b35; cursor: pointer;">[Click to expand]</em>' : ''}}</div>
                        <div class="insight-full" style="display: none;">${{insight}}</div>
                    </div>
                `;
            }} else if (userValue === 0) {{
                insightHtml += `
                    <div class="insight-content" style="margin-top: 12px;">
                        <strong>Opportunity:</strong><br>
                        <em>No activity recorded for this vector. Consider focusing on this area to align with typical CIO usage patterns.</em>
                    </div>
                `;
            }}
            
            vectorInsightContent.innerHTML = insightHtml;
            
            // Animate the numbers
            animateNumbers();
            
            currentHighlightedVector = vectorName;
        }}
        
        function toggleInsightExpansion(element) {{
            const shortText = element.querySelector('.insight-text');
            const fullText = element.querySelector('.insight-full');
            
            if (fullText.style.display === 'none') {{
                shortText.style.display = 'none';
                fullText.style.display = 'block';
                fullText.style.animation = 'fadeIn 0.3s ease';
            }} else {{
                shortText.style.display = 'block';
                fullText.style.display = 'none';
            }}
        }}
        
        function animateNumbers() {{
            document.querySelectorAll('.animated-number').forEach(num => {{
                num.classList.add('pulse-animation');
                setTimeout(() => num.classList.remove('pulse-animation'), 1000);
            }});
        }}
        
        // Click outside to clear highlights
        document.addEventListener('click', function(e) {{
            if (!e.target.closest('.chart-wrapper') && !e.target.closest('.session-card')) {{
                // Don't clear highlights when clicking outside - keep current selection
            }}
        }});
    </script>
</body>
</html>"""
        
        return html_content
        
        # Convert markdown content to HTML with enhanced styling
        lines = markdown_content.split('\n')
        in_code_block = False
        
        for line in lines:
            if line.startswith('```'):
                if in_code_block:
                    html_lines.append("        </pre>")
                    in_code_block = False
                else:
                    html_lines.append("        <pre>")
                    in_code_block = True
                continue
            
            if in_code_block:
                html_lines.append(f"            {line}")
                continue
                
            # Convert markdown elements to styled HTML
            if line.startswith('# '):
                html_lines.append(f"        <div class='header'><h1>{line[2:]}</h1></div>")
                html_lines.append("        <div class='content'>")
            elif line.startswith('## Executive Summary'):
                html_lines.append("        <div class='executive-summary'>")
                html_lines.append(f"            <h2>{line[3:]}</h2>")
            elif line.startswith('## '):
                if 'executive-summary' in ''.join(html_lines[-5:]):
                    html_lines.append("        </div>")
                html_lines.append(f"        <h2>{line[3:]}</h2>")
            elif line.startswith('### 🔹'):
                vector_name = line[7:]
                active_class = 'vector-active' if any(word in vector_name.lower() for word in ['strategy', 'portfolio']) else 'vector-inactive'
                html_lines.append(f"        <div class='vector-card {active_class}'>")
                html_lines.append(f"            <h3><span class='emoji'>🔹</span>{vector_name}</h3>")
            elif line.startswith('### 🔸'):
                html_lines.append("        <div class='insight-section'>")
                html_lines.append(f"            <h3><span class='emoji'>🔸</span>{line[7:]}</h3>")
            elif line.startswith('### Session'):
                html_lines.append("        <div class='activity-session'>")
                html_lines.append(f"            <h3>{line[4:]}</h3>")
            elif line.startswith('- **Total Vector Entries:**'):
                # Start metrics section
                html_lines.append("        <div class='metrics'>")
                number = line.split('**')[2].strip()
                html_lines.append(f"            <div class='metric-card'><div class='metric-number'>{number}</div><div class='metric-label'>Total Vector Entries</div></div>")
            elif line.startswith('- **Total Activities:**'):
                number = line.split('**')[2].strip()
                html_lines.append(f"            <div class='metric-card'><div class='metric-number'>{number}</div><div class='metric-label'>Total Activities</div></div>")
            elif line.startswith('- **Active Vectors:**'):
                number = line.split('**')[2].strip()
                html_lines.append(f"            <div class='metric-card'><div class='metric-number'>{number}</div><div class='metric-label'>Active Vectors</div></div>")
            elif line.startswith('- **Vectors with Activity:**'):
                number = line.split('**')[2].strip()
                html_lines.append(f"            <div class='metric-card'><div class='metric-number'>{number}</div><div class='metric-label'>Vectors with Activity</div></div>")
                html_lines.append("        </div>")
            elif line.startswith('**Top Performing Vectors:**'):
                html_lines.append(f"        <h4>{line}</h4>")
            elif line.startswith('- 📅'):
                html_lines.append(f"        <p><span class='date-badge'>📅 {line[4:]}</span></p>")
            elif line.startswith('**') and line.endswith('**') and len(line) > 4:
                html_lines.append(f"        <h4>{line[2:-2]}</h4>")
            elif line.startswith('*') and line.endswith('*'):
                html_lines.append(f"        <p><em>{line[1:-1]}</em></p>")
            elif line.strip() == '---':
                html_lines.append("        <hr>")
            elif line.strip():
                html_lines.append(f"        <p>{line}</p>")
            else:
                # Close any open divs on empty lines in certain contexts
                if 'vector-card' in ''.join(html_lines[-3:]) or 'insight-section' in ''.join(html_lines[-3:]) or 'activity-session' in ''.join(html_lines[-3:]):
                    html_lines.append("        </div>")
                html_lines.append("        <br>")
        
        # Close any remaining open divs and add footer
        html_lines.extend([
            "        </div>",
            "        <div class='footer'>",
            f"            <p>Report generated by Trmeric Vector Analysis System on {datetime.now().strftime('%Y-%m-%d at %H:%M:%S')}</p>",
            "        </div>",
            "    </div>",
            "</body>",
            "</html>"
        ])
        
        return '\n'.join(html_lines)


def generate_vector_period_report(tenant_id: int, days: float = 7.0, user_id: Optional[int] = None) -> str:
    """
    Generate a comprehensive vector analysis report for a time period
    
    Args:
        tenant_id: The tenant ID
        days: Number of days to analyze (default: 7)
        user_id: Optional user ID filter
        
    Returns:
        Path to the generated markdown report file
    """
    try:
        visualizer = VectorVisualization(tenant_id)
        report_content = visualizer.generate_time_period_report(days, user_id)
        
        # Get vector data for HTML generation
        vector_data = get_vector_counts_by_category(
            days=days,
            tenant_id=tenant_id,
            user_id=user_id
        )
        
        # Save to file  
        report_path = visualizer._save_report_to_file(f"tenant_{tenant_id}_days_{days}", report_content, vector_data, days, user_id)
        
        appLogger.info({
            "event": "generate_vector_period_report_complete",
            "tenant_id": tenant_id,
            "days": days,
            "user_id": user_id,
            "report_path": report_path
        })
        
        return report_path
        
    except Exception as e:
        appLogger.error({
            "event": "generate_vector_period_report_error",
            "tenant_id": tenant_id,
            "error": str(e),
            "traceback": traceback.format_exc()
        })
        return f"Error generating report: {str(e)}"
