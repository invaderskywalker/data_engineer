
import re
import json
import traceback
import sys
import sys
sys.path.append('/home/ubuntu/trmeric-ai') 
from calendar import monthrange
from datetime import datetime, timezone, timedelta
from src.trmeric_utils.api.main import ApiUtils
from src.trmeric_api.logging.AppLogger import appLogger, debugLogger
from src.trmeric_database.dao import ProjectsDaoV2,AuthDao, NotificationDao, InsightDao, JobDAO, RoadmapDao
from src.trmeric_services.signals import *

ALL_ROLES = [
    "org_admin",
    "org_leader",
    "org_portfolio_leader",
    "org_project_manager",
    "org_member",
    "org_demand_requestor",
    "org_demand_manager",
    "org_resource_manager",
    "org_solution_leader",
    "org_sponsor_approver",
    "org_only_discovery",
    "external_customer",
    # "provider_org_admin",
]

def email_content(user_name: str, project_name: str, pending_text: str='') -> str:
    today = datetime.now().strftime("%b %d, %Y")
    print("--debug today--", today)
    debugLogger.info(f"Email reminder generated on {today}")

    content = f"""
        <div style="font-family: Arial, sans-serif; font-size:14px;">
            <p>Hi {user_name},</p>

            <p>
                This is a gentle reminder that the following update is pending for your project
                <strong>{project_name}</strong>:
            </p>

            <p>
                <strong>{pending_text} (Milestone Updates) not done yet</strong>
            </p>

            <p>
                As of {today}, this update has not been submitted within the current reporting window.
            </p>
            <p>
                Please take a moment to review and update your project status.
            </p>
            <p>
                If you’ve already completed the update, you can safely ignore this message.
            </p>
            <p class="footer">
                Thank you for keeping project status up to date on trmeric.
            </p>
        </div>
    """
    return content

class AlertCreator:
    """
    Daily cron service to remind PMs to update project status

    AI should autonomously generate a Signal that should be visible in Signals section, an app notification and an email notification 
    to the Project manager of the project at the end of every month reminding him to update the status of the project on trmeric 
    if its not updated by the threshold date of a particular month - this has to be checked every month and the signals and reminders 
    should go to the respective Project Manager only if not update beyonf the threshold date on a dialy basis until he updates the project. 
    
    The threshold date should be 18th of every month
    """
    def __init__(self, tenant_id:int, threshold_day: int = 18):
        self.tenant_id = tenant_id
        self.threshold_day = threshold_day

        self.window_before = 3
        self.window_after = 2
        self.weekend_days = {5, 6}   # Saturday, Sunday week days(0=Mon ... 6=Sun)
        self.holidays = set()

    def _is_working_day(self, dt):
        res = dt.weekday() not in self.weekend_days and dt.date() not in self.holidays
        print("--debug _is_working_day------", res)
        return res

    def _shift_working_days(self, start_date, shift):
        try:
            step = 1 if shift > 0 else -1
            remaining = abs(shift)
            current = start_date

            while remaining > 0:
                current += timedelta(days=step)
                if self._is_working_day(current):
                    remaining -= 1

            return current
        except Exception as e:
            print("error workingdays------", str(e))
            return None

    def _pending_update_text(self, scope, schedule):
        if scope and schedule:
            return "Scope status and Schedule status"
        if scope:
            return "Scope status"
        if schedule:
            return "Schedule status"
        return "Project Status Update"
        
    def _get_update_window(self, now):
        try:
            year = now.year
            month = now.month
            last_day = monthrange(year, month)[1]
            print("--deug yesar, month getupdatewoindo-------", year,month,last_day)

            month_end = datetime(year, month, last_day,tzinfo=timezone.utc)

            start = self._shift_working_days(month_end,-self.window_before)
            end = self._shift_working_days(month_end,self.window_after)

            start = start.replace(hour=0, minute=0, second=0, microsecond=0)
            end = end.replace(hour=23, minute=59, second=59)
            debugLogger.info(f"Updated window for {month} {year}: {start} to {end}")
            return start, end
        except Exception as e:
            print("--edeug window error------", e)
            return None, None

    def parse_ts(self,ts: str) -> datetime:
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            from dateutil.parser import isoparse
            return isoparse(ts)


    def _create_signal(self, user_id: int, project_name: str, threshold_date: datetime, pending_text:str):
        """
        Idempotency:
        - ONE reminder signal per project per PM per day
        - If signal exists today → DO NOTHING
        """
        try:
            today_start = datetime.now(timezone.utc).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            existing_signals = InsightDao.fetchSignalsWithProjectionAttrs(
                tenant_id=self.tenant_id,
                projection_attrs=["id"],
                user_id=user_id,
                type_="project",
                tag="Status Reminder",
                head_text=f"Action Required : {project_name}",
                # created_after=threshold_date,
                created_after = today_start,
            )

            if existing_signals:
                debugLogger.info(f"--debug signal already exists--- {existing_signals}")
                return False  # already created_today

            result = InsightDao.insert_signal(
                user_id=user_id,
                tenant_id=self.tenant_id,
                type_="project",
                tag="Status Reminder",
                head_text=f"Action Required : {project_name}",
                label_text=f"{pending_text} pending for your project {project_name} for this month.",
                # label_text=f"Project status update pending for your project {project_name} for this month. Please update the latest status.",
                details_text="Please update the status of this project.",
                details_highlight_text=json.dumps([
                    {
                        "key": "Pending Update",
                        "value": f"since {threshold_date.strftime('%b. %d, %Y')}"
                    }
                ]),
                state=1,
            )
            return result

        except Exception as e:
            appLogger.error({"function": "_create_signal","error": str(e),"traceback": traceback.format_exc(),'tenant_id': self.tenant_id})
            return False
    
    def _create_notification(self,user_id: int,project_id: int,project_name: str,threshold_date: datetime, pending_text:str):
        try:
            # exists = NotificationDao.notification_exists_after_threshold(
            exists = NotificationDao.notification_exists_today(
                tenant_id=self.tenant_id,
                user_id=user_id,
                notification_type="PROJECT_STATUS_REMINDER",
                project_id=project_id,
                threshold_date=threshold_date,
            )
            debugLogger.info(f"--debug _create_notification already exists--- {exists}")
            # print("--debug _create_notification exists--", exists)

            if exists:
                # print("--debug notification already exists-----------", exists)
                return False # already notified this month

            NotificationDao.insert_notification(
                type_="PROJECT_STATUS_REMINDER",
                subject="Project status update required",
                # content=f'Action Required: Project status update pending for your project "{project_name}" for the month. Please update the latest status.',
                content=f'Action Required: {pending_text} pending for your project "{project_name}".',
                # link=f"/projects/{project_id}/status",
                link = None,
                params={
                    "project_id": project_id,
                    "project_name": project_name,
                },
                created_by_id=user_id,  # system-as-user OR pm himself
                tenant_id=self.tenant_id,
                user_id=user_id,
            )
            return True

        except Exception as e:
            appLogger.error({"function": "AlertCreator._create_notification","error": str(e),"traceback": traceback.format_exc(),'tenant_id': self.tenant_id})
            return False

    def _send_email(self,
        user_id: int,
        user_name: str,
        user_email: str,
        project_name: str, 
        update_message: str='',
        template_key: str="TANGO-CONNECT-PROVIDER",
        email_subject: str= None,
        email_content_: str= None
    ):
        try:
            if not user_email:
                appLogger.error({"function": "_send_email","error": "No user email provided",
                    'user_id': user_id,'user_name': user_name,'tenant_id': self.tenant_id
                })
                return
            
            brief_email = email_content_ if email_content_ else email_content(user_name, project_name, update_message)
            name_and_designation_string = "Trmeric team"
            email_subject = f"Reminder: Please Update Your Project Status ({project_name}) on Trmeric"
            template_key=template_key

            api_utils = ApiUtils()
            email_res =  api_utils.send_notification_mail_api(
                email_content=brief_email,
                email_data={
                    "email_content": brief_email,
                    "name_and_position": name_and_designation_string,
                    "subject": email_subject
                }, 
                receiver_email=user_email,
                template_key=template_key
            )
            # print("--debug res-------",email_res)
            return email_res

        except Exception as e:
            appLogger.error({"function": "_send_email","error": str(e),"traceback": traceback.format_exc(),'tenant_id': self.tenant_id})

    
    def _check_project_update_status(self, status_comments, window_start, window_end):
        """
        Returns:
            needs_update
            needs_scope_update
            needs_schedule_update
        """

        if not status_comments:
            return True, True, True

        scope_ts = [
            self.parse_ts(s["timestamp"])
            for s in status_comments
            if s.get("timestamp")
        ]

        schedule_comments = [
            sc for sc in status_comments
            if sc.get("type") == "schedule_status"
        ]

        schedule_ts = [
            self.parse_ts(s["timestamp"])
            for s in schedule_comments
            if s.get("timestamp")
        ]
        debugLogger.info(f"Fetched total status comments: {len(status_comments) or 0}, schedule status: {len(schedule_comments) or 0}")
        needs_scope_update = True
        needs_schedule_update = True

        if scope_ts:
            latest_scope = max(scope_ts)
            if window_start <= latest_scope <= window_end:
                needs_scope_update = False

        if schedule_ts:
            latest_schedule = max(schedule_ts)
            if window_start <= latest_schedule <= window_end:
                needs_schedule_update = False

        debugLogger.info(
            f"Latest scope update: {max(scope_ts) if scope_ts else None}, "
            f"Latest schedule update: {max(schedule_ts) if schedule_ts else None}"
        )

        needs_update = needs_scope_update or needs_schedule_update
        debugLogger.info(f"Needs update: scope-> {needs_scope_update}, schedule-> {needs_schedule_update}")
        return needs_update, needs_scope_update, needs_schedule_update
    

    def generate_alerts2(self):

        debugLogger.info(f"generate_alerts started for tenant {self.tenant_id}")

        try:

            now = datetime.now(timezone.utc)
            if not self._is_working_day(now):
                debugLogger.info(f"Today: {now} Weekend detected. Skipping reminder cron.")
                return
            
            window_start, window_end = self._get_update_window(now)
            print("--deugusg windoew------", window_start, window_end)

            if not window_start or not window_end:
                debugLogger.info(f"Couldn't find Update window: {window_start} → {window_end}")
                appLogger.error({'event': "generate_alerts2","error": f"Couldn't find Update window: {window_start} → {window_end}"})
                return
            
            debugLogger.info(f"Update window: {window_start} → {window_end}")

            if now < window_start:
                debugLogger.info(f"Before reminder window. Skipping.")
                return
            # -------- Fetch Project Managers --------
            project_managers_map = {}
            for role in ALL_ROLES:
                users = AuthDao.fetchAllUsersOfRoleInTenant(role=role,tenant_id=self.tenant_id)
                for pm in users:
                    project_managers_map[pm["user_id"]] = pm

            project_managers = list(project_managers_map.values())
            total_projects_reminded = 0

            for pm in project_managers:

                user_id = pm["user_id"]
                user_email = pm["email"]
                user_name = f"{pm['first_name']} {pm['last_name']}"

                # if user_id != 466:
                #     continue
                debugLogger.info(f"Processing PM: {user_name}")

                pm_projects = ProjectsDaoV2.fetchProjectsDataWithProjectionAttrs(
                    projection_attrs=["id", "title","stage","status"],
                    tenant_id=self.tenant_id,
                    project_manager_id=user_id,
                )
                if not pm_projects or len(pm_projects) == 0:
                    print(f"No projects found for PM user_id: {user_id}")
                    continue
                
                # print("\n\n--debug pm_projects---", len(pm_projects))
                debugLogger.info(f"Total PM projects: {len(pm_projects) or 0}")
                user_project_count = 0

                signal_created = False
                notification_created = False
                for project in pm_projects:

                    project_id = project["id"]
                    project_name = project["title"]
                    project_stage = (project.get("stage","") or "").lower()
                    status_comments = project.get("status_comments") or []

                    # if project_id !=  5045:
                    #     continue
                    debugLogger.info(f"Checking project: {project['title']}, stage: {project_stage} with status comments: {len(status_comments) or 0}")
                    if project_stage and project_stage == "complete":
                        debugLogger.info(f"Project '{project_name}' stage is {project_stage} → skipping reminder.")
                        continue

                    needs_update, needs_scope_update, needs_schedule_update = self._check_project_update_status(
                        status_comments,
                        window_start,
                        window_end
                    )

                    debugLogger.info(f"Needs update trigger: ----- {needs_update}")
                    if not needs_update:
                        print(f"Project '{project_name}' is up-to-date. No reminder needed.")
                        appLogger.info({
                            'tenant_id': self.tenant_id,
                            "function": "generate_alerts",
                            "message": f"Project {project_name} is up-to-date. No reminder needed.",
                            'user_id': user_id,
                            'project_id': project_id,
                        })
                        continue

                    pending_text = self._pending_update_text(needs_scope_update,needs_schedule_update)
                    signal_created = self._create_signal(
                        user_id,project_name,window_start,pending_text
                    )

                    notification_created = self._create_notification(
                        user_id,
                        project_id,
                        project_name,
                        window_start,
                        pending_text
                    )

                    if notification_created:
                        existing_email_job = JobDAO.check_recent_job_for_project(
                            tenant_id=self.tenant_id,
                            user_id=user_id,
                            job_type="email-trigger",
                            project_id=project_id,
                            hours=24
                        )

                        if not existing_email_job:
                            res = self._trigger_email(
                                user_id,
                                project_id,
                                user_name,
                                user_email,
                                project_name,
                                pending_text
                            )
                            debugLogger.info(f"New email job created for project: {project_id} & {user_name}. Result: {res}")


                    user_project_count += 1
                    total_projects_reminded += 1

                appLogger.info({
                    "tenant_id": self.tenant_id,
                    "user_id": user_id,
                    "projects_reminded": user_project_count,
                    "message": "PM reminder processing completed",
                    'signal_created': signal_created,'notification_created': notification_created,'email_sent': bool(notification_created),
                })

            appLogger.info({
                "tenant_id": self.tenant_id,
                "total_projects_reminded": total_projects_reminded,
                "message": "Project status reminder cron completed"
            })

        except Exception as e:
            print("--debug error in generate_alerts2---", str(e))
            appLogger.error({
                "function": "generate_alerts",
                "tenant_id": self.tenant_id,
                "error": str(e),
                "traceback": traceback.format_exc()
            })
    
    
    def _trigger_email(self,user_id:int, project_id:int,user_name:str,user_email:str,project_name:str, pending_text: str=''):
        args = locals()
        debugLogger.info(f"_trigger_email job: {project_name}, updates: {pending_text}")

        job_type = "email-trigger"
        current_date = datetime.now(timezone.utc)
        run_id = f"{job_type}-{self.tenant_id}-{current_date.strftime('%Y%m%d%H%M%S')}"
        payload = {
            "job_type": job_type,
            "project_id": project_id,
            "user_id": user_id,
            "user_name": user_name,
            "user_email": user_email,
            "project_name": project_name,
            "pending_text": pending_text,
            "run_id": run_id,
            "total_count": 1
        }
        try:
            job_id = JobDAO.create(
                tenant_id=self.tenant_id,
                user_id=user_id,
                schedule_id=None,
                job_type=payload['job_type'],
                payload=payload
            )
            return {'success': True, 'message': f"Created job_id for {job_type}: {job_id}", "run_id": run_id}
        except Exception as e:
            return {'success': False, 'message': f"Failed creating job_id for {job_type}", "run_id": run_id}


    # def email(self):
    #     name_and_designation_string = "Team trmeric"
    #     brief_email = email_content("Saphal", "Project X")

    #     email_subject = "Reminder: Please Update Your Project Status on Trmeric"
    #     receiver_email="saphal@trmeric.com"
    #     template_key='TANGO-CONNECT-PROVIDER'

    #     api_utils = ApiUtils()
    #     res =  api_utils.send_notification_mail_api(
    #         email_content=brief_email,
    #         email_data={
    #             "email_content": brief_email,
    #             "name_and_position": name_and_designation_string,
    #             "subject": email_subject
    #         }, 
    #         receiver_email=receiver_email,
    #         template_key=template_key
    #     )
    #     print("--debug res-------",res)
    #     return res

    def generate_alerts(self):
        print("--debug generate_alerts called---", self.tenant_id)
        try:
            now = datetime.now(timezone.utc)
            year = now.year
            month = now.month
            last_day = monthrange(year, month)[1]
            feb_6_cutoff = datetime(2026, 2, 6, tzinfo=timezone.utc)
            if month == 2:
                self.threshold_day = 20

            safe_day = min(self.threshold_day, last_day)
            threshold_date = now.replace(day=safe_day,hour=0,minute=0,second=0,microsecond=0)
            debugLogger.info(f"--debug threshold_date-- {threshold_date},  month: {month},  safe_day: {safe_day}")
            # Do nothing before threshold date
            if now < threshold_date:
                debugLogger.info(f"Before threshold date: {threshold_date}, skipping reminders. Today: {now}")
                return

            roles = ALL_ROLES
            project_managers_map = {}
            for role in roles:
                for pm in AuthDao.fetchAllUsersOfRoleInTenant(role=role, tenant_id=self.tenant_id):
                    project_managers_map[pm["user_id"]] = pm

            project_managers = list(project_managers_map.values())
            # print("\n---debug project_managers------", project_managers)
            # return

            total = 0
            for pm in project_managers:
                user_id = pm["user_id"]
                user_email = pm["email"]
                user_name = pm['first_name'] + ' ' + pm['last_name']

                debugLogger.info(f"Executing for PM: {pm}")

                pm_projects = ProjectsDaoV2.fetchProjectsDataWithProjectionAttrs(
                    projection_attrs=["id", "title","stage","status"],
                    tenant_id=self.tenant_id,
                    project_manager_id=user_id,
                )
                if not pm_projects or len(pm_projects) == 0:
                    print(f"No projects found for PM user_id: {user_id}")
                    continue

                # print("\n\n--debug pm_projects---", len(pm_projects))
                debugLogger.info(f"Total PM projects: {len(pm_projects) or 0}")
                user_total = 0
                for project in pm_projects:
                    project_id = project["id"]
                    # if project_id !=  5045:
                    #     continue
                    project_name = project["title"]
                    project_stage = project.get("stage",None) or None
                    status_comments = project.get("status_comments") or []
                    # print("--debug project---", project['title'],len(status_comments), project_stage)
                    debugLogger.info(f"Checking project: {project['title']}, stage: {project_stage} with status comments: {len(status_comments) or 0}")

                    needs_update = False
                    if project_stage and project_stage.lower() == "complete":
                        debugLogger.info(f"Project '{project_name}' stage is {project_stage} → skipping reminder.")
                        continue

                    # ---------- STATUS CHECK ----------
                    if not status_comments:
                        needs_update = True
                    else:
                        timestamps = [
                            self.parse_ts(s["timestamp"])
                            for s in status_comments
                            if s.get("timestamp")
                        ]
                        schedule_statuses = [sc for sc in status_comments if sc.get("type") == "schedule_status"]
                        schedule_timestamps =  [
                            self.parse_ts(s["timestamp"])
                            for s in schedule_statuses
                            if s.get("timestamp")
                        ]
                        # print("--debug schedule_timestamps----------", schedule_timestamps, schedule_statuses)
                        debugLogger.info(f"Checking schedule status comments: {len(schedule_statuses) or 0}")

                        if not timestamps or len(timestamps) == 0 or not schedule_timestamps or len(schedule_timestamps)==0:
                            needs_update = True
                        else:
                            latest_schedule_status = schedule_statuses[0].get('detailed_status',None) or None
                            debugLogger.info(f"Latest schedule status: {latest_schedule_status}")

                            if latest_schedule_status and latest_schedule_status.lower() in ["cancelled","project closed"]:
                                debugLogger.info(f"Project '{project_name}' has schedule status '{latest_schedule_status}' → skipping reminder.")
                                continue

                            latest_update_ts = max(timestamps)
                            latest_update_schedule_ts = max(schedule_timestamps)
                            debugLogger.info(f"Latest update timestamp: {latest_update_ts}, Latest schedule status timestamp: {latest_update_schedule_ts}")

                            max_ts = max(latest_update_ts, latest_update_schedule_ts)
                            if feb_6_cutoff <= max_ts < threshold_date:
                                debugLogger.info(f"Project is last updated at {max_ts} after {feb_6_cutoff} → needs_update = False")
                                needs_update = False
                            else:
                                # print("--debug schedule-----timecond--", (latest_update_schedule_ts < threshold_date))
                                needs_update = (latest_update_ts < threshold_date) or (latest_update_schedule_ts < threshold_date)

                    debugLogger.info(f"Needs update trigger: ----- {needs_update}")
                    if not needs_update:
                        print(f"Project '{project_name}' is up-to-date. No reminder needed.")
                        appLogger.info({
                            'tenant_id': self.tenant_id,
                            "function": "generate_alerts",
                            "message": f"Project {project_name} is up-to-date. No reminder needed.",
                            'user_id': user_id,
                            'project_id': project_id,
                        })
                        continue

                    signal_created = self._create_signal(user_id, project_name, threshold_date)
                    notifi_created = self._create_notification(user_id,project_id,project_name,threshold_date)
                    if notifi_created:
                        existing_email_job = JobDAO.check_recent_job_for_project(
                            tenant_id = self.tenant_id,
                            user_id = user_id,
                            job_type = "email-trigger",
                            project_id = project_id,
                            hours = 24
                        )
                        if not existing_email_job:
                            res = self._trigger_email(user_id,project_id, user_name,user_email,project_name)
                            # print("--debug existing_email_job created-------", existing_email_job, res)
                            debugLogger.info(f"New email job created for project: {project_id} & {user_name}. Result: {res}")
                            # self._send_email(user_id,user_name,user_email,project_name)
                        total += 1
                        user_total += 1

                    appLogger.info({
                        'tenant_id': self.tenant_id,
                        "function": "generate_alerts",
                        "message": f"Project {project_name} status reminder cron completed",
                        'signal_created': signal_created,'notification_created': notifi_created,'email_sent': bool(notifi_created),
                    })
                    # break
                appLogger.info({
                    'tenant_id': self.tenant_id,
                    "function": "generate_alerts",
                    "message": f"Project status reminder cron completed for PM {user_name}",
                    'user_id': user_id,
                    'total_projects_reminded': user_total
                })

            appLogger.info({
                'tenant_id': self.tenant_id,
                "function": "generate_alerts",
                "message": f"Project status reminder cron completed for {project_managers}",
                'total_projects_reminded': total
            })

        except Exception as e:
            print("--debug error in generate_alerts---", str(e))
            appLogger.error({"function": "generate_alerts","error": str(e),'tenant_id': self.tenant_id,"traceback": traceback.format_exc()})

    
    
    def generate_demand_alerts_seagate(self, job_type):
        debugLogger.info(f"generate_alerts started for tenant {self.tenant_id} {job_type}")

        try:
            now = datetime.now(timezone.utc)

            if not self._is_working_day(now):
                debugLogger.info(f"Weekend detected. Skipping reminder cron.")
                return

            cc_list = []

            # ─────────────────────────────────────────────────────────────
            # CASE 1: FY27 Draft Demands → remind Business Requestors
            # Deadline: 20th March
            # Send email to each Business Requestor about their DRAFT demands
            # ─────────────────────────────────────────────────────────────
            if job_type == "emails:fy27-demand-kickoff":

                DEADLINE = datetime(2026, 3, 20, tzinfo=timezone.utc)

                if now > DEADLINE:
                    debugLogger.info("Deadline passed. Skipping FY27 kickoff.")
                    return

                data = RoadmapDao.fetchBusinessSponsorsOfRoadmaps(
                    tenant_id=self.tenant_id,
                    demand_queue="FY27",
                    state=200
                )

                if not data:
                    debugLogger.info("No draft FY27 demands found.")
                    return

                # Group draft demands by business requestor email
                # so one person with multiple demands gets ONE email
                from collections import defaultdict
                requestor_demands = defaultdict(
                    lambda: {"demands": [], "name": "", "email": ""}
                )

                for row in data:
                    email = row.get("email")
                    print("debug email", email)
                    if not email:
                        continue

                    requestor_demands[email]["name"] = (
                        f"{row.get('first_name','')} {row.get('last_name','')}"
                    ).strip()
                    requestor_demands[email]["email"] = email
                    requestor_demands[email]["demands"].append({
                        "roadmap_id": row.get("roadmap_id"),
                        "roadmap_title": row.get("roadmap_title"),
                        "release_cycle": row.get("release_cycle_title"),
                        "business_unit": row.get("business_unit"),
                    })

                debugLogger.info(
                    f"Draft FY27 demands grouped into {len(requestor_demands)} requestors"
                )

                for email, info in requestor_demands.items():
                    user_name = info.get("name") or "there"
                    demands = info["demands"]
                    demand_lines = "".join([
                        f"<li>{d['roadmap_title']}</li>"
                        for d in demands
                    ])
                    body_html = FY27_DEMAND_KICKOFF_TEMPLATE.format(
                        user_name=user_name,
                        demand_count=len(demands),
                        demand_lines=demand_lines,
                        deadline="20th March 2026"
                    )

                    email_log_job_type = "email:fy27-demand-kickoff"
                    existing_job = JobDAO.check_recent_job_identifier(
                        tenant_id=self.tenant_id,
                        identifier=email,
                        job_type=email_log_job_type,
                        minutes=1440
                    )

                    if existing_job:
                        debugLogger.info(f"Email already sent to {email}")
                        continue

                    res = self._send_email_internal(
                        user_email=email,
                        user_name=user_name,
                        subject="Action Required: Submit Your FY27 Draft Demands by 20th March",
                        body_html=body_html,
                        cc_list=cc_list
                    )
                    if res:
                        self._record_email_log(
                            identifier=email,
                            job_type=email_log_job_type
                        )
                        debugLogger.info(f"Kickoff email sent → {email} result {res}")

            # ============================================================
            # CASE 2 → Zero Demand Nudge
            # ============================================================

            elif job_type == "emails:fy27-zero-demand-nudge":
                DEADLINE = datetime(2026, 3, 20, tzinfo=timezone.utc)
                email_log_job_type = "email:fy27-zero-demand-nudge"
                if now > DEADLINE:
                    debugLogger.info("Deadline passed. Skipping zero-demand nudge.")
                    return
                requestors = RoadmapDao.fetchAllBusinessRequestorsWithZeroRoadmaps(tenant_id=self.tenant_id)
                debugLogger.info(f"Zero-demand requestors: {len(requestors)}")
                for r in requestors:
                    email = r.get("email")
                    print("rrrr ", r)
                    user_name = (
                        f"{r.get('first_name','')} {r.get('last_name','')}"
                    ).strip() or "there"
                    if not email:
                        continue
                    existing_job = JobDAO.check_recent_job_identifier(
                        tenant_id=self.tenant_id,
                        identifier=email,
                        job_type=email_log_job_type,
                        minutes=1440
                    )
                    if existing_job:
                        debugLogger.info(f"Nudge already sent to {email}")
                        continue
                    body_html = FY27_ZERO_DEMAND_TEMPLATE.format(
                        user_name=user_name,
                        deadline="20th March 2026"
                    )
                    res = self._send_email_internal(
                        user_email=email,
                        user_name=user_name,
                        subject="Reminder: No FY27 Demands Submitted Yet — Deadline 20th March",
                        body_html=body_html,
                        cc_list=cc_list
                    )
                    if res:
                        self._record_email_log(
                            identifier=email,
                            job_type=email_log_job_type
                        )
                        debugLogger.info(f"Zero-demand email sent → {email} result {res}")

        except Exception as e:
            appLogger.error({
                "function": "generate_demand_alerts_seagate",
                "tenant_id": self.tenant_id,
                "error": str(e),
                "traceback": traceback.format_exc()
            })

            

    def _send_email_internal(
        self,
        user_email: str,
        user_name: str,
        subject: str,
        body_html: str,
        cc_list=None,
        bcc_list=None,
        attachments=None
    ):
        """
        Send roadmap related email notifications.
        """

        try:

            if not user_email:
                appLogger.error({
                    "function": "_send_email_internal",
                    "error": "Missing user_email",
                    "tenant_id": self.tenant_id
                })
                return False

            # ## for testing
            # if user_email not in ["abhishek+ey@trmeric.com", "ashish+ey_dm@trmeric.com", "jothika+qa@trmeric.com"]:
            #     print("not abhishek .... not proceeding", user_email)
            #     return False
            # user_email = "abhishek+ey@trmeric.com"

            res = send_email_notification(
                receiver_email=user_email,
                subject=subject,
                body_html=body_html,
                cc_list=cc_list,
                bcc_list=bcc_list,
                attachments=attachments
            )

            debugLogger.info({
                "function": "_send_email_internal",
                "email": user_email,
                "subject": subject,
                "result": res
            })

            return res

        except Exception as e:
            appLogger.error({
                "function": "_send_email_internal",
                "tenant_id": self.tenant_id,
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            return False
    

    def _record_email_log(self, identifier: str, job_type: str):
        """
        Create a completed job entry to prevent duplicate emails.
        identifier = email used for throttling
        """
        try:
            import time
            time.sleep(1)
            run_id = f"{job_type}-{self.tenant_id}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
            payload = {
                "job_type": job_type,
                "identifier": identifier,   # ⭐ IMPORTANT
                "run_id": run_id,
                "total_count": 1
            }
            job_id = JobDAO.create(
                tenant_id=self.tenant_id,
                user_id=None,   # not tied to internal user
                schedule_id=None,
                job_type=job_type,
                payload=payload
            )

            # mark completed so cron worker never executes it
            JobDAO.update_status(job_id, "done")
            return job_id
        except Exception as e:
            appLogger.error({
                "function": "_record_email_log",
                "tenant_id": self.tenant_id,
                "error": str(e),
                "traceback": traceback.format_exc()
            })
            
       
if __name__ == "__main__":
    # Example usage
    tenant_id = 776  # Replace with actual tenant ID
    alert_creator = AlertCreator(tenant_id=tenant_id, threshold_day=18)
    # alert_creator.generate_alerts2()
    # trigger_email = alert_creator.email()
    # print("--debug trigger_email--", trigger_email)
    print("--debug done---------------------------------")