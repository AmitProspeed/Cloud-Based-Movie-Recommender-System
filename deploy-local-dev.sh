#!/bin/sh
#
# You can use this script to launch Redis and RabbitMQ on Kubernetes
# and forward their connections to your local computer. That means
# you can then work on your worker-server.py and rest-server.py
# on your local computer rather than pushing to Kubernetes with each change.
#
# To kill the port-forward processes us e.g. "ps augxww | grep port-forward"
# to identify the processes ids
#
kubectl apply -f redis/redis-deployment.yaml
kubectl apply -f redis/redis-service.yaml
kubectl apply -f rabbitmq/rabbitmq-deployment.yaml
kubectl apply -f rabbitmq/rabbitmq-service.yaml

kubectl port-forward --address 0.0.0.0 service/rabbitmq 5672:5672 &
kubectl port-forward --address 0.0.0.0 service/redis 6379:6379 &