FROM public.ecr.aws/lambda/python:3.12

COPY requirements.txt .
RUN pip install -r requirements.txt --quiet

COPY *.py .
COPY config.json .
COPY system_prompt.md .

CMD ["lambda_function.lambda_handler"]
