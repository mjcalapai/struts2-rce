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

            task = {
                "id": str(uuid.uuid4()),
                "title": data.get("title"),
                "description": data.get("description"),
                "status": data.get("status", "pending")
            }

            if not task["title"]:
                return {"error": "title is required"}, 400

            response = self.supabase.table("tasks").insert(task).execute()
            return response.data, 201

        except Exception as e:
            return {"error": str(e)}, 500