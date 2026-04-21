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
    base = os.path.dirname(os.path.abspath(__file__))
    cert = os.path.join(base, "cert.pem")
    key  = os.path.join(base, "key.pem")
    ssl_context = (cert, key) if os.path.exists(cert) and os.path.exists(key) else None
    app.run(debug=True, ssl_context=ssl_context)
 