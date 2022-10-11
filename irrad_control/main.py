import sys
import argparse
import importlib
import logging


# Package imports
import irrad_control

# If we are not on a server, the requirements are not installed and we cannot run a server process
_procs = {proc: None for proc in ('gui', 'converter', 'server')}
for proc in _procs:
    try:
        _procs[proc] = importlib.import_module(f'irrad_control.processes.{proc}')
    except (ImportError, ModuleNotFoundError) as e:
        logging.debug(f"'irrad_control --{proc}' not available: {e.msg}!")

if all(val is None for _, val in _procs.items()):
    raise RuntimeError("No process from irrad_control could be imported. Check installation!")

def main():

    # Create parser
    process_parser = argparse.ArgumentParser(description="Start irrad_control process")

    # Add group of processes to run
    process_group = process_parser.add_mutually_exclusive_group()

    process_group.add_argument('--gui', required=False, action='store_true')
    process_group.add_argument('--server', required=False, action='store_true')
    process_group.add_argument('--converter', required=False, action='store_true')
    process_group.add_argument('--version', required=False, action='store_true')  # Get irrad_control version
    
    # Actually parse the guy 
    parsed = vars(process_parser.parse_args(sys.argv[1:]))

    # Default is to launch the GUI
    if all(not val for _, val in parsed.items()):
        parsed['gui'] = True

    if parsed['version']:
        print(f'irrad_control {irrad_control.__version__}')

    elif parsed['gui']:
        if _procs['gui'] is None:
            logging.error(f"'irrad_control --gui' not available!")
            return
        _procs['gui'].run()

    elif parsed['converter']:
        if _procs['converter'] is None:
            logging.error(f"'irrad_control --converter' not available!")
            return
        _procs['converter'].run()

    elif parsed['server']:
        if _procs['server'] is None:
            logging.error(f"'irrad_control --server' not available!")
            return
        _procs['server'].run()


if __name__ == '__main__':
    main()