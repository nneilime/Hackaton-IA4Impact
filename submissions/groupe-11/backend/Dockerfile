FROM fedora:44

COPY . /app

WORKDIR /app

RUN dnf install uv -y
RUN dnf install python -y
RUN dnf install mesa-libGL -y
RUN uv python install 3.13
RUN uv sync
RUN rm -f traitees.txt

EXPOSE 8000

CMD [ "uv", "run", "uvicorn", "main:app", "--reload" ]
