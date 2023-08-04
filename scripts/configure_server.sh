#!/bin/bash
# Setup of RaspberryPi server for the irradiation site

function create_start_script {
  echo "Create irrad_sever start script"
  START_SCRIPT=${IRRAD_PATH}/scripts/start_server.sh
  # Create empty file; if it already exists, clear contents
  echo -n >$START_SCRIPT
  echo "source ${MAMBAFORGE_PATH}/etc/profile.d/conda.sh" >> $START_SCRIPT
  echo "conda activate $CONDA_ENV_NAME" >> $START_SCRIPT
  echo "irrad_control --server" >> $START_SCRIPT 
}

function source_conda {
  # Activate conda
  source "${MAMBAFORGE_PATH}/etc/profile.d/conda.sh"
}

function read_requirements {

  if [[ "$IRRAD_SERVER" != false ]]; then
    REQ_FILE=$IRRAD_PATH/requirements_server.txt
  else
    REQ_FILE=$IRRAD_PATH/requirements.txt
  fi
  
  while IFS= read -r line; do
    # Read package and remove comments and whitespaces
    PKG=$(echo "$line" | cut -f1 -d"#" | xargs)
    REQ_PKGS+=("$PKG")
  done < $REQ_FILE
}

# Function to install and update packages
function env_installer {

  echo "Checking for environment $CONDA_ENV_NAME"

  ENVS=$(conda env list | awk '{print $1}' | while read -r ENV; do if [ "$ENV" != "#" ]; then echo "$ENV"; fi; done)

  if [[ ! "{$ENVS[@]}" =~ $CONDA_ENV_NAME ]]; then
    echo "Not found. Creating environment $CONDA_ENV_NAME..."
    conda create -n $CONDA_ENV_NAME Python=3.9 -y
  else
    echo "Found environment $CONDA_ENV_NAME."
  fi

  conda activate $CONDA_ENV_NAME
  
  # Checking for required packages
  echo "Checking for required packages..."

  # Get list of packages in env
  ENV_PKGS=$(conda list | awk '{print $1}' | while read -r PKG; do if [ "$PKG" != "#" ]; then echo "$PKG"; fi; done)

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
      pip install --upgrade pip
      pip install $TO_BE_INSTALLED
  else
    echo "All required packages are installed."
  fi

  if $CONDA_UPDATE; then

    echo 'Updating conda'

    # Update mamba and packages
    conda update -n base -c conda-forge conda -y
  fi

  echo "Environment is set up."

}

# Needed variables
MAMBAFORGE_PATH=$HOME/mambaforge
MAMBAFORGE="https://github.com/conda-forge/miniforge/releases/latest/download/Mambaforge-$(uname)-$(uname -m).sh"
IRRAD_PATH=$HOME/irrad_control
IRRAD_SERVER=false
CONDA_UPDATE=false
CONDA_ENV_NAME="irrad-control"
IRRAD_URL="https://github.com/Cyclotron-Bonn/irrad_control"
IRRAD_BRANCH=false
IRRAD_PULL=false
IRRAD_INSTALL=false
REQ_PKGS=()

# Parse command line arguments
for CMD in "$@"; do
  case $CMD in
    # Install everything on a server
    -s|--server)
    IRRAD_SERVER=true
    shift
    ;;
    # Update conda
    -u|--update)
    CONDA_UPDATE=true
    shift
    ;;
    # Checkout branch of irrad_control
    -p=*|--path=*)
    IRRAD_PATH="${CMD#*=}"
    shift
    ;;
    # Checkout branch of irrad_control
    -b=*|--branch=*)
    IRRAD_BRANCH="${CMD#*=}"
    shift
    ;;
    # Pull new changes from origin
    -gp|--git_pull)
    IRRAD_PULL=true
    shift
    ;;
    # Branch in which installation goes
    -ce=*|--conda_env=*)
    CONDA_ENV_NAME="${CMD#*=}"
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

# Get irrad_control software
if [ ! -d "$IRRAD_PATH" ]; then

  echo "irrad_control not found. Collecting irrad_control from $IRRAD_URL"

  # Clone into IRRAD_PATH
  git clone $IRRAD_URL $IRRAD_PATH
else
  echo "Found irrad_control at $IRRAD_PATH"
fi

if [ "$IRRAD_BRANCH" != false ]; then
  cd $IRRAD_PATH && git checkout $IRRAD_BRANCH
fi

if [ "$IRRAD_PULL" != false ]; then
  cd $IRRAD_PATH && git pull
fi

read_requirements

# Miniconda is not installed; download and install
if [ ! -d "$MAMBAFORGE_PATH" ]; then
  
  echo "Server missing Python environment! Setting up environment..."
  
  # Get mambaforge
  echo "Getting mambaforge from ${MAMBAFORGE}"
  wget -O Mambaforge.sh $MAMBAFORGE
  
  # Install miniconda
  bash Mambaforge.sh -b -p $MAMBAFORGE_PATH
  rm Mambaforge.sh
  
  source_conda
  
  # Update conda and packages
  CONDA_UPDATE=true
  
  # Let's install all the stuff
  env_installer

else
  source_conda
  # Let's install all the stuff
  env_installer
fi

# Install irrad_control if necessarry
if [ "$IRRAD_INSTALL" != false ]; then
  if [ "$IRRAD_SERVER" != false ]; then
    echo "Installing irrad_server into $CONDA_ENV_NAME environment..."
    cd $IRRAD_PATH && python setup.py develop server
    create_start_script
  else
    echo "Installing irrad_control into $CONDA_ENV_NAME environment..."
    pip install -e $IRRAD_PATH
  fi
fi
