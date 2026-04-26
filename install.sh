#!/bin/bash

#####################################################################
######################## Global variables ###########################
#####################################################################
INPUT_ARGS="$@"
# Git-related
REPO_PATH=$PWD
REPO_URL="https://github.com/cyclotron-bonn/irrad_control"
REPO_BRANCH=false
REPO_UPDATE=true
# Python-related
VENV_PATH=$REPO_PATH/.venv
USE_VENV=true
HAS_PY=false
HAS_PY3=false
PYTHON_CMD="python"
PIP_CMD="pip"
PIP_UPDATE=false
# Irrad-control
IRRAD_INSTALL=false
IRRAD_SERVER=false

#####################################################################
###################### Function definitons ##########################
#####################################################################

# Display help message
function usage {
  echo "usage: $0 [-s|--server -u|--update -icu|--ic-update -nv|--no-venv]
                    [-icp|--ic-path=PATH]
                    [-icb|--ic-branch=BRANCH_NAME]"

  echo "  -s|--server                   Perform an irrad_server install (selected: $IRRAD_SERVER)"
  echo "  -u|--update                   Update pip and packages (selected: $PIP_UPDATE)"
  echo "  -nv|--no-venv                 Do not create a virtual Python environment (selected: venv at $VENV_PATH)"
  echo "  -icu|--ic-update              Update code on current branch to origin (selected: $REPO_UPDATE)"
  echo "  -icp|--ic-path=PATH           Specifiy the path of existing irrad_control package (selected: $REPO_PATH)"
  echo "  -icb|--ic-branch=BRANCH_NAME  Specify the respective branch of irrad_control (selected: $REPO_BRANCH)"
  exit 0
}


function parse_args () {
  # Parse command line arguments
  for CMD in $INPUT_ARGS; do
    case $CMD in
      # Install everything on a server
      -s|--server)
      IRRAD_SERVER=true
      shift
      ;;
      # Update conda
      -u|--update)
      PIP_UPDATE=true
      shift
      ;;
      # Update conda
      -nv|--no-venv)
      USE_VENV=false
      shift
      ;;
      # Set path to existing irrad_control / prefix to where it is installed
      -icp=*|--ic-path=*)
      REPO_PATH=$(realpath -m "${CMD#*=}")
      VENV_PATH=$REPO_PATH/.venv
      shift
      ;;
      # Checkout branch of irrad_control
      -icb=*|--ic-branch=*)
      REPO_BRANCH="${CMD#*=}"
      shift
      ;;
      # Pull new changes from origin
      -icu|--ic-update)
      REPO_PULL=true
      shift
      ;;
      # Branch in which installation goes
      -h|--help)
      usage
      ;;
      # Unknown option
      *)
      echo "Unknown command line argument or option: $CMD. Skipping."
      shift
      ;;
    esac
  done
}


# Function to check if a given command is available.
# Command to be checked is first argument i.e. $1.
# Usage: if [[ -z $(check_command_exists cmd_to_probe) ]]; then <cmd_to_probe does not exist>
# See https://stackoverflow.com/questions/592620/how-can-i-check-if-a-program-exists-from-a-bash-script
function check_command_exists () {
  cmd_to_probe=$1
  if ! command -v $cmd_to_probe >/dev/null 2>&1; then
    echo "Command $cmd_to_probe does not exist!"
  fi
}


function verify_py3 () {
  py_cmd=$1
  if [[ "$($py_cmd -c 'import sys; print(sys.version_info.major)')" -lt "3" ]]; then
    echo "Python version 3.X is required to install!"
  fi 
}


# Function to check that python and git are available
function check_prerequisites () {
  # Check if Python exists
  if [[ -z $(check_command_exists python) ]]; then
    if [[ -z $(verify_py3 python) ]]; then
      HAS_PY=true
    fi
  fi
  # Check if Python3 exists
  if [[ -z $(check_command_exists python3) ]]; then
    if [[ -z $(verify_py3 python3) ]]; then
      HAS_PY3=true
    fi
  fi
  # Exit if missing python entirely
  if ! ($HAS_PY || $HAS_PY3); then  
    echo "Python installation is required but 'python' not found!"
    exit 1
  fi
  # Check if git exists
  if ! [[ -z $(check_command_exists git) ]]; then
    echo "Git installation is required but 'git' not found!"
    exit 1
  fi
  # Check if realpath exists
  if ! [[ -z $(check_command_exists realpath) ]]; then
    echo "Realpath is required but 'realpath' not found!"
    exit 1
  fi
  # Server install needs to use sudo privileges without prompting user input
  if $IRRAD_SERVER; then
    if ! sudo -n true 2>/dev/null; then
      echo "Server install requires non-interactive sudo privileges"
      exit 1
    fi
  fi
}


# Function that sets the correct python command.
function set_py_command () {
  if $HAS_PY; then
    PYTHON_CMD="python"
  else
    PYTHON_CMD="python3"
  fi
}


# Function that sets the correct pip command.
# It either uses the pip command or pythons module invocation
function set_pip_command () {
  # Check if regular pip exists
  if [[ -z $(check_command_exists pip) ]]; then
    PIP_CMD="pip"
  else
    echo "Pip installation not found, using 'python -m pip' fallback."
    PIP_CMD="$PYTHON_CMD -m pip"
  fi
}


# Function to check whether the provided REPO_PATH is in fact the irrad_control repo
function setup_repo () {
  # If the path does not exist, we have to clone the repo in there
  if ! [[ -d $REPO_PATH ]]; then
    echo "$REPO_PATH does not exist. Cloning irrad_control from $REPO_URL to $REPO_PATH"
    git clone $REPO_URL $REPO_PATH
  # Figure things out
  else
    cd $REPO_PATH
    # Check that the provided REPO_PATH is a git repo
    # If it is a repo, ensure it is irrad_control repo, otherwise exit
    is_git_repo=$(git rev-parse --is-inside-work-tree 2>/dev/null)
    if [[ "$is_git_repo" == "true" ]]; then
      # Check that we are in the correct repo
      remote_url=$(git config --get remote.origin.url)
      if ! [[ "$remote_url" == "$REPO_URL" ]]; then
        echo "Remote repo URL '$remote_url' not irrad_control URL '$REPO_URL'"
        exit 1
      else
        echo "Found irrad_control under $REPO_PATH"
      fi
    # Not a git repo, we have to find irrad_control here or clone it
    else
      # Check if there is an irrad_control folder under $REPO_PATH
      if [[ -d "$REPO_PATH/irrad_control" ]]; then
        cd "$REPO_PATH/irrad_control"
        remote_url=$(git config --get remote.origin.url)
        if ! [[ "$remote_url" == "$REPO_URL" ]]; then
          echo "Remote repo URL '$remote_url' not irrad_control URL '$REPO_URL'"
          exit 1
        else
          echo "Found irrad_control under $REPO_PATH/irrad_control"
          REPO_PATH="$REPO_PATH/irrad_control"
        fi
      # We have to clone irrad_control
      else
        echo "Cloning irrad_control to $REPO_PATH/irrad_control"
        git clone $REPO_URL irrad_control
        REPO_PATH="$REPO_PATH/irrad_control"
      fi
    fi
    # Set REPO_PATH to the top-level repo path
    cd $REPO_PATH
    top_irrad_path=$(git rev-parse --show-toplevel)
    if ! [[ "$top_irrad_path" == "$REPO_PATH" ]]; then
      echo "Setting local repo path to $top_irrad_path"
      REPO_PATH=$top_irrad_path
    fi
  fi
  # Now we have the repo locally
  VENV_PATH=$REPO_PATH/.venv
  cd $REPO_PATH
  # We want to checkout a specific branch
  if [[ $REPO_BRANCH != false ]]; then
    branch=$(git symbolic-ref --short HEAD)
    if [[ "$REPO_BRANCH" != "$branch" ]]; then
      echo "Switching to target branch '$REPO_BRANCH' from '$branch'"
      git checkout "$REPO_BRANCH"
    fi
  fi
  if $REPO_UPDATE; then
    git pull
  fi
}


# Function to check the current Python for installed packages
# Set flag whether to install irrad_control
function setup_python_env () {

  if $USE_VENV; then
    if ! [[ -d $VENV_PATH ]]; then
      echo "Setting up Python environment at $VENV_PATH"
      $PYTHON_CMD -m venv $VENV_PATH
      PIP_UPDATE=true
    fi
    echo "Activating Python environment at $VENV_PATH"
    source $VENV_PATH/bin/activate
  fi
  # We can now set the correct pip command
  set_pip_command
  # Get array of packages in env
  env_pkgs=$($PIP_CMD list | awk '/-/{p++;if(p==1){next}}p{print $1}')
  if $PIP_UPDATE; then
    echo "Updating pip and packages..."
    # Update pip and packages
    $PIP_CMD install --upgrade pip
    $PIP_CMD install --upgrade $env_pkgs
  fi

    # Check if irrad_control is already installed in this env
  if [[ ! "{$env_pkgs[@]}" =~ "irrad_control" ]]; then
    IRRAD_INSTALL=true
  fi
}


function install_editable () {
  if $IRRAD_INSTALL; then
    py_exec=$(which $PYTHON_CMD)
    if $IRRAD_SERVER; then
      echo "Installing irrad_server into $py_exec environment"
      cd $REPO_PATH && $PIP_CMD install -e .[server] 
    else
      echo "Installing irrad_control into $py_exec environment"
      cd $REPO_PATH && $PIP_CMD install -e .[main] 
    fi
  fi
}


function post_install () {
  if $IRRAD_INSTALL; then
    # Post install server actions
    if $IRRAD_SERVER; then
      create_run_server_script
      # Enable the pigpio deamon on boot
      sudo systemctl enable pigpiod.service
    # Main installation currently needs no post install actions
    else
      :  # noop
    fi
  fi  
}


function post_setup () {
  if $IRRAD_SERVER; then
    # Check if we have the pigpio deamon running if we are on a server
    # 'pigs t' returns u32 of amount of ticks (in µs) which have passed since boot (overflows within ~ 1h12m)
    # If second statement evaluates to 'true' it is any number
    if [[ ! $(sudo pigs t) =~ ^[0-9]+$ ]]; then
      echo "Starting pigpio daemon"
      sudo pigpiod
    fi
  # Main installation needs no post setup actions
  else
    :
  fi

}


function create_run_server_script {
  echo "Create irrad_sever start script"
  RUN_SERVER_SCRIPT="$HOME/run_irrad_server.sh"
  # Create empty file; if it already exists, clear contents
  echo -n >$RUN_SERVER_SCRIPT
  if $USE_VENV; then
    echo "source ${VENV_PATH}/bin/activate" >> $RUN_SERVER_SCRIPT
  fi
  echo "irrad_control --server" >> $RUN_SERVER_SCRIPT 
}

#####################################################################
########################### Script start ############################
#####################################################################

# Parse input arguments
parse_args

# Check for Python and git
check_prerequisites

# Set python command
set_py_command

# Setup repo
setup_repo

# Activate (and create) virtual Python environment if needed.
# Update Pyhon packages if needed
setup_python_env

# Irrad control only supports editable install
install_editable

# Post install actions
post_install

# Last actions after script ran through
post_setup
