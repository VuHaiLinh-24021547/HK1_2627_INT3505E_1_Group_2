league of legends match history api (just clone op.gg)
object:
	player: id, name_with_hashtag, recent_games_id[20]
	game: id, players_id[10], champion_id[10], objective_id, time_end, team_win(categorical: [red, blue]), champion_level_in_the_end[10]
	champion: id, name
	event_in_game: id, game_id, time_stamp, event_type(categorical: [red kill, blue kill, red take objective, blue take objective])
		who kills? who was killed? which team takes objective? will be added later 
	item: id, name
	objective: id, name
GET: 
	/players: only return id, name_with_hashtag
	/players/<int:id>: return all fields
	/champions
	/games: return id, players_id, champion_id, team_win, time_end
	/games/<int:id>: return all fields in event_in_game and game
	/items
	/objectives
	/players_games_info?player_id=&game_id=: (added later)
api design requirements:
	Restful
	return json
	GET method must have cache and pagination
	HTTP methods must be safe or idempotent
	Authorization: JWT, OAuth 2.0
	each function must have unit test
	avoid N+1 queries
	avoid SQL injection
	automated test suite with postman
	only admin role can use DELETE method
	use extension. blueprint, application factory