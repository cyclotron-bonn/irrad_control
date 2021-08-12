import os
import yaml


__all__ = ['location', 'make_path', 'safe_yaml', 'load_yaml']


def location(f):
    return os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(f)))


def make_path(*args):
    return os.path.join(*args)


def load_yaml(path):

    with open(path, 'r') as _a:
        _b = yaml.safe_load(_a)

    return _b


def safe_yaml(path, data):

    with open(path, 'w') as _a:
        yaml.safe_dump(data, _a)
