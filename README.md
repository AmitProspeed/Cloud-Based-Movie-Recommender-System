# Cloud-Based-Movie-Recommender-System
A recommender system is used to recommend items to a user based on the judgement whether they would prefer the item or not. This is done by predicting the future preferences of the user on the basis of past preferences and the preferences of similar users. The goal of our project is to create such a recommender system for movies using collaborative filtering approach. For an interactive experience for online users, we are planning to create a data application using open source frameworks (such as Streamlit). We will host the application as a Docker container on GCP and deploy it to Kubernetes cluster using GKE. Our primary goal is to implement the recommender system for movies. Our stretch goal is to extend this system to work with other datasets such as music, ecommerce, etc.



Instructions to setup:- 

-> Setup streamlit environment

1. Inside project folder, python3 -m pip install --user virtualenv

2. python3 -m pip install --user virtualenv

3. source env/bin/activate

4. pip install streamlit

5. pip install redis

6. pip install flask

7. pip install jsonpickle

6. streamlit run filename.py


Local URL: http://localhost:8501
Network URL: http://10.0.0.33:8501

7. Finally, deactivate


-> Setup kubernetes (local)

1. curl -LO "https://storage.googleapis.com/kubernetes-release/release/$(curl -s https://storage.googleapis.com/kubernetes-release/release/stable.txt)/bin/linux/amd64/kubectl"
2. chmod +x ./kubectl
3. sudo mv ./kubectl /usr/local/bin/kubectl

-> Setup gcloud redis/rabbitmq

1. gcloud config set compute/zone us-central1-b
2. gcloud config set project southern-surge-289519
3. gcloud container clusters create --preemptible mykube
4. ./deploy-local-dev.sh

-> Dataset - https://grouplens.org/datasets/movielens/25m/

-> Collaborative filtering algorithm - https://github.com/TheClub4/collaborative_filtering/blob/master/collaborative_filtering.ipynb