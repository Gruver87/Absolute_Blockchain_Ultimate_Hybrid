FROM python:3.13-slim
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
CMD ["python", "ABSOLUTE_FINAL_FIXED.py"]
