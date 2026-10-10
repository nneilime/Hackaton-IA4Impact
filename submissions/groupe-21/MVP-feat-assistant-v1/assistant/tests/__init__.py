# Les tests d'orchestration scriptent chaque appel au modèle : la présélection FAQ et la réponse rapide aux calculs
# (qui évitent des appels) sont désactivées ici et testées à part (test_agent.FastPath).
from assistant import agent as _agent

_agent.PRELOAD = 0
_agent.FAST_FINANCE = False
