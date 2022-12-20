docker build -t dcbot:latest -f ./dcbot.dockerfile ./ 

docker network create qcbot-net

docker run --net qcbot-net -d --name redis-qc -p 6379:6379 -v /home/barakor/gits/DiscordQCPUG/redis_qc_data/:/data redis/redis-stack-server:latest 

docker rm --force qcbot ; docker build -t qcbot:test ./ ;docker run -d --net qcbot-net --name qcbot qcbot:test