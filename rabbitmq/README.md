# RabbitMQ Messaging

We have provide a single-pod deployment that provides a RabbitMQ message server and a service called `rabbitmq` so that worker nodes can use DNS names to locate the instance. The provided deployment uses [the one provided by the Rabbitmq developers](https://hub.docker.com/_/rabbitmq).

You do not need to create any queues or exchanges; this will be done by the worker and rest VM's.

### *N.B.*

If you restart or delete your rabbitmq instance, any messages (e.g. outstanding images that need to be processed) in the instance will not be retained. This isn't a design flaw in rabbitmq and [there are extensive directions on how to turn this into a reliable service](https://www.rabbitmq.com/admin-guide.html).