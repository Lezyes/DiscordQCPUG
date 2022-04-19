FROM python:alpine

# RUN useradd -m -p 123456 -s /bin/bash userman 
# RUN usermod -aG sudo userman
# USER userman
# ENV PATH="/home/userman/.local/bin:${PATH}"

RUN pip install --upgrade pip
# WORKDIR /home/mruser
WORKDIR /tmp
COPY . .
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 443

CMD ["python3", "main.py"]
