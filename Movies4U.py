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

#streamlit page settings
st.set_page_config(layout="wide")
page_bg_img = '''
<style>
body {
background-image: url("https://oldschoolgrappling.com/wp-content/uploads/2018/08/Background-opera-speeddials-community-web-simple-backgrounds.jpg");
background-size: cover;
}
</style>
'''

st.markdown(page_bg_img, unsafe_allow_html=True)

##
## Configure test vs. production
##
redisHost = os.getenv("REDIS_HOST") or "localhost"
restHost = os.getenv("REST") or "localhost:5000"
addr = "http://" + restHost

#redis db connections
genDb = redis.StrictRedis(host=redisHost, db=0, decode_responses=True)
loginDb = redis.StrictRedis(host=redisHost, db=1, decode_responses=True)    # userName -> [passwordHash, userId]
activeUserRatingDb = redis.StrictRedis(host=redisHost, db=2, decode_responses=True)    # userId -> userInputrecs dictionary <movieId><[rating,genre]>
movieDb = redis.StrictRedis(host=redisHost, db=3, decode_responses=True)    # movieId -> [movieName, ImageUrl, genres, year]
userMovieDb = redis.StrictRedis(host=redisHost, db=4, decode_responses=True)    # userId -> [[user genre filtered movieId, genre]]
userReccDb = redis.StrictRedis(host=redisHost, db=5, decode_responses=True)    # userId -> [[Recommended movieId,genre]]

# Security
def make_hashes(password):
	return hashlib.sha256(str.encode(password)).hexdigest()

def check_hashes(password,hashed_text):
	if make_hashes(password) == hashed_text:
		return hashed_text
	return False

#Renders 'Rate Movies' section
def render_movie_list(login_userid, start_index, rec_dict):
	cols = st.beta_columns(12)
	rating_list = []
	ind = 0
	movie_dict = json.loads(movieDb.get("movie_dict"))
	user_movie_list = json.loads(userMovieDb.get(login_userid))
	total_movies = 24
	for i in range(int(total_movies/6)+1):
		for j in range(0, 12, 2):
			movieId = str(user_movie_list[start_index + ind][0])
			genre = user_movie_list[start_index + ind][1]
			movieName = movie_dict[movieId][0]
			movieNameShorten = movieName[:8] + '..' if len(movieName) > 8 else movieName
			movieImg = movie_dict[movieId][1]
			year = movie_dict[movieId][3]
			cols[j].image(movieImg, width=100)
			expander = cols[j].beta_expander(movieNameShorten, expanded=False)
			with expander:
				st.write("{} ({})".format(movieName,genre))
				st.write(year)
			v = 0.0
			if rec_dict.get(movieId) is not None:
				v = float(rec_dict.get(movieId)[0])
			val = cols[j].slider(label="Rating", min_value=0.0, max_value=5.0, step=0.5, value=v, format='%.1f', key=start_index + ind)
			if val > 0.0:
				rec_dict[movieId] = [str(val),genre]
			ind += 1
			if ind == total_movies:
				return rec_dict
	return rec_dict

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
			rating = float(rec_dict.get(movieId)[0])
			genre = rec_dict.get(movieId)[1]
			expander = cols[j].beta_expander(movieNameShorten, expanded=False)
			with expander:
				st.write("{} ({})".format(movieName,genre))
				st.write(year)
				st.write("My rating: {}".format(rating))
			ind += 1
			if ind == total_movies:
				return

#Renders 'Movie Recommendations' section
def display_recommendations(login_userid, start_index, total_movies, recc_list):
	cols = st.beta_columns(12)
	ind = 0
	movie_dict = json.loads(movieDb.get("movie_dict"))
	for i in range(int(total_movies/6)+1):
		for j in range(0, 12, 2):
			movieId = str(recc_list[start_index+ind][0])
			genre = recc_list[start_index+ind][1]
			match_percent = recc_list[start_index+ind][2]
			movieName = movie_dict[movieId][0]
			movieNameShorten = movieName[:8] + '..' if len(movieName) > 8 else movieName
			movieImg = movie_dict[movieId][1]
			year = movie_dict[movieId][3]
			cols[j].image(movieImg, width=100)
			expander = cols[j].beta_expander(movieNameShorten, expanded=False)
			with expander:
				st.write("{} ({})".format(movieName,genre))
				st.write(year)
				st.write("{}% match".format(match_percent))
			ind += 1
			if ind == total_movies:
				return

@st.cache(suppress_st_warning=True, allow_output_mutation=True)
def getSessionState():
	print ("Creating new session")
	return SessionState.get(logout=False, show_movie_count=0, show_reco_count=0, rec_dict={}, options=[], api_call=False)


def main():
	"""Movie Recommender App"""
	global latest_user_id

	st.title("Movie Recommender System")

	menu = ["Home","Login","SignUp"]
	choice = st.sidebar.selectbox("Menu",menu)

	session_state = getSessionState()

	if choice == "Home":
		st.subheader("Home")
		session_state.show_movie_count = 0
		session_state.show_reco_count = 0
		session_state.rec_dict = {}
		session_state.options =[]
		session_state.api_call = False
		st.image("https://i.pinimg.com/originals/af/21/0f/af210fbb1e24644723dbe71312595034.jpg", use_column_width=True)

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
						session_state.show_movie_count = 0
						session_state.show_reco_count = 0
						session_state.rec_dict = {}
						session_state.options =[]
						session_state.api_call = False
						if st.button("Login Again!"):
							st.write("true")

					else:

						st.success("Logged In as {}".format(username))
						login_userid = loginDb.lindex(username, 1)

						task = st.selectbox("Task",["Rated Movies","Movie Recommendations","Rate Movies"])
						userInput = activeUserRatingDb.get(login_userid)

						if task == "Rated Movies":
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
									with st.spinner("Computing your personalized recommendations. Please Wait.."):
										response = {}
										if not session_state.api_call:
											#This boolean handles Kubernetes health check to prevent multiple compute recc calls
											session_state.api_call = True
											headers = {'content-type': 'application/json'}
											url = addr + '/compute/recommendations/' + login_userid
											response = requests.post(url, headers=headers)
										calls_dict = json.loads(genDb.get(login_userid))
										if (response and json.loads(response.text)['status'] == 'OK') or (calls_dict['recc'] == False):
											session_state.api_call = False
											if st.button("Show More", key=1):
												session_state.show_reco_count += 24
											if st.button("Back", key=1):
												session_state.show_reco_count = max(0, session_state.show_reco_count-24)
											with st.spinner("Listing data. Please Wait.."):
												st.write("Showing top {} recommendations".format(str(session_state.show_reco_count) + "-" + str(session_state.show_reco_count+24)))
												recc_list = json.loads(userReccDb.get(login_userid))
												if recc_list:
													if session_state.show_reco_count < (len(recc_list)-24):
														display_recommendations(login_userid, session_state.show_reco_count, 24, recc_list)
													else:
														count = len(recc_list) - session_state.show_reco_count
														display_recommendations(login_userid, session_state.show_reco_count, count, recc_list)
													#calls_dict = json.loads(genDb.get(login_userid))
													#calls_dict['recc'] = False
													#genDb.set(login_userid, jsonpickle.dumps(calls_dict))		#<userid><'recc':true/fasle, 'rate':true/false>
												else:
													st.write("Not enough movies rated. Please rate few more.")
													raise Exception("Not enough ratings. Need atleast 5")

										else:
											st.warning("Still computing....Please wait.")
											st.button('Force Retry', key=1)
								except Exception as e:
									st.error('Error Occurred - {}'.format(str(e)))
									print (traceback.print_exc())
									st.button('Try Again', key=1)

							else:
								st.subheader("Please rate movies to get new recommendations.")

						elif task == "Rate Movies":
							#get genres - user should select upto 5 genres
							genres = [genDb.lindex("genres", i) for i in range(0, genDb.llen("genres"))]
							options = st.multiselect("Choose atleast 5 Genres", genres)
							if len(options) >= 5:
								#REST api call for compute movies to rate -
								try:
									if session_state.options != options:
										calls_dict = json.loads(genDb.get(login_userid))
										calls_dict['rate'] = True
										genDb.set(login_userid, jsonpickle.dumps(calls_dict))		#<userid><'recc':true/fasle, 'rate':true/false>
									headers = {'content-type': 'application/json'}
									url = addr + '/compute/movies/' + login_userid
									data = jsonpickle.encode(options)
									response = requests.post(url, data=data, headers=headers)
									calls_dict = json.loads(genDb.get(login_userid))
									calls_dict['rate'] = False
									genDb.set(login_userid, jsonpickle.dumps(calls_dict))		#<userid><'recc':true/fasle, 'rate':true/false>
									session_state.options = options
									if json.loads(response.text)['status'] == 'OK':
										user_movie_list = json.loads(userMovieDb.get(login_userid))
										total_movies = len(user_movie_list)

										#check if previous recommendation list exists for current user to update - otherwise create new
										original_dict = {}		#<movieId> <[rating,genre]>
										if activeUserRatingDb.get(login_userid):
											original_dict = json.loads(activeUserRatingDb.get(login_userid))
											if not session_state.rec_dict:
												session_state.rec_dict = original_dict

										ratings = []
										if total_movies > 0:
											if st.button("Show More", key=2):
												session_state.show_movie_count += 24
											if st.button("Back", key=2):
												session_state.show_movie_count = max(0, session_state.show_movie_count-24)
											with st.spinner("Fetching data. Please Wait.."):
												st.write("Showing {} movies to rate (Please rate atleast 5)".format(str(session_state.show_movie_count) + "-" + str(session_state.show_movie_count+24)))
												if session_state.show_movie_count < (total_movies-24):
													session_state.rec_dict = render_movie_list(login_userid, session_state.show_movie_count, session_state.rec_dict)

										if st.button("Submit"):
											if original_dict:		#update
												for key in session_state.rec_dict:
													original_dict[key] = session_state.rec_dict[key]
											else:
												original_dict = session_state.rec_dict		#create new

											activeUserRatingDb.set(login_userid, jsonpickle.dumps(original_dict))	#add to db
											session_state.rec_dict = {}		#clear temp dictionary
											calls_dict = json.loads(genDb.get(login_userid))
											calls_dict['recc'] = True
											session_state.api_call = False
											genDb.set(login_userid, jsonpickle.dumps(calls_dict))		#<userid><'recc':true/fasle, 'rate':true/false>
											st.success("You have successfully submitted your ratings")
									else:
										st.write(json.loads(response.text)['status'])
										st.button('Retry', key=2)
								
								except Exception as e:
									st.error('Error Occurred - {}'.format(str(e)))
									print (traceback.print_exc())
									st.button('Try Again', key=2)
						
				else:
					st.warning("Incorrect Username/Password")

			else:
				session_state.show_movie_count = 0
				session_state.show_reco_count = 0
				session_state.rec_dict = {}
				session_state.options =[]
				session_state.api_call = False
				session_state.logout = False


	elif choice == "SignUp":
		try:
			session_state.show_movie_count = 0
			session_state.show_reco_count = 0
			session_state.rec_dict = {}
			session_state.options =[]
			session_state.api_call = False
			st.subheader("Create New Account")
			new_user = st.text_input("UserName")
			new_password = st.text_input("Password",type='password')
			if st.button("Signup"):
				if(not loginDb.llen(new_user)):
					userid = int(latest_user_id)+1
					loginDb.rpush(new_user, make_hashes(new_password), str(userid))
					st.success("You have successfully created a valid Account")
					st.info("Go to Login Menu to login")
					genDb.set("latest_user_id", userid)
					genDb.set(userid, jsonpickle.dumps({}))
				else:
					st.warning("User already exists. Please login.")

		except Exception as e:
			st.error("Error signing up - {}".format(str(e)))
			print (traceback.print_exc())


if __name__ == '__main__':
	try:
		#initialize()

		latest_user_id = genDb.get("latest_user_id")
		latest_movie_id = genDb.get("latest_movie_id")

		main()
	
	except Exception as e:
		#restart required
		st.error("Exception occurred - need server restart - {}".format(str(e)))
		print("Exception occurred, need restart...\nDetail:\n%s" % e)
		print (traceback.print_exc())