import sys
import argparse
import importlib
import logging


# Package imports
import irrad_control


def _load_irrad_control_process(proc):
    try:
        return importlib.import_module(f'irrad_control.processes.{proc}')
    except (ImportError, ModuleNotFoundError) as e:
        logging.error(f"'irrad_control --{proc}' not available: {e.msg}!")


def _run_irrad_control_process(proc):
    actual_proc = _load_irrad_control_process(proc=proc)
    if actual_proc is None:
        logging.error(f"'irrad_control --{proc}' not available!")
        return
    actual_proc.run()


def main():

    # Create parser
    process_parser = argparse.ArgumentParser(description="Start irrad_control process")

    # Add group of processes to run
    process_group = process_parser.add_mutually_exclusive_group()

    process_group.add_argument('--gui', required=False, action='store_true')
    process_group.add_argument('--monitor', required=False, action='store_true')
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
        _run_irrad_control_process(proc='gui')
    
    elif parsed['monitor']:
        _run_irrad_control_process(proc='monitor')

    elif parsed['converter']:
        _run_irrad_control_process(proc='converter')

    elif parsed['server']:
        _run_irrad_control_process(proc='server')


if __name__ == '__main__':
    main()