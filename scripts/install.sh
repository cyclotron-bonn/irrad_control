#!/bin/bash

function usage {
    echo "usage: $0 [-s|--server -u|--update -icu|--ic_update -nv|--no_venv]
                    [-vp|--venv_path=VENV_PATH]
                    [-icp|--ic_path=PATH]
                    [-icb|--ic_branch=BRANCH_NAME]"

    echo "  -s|--server                   Perform an irrad_server install"
    echo "  -u|--update                   Update pip and packages"
    echo "  -nv|--no_venv                 Do not create a virtual Python environment under $VENV_PATH"
    echo "  -vp|--venv_path=VENV_PATH     Specify path for virtual environment; if given, venv is used to create if it does not exist (default: $IRRAD_PATH/.venv)"
    echo "  -icu|--ic_update              Update code on current branch to origin"
    echo "  -icp|--ic_path=PATH           Specifiy the path of existing irrad_control package (default: $PWD)"
    echo "  -icb|--ic_branch=BRANCH_NAME  Specify the respective branch of irrad_control"
    exit 1
}

function create_server_start_script {
  echo "Create irrad_sever start script"
  START_SCRIPT=${IRRAD_PATH}/scripts/start_server.sh
  # Create empty file; if it already exists, clear contents
  echo -n >$START_SCRIPT
  if [ "$USE_VENV" == true ]; then
    echo "source ${VENV_PATH}/bin/activate" >> $START_SCRIPT
  fi
  echo "irrad_control --server" >> $START_SCRIPT 
}

function read_requirements {
  
  while IFS= read -r line; do
    # Read package and remove comments and whitespaces
    PKG=$(echo "$line" | cut -f1 -d"#" | xargs)
    REQ_PKGS+=("$PKG")
  done < $REQ_FILE
}

# Function to install and update packages
function pip_installer {

  # Get array of packages in env
  ENV_PKGS=$(python -m pip list | awk '/-/{p++;if(p==1){next}}p{print $1}')

  if $PIP_UPDATE; then

    echo 'Updating pip'

    # Update pip and packages
    python -m pip install --upgrade pip
    python -m pip install --upgrade $ENV_PKGS
    
  fi
  
  # Checking for required packages
  echo "Checking for required packages..."

  # Check if irrad_control is already installed in this env
  if [[ ! "{$ENV_PKGS[@]}" =~ "irrad-control" ]]; then
    IRRAD_INSTALL=true
  fi

  # Loop over required packages and check if current env contains them
  MISS_PKGS=()
  for REQ in "${REQ_PKGS[@]}"; do

    # As soon as one of the packages is missing, just install all and break
    if [[ ! "{$ENV_PKGS[@]}" =~ "${REQ}" ]]; then
      MISS_PKGS+=("$REQ")
    fi
  done

  # Install everything we need
  if [[ ! "${#MISS_PKGS[@]}" -eq 0 ]]; then

      # List all packages separated by whitespace and remove leading /trainling whitespace
      TO_BE_INSTALLED=$(echo "${MISS_PKGS[@]/#/}" "$1"| xargs)
      
      echo "Installing missing required packages" $TO_BE_INSTALLED
      
      # Upgrade pip and install needed packages from pip
      python -m pip install $TO_BE_INSTALLED
  else
    echo "All required packages are installed."
  fi

  echo "Environment is set up."

}

# Needed variables
IRRAD_PATH=$PWD
VENV_PATH=$IRRAD_PATH/.venv
USE_VENV=true
IRRAD_SERVER=false
PIP_UPDATE=false
IRRAD_URL="https://github.com/Cyclotron-Bonn/irrad_control"
IRRAD_BRANCH=false
IRRAD_PULL=false
IRRAD_INSTALL=false
REQ_PKGS=()

# Parse command line arguments
for CMD in "$@"; do
  case $CMD in
    # Branch in which installation goes
    -h|--help)
    usage
    ;;
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
    -nv|--no_venv)
    USE_VENV=false
    shift
    ;;
    # Set path to existing irrad_control / prefix to where it is installed
    -icp=*|--ic_path=*)
    IRRAD_PATH="${CMD#*=}"
    shift
    ;;
    # Checkout branch of irrad_control
    -icb=*|--ic_branch=*)
    IRRAD_BRANCH="${CMD#*=}"
    shift
    ;;
    # Pull new changes from origin
    -icu|--ic_update)
    IRRAD_PULL=true
    shift
    ;;
    # Conda env in which installation goes
    -vp=*|--venv_path=*)
    VENV_PATH="${CMD#*=}"
    shift
    ;;
    # Unknown option
    *)
    echo "Unknown command line argument or option: $CMD. Skipping."
    shift
    ;;
  esac
done

# Check for git installation
if git --version &>/dev/null; then
  :
else
  echo "Installing Git..."
  sudo apt-get install git
fi

# Set requirements file
if [[ "$IRRAD_SERVER" != false ]]; then
  REQ_FILE=$IRRAD_PATH/requirements_server.txt
else
  REQ_FILE=$IRRAD_PATH/requirements.txt
fi

# Get irrad_control software
if [ ! -d "$IRRAD_PATH" ]; then

  echo "irrad_control not found. Collecting irrad_control from $IRRAD_URL"

  # Clone into IRRAD_PATH
  git clone $IRRAD_URL $IRRAD_PATH
else
  if [ ! -f $REQ_FILE ]; then
    echo "$PWD not valid irrad_control path; \"$(basename $REQ_FILE)\" at $REQ_FILE missing!"
    exit 1
  else
    echo "Found irrad_control at $IRRAD_PATH"
  fi
fi

if [ "$IRRAD_BRANCH" != false ]; then
  cd $IRRAD_PATH && git checkout $IRRAD_BRANCH
fi

if [ "$IRRAD_PULL" != false ]; then
  cd $IRRAD_PATH && git pull
fi

read_requirements

# Miniconda is not installed; download and install
if [ "$USE_VENV" == true ]; then

  if [ ! -d "$VENV_PATH" ]; then
  
    echo "Missing virtual Python environment at $VENV_PATH! Setting up..."

    # Create venv using specified Python executable
    python -m venv $VENV_PATH

    # Update conda and packages
    PIP_UPDATE=true
  fi
  source $VENV_PATH/bin/activate
fi

# Install everything using pip
pip_installer

# Install irrad_control if necessarry
if [ "$IRRAD_INSTALL" != false ]; then
  if [ "$IRRAD_SERVER" != false ]; then
    echo "Installing irrad_server into $CONDA_ENV_NAME environment..."
    cd $IRRAD_PATH && python setup.py develop server
    create_server_start_script
    # Enable the pigpio deamon on boot
    sudo systemctl enable pigpiod.service
  else
    echo "Installing irrad_control into $CONDA_ENV_NAME environment..."
    python -m pip install -e $IRRAD_PATH
  fi
fi

# Check if we have the pigpio deamon running if we are on a server
# 'pigs t' returns u32 of amount of ticks (in µs) which have passed since boot (overflows within ~ 1h12m)
# If second statement evaluates to 'true' it is any number
if [ "$IRRAD_SERVER" == true ] && [[ ! $(sudo pigs t) =~ ^[0-9]+$ ]]; then
  echo "Starting pigpio daemon"
  sudo pigpiod
fi
