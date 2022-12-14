docker build -t dcbot:latest -f ./dcbot.dockerfile ./ 

docker network create qcbot-net

docker run --net qcbot-net -d --name redis-qc -p 6379:6379 -v /home/barakor/gits/DiscordQCPUG/redis_qc_data/:/data redis/redis-stack-server:latest 

docker rm --force qcbot ; docker build -t qcpug:test ./ ;docker run -v /home/barakor/gits/DiscordQCPUG/ocr/:/ocr  -d --net qcbot-net --name qcbot qcpug:test

docker run --rm -it --name qcocr -e "TESSDATA_PREFIX=/app" -v /home/barakor/gits/DiscordQCPUG/ocr/:/app -w /app clearlinux/tesseract-ocr tesseract *.png stdout --oem 1