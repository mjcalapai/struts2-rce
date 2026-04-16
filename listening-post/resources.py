import uuid

from flask import request
from flask_restful import Resource


class Tasks(Resource):
    def __init__(self, supabase):
        self.supabase = supabase

    # ListTasks
    def get(self):
        try:
            response = self.supabase.table("tasks").select("*").execute()
            return response.data, 200
        except Exception as e:
            return {"error": str(e)}, 500

    # AddTasks
    def post(self):
        try:
            data = request.get_json()

            if not data:
                return {"error": "Request body must be JSON"}, 400
            
            if isinstance(data, list):
                return {"error": "Request body must be JSON"}, 400

            inserted_tasks = []

            for item in data:
                task = {
                    "id": str(uuid.uuid4()),
                    "title": item.get("title"),
                    "description": item.get("description"),
                    "status": item.get("status", "pending"),
                    "task_type": item.get("task_type")
                }

                if not task["title"]:
                    return {"error": "title is required"}, 400

                if not task["task_type"]:
                    return {"error": "task_type is required"}, 400

                response = self.supabase.table("tasks").insert(task).execute()
                inserted_tasks.extend(response.data)

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
                return {"error": "Request body must be JSON"}, 400

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
            # Get all history rows
            history_response = self.supabase.table("history").select("*").execute()
            history_rows = history_response.data

            # Get all result rows
            results_response = self.supabase.table("results").select("*").execute()
            results_rows = results_response.data

            # For each result, update matching history row
            for result in results_rows:
                task_id = result.get("task_id")
                output = result.get("output")

                if task_id:
                    self.supabase.table("history") \
                        .update({"task_results": output}) \
                        .eq("task_id", task_id) \
                        .execute()

            # Re-read history so returned data includes updates
            updated_history_response = self.supabase.table("history").select("*").execute()
            return updated_history_response.data, 200

        except Exception as e:
            return {"error": str(e)}, 500