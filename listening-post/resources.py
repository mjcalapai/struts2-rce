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

            task = {
                "id": str(uuid.uuid4()),
                "title": data.get("title"),
                "description": data.get("description"),
                "status": data.get("status", "pending"),
                "task_type": data.get("task_type")
            }

            if not task["title"]:
                return {"error": "title is required"}, 400

            response = self.supabase.table("tasks").insert(task).execute()
            return response.data, 201

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
        
