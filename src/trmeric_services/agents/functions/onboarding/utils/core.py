import re
import os
import json
import datetime
import traceback
from dateutil import parser
from src.trmeric_api.logging.AppLogger import appLogger



class OnboardingAgentUtils:
    def __init__(self):
        # budget calculation 
        # available role calculation
        # team role data
        pass
    
    
    def calculate_non_labour_budget_from_team(self,team):
        """
        Calculate the non-labour cost by summing the estimate_value of each team entry with labour_type equal to 2.
        """
        total_non_labour_cost = 0
        for item in team:
            if item.get('labour_type') == 2:
                try:
                    estimate_value = float(item.get('estimate_value', 0))
                except (ValueError, TypeError):
                    estimate_value = 0
                total_non_labour_cost += estimate_value
        print("--debug in calculate_non_labour_budget_from_team--", total_non_labour_cost)
        return total_non_labour_cost

    def calculate_labour_budget_from_roles(self,recommended_roles):
        """
        Calculate total labour cost from recommended project roles.
        Each role should have:
        - approximate_rate: USD/hour (string or number)
        - allocation: a percentage (e.g., '100%' or 100)
        - suggested_frequency: number of individuals
        - timeline: a list of segments with start_date and end_date.
        
        For each timeline segment, cost = approximate_rate * 8 hours * number_of_weekdays *(allocation/100) * suggested_frequency.
        """
        try:
            total_labour_cost = 0
            for role in recommended_roles:
                # Get the approximate rate (USD/hour)
                try:
                    approximate_rate = float(role.get('approximate_rate', 0))
                except (ValueError, TypeError):
                    approximate_rate = 0

                # Parse allocation, which might be a string like "100%" or a number.
                allocation_val = role.get('allocation', 0)
                try:
                    if isinstance(allocation_val, str) and allocation_val.endswith('%'):
                        allocation = float(allocation_val.rstrip('%'))
                    else:
                        allocation = float(allocation_val)
                except (ValueError, TypeError):
                    allocation = 0

                # Number of individuals in this role
                suggested_frequency = role.get('suggested_frequency', 1)
                timeline_segments = role.get('timeline', [])

                # For each timeline segment, calculate the cost
                for segment in timeline_segments:
                    seg_start = segment.get('start_date', '')
                    seg_end = segment.get('end_date', '')
                    if seg_start and seg_end:
                        no_days = self.get_weekdays_between_dates(seg_start, seg_end)
                        cost = approximate_rate * 8 * no_days * (allocation / 100.0)
                        total_labour_cost += cost
            print("--debug in calculate_labour_budget_from_roles--", total_labour_cost)
            return total_labour_cost
        
        except Exception as e:
            appLogger.error({"event":"calculate_labour_budget_from_roles","error":e,"traceback": traceback.format_exc()})
            return 0

    def calculate_available_roles(self, all_roles_count_master_data,all_roles_consumed_for_tenant):
        """
            Computes available roles by subtracting the total roles consumed from the master role count for a given tenant, ensuring no negative values.
        """
        
        master_data_dict = {role["role"]: role["total_count"] for role in all_roles_count_master_data}
        allocated_roles_dict = {role["role"]: role["allocated_count"] for role in all_roles_consumed_for_tenant}

        # Get all unique roles from both datasets
        all_roles = set(master_data_dict.keys()).union(set(allocated_roles_dict.keys()))

        # Compute available roles ensuring no negative values
        available_roles = {}
        for role in all_roles:
            total_count = master_data_dict.get(role, 0)  # Default to 0 if role is missing
            allocated_count = allocated_roles_dict.get(role, 0)  # Default to 0 if role is missing
            available_roles[role] = max(total_count - allocated_count, 0)  # Ensure non-negative

        return available_roles
    
    def transform_role_data(self, role_data):
        transformed = []
        
        for timeline_entry in role_data.get("timeline", []):
            # print("------", role_data )
            allocation_str = role_data.get("allocation", "")
            if isinstance(allocation_str, str):
                # Extract number from string like '45%'
                allocation_number = int(re.findall(r'\d+', allocation_str)[0]) if re.findall(r'\d+', allocation_str) else 0
            elif isinstance(allocation_str, int):
                allocation_number = allocation_str
            else:
                # Default
                allocation_number = 75
            # allocation_number = int(re.findall(r'\d+', allocation_str)[0]) if re.findall(r'\d+', allocation_str) else 0
            # print("---deubg allocation_number---", allocation_number)
            transformed.append({
                "labour_type": 1,
                "name": role_data.get("name", ""),
                "description": role_data.get("description", ""),
                "allocation": allocation_number,
                "suggested_frequency": role_data.get("suggested_frequency") or 0,
                "location": role_data.get("location"),
                "tango_analysis": {
                    "insight": role_data.get("insight"),
                    "availability": role_data.get("availability"),
                    "label": role_data.get("label")
                },                
                "start_date": timeline_entry.get("start_date", ""),
                "end_date": timeline_entry.get("end_date", ""),
                "estimate_value": role_data.get("approximate_rate", "")
            })
        
        return transformed
    
    def get_weekdays_between_dates(self,start_date_str, end_date_str, date_format='%Y-%m-%d'):
        """Calculate the number of weekdays (Monday-Friday) between two dates."""
        try:
            start = parser.parse(start_date_str).date()
            end = parser.parse(end_date_str).date()
            
            count = 0
            current = start
            while current <= end:
                if current.weekday() < 5:  # Monday = 0, Friday = 4
                    count += 1
                current += datetime.timedelta(days=1)
                
            # print("\n--debug in get_weekdays_between_dates--", count)
            return count
        except Exception as e:
            print(f"Error in get_weekdays_between_dates: {e}")
            appLogger.error({"event":"get_weekdays_between_dates","error":e,"traceback": traceback.format_exc()})
            return 0

    
