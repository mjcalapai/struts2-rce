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

            #Either object or array of objects are accepted
            if isinstance(data, dict):
                data = [data]

            if not isinstance(data, list):
                return {"error": "Request body must be a JSON object or array of objects"}, 400

            inserted_tasks = []

            for item in data:
                task_id = str(uuid.uuid4())

                task = {
                    "id": task_id,
                    "title": item.get("title"),
                    "description": item.get("description"),
                    "status": item.get("status", "pending"),
                    "task_type": item.get("task_type")
                }

                if not task["title"]:
                    return {"error": "title is required"}, 400

                if not task["task_type"]:
                    return {"error": "task_type is required"}, 400

                # Insert into tasks table
                task_response = self.supabase.table("tasks").insert(task).execute()
                inserted_tasks.extend(task_response.data)
                #build task options string for history entry
                task_options = []
                for key, value in item.items():
                    if key not in ["title", "description", "status", "task_type"]:
                        task_options.append(f"{key}: {value}")

                #Insert into history table
                history_entry = {
                    "task_id": task_id,
                    "task_type": task["task_type"],
                    "task_object": item,
                    "task_options": task_options,
                    "task_results": ""
                }

                self.supabase.table("history").insert(history_entry).execute()

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

    # AddResults
    def post(self):
        try:
            data = request.get_json()
            if not data:
                return {"error": "Request body must be JSON"}, 400

            if isinstance(data, list):
                return {"error": "Request body must be a JSON object, not a list"}, 400

            result = {
                "id": str(uuid.uuid4()),
                "task_id": data.get("task_id"),
                "output": data.get("output")
            }

            if not result["task_id"]:
                return {"error": "task_id is required"}, 400

            response = self.supabase.table("results").insert(result).execute()
            return response.data, 201

        except Exception as e:
            return {"error": str(e)}, 500


class History(Resource):
    def __init__(self, supabase):
        self.supabase = supabase

    # ListHistory
    def get(self):
        try:
            
            results_response = self.supabase.table("results").select("*").execute()
            results_rows = results_response.data

            #update matching history row with result output
            for result in results_rows:
                task_id = result.get("task_id")
                output = result.get("output")

                if task_id:
                    self.supabase.table("history") \
                        .update({"task_results": output}) \
                        .eq("task_id", task_id) \
                        .execute()

            updated_history_response = self.supabase.table("history").select("*").execute()
            return updated_history_response.data, 200

        except Exception as e:
            return {"error": str(e)}, 500