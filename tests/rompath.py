"""Where the tests find the original ROM: the SMAR_ROM environment variable, else base/original.sfc (headerless Super Metroid (Japan, USA) (En,Ja))."""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROM = os.environ.get("SMAR_ROM") or os.path.join(ROOT, "base", "original.sfc")
