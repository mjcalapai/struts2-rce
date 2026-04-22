import os
import resources

from flask import Flask
from flask_restful import Api
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

# Initialize Flask application instance
app = Flask(__name__)

# Create Supabase client using credentials from environment variables
supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)


# Initialize Flask-RESTful API wrapper around Flask app
api = Api(app)

# Register API resources
# Each resource is injected with the shared Supabase client instance
api.add_resource(resources.Tasks, "/tasks", resource_class_kwargs={"supabase": supabase})
api.add_resource(resources.Results, '/results', resource_class_kwargs={"supabase": supabase})
api.add_resource(resources.History, "/history", resource_class_kwargs={"supabase": supabase})

if __name__ == "__main__":
    # Start the Flask development server
    # host="0.0.0.0" allows external connections
    # ssl_context enables HTTPS using provided certificate and key
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False,    # disable in production
        ssl_context=("cert.pem", "key.pem") # TLS encryption for secure communication
    )