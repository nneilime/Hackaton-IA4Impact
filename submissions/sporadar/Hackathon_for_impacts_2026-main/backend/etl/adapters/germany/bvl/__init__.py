from .base import BaseAdapter, CanonicalBundle
from .de_bvl import GermanyBVLAdapter

REGISTRY = {"DE": GermanyBVLAdapter}  # teammates: add "FR": FranceAdapter, "CA": CanadaAdapter
