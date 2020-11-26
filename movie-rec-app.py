import streamlit as st
import pandas as pd
import redis
import traceback
import hashlib
import os
import requests
import SessionState
import json, jsonpickle
import requests

#from streamlit.ScriptRunner import StopException, RerunException


##
## Configure test vs. production
##
redisHost = os.getenv("REDIS_HOST") or "localhost"
restHost = os.getenv("REST") or "localhost:5000"
addr = "http://" + restHost

#redis db connections
genDb = redis.StrictRedis(host=redisHost, db=0, decode_responses=True)
loginDb = redis.StrictRedis(host=redisHost, db=1, decode_responses=True)    # userName -> [passwordHash, userId]
activeUserRatingDb = redis.StrictRedis(host=redisHost, db=2, decode_responses=True)    # userId -> userInputrecs dictionary <movieId><rating>
movieDb = redis.StrictRedis(host=redisHost, db=3, decode_responses=True)    # movieId -> [movieName, ImageUrl, genres, year]
userMovieDb = redis.StrictRedis(host=redisHost, db=4, decode_responses=True)    # userId -> [user genre filtered movieIds]
userReccDb = redis.StrictRedis(host=redisHost, db=5, decode_responses=True)    # userId -> [Recommended movieIds]



# Security
def make_hashes(password):
	return hashlib.sha256(str.encode(password)).hexdigest()

def check_hashes(password,hashed_text):
	if make_hashes(password) == hashed_text:
		return hashed_text
	return False

#Renders 'Rate Movies' section
def render_movie_list(login_userid, total_movies, rec_dict):
	cols = st.beta_columns(12)
	rating_list = []
	ind = 0
	movie_dict = json.loads(movieDb.get("movie_dict"))
	print (movie_dict.get('1')[3])
	user_movie_list = json.loads(userMovieDb.get(login_userid))
	total_movies = 24
	st.write("Showing {} movies to rate".format(total_movies))
	for i in range(int(total_movies/6)+1):
		for j in range(0, 12, 2):
			movieId = str(user_movie_list[ind])
			movieName = movie_dict[movieId][0]
			movieNameShorten = movieName[:8] + '..' if len(movieName) > 8 else movieName
			movieImg = movie_dict[movieId][1]
			year = movie_dict[movieId][3]
			cols[j].image(movieImg, width=100)
			expander = cols[j].beta_expander(movieNameShorten, expanded=False)
			with expander:
				st.write(movieName)
				st.write(year)
			v = 0.0
			if rec_dict.get(movieId) is not None:
				v = rec_dict.get(movieId)
			val = cols[j].slider(label="Rating", min_value=0.0, max_value=5.0, step=0.5, value=v, format='%.1f', key=ind)
			rating_list.append(val)
			ind += 1
			if ind == total_movies:
				return rating_list
	return rating_list

#Renders 'Movies Watched' section
def display_rated_movies(login_userid, rec_dict):
	cols = st.beta_columns(12)
	movie_id_list = list(rec_dict.keys())
	ind = 0
	total_movies = len(movie_id_list)
	#total_movies = 24
	movie_dict = json.loads(movieDb.get("movie_dict"))
	for i in range(int(total_movies/6)+1):
		for j in range(0, 12, 2):
			movieId = str(movie_id_list[ind])
			movieName = movie_dict[movieId][0]
			movieNameShorten = movieName[:8] + '..' if len(movieName) > 8 else movieName
			movieImg = movie_dict[movieId][1]
			year = movie_dict[movieId][3]
			cols[j].image(movieImg, width=100)
			rating = rec_dict.get(movieId)
			#cols[j].text_input("My Rating", value=rating, key=ind)
			expander = cols[j].beta_expander(movieNameShorten, expanded=False)
			with expander:
				st.write(movieName)
				st.write(year)
				st.write("My rating: {}".format(rating))
			ind += 1
			if ind == total_movies:
				return

#Renders 'Movie Recommendations' section
def display_recommendations(login_userid):
	cols = st.beta_columns(12)
	ind = 0
	recc_list = json.loads(userReccDb.get(login_userid))
	total_movies = len(recc_list)
	movie_dict = json.loads(movieDb.get("movie_dict"))
	for i in range(int(total_movies/6)+1):
		for j in range(0, 12, 2):
			movieId = str(recc_list[ind])
			movieName = movie_dict[movieId][0]
			movieNameShorten = movieName[:8] + '..' if len(movieName) > 8 else movieName
			movieImg = movie_dict[movieId][1]
			year = movie_dict[movieId][3]
			cols[j].image(movieImg, width=100)
			expander = cols[j].beta_expander(movieNameShorten, expanded=False)
			with expander:
				st.write(movieName)
				st.write(year)
			ind += 1
			if ind == total_movies:
				return


def main():
	"""Movie Recommender App"""
	global latest_user_id

	st.set_page_config(layout="wide")

	st.title("Movie Recommender System")

	menu = ["Home","Login","SignUp"]
	choice = st.sidebar.selectbox("Menu",menu)

	session_state = SessionState.get(logout=False)

	if choice == "Home":
		st.subheader("Home")
		cols = st.beta_columns(12)
		list = {}
		ind = 0
		for j in range(2):
			for i in range(0, 12, 2):
				cols[i].image("https://s3.gaming-cdn.com/images/products/4889/orig/assassins-creed-brotherhood-deluxe-edition-cover.jpg", caption="Assassins Creed", width=100)
				val = cols[i].slider(label="Rating", min_value=0.0, max_value=5.0, step=0.5, value = 0.5, format='%.1f', key=ind)
				ind += 1
				#entry = {'title':'AC', 'rating': val}
				list['AC'] = val
				my_expander = cols[i].beta_expander("Details", expanded=True)
				with my_expander:
					st.write("Assassins Creed Brotherhood")
		st.write(list)

	elif choice == "Login":
		st.subheader("Login Section")

		if session_state.logout:
			session_state.logout = False

		else:
			username = st.sidebar.text_input("username")
			password = st.sidebar.text_input("password",type='password')
			login_checkbox = st.sidebar.empty()
			
			if login_checkbox.checkbox("Login") and not session_state.logout:
				# if password == '12345':
				
				hashed_pswd = make_hashes(password)
				login_password = loginDb.lindex(username, 0)

				if login_password == check_hashes(password,hashed_pswd):

					#session_state.logout = True
					if st.checkbox("Logout"):
						#login_checkbox.checkbox("Login", False)
						st.write("Logged out successfully")
						session_state.logout = True
						if st.button("Login Again!"):
							st.write("true")

					else:

						st.success("Logged In as {}".format(username))
						login_userid = loginDb.lindex(username, 1)

						task = st.selectbox("Task",["Movies watched","Movie Recommendations","Rate Movies"])
						userInput = activeUserRatingDb.get(login_userid)

						if task == "Movies watched":
							if activeUserRatingDb.get(login_userid):
								with st.spinner("Fetching data. Please Wait.."):
									rec_dict = json.loads(activeUserRatingDb.get(login_userid))
									display_rated_movies(login_userid, rec_dict)

							else:
								st.subheader("Please rate movies.")

						elif task == "Movie Recommendations":
							if activeUserRatingDb.get(login_userid):
								#REST api call for compute recommendations -
								try:
									headers = {'content-type': 'application/json'}
									url = addr + '/compute/recommendations/' + login_userid
									with st.spinner("Computing your personalized recommendations. Please Wait.."):
										response = requests.post(url, headers=headers)
									if json.loads(response.text)['status'] == 'OK':
										with st.spinner("Listing data. Please Wait.."):
											display_recommendations(login_userid)
											genDb.set(login_userid, 'false')		#flag to set compute new recommendations true or false

									else:
										st.write(json.loads(response.text)['status'])
										st.button('Retry', key=1)
								except Exception as e:
									st.error('Error Occurred:' + e)
									print (traceback.print_exc())
									st.button('Try Again', key=1)

							else:
								st.subheader("Please rate movies to get new recommendations.")

						elif task == "Rate Movies":
							#get genres - user should select upto 5 genres
							genres = [genDb.lindex("genres", i) for i in range(0, genDb.llen("genres"))]
							options = st.multiselect("Choose 5 Genres", genres)
							if len(options) == 5:
								#REST api call for compute movies to rate -
								try:
									headers = {'content-type': 'application/json'}
									url = addr + '/compute/movies/' + login_userid
									data = jsonpickle.encode(options)
									response = requests.post(url, data=data, headers=headers)
									if json.loads(response.text)['status'] == 'OK':
										user_movie_list = json.loads(userMovieDb.get(login_userid))
										total_movies = len(user_movie_list)

										#check if previous recommendation list exists for current user to update - otherwise create new
										rec_dict = {}		#<movieId> <rating>
										if activeUserRatingDb.get(login_userid):
											rec_dict = json.loads(activeUserRatingDb.get(login_userid))

										ratings = []
										if total_movies > 0:
											with st.spinner("Fetching data. Please Wait.."):
												ratings = render_movie_list(login_userid, total_movies, rec_dict)
										if st.button("Submit"):
											userInput = []
											for index, i in enumerate(ratings):
												if i > 0.0:
													movieId = user_movie_list[index]
													#movieTitle = movieDb.lindex(movieId, 0)
													rec_dict[movieId] = i
													#entry = {'title': movieTitle, 'rating': i}
											activeUserRatingDb.set(login_userid, jsonpickle.dumps(rec_dict))
											genDb.set(login_userid, 'true')		#flag to set compute new recommendations true or false
											st.success("You have successfully submitted your ratings")
									else:
										st.write(json.loads(response.text)['status'])
										st.button('Retry', key=2)
								
								except Exception as e:
									st.error('Error Occurred:' + e)
									print (traceback.print_exc())
									st.button('Try Again', key=2)
						
				else:
					st.warning("Incorrect Username/Password")

			else:
				session_state.logout = False


	elif choice == "SignUp":
		try:
			st.subheader("Create New Account")
			new_user = st.text_input("UserName")
			new_password = st.text_input("Password",type='password')
			if st.button("Signup"):
				if(not loginDb.llen(new_user)):
					loginDb.rpush(new_user, make_hashes(new_password), str(int(latest_user_id)+1))
					st.success("You have successfully created a valid Account")
					st.info("Go to Login Menu to login")
					genDb.set("latest_user_id", int(latest_user_id)+1)
				else:
					st.warning("User already exists. Please login.")

		except Exception as e:
			st.error("Error signing up:" + e)
			print (traceback.print_exc())


if __name__ == '__main__':
	try:

		latest_user_id = genDb.get("latest_user_id")
		latest_movie_id = genDb.get("latest_movie_id")

		main()
	
	except Exception as e:
		#restart required
		print("Exception occurred, need restart...\nDetail:\n%s" % e)
		print (traceback.print_exc())