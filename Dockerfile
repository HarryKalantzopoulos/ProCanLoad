# Use an official Python runtime as a parent image
FROM python:3.10

# Set the working directory inside the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY /ProCanLoad /app/ProCanLoad
COPY setup.py /app
COPY requirements.txt /app

# Install any needed packages specified in requirements.txt
RUN pip install .
RUN pip install -r requirements.txt

# Run your script when the container launches
CMD ["python", "ProCanLoad/main.py"]