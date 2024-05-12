import json
import logging
import typing
import pathlib
import dataclasses
import copy

import jsondiff # type: ignore

import sc2_data


logger = logging.getLogger(__name__)


def prep_towers(towers: dict[str, sc2_data.Tower]) -> dict[str, sc2_data.Tower]:
    """
    update upgrades and predecessors to be using lowercase name rather than id
    """
    towers_c = copy.deepcopy(towers)
    for v in towers_c.values():
        v.upgrades = [towers_c[u].name.lower() for u in v.upgrades]
        v.predecessors = [towers_c[p].name.lower() for p in v.predecessors]
    return towers_c


def write_to_json(data: typing.Any, filepath: str) -> None:
    try:
        try:
            with open(filepath, 'r') as fr:
                old = json.load(fr)
        except FileNotFoundError as e:
            with open(filepath, 'w') as fw:
                json.dump(data, fw, indent=4)
                logger.info('Writing to %s', filepath)
                return
        if len(jsondiff.diff(old, data)) > 0:
            with open(filepath, 'w') as fp:
                json.dump(data, fp, indent=4)
                logger.info('Writing to %s', filepath)
    except OSError as e:
        logger.error('Failed to write %s, %s', filepath, e)


def export_units(units: dict[str, typing.Any], filename: str) -> None:
    ref = units
    if 'towers' in filename:
        ref = prep_towers(units)
    filepath = str(pathlib.Path(__file__).parent.parent / f'output/json/{filename}')
    unit_list = [dataclasses.asdict(unit) for unit in ref.values()]
    # for users probably best to put key as lowercase name rather than id
    json_data = {key: value for key, value in zip([unit.name.lower() for unit in ref.values()], unit_list)}
    write_to_json(json_data, filepath)


def export_abils(abils: dict[str, sc2_data.Ability], filename: str) -> None:
    filepath = str(pathlib.Path(__file__).parent.parent / f'output/json/{filename}')
    abil_list = [dataclasses.asdict(abil) for abil in abils.values()]
    json_data = {key: value for key, value in zip([abil.name.lower() for abil in abils.values()], abil_list)}
    write_to_json(json_data, filepath)
