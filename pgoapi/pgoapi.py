# Credits to Tejado and the devs over at the subreddit /r/PokemonGoDev -TomTheBotter

from __future__ import absolute_import

import logging
import re
from itertools import chain, imap

import requests
from .utilities import f2i, h2f
from pgoapi.rpc_api import RpcApi
from pgoapi.auth_ptc import AuthPtc
from pgoapi.auth_google import AuthGoogle
from pgoapi.exceptions import AuthException, NotLoggedInException, ServerBusyOrOfflineException
from . import protos
from pgoapi.protos.POGOProtos.Networking.Requests_pb2 import RequestType
from pgoapi.protos.POGOProtos import Inventory_pb2 as Inventory

import pickle
import random
import json
from pgoapi.location import *
import pgoapi.protos.POGOProtos.Enums_pb2 as RpcEnum
from pgoapi.poke_utils import *
from time import sleep
from collections import defaultdict
from operator import itemgetter, attrgetter
import os.path

logger = logging.getLogger(__name__)
BAD_ITEM_IDS = [101,102,701,702,703] #Potion, Super Potion, RazzBerry, BlukBerry, Revive

# Minimum amount of the bad items that you should have ... Modify based on your needs ... like if you need to battle a gym?
MIN_BAD_ITEM_COUNTS = {Inventory.ITEM_POTION: 10,
                       Inventory.ITEM_SUPER_POTION: 10,
                       Inventory.ITEM_RAZZ_BERRY: 10,
                       Inventory.ITEM_BLUK_BERRY: 10,
                       Inventory.ITEM_NANAB_BERRY: 10,
                       Inventory.ITEM_REVIVE: 10}
MIN_SIMILAR_POKEMON = 1


class PGoApi:

    API_ENTRY = 'https://pgorelease.nianticlabs.com/plfe/rpc'

    def __init__(self, config, pokemon_names):

        self.log = logging.getLogger(__name__)

        self._auth_provider = None
        self._api_endpoint = None
        self.config = config
        self._position_lat = 0
        self._position_lng = 0
        self._position_alt = 0
        self._posf = (0,0,0)
        self.MIN_KEEP_IV = config.get("MIN_KEEP_IV", 0)
        self.KEEP_CP_OVER = config.get("KEEP_CP_OVER", 0)
        self._req_method_list = []
        self._heartbeat_number = 5
        self.pokemon_names = pokemon_names
        self.AUTO_EVOLVE_POKEMON_IDS = config.get("AUTO_EVOLVE_POKEMON_IDS", [])
        self.KEEP_BEST_POKEMON_ONLY = config.get("KEEP_BEST_POKEMON_ONLY", False)
        self.KEEP_BEST_POKEMON_MIN_CP = config.get("KEEP_BEST_POKEMON_MIN_CP", 100)
        self.KEEP_BEST_POKEMON_MIN_IV = config.get("KEEP_BEST_POKEMON_MIN_IV", 20)

    def call(self):
        if not self._req_method_list:
            return False

        if self._auth_provider is None or not self._auth_provider.is_login():
            self.log.info('Not logged in')
            return False

        player_position = self.get_position()

        request = RpcApi(self._auth_provider)

        if self._api_endpoint:
            api_endpoint = self._api_endpoint
        else:
            api_endpoint = self.API_ENTRY

        self.log.debug('Execution of RPC')
        response = None
        try:
            response = request.request(api_endpoint, self._req_method_list, player_position)
        except ServerBusyOrOfflineException as e:
            self.log.info('Server seems to be busy or offline - try again!')

        # cleanup after call execution
        self.log.debug('Cleanup of request!')
        self._req_method_list = []

        return response

    def list_curr_methods(self):
        for i in self._req_method_list:
            print("{} ({})".format(RequestType.Name(i),i))
    def set_logger(self, logger):
        self._ = logger or logging.getLogger(__name__)

    def get_position(self):
        return (self._position_lat, self._position_lng, self._position_alt)
    def set_position(self, lat, lng, alt):
        self.log.debug('Set Position - Lat: %s Long: %s Alt: %s', lat, lng, alt)
        self._posf = (lat,lng,alt)
        self._position_lat = f2i(lat)
        self._position_lng = f2i(lng)
        self._position_alt = f2i(alt)

    def __getattr__(self, func):
        def function(**kwargs):

            if not self._req_method_list:
                self.log.debug('Create new request...')

            name = func.upper()
            if kwargs:
                self._req_method_list.append( { RequestType.Value(name): kwargs } )
                self.log.debug("Adding '%s' to RPC request including arguments", name)
                self.log.debug("Arguments of '%s': \n\r%s", name, kwargs)
            else:
                self._req_method_list.append( RequestType.Value(name) )
                self.log.debug("Adding '%s' to RPC request", name)

            return self

        if func.upper() in RequestType.keys():
            return function
        else:
            raise AttributeError
    def heartbeat(self):
        self.get_player()
        if self._heartbeat_number % 10 == 0:
            self.check_awarded_badges()
            self.get_inventory()
        res = self.call()
        if res.get("direction",-1) == 102:
            self.log.error("There were a problem responses for api call: %s. Restarting!!!", res)
            raise AuthException("Token probably expired?")
        self.log.debug('Heartbeat dictionary: \n\r{}'.format(json.dumps(res, indent=2)))

        if self._heartbeat_number % 20 == 0:
            if 'GET_PLAYER' in res['responses']:
                player_data = res['responses'].get('GET_PLAYER', {}).get('player_data', {})
                if os.path.isfile("accounts/%s.json" % self.config['username']):
                    with open("accounts/%s.json" % self.config['username'], "r") as f:
                        file = f.read()
                        json_file = json.loads(file)
                    inventory_items = json_file.get('GET_INVENTORY', {}).get('inventory_delta', {}).get('inventory_items', [])
                    inventory_items_dict_list = map(lambda x: x.get('inventory_item_data', {}), inventory_items)
                    player_stats = filter(lambda x: 'player_stats' in x, inventory_items_dict_list)[0].get('player_stats', {})
                else:
                    player_stats = {}
                currencies = player_data.get('currencies', [])
                currency_data = ",".join(map(lambda x: "{0}: {1}".format(x.get('name', 'NA'), x.get('amount', 'NA')), currencies))
                self.log.info("Username: %s, Lvl: %s, XP: %s/%s, Currencies: %s", player_data.get('username', 'NA'), player_stats.get('level', 'NA'), player_stats.get('experience', 'NA'), player_stats.get('next_level_xp', 'NA'), currency_data)

            if 'GET_INVENTORY' in res['responses']:
                with open("accounts/%s.json" % self.config['username'], "w") as f:
                    res['responses']['lat'] = self._posf[0]
                    res['responses']['lng'] = self._posf[1]
                    f.write(json.dumps(res['responses'], indent=2))
                self.log.info(get_inventory_data(res, self.pokemon_names))
                self.log.debug(self.cleanup_inventory(res['responses']['GET_INVENTORY']['inventory_delta']['inventory_items']))

        self._heartbeat_number += 1
        return res
    def walk_to(self,loc):
        steps = get_route(self._posf, loc, self.config.get("USE_GOOGLE", False), self.config.get("GMAPS_API_KEY", ""))
        for step in steps:
            for i,next_point in enumerate(get_increments(self._posf,step,self.config.get("STEP_SIZE", 200))):
                self.set_position(*next_point)
                self.heartbeat()
                # self.log.info("Sleeping before next heartbeat")
                sleep(2) # If you want to make it faster, delete this line... would not recommend though
                while self.catch_near_pokemon():
                    sleep(1) # If you want to make it faster, delete this line... would not recommend though



    def spin_near_fort(self):
        map_cells = self.nearby_map_objects()['responses']['GET_MAP_OBJECTS']['map_cells']
        forts = PGoApi.flatmap(lambda c: c.get('forts', []), map_cells)
        destinations = filtered_forts(self._posf,forts)
        if destinations:
            fort = destinations[0]
            # self.log.info("Walking to fort at %s,%s", fort['latitude'], fort['longitude'])
            self.walk_to((fort['latitude'], fort['longitude']))
            position = self._posf # FIXME ?
            res = self.fort_search(fort_id = fort['id'], fort_latitude=fort['latitude'],fort_longitude=fort['longitude'],player_latitude=position[0],player_longitude=position[1]).call()['responses']['FORT_SEARCH']
            self.log.debug("Fort spinned: %s", res)
            if 'lure_info' in fort:
                encounter_id = fort['lure_info']['encounter_id']
                fort_id = fort['lure_info']['fort_id']
                position = self._posf
                resp = self.disk_encounter(encounter_id=encounter_id, fort_id=fort_id, player_latitude=position[0], player_longitude=position[1]).call()['responses']['DISK_ENCOUNTER']
                self.disk_encounter_pokemon(fort['lure_info'])
            return True
        else:
            self.log.error("No fort to walk to!")
            return False

    def catch_near_pokemon(self):
        map_cells = self.nearby_map_objects()['responses']['GET_MAP_OBJECTS']['map_cells']
        pokemons = PGoApi.flatmap(lambda c: c.get('catchable_pokemons', []), map_cells)

        # catch first pokemon:
        origin = (self._posf[0], self._posf[1])
        pokemon_distances = [(pokemon, distance_in_meters(origin,(pokemon['latitude'], pokemon['longitude']))) for pokemon in pokemons]
        self.log.debug("Nearby pokemon: : %s", pokemon_distances)
        for pokemon_distance in pokemon_distances:
            target = pokemon_distance
            self.log.debug("Catching pokemon: : %s, distance: %f meters", target[0], target[1])
            self.log.info("Catching Pokemon: %s", self.pokemon_names[str(target[0]['pokemon_id'])])
            return self.encounter_pokemon(target[0])
        return False

    def nearby_map_objects(self):
        position = self.get_position()
        neighbors = getNeighbors(self._posf)
        return self.get_map_objects(latitude=position[0], longitude=position[1], since_timestamp_ms=[0]*len(neighbors), cell_id=neighbors).call()
    
    def attempt_catch(self,encounter_id,spawn_point_guid): #Problem here... add 4 if you have master ball
        for i in range(1,3): # Range 1...4 iff you have master ball `range(1,4)`
            r = self.catch_pokemon(
                normalized_reticle_size= 1.950,
                pokeball = i,
                spin_modifier= 0.850,
                hit_pokemon=True,
                normalized_hit_position=1,
                encounter_id=encounter_id,
                spawn_point_guid=spawn_point_guid,
                ).call()['responses']['CATCH_POKEMON']
            if "status" in r:
                return r

    def cleanup_inventory(self, inventory_items=None):
        if not inventory_items:
            inventory_items = self.get_inventory().call()['responses']['GET_INVENTORY']['inventory_delta']['inventory_items']
        caught_pokemon = defaultdict(list)
        for inventory_item in inventory_items:
            if "pokemon_data" in  inventory_item['inventory_item_data']:
                # is a pokemon:
                pokemon = inventory_item['inventory_item_data']['pokemon_data']
                if 'cp' in pokemon and "favorite" not in pokemon:
                    caught_pokemon[pokemon["pokemon_id"]].append(pokemon)
            elif "item" in  inventory_item['inventory_item_data']:
                item = inventory_item['inventory_item_data']['item']
                if item['item_id'] in MIN_BAD_ITEM_COUNTS and "count" in item and item['count'] > MIN_BAD_ITEM_COUNTS[item['item_id']]:
                    recycle_count = item['count'] - MIN_BAD_ITEM_COUNTS[item['item_id']]
                    self.log.info("Recycling Item_ID {0}, item count {1}".format(item['item_id'], recycle_count))
                    self.recycle_inventory_item(item_id=item['item_id'], count=recycle_count)

        for pokemons in caught_pokemon.values():
            self.auto_evolve(pokemons, inventory_items)
            self.auto_release_pokemon(pokemons, self.KEEP_BEST_POKEMON_ONLY)

        return self.call()

    
    def release_single_pokemon(self, pokemon):
        self.log.debug("Releasing pokemon: %s", pokemon)
        self.log.info("Releasing pokemon: %s (CP: %s IV: %s)", self.pokemon_names[str(pokemon['pokemon_id'])], pokemon['cp'], pokemonIV(pokemon))
        self.release_pokemon(pokemon_id = pokemon["id"])
        return True

    def auto_release_pokemon(self, pokemons, keep_best_only=False):
        if len(pokemons) > MIN_SIMILAR_POKEMON:
            if keep_best_only:
                caught_pokemon_dict = {}
                for pokemon in pokemons[MIN_SIMILAR_POKEMON:]:
                    if pokemon['pokemon_id'] not in caught_pokemon_dict:
                        caught_pokemon_dict[pokemon['pokemon_id']] = 0                    
                    if pokemonIV(pokemon) > caught_pokemon_dict[pokemon['pokemon_id']]:
                        caught_pokemon_dict[pokemon['pokemon_id']] = pokemonIV(pokemon)

                pokemons = sorted(pokemons, lambda x,y: cmp(x['pokemon_id'], y['pokemon_id']))
                for pokemon in pokemons[MIN_SIMILAR_POKEMON:]:
                    if pokemonIV(pokemon) < caught_pokemon_dict[pokemon['pokemon_id']] and pokemonIV(pokemon) < self.KEEP_BEST_POKEMON_MIN_IV:
                        self.release_single_pokemon(pokemon)
            else:
                pokemons = sorted(pokemons, lambda x,y: cmp(x['cp'],y['cp']),reverse=True)
                for pokemon in pokemons[MIN_SIMILAR_POKEMON:]:
                    if 'cp' in pokemon and pokemonIVPercentage(pokemon) < self.MIN_KEEP_IV and pokemon['cp'] < self.KEEP_CP_OVER:
                        self.release_single_pokemon(pokemon)
        return True

    def auto_evolve(self, pokemons, inventory_items):
        for pokemon in pokemons:
            if pokemon['pokemon_id'] in self.AUTO_EVOLVE_POKEMON_IDS:
                for inventory_item in inventory_items:
                    if "pokemon_family" in inventory_item['inventory_item_data'] and inventory_item['inventory_item_data']['pokemon_family']['family_id'] == 16 and inventory_item['inventory_item_data']['pokemon_family']['candy'] > 11:
                        self.log.info("Evolving pokemon: %s", self.pokemon_names[str(pokemon['pokemon_id'])])
                        self.evolve_pokemon(pokemon_id = pokemon['id'])
        return True


    def disk_encounter_pokemon(self, lureinfo):
        try:
            encounter_id = lureinfo['encounter_id']
            fort_id = lureinfo['fort_id']
            position = self._posf
            resp = self.disk_encounter(encounter_id=encounter_id, fort_id=fort_id, player_latitude=position[0], player_longitude=position[1]).call()['responses']['DISK_ENCOUNTER']
            if resp['result'] == 1:
                capture_status = -1
                while capture_status != 0 and capture_status != 3:
                    catch_attempt = self.attempt_catch(encounter_id,fort_id)
                    capture_status = catch_attempt['status']
                    if capture_status == 1:
                        self.log.debug("Caught Pokemon: : %s", catch_attempt)
                        self.log.info("Caught Pokemon:  %s (CP: %s)", self.pokemon_names[str(resp['pokemon_data']['pokemon_id'])], resp['pokemon_data']['cp'])
                        sleep(2) # If you want to make it faster, delete this line... would not recommend though
                        return catch_attempt
                    elif capture_status != 2:
                        self.log.debug("Failed Catch: : %s", catch_attempt)
                        self.log.info("Failed to catch Pokemon:  %s (CP: %s)", self.pokemon_names[str(resp['pokemon_data']['pokemon_id'])], resp['pokemon_data']['cp'])
                        return False
                    sleep(2) # If you want to make it faster, delete this line... would not recommend though
        except Exception as e:
            self.log.error("Error in disk encounter %s", e)
            return False


    def encounter_pokemon(self,pokemon):
        encounter_id = pokemon['encounter_id']
        spawn_point_id = pokemon['spawn_point_id']
        position = self._posf
        encounter = self.encounter(encounter_id=encounter_id,spawn_point_id=spawn_point_id,player_latitude=position[0],player_longitude=position[1]).call()['responses']['ENCOUNTER']
        self.log.debug("Started Encounter: %s", encounter)
        if encounter['status'] == 1:
            capture_status = -1
            while capture_status != 0 and capture_status != 3:
                catch_attempt = self.attempt_catch(encounter_id,spawn_point_id)
                capture_status = catch_attempt['status']
                if capture_status == 1:
                    self.log.debug("Caught Pokemon: : %s", catch_attempt)
                    self.log.info("Caught Pokemon:  %s ", self.pokemon_names[str(pokemon['pokemon_id'])])
                    sleep(2) # If you want to make it faster, delete this line... would not recommend though
                    return catch_attempt
                elif capture_status != 2:
                    self.log.debug("Failed Catch: : %s", catch_attempt)
                    self.log.info("Failed to Catch Pokemon:  %s", self.pokemon_names[str(pokemon['pokemon_id'])])
                return False
                sleep(2) # If you want to make it faster, delete this line... would not recommend though
        return False



    def login(self, provider, username, password,cached=False):
        if not isinstance(username, basestring) or not isinstance(password, basestring):
            raise AuthException("Username/password not correctly specified")

        if provider == 'ptc':
            self._auth_provider = AuthPtc()
        elif provider == 'google':
            self._auth_provider = AuthGoogle()
        else:
            raise AuthException("Invalid authentication provider - only ptc/google available.")

        self.log.debug('Auth provider: %s', provider)

        if not self._auth_provider.login(username, password):
            self.log.info('Login process failed')
            return False

        self.log.info('Starting RPC login sequence (app simulation)')
        self.get_player()
        self.get_hatched_eggs()
        self.get_inventory()
        self.check_awarded_badges()
        self.download_settings(hash="05daf51635c82611d1aac95c0b051d3ec088a930")

        response = self.call()

        if not response:
            self.log.info('Login failed!')
        if os.path.isfile("auth_cache") and cached:
            response = pickle.load(open("auth_cache"))
        fname = "auth_cache_%s" % username
        if os.path.isfile(fname) and cached:
            response = pickle.load(open(fname))
        else:
            response = self.heartbeat()
            f = open(fname,"w")
            pickle.dump(response, f)
        if not response:
            self.log.info('Login failed!')
            return False

        if 'api_url' in response:
            self._api_endpoint = ('https://{}/rpc'.format(response['api_url']))
            self.log.debug('Setting API endpoint to: %s', self._api_endpoint)
        else:
            self.log.error('Login failed - unexpected server response!')
            return False

        if 'auth_ticket' in response:
            self._auth_provider.set_ticket(response['auth_ticket'].values())

        self.log.info('Finished RPC login sequence (app simulation)')
        self.log.info('Login process completed')

        return True

    def main_loop(self):
        self.heartbeat()
        while True:
            self.heartbeat()
            sleep(1) # If you want to make it faster, delete this line... would not recommend though
            self.spin_near_fort()
            while self.catch_near_pokemon():
                sleep(4) # If you want to make it faster, delete this line... would not recommend though
                pass

    @staticmethod
    def flatmap(f, items):
        return chain.from_iterable(imap(f, items))
