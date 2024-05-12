import argparse
import logging

import sc2_data
import spreadsheet
import exporter

logger = logging.getLogger(__name__)


def configure_logger(level: int = logging.WARNING) -> None:
    logging.basicConfig(format='%(levelname)-8s %(filename)s:%(lineno)-4d %(message)s', level=level)


def main(args: argparse.Namespace) -> None:
    loaded_data = sc2_data.load_game_data()
    towers = loaded_data.towers
    sends = loaded_data.sends
    waves = loaded_data.waves
    abils = loaded_data.abils

    spreadsheet.output_unit_statistics(towers, sends, waves, abils)
    exporter.export_units(towers, 'towers.json')
    exporter.export_units(sends, 'sends.json')
    exporter.export_units(waves, 'waves.json')
    exporter.export_abils(abils, 'abils.json')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--ll', dest='log_level', default='INFO', help='Set the logging level')
    arguments = parser.parse_args()
    configure_logger(arguments.log_level)
    main(arguments)
