# pull official base image
FROM python:3.8.3
# Prevents Python from writing pyc files to disc (equivalent to python -B option)
ENV PYTHONDONTWRITEBYTECODE 1
# Prevents Python from buffering stdout and stderr (equivalent to python -u option)
ENV PYTHONUNBUFFERED 1
# set work directory
WORKDIR /usr/src/app
# install dependencies
COPY ./requirements.txt .
RUN pip install --upgrade pip
RUN pip install -r requirements.txt
# copy project
COPY . .
# run entrypoint.sh
ENTRYPOINT ["sh", "/usr/src/app/entrypoint.sh"]