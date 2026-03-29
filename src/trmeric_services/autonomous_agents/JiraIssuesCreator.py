
from src.trmeric_ml.llm.Types import ModelOptions
from src.trmeric_ml.llm.models.OpenAIClient import ChatGPTClient
from src.trmeric_database.dao.projects import ProjectsDao
from src.trmeric_services.autonomous_agents.BaseAutonomousIssueCreatorService import BaseAutonomousIssueCreatorService
from src.trmeric_services.autonomous_agents.Prompts import *
import json
from src.trmeric_utils.json_parser import *
import traceback


class JiraIssuesCreatorService(BaseAutonomousIssueCreatorService):

    def __init__(self, tenant_id, user_id):
        super().__init__(tenant_id, user_id)

    def startProcess(self, project_ids):
        print("in start process")
        # result = None

        for p_id in project_ids:
            # 1. fetch project description, objectives, key results
            # 2. find major compoennts: milestones for the project
            try:
                project_data = ProjectsDao.fetchProjectDetailsForIssueCreation(
                    project_id=p_id
                )

                print("debug -- ", project_data)

                milestones_and_tasks_breakdown = self.llm.run(
                    MilestonesAndTasksBreakdownPrompt(
                        project_data
                    ),
                    self.modelOptions,
                    "jira_issue_creator::create_milestones_and_tasks_breakdown",
                    self.logInfo
                )

                with open(self.milestones_and_tasks_breakdown_file_path, 'w') as json_file:
                    json.dump(extract_json_after_llm(
                        milestones_and_tasks_breakdown), json_file, indent=4)

                return milestones_and_tasks_breakdown

            except Exception as e:
                print("error in startProcess issues --- ",
                      e, traceback.format_exc())

    def updateMilestoneAndTaskBreakDown(self, user_input):
        try:
            old_milestones_and_tasks_breakdown = self.fetchMilestonesAndTaskBreakdownData()
            jira_issues = self.llm.run(
                UpdateMilestonesAndTasksBreakdownPrompt(
                    milestones_and_tasks_breakdown=old_milestones_and_tasks_breakdown,
                    user_input=user_input
                ),
                self.modelOptionsFast,
                "jira_issue_creator::update_milestones_and_tasks_breakdown",
                self.logInfo
            )
            json_data = extract_json_after_llm(
                jira_issues
            )

            with open(self.milestones_and_tasks_breakdown_file_path, 'w') as json_file:
                json.dump(json_data, json_file, indent=4)

            return jira_issues

        except Exception as e:
            print("error in updateMilestoneAndTaskBreakDown issues --- ",
                  e, traceback.format_exc())

    def fetchMilestonesAndTaskBreakdownData(self):
        old_milestones_and_tasks_breakdown = ''
        with open(self.milestones_and_tasks_breakdown_file_path, 'r') as json_file:
            old_milestones_and_tasks_breakdown = json.load(json_file)
        return json.dumps(old_milestones_and_tasks_breakdown)

    # def fetchUpdatedMilestonesAndTaskBreakdownData(self):
    #     old_milestones_and_tasks_breakdown = ''
    #     with open(self.updated_milestones_and_tasks_breakdown_file_path, 'r') as json_file:
    #         old_milestones_and_tasks_breakdown = json.load(json_file)
    #     return json.dumps(old_milestones_and_tasks_breakdown)

    def fetchJiraIssues(self):
        jira_issues = ''
        with open(self.jira_issues_file_path, 'r') as json_file:
            jira_issues = json.load(json_file)
        return json.dumps(jira_issues)

    def createIssuesData(self, milestones_and_tasks_breakdown):
        try:
            old_milestones_and_tasks_breakdown = self.fetchMilestonesAndTaskBreakdownData()
            context = old_milestones_and_tasks_breakdown + \
                "\n\n changes suggessted by user: \n" + \
                "<changes_suggessted_by_user>\n" + \
                milestones_and_tasks_breakdown + "\n" + \
                "<changes_suggessted_by_user>\n"
            jira_issues = self.llm.run(
                CreateJiraIssuesPrompt(
                    context
                ),
                self.modelOptions,
                "jira_issue_creator::create_jira_issues",
                self.logInfo
            )
            print("debug here .. jira issues", jira_issues)
            json_data = extract_json_after_llm(
                jira_issues
            )

            with open(self.jira_issues_file_path, 'w') as json_file:
                json.dump(json_data, json_file, indent=4)

            # with open(self.updated_milestones_and_tasks_breakdown_file_path, 'w') as json_file:
            #     json.dump(context, json_file, indent=4)

            return jira_issues

        except Exception as e:
            print("error in createIssuesData issues --- ",
                  e, traceback.format_exc())

    def updateIssuesData(self, user_changes):
        try:
            old_milestones_and_tasks_breakdown = self.fetchMilestonesAndTaskBreakdownData()
            issues = self.fetchJiraIssues()
            jira_issues = self.llm.run(
                UpdateJiraIssuesPrompt(
                    milestones_and_tasks_breakdown=old_milestones_and_tasks_breakdown,
                    jira_issues=issues,
                    user_changes=user_changes
                ),
                self.modelOptionsFast,
                "jira_issue_creator::update_jira_issues",
                self.logInfo
            )
            print("debug here .. updated jira issues", jira_issues)
            json_data = extract_json_after_llm(
                jira_issues
            )

            with open(self.jira_issues_file_path, 'w') as json_file:
                json.dump(json_data, json_file, indent=4)

            return jira_issues

        except Exception as e:
            print("error in createIssuesData issues --- ",
                  e, traceback.format_exc())

    def createEpicsAndSave(self):
        try:
            old_milestones_and_tasks_breakdown = self.fetchMilestonesAndTaskBreakdownData()
            issues = self.fetchJiraIssues()
            jira_epics = self.llm.run(
                CreateEpicsPrompt(
                    milestones_and_tasks_breakdown=old_milestones_and_tasks_breakdown,
                    jira_issues=issues,
                ),
                self.modelOptions,
                "jira_issue_creator::create_jira_epics",
                self.logInfo
            )
            json_data = extract_json_after_llm(
                jira_epics
            )

            with open(self.jira_epics_file_path, 'w') as json_file:
                json.dump(json_data, json_file, indent=4)

            return jira_epics

        except Exception as e:
            print(
                "error in createEpicsAndSave issues --- ", e
            )
