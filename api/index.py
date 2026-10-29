"""Vercel entry point: all routes are rewritten here (see vercel.json)."""
import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from mcla_app import Handler

class handler(Handler):
    pass
