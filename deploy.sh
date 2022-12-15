#!/bin/bash 

# docker network create qcbot-net

# docker run --net qcbot-net -d --name redis-qc -p 6379:6379 -v /home/barakor/gits/DiscordQCPUG/redis_qc_data/:/data redis/redis-stack-server:latest 

# docker build -t qcpug:test ./ 
docker run -v /home/barakor/gits/DiscordQCPUG/:/code -it --rm -v /home/barakor/Downloads:/ocr  --net qcbot-net --name qcbot qcpug:test
