### src/trmeric_services/agents/reports/customers/pf/monthly_savings/data.py


## Fetch Data for monthly savings


from src.trmeric_database.Database import db_instance
from src.trmeric_services.integration.IntegrationService import IntegrationService
from src.trmeric_database.dao import ProjectsDaoV2
from typing import List, Dict, Optional
from datetime import datetime
from dateutil.parser import parse
from collections import defaultdict, OrderedDict
from src.trmeric_api.logging.AppLogger import appLogger


def fetchDataForMonthlySavingsAndAnalysis(program_ids: List[int], tenant_id: int, user_id: int) -> Dict:
    """
    Fetch and aggregate monthly savings data for projects under specified program IDs, grouped by program names.
    Includes Table 2 data with cumulative savings calculations and program totals.
    
    Args:
        program_ids (List[int]): List of program IDs to filter projects.
        tenant_id (int): Tenant ID for filtering projects.
        user_id (int): User ID for integration service authentication.
    
    Returns:
        Dict: Aggregated savings data formatted for monthly savings report, matching prompt.py expectations.
    """
    try:
        # Step 1: Fetch project data
        projection_attrs = [
            "id", "title", "program_id", "program_name", 
            "project_category", "project_budget", "start_date", "end_date"
        ]
        print("fetchDataForMonthlySavingsAndAnalysis ---- ", projection_attrs)
        project_data = ProjectsDaoV2.fetchProjectsDataWithProjectionAttrs(
            program_id=None,
            projection_attrs=projection_attrs,
            tenant_id=tenant_id,
            include_archived=False
        )

        # Filter projects by program_ids
        project_data = [
            project for project in project_data 
            if project.get("program_id") in program_ids
        ]
        project_ids = [project["id"] for project in project_data]
        
        print("fetchDataForMonthlySavingsAndAnalysis  project_ids---- ", project_ids)

        if not project_ids:
            return {
                "status": "error",
                "message": "No projects found for the specified program IDs",
                "data": {}
            }

        # Create lookups for program_id to program_name and project_id to program_id
        program_name_map = {project["program_id"]: project.get("program_name", "Unknown") for project in project_data}
        project_program_map = {project["id"]: project["program_id"] for project in project_data}

        # Step 2: Fetch integration data from Google Sheets
        integration_data = IntegrationService().fetchProjectDataforAllIntegration(
            tenant_id=tenant_id,
            user_id=user_id,
            integration_type="drive",
            project_ids=project_ids
        )

        # Step 3: Aggregate savings by month and program name
        monthly_savings = defaultdict(lambda: defaultdict(lambda: {"savings": 0.0, "projects": set()}))  # {month: {program_name: {"savings": float, "projects": set}}}
        total_possible_savings = 0.0

        for project_id, items in integration_data.items():
            project_id = int(project_id)
            if project_id not in project_ids:
                continue

            program_id = project_program_map.get(project_id)
            if not program_id:
                continue
            program_name = program_name_map.get(program_id, "Unknown")

            for item in items:
                integration_item = item.get("integration_data", {})
                forecasted_savings = float(integration_item.get("forecasted savings usd", 0) or 0)
                savings_date = integration_item.get("forecasted savings date")

                # Parse savings date to month (format as "Jul" for 2025, "Jan" for 2026)
                month = "No date"
                if savings_date:
                    try:
                        parsed_date = parse(savings_date)
                        if parsed_date.year == 2025:
                            month = parsed_date.strftime("%b")
                        elif parsed_date.year == 2026 and parsed_date.month == 1:
                            month = "Jan"
                    except (ValueError, TypeError):
                        pass

                # Aggregate savings and track unique projects
                monthly_savings[month][program_name]["savings"] += forecasted_savings
                monthly_savings[month][program_name]["projects"].add(project_id)
                total_possible_savings += forecasted_savings
                
                print("debug-------", project_id, program_id, program_name, month, forecasted_savings)

        # Step 4: Format data for prompt.py
        expected_months = ["No date", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "Jan"]  # Jul-Dec 2025, Jan 2026
        program_names = list(set(program_name_map.values()))
        snapshot_data = {
            "programs": {program_name: {} for program_name in program_names},
            "program_totals": {program_name: {"savings": 0.0, "projects": set()} for program_name in program_names},
            "total_possible_savings": round(total_possible_savings, 2),
            "table2_data": []
        }

        # Step 5: Populate programs data for Table 1 and program totals
        for month in expected_months:
            for program_name in program_names:
                savings = monthly_savings[month][program_name]["savings"]
                project_count = len(monthly_savings[month][program_name]["projects"])
                snapshot_data["programs"][program_name][month] = {
                    "savings": round(savings, 2),
                    "projects": project_count
                }
                # Update program totals
                snapshot_data["program_totals"][program_name]["savings"] += savings
                snapshot_data["program_totals"][program_name]["projects"].update(monthly_savings[month][program_name]["projects"])

        # Convert project sets to counts in program_totals
        for program_name in program_names:
            snapshot_data["program_totals"][program_name]["projects"] = len(snapshot_data["program_totals"][program_name]["projects"])
            snapshot_data["program_totals"][program_name]["savings"] = round(snapshot_data["program_totals"][program_name]["savings"], 2)

        # Step 6: Compute Table 2 data with cumulative savings
        month_multipliers = OrderedDict([
            ("Jul", 7),  # Jul 2025 to Jan 2026
            ("Aug", 6),  # Aug 2025 to Jan 2026
            ("Sep", 5),  # Sep 2025 to Jan 2026
            ("Oct", 4),  # Oct 2025 to Jan 2026
            ("Nov", 3),  # Nov 2025 to Jan 2026
            ("Dec", 2),  # Dec 2025 to Jan 2026
            ("Jan", 1)   # Jan 2026
        ])

        # Initialize Table 2 data
        table2_data = []
        cumulative_dated_savings = 0.0
        cumulative_dated_cumulative_savings = 0.0
        cumulative_dated_projects = 0

        for month in expected_months:
            # Sum savings and projects across programs
            monthly_savings_total = sum(
                snapshot_data["programs"][program_name].get(month, {}).get("savings", 0.0)
                for program_name in program_names
            )
            project_count = sum(
                snapshot_data["programs"][program_name].get(month, {}).get("projects", 0)
                for program_name in program_names
            )

            # Calculate cumulative savings
            cumulative_savings = monthly_savings_total
            if month in month_multipliers:
                cumulative_savings = monthly_savings_total * month_multipliers[month]

            # Add to Table 2
            table2_data.append({
                "month": month,
                "monthly_savings": round(monthly_savings_total, 2),
                "cumulative_savings": round(cumulative_savings, 2),
                "project_count": project_count
            })

            if month in month_multipliers:
                cumulative_dated_savings += monthly_savings_total
                cumulative_dated_cumulative_savings += cumulative_savings
                cumulative_dated_projects += project_count

        # Add "Cumulative dated" row
        table2_data.append({
            "month": "Cumulative dated",
            "monthly_savings": round(cumulative_dated_savings, 2),
            "cumulative_savings": round(cumulative_dated_cumulative_savings, 2),
            "project_count": cumulative_dated_projects
        })

        snapshot_data["table2_data"] = table2_data

        # Step 7: Validate data
        dated_savings_sum = sum(
            snapshot_data["programs"][program_name][month]["savings"]
            for program_name in program_names
            for month in expected_months[1:]  # Exclude "No date"
        )
        no_date_savings = sum(
            snapshot_data["programs"][program_name]["No date"]["savings"]
            for program_name in program_names
        )
        calculated_total = round(dated_savings_sum + no_date_savings, 2)
        program_totals_sum = sum(
            snapshot_data["program_totals"][program_name]["savings"]
            for program_name in program_names
        )
        if abs(calculated_total - snapshot_data["total_possible_savings"]) > 0.01 or \
           abs(program_totals_sum - snapshot_data["total_possible_savings"]) > 0.01:
            appLogger.warning({
                "function": "fetchDataForMonthlySavingsAndAnalysis",
                "message": "Total savings mismatch",
                "data": {
                    "calculated_total": calculated_total,
                    "program_totals_sum": program_totals_sum,
                    "total_possible_savings": snapshot_data["total_possible_savings"]
                }
            })

        return {
            "status": "success",
            "data": snapshot_data
        }

    except Exception as e:
        appLogger.error({
            "function": "fetchDataForMonthlySavingsAndAnalysis",
            "error": str(e),
            "data": {
                "program_ids": program_ids,
                "tenant_id": tenant_id,
                "user_id": user_id
            }
        })
        return {
            "status": "error",
            "message": str(e),
            "data": {}
        }
        