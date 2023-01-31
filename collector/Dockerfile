FROM python:3.10-slim as dependencies

RUN apt-get update

#install dependencies
RUN apt-get update && apt-get install -y --no-install-recommends gcc libc6-dev
WORKDIR /app
COPY requirements.txt .
# install dependencies
RUN pip install -r requirements.txt


FROM python:3.10-slim
COPY --from=dependencies /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages

# Copy the application source to this directory
COPY . /usr/src/collector






    
    
    
    
    
    
