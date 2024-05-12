"""
Currently used just for loading a txt file. Other actions are performed in sc2_data.py mostly.
We need to define load function here so we can load all text into one place (sc2_data.py),
which can then be used anywhere and properly shared (similar to xml files, but makes more sense to define here)
"""
import pathlib


def load_text_file(file: pathlib.Path) -> dict[str, str]:
    with open(file, 'r', encoding='utf-8-sig') as fp:
        lines = fp.readlines()
        lines = [line.rstrip('\n') for line in lines]
    return dict(line.split('=', 1) for line in lines)
