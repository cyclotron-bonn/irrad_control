#!/bin/bash

# Script to start and stop item GmbH controller daemon
# Unfortunately, this needs sudo priveleges to launch.
# In order to prevent needing to launch the server process with sudo,
# this bash script is called as a subprocess, launching/stopping the 
# controller daemon with sudo. The start script itself,
# located at $ITEM_DAEMON_START_SCRIPT, should look like this

#   #!/bin/bash
#   # Get current directory
#   SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
#   # Switch to actual subdir containing the daemon for the respective platform
#    cd $SCRIPT_DIR/linux64
#   ./itemControllerDaemon



# Function to stop the item controller daemon
function stop_daemon {

    # Get array of all running instances PIDs of the item controller by name
    RUNNING_ITEM_DAEMONS=($(ps -e | awk -v name=$ITEM_DAEMON_PNAME '$4 == name {print $1}'))

    # Check if there are any
    if [ ${#RUNNING_ITEM_DAEMONS[@]} -ne 0 ]; then
        
        for DAEMON in ${RUNNING_ITEM_DAEMONS[@]}; do
            echo "Stopping $ITEM_DAEMON_PNAME with PID $DAEMON"
            sudo kill $DAEMON
        done

    fi
}

function start_daemon {
    
    # First stop all running instances if there are any; there can only be one at a time
    stop_daemon

    # If the start script does not exist, abort.
    if [ ! -f "$ITEM_DAEMON_START_SCRIPT" ]; then
        
        echo "$ITEM_DAEMON_START_SCRIPT does not exist. Aborting"

    else
        # Launch stupid server with sudo privileges
        sudo $ITEM_DAEMON_START_SCRIPT

    fi
}

# Needed variables
ITEM_DAEMON_PNAME="itemControllerD"
USER_HOME=$(getent passwd $USER | cut -d: -f6) 
ITEM_DAEMON_START_SCRIPT=$USER_HOME/item/start.sh
START=true

# Parse command line arguments
for CMD in "$@"; do
  case $CMD in
    # Overwrite default path to the start script
    -p=*|--path=*)
    ITEM_DAEMON_START_SCRIPT="${CMD#*=}"
    shift
    ;;
    # Start the daemon; the default, call "do-nothing" command a.k.a ':'"
    --start)
    :
    shift
    ;;
    # Checkout branch of irrad_control
    --stop)
    START=false
    shift
    ;;
    # Unknown option
    *)
    echo "Unknown command line argument or option: $CMD. Skipping."
    shift
    ;;
  esac
done

# We want to start the daemon
if [ "$START" == true ]; then
    
    start_daemon

else

    stop_daemon

fi
