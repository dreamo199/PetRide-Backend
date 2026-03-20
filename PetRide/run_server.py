from waitress import serve
from PetRide.wsgi import application

serve(application, host='0.0.0.0', port=8000, threads=8)
