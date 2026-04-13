# Welcome to Cloud Functions for Firebase for Python!
# To get started, simply uncomment the below code or create your own.
# Deploy with `firebase deploy`

import os
import re
import json
import requests
import tempfile
from datetime import datetime, timedelta
from firebase_functions import https_fn, options
from firebase_admin import initialize_app, firestore
from bs4 import BeautifulSoup
from google import genai
from google.genai import types

initialize_app()

# Cliente Firestore inicializado no nível do módulo (padrão recomendado)
db = firestore.client()

# Configuração do Gemini (Migrado para Secret Manager)
def get_gemini_client():
    """Retorna o cliente Gemini usando a chave do Secret Manager."""
    api_key = os.environ.get("GEMINI_API_KEY")
    return genai.Client(api_key=api_key)
