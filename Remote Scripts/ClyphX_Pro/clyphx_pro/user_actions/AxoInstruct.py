# AxoInstruct
# Multi-user cue lists and stage instructions with Ableton Live, ClyphX Pro and TouchOSC
# (c) 2019-2022, Matthias Farian / Axoplasma (https://github.com/axoplasma/AxoInstruct)
# 
# AxoInstruct is licensed under the Mozilla Public License 2.0
# https://github.com/axoplasma/AxoInstructV2/blob/master/LICENSE
# 
from ClyphX_Pro.clyphx_pro.ParseUtils import parse_number
from ClyphX_Pro.clyphx_pro.UserActionsBase import UserActionsBase
from ClyphX_Pro.clyphx_pro.ClyphXComponentBase import ClyphXComponentBase

import json
import os.path
from os.path import expanduser
import re
import base64

DEBUG_LOG = False
DEBUG_OSC = False

class AxoInstruct(UserActionsBase):
    
    def create_actions(self):
        self.add_global_action('init_instruct', self.init_instruct)
        self.add_global_action('prep', self.prepare_song)
        self.add_global_action('instruct', self.instruct)
        self.add_global_action('debug_instruct', self.debug_instruct)
        

    def init_instruct(self, _, args):
        # Send full reset to TOSC
        self._send_message(str("/reset"), str("true"), "single")
        
        # provide config to OSC receiver
        self._load_json(args)
        self._send_config()
        
        # reset current configuration
        self._current_config = {}
        self._current_config["channels"] = {}
        self._current_config["songs"] = {}
        self._current_config["cue_list"] = {}
        self._current_config["current_cue"] = {}
        self._current_config["current_song"] = {}
        
        # dynamically populate channels from JSON config
        chData = self._config_data["AxoInstruct"]["config"]["channels"]
        for channel in chData:
            self._current_config["channels"][channel] = channel
            self._current_config["current_cue"][channel] = 0
            self._send_message(str("/cue" + "/" + channel), _) # Stop scheduled cue list updates
        self._debug("Channels: %s" % self._current_config["channels"])
        self._debug("Current cue: %s" % self._current_config["current_cue"])

        # dynamically populate songs from JSON config
        songData = self._config_data["AxoInstruct"]["songs"]
        for song in songData.keys():
            self._current_config["songs"][song] = songData[song]["name"]
        self._debug("Songs: %s" % self._current_config["songs"])
        
        
    def prepare_song(self, _, args):
        flag_song_valid = False
        
        # Set song internally and in TOSC
        if str(args) in self._current_config["songs"]:
            
            self._current_config["current_song"] = str(args)
            self._send_message(str("/song"), str(args), "single")
            flag_song_valid = True
        elif str(args[1:-1]) in self._current_config["songs"]:
            self._current_config["current_song"] = str(args[1:-1])
            self._send_message(str("/song"), str(args[1:-1]), "single")
            flag_song_valid = True
        else:
            self._debug("Invalid song: %s" % args)
            self._debug("Available songs: %s" % (self._current_config["songs"]))
            
        if flag_song_valid is True:
            # Reset cue list internally and in TOSC
            self._current_config["cue_list"] = {}
            self._current_config["current_cue"] = {}
            
            # for channel in self._current_config["channels"].keys():
            for channel in self._current_config["channels"]:
                self._debug("Processing channel: %s" % channel)
                self._send_message("/cue" + str("/" + channel), _) # Stop scheduled cue list updates
                self._current_config["cue_list"][channel] = self._config_data["AxoInstruct"]["songs"][self._current_config["current_song"]]["instructions"][channel]
                self._current_config["current_cue"][channel] = 0
                self._send_message(str("/reset" + "/" + channel), str("true"), "single")
                self._debug("[%s] cue list: %s" % (channel, self._current_config["cue_list"][channel]))
            
            self._debug("Preparation completed: %s (%s)" % (self._current_config["songs"][self._current_config["current_song"]], self._current_config["current_song"]))
            
        
        
    def instruct(self, _, args):
        flag_cue_valid = False
        
        subargs = args.split()
        # self._debug("self._current_config[current_song]: %s" % self._current_config["current_song"])
        if self._current_config["current_song"]:
            if len(subargs) == 2:
                arg_channel = subargs[0]
                arg_cue = subargs[1]
                
                if arg_channel in self._current_config["channels"]:
                    self._debug("Valid channel: check")
                    current_channel = self._current_config["channels"][arg_channel]
                    self._debug("self._current_config[cue_list]: %s" % self._current_config["cue_list"])
                    cue_list_short = self._current_config["cue_list"][current_channel]
                    self._debug("Valid channel: check 2")
                    len_cue_list = len(cue_list_short)
                    
                    if str(arg_cue).lower() == "first":
                        self._debug("First cue: check")
                        self._current_config["current_cue"][current_channel] = 1
                        flag_cue_valid = True
                    elif str(arg_cue).lower() == "last":
                        self._debug("Last cue: check")
                        self._current_config["current_cue"][current_channel] = len_cue_list
                        flag_cue_valid = True
                    elif str(arg_cue).lower() == "prev":
                        self._debug("Prev cue: check")
                        if self._current_config["current_cue"][current_channel] > 1:
                            self._debug("Correct range: check")
                            self._current_config["current_cue"][current_channel] = self._current_config["current_cue"][current_channel] - 1
                            flag_cue_valid = True
                    elif str(arg_cue).lower() == "next":
                        self._debug("Next cue: check")
                        if self._current_config["current_cue"][current_channel] < len_cue_list:
                            self._debug("Correct range: check")
                            self._current_config["current_cue"][current_channel] = self._current_config["current_cue"][current_channel] + 1
                            flag_cue_valid = True
                    elif isinstance(int(arg_cue), int):
                        self._debug("Numeric cue: check")
                        if int(arg_cue) > 0 and int(arg_cue) <= len_cue_list:
                            self._debug("Correct range: check")
                            self._current_config["current_cue"][current_channel] = int(subargs[1])
                            flag_cue_valid = True
                    else:
                        self._debug("Invalid cue: %s" % arg_cue)
                        self._debug("None of First/Last/Prev/Next/Numeric")
                    
                    if flag_cue_valid is True:
                        self._send_message("/cue" + str("/" + self._current_config["channels"][arg_channel]), self._current_config["current_cue"][current_channel])
                        self._debug("[%s] Cue %s" % (self._current_config["channels"][arg_channel], self._current_config["current_cue"][current_channel]))
                else:
                    self._debug("Invalid channel: %s" % arg_channel)
            else:
                self._debug("Invalid number of arguments (%i)" % len(subargs))
        else:
            self._debug("No song prepared")
            
            
    def debug_instruct(self, _, args):
        if args == "1" or args.lower() == "on":
            self._DEBUG_LOG = True
            self._DEBUG_OSC = True
            self._debug("Activating debug output")
        elif args == "0" or args.lower() == "off":
            self._debug("Deactivating debug output")
            self._DEBUG_LOG = False
            self._DEBUG_OSC = False
        else:
            self._debug("Toggling debug output")
            self._DEBUG_LOG = not(self._DEBUG_LOG)
            self._DEBUG_OSC = not(self._DEBUG_OSC)
            self._debug("Toggling debug output")
        
        
    def __init__(self, cx_core, *a, **k):
        self._DEBUG_LOG = DEBUG_LOG
        self._DEBUG_OSC = DEBUG_OSC
        super(AxoInstruct, self).__init__(cx_core, *a, **k)
        self._server = None
        self.canonical_parent.schedule_message(2, self._do_init, cx_core)
        
        
    def _do_init(self, cx_core):
        # need to use scheduling here as user actions are created before the OSC server.
        self._server = cx_core.osc_server
        
        
    def _debug(self, msg):
        if self._DEBUG_LOG is True:
            self.canonical_parent.show_message(str(msg))
        if self._DEBUG_OSC is True:
            self._send_message("/DEBUG", str(msg), "single")
        
        
    def _encode_config(self):
        msg = json.dumps(self._config_data, separators=(',', ':'))
        self._debug('Compacted JSON config %s: ' % msg)
        
        msgBytes = msg.encode('ascii')
        base64Bytes = base64.b64encode(msgBytes)
        base64Message = base64Bytes.decode('ascii')
        
        return base64Message
        
        
    def _send_message(self, addr, msg="", msgType=""):
        self._server.sendOSC(str(addr), msg)
        if msgType == "single":
            self._server.sendOSC(str(addr)) # workaround: remove message from ClyphX's scheduler
        
        
    def _send_config(self):
        self._debug('"AxoInstruct" %s' % json.dumps(self._config_data["AxoInstruct"]))
        self._send_message("/config", self._encode_config(), "single")
        self._debug('Config sent successfully')
        
        
    def _load_json(self, args):
        jsonFile = os.path.join(expanduser("~"), 'Documents', 'AxoInstruct', args[1:-1])
        self._debug('Provided jsonFile: %s' % jsonFile)
        
        if os.path.isfile(jsonFile):
            self._debug('JSON file %s found ...' % jsonFile)
        else:
            jsonFile = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo.json") # User Remote Script folder
            self._debug('ERROR: specified JSON file not found, using %s instead' % jsonFile)
        
        with open(jsonFile, 'r') as infile:
            jsonFileData = infile.read()
            self._debug('JSON file read')
            self._config_data = json.loads(jsonFileData)
            self._debug('Prepared self._config_data')
        
