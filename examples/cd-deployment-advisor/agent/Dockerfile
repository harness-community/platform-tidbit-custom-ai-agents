FROM python:3.11-slim

WORKDIR /agent

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ../../agent-instructions/cd-deployment-advisor.md instructions.md
COPY main.py .

ENTRYPOINT ["python", "main.py"]
