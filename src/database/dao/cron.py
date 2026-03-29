from src.database.Database import db_instance


class CronDao:
    @staticmethod
    def FetchTangoLastCronRunTime(key="tango_cron_run"):
        query = f"""
            SELECT id, name, frequency, last_run_date
            FROM public.cron_insightscronschedule
            WHERE name = '{key}';
        """
        data = db_instance.retrieveSQLQueryOld(query)
        if len(data) > 0:
            return data[0]["last_run_date"]
        else:
            return None
        
    # @staticmethod
    # def UpdateTangoLastCronRunTime(current_time):
    #     print("in UpdateTangoLastCronRunTime ", current_time)
    #     query = """
    #         UPDATE public.cron_insightscronschedule
    #         SET last_run_date = %s
    #         WHERE name = %s;
    #     """
    #     params = (current_time, 'tango_cron_run')
    #     db_instance.executeSQLQuery(query, params)
        
    @staticmethod
    def UpdateTangoLastCronRunTime(current_time, key="tango_cron_run", frequency_value="daily"):
        print("in UpdateTangoLastCronRunTime ", current_time)
        existing_data = CronDao.FetchTangoLastCronRunTime(key)

        if existing_data:
            # If the record exists, update it
            update_query = """
                UPDATE public.cron_insightscronschedule
                SET last_run_date = %s
                WHERE name = %s;
            """
            db_instance.executeSQLQuery(update_query, (current_time, key))
        else:
            # If no record exists, insert a new one
            insert_query = """
                INSERT INTO public.cron_insightscronschedule (name, last_run_date, frequency)
                VALUES (%s, %s, %s);
            """
            # Set a value for 'frequency' (you can change this based on your business logic)
            # frequency_value = 'daily'  # Example default value
            db_instance.executeSQLQuery(insert_query, (key, current_time, frequency_value))
            
    @staticmethod
    def fetch_due_tenant_schedules():
        query = """
            SELECT id, tenant_id, frequency, interval_unit, start_time, is_active, last_run_date, last_scheduled_at
            FROM public.cron_tenantschedule
            WHERE is_active = TRUE
              AND (
                    last_scheduled_at IS NULL
                    OR last_scheduled_at + (frequency || ' ' || interval_unit)::interval <= NOW()
                  );
        """
        return db_instance.retrieveSQLQueryOld(query)

    @staticmethod
    def update_last_run(schedule_id, run_time):
        query = """
            UPDATE public.cron_tenantschedule
            SET last_run_date = %s, updated_at = NOW()
            WHERE id = %s;
        """
        db_instance.executeSQLQuery(query, (run_time, schedule_id))
        
        
    @staticmethod
    def update_last_scheduled(schedule_id, scheduled_time, note=None):
        query = """
            UPDATE public.cron_tenantschedule
            SET last_scheduled_at = %s,
                progress_log = %s,
                updated_at = NOW()
            WHERE id = %s;
        """
        db_instance.executeSQLQuery(query, (scheduled_time, note, schedule_id))

    @staticmethod
    def update_progress(schedule_id, note):
        query = """
            UPDATE public.cron_tenantschedule
            SET progress_log = %s,
                updated_at = NOW()
            WHERE id = %s;
        """
        db_instance.executeSQLQuery(query, (note, schedule_id))

