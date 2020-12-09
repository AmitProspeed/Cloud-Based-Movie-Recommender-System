from flask import Flask, request, Response
import pickle, json, jsonpickle
import pandas as pd
import traceback
import redis
import os

#Math functions, we'll only need the sqrt function so let's import only that
from math import sqrt
import numpy as np

# Initialize the Flask application
app = Flask(__name__)

##
## Configure test vs. production
##
redisHost = os.getenv("REDIS_HOST") or "localhost"

#db connections
genDb = redis.StrictRedis(host=redisHost, db=0, decode_responses=True)
activeUserRatingDb = redis.StrictRedis(host=redisHost, db=2, decode_responses=True)    # userId -> userInputrecs dictionary <movieId><[rating,genre]>
movieDb = redis.StrictRedis(host=redisHost, db=3, decode_responses=True)    # movieId -> [movieName, ImageUrl, genres, year]
userMovieDb = redis.StrictRedis(host=redisHost, db=4, decode_responses=True)    # userId -> [[user genre filtered movieId,genre]]
userReccDb = redis.StrictRedis(host=redisHost, db=5, decode_responses=True)    # userId -> [[Recommended movieId,genre]]

def initialize_application():
    global genres, ratings_df, movies_df, links_df
    try:
        #adding genres to DB0 <genres><[genres list]
        if not genDb.llen("genres"):
            for i in genres:
                genDb.rpush("genres", i)
            print ("genres loaded to DB0.")
        else:
            print ("genres list exist in DB0. Loading not required")
        
        #Read movies, ratings and links csv
        ratings_df = pd.read_csv("dataset/ratings.csv")
        movies_df = pd.read_csv("dataset/movies.csv")
        links_df = pd.read_csv("dataset/links_new.csv")
        #genDb.set("movies_df", pickle.dumps(movies_df))
        #genDb.set("ratings_df", pickle.dumps(ratings_df))
        #genDb.set("links_df", pickle.dumps(links_df))

        #preprocessing
        #Using regular expressions to find a year stored between parentheses
        #Store the years in a separate column
        movies_df['year'] = movies_df.title.str.extract('(\(\d\d\d\d\))',expand=False)
        #Removing the parentheses
        movies_df['year'] = movies_df.year.str.extract('(\d\d\d\d)',expand=False)
        #Removing the years from the 'title' column
        movies_df['title'] = movies_df.title.str.replace('(\(\d\d\d\d\))', '')
        #Applying the strip function to get rid of any ending whitespace characters that may have appeared
        movies_df['title'] = movies_df['title'].apply(lambda x: x.strip())
        #Dropping timestamp from dataframe
        ratings_df = ratings_df.drop('timestamp', 1)
        print ("Dataframes loaded and preprocessed.")

        #Store latest user and movie Id
        latest_user_id =  max(ratings_df["userId"].max(), int(genDb.get("latest_user_id"))) if genDb.get("latest_user_id") else ratings_df["userId"].max()
        latest_movie_id =  max(ratings_df["movieId"].max(), int(genDb.get("latest_movie_id"))) if genDb.get("latest_movie_id") else ratings_df["movieId"].max()
        genDb.set("latest_user_id", int(latest_user_id))
        genDb.set("latest_movie_id", int(latest_movie_id))
        print ("Latest user id:{}".format(latest_user_id))
        print ("Latest movie id:{}".format(latest_movie_id))

        #Store movie details in movieDb
        movie_dict = {}
        if movieDb.get("movie_dict") is not None:
            movie_dict = json.loads(movieDb.get("movie_dict"))
        
        for i,j in enumerate(links_df['movieId']):
            if movie_dict.get(j) is None:
                imgUrl = links_df['imglink'][i]
                movie_name = movies_df['title'][i]
                genres = movies_df['genres'][i]
                year = movies_df['year'][i]
                movie_dict[j] = [movie_name, imgUrl, genres, year]
                #movieDb.rpush(j,movie_name)
                #movieDb.rpush(j, imgUrl)
        movieDb.set("movie_dict", jsonpickle.dumps(movie_dict))
        print ("MovieDB populated.")

    except Exception as e:
        print ("Error, need restart for components to work properly")
        print (traceback.print_exc())

# route http posts to this method
@app.route('/compute/movies/<userid>', methods=['POST'])
def compute_movies(userid):
    try:
        global movies_df
        print ("/compute/movies api call started")
        if json.loads(genDb.get(userid))['rate']:
            r = request
            genre_list = jsonpickle.loads(r.data)
            print (genre_list)
            #movies_df = pickle.loads(genDb.get("movies_df"))
            #movies_df = pd.read_csv("../dataset/ml_25m/movies.csv")
            result = []
            for i in genre_list:
                user_movies_df = movies_df[movies_df['genres'].str.contains(i)]
                result += user_movies_df['movieId'].tolist()
            movie_list = []
            movie_dict = json.loads(movieDb.get("movie_dict"))
            for i in list(dict.fromkeys(result)):
                genres = movie_dict[str(i)][2]
                genres = genres.split("|")
                movie_list.append([i,list(set(genres) & set(genre_list))[0]])
            userMovieDb.set(userid, jsonpickle.dumps(movie_list))

        else:
            print ('Not computing new movies for genres as user {} genre selection unchanged'.format(userid))
        
        response = {'status' : 'OK'}
        print (response)

    except Exception as e:
        response = { 'status' : 'error'}
        print (traceback.print_exc())

    # encode response using jsonpickle
    response_pickled = jsonpickle.encode(response)

    return Response(response=response_pickled, status=200, mimetype="application/json")



# route http posts to this method
@app.route('/compute/recommendations/<userid>', methods=['POST'])
def compute_recommendations(userid):
    global ratings_df, movies_df
    try:
        print ("/compute/recommendations/ api call started")

        if json.loads(genDb.get(userid))['recc']:		#<userid><'recc':true/fasle, 'rate':true/false>

            print ("Computing new recommendations for user {} based on active ratings".format(userid))
        
            print (ratings_df.head())
            print (movies_df.head())

            user_dict = jsonpickle.loads(activeUserRatingDb.get(userid))
            userInput = []
            movie_dict = jsonpickle.loads(movieDb.get("movie_dict"))
            for key in user_dict.keys():
                entry = {'title': movie_dict[key][0], 'rating': float(user_dict[key][0])}
                userInput.append(entry)
            inputMovies = pd.DataFrame(userInput)
            print (inputMovies)

            #collaborative filtering begins
            #---------------------------------------------------------------------------------------------------------------------------
            #---------------------------------------------------------------------------------------------------------------------------
            #Filtering out the movies by title
            inputId = movies_df[movies_df['title'].isin(inputMovies['title'].tolist())]
            #Then merging it so we can get the movieId. It's implicitly merging it by title.
            inputMovies = pd.merge(inputId, inputMovies)
            #Dropping information we won't use from the input dataframe
            #inputMovies = inputMovies.drop('year', 1)
            print (inputMovies)
            #Filtering out users that have watched movies that the input has watched and storing it
            userSubset = ratings_df[ratings_df['movieId'].isin(inputMovies['movieId'].tolist())]
            print (userSubset.head())
            #Groupby creates several sub dataframes where they all have the same value in the column specified as the parameter
            userSubsetGroup = userSubset.groupby(['userId'])
            #print (userSubsetGroup.get_group(1130))
            #Sorting it so users with movie most in common with the input will have priority
            userSubsetGroup = sorted(userSubsetGroup,  key=lambda x: len(x[1]), reverse=True)
            print (userSubsetGroup[0:3])
            #Taking 100 users
            userSubsetGroup = userSubsetGroup[0:100]

            #Store the Pearson Correlation in a dictionary, where the key is the user Id and the value is the coefficient
            pearsonCorrelationDict = {}

            #For every user group in our subset
            for name, group in userSubsetGroup:
                #Let's start by sorting the input and current user group so the values aren't mixed up later on
                group = group.sort_values(by='movieId')
                inputMovies = inputMovies.sort_values(by='movieId')
                #Get the N for the formula
                nRatings = len(group)
                #Get the review scores for the movies that they both have in common
                temp_df = inputMovies[inputMovies['movieId'].isin(group['movieId'].tolist())]
                #And then store them in a temporary buffer variable in a list format to facilitate future calculations
                tempRatingList = temp_df['rating'].tolist()
                #Let's also put the current user group reviews in a list format
                tempGroupList = group['rating'].tolist()
                #Now let's calculate the pearson correlation between two users, so called, x and y
                Sxx = sum([i**2 for i in tempRatingList]) - pow(sum(tempRatingList),2)/float(nRatings)
                Syy = sum([i**2 for i in tempGroupList]) - pow(sum(tempGroupList),2)/float(nRatings)
                Sxy = sum( i*j for i, j in zip(tempRatingList, tempGroupList)) - sum(tempRatingList)*sum(tempGroupList)/float(nRatings)
                
                #If the denominator is different than zero, then divide, else, 0 correlation.
                if Sxx != 0 and Syy != 0:
                    pearsonCorrelationDict[name] = Sxy/sqrt(Sxx*Syy)
                else:
                    pearsonCorrelationDict[name] = 0
                
            pearsonDF = pd.DataFrame.from_dict(pearsonCorrelationDict, orient='index')
            pearsonDF.columns = ['similarityIndex']
            pearsonDF['userId'] = pearsonDF.index
            pearsonDF.index = range(len(pearsonDF))
            print (pearsonDF.head())
            #Get the top 50 users that are most similar to the input.
            topUsers=pearsonDF.sort_values(by='similarityIndex', ascending=False)[0:50]
            print (topUsers.head())

            topUsersRating=topUsers.merge(ratings_df, left_on='userId', right_on='userId', how='inner')

            #Multiplies the similarity by the user's ratings
            topUsersRating['weightedRating'] = topUsersRating['similarityIndex']*topUsersRating['rating']
            print (topUsersRating.head())
            #Applies a sum to the topUsers after grouping it up by userId
            tempTopUsersRating = topUsersRating.groupby('movieId').sum()[['similarityIndex','weightedRating']]
            tempTopUsersRating.columns = ['sum_similarityIndex','sum_weightedRating']
            print (tempTopUsersRating.head())

            #Creates an empty dataframe
            recommendation_df = pd.DataFrame()
            #Now we take the weighted average
            recommendation_df['weighted average recommendation score'] = tempTopUsersRating['sum_weightedRating']/tempTopUsersRating['sum_similarityIndex']
            recommendation_df['movieId'] = tempTopUsersRating.index

            recommendation_df = recommendation_df.sort_values(by='weighted average recommendation score', ascending=False)
            print (recommendation_df.head())
            #Taking top 20 recommendations
            #movies_df.loc[movies_df['movieId'].isin(recommendation_df.head(20)['movieId'].tolist())]

            #Store top 20 movie recommendations in the userReccDb
            recc_list = []
            user_rated_movies = topUsersRating['movieId'].tolist()
            for i in recommendation_df['movieId']:
                weighted_rating = recommendation_df.loc[recommendation_df['movieId'] == i, 'weighted average recommendation score'].iloc[0]
                if (weighted_rating >= 4.0 and weighted_rating <= 5.00):        #only recommend high rated movies from similar users
                    count = user_rated_movies.count(i)
                    match_percent = int((count/50) * 100)   #finding match percent - hitratio@N evaluation - percentage of similar users who has watched the recommended movie - 
                    genres = movie_dict[str(i)][2]
                    genres = genres.split("|")
                    recc_list.append([i,genres[0], match_percent, weighted_rating])
            print ("Total number of recommendations for userId {} - {}".format(userid, len(recc_list)))
            recc_list = sorted(recc_list, key=lambda x: x[2], reverse=True)
            #print (recommendation_df.head(10)['movieId'])
            print (recc_list[:10])
            userReccDb.set(userid, jsonpickle.dumps(recc_list))
            calls_dict = json.loads(genDb.get(userid))
            calls_dict['recc'] = False
            genDb.set(userid, jsonpickle.dumps(calls_dict))		#<userid><'recc':true/fasle, 'rate':true/false>

        else:
            print ('Not computing new recommendations as user {} active ratings unchanged'.format(userid))
        
        response = {'status' : 'OK'}
        print (response)

    except Exception as e:
        response = { 'status' : 'error'}
        print (traceback.print_exc())

    # encode response using jsonpickle
    response_pickled = jsonpickle.encode(response)

    return Response(response=response_pickled, status=200, mimetype="application/json")
    
#initia;ize application
genres = ["Adventure", "Animation", "Children", "Comedy", "Fantasy", "Romance", "Drama", "Documentary", "Action", "Crime", "Thriller",
        "Musical", "War", "Mystery", "Sci-Fi", "Western", "IMAX", "Horror", "Film-Noir"]

print ("Initializing application...")

initialize_application()

# start flask app
app.run(host="0.0.0.0", port=5000)