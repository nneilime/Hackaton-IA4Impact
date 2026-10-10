"""Lance la V1 : python -m assistant [--host 127.0.0.1] [--port 8000]"""
import argparse

from . import config, server

parser = argparse.ArgumentParser(prog="python -m assistant", description=__doc__)
parser.add_argument("--host", help="adresse d'écoute (défaut : 127.0.0.1, accessible depuis ce poste seulement)")
parser.add_argument("--port", type=int, help="port (défaut : 8000)")
args = parser.parse_args()
server.run(config.from_env(host=args.host, port=args.port))
