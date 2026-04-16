import os
import resources

from flask import Flask
from flask_restful import Api
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

app = Flask(__name__)

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)



api = Api(app)

api.add_resource(resources.Tasks, "/tasks", resource_class_kwargs={"supabase": supabase})
api.add_resource(resources.Results, '/results', resource_class_kwargs={"supabase": supabase})
api.add_resource(resources.History, "/history", resource_class_kwargs={"supabase": supabase})

if __name__ == "__main__":
    app.run(debug=True)