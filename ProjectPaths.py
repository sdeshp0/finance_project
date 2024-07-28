import os

C_PATH_BASE = os.path.abspath(os.path.dirname(__file__))
C_PATH_REPO_BASE = os.path.join(C_PATH_BASE, os.path.pardir)
C_PATH_TEMPLATES = os.path.join(C_PATH_BASE, 'templates')
C_PATH_ANALYSIS = os.path.join(C_PATH_BASE, 'analysis')