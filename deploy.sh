#!/bin/bash 

docker network create qcbot-net

# run redis server
docker run --rm -d --name redis-qc --net qcbot-net -p 6379:6379 -v $(pwd)/redis_qc_data/:/data redis/redis-stack-server:latest 

# run tessarest server for OCR support
docker build -t tessarest:latest ./tessarest
docker run --rm -d --name tessarest --net qcbot-net  -p 6969:80 tessarest:latest

# run the discord bot 
docker build -t qcpug:latest ./ 
docker run --rm -d  --name qcbot --net qcbot-net -p 6443:443  qcpug:latest
