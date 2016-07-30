# Pokemon Go Working Bot Hack


## USE WITH CAUTION! 
Niantic may ban you if you run the bot while signed in through your phone.


## Important Announcement
If your bot stops working all of a sudden and doesn't move, input your latitude and longitude manually in pokebot.py. This happened because there is a limit to how many calls you can make for the API. Also, I won't be able to respond to all issues asap, due to the busy schedule ahead of me. I may go back to this project in a week or two. Cheers!


## Changes and updates
1. Now you can hatch and incubate eggs. In order to do this, change step size in the config.json file to like 1 or 2 or something like that. Step size corresponds to the meters traveled per server call.
2. Terminal/CMD output is so much more cleaner
3. Pokemon and transfered and you can get their candy
4. Easier and faster to level up and catch rare pokemon


## Instructions
1. Download or fork project and open up zip file.
2. Open up CMD/Terminal and change directory to that folder; for example, if I saved it the file in my desktop, I would `cd Desktop` and then `cd Pokemon-Go-Bot-Working-Hack-API-master`
3. You need to install Python version 2.7 and have pip installed; if you don't have that, refer to tutorials on the web.
4. Run the following line on terminal/CMD: `pip install -r requirements.txt` If that doesn't work then just add `sudo` to the beginning and enter the password for your main computer account.
5. Create a google maps API server key and activate it:
    1. Create it here: https://console.developers.google.com/projectselector/apis/credentials
    2. Then activate Gmaps Direction API here (select your project on the dropdown menu): https://console.developers.google.com/apis/api/directions_backend/overview?project=_
6. Create two another keys with different project. You have 2500 request per day quota per project.
7. Copy config.json.example to a new file: config.json. Put in your username, password, location (any Gmaps searchable location, e.g: Sydney AU), your google maps API keys which you created earlier.
8. Run the following line on terminal/CMD if you login into Pokemon Go with Google: `python pokebot.py -i 0` and `python pokebot.py -i 1` if you use Pokemon Trainer's Club
9. You can optionally run it with `--cache` to the end after the first time. For example, `python pokebot.py -i 0 --cache`
9. Many thanks to Tejado, Milaly, and the other wonderful devs that worked on this project!


## TODO
1. If your pokebox is full, then the bot won't do anything as of right now; I can do something about this later. Just transfer some pokemon manually for now. But with the bot, if you start off with like 100 pokemon, it will take quite some time to fill up, since it transfers pokemon that don't make the cutoffs that are set in config.json
2. Throw the type of ball based on the color of the circle of the pokemon
