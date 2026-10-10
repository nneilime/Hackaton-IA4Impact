"""Field simulator: plays the outside world for the live mode, as a separate process.

It is NOT part of the backend: it only talks to the API over HTTP, exactly like a real alert system and the field
teams' terminals would. It replays a past crisis shifted to now (alerts with the same spacing), watches the trips the
manager validated, and reports when each team is on site and when its repair is done.

  python -m simulator --crisis CRISE_027 --speed 60
"""
