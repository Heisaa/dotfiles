#!/bin/sh
# Prints mango's current key mode for the custom/keymode module, one line per
# change. An empty line hides the module, so nothing shows in the default mode.
mmsg watch keymode | jq --unbuffered -r '.keymode
    | if . == "default" then ""
      elif . == "hibernate" then "hibernate? [h]yes [esc]no"
      elif . == "exit" then "exit mango? [y]es [esc]no"
      else . end'
