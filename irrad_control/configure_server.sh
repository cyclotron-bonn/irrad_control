#!/bin/bash
# Setup of RaspberryPi server for the irradiation site

# Function to install and update conda packages
function conda_env_installer {

  # Checking for required packages
  echo "Checking for required packages..."

  # Get list of packages in env
  ENV_PKGS=$(conda list | awk '{print $1}' | while read -r PKG; do if [ "PKG" != "#" ]; then echo "$PKG"; fi; done)

  # Check if irrad_control is already installed in this env
  if [[ ! "{$ENV_PKGS[@]}" =~ "irrad-control" ]]; then
    IRRAD_INSTALL=true
  fi

  # Loop over required packages and check if current env contains them
  for REQ in "${REQ_PKGS[@]}"; do

    # As soon as one of the packages is missing, just install all and break
    if [[ ! "{$ENV_PKGS[@]}" =~ "${REQ}" ]]; then
      
      # Install everything we need
      
      echo 'Installing packages...'

      # Install python packages
      conda config --set always_yes yes
      conda install pyzmq pip pyyaml
      
      # Upgrade pip and install needed packages from pip
      pip install --upgrade pip
      pip install wiringpi zaber.serial
      
      break
    fi
  done

  if $CONDA_UPDATE; then

    echo 'Updating conda and packages...'

    # Update conda and packages
    conda update conda && conda update --all
  fi

}

# Needed variables
IRRAD_PATH=$HOME/irrad_control
PY_VERSION=false
CONDA_UPDATE=false
IRRAD_URL="https://github.com/SiLab-Bonn/irrad_control"
IRRAD_BRANCH=false
IRRAD_PULL=false
IRRAD_INSTALL=false
REQ_PKGS=(pyzmq pyyaml pip wiringpi zaber.serial)

# Parse command line arguments
for CMD in "$@"; do
  case $CMD in
    # Get Python version to use
    -v=*|--version=*)
    PY_VERSION="${CMD#*=}"
    shift
    ;;
    # Update conda
    -u|--update)
    CONDA_UPDATE=true
    shift
    ;;
    # Checkout branch of irrad_control
    -b=*|--branch=*)
    IRRAD_BRANCH="${CMD#*=}"
    shift
    ;;
    # Pull new changes from origin
    -p|--pull)
    IRRAD_PULL=true
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

  echo "Collecting irrad_control"

  # Clone into IRRAD_PATH
  git clone $IRRAD_URL $IRRAD_PATH

fi

if [ "$IRRAD_BRANCH" != false ]; then
  cd $IRRAD_PATH && git checkout $IRRAD_BRANCH
fi

if [ "$IRRAD_PULL" != false ]; then
  cd $IRRAD_PATH && git pull
fi

# Loop over Python versions to check if respective miniconda installation exists
MINICONDA_PATH=false
for PY_V in {2,3}; do
  if [ -d "$MINICONDA_BASE$PY_V" ]; then
    MINICONDA_PATH=$MINICONDA_BASE$PY_V
    break
  fi
done

# Get Python version from command line arg
if [ "$PY_VERSION" == false ]; then
  PY_VERSION=3
  echo "No Python version specified; using Python ${PY_VERSION}"
fi

# Miniconda is not installed; download and install
if [ "$MINICONDA_PATH" == false ]; then
  
  echo "Server missing Miniconda. Setting up Python ${PY_VERSION} environment..."
  
  # Update Miniconda path variable
  MINICONDA_PATH=$MINICONDA_BASE$PY_VERSION

  # Miniconda dist for RaspberryPi2/3 url using Python VERSION
  MINICONDA="https://github.com/jjhelmus/berryconda/releases/download/v2.0.0/Berryconda${PY_VERSION}-2.0.0-Linux-armv7l.sh"
  
  # Get Berryconda as miniconda
  echo "Getting Berryconda from ${MINICONDA}"
  wget --tries 0 --waitretry 5 $MINICONDA -O miniconda.sh
  chmod +x miniconda.sh
  
  # Install miniconda
  bash miniconda.sh -b -p $MINICONDA_PATH
  rm miniconda.sh
  
  # Activate Python environ
  echo 'export PATH="$HOME/miniconda'${PY_VERSION}'/bin:$PATH"' >> $HOME/.bashrc
  source $MINICONDA_PATH/bin/activate
  
  # Update conda and packages
  CONDA_UPDATE=true
  
  # Let's install all the stuff
  conda_env_installer

  echo "Miniconda Python $PY_VERSION environment set up!"

  # Create server start script for server
  echo "source ${MINICONDA_PATH}/bin/activate; irrad_server" > ${HOME}/start_irrad_server.sh

else
  
  # Source that bad boy
  source $MINICONDA_PATH/bin/activate
  
  # Check if we got the correct Python version
  CURR_PY_VERSION=$(python -c 'import sys; print(sys.version_info[0])')
  
  # Check
  echo "Checking existing Python $CURR_PY_VERSION environment at $MINICONDA_PATH..."
  
  # Check whether we want that verion of Python; if not; check envs and create new if neccessary
  if [ "$CURR_PY_VERSION" == "$PY_VERSION" ]; then
    
    conda_env_installer
    
    echo "Environment is set up."

    # Create server start script for server
    echo "source ${MINICONDA_PATH}/bin/activate; irrad_server" > ${HOME}/start_irrad_server.sh
    
  else
    # We don't have the correct version of Python; check for envs
    if [ ! -d "$MINICONDA_PATH/envs" ]; then
      
      echo "Creating new Python $PY_VERSION environment py${PY_VERSION}..."

      # Create new environment with respective Python version and activate
      conda create -n py$PY_VERSION python=$PY_VERSION && conda activate py$PY_VERSION

      # Update conda and packages
      CONDA_UPDATE=true

      # Install packages
      conda_env_installer

      # Create server start script for server
      echo "source ${MINICONDA_PATH}/bin/activate; conda activate py${PY_VERSION}; irrad_server" > ${HOME}/start_irrad_server.sh

    else

      echo "Looking for existing Python environment matching Python version ${PY_VERSION}..."

      # Store matching environment
      MATCH_ENV=false
      
      # Loop over envs and check if they have the correct Python version; fancy shit: pipes in subshell to keep local variable values
      while read -r ENV; do
        if [ "$ENV" == "#" ]; then
          continue
        else
          # Activate env and check py version
          conda activate $ENV

          # Get envs Python version
          ENV_PY_VERSION=$(python -c 'import sys; print(sys.version_info[0])')
          
          if [ "$ENV_PY_VERSION" == "$PY_VERSION" ]; then
            MATCH_ENV=$ENV
            break
          fi
        fi
      done < <(conda-env list | awk '{print $1}')
      
      # Check if we got a matching environment; if not, create
      if [ "$MATCH_ENV" == false ]; then
        
        echo "No environment matches Python version ${PY_VERSION}. Creating new environment py${PY_VERSION}..."
        # Create new environment with respective Python version and activate
        conda create -n py$PY_VERSION python=$PY_VERSION && conda activate py$PY_VERSION

        # Update conda and packages
        CONDA_UPDATE=true
        
        # Install packages
        conda_env_installer

        # Create server start script for server
        echo "source ${MINICONDA_PATH}/bin/activate; conda activate py${PY_VERSION}; irrad_server" > ${HOME}/start_irrad_server.sh

      else

        echo "$MATCH_ENV matches required Python version ${PY_VERSION}."
        # Activate matching environment and install required packages
        conda activate $MATCH_ENV && conda_env_installer

        echo "Environment is set up."

        # Create server start script for server
        echo "source ${MINICONDA_PATH}/bin/activate; conda activate ${MATCH_ENV}; irrad_server" > ${HOME}/start_irrad_server.sh
      fi
    fi
  fi
fi

# Install irrad_control if necessarry
if [ "$IRRAD_INSTALL" != false ]; then
  echo "Installing irrad_control for Python $PY_VERSION environment..."
  cd $IRRAD_PATH && python setup.py develop server
fi
